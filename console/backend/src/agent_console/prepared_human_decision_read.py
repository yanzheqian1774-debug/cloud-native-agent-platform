"""Exact, current-authority projection of an existing immutable Human decision."""

from .authority_contracts import AuthorityError
from .resource_use_domain import canonical_digest


def read_human_decision(connection, principal, authority, preparation, outcome):
    unavailable = {"status": "UNAVAILABLE"}
    try:
        authority.require(
            principal,
            "HUMAN_CONFIRMATION",
            "READ",
            "human-confirmation:prepared:" + preparation.digest,
        )
    except AuthorityError:
        return unavailable
    if not outcome or outcome.get("runId") != preparation.run_id:
        return unavailable
    confirmation_id = outcome.get("confirmationId")
    if not confirmation_id:
        return {"status": "NOT_RECORDED"}
    row = connection.execute(
        "SELECT h.*,e.record evaluated,e.digest evaluation_digest,"
        "e.workflow_run_id evaluated_run,e.snapshot_id evaluated_snapshot,"
        "e.predecessor_id evaluated_predecessor,"
        "s.record snapshot,s.digest snapshot_digest,"
        "s.workflow_run_id snapshot_run,o.record outcome,o.digest outcome_digest,"
        "o.predecessor_id outcome_predecessor,o.resolution outcome_resolution,"
        "n.record successor,n.digest successor_digest, "
        "n.workflow_run_id successor_run,n.evaluation_id successor_id, "
        "n.snapshot_id successor_snapshot,n.predecessor_id successor_predecessor "
        "FROM human_governance.confirmations h "
        "JOIN success_criteria_evaluation.results e ON "
        "(e.namespace,e.security_domain,e.evaluation_id)="
        "(h.namespace,h.security_domain,h.evaluation_id) "
        "JOIN success_criteria_evaluation.snapshots s ON "
        "(s.namespace,s.security_domain,s.snapshot_id)="
        "(h.namespace,h.security_domain,h.snapshot_id) "
        "JOIN product_outcome.outcomes o ON "
        "(o.namespace,o.security_domain,o.confirmation_id)="
        "(h.namespace,h.security_domain,h.confirmation_id) "
        "JOIN success_criteria_evaluation.results n ON "
        "(n.namespace,n.security_domain,n.evaluation_id)="
        "(o.namespace,o.security_domain,o.evaluation_id) "
        "WHERE h.namespace=%s AND h.security_domain=%s AND h.confirmation_id=%s "
        "AND o.outcome_id=%s AND o.workflow_run_id=%s",
        (
            preparation.namespace,
            preparation.security_domain,
            confirmation_id,
            outcome["outcomeId"],
            preparation.run_id,
        ),
    ).fetchone()
    if not row:
        return unavailable
    value, evaluated, snapshot, successor = (
        row["record"],
        row["evaluated"],
        row["snapshot"],
        row["successor"],
    )
    expected = {
        "confirmationId": row["confirmation_id"],
        "evaluationId": row["evaluation_id"],
        "evaluationDigest": row["evaluation_digest"],
        "reviewedSnapshotId": row["snapshot_id"],
        "reviewedSnapshotDigest": row["snapshot_digest"],
        "actorId": row["actor_id"],
        "authorityBasis": row["authority_basis"],
        "decision": row["decision"],
        "reason": row["reason"],
    }
    if not (
        row["namespace"] == preparation.namespace
        and row["security_domain"] == preparation.security_domain
        and value == expected
        and canonical_digest(value) == row["digest"]
        and row["actor_id"].startswith("human:")
        and row["authority_basis"]
        and row["decision"] in {"ACKNOWLEDGE_UNDETERMINED", "DISAGREE"}
        and row["outcome_predecessor"] == outcome.get("predecessorId")
        and row["outcome_resolution"] == outcome.get("businessResolution")
        and row["outcome"] == outcome
        and canonical_digest(outcome) == row["outcome_digest"]
        and canonical_digest(evaluated) == row["evaluation_digest"]
        and canonical_digest(snapshot) == row["snapshot_digest"]
        and canonical_digest(successor) == row["successor_digest"]
        and snapshot.get("preparationDigest") == preparation.digest
        and snapshot.get("runId")
        == row["evaluated_run"]
        == row["snapshot_run"]
        == preparation.run_id
        and row["evaluated_predecessor"] == evaluated.get("predecessorId")
        and evaluated.get("evaluationId") == row["evaluation_id"]
        and row["evaluated_snapshot"] == row["snapshot_id"]
        and evaluated.get("snapshotId") == row["snapshot_id"]
        and evaluated.get("snapshotDigest") == row["snapshot_digest"]
        and row["successor_run"] == preparation.run_id
        and row["successor_id"] == successor.get("evaluationId")
        and row["successor_id"] == outcome.get("evaluation", {}).get("evaluationId")
        and row["successor_snapshot"] == row["snapshot_id"]
        and row["successor_predecessor"] == row["evaluation_id"]
        and successor.get("predecessorId") == row["evaluation_id"]
        and successor.get("humanConfirmationId") == confirmation_id
        and successor.get("snapshotId") == row["snapshot_id"]
        and successor.get("snapshotDigest") == row["snapshot_digest"]
        and outcome.get("evaluation") == successor
        and outcome.get("evaluationDigest") == row["successor_digest"]
    ):
        return unavailable
    return {
        "status": "READABLE",
        "decision": value,
        "digest": row["digest"],
        "createdAt": row["created_at"].isoformat(),
    }
