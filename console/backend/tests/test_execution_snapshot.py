from dataclasses import replace

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
    EvidenceEventType,
    ExecutionEvidenceRecord,
    OutcomeClassification,
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
        "task_identity": "task",
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
        "evidence_references": ("evidence-ref",),
        "citation_references": ("citation-ref",),
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
    return assemble_execution_snapshot(
        scope=AuthorizedEvidenceScope("agent-workloads", "domain-a"),
        workflow=WORKFLOW,
        tasks=TASKS,
        evidence=records or [evidence()],
        evidence_high_water_mark=1,
        graph=graph(),
        **kwargs,
    )


def test_snapshot_identity_is_deterministic_and_binds_all_authorities() -> None:
    first = assemble()
    second = assemble()
    assert first == second
    assert first.state is SnapshotState.COMPLETE
    assert first.shared_snapshot_id.startswith("execution-snapshot:v1:")
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


def test_input_order_does_not_change_snapshot_identity() -> None:
    second = replace(
        evidence(),
        evidence_record_id="evidence.native.pei-001.1.2",
        event_ordinal=2,
        storage_sequence=2,
    )
    forward = assemble([evidence(), second])
    reverse = assemble([second, evidence()])
    assert forward.shared_snapshot_id == reverse.shared_snapshot_id
    assert tuple(item.event_ordinal for item in reverse.evidence) == (1, 2)
