"""Tests for the shared Product/Technical view source."""

from dataclasses import replace

import pytest
from agent_console.shared_views import (
    HERMES_SUPPORT,
    NATIVE_SUPPORT,
    OPENCLAW_SUPPORT,
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
    with pytest.raises(ViewProjectionError, match="RUNTIME_SUBSTITUTION_NOT_ALLOWED"):
        source(requested_runtime="OPENCLAW", effective_runtime="NATIVE")


def test_runtime_classifications_are_exact_and_support_is_not_claimed() -> None:
    assert NATIVE_SUPPORT.classification == (
        "COMPONENT_TESTED_CANDIDATE / PRIMARY_GOLDEN_PATH_CANDIDATE"
    )
    assert NATIVE_SUPPORT.support == "NOT_CERTIFIED"
    assert OPENCLAW_SUPPORT.classification == "EXACT_VERSION_CANDIDATE"
    assert OPENCLAW_SUPPORT.availability == (
        "CURRENTLY_UNAVAILABLE_WITHOUT_LIVE_MANAGED_PROFILE_EVIDENCE"
    )
    assert OPENCLAW_SUPPORT.support == "SUPPORT_NOT_GRANTED"
    assert HERMES_SUPPORT.classification == ("EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE")
    assert HERMES_SUPPORT.support == "SUPPORT_NOT_GRANTED"


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


def test_allow_requires_provider_call_evidence() -> None:
    with pytest.raises(
        ViewProjectionError, match="ALLOW_REQUIRES_PROVIDER_CALL_EVIDENCE"
    ):
        source(provider_call_count=0)


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


def test_mutable_collections_are_defensively_copied() -> None:
    plan = ["plan.group_themes"]
    citations = [source().citations[0]]
    shared = source(work_plan_keys=plan, citations=citations)
    plan.append("plan.mutated")
    citations.clear()
    assert shared.work_plan_keys == ("plan.group_themes",)
    assert len(shared.citations) == 1


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        (
            {"work_plan_keys": tuple(f"plan.{index}" for index in range(33))},
            "MALFORMED_PROJECTION_COLLECTION",
        ),
        ({"outcome_summary_key": "x" * 2_001}, "PROJECTION_LIMIT_EXCEEDED"),
        ({"capability_decision": "ALLOW"}, "INVALID_CAPABILITY_DECISION"),
        ({"outcome_status": "PASS"}, "INVALID_OUTCOME_STATUS"),
        ({"task_id": "instance-001"}, "IDENTITY_DOMAIN_COLLISION"),
        (
            {"provider_native_correlation_id": "pei-demo-001"},
            "NATIVE_ID_CANNOT_BE_PLATFORM_AUTHORITY",
        ),
        ({"citations": (object(),)}, "MALFORMED_CITATION"),
        (
            {"outcome_summary_key": "outcome.api_key.must-not-leak"},
            "SECRET_SHAPED_VALUE_REJECTED",
        ),
    ],
)
def test_hostile_or_contradictory_projection_evidence_fails_closed(
    overrides, code
) -> None:
    with pytest.raises(ViewProjectionError) as exc_info:
        source(**overrides)
    assert str(exc_info.value) == code
    assert "/private/" not in str(exc_info.value)


def test_non_synthetic_knowledge_evidence_is_rejected() -> None:
    with pytest.raises(ViewProjectionError, match="NON_SYNTHETIC_KNOWLEDGE_EVIDENCE"):
        KnowledgeCitation(
            "knowledge-collection.production.quality",
            "knowledge-asset.synthetic.standard",
            "revision.synthetic.standard.r3",
            "evidence.synthetic.standard.12",
            "citation.synthetic.standard.section_2",
        )


def test_aggregate_projection_output_is_bounded() -> None:
    large = tuple(f"message.{index}.{'x' * 990}" for index in range(32))
    with pytest.raises(ViewProjectionError, match="PROJECTION_LIMIT_EXCEEDED"):
        source(
            responsibility_keys=large,
            allowed_activity_keys=large,
            prohibited_activity_keys=large,
        )
