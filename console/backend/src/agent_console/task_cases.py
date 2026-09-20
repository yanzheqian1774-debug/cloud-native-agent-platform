"""Independently signed, explicit 323 cases on the original task and ledgers."""

from datetime import UTC, datetime

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError


class CaseEnrollment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context_id: str = Field(min_length=1, max_length=200)
    case_label: str = Field(min_length=1, max_length=200)
    description_digest: str = Field(pattern="^[a-f0-9]{64}$")
    unknown_invocation_ids: list[str] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)


def cases(c, identity):
    if not c.execute(
        "SELECT to_regclass('authorization_admin.task_cases') AS name"
    ).fetchone()["name"]:
        return []
    return c.execute(
        "SELECT * FROM authorization_admin.task_cases WHERE delegation_id=%s ORDER BY"
        " created_at,context_id",
        (identity,),
    ).fetchall()


def context_ids(c, row):
    return [
        row["root_context_id"],
        *(r["context_id"] for r in cases(c, row["delegation_id"])),
    ]


def enroll(service, context, identity, spec):
    from .task_delegation import active, digest
    from .task_development import revision, unknown_facts

    service._admin(context)
    with service.repository.connection_scope() as c:
        service._admin(context, c)
        row, _ = active(c, identity, lock=True)
        if context.principal_id == row["subject_id"]:
            raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
        rev = revision(c, identity)
        if (
            not rev
            or row["task_id"] != "S5-V023-ARCH-323"
            or (row["tenant_id"], row["security_domain"])
            != (context.scope.tenant_id, context.scope.security_domain)
        ):
            raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
        if any(
            row["record"][kind] != service.configurations[kind]
            for kind in ("understanding", "planning")
        ):
            raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
        root = c.execute(
            "SELECT 1 FROM draft_assistance.contexts WHERE namespace=%s AND "
            "security_domain=%s AND context_id=%s AND initiating_principal_id=%s",
            (
                row["tenant_id"],
                row["security_domain"],
                spec.context_id,
                row["subject_id"],
            ),
        ).fetchone()
        if not root or spec.context_id == row["root_context_id"]:
            raise AuthorityError("TASK_CASE_CONTEXT_INVALID")
        facts, _ = unknown_facts(c, row, spec.unknown_invocation_ids)
        record = {
            **spec.model_dump(),
            "facts": facts,
            "development_revision_digest": rev["digest"],
            "subject_id": row["subject_id"],
            "tenant_id": row["tenant_id"],
            "security_domain": row["security_domain"],
            "generation": row["generation"],
            "recovery_epoch": row["recovery_epoch"],
            "configurations": service.configurations,
            "synthetic_case_only": True,
        }
        previous = c.execute(
            "SELECT * FROM authorization_admin.task_cases WHERE delegation_id=%s AND "
            "(context_id=%s OR idempotency_key=%s)",
            (identity, spec.context_id, spec.idempotency_key),
        ).fetchone()
        if previous:
            if previous["digest"] != digest(record):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return previous
        # A context cannot acquire case membership after producing a Problem.
        if c.execute(
            "SELECT 1 FROM draft_assistance.invocation_versions WHERE namespace=%s "
            "AND security_domain=%s AND record->>'contextId'=%s AND "
            "record->>'problemId' IS NOT NULL LIMIT 1",
            (row["tenant_id"], row["security_domain"], spec.context_id),
        ).fetchone():
            raise AuthorityError("TASK_CASE_ALREADY_MATERIALIZED")
        c.execute(
            "INSERT INTO "
            "authorization_admin.task_cases(delegation_id,context_id,issuer_id,idempotency_key,digest,record)"
            " VALUES(%s,%s,%s,%s,%s,%s)",
            (
                identity,
                spec.context_id,
                context.principal_id,
                spec.idempotency_key,
                digest(record),
                Jsonb(record),
            ),
        )
        service.repository._audit(
            c,
            event_type="TASK_CASE_ENROLLED",
            actor_id=context.principal_id,
            outcome="APPROVED",
            reason="EXPLICIT_SYNTHETIC_CASE",
            occurred_at=datetime.now(UTC),
            scope=context.scope,
            subject_id=identity,
            recovery_epoch=row["recovery_epoch"],
        )
        return next(r for r in cases(c, identity) if r["context_id"] == spec.context_id)


def bind_problem(c, row, context, problem_id, invocation_id):
    from .task_delegation import draft_records

    draft = next(
        (r for r in draft_records(c, row) if r["invocationId"] == invocation_id), None
    )
    if (
        not draft
        or draft["state"] != "SUCCEEDED"
        or draft.get("resultKind") != "DRAFT_READY"
    ):
        raise AuthorityError("TASK_CASE_DRAFT_REQUIRED")
    if draft["contextId"] == row["root_context_id"]:
        return False
    case = next(
        (
            r
            for r in cases(c, row["delegation_id"])
            if r["context_id"] == draft["contextId"]
        ),
        None,
    )
    if not case or draft.get("problemId") not in (None, problem_id):
        raise AuthorityError("TASK_CASE_TARGET_DENIED")
    prior = c.execute(
        "SELECT context_id,problem_id,invocation_id FROM "
        "authorization_admin.task_case_problems WHERE delegation_id=%s AND "
        "(context_id=%s OR problem_id=%s)",
        (row["delegation_id"], case["context_id"], problem_id),
    ).fetchone()
    expected = {
        "context_id": case["context_id"],
        "problem_id": problem_id,
        "invocation_id": invocation_id,
    }
    if prior and prior != expected:
        raise AuthorityError("TASK_CASE_PROBLEM_ALREADY_BOUND")
    if not prior:
        c.execute(
            "INSERT INTO "
            "authorization_admin.task_case_problems(delegation_id,context_id,problem_id,invocation_id)"
            " VALUES(%s,%s,%s,%s)",
            (row["delegation_id"], case["context_id"], problem_id, invocation_id),
        )

    return True


def historical_unknowns(c, row, invocation):
    """Only the exact signed liabilities; all new/other pending calls still block."""
    from .task_delegation import draft_records, planning_record
    from .task_development import revision, unknown_facts

    enrollments = cases(c, row["delegation_id"])
    if not enrollments:
        return set()
    draft = next(
        (
            r
            for r in draft_records(c, row)
            if r["invocationId"] == invocation.invocation_id
        ),
        None,
    )
    context_id = draft["contextId"] if draft else None
    if context_id is None:
        planning = planning_record(c, row, invocation.invocation_id)
        if planning:
            bound = c.execute(
                "SELECT context_id FROM authorization_admin.task_case_problems WHERE "
                "delegation_id=%s AND problem_id=%s",
                (
                    row["delegation_id"],
                    planning["target"]["problem"]["problem"]["resource_id"],
                ),
            ).fetchone()
            context_id = bound["context_id"] if bound else None
    case = next((r for r in enrollments if r["context_id"] == context_id), None)
    if case is None:
        return set()
    record = case["record"]
    rev = revision(c, row["delegation_id"])
    if (
        not rev
        or rev["digest"] != record["development_revision_digest"]
        or any(
            record[k] != row[k]
            for k in (
                "subject_id",
                "tenant_id",
                "security_domain",
                "generation",
                "recovery_epoch",
            )
        )
    ):
        raise AuthorityError("TASK_CASE_INACTIVE")
    facts, _ = unknown_facts(c, row, record["unknown_invocation_ids"])
    if facts != record["facts"]:
        raise AuthorityError("TASK_CASE_RECEIPT_MISMATCH")
    return {f["invocation_id"] for f in facts}
