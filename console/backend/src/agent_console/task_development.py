"""323-only development revision and exact diagnostic successor admission.

The signed revision changes admission policy, never historical budget facts.
A diagnostic permit is an owner-verified observation, not a Human signature.
"""

import os
from datetime import UTC, datetime
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError


class DevelopmentRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    original_digest: str = Field(pattern="^[a-f0-9]{64}$")
    mode: Literal["UNTIL_COMPLETE_PAUSE_OR_REVOKE"]
    accept_unknown_remote_processing_and_cost: Literal[True]
    synthetic_case_only: Literal[True]
    idempotency_key: str = Field(min_length=1, max_length=200)


class DiagnosticAdmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_key: str = Field(min_length=1, max_length=200)
    unknown_invocation_ids: list[str] = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1000)


def revision(connection, identity):
    if (
        connection.execute(
            "SELECT to_regclass("
            "'authorization_admin.task_development_revisions') AS name"
        ).fetchone()["name"]
        is None
    ):
        return None
    return connection.execute(
        "SELECT * FROM authorization_admin.task_development_revisions "
        "WHERE delegation_id=%s",
        (identity,),
    ).fetchone()


def revise(service, context, identity, spec):
    from .task_delegation import active, digest

    service._admin(context)
    with service.repository.connection_scope() as c:
        service._admin(context, c)
        row, _ = active(c, identity, lock=True, allow_expired=True)
        if context.principal_id == row["subject_id"]:
            raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
        if (row["tenant_id"], row["security_domain"]) != (
            context.scope.tenant_id,
            context.scope.security_domain,
        ) or row["task_id"] != "S5-V023-ARCH-323":
            raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
        if spec.original_digest != row["digest"] or any(
            row["record"][kind] != service.configurations[kind]
            for kind in ("understanding", "planning")
        ):
            raise AuthorityError("TASK_DELEGATION_CONFIGURATION_MISMATCH")
        record = spec.model_dump(mode="json")
        record.update(
            task_id=row["task_id"],
            subject_id=row["subject_id"],
            tenant_id=row["tenant_id"],
            security_domain=row["security_domain"],
            generation=row["generation"],
            recovery_epoch=row["recovery_epoch"],
            root_context_id=row["root_context_id"],
            configurations=service.configurations,
        )
        previous = revision(c, identity)
        if previous:
            if previous["digest"] != digest(record):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return previous
        c.execute(
            "INSERT INTO authorization_admin.task_development_revisions "
            "(delegation_id,issuer_id,digest,record) VALUES(%s,%s,%s,%s)",
            (identity, context.principal_id, digest(record), Jsonb(record)),
        )
        service.repository._audit(
            c,
            event_type="TASK_DEVELOPMENT_REVISED",
            actor_id=context.principal_id,
            outcome="APPROVED",
            reason="CONTINUOUS_DEVELOPMENT_UNKNOWN_RISK_ACCEPTED",
            occurred_at=datetime.now(UTC),
            scope=context.scope,
            subject_id=identity,
            recovery_epoch=row["recovery_epoch"],
        )
        return revision(c, identity)


def unknown_facts(c, row, identities):
    """Verify persisted planning owner receipts; PID absence alone is insufficient."""
    from .task_delegation import digest, planning_record

    if len(set(identities)) != len(identities):
        raise AuthorityError("DIAGNOSTIC_UNKNOWN_SET_INVALID")
    facts = []
    target = None
    for identity in sorted(identities):
        inv = planning_record(c, row, identity)
        if inv is None:
            raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
        result = c.execute(
            "SELECT record FROM workflow_planning.invocation_results WHERE "
            "namespace=%s AND security_domain=%s AND invocation_id=%s",
            (row["tenant_id"], row["security_domain"], identity),
        ).fetchone()
        receipt = c.execute(
            "SELECT record FROM workflow_planning.provider_receipts WHERE "
            "namespace=%s AND security_domain=%s AND invocation_id=%s",
            (row["tenant_id"], row["security_domain"], identity),
        ).fetchone()
        if (
            not result
            or result["record"].get("technical_status") != "OUTCOME_UNKNOWN"
            or not receipt
        ):
            raise AuthorityError("DIAGNOSTIC_UNKNOWN_RECEIPT_REQUIRED")
        receipt = receipt["record"]
        deadline = receipt.get("deadline", {})
        if (
            deadline.get("reaped") is not True
            or deadline.get("reason") == "CLEANUP_FAILURE"
        ):
            raise AuthorityError("DIAGNOSTIC_WORKER_NOT_REAPED")
        pid = deadline.get("worker_pid")
        if not isinstance(pid, int) or pid <= 0:
            raise AuthorityError("DIAGNOSTIC_WORKER_NOT_REAPED")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        except (PermissionError, OSError):
            raise AuthorityError("DIAGNOSTIC_WORKER_NOT_REAPED") from None
        else:
            raise AuthorityError("DIAGNOSTIC_WORKER_NOT_REAPED")
        reservation = c.execute(
            "SELECT reservation_id FROM draft_provider_budget.reservations WHERE "
            "namespace=%s AND security_domain=%s AND ledger_id=%s AND invocation_id=%s",
            (
                row["tenant_id"],
                row["security_domain"],
                row["record"]["planning"]["ledger_id"],
                identity,
            ),
        ).fetchone()
        if not reservation or reservation["reservation_id"] != receipt.get(
            "reservation_id"
        ):
            raise AuthorityError("DIAGNOSTIC_RESERVATION_MISMATCH")
        current = inv["target"]["problem"]
        if target is not None and current != target:
            raise AuthorityError("TASK_DELEGATION_TARGET_DENIED")
        target = current
        facts.append(
            {
                "invocation_id": identity,
                "reservation_id": reservation["reservation_id"],
                "receipt_digest": digest(receipt),
                "local_worker_reaped": True,
                "remote_processing_and_cost": "UNKNOWN",
            }
        )
    return facts, target


def admit(service, context, identity, spec):
    from .task_delegation import active, digest

    with service.repository.connection_scope() as c:
        row, _ = active(c, identity, lock=True)
        if (row["subject_id"], row["tenant_id"], row["security_domain"]) != (
            context.principal_id,
            context.scope.tenant_id,
            context.scope.security_domain,
        ) or not revision(c, identity):
            raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
        facts, target = unknown_facts(c, row, spec.unknown_invocation_ids)
        record = {
            **spec.model_dump(),
            "facts": facts,
            "target": target,
            "revision_digest": revision(c, identity)["digest"],
        }
        previous = c.execute(
            "SELECT record,digest FROM authorization_admin.task_diagnostic_admissions "
            "WHERE delegation_id=%s AND request_key=%s",
            (identity, spec.request_key),
        ).fetchone()
        if previous:
            if previous["digest"] != digest(record):
                raise AuthorityError("IDEMPOTENCY_PAYLOAD_CONFLICT")
            return previous
        if c.execute(
            "SELECT 1 FROM workflow_planning.invocations WHERE namespace=%s AND "
            "security_domain=%s AND actor_id=%s AND request_key=%s",
            (
                row["tenant_id"],
                row["security_domain"],
                row["subject_id"],
                spec.request_key,
            ),
        ).fetchone():
            raise AuthorityError("DIAGNOSTIC_NEW_KEY_REQUIRED")
        c.execute(
            "INSERT INTO authorization_admin.task_diagnostic_admissions "
            "(delegation_id,request_key,actor_id,digest,record) VALUES(%s,%s,%s,%s,%s)",
            (
                identity,
                spec.request_key,
                context.principal_id,
                digest(record),
                Jsonb(record),
            ),
        )
        return {"record": record, "digest": digest(record)}


def permitted_unknowns(c, row, invocation):
    """Only exact diagnostic permits or independently enrolled case liabilities."""
    from .task_cases import historical_unknowns
    from .task_delegation import planning_record

    if not revision(c, row["delegation_id"]):
        return set()
    historical = historical_unknowns(c, row, invocation)
    inv = planning_record(c, row, invocation.invocation_id)
    if inv is None:
        return historical
    permit = c.execute(
        "SELECT a.record FROM authorization_admin.task_diagnostic_admissions a "
        "JOIN workflow_planning.invocations i ON i.request_key=a.request_key "
        "WHERE a.delegation_id=%s AND i.namespace=%s AND i.security_domain=%s "
        "AND i.actor_id=%s AND i.invocation_id=%s",
        (
            row["delegation_id"],
            row["tenant_id"],
            row["security_domain"],
            row["subject_id"],
            invocation.invocation_id,
        ),
    ).fetchone()
    if not permit:
        return historical
    record = permit["record"]
    facts, target = unknown_facts(c, row, record["unknown_invocation_ids"])
    if facts != record["facts"] or target != inv["target"]["problem"]:
        raise AuthorityError("DIAGNOSTIC_TARGET_MISMATCH")
    return historical | {f["invocation_id"] for f in facts}


class DevelopmentStop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["PAUSED", "COMPLETED"]


def stopped(c, identity):
    return (
        revision(c, identity) is not None
        and c.execute(
            "SELECT 1 FROM authorization_admin.task_development_stops "
            "WHERE delegation_id=%s",
            (identity,),
        ).fetchone()
        is not None
    )


def stop(service, context, identity, spec):
    with service.repository.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.task_delegations "
            "WHERE delegation_id=%s AND tenant_id=%s AND security_domain=%s "
            "FOR UPDATE",
            (identity, context.scope.tenant_id, context.scope.security_domain),
        ).fetchone()
        if row is None or not revision(c, identity):
            raise AuthorityError("TASK_DELEGATION_NOT_FOUND")
        if context.principal_id != row["subject_id"]:
            service._admin(context, c)
        c.execute(
            "INSERT INTO authorization_admin.task_development_stops "
            "(delegation_id,actor_id,reason) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (identity, context.principal_id, spec.reason),
        )
        return {"stopped": True}
