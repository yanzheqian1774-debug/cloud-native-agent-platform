from dataclasses import replace

import pytest
from agent_console.execution_snapshot import SnapshotState, assemble_execution_snapshot
from agent_console.graph_projection import (
    NodeSpec,
    NodeType,
    SnapshotContext,
    build_graph,
)
from agent_core.execution_evidence import (
    AuthorizationDecision,
    AuthorizedEvidenceScope,
    AuthorizedReference,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    OutcomeClassification,
    ReferenceType,
    ReferenceVisibility,
)


def reference(
    identity: str,
    reference_type: ReferenceType,
    decision: AuthorizationDecision = AuthorizationDecision.ALLOW,
) -> AuthorizedReference:
    return AuthorizedReference(
        identity,
        reference_type,
        "agent-workloads",
        "domain-a",
        decision,
        "REFERENCE_ALLOWED"
        if decision is AuthorizationDecision.ALLOW
        else "REFERENCE_DENIED",
        ReferenceVisibility.BOTH,
        "execution-evidence",
        "native-runtime",
    )


WORKFLOW = {
    "metadata": {"name": "workflow", "uid": "workflow-uid", "resourceVersion": "10"}
}
TASKS = [
    {
        "metadata": {"name": "task", "uid": "task-uid", "resourceVersion": "20"},
        "spec": {},
    }
]


def evidence(**overrides):
    values = {
        "evidence_record_id": "evidence.native.pei-001.1.1",
        "namespace": "agent-workloads",
        "security_domain": "domain-a",
        "platform_execution_identity": "pei-001",
        "workflow_identity": "workflow-uid",
        "task_identity": "task-uid",
        "attempt_ordinal": 1,
        "event_ordinal": 1,
        "event_type": EvidenceEventType.EXECUTION_OUTCOME,
        "occurred_at": "2026-08-27T08:00:00Z",
        "runtime_classification": "NATIVE",
        "selected_instance_identity": "instance-001",
        "capability_identity": "lookup",
        "authorization_decision": AuthorizationDecision.ALLOW,
        "reason_code": "TASK_RUNTIME_SUCCEEDED",
        "provider_correlation_id": "provider-001",
        "provider_call_count": 1,
        "outcome_classification": OutcomeClassification.SUCCEEDED,
        "references": (
            reference("evidence-ref", ReferenceType.EVIDENCE),
            reference("citation-ref", ReferenceType.CITATION),
            reference("denied-ref", ReferenceType.CITATION, AuthorizationDecision.DENY),
        ),
        "storage_sequence": 1,
        "recorded_at": "2026-08-27T08:00:01Z",
    }
    values.update(overrides)
    return ExecutionEvidenceRecord(**values)


def graph():
    return build_graph(
        SnapshotContext(
            "workflow-uid:10", "10", "high-water:1", security_domain="domain-a"
        ),
        [NodeSpec(NodeType.TASK, "task-uid", "graph.task")],
        [],
    )


def assemble(records=None, **kwargs):
    selected_records = records or [evidence()]
    return assemble_execution_snapshot(
        scope=AuthorizedEvidenceScope("agent-workloads", "domain-a"),
        workflow=WORKFLOW,
        tasks=TASKS,
        evidence=selected_records,
        evidence_high_water_mark=max(
            item.storage_sequence or 0 for item in selected_records
        ),
        graph=graph(),
        selected_task_identity="task-uid",
        **kwargs,
    )


def test_snapshot_identity_is_deterministic_and_binds_all_authorities() -> None:
    first = assemble()
    second = assemble()
    assert first == second
    assert first.state is SnapshotState.COMPLETE
    assert first.shared_snapshot_id.startswith("execution-snapshot:v2:")
    assert first.graph_snapshot_id == first.graph.graph_snapshot_id


def test_product_and_technical_are_siblings_with_identical_authority() -> None:
    payload = assemble().to_dict()
    product = payload["product"]
    technical = payload["technical"]
    for key in (
        "platformExecutionIdentity",
        "sharedSnapshotId",
        "graphSnapshotId",
        "authorization",
        "runtime",
        "outcome",
        "evidence",
        "citations",
        "graph",
    ):
        assert product[key] == technical[key] == payload[key]


def test_gap_is_partial_and_stale_is_never_complete() -> None:
    gap = replace(
        evidence(),
        evidence_record_id="evidence.native.pei-001.1.2",
        event_ordinal=2,
    )
    assert assemble([gap]).state is SnapshotState.PARTIAL
    assert assemble(stale=True).state is SnapshotState.STALE


def test_contiguous_nonterminal_evidence_is_partial() -> None:
    nonterminal = replace(evidence(), event_type=EvidenceEventType.RUNTIME_OUTCOME)
    assert assemble([nonterminal]).state is SnapshotState.PARTIAL


def test_allow_without_required_provider_call_evidence_is_partial() -> None:
    missing_call = replace(evidence(), provider_call_count=0)
    assert assemble([missing_call]).state is SnapshotState.PARTIAL


def test_explicit_deny_with_zero_call_proof_can_be_complete() -> None:
    denied = replace(
        evidence(),
        authorization_decision=AuthorizationDecision.DENY,
        provider_call_count=0,
        outcome_classification=OutcomeClassification.DENIED,
        references=(
            reference(
                "denied-ref",
                ReferenceType.CITATION,
                AuthorizationDecision.DENY,
            ),
        ),
    )
    assert assemble([denied]).state is SnapshotState.COMPLETE


def test_contradictory_terminal_evidence_fails_closed() -> None:
    second = replace(
        evidence(),
        evidence_record_id="evidence.native.pei-001.1.2",
        event_ordinal=2,
        storage_sequence=2,
    )
    with pytest.raises(ValueError, match="CONTRADICTORY_TERMINAL_EVIDENCE"):
        assemble([evidence(), second])


def test_contradictory_execution_identity_fails_closed() -> None:
    foreign = replace(
        evidence(),
        evidence_record_id="evidence.native.pei-foreign.1.1",
        platform_execution_identity="pei-foreign",
    )
    with pytest.raises(ValueError, match="EXECUTION_IDENTITY_CONFLICT"):
        assemble([evidence(), foreign])


def test_reference_scope_conflict_fails_closed() -> None:
    wrong_scope = AuthorizedReference(
        "citation-foreign",
        ReferenceType.CITATION,
        "agent-workloads",
        "domain-foreign",
        AuthorizationDecision.ALLOW,
        "REFERENCE_ALLOWED",
        ReferenceVisibility.BOTH,
        "execution-evidence",
        "native-runtime",
    )
    with pytest.raises(ValueError, match="REFERENCE_SCOPE_MISMATCH"):
        assemble([replace(evidence(), references=(wrong_scope,))])


def test_denied_reference_is_omitted_without_count_or_identity() -> None:
    payload = assemble().to_dict()
    assert [item["referenceIdentity"] for item in payload["citations"]] == [
        "citation-ref"
    ]
    assert "denied-ref" not in str(payload)


def test_input_order_does_not_change_snapshot_identity() -> None:
    first = replace(evidence(), event_type=EvidenceEventType.RUNTIME_OUTCOME)
    second = replace(
        evidence(),
        evidence_record_id="evidence.native.pei-001.1.2",
        event_ordinal=2,
        storage_sequence=2,
    )
    forward = assemble([first, second])
    reverse = assemble([second, first])
    assert forward.shared_snapshot_id == reverse.shared_snapshot_id
    assert tuple(item.event_ordinal for item in reverse.evidence) == (1, 2)
