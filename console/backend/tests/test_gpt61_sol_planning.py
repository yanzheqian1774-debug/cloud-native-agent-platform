"""GPT planning compatibility; no external provider or real credential access."""

import json
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console import plan_suggestion_runtime as runtime
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_assistance_bootstrap import _profile
from agent_console.planning_measurement import measurement
from test_openai_responses_draft_adapter import mock_responses as mock_responses
from test_planning_runtime import formal as formal
from test_planning_runtime import send

POLICY = "gpt61-sol-standard-uncached-low.v1"


def configure(formal):
    formal.document.update(nativeModelId="gpt-6.1-sol", planningModelPolicy=POLICY)
    formal.document["budget"].update(
        inputPriceMicrousdPerMillionTokens=2_000_000,
        outputPriceMicrousdPerMillionTokens=10_000_000,
    )
    formal.path.write_text(json.dumps(formal.document))
    return _profile(formal.document, planning=True)[2]


def response():
    return {
        "id": "resp-gpt-test",
        "model": "gpt-6.1-sol",
        "status": "completed",
        "service_tier": "default",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 30,
            "total_tokens": 130,
            "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 12},
        },
    }


@pytest.mark.parametrize("mode", ["valid", "timeout", "wrong-model", "tool", "invalid"])
def test_gpt_formal_path_reasoning_and_unchanged_contract(formal, monkeypatch, mode):
    configure(formal)
    original = runtime.OpenAIResponsesDraftTransport.exchange

    def exchange(self, **kwargs):
        formal.mode = "timeout" if mode == "timeout" else "valid"
        status, body, correlation, latency = original(self, **kwargs)
        obj = json.loads(body)
        obj.update({k: v for k, v in response().items() if k != "output"})
        obj["output"].insert(0, {"type": "reasoning", "summary": []})
        if mode == "wrong-model":
            obj["model"] = "another-model"
        if mode == "tool":
            obj["output"].insert(0, {"type": "function_call"})
        if mode == "invalid":
            obj["output"][-1]["content"][0]["text"] = '{"untrusted":true}'
        return status, json.dumps(obj).encode(), correlation, latency

    monkeypatch.setattr(runtime.OpenAIResponsesDraftTransport, "exchange", exchange)
    client = formal.start()
    first = send(client)
    assert first.status_code == 201, first.text
    assert send(client).json() == first.json()
    assert len(formal.calls) == 1  # Includes UNKNOWN: original key never retries.
    sent = formal.calls[0]
    assert sent["model"] == "gpt-6.1-sol"
    assert sent["reasoning"] == {"effort": "low"}
    assert sent["service_tier"] == "default"
    assert sent["prompt_cache_options"] == {"mode": "explicit", "ttl": "30m"}
    assert sent["text"]["format"]["strict"] is True
    result = first.json()["result"]["result"]
    if mode == "valid":
        assert result["kind"] == "VALID_SUGGESTION"
    elif mode == "timeout":
        assert result["technical_status"] == "OUTCOME_UNKNOWN"
    else:
        assert result["kind"] == "INVALID" or result["technical_status"] == "FAILED"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda r: r.update(service_tier="priority"),
        lambda r: r.pop("service_tier"),
        lambda r: r["usage"].pop("input_tokens_details"),
        lambda r: r["usage"]["input_tokens_details"].update(cached_tokens=10),
        lambda r: r["usage"]["input_tokens_details"].update(cache_write_tokens=1),
        lambda r: r["usage"]["input_tokens_details"].update(cache_write_tokens=True),
        lambda r: r["usage"]["input_tokens_details"].update(
            cache_write_tokens_details={"ttl_12h_tokens": 2}
        ),
        lambda r: r["usage"].update(total_tokens=999),
        lambda r: r.update(model="other"),
    ],
)
def test_unexpected_tier_cache_or_usage_cannot_release_reserve(formal, mutator):
    config = configure(formal)
    obj = response()
    mutator(obj)
    assert not measurement(obj, "req-1", "inv-1", 1, config)["settleable"]


def test_standard_uncached_counts_reasoning_once_and_protocol_is_openai(formal):
    config = configure(formal)
    result = measurement(response(), "req-1", "inv-1", 1, config)
    assert result["settleable"]
    assert result["usage"]["output_tokens"] == 30
    assert result["usage"]["reasoning_tokens"] == 12
    p = runtime.PlanningResponsesProvider(config, NS(), NS())
    assert p.protocol == "OPENAI_RESPONSES_V1"
    assert p.gpt61_policy
    with pytest.raises(DraftAssistanceError):
        replace(config, native_model_id="gpt-other")


def test_unknown_policy_and_gpt_policy_on_kimi_fail_closed(formal):
    configure(formal)
    formal.document["planningModelPolicy"] = "unknown"
    with pytest.raises(DraftAssistanceError):
        _profile(formal.document, planning=True)
    formal.document["providerProtocol"] = "KIMI_RESPONSES_V1"
    with pytest.raises(DraftAssistanceError):
        _profile(formal.document, planning=True)


def test_legacy_openai_configuration_digest_is_unchanged(formal):
    from dataclasses import asdict

    from agent_console.task_delegation import configured_limits, digest

    profile, _, config, _ = _profile(formal.document, planning=True)
    old_provider = asdict(config)
    old_provider.pop("planning_model_policy")
    owner = NS(ledger_id="same", call_cap=8, total_cost_cap_microusd=10000000)
    limits = configured_limits(profile, config, owner, planning=True)
    assert limits["configuration_digest"] == digest(
        {"profile": asdict(profile), "provider": old_provider}
    )


def test_gpt_requires_explicit_policy_even_with_known_model(formal):
    formal.document["nativeModelId"] = "gpt-6.1-sol"
    with pytest.raises(DraftAssistanceError, match="PLANNING_PROFILE_INVALID"):
        _profile(formal.document, planning=True)


@pytest.mark.parametrize("http_status", [200, 401, 429])
def test_spawned_gpt_job_over_real_local_https(mock_responses, http_status):
    from agent_console.plan_suggestion_invocation import PlanningRequest
    from agent_console.plan_suggestion_policy import POLICY_DIGEST
    from test_openai_responses_draft_adapter import (
        _credential_file,
        _real_runtime_document,
        _ResponsesHandler,
    )
    from test_plan_suggestion_v2 import sample

    server, cert, tmp_path = mock_responses
    _credential_file(tmp_path)
    document = _real_runtime_document(server, cert, tmp_path)
    document.update(
        schemaVersion="planning-runtime.v1",
        nativeModelId="gpt-6.1-sol",
        planningModelPolicy=POLICY,
        maximumInputTokens=65536,
        outputSchemaVersion="plan-suggestion-output.v1",
        targetFormatVersion="plan-suggestion-target.v1",
        policyDigest=POLICY_DIGEST,
        realCallsEnabled=True,
    )
    document["budget"]["outputPriceMicrousdPerMillionTokens"] = 10_000_000
    profile, _, config, _ = _profile(
        document, planning=True, allow_local_https_mock=True
    )
    obj = response()
    obj["output"] = [
        {"type": "reasoning", "summary": []},
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": json.dumps(
                        {
                            "kind": "NEEDS_CLARIFICATION",
                            "questions": ["Synthetic date?"],
                        }
                    ),
                }
            ],
        },
    ]
    _ResponsesHandler.response = obj
    _ResponsesHandler.status = http_status
    provider = runtime.PlanningResponsesProvider(
        config, profile, runtime.planning_credentials(config, profile)
    )
    request = PlanningRequest.model_validate(
        {"target": sample()["target"], "idempotency_key": "new-gpt-local"}
    )
    result = provider.suggest(
        request, None, profile, {"planning_context": {"invocation_id": "gpt-local"}}
    )
    assert len(_ResponsesHandler.requests) == 1
    sent = _ResponsesHandler.requests[0]["body"]
    assert sent["model"] == "gpt-6.1-sol"
    assert sent["reasoning"] == {"effort": "low"}
    assert result["deadline"]["reaped"]
    if http_status == 200:
        assert result["failure"] is None
        assert result["measurement"]["settleable"]
    else:
        assert result["failure"] == "PLANNING_PROVIDER_HTTP_REJECTED"
        assert not result["measurement"]["settleable"]


def test_gpt_does_not_coerce_incorrect_input_kinds(formal, monkeypatch):
    from agent_console.plan_suggestion_invocation import PlanningRequest
    from test_planning_contracts import modern

    config = configure(formal)
    transport_profile = _profile(formal.document, planning=True)[0]
    provider = runtime.PlanningResponsesProvider(config, transport_profile, NS())
    semantics = modern(("READ_DATA", "SUMMARIZE", "RENDER_REPORT"))
    semantics["tasks"][-1]["depends_on"] = ["node-0", "node-1"]
    semantics["tasks"][-1]["input_kinds"] = ["SUMMARY"]
    obj = response()
    obj["output"] = [
        {
            "type": "message",
            "content": [
                {
                    "type": "output_text",
                    "text": json.dumps(
                        {"kind": "VALID_SUGGESTION", "semantics": semantics}
                    ),
                }
            ],
        }
    ]
    monkeypatch.setattr(provider.credentials, "resolve", lambda *_: NS(), raising=False)
    monkeypatch.setattr(
        provider.transport,
        "exchange",
        lambda **_: (200, json.dumps(obj).encode(), "req-gpt", 1),
    )
    request = PlanningRequest.model_validate(
        {
            "target": semantics["target"],
            "policy": semantics["policy"],
            "idempotency_key": "input-kind-new",
        }
    )
    result = provider._suggest_once(
        request,
        transport_profile,
        {"planning_context": {"invocation_id": "new-input-kind"}},
    )
    assert result["failure"] == "PLANNING_OUTPUT_SCHEMA_INVALID"
    assert result["text"] is None
    assert result["measurement"]["settleable"]
    assert "PLANNING_OPERATION_INPUT_CONFLICT" in json.dumps(
        result["validation_diagnostic"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"input_price_microusd_per_million_tokens": 0},
        {"output_price_microusd_per_million_tokens": 8_000_000},
        {"maximum_input_tokens": 272_000},
    ],
)
def test_gpt_price_policy_cannot_silently_use_zero_old_or_long_input_rates(
    formal, change
):
    config = configure(formal)
    with pytest.raises(DraftAssistanceError, match="OPENAI_RESPONSES_PROFILE_INVALID"):
        replace(config, **change)
