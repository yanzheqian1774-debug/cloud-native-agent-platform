"""Focused contract and isolation tests for execution accounting."""

from __future__ import annotations

from dataclasses import replace

import pytest
from agent_console.execution_accounting import (
    AccountingError,
    Availability,
    ScopedOutcomeComparison,
    build_execution_accounting,
)
from agent_console.execution_snapshot import (
    AuthorizationDecision,
    AuthorizedEvidenceScope,
    EvidenceEventType,
    ExecutionEvidenceRecord,
    SnapshotState,
    assemble_execution_snapshot,
)
from agent_console.graph_projection import (
    NodeSpec,
    NodeType,
    SnapshotContext,
    build_graph,
)
from agent_console.intervention_feedback_schemas import (
    InterventionEventRecord,
    OutcomeFeedbackRecord,
)
from agent_console.live_journey_schemas import JourneyOutcome


def evidence(execution: str = "execution-1", **overrides: object):
    values: dict[str, object] = {
        "evidence_record_id": f"evidence.{execution}.1.1",
        "namespace": "namespace-a",
        "security_domain": "domain-a",
        "platform_execution_identity": execution,
        "workflow_identity": "workflow-uid",
        "task_identity": "task-uid",
        "attempt_ordinal": 1,
        "event_ordinal": 1,
        "event_type": EvidenceEventType.EXECUTION_OUTCOME,
        "occurred_at": "2026-08-30T01:00:00Z",
        "runtime_classification": "NATIVE",
        "selected_instance_identity": "instance-1",
        "capability_identity": "lookup",
        "authorization_decision": AuthorizationDecision.ALLOW,
        "reason_code": "EXECUTION_COMPLETE",
        "provider_correlation_id": "provider-1",
        "provider_call_count": 2,
        "outcome_classification": "SUCCEEDED",
        "outcome_reference": f"outcome:{execution}",
        "references": (),
        "limitation_code": None,
        "supersedes_record_id": None,
        "schema_version": 1,
        "storage_sequence": 1,
        "recorded_at": "2026-08-30T01:00:01Z",
    }
    values.update(overrides)
    producer = {
        key: value
        for key, value in values.items()
        if key not in {"storage_sequence", "recorded_at"}
    }
    record = ExecutionEvidenceRecord.from_allowlisted(producer)
    return record.with_repository_metadata(
        storage_sequence=values["storage_sequence"],  # type: ignore[arg-type]
        recorded_at=values["recorded_at"],  # type: ignore[arg-type]
    )


def snapshot(execution: str = "execution-1", records=None, **overrides: object):
    selected = records or [evidence(execution)]
    graph = build_graph(
        SnapshotContext(
            f"workflow-uid:{execution}", "1", f"high-water:{execution}", "domain-a"
        ),
        [NodeSpec(NodeType.TASK, "task-uid", "graph.task")],
        [],
    )
    result = assemble_execution_snapshot(
        scope=AuthorizedEvidenceScope("namespace-a", "domain-a"),
        workflow={
            "metadata": {
                "name": "workflow",
                "uid": "workflow-uid",
                "resourceVersion": execution,
            }
        },
        tasks=[
            {
                "metadata": {
                    "name": "task",
                    "uid": "task-uid",
                    "resourceVersion": execution,
                }
            }
        ],
        evidence=selected,
        evidence_high_water_mark=max(item.storage_sequence or 0 for item in selected),
        graph=graph,
        selected_task_identity="task-uid",
        stale=bool(overrides.pop("stale", False)),
    )
    return replace(result, **overrides)


def accounting(snapshots=None, **overrides: object):
    return build_execution_accounting(
        namespace="namespace-a",
        security_domain="domain-a",
        snapshots=tuple((snapshot(),) if snapshots is None else snapshots),
        **overrides,  # type: ignore[arg-type]
    )


def outcome(identity: str, value: float | None, metric: str = "quality"):
    return JourneyOutcome(
        outcomeId=identity,
        classification="SUCCEEDED",
        summary="bounded outcome",
        comparableMetric=metric,
        comparableValue=value,
    )


def comparison(before: float | None, after: float | None, **overrides: object):
    values: dict[str, object] = {
        "namespace": "namespace-a",
        "security_domain": "domain-a",
        "predecessor_execution_identity": "execution-1",
        "successor_execution_identity": "execution-2",
        "predecessor": outcome("outcome-1", before),
        "successor": outcome("outcome-2", after),
    }
    values.update(overrides)
    return ScopedOutcomeComparison(**values)  # type: ignore[arg-type]


def intervention(**overrides: object):
    values: dict[str, object] = {
        "recordId": "intervention-record-1",
        "interventionEventId": "intervention-event-1",
        "recordDigest": "a" * 64,
        "lifecycle": "RECORDED",
        "supersedesRecordId": None,
        "journeyId": "journey-1",
        "predecessorRevisionId": "revision-1",
        "predecessorRevisionDigest": "b" * 64,
        "successorRevisionId": "revision-2",
        "successorRevisionDigest": "c" * 64,
        "affectedElementReference": "CONSTRAINT",
        "correctionPatchReference": "CONSTRAINT_PATCH",
        "eventKind": "CONSTRAINT_CHANGED",
        "reasonCode": "MISSING_CONSTRAINT",
        "principalId": "human-1",
        "decisionTime": "2026-08-30T02:00:00Z",
        "tenantId": "namespace-a",
        "securityDomain": "domain-a",
        "platformExecutionIdentity": "execution-1",
        "outcomeId": "outcome-1",
        "executionEvidenceIds": ("evidence.execution-1.1.1",),
        "provenance": "LIVE_EXECUTION",
        "optimizationUseConsentDecision": "DENIED",
    }
    values.update(overrides)
    return InterventionEventRecord.model_validate(values)


def feedback(**overrides: object):
    values: dict[str, object] = {
        "feedbackId": "feedback-1",
        "feedbackDigest": "d" * 64,
        "revision": 1,
        "supersedesFeedbackId": None,
        "journeyId": "journey-1",
        "canonicalWorkflowRevisionId": "revision-1",
        "platformExecutionIdentity": "execution-1",
        "outcomeId": "outcome-1",
        "evidenceId": "evidence.execution-1.1.1",
        "assessment": "SATISFIED",
        "reasonCodes": ("MISSING_CONSTRAINT",),
        "principalId": "human-1",
        "decisionTime": "2026-08-30T02:00:00Z",
        "tenantId": "namespace-a",
        "securityDomain": "domain-a",
        "provenance": "LIVE_EXECUTION",
    }
    values.update(overrides)
    return OutcomeFeedbackRecord.model_validate(values)


def test_aggregation_is_deterministic_ordered_and_repeated_stably() -> None:
    one = snapshot()
    two = snapshot("execution-2", records=[evidence("execution-2", storage_sequence=7)])
    forward = accounting([two, one]).to_dict()
    reverse = accounting([one, two]).to_dict()
    assert forward == reverse
    assert forward["sourceSnapshotIds"] == sorted(forward["sourceSnapshotIds"])
    assert forward["executionCount"] == 2
    assert forward["attemptCount"] == 2
    assert forward["providerCallCount"] == 4
    assert forward["sourceHighWaterMark"] == 7
    assert all(
        metric["value"] == 1.0 for metric in forward["identityCoverage"].values()
    )


def test_exact_snapshot_evidence_and_outcome_identity_provenance() -> None:
    snapshots = [snapshot(), snapshot("execution-2")]
    model = accounting(
        snapshots,
        outcome_comparisons=(comparison(1, 2),),
        interventions=(intervention(),),
        feedback=(feedback(),),
    )
    assert model.source_snapshot_ids == tuple(
        sorted(item.shared_snapshot_id for item in snapshots)
    )
    assert model.evidence_identities == (
        "evidence.execution-1.1.1",
        "evidence.execution-2.1.1",
    )
    assert model.outcome_identities == ("outcome-1", "outcome-2")
    assert model.intervention_linkage_count == model.feedback_linkage_count == 1


@pytest.mark.parametrize(
    ("classification", "field"),
    [
        ("SUCCEEDED", "success"),
        ("FAILED", "failure"),
        ("DENIED", "denial"),
        ("UNKNOWN", "unknown"),
    ],
)
def test_outcome_counts_and_rates(classification, field: str) -> None:
    record = evidence(outcome_classification=classification)
    if classification == "DENIED":
        record = replace(
            record,
            authorization_decision=AuthorizationDecision.DENY,
            provider_call_count=0,
        )
    metric = getattr(accounting([snapshot(records=[record])]), field)
    assert (metric.numerator, metric.denominator, metric.value) == (1, 1, 1.0)


def test_empty_denominators_are_not_measurable_not_zero_rate_evidence() -> None:
    model = accounting(())
    assert model.execution_count == 0
    assert model.success.value is None
    assert model.success.availability is Availability.NOT_MEASURABLE
    assert model.evidence_completeness.availability is Availability.NOT_MEASURABLE


def test_duplicate_snapshot_and_evidence_are_idempotent() -> None:
    source = snapshot()
    model = accounting([source, source])
    assert model.execution_count == model.attempt_count == 1
    assert model.provider_call_count == 2
    assert len(model.evidence_identities) == 1


@pytest.mark.parametrize("state", [SnapshotState.PARTIAL, SnapshotState.STALE])
def test_partial_and_stale_sources_are_explicitly_partial(state) -> None:
    model = accounting([replace(snapshot(), state=state)])
    assert model.source_availability is Availability.PARTIAL
    assert model.success.availability is Availability.PARTIAL
    assert dict(model.limitation_counts)


def test_unsupported_token_cost_and_latency_are_not_measurable() -> None:
    model = accounting()
    assert model.token_usage_availability is Availability.NOT_MEASURABLE
    assert model.monetary_cost_availability is Availability.NOT_MEASURABLE
    assert model.elapsed_latency_availability is Availability.NOT_MEASURABLE


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [(1, 2, "IMPROVEMENT"), (2, 1, "REGRESSION"), (1, 1, "NO_CHANGE")],
)
def test_comparable_outcome_change(before, after, expected) -> None:
    model = accounting(
        [snapshot(), snapshot("execution-2")],
        outcome_comparisons=(comparison(before, after),),
    )
    assert dict(model.outcome_change_counts)[expected] == 1
    assert model.outcome_comparison_availability is Availability.MEASURED


def test_noncomparable_outcome_is_not_measurable() -> None:
    model = accounting(
        [snapshot(), snapshot("execution-2")],
        outcome_comparisons=(comparison(None, 2),),
    )
    assert model.outcome_comparison_availability is Availability.NOT_MEASURABLE


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"namespace": "foreign"}, "ACCOUNTING_SCOPE_DENIED"),
        ({"security_domain": "foreign"}, "ACCOUNTING_SCOPE_DENIED"),
    ],
)
def test_cross_scope_snapshot_denied_before_aggregation(kwargs, reason) -> None:
    with pytest.raises(AccountingError, match=reason):
        accounting([replace(snapshot(), **kwargs)])


def test_cross_scope_records_do_not_disclose_identity_count_or_existence() -> None:
    with pytest.raises(AccountingError) as captured:
        accounting(interventions=(intervention(tenantId="foreign-secret"),))
    assert "foreign-secret" not in str(captured.value)
    assert "intervention-record-1" not in str(captured.value)


def test_input_facts_are_not_mutated_and_aggregation_has_no_external_calls(
    monkeypatch,
) -> None:
    source = snapshot()
    before = source.to_dict()
    for module in ("socket", "subprocess"):
        monkeypatch.setattr(
            f"{module}.Popen" if module == "subprocess" else f"{module}.socket",
            lambda *args, **kwargs: pytest.fail("external call attempted"),
        )
    accounting([source])
    assert source.to_dict() == before
