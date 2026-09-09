"""Explicit composition and activation coordination for I1 authority ports."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Condition
from typing import Any, Protocol

from agent_console.authority_configuration import (
    AuthorityRuntimeConfiguration,
    StaticAuthorityGeneration,
    StaticAuthorityLoader,
    validate_registered_grant,
)
from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    ContinuationClaim,
    ControlState,
    CredentialId,
    ExactGrant,
    GrantSource,
    GrantTargetValidator,
    VerifiedPrincipal,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.authority_recovery import HostControlRecord, HostRecoveryControl
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
)


class ActivationBarrier:
    """Process-local read/write barrier pinning one immutable generation per call."""

    def __init__(self, snapshot: StaticAuthorityGeneration) -> None:
        self._condition = Condition()
        self._snapshot = snapshot
        self._readers = 0
        self._writer = False

    @contextmanager
    def read(self) -> Iterator[StaticAuthorityGeneration]:
        with self._condition:
            while self._writer:
                self._condition.wait()
            self._readers += 1
            snapshot = self._snapshot
        try:
            yield snapshot
        finally:
            with self._condition:
                self._readers -= 1
                if self._readers == 0:
                    self._condition.notify_all()

    @contextmanager
    def write(self) -> Iterator[None]:
        with self._condition:
            while self._writer or self._readers:
                self._condition.wait()
            self._writer = True
        try:
            yield
        finally:
            with self._condition:
                self._writer = False
                self._condition.notify_all()

    @property
    def snapshot(self) -> StaticAuthorityGeneration:
        return self._snapshot

    def publish(self, snapshot: StaticAuthorityGeneration) -> None:
        if not self._writer:
            raise AuthorityError("AUTHORITY_ACTIVATION_PROTOCOL_VIOLATION")
        self._snapshot = snapshot


@dataclass(frozen=True, slots=True)
class AuthorityReadiness:
    generation: int
    generation_digest: str
    recovery_epoch: int
    database_fingerprint: str


class AuthorityGenerationRepository(Protocol):
    def active_generation(self) -> tuple[int, str, int] | None: ...

    def activate_generation(
        self,
        generation: int,
        digest: str,
        recovery_epoch: int,
        *,
        operator_id: str,
        revoked_credentials: Sequence[CredentialId],
        now: datetime,
    ) -> None: ...


class AuthorityGenerationController:
    def __init__(
        self,
        barrier: ActivationBarrier,
        repository: AuthorityGenerationRepository,
        control: HostRecoveryControl,
        readiness: AuthorityReadiness,
    ) -> None:
        self.barrier = barrier
        self.repository = repository
        self.control = control
        self.readiness = readiness

    @contextmanager
    def protected_request(self) -> Iterator[StaticAuthorityGeneration]:
        with self.barrier.read() as snapshot:
            active = self.repository.active_generation()
            expected = (
                snapshot.generation,
                snapshot.digest,
                self.readiness.recovery_epoch,
            )
            if active != expected:
                raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
            self.control.require_ready(
                database_fingerprint=self.readiness.database_fingerprint,
                generation=snapshot.generation,
                generation_digest=snapshot.digest,
                recovery_epoch=self.readiness.recovery_epoch,
            )
            yield snapshot

    def activate(
        self,
        candidate: StaticAuthorityGeneration,
        *,
        control_epoch: int,
        operator_id: str,
        now: datetime,
    ) -> AuthorityReadiness:
        current = self.barrier.snapshot
        same_published_candidate = (
            candidate.generation == current.generation
            and candidate.digest == current.digest
        )
        if candidate.generation < current.generation or (
            candidate.generation == current.generation and not same_published_candidate
        ):
            raise AuthorityError("AUTHORITY_GENERATION_STALE")
        candidate_identity = (
            candidate.generation,
            candidate.digest,
            self.readiness.recovery_epoch,
        )
        pending_retry = False
        pending_control_epoch = control_epoch
        active_operator_id = operator_id
        if same_published_candidate:
            committed = self.repository.active_generation()
            record = self.control.read()
            record_matches = (
                record.database_fingerprint == self.readiness.database_fingerprint
                and record.recovery_epoch == self.readiness.recovery_epoch
                and record.generation == candidate.generation
                and record.generation_digest == candidate.digest
            )
            if committed != candidate_identity or not record_matches:
                raise AuthorityError("AUTHORITY_GENERATION_STALE")
            if record.state is ControlState.ACTIVE:
                self.readiness = AuthorityReadiness(
                    candidate.generation,
                    candidate.digest,
                    self.readiness.recovery_epoch,
                    self.readiness.database_fingerprint,
                )
                return self.readiness
            if record.state is not ControlState.ACTIVATION_PENDING:
                raise AuthorityError("AUTHORITY_GENERATION_STALE")
            pending_retry = True
            pending_control_epoch = record.control_epoch
            active_operator_id = record.operator_id
        if not current.credential_revocation_tombstones <= (
            candidate.credential_revocation_tombstones
        ):
            raise AuthorityError("AUTHORITY_REVOCATION_TOMBSTONE_MISSING")
        if not current.static_grant_revocation_tombstones <= (
            candidate.static_grant_revocation_tombstones
        ):
            raise AuthorityError("AUTHORITY_REVOCATION_TOMBSTONE_MISSING")
        current_credentials = {item.credential_id: item for item in current.credentials}
        candidate_credentials = {
            item.credential_id: item for item in candidate.credentials
        }
        removed_credentials = set(current_credentials) - set(candidate_credentials)
        if not removed_credentials <= set(candidate.credential_revocation_tombstones):
            raise AuthorityError("AUTHORITY_REVOCATION_TOMBSTONE_MISSING")
        removed_static_grants = {
            (credential_id, grant.grant)
            for credential_id, credential in current_credentials.items()
            for grant in credential.grants
            if credential_id in candidate_credentials
            and grant.grant
            not in {item.grant for item in candidate_credentials[credential_id].grants}
        }
        if not removed_static_grants <= set(
            candidate.static_grant_revocation_tombstones
        ):
            raise AuthorityError("AUTHORITY_REVOCATION_TOMBSTONE_MISSING")
        revoked_credentials = tuple(
            candidate.credential_revocation_tombstones
            - current.credential_revocation_tombstones
            | removed_credentials
        )
        with self.barrier.write():
            if not pending_retry:
                pending = HostControlRecord(
                    control_epoch=control_epoch,
                    recovery_epoch=self.readiness.recovery_epoch,
                    state=ControlState.ACTIVATION_PENDING,
                    database_fingerprint=self.readiness.database_fingerprint,
                    generation=candidate.generation,
                    generation_digest=candidate.digest,
                    operator_id=operator_id,
                )
                self.control.replace(pending)
            committed = self.repository.active_generation()
            if committed != candidate_identity:
                self.repository.activate_generation(
                    candidate.generation,
                    candidate.digest,
                    self.readiness.recovery_epoch,
                    operator_id=operator_id,
                    revoked_credentials=revoked_credentials,
                    now=now,
                )
            self.barrier.publish(candidate)
            active = HostControlRecord(
                control_epoch=max(control_epoch, pending_control_epoch) + 1,
                recovery_epoch=self.readiness.recovery_epoch,
                state=ControlState.ACTIVE,
                database_fingerprint=self.readiness.database_fingerprint,
                generation=candidate.generation,
                generation_digest=candidate.digest,
                operator_id=active_operator_id,
            )
            self.control.replace(active)
            self.readiness = AuthorityReadiness(
                candidate.generation,
                candidate.digest,
                self.readiness.recovery_epoch,
                self.readiness.database_fingerprint,
            )
            return self.readiness


class SignedContinuationOwner:
    """Authenticated owner envelope bound to one subject, scope, and purpose."""

    def __init__(self, signing_key: bytes) -> None:
        if len(signing_key) < 32:
            raise AuthorityError("AUTHORITY_CONFIGURATION_INVALID")
        self.signing_key = signing_key

    def mint(self, claim: ContinuationClaim) -> str:
        if claim.expires_at - claim.issued_at > timedelta(minutes=10):
            raise AuthorityError("CONTINUATION_INVALID")
        for member in claim.members:
            validate_registered_grant(member, allow_meta=False)
        payload = {
            "nonce": claim.nonce,
            "subjectPrincipalId": claim.subject_principal_id,
            "tenantId": claim.scope.tenant_id,
            "securityDomain": claim.scope.security_domain,
            "purpose": claim.purpose,
            "members": [
                {
                    "owner": item.owner,
                    "action": item.action,
                    "exactResource": item.exact_resource,
                }
                for item in claim.members
            ],
            "canonicalResourceReference": claim.canonical_resource_reference,
            "ownerRevision": claim.owner_revision,
            "policyGeneration": claim.policy_generation,
            "issuedAt": claim.issued_at.isoformat(),
            "expiresAt": claim.expires_at.isoformat(),
        }
        encoded = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).rstrip(b"=")
        signature = hmac.new(self.signing_key, encoded, hashlib.sha256).hexdigest()
        return f"{encoded.decode()}.{signature}"

    def resolve_continuation(
        self, opaque_continuation: str, *, now: datetime
    ) -> ContinuationClaim:
        try:
            encoded, signature = opaque_continuation.split(".", 1)
            expected = hmac.new(
                self.signing_key, encoded.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
            issued_at = datetime.fromisoformat(payload["issuedAt"])
            expires_at = datetime.fromisoformat(payload["expiresAt"])
            if issued_at.tzinfo is None or expires_at.tzinfo is None:
                raise ValueError
            claim = ContinuationClaim(
                nonce=payload["nonce"],
                subject_principal_id=payload["subjectPrincipalId"],
                scope=AuthorityScope(payload["tenantId"], payload["securityDomain"]),
                purpose=payload["purpose"],
                members=tuple(
                    ExactGrant(item["owner"], item["action"], item["exactResource"])
                    for item in payload["members"]
                ),
                canonical_resource_reference=payload["canonicalResourceReference"],
                owner_revision=payload["ownerRevision"],
                policy_generation=payload["policyGeneration"],
                issued_at=issued_at.astimezone(UTC),
                expires_at=expires_at.astimezone(UTC),
            )
            if (
                now < claim.issued_at
                or now >= claim.expires_at
                or claim.expires_at - claim.issued_at > timedelta(minutes=10)
            ):
                raise ValueError
            for member in claim.members:
                validate_registered_grant(member, allow_meta=False)
            return claim
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthorityError("CONTINUATION_INVALID") from exc


class GovernedExecutionAuthenticatorAdapter:
    """Expose existing service Bearer verification through the typed port."""

    def __init__(self, authority: Any) -> None:
        self.authority = authority

    def authenticate(self, credential: str, *, now: datetime) -> VerifiedPrincipal:
        try:
            principal = self.authority.authenticate(f"Bearer {credential}")
        except ValueError as exc:
            raise AuthorityError("AUTHENTICATION_REQUIRED") from exc
        if now >= principal.expires_at:
            raise AuthorityError("AUTHENTICATION_REQUIRED")
        return VerifiedPrincipal(
            principal_id=principal.principal_id,
            scope=AuthorityScope(principal.tenant_id, principal.security_domain),
            credential_id=CredentialId(principal.credential_id),
            credential_expires_at=principal.expires_at,
            policy_version=self.authority.policy_version,
        )


@dataclass(slots=True)
class AuthorityFoundation:
    repository: PostgresAuthorityRepository
    sessions: BrowserSessionService
    grants: GrantAdministrationService
    generation_controller: AuthorityGenerationController
    continuation_owner: SignedContinuationOwner

    def close(self) -> None:
        self.repository.close()


def initialize_authority_generation(
    runtime: AuthorityRuntimeConfiguration,
    *,
    control_epoch: int,
    recovery_epoch: int,
    now: datetime,
) -> AuthorityReadiness:
    """Privileged first activation or response-loss resume; never called at import."""
    generation = StaticAuthorityLoader.load(
        runtime.generation_path, expected_digest=runtime.generation_digest
    )
    repository = PostgresAuthorityRepository(
        runtime.database_url, migration_path=runtime.migration_path
    )
    control = HostRecoveryControl(runtime.recovery_control_path)
    try:
        repository.migrate()
        pending = HostControlRecord(
            control_epoch=control_epoch,
            recovery_epoch=recovery_epoch,
            state=ControlState.ACTIVATION_PENDING,
            database_fingerprint=runtime.database_fingerprint,
            generation=generation.generation,
            generation_digest=generation.digest,
            operator_id=runtime.operator_id,
        )
        control.replace(pending)
        identity = (generation.generation, generation.digest, recovery_epoch)
        active = repository.active_generation()
        if active is None:
            repository.activate_generation(
                generation.generation,
                generation.digest,
                recovery_epoch,
                operator_id=runtime.operator_id,
                revoked_credentials=tuple(generation.credential_revocation_tombstones),
                now=now,
            )
        elif active != identity:
            raise AuthorityError("AUTHORITY_GENERATION_STALE")
        control.replace(
            HostControlRecord(
                control_epoch=control_epoch + 1,
                recovery_epoch=recovery_epoch,
                state=ControlState.ACTIVE,
                database_fingerprint=runtime.database_fingerprint,
                generation=generation.generation,
                generation_digest=generation.digest,
                operator_id=runtime.operator_id,
            )
        )
        return AuthorityReadiness(
            generation.generation,
            generation.digest,
            recovery_epoch,
            runtime.database_fingerprint,
        )
    finally:
        repository.close()


def build_authority_foundation(
    runtime: AuthorityRuntimeConfiguration,
    session_policy: BrowserSessionPolicy,
    *,
    target_validator: GrantTargetValidator | None = None,
) -> AuthorityFoundation:
    """Construct I1 ports only when DB, immutable file, and host gate agree."""
    generation = StaticAuthorityLoader.load(
        runtime.generation_path, expected_digest=runtime.generation_digest
    )
    repository = PostgresAuthorityRepository(
        runtime.database_url,
        migration_path=runtime.migration_path,
    )
    try:
        repository.migrate()
        active = repository.active_generation()
        if active is None or active[:2] != (generation.generation, generation.digest):
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
        recovery_epoch = active[2]
        control = HostRecoveryControl(runtime.recovery_control_path)
        control.require_ready(
            database_fingerprint=runtime.database_fingerprint,
            generation=generation.generation,
            generation_digest=generation.digest,
            recovery_epoch=recovery_epoch,
        )
        csrf_key = AuthorityRuntimeConfiguration.read_external_key(
            runtime.csrf_signing_key_path
        )
        continuation_owner = SignedContinuationOwner(
            AuthorityRuntimeConfiguration.read_external_key(
                runtime.continuation_signing_key_path
            )
        )
        barrier = ActivationBarrier(generation)
        readiness = AuthorityReadiness(
            generation.generation,
            generation.digest,
            recovery_epoch,
            runtime.database_fingerprint,
        )
        controller = AuthorityGenerationController(
            barrier, repository, control, readiness
        )
        sessions = BrowserSessionService(
            repository,
            StaticGenerationAuthenticator(
                lambda: barrier.snapshot, source=GrantSource.BROWSER_BOOTSTRAP
            ),
            session_policy,
            csrf_signing_key=csrf_key,
            recovery_epoch=recovery_epoch,
        )
        reader = GenerationAuthorizationReader(
            lambda: barrier.snapshot,
            repository,
            repository,
            recovery_epoch=recovery_epoch,
        )
        grants = GrantAdministrationService(
            repository,
            reader,
            lambda: barrier.snapshot,
            continuation_owner=continuation_owner,
            target_validator=target_validator,
            recovery_epoch=recovery_epoch,
        )
        return AuthorityFoundation(
            repository, sessions, grants, controller, continuation_owner
        )
    except Exception:
        repository.close()
        raise
