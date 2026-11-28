"""Planning contract construction; real source/association reads covered separately."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console import capability_planning_input as module
from agent_console.capability_execution_constraints import exclusion_boundaries
from agent_console.capability_work_input import work_input
from agent_console.plan_suggestion_invocation import PlanningRequest
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_capability_execution_constraints import fixture
from test_plan_suggestion_v2 import sample


def setup(monkeypatch):
    resolved, _, current, _ = fixture()
    contract = resolved["contract"]
    contract.update(conversationId="conversation", sourceMessageId="message")
    contract["bindings"].append(
        {
            "kind": "KNOWLEDGE",
            "reference": {
                "resource_id": "knowledge",
                "revision_id": "v1",
                "digest": "f" * 64,
            },
        }
    )
    current["criteria"][0]["applicability"] = work_input(resolved)["criterion"][
        "applicability"
    ]
    current["target"] = sample()["target"]
    seen = []
    app = SimpleNamespace(current_input=lambda *args: current, scope=lambda p: "scope")
    automation = SimpleNamespace(
        authenticate=lambda ctx: None,
        bound_app=lambda call: app,
        capability_contract_reader=lambda *args: resolved,
        work=lambda *args: "work",
        grants=SimpleNamespace(clock=lambda: None),
    )
    monkeypatch.setattr(
        module, "verify_work_association", lambda *args: seen.append("association")
    )
    monkeypatch.setattr(
        module, "require_read", lambda *args: seen.append("source-read")
    )
    monkeypatch.setattr(
        module,
        "read_employee_member",
        lambda *args: (
            {"documents": [{"chunks": [{"content": '{"synthetic":true}'}]}]},
            "Source",
        ),
    )
    monkeypatch.setattr(
        module, "validate", lambda *args: {"sourceSchema": "document-review-source.v1"}
    )

    def observe(*args, **kwargs):
        assert kwargs["fixed_bindings"] == contract["bindings"]
        seen.append("fixed-members")
        return {
            "operations": [
                {"operation": op, "inputKinds": ["CONTEXT"], "outputKind": "DATA"}
                for op in ["READ_DATA", "ANALYZE_DATA", "RENDER_REPORT"]
            ]
        }

    monkeypatch.setattr(module, "observe", observe)
    call = SimpleNamespace(
        context=SimpleNamespace(
            principal_id="user",
            scope=SimpleNamespace(tenant_id="tenant", security_domain="domain"),
        ),
        connection=object(),
        authority=object(),
        payload={
            "conversationId": "conversation",
            "sourceMessageId": "message",
            "contractDigest": resolved["contractDigest"],
            "problemId": "problem",
            "idempotencyKey": "planning-key",
        },
    )
    return automation, call, resolved, current, seen


def test_prepares_fresh_target_and_observes_only_fixed_members(monkeypatch):
    automation, call, resolved, current, seen = setup(monkeypatch)
    before = deepcopy((resolved, current))
    result = module.CapabilityPlanningInput(automation)(call)
    planning = PlanningRequest.model_validate(result["planningRequest"])
    assert planning.target.model_dump(mode="json") == current["target"]
    assert (
        planning.source_proposal is None and planning.predecessor_invocation_id is None
    )
    assert "No deployment" in planning.answers
    assert seen == ["association", "source-read", "fixed-members"]
    assert result["modelCalls"] == 0 and result["executionStarted"] is False
    assert (resolved, current) == before


@pytest.mark.parametrize("mode", ["digest", "input", "criteria", "unsupported"])
def test_changed_contract_cannot_produce_planning_request(monkeypatch, mode):
    automation, call, resolved, current, seen = setup(monkeypatch)
    if mode == "digest":
        call.payload["contractDigest"] = "e" * 64
    elif mode == "input":
        current["description"] = "Changed"
    elif mode == "criteria":
        current["criteria"][0]["measurement"]["rubric"] = "Changed"
    else:
        resolved["contract"]["bindings"].append({"kind": "TOOL", "reference": {}})
        current["criteria"][0]["applicability"] = work_input(resolved)["criterion"][
            "applicability"
        ]
    with pytest.raises(WorkbenchOwnerError):
        module.CapabilityPlanningInput(automation)(call)
    assert "fixed-members" not in seen


def test_long_exclusions_are_preserved_in_bounded_ordered_parts():
    original = "禁" * 2000
    parts = exclusion_boundaries({"exclusions": original})
    assert all(len(part) <= 500 for part in parts)
    assert "".join(part.split("] ", 1)[1] for part in parts) == original
