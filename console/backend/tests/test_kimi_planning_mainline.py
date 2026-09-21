"""Kimi-specific formal app assembly and local TLS evidence, never a real provider."""

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import test_planning_responses_boundaries as boundary
import test_understanding_usage_closure as understanding
from agent_console import plan_suggestion_runtime as runtime
from test_openai_responses_draft_adapter import mock_responses as mock_responses
from test_plan_suggestion_v2 import repository as repository
from test_planning_responses_boundaries import endpoint as endpoint
from test_planning_runtime import formal as formal
from test_planning_runtime import send
from test_understanding_usage_closure import assembled as assembled


@pytest.fixture
def kimi_network(formal, endpoint, monkeypatch, request):
    monkeypatch.setattr(
        runtime,
        "build_planning_runtime",
        lambda **kw: boundary.REAL_BUILD(**kw, allow_local_https_mock=True),
    )
    monkeypatch.setattr(
        runtime.PlanningResponsesProvider, "__init__", boundary.REAL_PROVIDER_INIT
    )
    document = formal.document
    document.update(
        executionClass="LOCAL_HTTPS_MOCK",
        responsesUrl=endpoint.url,
        tls={"caFile": str(endpoint.cert)},
        connectTimeoutSeconds=2,
        readTimeoutSeconds=5,
        totalTimeoutSeconds=5,
        providerProtocol="KIMI_RESPONSES_V1",
        reasoningEffort="low",
        adapter={"id": "kimi-responses-draft", "revision": "v1"},
    )
    document.update(getattr(request, "param", {}))
    secret = Path(document["credential"]["file"])
    secret.write_text("synthetic-kimi-planning-only")
    secret.chmod(0o600)
    formal.path.write_text(json.dumps(document))
    client = formal.start()
    try:
        yield NS(client=client, state=formal, endpoint=endpoint)
    finally:
        endpoint.release.set()
        client.close()


def test_kimi_formal_https_usage_and_request(kimi_network):
    n = kimi_network
    response = send(n.client)
    assert boundary.result(response)["kind"] == "NEEDS_CLARIFICATION"
    m = boundary.receipt(n, response)["measurement"]
    assert m["settleable"]
    assert m["metering"] == "KIMI_RESPONSES_V1_TOTALS_INCLUDE_DETAILS"
    assert m["provider_request_id"] == "req-local-323"
    assert m["provider_response_id"] == "resp-local-323"
    document = n.endpoint.documents[0]
    assert document["reasoning"] == {"effort": "low"}
    assert document["text"]["format"]["name"] == "plan_suggestion_output"
    assert document["text"]["format"]["strict"] is True
    assert "tools" not in document and "truncation" not in document
    assert n.endpoint.requests == 1


@pytest.mark.parametrize(
    "mode,status,kind",
    [
        ("invalid-json", "FAILED", None),
        ("invalid-inner", "SUCCEEDED", "INVALID"),
        ("oversized", "FAILED", None),
    ],
)
def test_kimi_invalid_outputs(kimi_network, mode, status, kind):
    boundary.test_local_https_outputs_and_metering_are_independent(
        kimi_network, mode, status, kind
    )


@pytest.mark.parametrize("mode", ["headers", "body", "drip"])
def test_kimi_deadlines(kimi_network, mode, record_property):
    boundary.test_actual_local_https_deadline_reaps_and_replay_never_retries(
        kimi_network, mode, record_property
    )


def test_kimi_cancel(kimi_network):
    boundary.test_client_cancellation_reaps_and_persists_unknown(kimi_network)


def test_kimi_denial(kimi_network, monkeypatch):
    boundary.test_permission_denial_starts_no_worker_and_zero_network(
        kimi_network, monkeypatch
    )


def test_kimi_cleanup_failure(kimi_network, monkeypatch):
    boundary.test_cleanup_failure_blocks_subsequent_dispatch(kimi_network, monkeypatch)


@pytest.mark.parametrize(
    "phase", ["DNS", "TCP", "TLS", "SEND_REQUEST", "VALIDATE_RESPONSE", "CLOSE"]
)
@pytest.mark.parametrize(
    "kimi_network",
    [{"totalTimeoutSeconds": 1, "readTimeoutSeconds": 1, "connectTimeoutSeconds": 1}],
    indirect=True,
)
def test_kimi_phase_substitutes(kimi_network, phase, monkeypatch, record_property):
    boundary.test_formal_worker_phase_substitutes_are_bounded(
        kimi_network, monkeypatch, phase, record_property
    )


@pytest.mark.parametrize("assembled", ["kimi"], indirect=True)
@pytest.mark.parametrize(
    "usage,settled",
    [
        ({"input_tokens": 50, "output_tokens": 20, "total_tokens": 70}, True),
        (None, False),
        ({"input_tokens": 50}, False),
        ({"input_tokens": 50, "output_tokens": 20, "total_tokens": 71}, False),
    ],
)
def test_kimi_understanding_pg(assembled, usage, settled, record_property):
    understanding.test_formal_usage_identity_persistence_and_independent_disclosure(
        assembled, usage, settled, record_property
    )


@pytest.mark.parametrize("assembled", ["kimi"], indirect=True)
def test_kimi_illegal_business_still_settles(assembled):
    understanding.test_illegal_business_output_still_settles_reliable_usage(assembled)


@pytest.mark.parametrize("assembled", ["kimi"], indirect=True)
def test_kimi_settlement_repair(assembled, monkeypatch):
    understanding.test_settlement_failure_restart_and_concurrent_repair_never_redispatches(
        assembled, monkeypatch
    )


@pytest.mark.parametrize("assembled", ["kimi"], indirect=True)
def test_kimi_understanding_v2(assembled):
    understanding.test_v2_formal_composition_preserves_usage_and_policy_context(
        assembled
    )


@pytest.mark.parametrize(
    "cached,written,reliable",
    [(7, 12, True), (7, 24, False), (7, -1, False), (7, True, False)],
)
def test_kimi_cache_categories_are_disjoint(cached, written, reliable):
    from agent_console.planning_measurement import measurement

    value = measurement(
        {
            "id": "r",
            "model": "kimi-controlled",
            "status": "completed",
            "usage": {
                "input_tokens": 30,
                "output_tokens": 10,
                "input_tokens_details": {
                    "cached_tokens": cached,
                    "cache_write_tokens": written,
                },
            },
        },
        "req",
        "local",
        1,
        NS(
            native_model_id="kimi-controlled",
            maximum_input_tokens=100,
            maximum_output_tokens=100,
        ),
        protocol="KIMI_RESPONSES_V1",
    )
    assert value["settleable"] is reliable
    assert value["usage"]["input_tokens"] == 30
    assert "cache_write_tokens" in value["usage"]
