import json
from copy import deepcopy
from pathlib import Path

import pytest
from capability_fixture import (
    AuthorizationContext,
    CapabilityRequest,
    ProviderResponse,
    ScriptedRestProvider,
    TransportAmbiguity,
    TransportTimeout,
    execute,
    frozen_arguments,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def request() -> CapabilityRequest:
    data = load("capability-request.json")
    data["arguments"] = frozen_arguments(data["arguments"])
    return CapabilityRequest(**data)


def authorization(name: str = "allow", **overrides) -> AuthorizationContext:
    values = load("authorization-contexts.json")[name]
    values.update(overrides)
    return AuthorizationContext(**values)


def response(name: str) -> ProviderResponse:
    return ProviderResponse(**load("rest-responses.json")[name])


def test_allow_invokes_provider_exactly_once_and_normalizes_success() -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    outcome = execute(request(), authorization(), provider)
    assert provider.call_count == 1
    assert outcome.status == "SUCCEEDED"
    assert outcome.reason == "CAPABILITY_INVOCATION_SUCCEEDED"
    assert outcome.result == {"customer_state": "active", "source": "synthetic"}
    assert provider.requests == [
        {
            "capability_id": "capability.synthetic.customer-lookup",
            "operation": "lookup",
            "platform_execution_identity": "pei-synthetic-qi-1042-attempt-1",
            "arguments": {"customer_reference": "customer-synthetic-1042"},
        }
    ]


def test_deny_occurs_before_provider_invocation() -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    outcome = execute(request(), authorization("deny"), provider)
    assert provider.call_count == 0
    assert not outcome.provider_invoked
    assert outcome.reason == "AUTHORIZATION_DENIED"


@pytest.mark.parametrize(
    ("context", "reason"),
    [
        (None, "AUTHORIZATION_DECISION_MISSING"),
        (authorization(decision=None), "AUTHORIZATION_DECISION_MISSING"),
        (authorization(decision="ALLOW_OR_DENY"), "AUTHORIZATION_DECISION_AMBIGUOUS"),
        (
            authorization(decision=["ALLOW", "DENY"]),
            "AUTHORIZATION_DECISION_AMBIGUOUS",
        ),
        (authorization(subject_id=""), "AUTHORIZATION_CONTEXT_MALFORMED"),
        (
            authorization(platform_execution_identity=""),
            "AUTHORIZATION_CONTEXT_MALFORMED",
        ),
        (
            authorization(platform_execution_identity="provider-native-identity"),
            "AUTHORIZATION_CONTEXT_IDENTITY_MISMATCH",
        ),
    ],
)
def test_invalid_authorization_fails_closed_before_invocation(context, reason) -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    outcome = execute(request(), context, provider)
    assert provider.call_count == 0
    assert outcome.status == "DENIED" and outcome.reason == reason


@pytest.mark.parametrize(
    ("request_overrides", "provider_id", "reason"),
    [
        (
            {"capability_id": ""},
            "provider.synthetic.rest",
            "CAPABILITY_IDENTITY_MISSING",
        ),
        (
            {"platform_execution_identity": ""},
            "provider.synthetic.rest",
            "PLATFORM_EXECUTION_IDENTITY_MISSING",
        ),
        ({}, "provider.untrusted.target", "PROVIDER_TARGET_INVALID"),
        (
            {"arguments": ["not", "a", "mapping"]},
            "provider.synthetic.rest",
            "CAPABILITY_REQUEST_MALFORMED",
        ),
        (
            {"arguments": {1: "non-string-key"}},
            "provider.synthetic.rest",
            "CAPABILITY_REQUEST_MALFORMED",
        ),
        (
            {"operation": "delete_everything"},
            "provider.synthetic.rest",
            "CAPABILITY_OPERATION_UNSUPPORTED",
        ),
    ],
)
def test_invalid_request_or_provider_fails_closed_before_invocation(
    request_overrides, provider_id, reason
) -> None:
    values = {
        "capability_id": "capability.synthetic.customer-lookup",
        "operation": "lookup",
        "platform_execution_identity": "pei-synthetic-qi-1042-attempt-1",
        "arguments": frozen_arguments({"customer_reference": "synthetic-1042"}),
    }
    values.update(request_overrides)
    provider = ScriptedRestProvider(provider_id, [response("success")])
    outcome = execute(CapabilityRequest(**values), authorization(), provider)
    assert provider.call_count == 0
    assert not outcome.provider_invoked
    assert (outcome.status, outcome.reason) == ("REJECTED", reason)


@pytest.mark.parametrize(
    ("fixture_name", "status", "reason"),
    [
        ("client_error", "FAILED", "PROVIDER_CLIENT_ERROR"),
        ("server_error", "FAILED", "PROVIDER_SERVER_ERROR"),
        ("malformed", "FAILED", "PROVIDER_RESPONSE_MALFORMED"),
    ],
)
def test_rest_responses_normalize_deterministically(
    fixture_name, status, reason
) -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [response(fixture_name)])
    outcome = execute(request(), authorization(), provider)
    assert provider.call_count == 1
    assert (outcome.status, outcome.reason) == (status, reason)


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (TransportTimeout("raw-sensitive-detail-a"), "PROVIDER_TIMEOUT_EFFECT_UNKNOWN"),
        (
            TransportAmbiguity("raw-sensitive-detail-b"),
            "PROVIDER_TRANSPORT_EFFECT_UNKNOWN",
        ),
    ],
)
def test_transport_failure_is_ambiguous_and_never_implies_safe_retry(
    failure, reason
) -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [failure])
    outcome = execute(request(), authorization(), provider)
    assert provider.call_count == 1
    assert outcome.status == "INDETERMINATE"
    assert outcome.reason == reason
    assert outcome.transport_ambiguous and not outcome.retry_safe
    assert "sensitive" not in outcome.reason.lower()


def test_platform_capability_and_provider_identities_remain_distinct() -> None:
    provider = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    outcome = execute(request(), authorization(), provider)
    assert outcome.platform_execution_identity == "pei-synthetic-qi-1042-attempt-1"
    assert outcome.capability_id == "capability.synthetic.customer-lookup"
    assert outcome.capability_provider_id == "provider.synthetic.rest"
    assert outcome.provider_request_id == "provider-request-synthetic-001"
    assert (
        len(
            {
                outcome.platform_execution_identity,
                outcome.capability_id,
                outcome.capability_provider_id,
                outcome.provider_request_id,
            }
        )
        == 4
    )


def test_provider_or_native_id_cannot_replace_platform_identity() -> None:
    provider_response = response("success")
    provider = ScriptedRestProvider("provider.synthetic.rest", [provider_response])
    outcome = execute(request(), authorization(), provider)
    assert outcome.platform_execution_identity == request().platform_execution_identity
    assert outcome.platform_execution_identity != provider_response.provider_request_id
    assert provider.requests[0]["platform_execution_identity"] == (
        request().platform_execution_identity
    )


def test_caller_owned_fixtures_are_not_mutated() -> None:
    request_data = load("capability-request.json")
    original_request = deepcopy(request_data)
    provider_body = load("rest-responses.json")["success"]["body"]
    original_body = deepcopy(provider_body)
    req = CapabilityRequest(
        capability_id=request_data["capability_id"],
        operation=request_data["operation"],
        platform_execution_identity=request_data["platform_execution_identity"],
        arguments=frozen_arguments(request_data["arguments"]),
    )
    provider = ScriptedRestProvider(
        "provider.synthetic.rest",
        [ProviderResponse(200, provider_body, "provider-request-synthetic-001")],
    )
    authorization_context = authorization()
    original_authorization = deepcopy(authorization_context)
    outcome = execute(req, authorization_context, provider)
    outcome.result["customer_state"] = "locally-modified"
    assert request_data == original_request
    assert authorization_context == original_authorization
    assert provider_body == original_body


def test_fixture_state_is_isolated_and_has_no_global_counter() -> None:
    first = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    second = ScriptedRestProvider("provider.synthetic.rest", [response("success")])
    execute(request(), authorization(), first)
    assert first.call_count == 1
    assert second.call_count == 0 and second.requests == []
    execute(request(), authorization(), second)
    assert first.call_count == second.call_count == 1


def test_production_python_does_not_import_spike_module() -> None:
    repository = Path(__file__).parents[3]
    production_roots = (
        repository / "core" / "src",
        repository / "operator" / "src",
        repository / "runtime" / "src",
        repository / "gateway",
        repository / "console" / "backend" / "src",
    )
    offenders = [
        str(path.relative_to(repository))
        for root in production_roots
        if root.exists()
        for path in root.rglob("*.py")
        if "capability_fixture" in path.read_text()
    ]
    assert offenders == []


def test_diagnostic_reasons_are_stable_redacted_codes() -> None:
    provider = ScriptedRestProvider(
        "provider.synthetic.rest", [TransportTimeout("raw-sensitive-detail-a")]
    )
    first = execute(request(), authorization(), provider)
    second_provider = ScriptedRestProvider(
        "provider.synthetic.rest", [TransportTimeout("raw-sensitive-detail-b")]
    )
    second = execute(request(), authorization(), second_provider)
    assert first.reason == second.reason == "PROVIDER_TIMEOUT_EFFECT_UNKNOWN"
    assert "sensitive" not in first.reason.lower()
