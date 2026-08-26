# ruff: noqa: E402
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
REPOSITORY = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from prototype import (
    accept_suggestion,
    apply_ai_suggestion,
    approve_draft,
    create_draft,
    field_diff,
    load_fixture,
    mock_publish,
    project_views,
    reject_draft,
    validate_draft,
)


def test_fixture_load_is_deterministic_and_independent() -> None:
    first = load_fixture()
    second = load_fixture()
    assert first == second
    first["execution"]["business_status"] = "locally changed"
    assert second["execution"]["business_status"] == "COMPLETED"


def test_required_stable_identities_are_present_and_distinct() -> None:
    identities = load_fixture()["identities"]
    required = {
        "digital_employee_id",
        "definition_id",
        "instance_id",
        "task_id",
        "platform_execution_identity",
        "knowledge_collection_id",
        "capability_request_id",
        "runtime_provider_id",
        "provider_correlation_id",
    }
    values = [identities[key] for key in required]
    assert all(values)
    assert len(values) == len(set(values))


def test_draft_is_separate_and_caller_fixture_is_not_mutated() -> None:
    fixture = load_fixture()
    original = deepcopy(fixture)
    draft = create_draft(fixture)
    draft["values"]["name"] = "Changed locally"
    assert fixture == original
    assert fixture["authoring"]["published"]["name"] == "Mira"


def test_ai_suggestion_remains_candidate_until_human_accepts() -> None:
    fixture = load_fixture()
    draft = apply_ai_suggestion(
        create_draft(fixture), fixture["authoring"]["ai_suggestion"]
    )
    assert draft["suggestions"][0]["status"] == "PENDING_HUMAN_REVIEW"
    assert (
        draft["values"]["business_responsibilities"]
        != (fixture["authoring"]["ai_suggestion"]["candidate"])
    )
    accepted = accept_suggestion(draft)
    assert accepted["suggestions"][0]["status"] == "HUMAN_ACCEPTED_IN_DRAFT"
    assert (
        accepted["values"]["business_responsibilities"]
        == (fixture["authoring"]["ai_suggestion"]["candidate"])
    )


def test_field_diff_is_deterministic_and_field_level() -> None:
    fixture = load_fixture()
    draft = create_draft(fixture)
    draft["values"]["role_description"] = "A Human-edited mock description."
    draft["values"]["can_do"] = ["Analyze authorized synthetic records"]
    expected = ["role_description", "can_do"]
    assert [
        row["field"] for row in field_diff(fixture["authoring"]["published"], draft)
    ] == expected
    assert [
        row["field"] for row in field_diff(fixture["authoring"]["published"], draft)
    ] == expected


def test_invalid_draft_fails_closed() -> None:
    fixture = load_fixture()
    draft = create_draft(fixture)
    draft["values"]["role_title"] = " "
    approved = approve_draft(draft)
    assert approved["state"] == "DRAFT_INVALID"
    assert approved["approval"] == "REQUIRED"
    assert {issue["code"] for issue in approved["validation_issues"]} == {
        "REQUIRED_VALUE_MISSING"
    }


def test_pending_suggestion_blocks_approval() -> None:
    fixture = load_fixture()
    draft = apply_ai_suggestion(
        create_draft(fixture), fixture["authoring"]["ai_suggestion"]
    )
    assert validate_draft(draft) == [
        {"field": "suggestions", "code": "HUMAN_REVIEW_REQUIRED"}
    ]
    assert approve_draft(draft)["state"] == "DRAFT_INVALID"


def test_publish_requires_human_approval_and_does_not_mutate_inputs() -> None:
    fixture = load_fixture()
    published = fixture["authoring"]["published"]
    draft = create_draft(fixture)
    with pytest.raises(ValueError, match="HUMAN_APPROVAL_REQUIRED"):
        mock_publish(published, draft)
    original_published = deepcopy(published)
    original_draft = deepcopy(draft)
    result = mock_publish(published, approve_draft(draft))
    assert result["publication"] == "IN_MEMORY_ONLY_NOT_PERSISTED"
    assert (published, draft) == (original_published, original_draft)


def test_reject_keeps_draft_visibly_non_published() -> None:
    rejected = reject_draft(create_draft(load_fixture()))
    assert rejected["state"] == "DRAFT_REJECTED_NOT_PUBLISHED"
    assert rejected["approval"] == "HUMAN_REJECTED"


def test_product_and_technical_views_share_platform_execution_truth() -> None:
    fixture = load_fixture()
    product, technical = project_views(fixture)
    expected = fixture["execution"]["platform_execution_identity"]
    assert product["platform_execution_identity"] == expected
    assert technical["platform_execution_identity"] == expected
    assert technical["provider_native_correlation_id"] != expected


def test_product_and_technical_identity_mapping_is_complete() -> None:
    fixture = load_fixture()
    product, technical = project_views(fixture)
    identities = fixture["identities"]
    assert product["digital_employee_id"] == identities["digital_employee_id"]
    assert technical["digital_employee_definition"] == identities["definition_id"]
    assert (
        technical["agent_definition_reference"]
        == identities["agent_definition_reference"]
    )
    assert technical["instance_identity"] == identities["instance_id"]
    assert technical["task_identity"] == identities["task_id"]
    assert technical["workflow_reference"] == identities["workflow_id"]


def test_runtime_support_labels_are_honest_and_exact() -> None:
    support = {item["runtime"]: item for item in load_fixture()["runtime_support"]}
    assert support["Native"]["product_label"] == "AVAILABLE"
    assert support["Native"]["support"] == "NOT_CERTIFIED"
    assert support["OpenClaw"]["target"] == "2026.7.1-2"
    assert support["OpenClaw"]["support"] == "NOT_GRANTED"
    assert support["Hermes"]["technical_state"] == "NOT_CURRENTLY_CERTIFIABLE"


def test_no_silent_runtime_substitution() -> None:
    execution = load_fixture()["execution"]
    assert execution["requested_runtime"] == execution["effective_runtime"] == "Native"
    assert execution["replay_barrier"] == "NO_AUTOMATIC_RETRY_AFTER_POSSIBLE_EFFECTS"


def test_capacity_is_mock_only_and_does_not_claim_scaling() -> None:
    execution = load_fixture()["execution"]
    assert (
        execution["desired_instance_count"]
        == execution["effective_instance_count"]
        == 2
    )
    assert execution["scale_recommendation"].endswith("MOCK_ONLY")


def test_knowledge_allow_and_zero_call_deny_are_visible() -> None:
    knowledge = load_fixture()["knowledge"]
    assert knowledge["authorization"] == {
        "decision": "ALLOW",
        "reason": "SYNTHETIC_SCOPE_MATCH",
        "provider_calls": 1,
    }
    assert knowledge["deny_evidence"]["decision"] == "DENY"
    assert knowledge["deny_evidence"]["provider_calls"] == 0


def test_citations_trace_to_distinct_assets_revisions_and_evidence() -> None:
    assets = load_fixture()["knowledge"]["assets"]
    for key in ("asset_id", "revision", "evidence_id", "citation"):
        values = [asset[key] for asset in assets]
        assert all(values)
        assert len(values) == len(set(values))


def test_all_required_mock_states_are_present() -> None:
    states = set(load_fixture()["states"])
    assert {
        "empty",
        "Draft",
        "Diff pending approval",
        "approved mock definition",
        "execution running",
        "execution succeeded",
        "capability denied",
        "outcome unknown",
        "OpenClaw unavailable",
        "Hermes experimental",
        "Knowledge authorization allowed",
        "Knowledge authorization denied",
        "citation available",
        "citation unavailable or stale",
    } <= states


def test_primary_business_journey_has_at_most_three_steps() -> None:
    assert load_fixture()["scenario"]["primary_steps"] == [
        "Enter a business problem",
        "Review recommended employees and plan",
        "Start mock work and view results",
    ]


def test_fixture_contains_only_synthetic_non_authoritative_labels() -> None:
    fixture = load_fixture()
    assert fixture["classification"] == (
        "INTERNAL_MOCK / NON_AUTHORITATIVE / VERSION_UNFROZEN"
    )
    assert fixture["knowledge"]["provider_label"] == "SYNTHETIC / VIEW_ONLY"
    assert fixture["knowledge"]["live_enterprise_provider"] == "NOT_IMPLEMENTED"
    assert fixture["knowledge"]["governance"] == "NOT_GRANTED"


def test_web_mock_has_accessible_dual_view_and_required_state_controls() -> None:
    html = (ROOT / "web" / "index.html").read_text()
    script = (ROOT / "web" / "app.js").read_text()
    assert 'aria-label="Primary journey"' in html
    assert 'aria-label="Technical View"' in html
    assert "Open Technical View" in html
    assert "Reject Draft" in html
    assert "Approve and mock publish" in html
    assert "@media (max-width:760px)" in (ROOT / "web" / "styles.css").read_text()
    assert "setTechnical" in script


def test_fixture_is_valid_json_and_contains_no_credential_keys() -> None:
    raw = (
        ROOT / "fixtures" / "customer-complaint-quality-improvement.json"
    ).read_text()
    json.loads(raw)
    forbidden = {"password", "api_key", "access_token", "client_secret", "private_key"}
    assert not forbidden.intersection(json.loads(raw))
    assert not any(f'"{key}"' in raw.lower() for key in forbidden)


def test_production_code_does_not_import_spike_prototype() -> None:
    production_roots = (
        REPOSITORY / "core" / "src",
        REPOSITORY / "gateway" / "src",
        REPOSITORY / "operator" / "src",
        REPOSITORY / "runtime" / "src",
        REPOSITORY / "console" / "backend" / "src",
        REPOSITORY / "console" / "frontend" / "src",
    )
    offenders = [
        str(path.relative_to(REPOSITORY))
        for root in production_roots
        if root.exists()
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".ts", ".tsx", ".js"}
        and "s5-spike-008" in path.read_text()
    ]
    assert offenders == []
