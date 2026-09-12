# ruff: noqa: E501
"""PostgreSQL authority adapters for browser identity and exact grants."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from psycopg import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.authority_configuration import validate_registered_grant
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    ContinuationClaim,
    CredentialId,
    DynamicAuthorizationState,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
    SessionId,
    TrustedRequestContext,
    VerifiedPrincipal,
    require_bounded_label,
)

ADAPTER = "browser-session-grant-authority-postgresql-v18"
MIGRATION_VERSION = 18


class PostgresAuthorityRepository:
    def __init__(
        self, database_url: str, *, migration_path: Path, timeout: float = 5.0
    ) -> None:
        if not database_url:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        pool = None
        try:
            pool = ConnectionPool(
                database_url,
                min_size=1,
                max_size=4,
                timeout=timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
                open=True,
            )
            pool.wait(timeout=timeout)
            self.pool = pool
        except Exception as exc:
            if pool is not None:
                pool.close()
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    @contextmanager
    def connection_scope(self, connection=None):
        if connection is not None:
            yield connection
        else:
            with self.pool.connection() as owned, owned.transaction():
                yield owned

    def migrate(self) -> None:
        if self.migration_path.name[:4] != "0018":
            raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout='30s'")
                connection.execute("SET LOCAL lock_timeout='3s'")
                connection.execute(self.migration_path.read_text())
                for schema in ("browser_identity", "authorization_admin"):
                    newer = connection.execute(
                        f"SELECT version FROM {schema}.schema_migrations "
                        "WHERE version>%s ORDER BY version LIMIT 1",
                        (MIGRATION_VERSION,),
                    ).fetchone()
                    if newer is not None:
                        raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
                    row = connection.execute(
                        f"SELECT checksum,adapter FROM {schema}.schema_migrations "
                        "WHERE version=%s",
                        (MIGRATION_VERSION,),
                    ).fetchone()
                    expected = {"checksum": self.migration_checksum, "adapter": ADAPTER}
                    if row is None:
                        connection.execute(
                            f"INSERT INTO {schema}.schema_migrations"
                            "(version,checksum,adapter) VALUES(%s,%s,%s)",
                            (MIGRATION_VERSION, self.migration_checksum, ADAPTER),
                        )
                    elif row != expected:
                        raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
        except AuthorityError:
            raise
        except (OSError, PsycopgError) as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def close(self) -> None:
        self.pool.close()

    @staticmethod
    def _audit(
        connection,
        *,
        event_type: str,
        actor_id: str,
        outcome: str,
        reason: str,
        occurred_at: datetime,
        scope: AuthorityScope | None = None,
        subject_id: str | None = None,
        generation: int | None = None,
        recovery_epoch: int | None = None,
    ) -> None:
        semantic = {
            "eventType": event_type,
            "actorId": actor_id,
            "scope": (
                [scope.tenant_id, scope.security_domain] if scope is not None else None
            ),
            "subjectId": subject_id,
            "generation": generation,
            "recoveryEpoch": recovery_epoch,
            "outcome": outcome,
            "reason": reason,
            "occurredAt": occurred_at.isoformat(),
        }
        digest = hashlib.sha256(
            json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            "INSERT INTO authorization_admin.audit_events"
            "(event_id,event_type,actor_id,tenant_id,security_domain,subject_id,"
            "generation,recovery_epoch,outcome,reason_category,event_digest,occurred_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                f"authority-audit-{secrets.token_hex(16)}",
                event_type,
                actor_id,
                scope.tenant_id if scope else None,
                scope.security_domain if scope else None,
                subject_id,
                generation,
                recovery_epoch,
                outcome,
                reason,
                digest,
                occurred_at,
            ),
        )

    def issue_login_nonce(self, digest: str, expires_at: datetime) -> None:
        try:
            with self.connection_scope() as connection:
                connection.execute(
                    "INSERT INTO browser_identity.login_nonces"
                    "(nonce_digest,expires_at) VALUES(%s,%s)",
                    (digest, expires_at),
                )
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def consume_login_nonce(self, digest: str, *, now: datetime) -> bool:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "UPDATE browser_identity.login_nonces SET consumed_at=%s "
                    "WHERE nonce_digest=%s AND consumed_at IS NULL AND expires_at>%s "
                    "RETURNING nonce_digest",
                    (now, digest, now),
                ).fetchone()
                return row is not None
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _insert_session(connection, session: BrowserSession, digest: str) -> None:
        connection.execute(
            "INSERT INTO browser_identity.sessions"
            "(session_id,secret_digest,principal_id,tenant_id,security_domain,"
            "credential_id,credential_expires_at,authentication_policy_version,"
            "issued_at,last_seen_at,idle_expires_at,absolute_expires_at,"
            "recovery_epoch,authority_generation) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                session.session_id,
                digest,
                session.principal.principal_id,
                session.principal.scope.tenant_id,
                session.principal.scope.security_domain,
                session.principal.credential_id,
                session.principal.credential_expires_at,
                session.principal.policy_version,
                session.issued_at,
                session.last_seen_at,
                session.idle_expires_at,
                session.absolute_expires_at,
                session.recovery_epoch,
                session.generation,
            ),
        )

    def create_session(self, session: BrowserSession, secret_digest: str) -> None:
        try:
            with self.connection_scope() as connection:
                self._insert_session(connection, session, secret_digest)
                self._audit(
                    connection,
                    event_type="SESSION_CREATED",
                    actor_id=session.principal.principal_id,
                    outcome="COMMITTED",
                    reason="AUTHENTICATED",
                    occurred_at=session.issued_at,
                    scope=session.principal.scope,
                    subject_id=session.session_id,
                    generation=session.generation,
                    recovery_epoch=session.recovery_epoch,
                )
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _session(row: dict[str, Any]) -> BrowserSession:
        return BrowserSession(
            session_id=SessionId(row["session_id"]),
            principal=VerifiedPrincipal(
                principal_id=row["principal_id"],
                scope=AuthorityScope(row["tenant_id"], row["security_domain"]),
                credential_id=CredentialId(row["credential_id"]),
                credential_expires_at=row["credential_expires_at"],
                policy_version=row["authentication_policy_version"],
            ),
            issued_at=row["issued_at"],
            last_seen_at=row["last_seen_at"],
            idle_expires_at=row["idle_expires_at"],
            absolute_expires_at=row["absolute_expires_at"],
            recovery_epoch=row["recovery_epoch"],
            generation=row["authority_generation"],
        )

    def touch_current_session(
        self,
        secret_digest: str,
        *,
        now: datetime,
        idle_expires_at: datetime,
        recovery_epoch: int,
    ) -> BrowserSession | None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT s.* FROM browser_identity.sessions s "
                    "LEFT JOIN browser_identity.session_revocation_facts r "
                    "ON r.session_id=s.session_id "
                    "WHERE s.secret_digest=%s AND r.session_id IS NULL "
                    "AND s.rotated_to_session_id IS NULL AND s.idle_expires_at>%s "
                    "AND s.absolute_expires_at>%s AND s.credential_expires_at>%s "
                    "AND s.recovery_epoch=%s FOR UPDATE OF s",
                    (secret_digest, now, now, now, recovery_epoch),
                ).fetchone()
                if row is None:
                    return None
                new_idle = min(idle_expires_at, row["absolute_expires_at"])
                row = connection.execute(
                    "UPDATE browser_identity.sessions SET last_seen_at=%s,idle_expires_at=%s "
                    "WHERE session_id=%s RETURNING *",
                    (now, new_idle, row["session_id"]),
                ).fetchone()
                return self._session(row)
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def rotate_session(
        self,
        current_session_id: SessionId,
        replacement: BrowserSession,
        replacement_secret_digest: str,
        *,
        now: datetime,
    ) -> bool:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT s.session_id FROM browser_identity.sessions s "
                    "LEFT JOIN browser_identity.session_revocation_facts r "
                    "ON r.session_id=s.session_id "
                    "WHERE s.session_id=%s AND r.session_id IS NULL "
                    "AND s.rotated_to_session_id IS NULL AND s.idle_expires_at>%s "
                    "AND s.absolute_expires_at>%s FOR UPDATE OF s",
                    (current_session_id, now, now),
                ).fetchone()
                if row is None:
                    return False
                self._insert_session(connection, replacement, replacement_secret_digest)
                connection.execute(
                    "UPDATE browser_identity.sessions SET rotated_to_session_id=%s "
                    "WHERE session_id=%s",
                    (replacement.session_id, current_session_id),
                )
                self._insert_session_revocation(
                    connection,
                    current_session_id,
                    reason="ROTATED",
                    actor_id=replacement.principal.principal_id,
                    now=now,
                )
                self._audit(
                    connection,
                    event_type="SESSION_ROTATED",
                    actor_id=replacement.principal.principal_id,
                    outcome="COMMITTED",
                    reason="ROTATED",
                    occurred_at=now,
                    scope=replacement.principal.scope,
                    subject_id=current_session_id,
                    generation=replacement.generation,
                    recovery_epoch=replacement.recovery_epoch,
                )
                return True
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _insert_session_revocation(
        connection,
        session_id: SessionId,
        *,
        reason: str,
        actor_id: str,
        now: datetime,
    ) -> bool:
        row = connection.execute(
            "INSERT INTO browser_identity.session_revocation_facts"
            "(revocation_id,session_id,reason_category,actor_id,revoked_at) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(session_id) DO NOTHING "
            "RETURNING revocation_id",
            (
                f"session-revocation-{secrets.token_hex(16)}",
                session_id,
                reason,
                actor_id,
                now,
            ),
        ).fetchone()
        return row is not None

    def revoke_session(
        self,
        session_id: SessionId,
        *,
        reason: str,
        actor_id: str,
        now: datetime,
    ) -> bool:
        try:
            with self.connection_scope() as connection:
                current = connection.execute(
                    "SELECT session_id FROM browser_identity.sessions "
                    "WHERE session_id=%s FOR UPDATE",
                    (session_id,),
                ).fetchone()
                if current is None:
                    return False
                inserted = self._insert_session_revocation(
                    connection, session_id, reason=reason, actor_id=actor_id, now=now
                )
                if inserted:
                    self._audit(
                        connection,
                        event_type="SESSION_REVOKED",
                        actor_id=actor_id,
                        outcome="COMMITTED",
                        reason=reason,
                        occurred_at=now,
                        subject_id=session_id,
                    )
                return inserted
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def revoke_credential_sessions(
        self,
        credential_id: CredentialId,
        *,
        reason: str,
        actor_id: str,
        now: datetime,
    ) -> int:
        try:
            with self.connection_scope() as connection:
                rows = connection.execute(
                    "SELECT s.session_id FROM browser_identity.sessions s "
                    "LEFT JOIN browser_identity.session_revocation_facts r "
                    "ON r.session_id=s.session_id "
                    "WHERE s.credential_id=%s AND r.session_id IS NULL FOR UPDATE OF s",
                    (credential_id,),
                ).fetchall()
                count = sum(
                    self._insert_session_revocation(
                        connection,
                        SessionId(row["session_id"]),
                        reason=reason,
                        actor_id=actor_id,
                        now=now,
                    )
                    for row in rows
                )
                self._audit(
                    connection,
                    event_type="CREDENTIAL_SESSIONS_REVOKED",
                    actor_id=actor_id,
                    outcome="COMMITTED",
                    reason=reason,
                    occurred_at=now,
                    subject_id=credential_id,
                )
                return count
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _current_credential_id(
        connection,
        context: TrustedRequestContext,
        *,
        now: datetime,
        recovery_epoch: int,
        lock_session: bool = False,
    ) -> CredentialId | None:
        lock_clause = " FOR SHARE OF s" if lock_session else ""
        if context.authentication_source.value == "SERVICE_CREDENTIAL":
            return CredentialId(context.session_id_or_service_credential_id)
        row = connection.execute(
            "SELECT s.credential_id FROM browser_identity.sessions s "
            "LEFT JOIN browser_identity.session_revocation_facts r "
            "ON r.session_id=s.session_id WHERE s.session_id=%s "
            "AND s.principal_id=%s AND s.tenant_id=%s AND s.security_domain=%s "
            "AND r.session_id IS NULL AND s.rotated_to_session_id IS NULL "
            "AND s.idle_expires_at>%s AND s.absolute_expires_at>%s "
            "AND s.credential_expires_at>%s AND s.recovery_epoch=%s" + lock_clause,
            (
                context.session_id_or_service_credential_id,
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
                now,
                now,
                now,
                recovery_epoch,
            ),
        ).fetchone()
        return CredentialId(row["credential_id"]) if row else None

    def current_credential_id(
        self,
        context: TrustedRequestContext,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> CredentialId | None:
        try:
            with self.connection_scope() as connection:
                return self._current_credential_id(
                    connection, context, now=now, recovery_epoch=recovery_epoch
                )
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def _authorization_read_checkpoint(self) -> None:
        """Test seam after the session read has established the transaction snapshot."""

    def _decision_request_locked_checkpoint(self) -> None:
        """Test seam after a grant decision locks its request aggregate."""

    def _recovery_requests_locked_checkpoint(self) -> None:
        """Test seam after recovery locks every pre-recovery pending request."""

    def read_linearized_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> tuple[CredentialId | None, DynamicAuthorizationState]:
        """Read session and grant state from one PostgreSQL repeatable-read snapshot."""
        credential_id, states = self.read_linearized_authorization_states(
            context,
            (grant,),
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
        )
        return credential_id, states[0]

    def read_linearized_authorization_states(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
        connection=None,
        configure_transaction: bool = True,
    ) -> tuple[CredentialId | None, tuple[DynamicAuthorizationState, ...]]:
        """Read one session and an exact grant bundle in the caller transaction."""
        if not grants:
            raise AuthorityError("INVALID_GRANT_TARGET")

        def read(current, *, lock_for_owner: bool):
            if configure_transaction:
                current.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            credential_id = self._current_credential_id(
                current,
                context,
                now=now,
                recovery_epoch=recovery_epoch,
                lock_session=lock_for_owner,
            )
            self._authorization_read_checkpoint()
            if lock_for_owner:
                self._lock_dynamic_grants(current, context, grants)
            states = tuple(
                self._read_dynamic_authorization_state(
                    current,
                    context,
                    grant,
                    now=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
                for grant in grants
            )
            return credential_id, states

        try:
            if connection is not None:
                return read(connection, lock_for_owner=True)
            with self.pool.connection() as owned, owned.transaction():
                return read(owned, lock_for_owner=False)
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _lock_dynamic_grants(
        connection, context: TrustedRequestContext, grants: Sequence[ExactGrant]
    ) -> None:
        """Serialize matching revocations behind the caller-owned owner commit."""
        for grant in grants:
            connection.execute(
                "SELECT g.grant_id FROM authorization_admin.grants g "
                "WHERE g.subject_principal_id=%s AND g.tenant_id=%s "
                "AND g.security_domain=%s AND g.owner=%s AND g.action=%s "
                "AND g.exact_resource=%s ORDER BY g.grant_id FOR SHARE",
                (
                    context.principal_id,
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    grant.owner,
                    grant.action,
                    grant.exact_resource,
                ),
            ).fetchall()

    @staticmethod
    def _claim(
        connection,
        scope: AuthorityScope,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
        payload_digest: str,
    ) -> dict[str, Any] | None:
        lock_key = json.dumps(
            [
                scope.tenant_id,
                scope.security_domain,
                actor_id,
                command_type,
                idempotency_key,
            ],
            separators=(",", ":"),
        )
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 302))", (lock_key,)
        )
        row = connection.execute(
            "SELECT payload_digest,result_record FROM authorization_admin.idempotency_claims "
            "WHERE tenant_id=%s AND security_domain=%s AND actor_id=%s "
            "AND command_type=%s AND idempotency_key=%s FOR UPDATE",
            (
                scope.tenant_id,
                scope.security_domain,
                actor_id,
                command_type,
                idempotency_key,
            ),
        ).fetchone()
        if row is not None and row["payload_digest"] != payload_digest:
            raise AuthorityError("IDEMPOTENCY_PAYLOAD_MISMATCH")
        return row["result_record"] if row else None

    @staticmethod
    def _complete(
        connection,
        scope: AuthorityScope,
        actor_id: str,
        command_type: str,
        idempotency_key: str,
        payload_digest: str,
        result_kind: str,
        result_id: str,
    ) -> None:
        connection.execute(
            "INSERT INTO authorization_admin.idempotency_claims"
            "(tenant_id,security_domain,actor_id,command_type,idempotency_key,"
            "payload_digest,result_kind,result_id,result_record) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                scope.tenant_id,
                scope.security_domain,
                actor_id,
                command_type,
                idempotency_key,
                payload_digest,
                result_kind,
                result_id,
                json.dumps({"id": result_id}),
            ),
        )

    @staticmethod
    def _epoch_command_type(command_type: str, recovery_epoch: int) -> str:
        if recovery_epoch < 1:
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
        return f"{command_type}:RECOVERY_EPOCH:{recovery_epoch}"

    @staticmethod
    def _require_current_recovery_epoch(connection, recovery_epoch: int) -> None:
        row = connection.execute(
            "SELECT a.recovery_epoch,r.state FROM "
            "authorization_admin.active_generation a LEFT JOIN "
            "authorization_admin.recovery_records r "
            "ON r.recovery_epoch=a.recovery_epoch WHERE a.singleton=true "
            "FOR SHARE OF a"
        ).fetchone()
        if (
            row is None
            or row["recovery_epoch"] != recovery_epoch
            or (row["state"] is not None and row["state"] != "ACTIVE")
        ):
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")

    @staticmethod
    def _request(connection, request_id: str) -> GrantRequest:
        row = connection.execute(
            "SELECT * FROM authorization_admin.grant_requests WHERE request_id=%s",
            (request_id,),
        ).fetchone()
        if row is None:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
        members = connection.execute(
            "SELECT owner,action,exact_resource FROM "
            "authorization_admin.grant_request_members WHERE request_id=%s "
            "ORDER BY ordinal",
            (request_id,),
        ).fetchall()
        return GrantRequest(
            request_id=row["request_id"],
            subject_principal_id=row["subject_principal_id"],
            scope=AuthorityScope(row["tenant_id"], row["security_domain"]),
            members=tuple(
                ExactGrant(member["owner"], member["action"], member["exact_resource"])
                for member in members
            ),
            purpose=row["purpose"],
            status=GrantRequestStatus(row["state"]),
            created_at=row["created_at"],
        )

    def inspect_request(self, request_id: str) -> GrantRequest:
        try:
            with self.connection_scope() as connection:
                return self._request(connection, request_id)
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def inspect_request_for(
        self,
        request_id: str,
        context: TrustedRequestContext,
        *,
        administrator_authorized: bool,
    ) -> GrantRequest:
        try:
            with self.connection_scope() as connection:
                allowed = connection.execute(
                    "SELECT request_id FROM authorization_admin.grant_requests "
                    "WHERE request_id=%s AND tenant_id=%s AND security_domain=%s "
                    "AND (subject_principal_id=%s OR %s)",
                    (
                        request_id,
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        context.principal_id,
                        administrator_authorized,
                    ),
                ).fetchone()
                if allowed is None:
                    raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
                return self._request(connection, request_id)
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def inspect_grant_subject(self, grant_id: GrantId) -> tuple[str, AuthorityScope]:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT subject_principal_id,tenant_id,security_domain FROM "
                    "authorization_admin.grants WHERE grant_id=%s",
                    (grant_id,),
                ).fetchone()
                if row is None:
                    raise AuthorityError("GRANT_NOT_FOUND")
                return row["subject_principal_id"], AuthorityScope(
                    row["tenant_id"], row["security_domain"]
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def inspect_grant_for_subject(
        self, grant_id: GrantId, context: TrustedRequestContext
    ) -> tuple[str, AuthorityScope]:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT subject_principal_id,tenant_id,security_domain FROM "
                    "authorization_admin.grants WHERE grant_id=%s "
                    "AND subject_principal_id=%s AND tenant_id=%s AND security_domain=%s",
                    (
                        grant_id,
                        context.principal_id,
                        context.scope.tenant_id,
                        context.scope.security_domain,
                    ),
                ).fetchone()
                if row is None:
                    raise AuthorityError("GRANT_NOT_FOUND")
                return row["subject_principal_id"], AuthorityScope(
                    row["tenant_id"], row["security_domain"]
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _continuation_claim(connection, offer_id: str) -> ContinuationClaim:
        row = connection.execute(
            "SELECT * FROM authorization_admin.continuation_offers WHERE offer_id=%s",
            (offer_id,),
        ).fetchone()
        if row is None:
            raise AuthorityError("CONTINUATION_INVALID")
        members = connection.execute(
            "SELECT owner,action,exact_resource FROM "
            "authorization_admin.continuation_offer_members WHERE offer_id=%s "
            "ORDER BY ordinal",
            (offer_id,),
        ).fetchall()
        return ContinuationClaim(
            nonce=row["offer_id"],
            subject_principal_id=row["subject_principal_id"],
            scope=AuthorityScope(row["tenant_id"], row["security_domain"]),
            purpose=row["purpose"],
            members=tuple(
                ExactGrant(item["owner"], item["action"], item["exact_resource"])
                for item in members
            ),
            canonical_resource_reference=row["canonical_resource_reference"],
            owner_revision=row["owner_revision"],
            policy_generation=row["policy_generation"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
        )

    def store_continuation_offer(
        self,
        claim: ContinuationClaim,
        *,
        continuation_digest: str,
        issuer_actor_id: str,
        mint_key: str,
        mint_payload_digest: str,
        recovery_epoch: int,
    ) -> ContinuationClaim:
        if not claim.members:
            raise AuthorityError("CONTINUATION_INVALID")
        for member in claim.members:
            validate_registered_grant(member, allow_meta=False)
        lock_key = json.dumps(
            [
                claim.members[0].owner,
                claim.canonical_resource_reference,
                claim.subject_principal_id,
                claim.purpose,
                mint_key,
            ],
            separators=(",", ":"),
        )
        try:
            with self.connection_scope() as connection:
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 302))",
                    (lock_key,),
                )
                existing = connection.execute(
                    "SELECT offer_id,mint_payload_digest FROM "
                    "authorization_admin.continuation_offers WHERE owner=%s "
                    "AND canonical_resource_reference=%s AND subject_principal_id=%s "
                    "AND purpose=%s AND mint_key=%s FOR UPDATE",
                    (
                        claim.members[0].owner,
                        claim.canonical_resource_reference,
                        claim.subject_principal_id,
                        claim.purpose,
                        mint_key,
                    ),
                ).fetchone()
                if existing is not None:
                    if existing["mint_payload_digest"] != mint_payload_digest:
                        raise AuthorityError("IDEMPOTENCY_PAYLOAD_MISMATCH")
                    return self._continuation_claim(connection, existing["offer_id"])
                connection.execute(
                    "INSERT INTO authorization_admin.continuation_offers"
                    "(offer_id,continuation_digest,subject_principal_id,tenant_id,"
                    "security_domain,purpose,owner,canonical_resource_reference,"
                    "owner_revision,policy_generation,mint_key,mint_payload_digest,"
                    "issued_at,expires_at,recovery_epoch) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        claim.nonce,
                        continuation_digest,
                        claim.subject_principal_id,
                        claim.scope.tenant_id,
                        claim.scope.security_domain,
                        claim.purpose,
                        claim.members[0].owner,
                        claim.canonical_resource_reference,
                        claim.owner_revision,
                        claim.policy_generation,
                        mint_key,
                        mint_payload_digest,
                        claim.issued_at,
                        claim.expires_at,
                        recovery_epoch,
                    ),
                )
                for ordinal, member in enumerate(claim.members, start=1):
                    connection.execute(
                        "INSERT INTO authorization_admin.continuation_offer_members"
                        "(offer_id,ordinal,owner,action,exact_resource) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (
                            claim.nonce,
                            ordinal,
                            member.owner,
                            member.action,
                            member.exact_resource,
                        ),
                    )
                self._audit(
                    connection,
                    event_type="CONTINUATION_OFFER_CREATED",
                    actor_id=issuer_actor_id,
                    outcome="COMMITTED",
                    reason=claim.purpose,
                    occurred_at=claim.issued_at,
                    scope=claim.scope,
                    subject_id=claim.subject_principal_id,
                    generation=claim.policy_generation,
                    recovery_epoch=recovery_epoch,
                )
                return claim
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def list_continuation_offers(
        self,
        context: TrustedRequestContext,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> tuple[ContinuationClaim, ...]:
        try:
            with self.connection_scope() as connection:
                rows = connection.execute(
                    "SELECT offer_id FROM authorization_admin.continuation_offers "
                    "WHERE subject_principal_id=%s AND tenant_id=%s AND security_domain=%s "
                    "AND revoked_at IS NULL AND expires_at>%s AND recovery_epoch=%s "
                    "ORDER BY issued_at,offer_id",
                    (
                        context.principal_id,
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        now,
                        recovery_epoch,
                    ),
                ).fetchall()
                return tuple(
                    self._continuation_claim(connection, row["offer_id"])
                    for row in rows
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def submit_request(
        self,
        request: GrantRequest,
        *,
        actor_id: str,
        idempotency_key: str,
        payload_digest: str,
        target_validation: Callable[[object], bool],
        recovery_epoch: int,
        continuation_digest: str | None = None,
    ) -> GrantRequest:
        require_bounded_label(request.purpose, reason_code="GRANT_REQUEST_INVALID")
        if not idempotency_key or len(idempotency_key) > 200:
            raise AuthorityError("IDEMPOTENCY_KEY_INVALID")
        if not request.members:
            raise AuthorityError("GRANT_REQUEST_INVALID")
        for member in request.members:
            validate_registered_grant(member, allow_meta=False)
        command_type = self._epoch_command_type("SUBMIT_GRANT_REQUEST", recovery_epoch)
        try:
            with self.connection_scope() as connection:
                self._require_current_recovery_epoch(connection, recovery_epoch)
                replay = self._claim(
                    connection,
                    request.scope,
                    actor_id,
                    command_type,
                    idempotency_key,
                    payload_digest,
                )
                if replay is not None:
                    return self._request(connection, replay["id"])
                if continuation_digest is not None:
                    connection.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended(%s, 302))",
                        (continuation_digest,),
                    )
                    consumed = connection.execute(
                        "SELECT * FROM authorization_admin.continuation_consumptions "
                        "WHERE continuation_digest=%s FOR UPDATE",
                        (continuation_digest,),
                    ).fetchone()
                    if consumed is not None:
                        same = (
                            consumed["subject_principal_id"]
                            == request.subject_principal_id
                            and consumed["purpose"] == request.purpose
                            and consumed["idempotency_key"] == idempotency_key
                            and consumed["payload_digest"] == payload_digest
                        )
                        if same:
                            return self._request(connection, consumed["request_id"])
                        raise AuthorityError("CONTINUATION_INVALID")
                    offer = connection.execute(
                        "SELECT subject_principal_id,purpose FROM "
                        "authorization_admin.continuation_offers "
                        "WHERE continuation_digest=%s AND revoked_at IS NULL "
                        "AND expires_at>%s AND recovery_epoch=%s FOR UPDATE",
                        (continuation_digest, request.created_at, recovery_epoch),
                    ).fetchone()
                    if offer != {
                        "subject_principal_id": request.subject_principal_id,
                        "purpose": request.purpose,
                    }:
                        raise AuthorityError("CONTINUATION_INVALID")
                if not target_validation(connection):
                    raise AuthorityError(
                        "CONTINUATION_INVALID"
                        if continuation_digest is not None
                        else "GRANT_REQUEST_NOT_FOUND"
                    )
                connection.execute(
                    "INSERT INTO authorization_admin.grant_requests"
                    "(request_id,subject_principal_id,tenant_id,security_domain,purpose,"
                    "state,created_at) VALUES(%s,%s,%s,%s,%s,'PENDING',%s)",
                    (
                        request.request_id,
                        request.subject_principal_id,
                        request.scope.tenant_id,
                        request.scope.security_domain,
                        request.purpose,
                        request.created_at,
                    ),
                )
                for ordinal, member in enumerate(request.members, start=1):
                    connection.execute(
                        "INSERT INTO authorization_admin.grant_request_members"
                        "(request_id,ordinal,owner,action,exact_resource) "
                        "VALUES(%s,%s,%s,%s,%s)",
                        (
                            request.request_id,
                            ordinal,
                            member.owner,
                            member.action,
                            member.exact_resource,
                        ),
                    )
                if continuation_digest is not None:
                    connection.execute(
                        "INSERT INTO authorization_admin.continuation_consumptions"
                        "(continuation_digest,request_id,subject_principal_id,purpose,"
                        "idempotency_key,payload_digest,consumed_at) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (
                            continuation_digest,
                            request.request_id,
                            request.subject_principal_id,
                            request.purpose,
                            idempotency_key,
                            payload_digest,
                            request.created_at,
                        ),
                    )
                self._complete(
                    connection,
                    request.scope,
                    actor_id,
                    command_type,
                    idempotency_key,
                    payload_digest,
                    "GRANT_REQUEST",
                    request.request_id,
                )
                self._audit(
                    connection,
                    event_type="GRANT_REQUEST_SUBMITTED",
                    actor_id=actor_id,
                    outcome="COMMITTED",
                    reason=request.purpose,
                    occurred_at=request.created_at,
                    scope=request.scope,
                    subject_id=request.subject_principal_id,
                    recovery_epoch=recovery_epoch,
                )
                return request
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _decision(connection, decision_id: str) -> GrantDecision:
        row = connection.execute(
            "SELECT * FROM authorization_admin.grant_decisions WHERE decision_id=%s",
            (decision_id,),
        ).fetchone()
        if row is None:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
        grant_rows = connection.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE decision_id=%s "
            "ORDER BY grant_id",
            (decision_id,),
        ).fetchall()
        return GrantDecision(
            decision_id=row["decision_id"],
            request_id=row["request_id"],
            issuer_principal_id=row["issuer_principal_id"],
            issuer_meta_decision_id=row["issuer_meta_decision_id"],
            approved=row["approved"],
            reason_category=row["reason_category"],
            basis_type=row["basis_type"],
            basis_reference_digest=row["basis_reference_digest"],
            policy_version=row["policy_version"],
            audit_source=row["audit_source"],
            created_at=row["created_at"],
            grants=tuple(GrantId(item["grant_id"]) for item in grant_rows),
        )

    def decide_request(
        self,
        decision: GrantDecision,
        *,
        grants: Sequence[tuple[GrantId, ExactGrant, datetime, datetime]],
        expected_status: GrantRequestStatus,
        idempotency_key: str,
        payload_digest: str,
        recovery_epoch: int,
    ) -> GrantDecision:
        require_bounded_label(
            decision.reason_category, reason_code="INVALID_GRANT_DECISION"
        )
        require_bounded_label(decision.basis_type, reason_code="INVALID_GRANT_DECISION")
        if not idempotency_key or len(idempotency_key) > 200:
            raise AuthorityError("IDEMPOTENCY_KEY_INVALID")
        command_type = self._epoch_command_type("DECIDE_GRANT_REQUEST", recovery_epoch)
        try:
            with self.connection_scope() as connection:
                self._require_current_recovery_epoch(connection, recovery_epoch)
                request = self._request(connection, decision.request_id)
                replay = self._claim(
                    connection,
                    request.scope,
                    decision.issuer_principal_id,
                    command_type,
                    idempotency_key,
                    payload_digest,
                )
                if replay is not None:
                    return self._decision(connection, replay["id"])
                row = connection.execute(
                    "SELECT subject_principal_id,state FROM "
                    "authorization_admin.grant_requests WHERE request_id=%s FOR UPDATE",
                    (decision.request_id,),
                ).fetchone()
                self._decision_request_locked_checkpoint()
                if row["subject_principal_id"] == decision.issuer_principal_id:
                    raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
                if row["state"] != expected_status.value:
                    raise AuthorityError("AUTHORIZATION_STATE_STALE")
                if decision.approved != bool(grants) or (
                    not decision.approved and grants
                ):
                    raise AuthorityError("INVALID_GRANT_DECISION")
                if decision.approved and (
                    len(grants) != len(request.members)
                    or {item[1] for item in grants} != set(request.members)
                ):
                    raise AuthorityError("INVALID_GRANT_DECISION")
                connection.execute(
                    "INSERT INTO authorization_admin.grant_decisions"
                    "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
                    "approved,reason_category,basis_type,basis_reference_digest,"
                    "policy_version,audit_source,created_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        decision.decision_id,
                        decision.request_id,
                        decision.issuer_principal_id,
                        decision.issuer_meta_decision_id,
                        decision.approved,
                        decision.reason_category,
                        decision.basis_type,
                        decision.basis_reference_digest,
                        decision.policy_version,
                        decision.audit_source,
                        decision.created_at,
                    ),
                )
                member_set = set(request.members)
                for grant_id, member, not_before, expires_at in grants:
                    if member not in member_set:
                        raise AuthorityError("INVALID_GRANT_DECISION")
                    self._insert_grant(
                        connection,
                        grant_id,
                        request,
                        decision,
                        member,
                        not_before,
                        expires_at,
                        recovery_epoch,
                    )
                new_status = "APPROVED" if decision.approved else "REJECTED"
                connection.execute(
                    "UPDATE authorization_admin.grant_requests "
                    "SET state=%s,aggregate_version=aggregate_version+1,decided_at=%s "
                    "WHERE request_id=%s",
                    (new_status, decision.created_at, decision.request_id),
                )
                self._complete(
                    connection,
                    request.scope,
                    decision.issuer_principal_id,
                    command_type,
                    idempotency_key,
                    payload_digest,
                    "GRANT_DECISION",
                    decision.decision_id,
                )
                self._audit(
                    connection,
                    event_type="GRANT_REQUEST_DECIDED",
                    actor_id=decision.issuer_principal_id,
                    outcome="APPROVED" if decision.approved else "REJECTED",
                    reason=decision.reason_category,
                    occurred_at=decision.created_at,
                    scope=request.scope,
                    subject_id=request.subject_principal_id,
                    recovery_epoch=recovery_epoch,
                )
                return replace(decision, grants=tuple(item[0] for item in grants))
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _insert_grant(
        connection,
        grant_id: GrantId,
        request: GrantRequest,
        decision: GrantDecision,
        member: ExactGrant,
        not_before: datetime,
        expires_at: datetime,
        recovery_epoch: int,
    ) -> None:
        values = (
            grant_id,
            decision.decision_id,
            request.request_id,
            request.subject_principal_id,
            request.scope.tenant_id,
            request.scope.security_domain,
            member.owner,
            member.action,
            member.exact_resource,
            decision.basis_type,
            decision.basis_reference_digest,
            decision.issuer_principal_id,
            decision.issuer_meta_decision_id,
            decision.policy_version,
            decision.audit_source,
            not_before,
            expires_at,
            decision.created_at,
            recovery_epoch,
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants"
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,recovery_epoch) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            values,
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants"
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,action,"
            "exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                grant_id,
                request.subject_principal_id,
                request.scope.tenant_id,
                request.scope.security_domain,
                member.owner,
                member.action,
                member.exact_resource,
                not_before,
                expires_at,
                recovery_epoch,
            ),
        )

    def has_current_grant(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> bool:
        return (
            self.read_dynamic_authorization_state(
                context,
                grant,
                now=now,
                generation=generation,
                recovery_epoch=recovery_epoch,
            )
            is DynamicAuthorizationState.ALLOWED
        )

    @staticmethod
    def _read_dynamic_authorization_state(
        connection,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> DynamicAuthorizationState:
        row = connection.execute(
            "SELECT a.generation,a.recovery_epoch,"
            "(SELECT max(r.revoked_at) FROM authorization_admin.grants g "
            "JOIN authorization_admin.grant_revocation_facts r "
            "ON r.grant_id=g.grant_id WHERE g.subject_principal_id=%s "
            "AND g.tenant_id=%s AND g.security_domain=%s AND g.owner=%s "
            "AND g.action=%s AND g.exact_resource=%s) AS latest_revocation,"
            "(SELECT max(g.created_at) FROM authorization_admin.grants g "
            "JOIN authorization_admin.effective_grants e ON e.grant_id=g.grant_id "
            "WHERE g.subject_principal_id=%s AND g.tenant_id=%s "
            "AND g.security_domain=%s AND g.owner=%s AND g.action=%s "
            "AND g.exact_resource=%s AND g.not_before<=%s AND g.expires_at>%s "
            "AND g.recovery_epoch=%s) AS latest_grant "
            "FROM authorization_admin.active_generation a WHERE a.singleton=true",
            (
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
                grant.owner,
                grant.action,
                grant.exact_resource,
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
                grant.owner,
                grant.action,
                grant.exact_resource,
                now,
                now,
                recovery_epoch,
            ),
        ).fetchone()
        if (
            row is None
            or row["generation"] != generation
            or row["recovery_epoch"] != recovery_epoch
        ):
            return DynamicAuthorizationState.UNAVAILABLE
        revoked_at = row["latest_revocation"]
        granted_at = row["latest_grant"]
        if revoked_at is not None and (granted_at is None or revoked_at >= granted_at):
            return DynamicAuthorizationState.REVOKED
        if granted_at is not None:
            return DynamicAuthorizationState.ALLOWED
        return DynamicAuthorizationState.NONE

    def read_dynamic_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> DynamicAuthorizationState:
        try:
            with self.connection_scope() as connection:
                return self._read_dynamic_authorization_state(
                    connection,
                    context,
                    grant,
                    now=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def has_dynamic_revocation(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> bool:
        active = self.active_generation()
        if active is None:
            return False
        return (
            self.read_dynamic_authorization_state(
                context,
                grant,
                now=now,
                generation=active[0],
                recovery_epoch=recovery_epoch,
            )
            is DynamicAuthorizationState.REVOKED
        )

    def revoke_grant(
        self,
        grant_id: GrantId,
        *,
        actor_id: str,
        reason: str,
        idempotency_key: str,
        payload_digest: str,
        now: datetime,
    ) -> bool:
        require_bounded_label(reason, reason_code="INVALID_GRANT_REVOCATION")
        if not idempotency_key or len(idempotency_key) > 200:
            raise AuthorityError("IDEMPOTENCY_KEY_INVALID")
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT tenant_id,security_domain FROM authorization_admin.grants "
                    "WHERE grant_id=%s FOR UPDATE",
                    (grant_id,),
                ).fetchone()
                if row is None:
                    raise AuthorityError("GRANT_NOT_FOUND")
                scope = AuthorityScope(row["tenant_id"], row["security_domain"])
                replay = self._claim(
                    connection,
                    scope,
                    actor_id,
                    "REVOKE_GRANT",
                    idempotency_key,
                    payload_digest,
                )
                if replay is not None:
                    return True
                revoked = connection.execute(
                    "SELECT revocation_id FROM authorization_admin.grant_revocation_facts "
                    "WHERE grant_id=%s",
                    (grant_id,),
                ).fetchone()
                if revoked is not None:
                    raise AuthorityError("AUTHORIZATION_STATE_STALE")
                revocation_id = f"grant-revocation-{secrets.token_hex(16)}"
                connection.execute(
                    "INSERT INTO authorization_admin.grant_revocation_facts"
                    "(revocation_id,grant_id,actor_id,reason_category,payload_digest,revoked_at) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    (revocation_id, grant_id, actor_id, reason, payload_digest, now),
                )
                connection.execute(
                    "DELETE FROM authorization_admin.effective_grants WHERE grant_id=%s",
                    (grant_id,),
                )
                self._complete(
                    connection,
                    scope,
                    actor_id,
                    "REVOKE_GRANT",
                    idempotency_key,
                    payload_digest,
                    "GRANT_REVOCATION",
                    revocation_id,
                )
                self._audit(
                    connection,
                    event_type="GRANT_REVOKED",
                    actor_id=actor_id,
                    outcome="COMMITTED",
                    reason=reason,
                    occurred_at=now,
                    scope=scope,
                    subject_id=grant_id,
                )
                return True
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def active_generation(self) -> tuple[int, str, int] | None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT generation,generation_digest,recovery_epoch FROM "
                    "authorization_admin.active_generation WHERE singleton=true"
                ).fetchone()
                if row is None:
                    return None
                return (
                    row["generation"],
                    row["generation_digest"],
                    row["recovery_epoch"],
                )
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def activate_generation(
        self,
        generation: int,
        digest: str,
        recovery_epoch: int,
        *,
        operator_id: str,
        revoked_credentials: Sequence[CredentialId],
        now: datetime,
    ) -> None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT generation,recovery_epoch FROM "
                    "authorization_admin.active_generation WHERE singleton=true FOR UPDATE"
                ).fetchone()
                if row is not None and (
                    generation <= row["generation"]
                    or recovery_epoch < row["recovery_epoch"]
                ):
                    raise AuthorityError("AUTHORITY_GENERATION_STALE")
                if row is None:
                    connection.execute(
                        "INSERT INTO authorization_admin.active_generation"
                        "(singleton,generation,generation_digest,recovery_epoch,"
                        "activated_by,activated_at) VALUES(true,%s,%s,%s,%s,%s)",
                        (generation, digest, recovery_epoch, operator_id, now),
                    )
                else:
                    connection.execute(
                        "UPDATE authorization_admin.active_generation SET generation=%s,"
                        "generation_digest=%s,recovery_epoch=%s,activated_by=%s,"
                        "activated_at=%s WHERE singleton=true",
                        (generation, digest, recovery_epoch, operator_id, now),
                    )
                for credential_id in revoked_credentials:
                    sessions = connection.execute(
                        "SELECT s.session_id FROM browser_identity.sessions s "
                        "LEFT JOIN browser_identity.session_revocation_facts r "
                        "ON r.session_id=s.session_id WHERE s.credential_id=%s "
                        "AND r.session_id IS NULL FOR UPDATE OF s",
                        (credential_id,),
                    ).fetchall()
                    for session in sessions:
                        self._insert_session_revocation(
                            connection,
                            SessionId(session["session_id"]),
                            reason="CREDENTIAL_REVOKED",
                            actor_id=operator_id,
                            now=now,
                        )
                self._audit(
                    connection,
                    event_type="AUTHORITY_GENERATION_ACTIVATED",
                    actor_id=operator_id,
                    outcome="COMMITTED",
                    reason="OPERATOR_ACTIVATION",
                    occurred_at=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def _terminate_pending_requests_for_recovery(
        self,
        connection,
        *,
        recovery_epoch: int,
        generation: int,
        operator_id: str,
        now: datetime,
    ) -> None:
        requests = connection.execute(
            "SELECT request_id,subject_principal_id,tenant_id,security_domain "
            "FROM authorization_admin.grant_requests WHERE state='PENDING' "
            "ORDER BY request_id FOR UPDATE"
        ).fetchall()
        self._recovery_requests_locked_checkpoint()
        for request in requests:
            connection.execute(
                "UPDATE authorization_admin.grant_requests SET state='REJECTED',"
                "aggregate_version=aggregate_version+1,decided_at=%s "
                "WHERE request_id=%s AND state='PENDING'",
                (now, request["request_id"]),
            )
            self._audit(
                connection,
                event_type="GRANT_REQUEST_RECOVERY_TERMINATED",
                actor_id=operator_id,
                outcome="TERMINATED",
                reason="DATABASE_RECOVERY",
                occurred_at=now,
                scope=AuthorityScope(request["tenant_id"], request["security_domain"]),
                subject_id=request["subject_principal_id"],
                generation=generation,
                recovery_epoch=recovery_epoch,
            )

    def reconcile_recovery(
        self,
        *,
        recovery_epoch: int,
        database_fingerprint: str,
        generation: int,
        generation_digest: str,
        migration_version: int,
        operator_id: str,
        audit_continuity_digest: str,
        now: datetime,
    ) -> None:
        try:
            with self.connection_scope() as connection:
                active = connection.execute(
                    "SELECT generation,generation_digest,recovery_epoch FROM "
                    "authorization_admin.active_generation WHERE singleton=true "
                    "FOR UPDATE"
                ).fetchone()
                latest = connection.execute(
                    "SELECT recovery_epoch,database_fingerprint,generation,"
                    "generation_digest,migration_version,operator_id,"
                    "audit_continuity_digest,state FROM "
                    "authorization_admin.recovery_records "
                    "ORDER BY recovery_epoch DESC LIMIT 1 FOR UPDATE"
                ).fetchone()
                if latest is not None and recovery_epoch <= latest["recovery_epoch"]:
                    expected = {
                        "recovery_epoch": recovery_epoch,
                        "database_fingerprint": database_fingerprint,
                        "generation": generation,
                        "generation_digest": generation_digest,
                        "migration_version": migration_version,
                        "operator_id": operator_id,
                        "audit_continuity_digest": audit_continuity_digest,
                    }
                    if recovery_epoch == latest["recovery_epoch"] and all(
                        latest[key] == value for key, value in expected.items()
                    ):
                        return
                    raise AuthorityError("AUTHORITY_RECOVERY_EPOCH_STALE")
                if (
                    active is None
                    or active["generation"] != generation
                    or active["generation_digest"] != generation_digest
                    or recovery_epoch <= active["recovery_epoch"]
                ):
                    raise AuthorityError("AUTHORITY_RECOVERY_EPOCH_STALE")
                connection.execute(
                    "INSERT INTO authorization_admin.recovery_records"
                    "(recovery_epoch,database_fingerprint,generation,generation_digest,"
                    "migration_version,state,operator_id,audit_continuity_digest,recorded_at) "
                    "VALUES(%s,%s,%s,%s,%s,'RECOVERY_CLOSED',%s,%s,%s)",
                    (
                        recovery_epoch,
                        database_fingerprint,
                        generation,
                        generation_digest,
                        migration_version,
                        operator_id,
                        audit_continuity_digest,
                        now,
                    ),
                )
                sessions = connection.execute(
                    "SELECT s.session_id FROM browser_identity.sessions s "
                    "LEFT JOIN browser_identity.session_revocation_facts r "
                    "ON r.session_id=s.session_id WHERE r.session_id IS NULL FOR UPDATE OF s"
                ).fetchall()
                for session in sessions:
                    self._insert_session_revocation(
                        connection,
                        SessionId(session["session_id"]),
                        reason="DATABASE_RECOVERY",
                        actor_id=operator_id,
                        now=now,
                    )
                self._terminate_pending_requests_for_recovery(
                    connection,
                    recovery_epoch=recovery_epoch,
                    generation=generation,
                    operator_id=operator_id,
                    now=now,
                )
                connection.execute(
                    "UPDATE authorization_admin.continuation_offers "
                    "SET revoked_at=%s WHERE revoked_at IS NULL",
                    (now,),
                )
                connection.execute("DELETE FROM authorization_admin.effective_grants")
                connection.execute(
                    "UPDATE authorization_admin.active_generation SET recovery_epoch=%s "
                    "WHERE singleton=true",
                    (recovery_epoch,),
                )
                self._audit(
                    connection,
                    event_type="AUTHORITY_RECOVERY_RECONCILED",
                    actor_id=operator_id,
                    outcome="RECOVERY_CLOSED",
                    reason="DATABASE_RESTORE",
                    occurred_at=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc

    def complete_recovery(
        self,
        *,
        recovery_epoch: int,
        generation: int,
        generation_digest: str,
        operator_id: str,
        now: datetime,
    ) -> None:
        try:
            with self.connection_scope() as connection:
                row = connection.execute(
                    "SELECT state,generation,generation_digest FROM "
                    "authorization_admin.recovery_records WHERE recovery_epoch=%s "
                    "FOR UPDATE",
                    (recovery_epoch,),
                ).fetchone()
                expected = {
                    "generation": generation,
                    "generation_digest": generation_digest,
                }
                if row is None or any(
                    row[key] != value for key, value in expected.items()
                ):
                    raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
                if row["state"] == "ACTIVE":
                    return
                if row["state"] != "RECOVERY_CLOSED":
                    raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
                active = connection.execute(
                    "SELECT generation,generation_digest,recovery_epoch FROM "
                    "authorization_admin.active_generation WHERE singleton=true FOR UPDATE"
                ).fetchone()
                if active != {
                    "generation": generation,
                    "generation_digest": generation_digest,
                    "recovery_epoch": recovery_epoch,
                }:
                    raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
                connection.execute(
                    "UPDATE authorization_admin.recovery_records SET state='ACTIVE',"
                    "operator_id=%s,recorded_at=%s WHERE recovery_epoch=%s",
                    (operator_id, now, recovery_epoch),
                )
                self._audit(
                    connection,
                    event_type="AUTHORITY_RECOVERY_ACTIVATED",
                    actor_id=operator_id,
                    outcome="ACTIVE",
                    reason="OPERATOR_ACTIVATION",
                    occurred_at=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
        except AuthorityError:
            raise
        except PsycopgError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc
