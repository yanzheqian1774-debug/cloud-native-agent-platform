"""Deterministic shared execution snapshot assembler."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_core.execution_evidence import (
    AuthorizedEvidenceScope,
    ExecutionEvidenceRecord,
    canonical_json,
)

from agent_console.graph_projection import CanonicalGraph, graph_to_dict
from agent_console.shared_views import sibling_snapshot_views


class SnapshotAssemblyError(ValueError):
    """Bounded invalid-authority or mixed-snapshot failure."""


class SnapshotState(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    AUTHORITY_MISSING = "AUTHORITY_MISSING"
    DENIED = "DENIED"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class KubernetesIdentityVersion:
    uid: str
    resource_version: str
    name: str


@dataclass(frozen=True, slots=True)
class SharedExecutionSnapshot:
    schema_version: int
    assembler_version: str
    state: SnapshotState
    namespace: str
    security_domain: str
    platform_execution_identity: str
    shared_snapshot_id: str
    graph_snapshot_id: str
    evidence_high_water_mark: int
    workflow: KubernetesIdentityVersion
    tasks: tuple[KubernetesIdentityVersion, ...]
    evidence: tuple[ExecutionEvidenceRecord, ...]
    graph: CanonicalGraph
    limitation_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        latest = self.evidence[-1]
        graph = graph_to_dict(self.graph)
        base = {
            "schemaVersion": self.schema_version,
            "assemblerVersion": self.assembler_version,
            "state": self.state.value,
            "namespace": self.namespace,
            "securityDomain": self.security_domain,
            "platformExecutionIdentity": self.platform_execution_identity,
            "sharedSnapshotId": self.shared_snapshot_id,
            "graphSnapshotId": self.graph_snapshot_id,
            "evidenceHighWaterMark": self.evidence_high_water_mark,
            "sourceVersions": {
                "workflow": {
                    "uid": self.workflow.uid,
                    "resourceVersion": self.workflow.resource_version,
                    "name": self.workflow.name,
                },
                "tasks": [
                    {
                        "uid": item.uid,
                        "resourceVersion": item.resource_version,
                        "name": item.name,
                    }
                    for item in self.tasks
                ],
            },
            "authorization": {
                "decision": latest.authorization_decision.value,
                "reasonCode": latest.reason_code,
                "providerCallCount": latest.provider_call_count,
            },
            "runtime": {
                "classification": latest.runtime_classification,
                "providerCorrelationId": latest.provider_correlation_id,
            },
            "outcome": {
                "classification": latest.outcome_classification.value,
                "reference": latest.outcome_reference,
            },
            "evidence": [
                {
                    "recordId": item.evidence_record_id,
                    "digest": item.payload_digest,
                    "attemptOrdinal": item.attempt_ordinal,
                    "eventOrdinal": item.event_ordinal,
                    "eventType": item.event_type.value,
                    "occurredAt": item.occurred_at,
                    "reasonCode": item.reason_code,
                    "evidenceReferences": list(item.evidence_references),
                }
                for item in self.evidence
            ],
            "citations": list(latest.citation_references),
            "graph": graph,
            "limitationCodes": list(self.limitation_codes),
        }
        product, technical = sibling_snapshot_views(base)
        base["product"] = product
        base["technical"] = technical
        return base


def _identity_version(resource: Mapping[str, Any]) -> KubernetesIdentityVersion:
    metadata = resource.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SnapshotAssemblyError("KUBERNETES_IDENTITY_MISSING")
    values = (
        metadata.get("uid"),
        metadata.get("resourceVersion"),
        metadata.get("name"),
    )
    if not all(isinstance(item, str) and item.strip() for item in values):
        raise SnapshotAssemblyError("KUBERNETES_IDENTITY_MISSING")
    return KubernetesIdentityVersion(*values)  # type: ignore[arg-type]


def assemble_execution_snapshot(
    *,
    scope: AuthorizedEvidenceScope,
    workflow: Mapping[str, Any],
    tasks: Sequence[Mapping[str, Any]],
    evidence: Sequence[ExecutionEvidenceRecord],
    evidence_high_water_mark: int,
    graph: CanonicalGraph,
    stale: bool = False,
) -> SharedExecutionSnapshot:
    """Assemble one fixed-high-water snapshot from already-authorized inputs."""
    if not evidence:
        raise SnapshotAssemblyError("EXECUTION_EVIDENCE_MISSING")
    workflow_identity = _identity_version(workflow)
    task_identities = tuple(
        sorted(
            (_identity_version(item) for item in tasks),
            key=lambda item: (item.uid, item.name),
        )
    )
    if not task_identities:
        raise SnapshotAssemblyError("TASK_AUTHORITY_MISSING")
    if any(
        item.namespace != scope.namespace
        or item.security_domain != scope.security_domain
        for item in evidence
    ):
        raise SnapshotAssemblyError("SECURITY_SCOPE_MISMATCH")
    executions = {item.platform_execution_identity for item in evidence}
    if len(executions) != 1:
        raise SnapshotAssemblyError("EXECUTION_IDENTITY_CONFLICT")
    ordered = tuple(
        sorted(
            evidence,
            key=lambda item: (
                item.attempt_ordinal,
                item.event_ordinal,
                item.occurred_at,
                item.recorded_at or "",
                item.evidence_record_id,
            ),
        )
    )
    gaps = False
    for attempt in sorted({item.attempt_ordinal for item in ordered}):
        ordinals = [
            item.event_ordinal for item in ordered if item.attempt_ordinal == attempt
        ]
        if ordinals != list(range(1, len(ordinals) + 1)):
            gaps = True
    state = (
        SnapshotState.STALE
        if stale
        else SnapshotState.PARTIAL
        if gaps
        else SnapshotState.COMPLETE
    )
    limitations = tuple(
        sorted({item.limitation_code for item in ordered if item.limitation_code})
    )
    identity_input = {
        "assemblerVersion": "execution-snapshot-v1",
        "namespace": scope.namespace,
        "securityDomain": scope.security_domain,
        "workflow": [workflow_identity.uid, workflow_identity.resource_version],
        "tasks": [[item.uid, item.resource_version] for item in task_identities],
        "platformExecutionIdentity": next(iter(executions)),
        "evidenceHighWaterMark": evidence_high_water_mark,
        "evidence": [
            [item.evidence_record_id, item.payload_digest] for item in ordered
        ],
        "graphSnapshotId": graph.graph_snapshot_id,
    }
    digest = hashlib.sha256(canonical_json(identity_input).encode()).hexdigest()
    return SharedExecutionSnapshot(
        schema_version=1,
        assembler_version="execution-snapshot-v1",
        state=state,
        namespace=scope.namespace,
        security_domain=scope.security_domain,
        platform_execution_identity=next(iter(executions)),
        shared_snapshot_id=f"execution-snapshot:v1:{digest}",
        graph_snapshot_id=graph.graph_snapshot_id,
        evidence_high_water_mark=evidence_high_water_mark,
        workflow=workflow_identity,
        tasks=task_identities,
        evidence=ordered,
        graph=graph,
        limitation_codes=limitations,
    )
