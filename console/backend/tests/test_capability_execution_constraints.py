from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.business_problem_domain import CriterionType, validate_measurement
from agent_console.business_problem_schemas import (
    CreateBusinessProblem,
    CreateCriterionRevision,
)
from agent_console.capability_execution_constraints import verify_plan, verify_resources
from agent_console.capability_work_input import work_input
from agent_console.readonly_continuation import ContinueReadonly
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from pydantic import ValidationError


def fixture():
    employee = {"resource_id": "worker", "revision_id": "v1", "digest": "a" * 64}
    skill = {"resource_id": "skill", "revision_id": "v1", "digest": "b" * 64}
    contract = {
        "objective": "Review",
        "inputNotes": "Document",
        "acceptanceCriteria": ["Cite source"],
        "exclusions": "No deployment",
        "bindings": [
            {"kind": "EMPLOYEE", "reference": employee},
            {"kind": "SKILL", "reference": skill},
        ],
    }
    resolved = {"contract": contract, "contractDigest": "c" * 64}
    target = {"problem": employee, "criteria": skill, "criterion_revision_ids": ["c1"]}
    plan = SimpleNamespace(
        semantics=SimpleNamespace(
            target=SimpleNamespace(model_dump=lambda **_: target),
            boundaries=["No deployment"],
        )
    )
    current = {
        "target": deepcopy(target),
        "description": "Review",
        "criteria": [
            {
                "measurement": work_input(resolved)["criterion"]["measurement"],
                "applicability": work_input(resolved)["criterion"]["applicability"],
                "criterion_type": "HUMAN_EVALUATED",
                "evaluator_type": "HUMAN",
                "evaluator_version": "v1",
            }
        ],
    }

    ready = {
        "assembly": {"definition": employee},
        "resources": [{"kind": "skill", "reference": skill}],
    }
    return resolved, plan, current, ready


def test_complete_source_reference_required():
    base = {
        "version": 1,
        "capabilityConversationId": "conversation",
        "capabilityMessageId": "message",
        "capabilityContractDigest": "a" * 64,
    }
    ContinueReadonly.model_validate(base)
    ContinueReadonly.model_validate({"version": 1})
    for field in base.keys() - {"version"}:
        with pytest.raises(ValidationError):
            ContinueReadonly.model_validate(
                {k: v for k, v in base.items() if k != field}
            )


def test_exact_constraints_do_not_modify_inputs():
    resolved, plan, current, ready = fixture()
    before = deepcopy((resolved, current, ready))
    verify_plan(resolved, plan, current)
    verify_resources(resolved, ready)
    assert (resolved, current, ready) == before


@pytest.mark.parametrize("mode", ["target", "input", "criteria", "digest", "boundary"])
def test_plan_cannot_substitute_capability_scope(mode):
    resolved, plan, current, _ = fixture()
    if mode == "target":
        current["target"]["criterion_revision_ids"] = ["other"]
    elif mode == "input":
        current["description"] = "Different objective"
    elif mode == "criteria":
        current["criteria"][0]["measurement"]["rubric"] = "Different standard"
    elif mode == "digest":
        current["criteria"][0]["applicability"]["capabilityContractDigest"] = "d" * 64
    else:
        plan.semantics.boundaries = []
    with pytest.raises(WorkbenchOwnerError):
        verify_plan(resolved, plan, current)


@pytest.mark.parametrize("mode", ["employee", "revision", "additional", "unsupported"])
def test_resource_assembly_cannot_change_fixed_business_resources(mode):
    resolved, _, _, ready = fixture()
    if mode == "employee":
        ready["assembly"]["definition"] = {"resource_id": "other"}
    elif mode == "revision":
        ready["resources"][0]["reference"] = {
            "resource_id": "skill",
            "revision_id": "v2",
            "digest": "d" * 64,
        }
    elif mode == "additional":
        ready["resources"].append({"kind": "mcp", "reference": {"resource_id": "new"}})
    else:
        resolved["contract"]["bindings"].append(
            {"kind": "TOOL", "reference": {"resource_id": "tool"}}
        )
    with pytest.raises(WorkbenchOwnerError):
        verify_resources(resolved, ready)


def test_runtime_owner_kind_is_normalized_without_changing_reference():
    resolved, _, _, ready = fixture()
    reference = {"resource_id": "runtime", "revision_id": "v1", "digest": "e" * 64}
    resolved["contract"]["bindings"].append(
        {"kind": "RUNTIME_PROFILE", "reference": reference}
    )
    ready["resources"].append({"kind": "runtime", "reference": reference})
    verify_resources(resolved, ready)
    ready["resources"][-1]["reference"] = {**reference, "revision_id": "v2"}
    with pytest.raises(WorkbenchOwnerError):
        verify_resources(resolved, ready)


def test_maximum_inputs_fit_real_owner_contracts_without_losing_notes():
    resolved, _, _, _ = fixture()
    resolved["contract"]["objective"] = "目" * 2000
    resolved["contract"]["inputNotes"] = "资" * 6000
    prepared = work_input(resolved)
    problem = CreateBusinessProblem.model_validate(
        {**prepared["problem"], "ownerId": "owner", "idempotencyKey": "problem-key"}
    )
    criterion = CreateCriterionRevision.model_validate(
        {**prepared["criterion"], "idempotencyKey": "criterion-key"}
    )
    validate_measurement(CriterionType(criterion.criterionType), criterion.measurement)
    assert len(problem.title) == 200
    assert problem.description == resolved["contract"]["objective"]
    assert criterion.applicability["capabilityConstraints"] == resolved["contract"]
    criterion.applicability["capabilityConstraints"]["inputNotes"] = "changed"
    assert resolved["contract"]["inputNotes"] == "资" * 6000


@pytest.mark.parametrize(
    "field", ["inputNotes", "bindings", "acceptanceCriteria", "objective"]
)
def test_persisted_criterion_cannot_change_contract_context(field):
    resolved, plan, current, _ = fixture()
    current["criteria"][0]["applicability"]["capabilityConstraints"][field] = "changed"
    with pytest.raises(WorkbenchOwnerError):
        verify_plan(resolved, plan, current)
