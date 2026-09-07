"""Map proven Attempt Knowledge retrieval Evidence into Resource Use facts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from agent_core.execution_contract import ScopeIdentity

from .resource_use_application import ResourceUseApplicationService
from .resource_use_domain import (
    MeasurementAvailability,
    ResourceKind,
    ResourceMeasurement,
    ResourceUseBinding,
    ResourceUseFact,
    ResourceUseFactKind,
    canonical_digest,
    canonical_record,
    stable_id,
)


def validate_knowledge_lineage(
    binding: ResourceUseBinding,
    scope: ScopeIdentity,
    knowledge_binding: dict[str, object],
) -> None:
    expected = {
        "scope": scope,
        "attempt_id": knowledge_binding["attemptId"],
        "resource_kind": ResourceKind.KNOWLEDGE,
        "resource_id": knowledge_binding["knowledgeId"],
        "resource_revision_id": knowledge_binding["revisionId"],
        "resource_digest": knowledge_binding["revisionDigest"],
        "binding_id": knowledge_binding["bindingId"],
        "binding_digest": knowledge_binding["digest"],
        "digital_employee_instance_id": knowledge_binding["digitalEmployeeInstanceId"],
        "agent_instance_id": knowledge_binding["agentInstanceId"],
        "authorization_decision_id": knowledge_binding["authorizationDecisionId"],
    }
    if any(getattr(binding, key) != value for key, value in expected.items()):
        raise ValueError("KNOWLEDGE_RESOURCE_USE_LINEAGE_MISMATCH")


def prepare_knowledge_retrieval(
    service: ResourceUseApplicationService,
    binding: ResourceUseBinding,
    knowledge_binding: dict[str, object],
    *,
    observed_at: datetime,
    idempotency_key: str,
    transaction_hook: Callable[[Any], None],
) -> tuple[object, bool]:
    """Durably prepare a Knowledge dispatch before the external call."""
    validate_knowledge_lineage(binding, binding.scope, knowledge_binding)
    fact = ResourceUseFact(
        stable_id("resource-use-dispatch", binding.resource_use_id, binding.binding_id),
        binding.resource_use_id,
        ResourceUseFactKind.DISPATCH_RECORDED,
        "KNOWLEDGE_ATTEMPT",
        binding.binding_id,
        binding.binding_digest,
        observed_at,
        observed_at,
    )
    semantic = {
        "binding": canonical_record(binding),
        "facts": [canonical_record(fact)],
    }
    created = False

    def mark_and_append(connection: Any) -> None:
        nonlocal created
        transaction_hook(connection)
        created = True

    snapshot = service.prepare_dispatch(
        binding,
        (fact,),
        idempotency_key=idempotency_key,
        payload_digest=canonical_digest(semantic),
        transaction_hook=mark_and_append,
    )
    return snapshot, created


def commit_knowledge_retrieval(
    service: ResourceUseApplicationService,
    scope: ScopeIdentity,
    resource_use_id: str,
    result: dict[str, object],
    *,
    observed_at: datetime,
    expected_high_water: int,
    idempotency_key: str,
    transaction_hook: Callable[[Any], None] | None = None,
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
        "NO_RESULT": ResourceUseFactKind.NO_RESULT,
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
        transaction_hook=transaction_hook,
    )
