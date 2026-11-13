"""Independent one-call recovery; local evidence never settles an UNKNOWN."""

from datetime import datetime
from hashlib import sha256

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .context_call_admission import active, latest, lock, request_row
from .plan_suggestion_invocation import PlanningRequest
from .task_delegation import digest


class RecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: str = Field(min_length=1, max_length=128)
    invocation_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=120)


def migrate(service):
    path = (
        service.repository.migration_path.parent
        / "0063_conversation_planning_recovery.sql"
    )
    checksum = sha256(path.read_bytes()).hexdigest()
    with service.repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3230028)")
        old = c.execute(
            "SELECT checksum FROM authorization_admin.schema_migrations WHERE "
            "version=63"
        ).fetchone()
        if old:
            if old["checksum"] != checksum:
                raise AuthorityError("AUTHORITY_SCHEMA_INCOMPATIBLE")
            return
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO "
            "authorization_admin.schema_migrations(version,checksum,adapter) "
            "VALUES(63,%s,'conversation-planning-recovery-v1')",
            (checksum,),
        )


def available(c):
    return bool(
        c.execute(
            "SELECT "
            "to_regclass('authorization_admin.conversation_planning_recoveries') AS "
            "name"
        ).fetchone()["name"]
    )


def scope(context):
    if isinstance(context, dict):
        return (context["tenant_id"], context["security_domain"], context["subject_id"])
    return (
        context.scope.tenant_id,
        context.scope.security_domain,
        context.principal_id,
    )


def old_record(c, context, identity):
    row = c.execute(
        "SELECT i.record invocation,r.record result,p.record "
        "receipt,a.context_id,a.record admission "
        "FROM workflow_planning.invocations i JOIN "
        "workflow_planning.invocation_results r "
        "USING(namespace,security_domain,invocation_id) "
        "JOIN workflow_planning.provider_receipts p "
        "USING(namespace,security_domain,invocation_id) "
        "JOIN authorization_admin.context_call_requests a ON "
        "a.tenant_id=i.namespace AND a.security_domain=i.security_domain AND "
        "a.first_invocation_id=i.invocation_id "
        "WHERE i.namespace=%s AND i.security_domain=%s AND i.actor_id=%s AND "
        "i.invocation_id=%s",
        (*scope(context), identity),
    ).fetchone()
    if (
        not row
        or row["result"].get("technical_status") != "OUTCOME_UNKNOWN"
        or row["receipt"].get("deadline", {}).get("reaped") is not True
    ):
        raise AuthorityError("PLANNING_RECOVERY_OBSERVATION_REQUIRED")
    if row["receipt"].get("deadline", {}).get("reason") == "CLEANUP_FAILURE":
        raise AuthorityError("PLANNING_RECOVERY_OBSERVATION_REQUIRED")
    reservation = c.execute(
        "SELECT r.* FROM draft_provider_budget.reservations r LEFT JOIN "
        "draft_provider_budget.settlements s USING(namespace,security_domain,"
        "ledger_id,reservation_id) WHERE r.namespace=%s AND r.security_domain=%s "
        "AND r.ledger_id=%s AND r.reservation_id=%s AND r.invocation_id=%s "
        "AND s.reservation_id IS NULL",
        (
            *scope(context)[:2],
            row["admission"]["configuration"]["ledger_id"],
            row["receipt"].get("reservation_id"),
            identity,
        ),
    ).fetchone()
    if not reservation:
        raise AuthorityError("PLANNING_RECOVERY_RESERVATION_REQUIRED")
    # Canonical JSON-safe exact reservation evidence; never settle or release it.
    row["reservation"] = {
        **reservation,
        "created_at": reservation["created_at"].isoformat(),
    }
    return row


def prepare_observation(admission, context, spec):
    """Persist exact server-read evidence. No model, budget or original-row writes."""
    experience = getattr(admission, "conversation_experience", None)
    if experience is None or not experience.experience.matches(context):
        raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
    with admission.repository.connection_scope() as c:
        lock(c, "f3-recovery:" + digest([*scope(context), spec.invocation_id]))
        previous = c.execute(
            "SELECT * FROM authorization_admin.conversation_planning_recoveries "
            "WHERE tenant_id=%s AND security_domain=%s AND subject_id=%s AND "
            "(request_key=%s OR predecessor_invocation_id=%s)",
            (*scope(context), spec.idempotency_key, spec.invocation_id),
        ).fetchall()
        old = old_record(c, context, spec.invocation_id)
        target = old["invocation"]["target"]["problem"]
        source, account, now, expires = experience.require_source(
            admission, c, context, target["problem"]["resource_id"]
        )
        if (
            source["record"].get("conversation_id") != spec.conversation_id
            or old["admission"].get("source_context_id") != source["context_id"]
        ):
            raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
        conversation = c.execute(
            "SELECT owner_id,archived_at FROM private_conversation.conversations "
            "WHERE tenant_id=%s AND security_domain=%s AND conversation_id=%s FOR "
            "SHARE",
            (*scope(context)[:2], spec.conversation_id),
        ).fetchone()
        if (
            not conversation
            or conversation["owner_id"] != context.principal_id
            or conversation["archived_at"] is not None
        ):
            raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
        if (
            old["admission"].get("experience_policy_digest")
            != experience.experience.policy_digest
            or old["admission"]["configuration"] != admission.configuration
        ):
            raise AuthorityError("PLANNING_RECOVERY_CONFIGURATION_CHANGED")
        original = PlanningRequest.model_validate(
            {
                k: v
                for k, v in old["invocation"]["request"].items()
                if k in PlanningRequest.model_fields
            }
        )
        if original.source_proposal is not None:
            raise AuthorityError("PLANNING_RECOVERY_SOURCE_PROPOSAL_UNSUPPORTED")
        identity = "f3-planning-recovery:" + digest(
            [*scope(context), spec.idempotency_key]
        )
        new_key = "recovery:" + digest([identity, spec.invocation_id])
        new_request = original.model_copy(
            update={"idempotency_key": new_key, "predecessor_invocation_id": None}
        ).model_dump(mode="json")
        prior_decision = latest(c, old["context_id"])
        if (
            not prior_decision
            or c.execute(
                "SELECT 1 FROM authorization_admin.context_call_revocations WHERE "
                "admission_id=%s",
                (prior_decision["admission_id"],),
            ).fetchone()
        ):
            raise AuthorityError("PLANNING_RECOVERY_PREDECESSOR_REVOKED")
        expires = min(expires, prior_decision["expires_at"])
        if expires <= now:
            raise AuthorityError("PLANNING_RECOVERY_EXPIRED")
        facts = {
            "provenance": "LOCAL_ONLY",
            "local_cleanup_confirmed": True,
            "old_invocation_digest": digest(old["invocation"]),
            "old_result_digest": digest(old["result"]),
            "provider_receipt_digest": digest(old["receipt"]),
            "reservation_id": old["receipt"].get("reservation_id"),
            "reservation_digest": digest(old["reservation"]),
            "request": new_request,
            "target": target,
            "source_context_id": source["context_id"],
            "understanding_input_source": source["understanding_input_source"],
            "account_id": account["account_id"],
            "account_revision": account["revision"],
            "configuration": admission.configuration,
            "experience_policy_digest": experience.experience.policy_digest,
            "budget_allowance_id": source["record"].get("budget_allowance_id"),
            "authorization_digest": source["record"].get("authorization_digest"),
            "expires_at": expires.isoformat(),
            "maximum_new_calls": 1,
            "observer": context.principal_id,
        }
        if previous:
            if (
                len(previous) != 1
                or previous[0]["recovery_id"] != identity
                or previous[0]["conversation_id"] != spec.conversation_id
                or previous[0]["record"] != facts
            ):
                raise AuthorityError("PLANNING_RECOVERY_ALREADY_BOUND")
            return previous[0]
        row = c.execute(
            "INSERT INTO "
            "authorization_admin.conversation_planning_recoveries(recovery_id,ten"
            "ant_id,security_domain,subject_id,conversation_id,predecessor_invoca"
            "tion_id,request_key,new_request_key,record,digest) VALUES(%s,%s,%s,%"
            "s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                identity,
                *scope(context),
                spec.conversation_id,
                spec.invocation_id,
                spec.idempotency_key,
                new_key,
                Jsonb(facts),
                digest(facts),
            ),
        ).fetchone()
        admission.repository._audit(
            c,
            event_type="PLANNING_RECOVERY_OBSERVATION",
            actor_id=context.principal_id,
            outcome="RECORDED",
            reason="LOCAL_ONLY_NO_SUPPLIER_ADJUDICATION",
            occurred_at=now,
            scope=context.scope,
            subject_id=identity,
            generation=admission.delegation.grants.generation.generation,
            recovery_epoch=admission.delegation.grants.recovery_epoch,
        )
        return row


def find(c, context, *, key=None, identity=None):
    if not available(c):
        return None
    field, value = (
        ("new_request_key", key) if key is not None else ("recovery_id", identity)
    )
    return c.execute(
        "SELECT * FROM authorization_admin.conversation_planning_recoveries WHERE "
        "tenant_id=%s AND security_domain=%s AND subject_id=%s AND " + field + "=%s",
        (*scope(context), value),
    ).fetchone()


def validate(admission, c, context, row, source):
    if not row or digest(row["record"]) != row["digest"]:
        raise AuthorityError("PLANNING_RECOVERY_RECORD_INVALID")
    record = row["record"]
    old = old_record(c, context, row["predecessor_invocation_id"])
    if any(
        record[k] != digest(old[v])
        for k, v in [
            ("old_invocation_digest", "invocation"),
            ("old_result_digest", "result"),
            ("provider_receipt_digest", "receipt"),
            ("reservation_digest", "reservation"),
        ]
    ):
        raise AuthorityError("PLANNING_RECOVERY_EVIDENCE_CHANGED")
    historical = latest(c, old["context_id"])
    if (
        not historical
        or c.execute(
            "SELECT 1 FROM authorization_admin.context_call_revocations "
            "WHERE admission_id=%s",
            (historical["admission_id"],),
        ).fetchone()
    ):
        raise AuthorityError("PLANNING_RECOVERY_PREDECESSOR_REVOKED")
    now = c.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
    if (
        datetime.fromisoformat(record["expires_at"]) <= now
        or record["source_context_id"] != source["context_id"]
        or record["configuration"] != admission.configuration
        or record["experience_policy_digest"]
        != source["record"].get("experience_policy_digest")
        or record["understanding_input_source"] != source["understanding_input_source"]
    ):
        raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
    if (record["account_id"], record["account_revision"]) != (
        source["account_id"],
        source["account_revision"],
    ):
        raise AuthorityError("PLANNING_RECOVERY_ACCOUNT_CHANGED")
    if (record.get("budget_allowance_id"), record.get("authorization_digest")) != (
        source["record"].get("budget_allowance_id"),
        source["record"].get("authorization_digest"),
    ):
        raise AuthorityError("PLANNING_RECOVERY_ALLOWANCE_CHANGED")
    return record


def unresolved(c, source, target):
    if not c.execute(
        "SELECT to_regclass('workflow_planning.invocations') AS name"
    ).fetchone()["name"]:
        return []
    return c.execute(
        "SELECT i.invocation_id FROM workflow_planning.invocations i JOIN "
        "authorization_admin.context_call_requests a ON a.tenant_id=i.namespace AND "
        "a.security_domain=i.security_domain AND "
        "a.first_invocation_id=i.invocation_id LEFT JOIN "
        "workflow_planning.invocation_results r ON r.namespace=i.namespace AND "
        "r.security_domain=i.security_domain AND r.invocation_id=i.invocation_id "
        "WHERE i.namespace=%s AND i.security_domain=%s AND "
        "a.record->>'source_context_id'=%s AND i.record->'target'->'problem'=%s AND "
        "(r.record IS NULL OR r.record->>'technical_status'='OUTCOME_UNKNOWN')",
        (
            source["tenant_id"],
            source["security_domain"],
            source["context_id"],
            Jsonb(target),
        ),
    ).fetchall()


def covered_predecessors(c, context, invocation_id):
    """Successful clarification descendants retain their signed recovery lineage."""
    covered = set()
    for _ in range(8):
        if not invocation_id:
            break
        prior = c.execute(
            "SELECT a.record,r.record result FROM "
            "authorization_admin.context_call_requests a JOIN "
            "workflow_planning.invocations i ON i.namespace=a.tenant_id AND "
            "i.security_domain=a.security_domain AND "
            "i.invocation_id=a.first_invocation_id JOIN "
            "workflow_planning.invocation_results r ON r.namespace=i.namespace AND "
            "r.security_domain=i.security_domain AND "
            "r.invocation_id=i.invocation_id WHERE a.tenant_id=%s AND "
            "a.security_domain=%s AND a.subject_id=%s AND a.first_invocation_id=%s",
            (*scope(context), invocation_id),
        ).fetchone()
        if not prior or prior["result"].get("technical_status") != "SUCCEEDED":
            break
        recovery = (
            find(c, context, identity=prior["record"].get("recovery_id"))
            if prior["record"].get("recovery_id")
            else None
        )
        if recovery:
            covered.add(recovery["predecessor_invocation_id"])
        invocation_id = prior["record"]["target"].get("predecessor_invocation_id")
    return covered


def projection(admission, context, identity):
    with admission.repository.connection_scope() as c:
        row = find(c, context, identity=identity)
        if row is None:
            raise AuthorityError("PLANNING_RECOVERY_NOT_FOUND")
        experience = admission.conversation_experience
        source, _, _, _ = experience.require_source(
            admission, c, context, row["record"]["target"]["problem"]["resource_id"]
        )
        validate(admission, c, context, row, source)
        binding = c.execute(
            "SELECT * FROM "
            "authorization_admin.conversation_planning_recovery_bindings WHERE "
            "recovery_id=%s",
            (identity,),
        ).fetchone()
        value = {
            "recovery_id": identity,
            "conversation_id": row["conversation_id"],
            "old_invocation_id": row["predecessor_invocation_id"],
            "new_request_key": row["new_request_key"],
            "local_cleanup_confirmed": True,
            "provenance": "LOCAL_ONLY",
            "original_outcome": "OUTCOME_UNKNOWN",
            "state": "OBSERVED",
            "expires_at": row["record"]["expires_at"],
        }
        if binding:
            context_row = request_row(c, binding["context_id"])
            require_binding(admission, c, context, context_row, source)
            value.update(
                context_id=binding["context_id"],
                invocation_id=binding["invocation_id"],
                state="AUTHORIZATION_PENDING",
            )
            try:
                active(c, context_row, admission.configuration)
                value["state"] = "AUTHORIZED"
            except AuthorityError as exc:
                if exc.reason_code != "CONTEXT_ADMISSION_REQUIRED":
                    raise
            claimed = c.execute(
                "SELECT 1 FROM workflow_planning.invocations WHERE namespace=%s AND "
                "security_domain=%s AND invocation_id=%s",
                (*scope(context)[:2], binding["invocation_id"]),
            ).fetchone()
            if claimed:
                value["state"] = "DISPATCHED"
        return value


def require_binding(admission, c, context, row, source):
    identity = row["record"].get("recovery_id")
    if not identity:
        return
    recovery = find(c, context, identity=identity)
    validate(admission, c, context, recovery, source)
    binding = c.execute(
        "SELECT * FROM authorization_admin.conversation_planning_recovery_bindings "
        "WHERE recovery_id=%s",
        (identity,),
    ).fetchone()
    if (
        not binding
        or binding["context_id"] != row["context_id"]
        or binding["invocation_id"] != row["first_invocation_id"]
        or binding["digest"] != digest(binding["record"])
        or binding["record"]["target"] != row["record"]["target"]
        or binding["record"]["request_digest"] != recovery["digest"]
    ):
        raise AuthorityError("PLANNING_RECOVERY_BINDING_INVALID")


def before_approve(admission, c, row, payload):
    identity = row["record"].get("recovery_id")
    if not identity:
        return False
    recovery = c.execute(
        "SELECT * FROM authorization_admin.conversation_planning_recoveries WHERE "
        "recovery_id=%s",
        (identity,),
    ).fetchone()
    binding = c.execute(
        "SELECT * FROM authorization_admin.conversation_planning_recovery_bindings "
        "WHERE recovery_id=%s",
        (identity,),
    ).fetchone()
    if (
        not recovery
        or not binding
        or binding["context_id"] != row["context_id"]
        or recovery["subject_id"] != row["subject_id"]
        or (recovery["tenant_id"], recovery["security_domain"])
        != (row["tenant_id"], row["security_domain"])
        or binding["invocation_id"] != row["first_invocation_id"]
        or binding["record"]["target"] != row["record"]["target"]
        or binding["record"]["request_digest"] != recovery["digest"]
        or digest(recovery["record"]) != recovery["digest"]
        or digest(binding["record"]) != binding["digest"]
    ):
        raise AuthorityError("PLANNING_RECOVERY_BINDING_INVALID")
    source = request_row(c, recovery["record"]["source_context_id"])
    if (
        not source
        or source["subject_id"] != row["subject_id"]
        or source["record"].get("experience_policy_digest")
        != recovery["record"]["experience_policy_digest"]
        or admission.configuration != recovery["record"]["configuration"]
    ):
        raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
    active(c, source, source["record"]["configuration"])
    original_source = c.execute(
        "SELECT record FROM draft_assistance.invocation_versions WHERE "
        "namespace=%s AND security_domain=%s AND invocation_id=%s "
        "ORDER BY aggregate_version DESC LIMIT 1",
        (row["tenant_id"], row["security_domain"], source["first_invocation_id"]),
    ).fetchone()
    if not original_source or original_source["record"].get("state") != "SUCCEEDED":
        raise AuthorityError("PLANNING_RECOVERY_SCOPE_DENIED")
    source["understanding_input_source"] = original_source["record"].get("inputSource")
    validate(admission, c, row, recovery, source)
    from .provider_budget_allowance import require_context

    if recovery["record"].get("budget_allowance_id"):
        require_context(
            c,
            row["tenant_id"],
            row["security_domain"],
            admission.configuration["ledger_id"],
            recovery["record"]["budget_allowance_id"],
            recovery["record"]["authorization_digest"],
            admission.configuration,
        )
    if datetime.fromisoformat(payload["expires_at"]) > datetime.fromisoformat(
        recovery["record"]["expires_at"]
    ):
        raise AuthorityError("PLANNING_RECOVERY_EXPIRY_EXTENSION_DENIED")
    return True
