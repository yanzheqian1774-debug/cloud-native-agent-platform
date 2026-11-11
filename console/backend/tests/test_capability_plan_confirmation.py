from types import SimpleNamespace

import pytest
from agent_console import capability_plan_confirmation as module
from agent_console.capability_plan_confirmation import (
    CapabilityPlanSource,
    validate_source,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from pydantic import ValidationError
from test_capability_execution_constraints import fixture


def source():
    return dict(
        capabilityConversationId="conversation",
        capabilityMessageId="message",
        capabilityContractDigest="c" * 64,
    )


@pytest.mark.parametrize("missing", list(source()))
def test_partial_reference_rejected(missing):
    payload = source()
    del payload[missing]
    with pytest.raises(ValidationError):
        CapabilityPlanSource.model_validate(payload)


def test_capability_marker_cannot_bypass_source_by_omission():
    _, plan, current, _ = fixture()
    with pytest.raises(WorkbenchOwnerError, match="SOURCE_REQUIRED"):
        validate_source(None, None, CapabilityPlanSource(), plan, current)


def test_legacy_unmarked_criteria_keep_existing_route():
    validate_source(
        None,
        None,
        CapabilityPlanSource(),
        None,
        {"criteria": [{"applicability": None}]},
    )


@pytest.mark.parametrize(
    "mode", ["valid", "digest", "association", "boundary", "revoked"]
)
def test_owned_source_checked_before_confirming(monkeypatch, mode):
    resolved, plan, current, _ = fixture()
    plan.semantics.target.problem = SimpleNamespace(
        model_dump=lambda **_: current["target"]["problem"]
    )
    seen = []

    def reader(call, conversation, message):
        seen.append((conversation, message))
        if mode == "revoked":
            raise WorkbenchOwnerError("SOURCE_REVOKED", 403)
        return resolved

    def association(*args):
        seen.append("association")
        if mode == "association":
            raise WorkbenchOwnerError("WRONG_PROBLEM", 409)

    monkeypatch.setattr(module, "verify_work_association", association)
    if mode == "digest":
        resolved["contractDigest"] = "d" * 64
    if mode == "boundary":
        plan.semantics.boundaries = []
    args = (
        SimpleNamespace(capability_contract_reader=reader),
        object(),
        CapabilityPlanSource(**source()),
        plan,
        current,
    )
    if mode == "valid":
        validate_source(*args)
        assert seen == [("conversation", "message"), "association"]
    else:
        with pytest.raises(WorkbenchOwnerError):
            validate_source(*args)
