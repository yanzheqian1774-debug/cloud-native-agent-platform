"""D324-7 task owner: preparation is not signature; immutable scoped records."""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .bounded_task_policy import (
    TaskAuthorizationRequest,
    require_current,
    require_scope,
)
from .task_delegation import digest


def available(c):
    return bool(
        c.execute(
            "SELECT to_regclass('authorization_admin.bounded_task_requests') AS name"
        ).fetchone()["name"]
    )


def task_lock(c, request_id):
    c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,39))", (request_id,))


def latest_root_decision(c, row):
    task_lock(
        c,
        digest(
            [row[k] for k in ("tenant_id", "security_domain", "subject_id", "root_id")]
        ),
    )
    return c.execute(
        "SELECT d.* FROM authorization_admin.bounded_task_decisions d "
        "JOIN authorization_admin.bounded_task_requests r USING(request_id) "
        "WHERE r.tenant_id=%s AND r.security_domain=%s AND r.subject_id=%s "
        "AND r.root_id=%s ORDER BY d.created_at DESC,d.decision_id DESC LIMIT 1",
        tuple(
            row[k] for k in ("tenant_id", "security_domain", "subject_id", "root_id")
        ),
    ).fetchone()


def current(c, row):
    decision = latest_root_decision(c, row)
    if decision and decision["request_id"] != row["request_id"]:
        raise AuthorityError("TASK_AUTHORIZATION_SUPERSEDED")
    account = c.execute(
        "SELECT status,revision,principal_id,tenant_id,security_domain FROM "
        "browser_identity.local_accounts WHERE account_id=%s FOR SHARE",
        (row["account_id"],),
    ).fetchone()
    generation = c.execute(
        "SELECT generation,recovery_epoch FROM authorization_admin.active_generation "
        "WHERE singleton=true FOR SHARE"
    ).fetchone()
    revoked = (
        decision
        and c.execute(
            "SELECT 1 FROM authorization_admin.bounded_task_revocations WHERE "
            "decision_id=%s",
            (decision["decision_id"],),
        ).fetchone()
    )
    require_current(
        row,
        decision,
        account,
        generation or {},
        c.execute("SELECT clock_timestamp() AS now").fetchone()["now"],
        revoked=bool(revoked),
    )
    return decision


class BoundedTaskAuthorization:
    def __init__(self, delegation, *, root_bindings):
        self.delegation = delegation
        self.repository = delegation.repository
        # Deployment pins actual roots; URL/task name never establishes membership.
        self.root_bindings = dict(root_bindings)

    def migrate(self):
        for version, name in (
            (39, "0039_bounded_task_authorization.sql"),
            (40, "0040_task_planning_successor.sql"),
        ):
            self._migrate(version, name)

    def _migrate(self, version, name):
        path = self.repository.migration_path.parent / name
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            prior = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations "
                "WHERE version=%s",
                (version,),
            ).fetchone()
            if prior:
                if prior["checksum"] != checksum:
                    raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
                return
            c.execute(path.read_text())
            c.execute(
                "INSERT INTO authorization_admin.schema_migrations(version,"
                "checksum,adapter) "
                "VALUES(%s,%s,'bounded-task-authorization-v1')",
                (version, checksum),
            )

    def _validate_targets(self, c, context, spec):
        validator = self.delegation.grants.target_validator
        from .authority_contracts import ExactGrant

        if validator is None or not all(
            validator.is_known_exact_target(
                context,
                ExactGrant(p.owner, p.action, p.exact_resource),
                connection=c,
            )
            for p in spec.permissions
        ):
            raise AuthorityError("TASK_AUTHORIZATION_TARGET_UNAVAILABLE")

    def prepare(self, context, spec):
        from .local_accounts import current_session_account

        scope = (context.scope.tenant_id, context.scope.security_domain)
        require_scope(spec.purpose, scope)
        if self.root_bindings.get((spec.purpose, *scope)) != spec.root.model_dump(
            mode="json"
        ):
            raise AuthorityError("TASK_AUTHORIZATION_ROOT_DENIED")
        with self.repository.connection_scope() as c:
            valid_session = current_session_account(
                c, session_id=context.session_id_or_service_credential_id
            )
            account = c.execute(
                "SELECT a.* FROM browser_identity.local_accounts a JOIN "
                "browser_identity.local_account_sessions s USING(account_id) "
                "WHERE s.session_id=%s AND a.revision=s.account_revision "
                "AND a.principal_id=%s AND a.tenant_id=%s AND "
                "a.security_domain=%s FOR SHARE OF a",
                (
                    context.session_id_or_service_credential_id,
                    context.principal_id,
                    *scope,
                ),
            ).fetchone()
            if not valid_session or not account:
                raise AuthorityError("TASK_AUTHORIZATION_ACCOUNT_INACTIVE")
            root = c.execute(
                "SELECT p.created_by,r.digest FROM "
                "business_problem_authority.problems p "
                "JOIN business_problem_authority.problem_revisions r "
                "USING(namespace,security_domain,business_problem_id) "
                "WHERE p.namespace=%s AND p.security_domain=%s AND "
                "p.business_problem_id=%s "
                "AND r.revision_id=%s",
                (*scope, spec.root.resource_id, spec.root.revision_id),
            ).fetchone()
            if root != {"created_by": context.principal_id, "digest": spec.root.digest}:
                raise AuthorityError("TASK_AUTHORIZATION_ROOT_DENIED")
            if spec.configuration is not None:
                from .bounded_task_policy import require_configuration
                from .task_planning_successor import validate_recovery

                actual = getattr(self, "actual_configuration", {})
                require_configuration(spec.configuration, actual, cleanup_seconds=2)
                validate_recovery(
                    c,
                    spec,
                    scope,
                    {
                        k: v
                        for k, v in actual.items()
                        if k not in {"connect_seconds", "read_seconds", "total_seconds"}
                    },
                )
            self._validate_targets(c, context, spec)
            key = (*scope, context.principal_id, spec.idempotency_key)
            task_lock(c, digest(key))
            payload = spec.model_dump(mode="json")
            old = c.execute(
                "SELECT * FROM authorization_admin.bounded_task_requests WHERE "
                "tenant_id=%s "
                "AND security_domain=%s AND subject_id=%s AND request_key=%s",
                key,
            ).fetchone()
            if old:
                if old["digest"] != digest(payload):
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                return old
            identity = "task-authorization-request:" + uuid4().hex
            c.execute(
                "INSERT INTO authorization_admin.bounded_task_requests "
                "(request_id,task_id,tenant_id,security_domain,root_id,"
                "subject_id,account_id,account_revision,request_key,digest,record) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    identity,
                    spec.task_id,
                    *scope,
                    spec.root.resource_id,
                    context.principal_id,
                    account["account_id"],
                    account["revision"],
                    spec.idempotency_key,
                    digest(payload),
                    Jsonb(payload),
                ),
            )
            c.execute(
                "INSERT INTO authorization_admin.bounded_task_objects "
                "(request_id,owner,resource_id,revision_id,digest,origin) "
                "VALUES(%s,'BUSINESS_PROBLEM',%s,%s,%s,'EXPLICIT_ROOT')",
                (
                    identity,
                    spec.root.resource_id,
                    spec.root.revision_id,
                    spec.root.digest,
                ),
            )
            return self._row(c, context, identity)

    def _row(self, c, context, identity):
        row = c.execute(
            "SELECT * FROM authorization_admin.bounded_task_requests WHERE "
            "request_id=%s "
            "AND tenant_id=%s AND security_domain=%s",
            (identity, context.scope.tenant_id, context.scope.security_domain),
        ).fetchone()
        if not row:
            raise AuthorityError("TASK_AUTHORIZATION_NOT_FOUND")
        if row["subject_id"] != context.principal_id:
            self.delegation._admin(context, c)
        return row

    def read(self, context, identity):
        with self.repository.connection_scope() as c:
            row = self._row(c, context, identity)
            try:
                decision, reason = current(c, row), None
            except AuthorityError as exc:
                decision, reason = None, exc.reason_code
            return {
                "request": row,
                "decision": decision,
                "reasonCode": reason,
                "status": "ACTIVE" if decision else "NOT_ADMITTED",
            }

    def approve(self, context, identity, signature):
        with self.repository.connection_scope() as c:
            self.delegation._admin(context, c)
            row = self._row(c, context, identity)
            if row["subject_id"] == context.principal_id:
                raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
            latest_root_decision(c, row)
            value = signature.model_dump(mode="json")
            prior = c.execute(
                "SELECT * FROM authorization_admin.bounded_task_decisions "
                "WHERE issuer_id=%s AND idempotency_key=%s",
                (context.principal_id, signature.idempotency_key),
            ).fetchone()
            if prior:
                if prior["request_id"] != identity or prior["payload_digest"] != digest(
                    value
                ):
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                return prior
            spec = TaskAuthorizationRequest.model_validate(row["record"])
            self._validate_targets(c, context, spec)
            now = datetime.now(UTC)
            if signature.request_digest != row["digest"] or signature.expires_at <= now:
                raise AuthorityError("TASK_AUTHORIZATION_INVALID")
            account = c.execute(
                "SELECT revision,status FROM browser_identity.local_accounts "
                "WHERE account_id=%s FOR SHARE",
                (row["account_id"],),
            ).fetchone()
            if account != {"revision": row["account_revision"], "status": "ENABLED"}:
                raise AuthorityError("TASK_AUTHORIZATION_ACCOUNT_INACTIVE")
            previous = latest_root_decision(c, row)
            decision_id = "task-authorization:" + uuid4().hex
            grants = self.delegation.grants
            c.execute(
                "INSERT INTO authorization_admin.bounded_task_decisions "
                "(decision_id,request_id,predecessor_id,issuer_id,"
                "idempotency_key,payload_digest,not_before,expires_at,generation,"
                "recovery_epoch) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    decision_id,
                    identity,
                    previous["decision_id"] if previous else None,
                    context.principal_id,
                    signature.idempotency_key,
                    digest(value),
                    signature.not_before,
                    signature.expires_at,
                    grants.generation.generation,
                    grants.recovery_epoch,
                ),
            )
            return c.execute(
                "SELECT * FROM authorization_admin.bounded_task_decisions WHERE "
                "decision_id=%s",
                (decision_id,),
            ).fetchone()

    def revoke(self, context, identity, decision_id):
        with self.repository.connection_scope() as c:
            self.delegation._admin(context, c)
            row = self._row(c, context, identity)
            latest_root_decision(c, row)
            if not c.execute(
                "SELECT 1 FROM authorization_admin.bounded_task_decisions WHERE "
                "request_id=%s AND decision_id=%s",
                (identity, decision_id),
            ).fetchone():
                raise AuthorityError("TASK_AUTHORIZATION_NOT_FOUND")
            c.execute(
                "INSERT INTO "
                "authorization_admin.bounded_task_revocations(decision_id,actor_id) "
                "VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (decision_id, context.principal_id),
            )
            return {"revoked": True}


def bind_plan(c, scope, actor_id, proposal):
    """Called only by planning owner after save, within its transaction."""
    if not available(c):
        return
    rows = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE tenant_id=%s "
        "AND security_domain=%s AND root_id=%s AND subject_id=%s",
        (
            scope.namespace,
            scope.security_domain,
            proposal.semantics.target.problem.resource_id,
            actor_id,
        ),
    ).fetchall()
    for row in rows:
        spec = TaskAuthorizationRequest.model_validate(row["record"])
        if spec.root != proposal.semantics.target.problem:
            continue
        c.execute(
            "INSERT INTO authorization_admin.bounded_task_objects "
            "(request_id,owner,resource_id,revision_id,digest,parent_owner,"
            "parent_id,parent_revision_id,origin) "
            "VALUES(%s,'PLAN',%s,%s,%s,'BUSINESS_PROBLEM',%s,%s,'PLANNING_OWNER') "
            "ON CONFLICT DO NOTHING",
            (
                row["request_id"],
                "plan:v2:" + proposal.proposal_id,
                str(proposal.revision),
                proposal.digest,
                spec.root.resource_id,
                spec.root.revision_id,
            ),
        )


def exact_decision(c, context, grant):
    """Existing sessions/revocation checks precede this optional narrow authority."""
    if not available(c):
        return False
    rows = c.execute(
        "SELECT * FROM authorization_admin.bounded_task_requests WHERE tenant_id=%s "
        "AND security_domain=%s AND subject_id=%s ORDER BY created_at DESC",
        (context.scope.tenant_id, context.scope.security_domain, context.principal_id),
    ).fetchall()
    for row in rows:
        spec = TaskAuthorizationRequest.model_validate(row["record"])
        exact = any(
            (p.owner, p.action, p.exact_resource)
            == (grant.owner, grant.action, grant.exact_resource)
            for p in spec.permissions
        )
        derived = any(
            (p.owner, p.action) == (grant.owner, grant.action)
            for p in spec.derived_permissions
        )
        if not exact and not derived:
            continue
        if (
            not exact
            and not c.execute(
                "SELECT 1 FROM authorization_admin.bounded_task_objects WHERE "
                "request_id=%s "
                "AND owner=%s AND resource_id=%s AND origin='PLANNING_OWNER'",
                (row["request_id"], grant.owner, grant.exact_resource),
            ).fetchone()
        ):
            continue
        try:
            decision = current(c, row)
        except AuthorityError:
            continue
        c.execute(
            "INSERT INTO authorization_admin.bounded_task_effects "
            "(decision_id,owner,action,resource_id,session_id) VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING",
            (
                decision["decision_id"],
                grant.owner,
                grant.action,
                grant.exact_resource,
                context.session_id_or_service_credential_id,
            ),
        )
        return decision
    return None
