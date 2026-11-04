"""Approved D9 local-evidence preconditions; never supplier adjudication or replay."""

from .authority_contracts import AuthorityError
from .task_delegation import digest


def require_recovery_evidence(c, spec, scope):
    unresolved = c.execute(
        "SELECT i.invocation_id,i.actor_id,i.record FROM "
        "workflow_planning.invocations i LEFT JOIN "
        "workflow_planning.invocation_results r "
        "USING(namespace,security_domain,invocation_id) "
        "WHERE i.namespace=%s AND i.security_domain=%s "
        "AND i.record->'target'->'problem'->'problem'->>'resource_id'=%s "
        "AND (r.record IS NULL OR r.record->>'technical_status'='OUTCOME_UNKNOWN')",
        (*scope, spec.root.resource_id),
    ).fetchall()
    ids = spec.initial_case_revision.recovery_observation_ids
    if not unresolved and not ids:
        return
    if not ids or len(ids) != len(set(ids)) or len(ids) != len(unresolved):
        raise AuthorityError("INITIAL_CASE_RECOVERY_REQUIRED")
    remaining = {item["invocation_id"]: item for item in unresolved}
    for identity in ids:
        observation = c.execute(
            "SELECT * FROM authorization_admin.planning_recovery_observations "
            "WHERE observation_id=%s AND tenant_id=%s AND security_domain=%s "
            "AND root_id=%s",
            (identity, *scope, spec.root.resource_id),
        ).fetchone()
        if not observation or digest(observation["record"]) != observation["digest"]:
            raise AuthorityError("INITIAL_CASE_RECOVERY_EVIDENCE_INVALID")
        invocation = remaining.pop(observation["invocation_id"], None)
        record = observation["record"]
        if (
            invocation is None
            or observation["subject_id"] != invocation["actor_id"]
            or invocation["record"]["target"]["problem"]["problem"]
            != spec.root.model_dump(mode="json")
            or record["root"] != spec.root.model_dump(mode="json")
            or record.get("provenance") != "LOCAL_ONLY"
            or record.get("local_cleanup_confirmed") is not True
        ):
            raise AuthorityError("INITIAL_CASE_RECOVERY_EVIDENCE_INVALID")
        receipt = c.execute(
            "SELECT record FROM workflow_planning.provider_receipts WHERE "
            "namespace=%s AND security_domain=%s AND invocation_id=%s",
            (*scope, invocation["invocation_id"]),
        ).fetchone()
        lineage = c.execute(
            "SELECT r.reservation_id FROM "
            "authorization_admin.initial_case_planning_calls d "
            "JOIN authorization_admin.context_call_requests q USING(context_id) "
            "JOIN draft_provider_budget.reservations r ON "
            "r.namespace=d.tenant_id AND r.security_domain=d.security_domain "
            "AND r.ledger_id=d.ledger_id AND r.invocation_id=q.first_invocation_id "
            "WHERE d.tenant_id=%s AND d.security_domain=%s AND d.root_id=%s "
            "AND d.subject_id=%s AND d.ledger_id=%s AND q.first_invocation_id=%s",
            (
                *scope,
                spec.root.resource_id,
                observation["subject_id"],
                spec.configuration.ledger_id,
                invocation["invocation_id"],
            ),
        ).fetchone()
        if (
            not receipt
            or not lineage
            or receipt["record"].get("deadline", {}).get("reaped") is not True
            or receipt["record"].get("measurement") != {}
            or receipt["record"].get("invocation_id") != invocation["invocation_id"]
            or receipt["record"].get("reservation_id") != lineage["reservation_id"]
            or receipt["record"].get("target_digest")
            != digest(invocation["record"]["target"])
            or record["evidence_digest"] != digest(receipt["record"])
        ):
            raise AuthorityError("INITIAL_CASE_RECOVERY_EVIDENCE_INVALID")
    if remaining:
        raise AuthorityError("INITIAL_CASE_RECOVERY_REQUIRED")
