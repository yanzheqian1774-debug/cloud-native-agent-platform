"""Independent, single-variable 323 planning read-timeout revision."""

from dataclasses import replace
from datetime import UTC, datetime

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError


class TimeoutRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    problem_id: str = Field(min_length=1, max_length=200)
    original_configuration_digest: str = Field(pattern="^[a-f0-9]{64}$")
    previous_read_seconds: int = Field(ge=1, le=300)
    read_seconds: int = Field(ge=1, le=300)
    idempotency_key: str = Field(min_length=1, max_length=200)


def current(c, identity):
    if not c.execute(
        "SELECT to_regclass('authorization_admin.task_timeout_revisions') AS name"
    ).fetchone()["name"]:
        return None
    return c.execute(
        "SELECT * FROM authorization_admin.task_timeout_revisions "
        "WHERE delegation_id=%s",
        (identity,),
    ).fetchone()


def effective_limits(c, row, purpose, invocation=None):
    original = row["record"][purpose]
    revision = current(c, row["delegation_id"]) if purpose == "planning" else None
    if revision is None:
        return original
    record = revision["record"]
    if record["original_limits"] != original or any(
        record[k] != row[k]
        for k in (
            "subject_id",
            "tenant_id",
            "security_domain",
            "generation",
            "recovery_epoch",
        )
    ):
        raise AuthorityError("TASK_TIMEOUT_REVISION_INACTIVE")
    if invocation is not None:
        from .task_delegation import planning_record

        inv = planning_record(c, row, invocation.invocation_id)
        if (
            not inv
            or inv["target"]["problem"]["problem"]["resource_id"]
            != revision["problem_id"]
        ):
            raise AuthorityError("TASK_TIMEOUT_TARGET_DENIED")
    return record["limits"]


def revise(service, context, identity, spec):
    from .task_delegation import active, configured_limits, digest
    from .task_development import revision

    service._admin(context)
    with service.repository.connection_scope() as c:
        service._admin(context, c)
        row, _ = active(c, identity, lock=True)
        if context.principal_id == row["subject_id"]:
            raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
        if (
            row["task_id"] != "S5-V023-ARCH-323"
            or not revision(c, identity)
            or (row["tenant_id"], row["security_domain"])
            != (context.scope.tenant_id, context.scope.security_domain)
            or service.timeout_source is None
        ):
            raise AuthorityError("TASK_TIMEOUT_REVISION_DENIED")
        binding = c.execute(
            "SELECT 1 FROM authorization_admin.task_case_problems WHERE "
            "delegation_id=%s AND problem_id=%s",
            (identity, spec.problem_id),
        ).fetchone()
        if not binding:
            raise AuthorityError("TASK_TIMEOUT_TARGET_DENIED")
        profile, configuration, budget = service.timeout_source
        if not (
            spec.previous_read_seconds
            < spec.read_seconds
            <= configuration.total_timeout_seconds
            and configuration.read_timeout_seconds
            in (spec.previous_read_seconds, spec.read_seconds)
        ):
            raise AuthorityError("TASK_TIMEOUT_BOUNDS_INVALID")
        old = configured_limits(
            profile,
            replace(configuration, read_timeout_seconds=spec.previous_read_seconds),
            budget,
            planning=True,
        )
        new = configured_limits(
            profile,
            replace(configuration, read_timeout_seconds=spec.read_seconds),
            budget,
            planning=True,
        )
        if (
            old != row["record"]["planning"]
            or old["configuration_digest"] != spec.original_configuration_digest
        ):
            raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
        record = {
            **spec.model_dump(),
            "original_limits": old,
            "limits": new,
            "total_seconds": configuration.total_timeout_seconds,
            **{
                k: row[k]
                for k in (
                    "subject_id",
                    "tenant_id",
                    "security_domain",
                    "generation",
                    "recovery_epoch",
                )
            },
        }
        prior = current(c, identity)
        if prior:
            if prior["digest"] != digest(record):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return prior
        c.execute(
            "INSERT INTO authorization_admin.task_timeout_revisions "
            "(delegation_id,problem_id,issuer_id,digest,record) VALUES(%s,%s,%s,%s,%s)",
            (
                identity,
                spec.problem_id,
                context.principal_id,
                digest(record),
                Jsonb(record),
            ),
        )
        service.repository._audit(
            c,
            event_type="TASK_PLANNING_TIMEOUT_REVISED",
            actor_id=context.principal_id,
            outcome="APPROVED",
            reason="BOUNDED_SINGLE_VARIABLE_READ_TIMEOUT",
            occurred_at=datetime.now(UTC),
            scope=context.scope,
            subject_id=identity,
            recovery_epoch=row["recovery_epoch"],
        )
        return current(c, identity)
