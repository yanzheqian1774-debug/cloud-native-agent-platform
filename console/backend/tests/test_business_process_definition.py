"""Business semantics must not collapse into executable workflow semantics."""

import pytest
from agent_console.business_process_definition import (
    BusinessArchitecture,
    BusinessCapabilityRelation,
    BusinessProcessContent,
    FixedBusinessReference,
    definition_issues,
    relation_issues,
)
from pydantic import ValidationError


def architecture():
    return BusinessArchitecture.model_validate(
        {
            "domains": [
                {"domain_id": "procurement", "name": "采购管理", "band": "CORE"}
            ],
            "groups": [
                {
                    "group_id": "suppliers",
                    "domain_id": "procurement",
                    "name": "供应商管理",
                }
            ],
        }
    )


def content():
    return BusinessProcessContent.model_validate(
        {
            "name": "供应商交付评审",
            "domain_id": "procurement",
            "group_id": "suppliers",
            "owner_description": "采购负责人",
            "purpose": "核对交付事实",
            "activities": [
                {
                    "activity_id": identity,
                    "name": name,
                    "responsible_role": "业务专员",
                    "inputs": ["交付资料"],
                    "outputs": ["核对依据"],
                    "completion_conditions": ["缺失事实明确列出"],
                    "human_boundary": "业务负责人核实",
                }
                for identity, name in [("collect", "收集资料"), ("review", "审核交付")]
            ],
            "handoffs": [
                {
                    "from_activity_id": "collect",
                    "to_activity_id": "review",
                    "event": "COMPLETED",
                    "explanation": "核对后交付",
                },
                {
                    "from_activity_id": "review",
                    "to_activity_id": "collect",
                    "event": "RETURNED",
                    "explanation": "有错误退回",
                    "responsible_role": "业务专员",
                },
                {
                    "from_activity_id": "review",
                    "to_activity_id": "collect",
                    "event": "NEEDS_INFORMATION",
                    "explanation": "补齐缺失资料",
                    "responsible_role": "业务专员",
                },
            ],
        }
    )


def reference(revision="r1"):
    return FixedBusinessReference(
        resource_id="process:1", revision_id=revision, digest="a" * 64
    )


def test_empty_enterprise_structure_is_not_seeded_with_prototype_facts():
    value = BusinessArchitecture()
    assert value.domains == value.groups == ()
    value = architecture().model_dump()
    value["groups"][0]["domain_id"] = "missing"
    with pytest.raises(ValidationError, match="BUSINESS_GROUP_DOMAIN_NOT_FOUND"):
        BusinessArchitecture.model_validate(value)


def test_incomplete_draft_preserves_unknowns_and_reports_real_paths():
    value = BusinessProcessContent(
        name="待完善流程", domain_id="procurement", group_id="suppliers"
    )
    assert value.owner_description is None and value.activities == ()
    assert {issue.path for issue in definition_issues(value, architecture())} == {
        "owner_description",
        "purpose",
        "activities",
    }
    assert "employee" not in type(value).model_fields


def test_business_return_and_information_handoffs_are_not_rejected_as_dag_cycles():
    value = content()
    assert definition_issues(value, architecture()) == ()
    assert value.activities[0].employee is None  # Human-led activity is legitimate.
    assert [edge.event for edge in value.handoffs] == [
        "COMPLETED",
        "RETURNED",
        "NEEDS_INFORMATION",
    ]


def test_employee_does_not_fill_missing_responsibility_or_authorize_execution():
    record = content().model_dump()
    record["activities"][0]["responsible_role"] = None
    record["activities"][0]["employee"] = reference().model_dump()
    value = BusinessProcessContent.model_validate(record)
    assert [issue.path for issue in definition_issues(value, architecture())] == [
        "activities.0.responsible_role"
    ]
    record["execution_authorized"] = True
    with pytest.raises(ValidationError):
        BusinessProcessContent.model_validate(record)


def test_dangling_handoff_and_duplicate_identity_rejected_without_guessing():
    record = content().model_dump()
    record["handoffs"][0]["to_activity_id"] = "not-registered"
    with pytest.raises(ValidationError, match="BUSINESS_HANDOFF_ACTIVITY_NOT_FOUND"):
        BusinessProcessContent.model_validate(record)
    record = content().model_dump()
    record["activities"][1]["activity_id"] = "collect"
    with pytest.raises(ValidationError, match="BUSINESS_ACTIVITY_DUPLICATE_ID"):
        BusinessProcessContent.model_validate(record)


@pytest.mark.parametrize("kind", ["SUPPORTS_ACTIVITY", "DERIVED_FROM_PROCESS"])
def test_fixed_relation_types_keep_history_and_multi_activity_coverage(kind):
    relation = BusinessCapabilityRelation(
        relation_id="link:1",
        relation_revision_id="link-revision:1",
        relation_type=kind,
        process=reference(),
        activity_ids=("collect", "review"),
        capability=FixedBusinessReference(
            resource_id="capability:1", revision_id="cap-r1", digest="b" * 64
        ),
        coverage_description="覆盖资料核对与审核辅助, 责任仍属人工",
    )
    assert relation_issues(relation, reference(), content()) == ()
    assert relation.relation_type == kind  # Never infer the other relationship.
    assert (
        relation_issues(relation, reference("r2"), content())[0].code
        == "PROCESS_REVISION_MISMATCH"
    )
    bad = relation.model_dump()
    bad["activity_ids"] = ["other-process-activity"]
    assert (
        relation_issues(
            BusinessCapabilityRelation.model_validate(bad), reference(), content()
        )[0].code
        == "ACTIVITY_COVERAGE_NOT_FOUND"
    )


def test_handoff_identity_survives_semantic_edit_and_duplicate_identity_is_rejected():
    original = content().model_dump(mode="json")
    assert original["handoffs"]
    original["handoffs"][0]["handoff_id"] = "handoff:stable"
    first = BusinessProcessContent.model_validate(original)
    edited = first.model_dump(mode="json")
    edited["handoffs"][0]["explanation"] = "补齐后记录核对依据"
    second = BusinessProcessContent.model_validate(edited)
    assert second.handoffs[0].handoff_id == first.handoffs[0].handoff_id
    another = {**edited["handoffs"][0], "event": "COMPLETED"}
    edited["handoffs"].append(another)
    with pytest.raises(ValidationError, match="BUSINESS_HANDOFF_DUPLICATE_ID"):
        BusinessProcessContent.model_validate(edited)
    legacy = content().model_dump(mode="json")
    for item in legacy["handoffs"]:
        item.pop("handoff_id", None)
    assert BusinessProcessContent.model_validate(legacy).handoffs[0].handoff_id is None
