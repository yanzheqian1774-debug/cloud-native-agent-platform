"""Bounded, independent task approval; never caller-admin or prefix authority.

Delegation is an authority fact, not another budget ledger. Future targets are
resolved through existing owners and the approved root context. Every issued
permission remains a normal exact grant, linked to its issuing delegation.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import (
    AuthorityError,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequestStatus,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ledger_id: str = Field(min_length=1, max_length=200)
    configuration_digest: str = Field(pattern="^[a-f0-9]{64}$")
    profile_revision_id: str
    profile_digest: str = Field(pattern="^[a-f0-9]{64}$")
    model_target: str
    calls: int = Field(ge=1, le=100)
    input_tokens: int = Field(ge=1)
    output_tokens: int = Field(ge=1)
    cost_microusd: int = Field(ge=1)


class TaskApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=1, max_length=100)
    subject_id: str = Field(min_length=1, max_length=200)
    root_context_id: str = Field(min_length=1, max_length=200)
    expires_at: datetime
    understanding: Limits
    planning: Limits
    allow_usage_read: bool = False
    allow_measurement_read: bool = False
    idempotency_key: str = Field(min_length=1, max_length=200)


# Purpose remains distinct from owner/action. No execution/assignment/employee
# administration or arbitrary resources can enter this set.
PURPOSES = {
    "PROBLEM_DRAFT_ASSISTANCE": {
        ("DRAFT_ASSISTANCE", "REQUEST_DRAFT_ASSISTANCE"),
        ("DRAFT_ASSISTANCE", "READ_DRAFT_ASSISTANCE_INVOCATION"),
        ("DRAFT_ASSISTANCE", "CANCEL_DRAFT_ASSISTANCE_INVOCATION"),
    },
    "PROBLEM_DRAFT_MODEL_INVOKE": {("MODEL_GOVERNANCE", "INVOKE_MODEL")},
    "WORKBENCH_PLANNING": {
        ("PLAN", "PREPARE"),
        ("PLAN", "READ"),
        ("PLAN", "APPROVE"),
        ("MODEL_GOVERNANCE", "INVOKE_MODEL"),
    },
    "WORKBENCH_PROBLEM": {
        ("BUSINESS_PROBLEM", "READ"),
        ("BUSINESS_PROBLEM", "REVISE"),
        ("BUSINESS_PROBLEM", "TRANSITION"),
    },
    "CONTINUE_PROBLEM_READ": {("BUSINESS_PROBLEM", "READ")},
    "WORKBENCH_SUCCESS_CRITERIA": {
        ("SUCCESS_CRITERION", "READ"),
        ("SUCCESS_CRITERION", "REVISE"),
        ("SUCCESS_CRITERIA_SET", "CREATE"),
        ("SUCCESS_CRITERIA_SET", "READ"),
        ("SUCCESS_CRITERIA_SET", "REVISE"),
    },
    "PROVIDER_USAGE_REVIEW": {
        ("RESOURCE_USE", "READ"),
        ("EVIDENCE", "READ_MEASUREMENT"),
    },
}


def available(connection):
    return (
        connection.execute(
            "SELECT to_regclass('authorization_admin.task_delegations') AS name"
        ).fetchone()["name"]
        is not None
    )


def active(connection, identity, *, lock=False, allow_expired=False):
    from .task_development import revision, stopped

    connection.execute("SELECT pg_advisory_xact_lock(3230028)")
    generation = connection.execute(
        "SELECT generation,generation_digest,recovery_epoch FROM "
        "authorization_admin.active_generation WHERE singleton=true FOR SHARE"
    ).fetchone()
    row = connection.execute(
        "SELECT d.*,control.revoked FROM authorization_admin.task_delegations d "
        "JOIN authorization_admin.task_delegation_control control "
        "USING(delegation_id) WHERE delegation_id=%s "
        + ("FOR UPDATE" if lock else "FOR SHARE"),
        (identity,),
    ).fetchone()
    if row is None:
        raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
    now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    revoked = connection.execute(
        "SELECT 1 FROM authorization_admin.task_delegation_revocations WHERE "
        "delegation_id=%s",
        (identity,),
    ).fetchone()
    from .task_identity_continuity import effective

    continuity = effective(connection, row, generation, now) if generation else None
    if continuity:
        row["_continuity"] = continuity
    if (
        (
            now >= row["expires_at"]
            and not allow_expired
            and not revision(connection, identity)
        )
        or stopped(connection, identity)
        or row["revoked"]
        or revoked
        or generation is None
        or (generation["generation"] != row["generation"] and continuity is None)
        or generation["recovery_epoch"] != row["recovery_epoch"]
    ):
        raise AuthorityError("TASK_DELEGATION_INACTIVE")
    return row, now


def draft_records(connection, row):
    from .task_cases import context_ids

    return [
        item["record"]
        for item in connection.execute(
            "SELECT DISTINCT ON (invocation_id) record FROM "
            "draft_assistance.invocation_versions WHERE namespace=%s AND "
            "security_domain=%s AND record->>'contextId'=ANY(%s) AND "
            "record->>'initiatingPrincipalId'=%s ORDER BY "
            "invocation_id,aggregate_version DESC",
            (
                row["tenant_id"],
                row["security_domain"],
                context_ids(connection, row),
                row["subject_id"],
            ),
        ).fetchall()
    ]


def task_problem_ids(connection, row):
    from .task_cases import cases

    linked = {
        r["problemId"] for r in draft_records(connection, row) if r.get("problemId")
    }
    owned = connection.execute(
        "SELECT resource_id FROM authorization_admin.task_delegation_resources "
        "WHERE delegation_id=%s AND owner='BUSINESS_PROBLEM'",
        (row["delegation_id"],),
    ).fetchall()
    if cases(connection, row["delegation_id"]):
        linked.update(
            r["problem_id"]
            for r in connection.execute(
                "SELECT problem_id FROM authorization_admin.task_case_problems WHERE "
                "delegation_id=%s",
                (row["delegation_id"],),
            ).fetchall()
        )
    return linked.intersection(r["resource_id"] for r in owned)


def planning_record(connection, row, invocation_id):
    result = connection.execute(
        "SELECT record FROM workflow_planning.invocations WHERE namespace=%s AND "
        "security_domain=%s AND actor_id=%s AND invocation_id=%s",
        (row["tenant_id"], row["security_domain"], row["subject_id"], invocation_id),
    ).fetchone()
    if result and result["record"]["target"]["problem"]["problem"][
        "resource_id"
    ] in task_problem_ids(connection, row):
        return result["record"]
    return None


def target_in_task(connection, row, grant):
    """Only canonical lineage, never caller-supplied task labels or substring IDs."""
    spec = row["record"]
    drafts = draft_records(connection, row)
    resource = grant.exact_resource
    if grant.owner == "DRAFT_ASSISTANCE" or (
        grant.owner == "MODEL_GOVERNANCE"
        and resource.startswith("model:invocation:draft-assistance:")
    ):
        for r in drafts:
            bound = spec["understanding"]
            if r["profileRevisionId"] != bound["profile_revision_id"]:
                continue
            expected = (
                f"model:invocation:draft-assistance:{r['contextId']}:{r['turnId']}:"
                f"{r['invocationId']}:{r['snapshotCandidateId']}:{bound['model_target']}"
            )
            if r["modelTarget"] != expected:
                continue
            if resource in {
                r["requestTarget"],
                r["modelTarget"],
                "draft-assistance:invocation:" + r["invocationId"],
            }:
                return True
        return False
    if grant.owner == "MODEL_GOVERNANCE":
        # Planning's existing exact model target is configuration-scoped. Its
        # actual per-invocation task membership is checked again by budget owner.
        return resource == spec["planning"]["model_target"]
    if grant.owner in {"RESOURCE_USE", "EVIDENCE"}:
        flag = (
            "allow_usage_read"
            if grant.owner == "RESOURCE_USE"
            else "allow_measurement_read"
        )
        if not spec[flag]:
            return False
        for r in drafts:
            from .provider_usage import grants

            if (grant.owner, grant.action, resource) in grants(
                "understanding", r["invocationId"]
            ):
                return True
        prefixes = (
            "resource-use:contextual-resource-use:",
            "evidence-reference:provider-usage:planning:",
        )
        return any(
            resource.startswith(p)
            and planning_record(connection, row, resource[len(p) :]) is not None
            for p in prefixes
        )
    problems = task_problem_ids(connection, row)
    if grant.owner == "BUSINESS_PROBLEM":
        return resource in {"business-problem:" + p for p in problems}
    if grant.owner == "PLAN":
        if resource in {
            prefix + p
            for prefix in ("plan:prepare:", "plan:prepared:")
            for p in problems
        }:
            return True
        if resource.startswith("plan:v2:"):
            records = connection.execute(
                "SELECT record FROM workflow_planning.proposals WHERE namespace=%s "
                "AND security_domain=%s AND proposal_id=%s",
                (row["tenant_id"], row["security_domain"], resource[len("plan:v2:") :]),
            ).fetchall()
            return any(
                r["record"]["semantics"]["target"]["problem"]["resource_id"] in problems
                for r in records
            )
    # Criteria-set mutations are exact to a task's Problem. Standalone criteria
    # are not task-owned until the owner has bound them to that Problem.
    if grant.owner == "SUCCESS_CRITERION":
        if resource == "success-criterion:collection":
            return grant.action == "READ"
        owned = connection.execute(
            "SELECT resource_id FROM authorization_admin.task_delegation_resources "
            "WHERE delegation_id=%s AND owner='SUCCESS_CRITERION'",
            (row["delegation_id"],),
        ).fetchall()
        return resource in {
            prefix + r["resource_id"]
            for r in owned
            for prefix in ("success-criterion:", "success-criterion:revision:")
        }
    if grant.owner == "SUCCESS_CRITERIA_SET":
        return resource in {"success-criteria-set:" + p for p in problems}
    return False


class TaskDelegationService:
    def __init__(self, grants, configurations, *, timeout_source=None):
        self.grants = grants
        self.repository = grants.repository
        self.configurations = configurations
        self.timeout_source = timeout_source

    def migrate(self):
        path = Path(__file__).parents[2] / "migrations/0028_task_delegation.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            existing = c.execute(
                "SELECT to_regclass('authorization_admin.task_delegation_migrations')"
                " AS name"
            ).fetchone()["name"]
            row = (
                c.execute(
                    "SELECT checksum FROM "
                    "authorization_admin.task_delegation_migrations WHERE version=28"
                ).fetchone()
                if existing
                else None
            )
            if row and row["checksum"] != checksum:
                raise AuthorityError("TASK_DELEGATION_SCHEMA_INCOMPATIBLE")
            if row is None:
                c.execute(path.read_text())
            c.execute(
                "INSERT INTO authorization_admin.schema_migrations"
                "(version,checksum,adapter) "
                "VALUES(28,%s,'task-delegation-v1') ON CONFLICT DO NOTHING",
                (checksum,),
            )
            c.execute(
                "INSERT INTO authorization_admin.task_delegation_migrations "
                "VALUES(28,%s) ON CONFLICT DO NOTHING",
                (checksum,),
            )

        path = Path(__file__).parents[2] / "migrations/0029_task_development.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            row = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations "
                "WHERE version=29"
            ).fetchone()
            if row and row["checksum"] != checksum:
                raise AuthorityError("TASK_DELEGATION_SCHEMA_INCOMPATIBLE")
            c.execute(path.read_text())
            c.execute(
                "INSERT INTO authorization_admin.schema_migrations"
                "(version,checksum,adapter) VALUES(29,%s,'task-development-v1') "
                "ON CONFLICT DO NOTHING",
                (checksum,),
            )
        path = Path(__file__).parents[2] / "migrations/0030_task_cases.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            row = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations WHERE "
                "version=30"
            ).fetchone()
            if row and row["checksum"] != checksum:
                raise AuthorityError("TASK_DELEGATION_SCHEMA_INCOMPATIBLE")
            if row is None:
                c.execute(path.read_text())
                c.execute(
                    "INSERT INTO "
                    "authorization_admin.schema_migrations"
                    "(version,checksum,adapter) "
                    "VALUES(30,%s,'task-cases-v1')",
                    (checksum,),
                )

        path = Path(__file__).parents[2] / "migrations/0031_task_timeout_revision.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            row = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations "
                "WHERE version=31"
            ).fetchone()
            if row and row["checksum"] != checksum:
                raise AuthorityError("TASK_DELEGATION_SCHEMA_INCOMPATIBLE")
            if row is None:
                c.execute(path.read_text())
                c.execute(
                    "INSERT INTO authorization_admin.schema_migrations"
                    "(version,checksum,adapter) "
                    "VALUES(31,%s,'task-timeout-revision-v1')",
                    (checksum,),
                )

        path = (
            Path(__file__).parents[2] / "migrations/0032_task_identity_continuity.sql"
        )
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            row = c.execute(
                "SELECT checksum FROM authorization_admin.schema_migrations "
                "WHERE version=32"
            ).fetchone()
            if row and row["checksum"] != checksum:
                raise AuthorityError("TASK_DELEGATION_SCHEMA_INCOMPATIBLE")
            if row is None:
                c.execute(path.read_text())
                c.execute(
                    (
                        "INSERT INTO "
                        "authorization_admin.schema_migrations"
                        "(version,checksum,adapter) "
                        "VALUES(32,%s,'task-identity-continuity-v1')"
                    ),
                    (checksum,),
                )

    def _admin(self, context, connection=None):
        meta = ExactGrant(
            "GRANT_ADMIN",
            "DECIDE",
            f"grant-scope:{context.scope.tenant_id}:{context.scope.security_domain}",
        )
        if connection is None:
            self.grants._require(context, meta)
            return
        connection.execute("SELECT pg_advisory_xact_lock(3230028)")
        generation = connection.execute(
            "SELECT generation,recovery_epoch FROM "
            "authorization_admin.active_generation WHERE singleton=true FOR SHARE"
        ).fetchone()
        if generation != {
            "generation": self.grants.generation.generation,
            "recovery_epoch": self.grants.recovery_epoch,
        }:
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
        if not all(
            self.grants.authorization.has_current_grants(
                context,
                (meta,),
                now=datetime.now(UTC),
                generation=generation["generation"],
                recovery_epoch=generation["recovery_epoch"],
                connection=connection,
                configure_transaction=False,
            )
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def approve(self, context, spec):
        self._admin(context)
        if (
            context.principal_id == spec.subject_id
            or spec.subject_id == "service:task-delegation"
        ):
            raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
        credentials = [
            v
            for v in self.grants.generation.credentials
            if v.principal_id == spec.subject_id
            and v.scope == context.scope
            and v.credential_id
            not in self.grants.generation.credential_revocation_tombstones
        ]
        if not credentials:
            raise AuthorityError("TASK_DELEGATION_SUBJECT_INVALID")
        expires = spec.expires_at
        if expires.utcoffset() != timedelta(0):
            raise AuthorityError("TASK_DELEGATION_WINDOW_INVALID")
        for kind in ("understanding", "planning"):
            if getattr(spec, kind).model_dump() != self.configurations[kind]:
                raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
        record = spec.model_dump(mode="json")
        record["purpose_policy"] = "problem-to-plan-task.v1"
        record["purposes"] = sorted(PURPOSES)
        payload_digest = digest(record)
        with self.repository.connection_scope() as c:
            c.execute("SELECT pg_advisory_xact_lock(3230028)")
            self._admin(context, c)
            now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if expires <= now or expires > min(v.expires_at for v in credentials):
                raise AuthorityError("TASK_DELEGATION_WINDOW_INVALID")
            root = c.execute(
                "SELECT 1 FROM draft_assistance.contexts WHERE namespace=%s AND "
                "security_domain=%s AND context_id=%s AND "
                "initiating_principal_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    spec.root_context_id,
                    spec.subject_id,
                ),
            ).fetchone()
            if not root:
                raise AuthorityError("TASK_DELEGATION_ROOT_INVALID")
            previous = c.execute(
                "SELECT delegation_id,digest FROM "
                "authorization_admin.task_delegations WHERE tenant_id=%s AND "
                "security_domain=%s AND issuer_id=%s AND idempotency_key=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    context.principal_id,
                    spec.idempotency_key,
                ),
            ).fetchone()
            if previous:
                if previous["digest"] != payload_digest:
                    raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
                return previous["delegation_id"]
            conflict = c.execute(
                "SELECT 1 FROM authorization_admin.task_delegations WHERE "
                "tenant_id=%s AND security_domain=%s AND (task_id=%s OR "
                "subject_id=%s OR root_context_id=%s)",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    spec.task_id,
                    spec.subject_id,
                    spec.root_context_id,
                ),
            ).fetchone()
            if conflict:
                raise AuthorityError("TASK_DELEGATION_ALREADY_BOUND")
            for kind in ("understanding", "planning"):
                b = getattr(spec, kind)
                policy = c.execute(
                    "SELECT * FROM draft_provider_budget.policies WHERE "
                    "namespace=%s AND security_domain=%s AND ledger_id=%s FOR "
                    "UPDATE",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        b.ledger_id,
                    ),
                ).fetchone()
                if not policy or any(
                    policy[k] != v
                    for k, v in {
                        "profile_revision_id": b.profile_revision_id,
                        "profile_digest": b.profile_digest,
                        "call_cap": b.calls,
                        "total_cost_cap_microusd": b.cost_microusd,
                    }.items()
                ):
                    raise AuthorityError("TASK_DELEGATION_BUDGET_MISMATCH")
            identity = "task-delegation:" + secrets.token_hex(16)
            c.execute(
                "INSERT INTO authorization_admin.task_delegations "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    identity,
                    spec.task_id,
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    spec.subject_id,
                    spec.root_context_id,
                    context.principal_id,
                    self.grants.generation.generation,
                    self.grants.recovery_epoch,
                    now,
                    expires,
                    spec.idempotency_key,
                    payload_digest,
                    Jsonb(record),
                ),
            )
            c.execute(
                "INSERT INTO "
                "authorization_admin.task_delegation_control(delegation_id) "
                "VALUES(%s)",
                (identity,),
            )
            for kind in ("understanding", "planning"):
                c.execute(
                    "INSERT INTO authorization_admin.task_delegation_ledgers "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        getattr(spec, kind).ledger_id,
                        identity,
                        kind,
                    ),
                )
            self.repository._audit(
                c,
                event_type="TASK_DELEGATION_APPROVED",
                actor_id=context.principal_id,
                outcome="APPROVED",
                reason="BOUNDED_TASK",
                occurred_at=now,
                scope=context.scope,
                subject_id=identity,
                recovery_epoch=self.grants.recovery_epoch,
            )
            return identity

    def revoke(self, context, identity):
        self._admin(context)
        with self.repository.connection_scope() as c:
            self._admin(context, c)
            row = c.execute(
                "SELECT * FROM authorization_admin.task_delegations WHERE "
                "delegation_id=%s AND tenant_id=%s AND security_domain=%s FOR "
                "UPDATE",
                (identity, context.scope.tenant_id, context.scope.security_domain),
            ).fetchone()
            if row is None:
                raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
            c.execute(
                "INSERT INTO authorization_admin.task_delegation_revocations "
                "VALUES(%s,%s,clock_timestamp()) ON CONFLICT DO NOTHING",
                (identity, context.principal_id),
            )
            c.execute(
                "UPDATE authorization_admin.task_delegation_control SET "
                "revoked=true WHERE delegation_id=%s",
                (identity,),
            )
            self.repository._audit(
                c,
                event_type="TASK_DELEGATION_REVOKED",
                actor_id=context.principal_id,
                outcome="REVOKED",
                reason="BOUNDED_TASK",
                occurred_at=datetime.now(UTC),
                scope=context.scope,
                subject_id=identity,
                recovery_epoch=self.grants.recovery_epoch,
            )

    def authorize(self, context, identity, request_id):
        try:
            return self._authorize(context, identity, request_id)
        except AuthorityError:
            with self.repository.connection_scope() as c:
                self.repository._audit(
                    c,
                    event_type="TASK_DELEGATION_DENIED",
                    actor_id=context.principal_id,
                    outcome="DENIED",
                    reason="BOUNDED_TASK",
                    occurred_at=datetime.now(UTC),
                    scope=context.scope,
                    recovery_epoch=self.grants.recovery_epoch,
                )
            raise

    def _authorize(self, context, identity, request_id):
        with self.repository.connection_scope() as c:
            row, now = active(c, identity, lock=True)
            from .task_timeout_revision import effective_limits

            if any(
                effective_limits(c, row, kind) != self.configurations[kind]
                for kind in ("understanding", "planning")
            ):
                raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
            if (row["subject_id"], row["tenant_id"], row["security_domain"]) != (
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            ):
                raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
            # Pin the authenticated subject and independent issuer's current
            # generation. The caller never obtains their credential or meta grant.
            credential_id = self.repository._current_credential_id(
                c,
                context,
                now=now,
                recovery_epoch=self.grants.recovery_epoch,
                lock_session=True,
            )
            if (
                row.get("_continuity")
                and credential_id != row["_continuity"]["subject_credential_id"]
            ):
                raise AuthorityError("TASK_CONTINUITY_IDENTITY_INVALID")
            credential = self.grants.generation.credential_by_id(credential_id)
            if credential is None or now >= credential.expires_at:
                raise AuthorityError("TASK_DELEGATION_SUBJECT_INVALID")
            c.execute(
                "SELECT request_id FROM authorization_admin.grant_requests WHERE "
                "request_id=%s FOR UPDATE",
                (request_id,),
            )
            request = self.repository._request(c, request_id)
            if (
                request.subject_principal_id != context.principal_id
                or request.scope != context.scope
            ):
                raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
            allowed = PURPOSES.get(request.purpose, set())
            for member in request.members:
                from .task_identity_continuity import require_unrevoked_member

                require_unrevoked_member(c, row, member)
                if (
                    (member.owner, member.action) not in allowed
                    or not self.grants.target_validator.is_known_exact_target(
                        context, member, connection=c
                    )
                    or not target_in_task(c, row, member)
                ):
                    raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
            previous = c.execute(
                "SELECT decision_id FROM "
                "authorization_admin.task_delegation_decisions WHERE "
                "delegation_id=%s AND request_id=%s",
                (identity, request_id),
            ).fetchone()
            if previous:
                return previous["decision_id"]
            if request.status is not GrantRequestStatus.PENDING:
                raise AuthorityError("AUTHORIZATION_STATE_STALE")
            from .task_development import revision

            expires = min(credential.expires_at, now + timedelta(hours=8))
            if not revision(c, identity):
                expires = min(expires, row["expires_at"])
            if row.get("_continuity"):
                expires = min(expires, row["_continuity"]["expires_at"])
            decision_id = "grant-decision-" + secrets.token_hex(16)
            decision = GrantDecision(
                decision_id,
                request_id,
                "service:task-delegation",
                identity,
                True,
                "BOUNDED_TASK",
                "POLICY",
                row["digest"],
                self.grants.generation.policy_version,
                "task-delegation:" + identity,
                now,
            )
            c.execute(
                "INSERT INTO "
                "authorization_admin.grant_decisions(decision_id,request_id,"
                "issuer_principal_id,issuer_meta_decision_id,approved,reason_category,"
                "basis_type,basis_reference_digest,policy_version,audit_source,"
                "created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    decision_id,
                    request_id,
                    decision.issuer_principal_id,
                    identity,
                    True,
                    decision.reason_category,
                    "POLICY",
                    row["digest"],
                    decision.policy_version,
                    decision.audit_source,
                    now,
                ),
            )
            for member in request.members:
                self.repository._insert_grant(
                    c,
                    GrantId("grant-" + secrets.token_hex(16)),
                    request,
                    decision,
                    member,
                    now,
                    expires,
                    self.grants.recovery_epoch,
                )
            c.execute(
                "INSERT INTO authorization_admin.task_delegation_decisions "
                "VALUES(%s,%s,%s,%s)",
                (
                    decision_id,
                    identity,
                    request_id,
                    digest([asdict(m) for m in request.members]),
                ),
            )
            c.execute(
                "UPDATE authorization_admin.grant_requests SET "
                "state='APPROVED',aggregate_version=aggregate_version+1,"
                "decided_at=%s WHERE request_id=%s",
                (now, request_id),
            )
            self.repository._audit(
                c,
                event_type="TASK_DELEGATION_EXACT_GRANTED",
                actor_id=decision.issuer_principal_id,
                outcome="APPROVED",
                reason="BOUNDED_TASK",
                occurred_at=now,
                scope=context.scope,
                subject_id=identity,
                recovery_epoch=self.grants.recovery_epoch,
            )
            return decision_id

    def read(self, context, identity):
        with self.repository.connection_scope() as c:
            row = c.execute(
                "SELECT * FROM authorization_admin.task_delegations WHERE "
                "delegation_id=%s AND tenant_id=%s AND security_domain=%s",
                (identity, context.scope.tenant_id, context.scope.security_domain),
            ).fetchone()
            if row is None:
                raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
            if context.principal_id != row["subject_id"]:
                self._admin(context)
            revoked = c.execute(
                "SELECT revoked_at FROM "
                "authorization_admin.task_delegation_revocations WHERE "
                "delegation_id=%s",
                (identity,),
            ).fetchone()
            from .task_cases import cases
            from .task_development import revision, stopped
            from .task_identity_continuity import latest
            from .task_timeout_revision import current as timeout_revision

            return {
                "identity_continuity": latest(c, identity),
                "timeout_revision": timeout_revision(c, identity),
                "development_stopped": stopped(c, identity),
                "development_revision": revision(c, identity),
                "cases": cases(c, identity),
                "original_digest": row["digest"],
                "delegation_id": identity,
                "approval": row["record"],
                "issuer_id": row["issuer_id"],
                "created_at": row["created_at"],
                "revoked_at": revoked["revoked_at"] if revoked else None,
            }


def configured_limits(profile, configuration, budget, *, planning=False):
    binding = profile.binding
    suffix = f"{binding.resource_id}:{binding.revision_id}:{binding.digest}"
    return {
        "ledger_id": budget.ledger_id,
        "configuration_digest": digest(
            {"profile": asdict(profile), "provider": asdict(configuration)}
        ),
        "profile_revision_id": profile.profile_revision_id,
        "profile_digest": profile.profile_digest,
        "model_target": ("model:invocation:plan-suggestion:" if planning else "")
        + suffix,
        "calls": budget.call_cap,
        "input_tokens": configuration.maximum_input_tokens,
        "output_tokens": configuration.maximum_output_tokens,
        "cost_microusd": budget.total_cost_cap_microusd,
    }


def grant_condition(connection, credential_id=None):
    """SQL predicate for existing grant readers; legacy grants remain unchanged."""
    if not available(connection):
        return ""
    has_extension = (
        connection.execute(
            "SELECT to_regclass("
            "'authorization_admin.task_development_revisions') AS name"
        ).fetchone()["name"]
        is not None
    )
    expiry = "d.expires_at<=clock_timestamp()"
    if has_extension:
        expiry = (
            "(" + expiry + " AND NOT EXISTS(SELECT 1 FROM "
            "authorization_admin.task_development_revisions v "
            "WHERE v.delegation_id=d.delegation_id))"
        )
    stop_predicate = ""
    if has_extension:
        stop_predicate = (
            "EXISTS(SELECT 1 FROM authorization_admin.task_development_stops st "
            "WHERE st.delegation_id=d.delegation_id) OR "
        )
    from .task_identity_continuity import available as continuity_available

    generation_mismatch = (
        "d.generation<>(SELECT generation FROM "
        "authorization_admin.active_generation WHERE singleton=true)"
    )
    if continuity_available(connection):
        from psycopg.sql import Literal

        credential_sql = Literal(credential_id).as_string(connection)
        generation_mismatch = (
            "NOT ("
            + generation_mismatch.replace("<>", "=")
            + (
                " OR EXISTS(SELECT 1 FROM "
                "authorization_admin.task_identity_continuities cc JOIN "
                "authorization_admin.task_identity_transitions tr "
                "USING(transition_id) JOIN authorization_admin.active_generation "
                "ag ON ag.singleton=true WHERE cc.delegation_id=d.delegation_id "
                "AND cc.generation=ag.generation AND "
                "cc.recovery_epoch=ag.recovery_epoch AND "
                "tr.generation_digest=ag.generation_digest AND "
                "cc.expires_at>clock_timestamp() AND g.created_at>=cc.created_at "
                + "AND cc.subject_credential_id="
                + credential_sql
                + " "
                + "AND NOT EXISTS(SELECT 1 FROM "
                "authorization_admin.task_identity_continuities nx WHERE "
                "nx.delegation_id=cc.delegation_id AND nx.ordinal>cc.ordinal) AND "
                "NOT EXISTS(SELECT 1 FROM "
                "authorization_admin.task_identity_continuity_revocations cr WHERE"
                " cr.continuity_id=cc.continuity_id)))"
            )
        )
    return (
        " AND NOT EXISTS (SELECT 1 FROM "
        "authorization_admin.task_delegation_decisions td JOIN "
        "authorization_admin.task_delegations d USING(delegation_id) WHERE "
        "td.decision_id=g.decision_id AND ("
        + expiry
        + " OR "
        + stop_predicate
        + "EXISTS(SELECT 1 FROM authorization_admin.task_delegation_revocations r "
        "WHERE r.delegation_id=d.delegation_id) OR "
        + generation_mismatch
        + " OR d.recovery_epoch<>g.recovery_epoch)) "
    )


def guard_budget(connection, budget, invocation, quote):
    """Atomic admission in the original budget transaction; unknowns stay held."""
    if not available(connection):
        return
    link = connection.execute(
        "SELECT delegation_id,purpose FROM "
        "authorization_admin.task_delegation_ledgers WHERE tenant_id=%s AND "
        "security_domain=%s AND ledger_id=%s",
        (
            invocation.scope.namespace,
            invocation.scope.security_domain,
            budget.ledger_id,
        ),
    ).fetchone()
    if not link:
        return
    row, _ = active(connection, link["delegation_id"], lock=True)
    from .task_development import permitted_unknowns, revision

    permitted = permitted_unknowns(connection, row, invocation)
    from .task_timeout_revision import effective_limits

    limits = effective_limits(connection, row, link["purpose"], invocation)
    if getattr(budget, "delegation_configuration", None) != limits:
        raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
    if (
        not 1 <= quote.input_token_upper_bound <= limits["input_tokens"]
        or quote.output_token_ceiling > limits["output_tokens"]
    ):
        raise AuthorityError("TASK_DELEGATION_TOKEN_LIMIT")
    if any(
        r["state"] in {"OUTCOME_UNKNOWN", "CANCELLATION_REQUESTED"}
        or (r.get("localCleanup") or {}).get("reason") == "CLEANUP_FAILURE"
        for r in draft_records(connection, row)
    ):
        raise AuthorityError("TASK_DELEGATION_OUTCOME_UNKNOWN")
    unknown_plans = connection.execute(
        "SELECT i.invocation_id FROM workflow_planning.invocations i LEFT JOIN "
        "workflow_planning.invocation_results r "
        "USING(namespace,security_domain,invocation_id) WHERE i.namespace=%s AND "
        "i.security_domain=%s AND i.actor_id=%s AND "
        "(r.record->>'technical_status'='OUTCOME_UNKNOWN' "
        "OR (i.invocation_id<>%s AND r.invocation_id IS NULL AND EXISTS(SELECT 1 FROM "
        "draft_provider_budget.reservations br "
        "JOIN draft_provider_budget.settlements bs "
        "USING(namespace,security_domain,ledger_id,reservation_id) "
        "WHERE br.namespace=i.namespace "
        "AND br.security_domain=i.security_domain "
        "AND br.invocation_id=i.invocation_id)))",
        (
            row["tenant_id"],
            row["security_domain"],
            row["subject_id"],
            invocation.invocation_id,
        ),
    ).fetchall()
    if any(
        planning_record(connection, row, r["invocation_id"])
        and r["invocation_id"] not in permitted
        for r in unknown_plans
    ):
        raise AuthorityError("TASK_DELEGATION_OUTCOME_UNKNOWN")
    if link["purpose"] == "understanding":
        records = draft_records(connection, row)
        matches = [r for r in records if r["invocationId"] == invocation.invocation_id]
        if not matches or not target_in_task(
            connection,
            row,
            ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", matches[0]["modelTarget"]),
        ):
            raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
    elif planning_record(connection, row, invocation.invocation_id) is None:
        raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
    # Both purpose ledgers share the delegation lock. A pending reservation,
    # including UNKNOWN or a crashed local worker, blocks all new admissions.
    pending = connection.execute(
        "SELECT 1 FROM draft_provider_budget.reservations r JOIN "
        "authorization_admin.task_delegation_ledgers l ON "
        "(r.namespace,r.security_domain,r.ledger_id)="
        "(l.tenant_id,l.security_domain,l.ledger_id) "
        "LEFT JOIN draft_provider_budget.settlements s ON "
        "(s.namespace,s.security_domain,s.ledger_id,s.reservation_id)="
        "(r.namespace,r.security_domain,r.ledger_id,r.reservation_id) "
        "WHERE l.delegation_id=%s AND s.reservation_id IS NULL "
        "AND r.invocation_id<>%s AND NOT (r.invocation_id=ANY(%s)) LIMIT 1",
        (row["delegation_id"], invocation.invocation_id, list(permitted)),
    ).fetchone()
    if pending:
        raise AuthorityError("TASK_DELEGATION_PENDING_RESERVATION")
    return bool(revision(connection, row["delegation_id"]))


def lock_grant_delegations(connection, context, grant):
    if not available(connection):
        return
    connection.execute(
        "SELECT control.delegation_id FROM "
        "authorization_admin.task_delegation_control control JOIN "
        "authorization_admin.task_delegation_decisions td USING(delegation_id) "
        "JOIN authorization_admin.grants g ON td.decision_id=g.decision_id WHERE "
        "g.subject_principal_id=%s AND g.tenant_id=%s AND g.security_domain=%s AND "
        "g.owner=%s AND g.action=%s AND g.exact_resource=%s ORDER BY "
        "control.delegation_id FOR SHARE OF control",
        (
            context.principal_id,
            context.scope.tenant_id,
            context.scope.security_domain,
            grant.owner,
            grant.action,
            grant.exact_resource,
        ),
    ).fetchall()


def record_created_object(
    connection, context, owner, result, *, draft_invocation_id=None
):
    """Owner-side binding, in the creation transaction, never a client task label.

    This bounded mode permits one immutable task per subject/isolated scope.
    Objects created by that subject in this scope belong to that task. Existing
    objects cannot be adopted and task IDs cannot be swapped by a request body.
    """
    if not available(connection):
        return result
    row = connection.execute(
        "SELECT delegation_id FROM authorization_admin.task_delegations WHERE "
        "subject_id=%s AND tenant_id=%s AND security_domain=%s",
        (context.principal_id, context.scope.tenant_id, context.scope.security_domain),
    ).fetchone()
    if not row:
        return result
    delegation, _ = active(connection, row["delegation_id"], lock=True)
    revision = result["revision"]
    if revision["created_by"] != context.principal_id:
        raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
    created = revision["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)
    if created < delegation["created_at"]:
        raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
    identities = (
        [revision["business_problem_id"]]
        if owner == "BUSINESS_PROBLEM"
        else [revision["success_criterion_id"], revision["revision_id"]]
    )
    if owner == "BUSINESS_PROBLEM":
        enrolled_case = False
        if draft_invocation_id:
            from .task_cases import bind_problem

            enrolled_case = bind_problem(
                connection, delegation, context, identities[0], draft_invocation_id
            )
        previous = connection.execute(
            "SELECT resource_id FROM authorization_admin.task_delegation_resources "
            "WHERE delegation_id=%s AND owner='BUSINESS_PROBLEM'",
            (row["delegation_id"],),
        ).fetchone()
        if previous and previous["resource_id"] != identities[0] and not enrolled_case:
            raise AuthorityError("TASK_DELEGATION_PROBLEM_ALREADY_BOUND")
    for identity in identities:
        c = connection.execute(
            "INSERT INTO authorization_admin.task_delegation_resources "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING delegation_id",
            (
                context.scope.tenant_id,
                context.scope.security_domain,
                owner,
                identity,
                row["delegation_id"],
            ),
        ).fetchone()
        if c is None:
            c = connection.execute(
                "SELECT delegation_id FROM "
                "authorization_admin.task_delegation_resources WHERE tenant_id=%s "
                "AND security_domain=%s AND owner=%s AND resource_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    owner,
                    identity,
                ),
            ).fetchone()
            if c["delegation_id"] != row["delegation_id"]:
                raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
    return result
