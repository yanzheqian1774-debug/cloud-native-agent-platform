from dataclasses import replace

import pytest
from agent_core.execution_evidence import (
    AuthorizationDecision,
    EvidenceEventType,
    EvidenceValidationError,
    ExecutionEvidenceRecord,
    OutcomeClassification,
)


def record(**overrides) -> ExecutionEvidenceRecord:
    values = {
        "evidence_record_id": "evidence.native.pei-001.1.1",
        "namespace": "agent-workloads",
        "security_domain": "business-unit-a",
        "platform_execution_identity": "pei-001",
        "workflow_identity": "workflow-uid-001",
        "task_identity": "task-uid-001",
        "attempt_ordinal": 1,
        "event_ordinal": 1,
        "event_type": EvidenceEventType.EXECUTION_OUTCOME,
        "occurred_at": "2026-08-27T08:00:00Z",
        "runtime_classification": "NATIVE",
        "selected_instance_identity": "instance-001",
        "capability_identity": "customer-lookup",
        "authorization_decision": AuthorizationDecision.ALLOW,
        "reason_code": "TASK_RUNTIME_SUCCEEDED",
        "provider_correlation_id": "provider-request-001",
        "provider_call_count": 1,
        "outcome_classification": OutcomeClassification.SUCCEEDED,
        "outcome_reference": "outcome-001",
        "evidence_references": ("evidence-ref-001",),
        "citation_references": ("citation-ref-001",),
        "limitation_code": None,
        "supersedes_record_id": None,
        "schema_version": 1,
    }
    values.update(overrides)
    return ExecutionEvidenceRecord(**values)


def test_record_is_immutable_and_digest_is_stable() -> None:
    value = record()
    assert value.payload_digest == record().payload_digest
    with pytest.raises(AttributeError):
        value.reason_code = "CHANGED"  # type: ignore[misc]


def test_repository_metadata_is_excluded_from_digest() -> None:
    value = record()
    persisted = value.with_repository_metadata(
        storage_sequence=99, recorded_at="2026-08-27T09:00:00Z"
    )
    assert persisted.payload_digest == value.payload_digest
    assert "recorded_at" not in persisted.canonical_payload
    assert "storage_sequence" not in persisted.canonical_payload


def test_occurred_at_is_normalized_and_stable() -> None:
    first = record(occurred_at="2026-08-27T16:00:00+08:00")
    second = record(occurred_at="2026-08-27T08:00:00Z")
    assert first.occurred_at == second.occurred_at
    assert first.payload_digest == second.payload_digest


def test_deny_requires_zero_provider_effects() -> None:
    denied = record(
        authorization_decision=AuthorizationDecision.DENY,
        provider_call_count=0,
        citation_references=(),
        outcome_classification=OutcomeClassification.DENIED,
    )
    assert denied.provider_call_count == 0
    with pytest.raises(EvidenceValidationError, match="DENY_REQUIRES_ZERO"):
        replace(denied, provider_call_count=1)


@pytest.mark.parametrize(
    "extra",
    [
        {"raw_prompt": "hello"},
        {"token": "opaque"},
        {"stack_trace": "trace"},
        {"arbitrary_metadata": "value"},
    ],
)
def test_prohibited_or_unknown_fields_are_rejected_before_hashing(extra) -> None:
    source = dict(record().canonical_payload)
    source.update(extra)
    with pytest.raises(
        EvidenceValidationError, match="UNKNOWN_OR_MISSING_EVIDENCE_FIELD"
    ):
        ExecutionEvidenceRecord.from_allowlisted(source)


def test_secret_shaped_allowed_value_and_host_path_are_rejected() -> None:
    with pytest.raises(EvidenceValidationError, match="PROHIBITED_EVIDENCE_CONTENT"):
        record(outcome_reference="token-secret-value")
    with pytest.raises(EvidenceValidationError, match="PROHIBITED_EVIDENCE_CONTENT"):
        record(outcome_reference="/Users/example/private-output")


def test_unknown_schema_and_unbounded_values_fail_closed() -> None:
    with pytest.raises(EvidenceValidationError, match="UNSUPPORTED_EVIDENCE_SCHEMA"):
        record(schema_version=2)
    with pytest.raises(EvidenceValidationError, match="INVALID_EVIDENCE"):
        record(namespace="x" * 600)
