"""Deterministic shared execution snapshot assembler."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_core.execution_evidence import (
    AuthorizationDecision,
    AuthorizedEvidenceScope,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    ReferenceType,
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
    terminal_evidence: ExecutionEvidenceRecord
    graph: CanonicalGraph
    limitation_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        latest = self.terminal_evidence
        graph = graph_to_dict(self.graph)
        allowed_references_by_identity = {
            (reference.reference_type.value, reference.reference_identity): {
                "referenceIdentity": reference.reference_identity,
                "referenceType": reference.reference_type.value,
                "namespace": reference.namespace,
                "securityDomain": reference.security_domain,
                "authorizationDecision": reference.authorization_decision.value,
                "reasonCode": reference.reason_code,
                "visibility": reference.visibility.value,
                "sourceIdentity": reference.source_identity,
                "provenance": reference.provenance,
            }
            for item in self.evidence
            for reference in item.references
            if reference.authorization_decision is AuthorizationDecision.ALLOW
        }
        allowed_references = [
            allowed_references_by_identity[key]
            for key in sorted(allowed_references_by_identity)
        ]
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
                }
                for item in self.evidence
            ],
            "evidenceReferences": [
                item
                for item in allowed_references
                if item["referenceType"] == ReferenceType.EVIDENCE.value
            ],
            "citations": [
                item
                for item in allowed_references
                if item["referenceType"] == ReferenceType.CITATION.value
            ],
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
    selected_task_identity: str,
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
        or item.workflow_identity != workflow_identity.uid
        or item.task_identity != selected_task_identity
        for item in evidence
    ):
        raise SnapshotAssemblyError("EVIDENCE_SUBJECT_MISMATCH")
    if selected_task_identity not in {item.uid for item in task_identities}:
        raise SnapshotAssemblyError("TASK_IDENTITY_MISMATCH")
    if any(
        reference.namespace != scope.namespace
        or reference.security_domain != scope.security_domain
        for item in evidence
        for reference in item.references
    ):
        raise SnapshotAssemblyError("REFERENCE_SCOPE_MISMATCH")
    reference_decisions: dict[tuple[object, str], object] = {}
    for item in evidence:
        for reference in item.references:
            key = (reference.reference_type, reference.reference_identity)
            existing = reference_decisions.setdefault(key, reference.canonical_payload)
            if existing != reference.canonical_payload:
                raise SnapshotAssemblyError("REFERENCE_AUTHORIZATION_CONFLICT")
    if any(
        item.storage_sequence is not None
        and item.storage_sequence > evidence_high_water_mark
        for item in evidence
    ):
        raise SnapshotAssemblyError("EVIDENCE_HIGH_WATER_CONFLICT")
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
    partial = False
    terminals: list[ExecutionEvidenceRecord] = []
    for attempt in sorted({item.attempt_ordinal for item in ordered}):
        attempt_records = [item for item in ordered if item.attempt_ordinal == attempt]
        ordinals = [item.event_ordinal for item in attempt_records]
        if ordinals != list(range(1, len(ordinals) + 1)):
            partial = True
        attempt_terminals = [
            item
            for item in attempt_records
            if item.event_type is EvidenceEventType.EXECUTION_OUTCOME
        ]
        if len(attempt_terminals) > 1:
            raise SnapshotAssemblyError("CONTRADICTORY_TERMINAL_EVIDENCE")
        if not attempt_terminals:
            partial = True
            continue
        terminal = attempt_terminals[0]
        if terminal.event_ordinal != max(ordinals):
            raise SnapshotAssemblyError("EVENT_AFTER_TERMINAL_EVIDENCE")
        if (
            terminal.authorization_decision is AuthorizationDecision.ALLOW
            and terminal.capability_identity is not None
            and terminal.provider_call_count < 1
        ):
            partial = True
        terminals.append(terminal)
    if not terminals:
        partial = True
        terminal = ordered[-1]
    else:
        terminal = max(terminals, key=lambda item: item.attempt_ordinal)
    state = (
        SnapshotState.STALE
        if stale
        else SnapshotState.PARTIAL
        if partial
        else SnapshotState.COMPLETE
    )
    limitations = tuple(
        sorted({item.limitation_code for item in ordered if item.limitation_code})
    )
    identity_input = {
        "assemblerVersion": "execution-snapshot-v2",
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
        assembler_version="execution-snapshot-v2",
        state=state,
        namespace=scope.namespace,
        security_domain=scope.security_domain,
        platform_execution_identity=next(iter(executions)),
        shared_snapshot_id=f"execution-snapshot:v2:{digest}",
        graph_snapshot_id=graph.graph_snapshot_id,
        evidence_high_water_mark=evidence_high_water_mark,
        workflow=workflow_identity,
        tasks=task_identities,
        evidence=ordered,
        terminal_evidence=terminal,
        graph=graph,
        limitation_codes=limitations,
    )
