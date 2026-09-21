"""Fixed probes are metered diagnostics, never planning proposals or free prompts."""

import json

import pytest
from agent_console import plan_suggestion_runtime as runtime
from agent_console.authority_contracts import AuthorityError
from agent_console.planning_diagnostics import diagnostic_document, validate_diagnostic
from test_plan_suggestion_v2 import sample
from test_planning_runtime import formal as formal


@pytest.mark.parametrize(
    "layer,text",
    [
        ("MINIMAL", "OK"),
        ("STRUCTURED", '{"ok":true}'),
        ("ADAPTER", '{"kind":"UNSUPPORTED","questions":[],"semantics":null}'),
    ],
)
def test_formal_diagnostic_is_not_proposal_and_replay_does_not_dispatch(
    formal, monkeypatch, layer, text
):
    authorizations = []
    monkeypatch.setattr(
        runtime.PlanningBudget,
        "require_diagnostic",
        lambda self, principal, request: authorizations.append(request.idempotency_key),
    )
    calls = []

    def exchange(self, *, invocation_id, request, credential):
        document = json.loads(request.payload)
        calls.append(document)
        return (
            200,
            json.dumps(
                {
                    "model": formal.document["nativeModelId"],
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": text}],
                        }
                    ],
                }
            ).encode(),
            "test",
            1,
        )

    monkeypatch.setattr(runtime.OpenAIResponsesDraftTransport, "exchange", exchange)
    client = formal.start()
    body = {"target": sample()["target"], "idempotency_key": "diagnostic"}
    route = "/api/workbench/v1/planning-v2/diagnostics/" + layer
    result = client.post(route, json=body, headers={"x-csrf-token": "test-csrf"})
    assert result.status_code == 201, result.text
    assert result.json()["result"]["result"] == {
        "technical_status": "SUCCEEDED",
        "kind": "DIAGNOSTIC",
        "diagnostic_layer": layer,
        "passed": True,
        "reason": "DIAGNOSTIC_ONLY_NOT_A_BUSINESS_PLAN",
    }
    assert (
        client.post(route, json=body, headers={"x-csrf-token": "test-csrf"}).json()
        == result.json()
    )
    assert len(calls) == 1 and len(authorizations) == 2
    assert calls[0]["store"] is False and calls[0]["background"] is False
    assert calls[0]["max_output_tokens"] == 8192
    assert "proposal" not in result.json()["result"]["result"]
    changed = client.post(
        "/api/workbench/v1/planning-v2/diagnostics/"
        + ("ADAPTER" if layer != "ADAPTER" else "MINIMAL"),
        json=body,
        headers={"x-csrf-token": "test-csrf"},
    )
    assert changed.status_code == 409 and len(calls) == 1


def test_diagnostic_missing_authority_or_csrf_fails_before_provider(
    formal, monkeypatch
):
    def deny(*args):
        raise AuthorityError("PLANNING_DIAGNOSTIC_NOT_AUTHORIZED")

    monkeypatch.setattr(runtime.PlanningBudget, "require_diagnostic", deny)
    client = formal.start()
    body = {"target": sample()["target"], "idempotency_key": "denied"}
    route = "/api/workbench/v1/planning-v2/diagnostics/MINIMAL"
    assert client.post(route, json=body).status_code == 403
    assert (
        client.post(route, json=body, headers={"x-csrf-token": "test-csrf"}).status_code
        == 404
    )
    assert not formal.calls and not formal.invocations.rows


def test_fixed_probe_preserves_configuration_and_rejects_false_positive():
    original = {
        "model": "kimi-k3",
        "max_output_tokens": 8192,
        "reasoning": {"effort": "low"},
        "store": False,
        "background": False,
        "text": {"format": {"strict": True}},
        "input": "private business context",
        "instructions": "planning",
    }
    for layer in ("MINIMAL", "STRUCTURED", "ADAPTER"):
        document = diagnostic_document(original, layer)
        for name in ("model", "max_output_tokens", "reasoning", "store", "background"):
            assert document[name] == original[name]
        assert "private business context" not in json.dumps(document)
    assert original["input"] == "private business context"
    assert not validate_diagnostic("STRUCTURED", '{"ok":1}')
    assert not validate_diagnostic("STRUCTURED", '{"ok":true,"extra":1}')
    assert not validate_diagnostic(
        "ADAPTER", '{"kind":"NEEDS_CLARIFICATION","questions":["x"],"semantics":null}'
    )
    with pytest.raises(ValueError):
        diagnostic_document(original, "CUSTOM")


def test_planning_transport_failure_retains_only_allowlisted_category(
    formal, monkeypatch
):
    from agent_console import responses_deadline

    formal.start()
    monkeypatch.setattr(
        responses_deadline,
        "supervise",
        lambda *a: (
            {
                "text": None,
                "failure": "PROVIDER_OUTCOME_UNKNOWN",
                "measurement": {},
                "transport_failure": {"category": "TIMEOUT"},
            },
            {"stage": "WAIT_HEADERS", "reason": "RESULT_ACCEPTED", "reaped": True},
        ),
    )
    provider = object.__new__(runtime.PlanningResponsesProvider)
    provider.cleanup_failed = False
    provider.isolation_enabled = True
    provider.configuration = provider.transport_profile = None
    result = provider.suggest(None, None, None, {})
    assert result["deadline"] == {
        "stage": "WAIT_HEADERS",
        "reason": "TRANSPORT_FAILURE",
        "reaped": True,
        "exception_category": "TIMEOUT",
    }
    assert result["failure"] == "PROVIDER_OUTCOME_UNKNOWN"
    assert "transport_failure" not in result
