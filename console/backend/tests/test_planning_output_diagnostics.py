import json

import pytest
from agent_console.plan_suggestion_invocation import FlexiblePlanningProviderResult
from agent_console.planning_output_diagnostics import diagnostic
from pydantic import ValidationError
from test_planning_runtime import formal as formal
from test_planning_runtime import send


def test_diagnostic_omits_unknown_keys_values_and_messages():
    text = json.dumps({"kind": "UNSUPPORTED", "secret-key": "private provider secret"})
    with pytest.raises(ValidationError) as caught:
        FlexiblePlanningProviderResult.model_validate_json(text)
    value = diagnostic(text, "SCHEMA_OR_CONTRACT", caught.value)
    assert value["issues"] == [
        {"path": ["UNKNOWN_FIELD"], "type": "extra_forbidden", "rule": None}
    ]
    assert value["output_bytes"] == len(text.encode())
    assert len(value["output_sha256"]) == 64
    assert "secret" not in json.dumps(value)


@pytest.mark.parametrize(
    "mode,rule",
    [("cycle", "PLAN_DEPENDENCY_CYCLE"), ("reference", "PLAN_REFERENCE_INVALID")],
)
def test_invalid_contract_keeps_diagnostic_in_receipt_without_business_acceptance(
    formal, mode, rule
):
    formal.mode = mode
    response = send(formal.start())
    result = response.json()["result"]
    assert result["result"] == {
        "technical_status": "SUCCEEDED",
        "kind": "INVALID",
        "reason": "PLANNING_OUTPUT_SCHEMA_INVALID",
    }
    receipt = formal.invocations.rows[result["invocation"]["target"]["invocation_id"]][
        "receipt"
    ]
    value = receipt["validation_diagnostic"]
    assert value["phase"] == "SCHEMA_OR_CONTRACT"
    assert value["issues"] == [
        {"path": ["semantics"], "type": "value_error", "rule": rule}
    ]
    assert "private provider" not in json.dumps(value)
    assert "text" not in receipt


@pytest.mark.parametrize("phase", ["TARGET_MISMATCH", "POLICY_MISMATCH"])
def test_exact_target_and_policy_mismatch_are_distinct(formal, monkeypatch, phase):
    from agent_console import plan_suggestion_runtime as runtime
    from test_planning_contracts import modern

    original = runtime.OpenAIResponsesDraftTransport.exchange

    def exchange(self, **kwargs):
        status, body, correlation, latency = original(self, **kwargs)
        response = json.loads(body)
        result = json.loads(response["output"][0]["content"][0]["text"])
        value = modern()
        value["target"] = result["semantics"]["target"]
        if phase == "TARGET_MISMATCH":
            value["target"]["expected_problem_version"] += 1
        else:
            value["policy"] = {
                "mode": "TEMPLATE_ASSISTED",
                "template": "procurement-overdue.v1",
            }
        result["semantics"] = value
        response["output"][0]["content"][0]["text"] = json.dumps(result)
        return status, json.dumps(response).encode(), correlation, latency

    monkeypatch.setattr(runtime.OpenAIResponsesDraftTransport, "exchange", exchange)
    result = send(formal.start(), policy={"mode": "FREE"}).json()["result"]
    assert result["result"]["kind"] == "INVALID"
    receipt = formal.invocations.rows[result["invocation"]["target"]["invocation_id"]][
        "receipt"
    ]
    assert receipt["validation_diagnostic"]["phase"] == phase
    assert receipt["validation_diagnostic"]["issues"] == []
