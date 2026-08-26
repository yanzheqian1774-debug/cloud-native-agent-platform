"""Tests for the shared Product/Technical view source."""

from dataclasses import replace

import pytest
from agent_console.shared_views import (
    AuthorizationDecision,
    KnowledgeCitation,
    OutcomeStatus,
    SharedExecutionView,
    ViewProjectionError,
    product_view,
    technical_view,
)
from agent_core.representation.v0_2 import PlatformExecutionIdentity


def source(**overrides) -> SharedExecutionView:
    values = {
        "platform_execution_identity": PlatformExecutionIdentity("pei-demo-001"),
        "definition_id": "definition.customer-insight",
        "definition_revision": "rev-001",
        "instance_id": "instance-001",
        "task_id": "task-001",
        "workflow_id": "workflow-001",
        "digital_employee_name_key": "employee.mira.name",
        "role_title_key": "employee.mira.role_title",
        "role_description_key": "employee.mira.role_description",
        "responsibility_keys": ("employee.mira.responsibility.classify",),
        "allowed_activity_keys": ("employee.mira.can_do.synthetic",),
        "prohibited_activity_keys": ("employee.mira.cannot_do.contact",),
        "suggested_team_ids": ("definition.customer-insight",),
        "instance_count": 1,
        "work_plan_keys": ("plan.group_themes", "plan.prioritize"),
        "business_progress_code": "COMPLETED",
        "approval_state": "HUMAN_APPROVED",
        "requested_runtime": "NATIVE",
        "effective_runtime": "NATIVE",
        "provider_native_correlation_id": "native-correlation-001",
        "capability_decision": AuthorizationDecision.ALLOW,
        "capability_reason_code": "SYNTHETIC_SCOPE_MATCH",
        "provider_call_count": 1,
        "outcome_status": OutcomeStatus.PASS,
        "outcome_summary_key": "outcome.synthetic.complaint_summary",
        "citations": (
            KnowledgeCitation(
                "knowledge-collection.synthetic.quality.v1",
                "knowledge-asset.synthetic.standard",
                "revision.synthetic.standard.r3",
                "evidence.synthetic.standard.12",
                "citation.synthetic.standard.section_2",
            ),
        ),
        "limitation_codes": ("SYNTHETIC_KNOWLEDGE_ONLY", "NOT_CERTIFIED"),
    }
    values.update(overrides)
    return SharedExecutionView(**values)


def test_both_views_share_one_execution_truth_and_distinct_identity_domains() -> None:
    shared = source()
    product = product_view(shared)
    technical = technical_view(shared)
    assert (
        product["platformExecutionIdentity"] == technical["platformExecutionIdentity"]
    )
    assert technical["definition"]["id"] != technical["instanceId"]
    assert technical["instanceId"] != technical["taskId"]
    assert technical["taskId"] != technical["workflowId"]
    assert technical["providerNativeCorrelation"] == {
        "id": "native-correlation-001",
        "authority": "CORRELATION_ONLY",
    }


def test_requested_and_effective_runtime_remain_separate_and_honest() -> None:
    shared = source(effective_runtime=None)
    technical = technical_view(shared)
    assert technical["requestedRuntime"]["runtime"] == "NATIVE"
    assert technical["effectiveRuntime"] is None
    with pytest.raises(ViewProjectionError, match="UNSUPPORTED_RUNTIME_EVIDENCE"):
        source(requested_runtime="OPENCLAW", effective_runtime="OPENCLAW")
    with pytest.raises(ViewProjectionError, match="UNSUPPORTED_RUNTIME_EVIDENCE"):
        source(requested_runtime="HERMES", effective_runtime="HERMES")


def test_allow_has_deterministic_synthetic_citations_and_serialization() -> None:
    shared = source()
    assert product_view(shared) == product_view(shared)
    assert technical_view(shared) == technical_view(shared)
    citation = product_view(shared)["citations"][0]
    assert citation["collection_id"].startswith("knowledge-collection.synthetic.")
    assert citation["evidence_id"] == "evidence.synthetic.standard.12"


def test_deny_requires_zero_provider_calls_and_no_citations() -> None:
    denied = source(
        capability_decision=AuthorizationDecision.DENY,
        capability_reason_code="KNOWLEDGE_SCOPE_NOT_AUTHORIZED",
        provider_call_count=0,
        citations=(),
        outcome_status=OutcomeStatus.FAIL,
    )
    assert technical_view(denied)["capability"]["providerCallCount"] == 0
    assert product_view(denied)["citations"] == []
    with pytest.raises(
        ViewProjectionError, match="DENY_REQUIRES_ZERO_PROVIDER_EFFECTS"
    ):
        replace(denied, provider_call_count=1)


def test_unknown_outcome_and_locale_neutral_semantics_are_preserved() -> None:
    ambiguous = source(outcome_status=OutcomeStatus.UNKNOWN)
    product = product_view(ambiguous)
    technical = technical_view(ambiguous)
    assert product["outcomeStatus"] == technical["outcome"]["status"] == "UNKNOWN"
    assert all(" " not in key for key in product["workPlanKeys"])
    assert "locale" not in product and "locale" not in technical


def test_projection_does_not_mutate_caller_source() -> None:
    shared = source()
    before = repr(shared)
    product = product_view(shared)
    technical = technical_view(shared)
    product["suggestedTeamIds"].append("mutated")
    technical["limitationCodes"].append("mutated")
    assert repr(shared) == before
    assert shared.suggested_team_ids == ("definition.customer-insight",)
