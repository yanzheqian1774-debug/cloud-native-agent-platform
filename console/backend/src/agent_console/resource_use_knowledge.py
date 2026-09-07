"""Map proven Attempt Knowledge retrieval Evidence into Resource Use facts."""

from __future__ import annotations

from datetime import datetime

from agent_core.execution_contract import ScopeIdentity

from .resource_use_application import ResourceUseApplicationService
from .resource_use_domain import (
    MeasurementAvailability,
    ResourceMeasurement,
    ResourceUseFact,
    ResourceUseFactKind,
    canonical_digest,
    canonical_record,
    stable_id,
)


def commit_knowledge_retrieval(
    service: ResourceUseApplicationService,
    scope: ScopeIdentity,
    resource_use_id: str,
    result: dict[str, object],
    *,
    observed_at: datetime,
    expected_high_water: int,
    idempotency_key: str,
) -> object:
    """Commit only Evidence returned by the governed retrieval path.

    This does not call Qdrant and is therefore replay-safe: the caller executes
    retrieval once, then retries this deterministic PostgreSQL commit as needed.
    """
    evidence = result["evidence"]
    if not isinstance(evidence, dict):
        raise ValueError("KNOWLEDGE_EVIDENCE_REQUIRED")
    state = evidence["retrievalState"]
    kind = {
        "RETRIEVED": ResourceUseFactKind.SUCCEEDED,
        "NO_RESULT": ResourceUseFactKind.NOT_EXECUTED,
        "STALE": ResourceUseFactKind.STALE,
        "UNAVAILABLE": ResourceUseFactKind.OUTCOME_UNKNOWN,
    }[str(state)]
    if observed_at.tzinfo is None:
        raise ValueError("KNOWLEDGE_OBSERVED_AT_REQUIRED")
    observed = observed_at
    evidence_id = str(evidence["evidenceId"])
    evidence_digest = str(evidence["evidenceDigest"])
    fact = ResourceUseFact(
        stable_id("resource-use-fact", resource_use_id, evidence_id),
        resource_use_id,
        kind,
        "KNOWLEDGE_ATTEMPT",
        evidence_id,
        evidence_digest,
        observed,
        observed,
        (evidence_id,),
        () if state == "RETRIEVED" else (str(evidence.get("reason")),),
    )
    citations = evidence.get("citations", [])
    measured = state == "RETRIEVED"
    measurement = ResourceMeasurement(
        stable_id("resource-measurement", resource_use_id, evidence_id),
        resource_use_id,
        "citation_count",
        len(citations) if measured else None,
        "count",
        (
            MeasurementAvailability.MEASURED
            if measured
            else MeasurementAvailability.NOT_COLLECTED
        ),
        evidence_id,
        evidence_digest,
        observed,
        observed,
        observed,
        "AUTHORITATIVE",
        "EXACT",
        (),
        "EXACT",
        measured,
        "NONE",
        (evidence_id,),
    )
    evidence_reference = {
        "evidenceId": evidence_id,
        "evidenceDigest": evidence_digest,
        "evidenceKind": "KNOWLEDGE_RETRIEVAL",
    }
    claim = {
        "claimId": stable_id("resource-use-claim", resource_use_id, evidence_id),
        "resourceUseId": resource_use_id,
        "state": kind.value,
        "evidenceId": evidence_id,
    }
    claim["claimDigest"] = canonical_digest(claim)
    semantic = {
        "resourceUseId": resource_use_id,
        "facts": [canonical_record(fact)],
        "measurements": [canonical_record(measurement)],
        "evidence": (evidence_reference,),
        "claim": claim,
        "expectedHighWater": expected_high_water,
    }
    return service.commit_observation(
        scope,
        resource_use_id,
        (fact,),
        (measurement,),
        evidence_records=(evidence_reference,),
        claim=claim,
        idempotency_key=idempotency_key,
        payload_digest=canonical_digest(semantic),
        expected_high_water=expected_high_water,
    )
