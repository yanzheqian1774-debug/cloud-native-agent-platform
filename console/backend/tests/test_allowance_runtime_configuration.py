"""Configuration-boundary checks: no provider, credentials or database access."""

from types import SimpleNamespace

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_assistance_bootstrap import _profile
from agent_console.plan_suggestion_policy import POLICY_DIGEST
from test_openai_responses_draft_adapter import _real_runtime_document


def runtime_document(tmp_path, planning):
    value = _real_runtime_document(SimpleNamespace(server_port=443), None, tmp_path)
    value.update(
        executionClass="REAL_PROVIDER",
        responsesUrl="https://provider.invalid/v1/responses",
        tls={"caFile": None},
    )
    if planning:
        value.update(
            schemaVersion="planning-runtime.v1",
            realCallsEnabled=True,
            outputSchemaVersion="plan-suggestion-output.v1",
            targetFormatVersion="plan-suggestion-target.v1",
            policyDigest=POLICY_DIGEST,
        )
    return value


@pytest.mark.parametrize("planning", [False, True])
def test_allowance_selection_preserves_model_and_transport(tmp_path, planning):
    value = runtime_document(tmp_path, planning)
    old = _profile(value, planning=planning)
    value["budget"]["allowanceId"] = "allowance:authorized"
    selected = _profile(value, planning=planning)
    assert selected[:3] == old[:3]
    assert selected[3] == {**old[3], "allowanceId": "allowance:authorized"}
    value["budget"]["unrecognized"] = True
    with pytest.raises(DraftAssistanceError, match="PROFILE_INVALID"):
        _profile(value, planning=planning)


@pytest.mark.parametrize("planning", [False, True])
@pytest.mark.parametrize("identity", [None, True, 42, "", " ", " spaced ", "x" * 201])
def test_invalid_allowance_selector_rejected(tmp_path, planning, identity):
    value = runtime_document(tmp_path, planning)
    value["budget"]["allowanceId"] = identity
    with pytest.raises(DraftAssistanceError, match="PROFILE_INVALID"):
        _profile(value, planning=planning)
