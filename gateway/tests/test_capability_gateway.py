from copy import deepcopy
from dataclasses import replace

import pytest
from agent_core.representation.v0_2 import PlatformExecutionIdentity
from agent_gateway.capability import (
    Ambiguity,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationResult,
    CapabilityGateway,
    CapabilityIdentity,
    CapabilityRequest,
    CapabilityStatus,
    DecisionReason,
    ProviderIdentity,
    ProviderNativeRequestId,
    ProviderResponse,
    RestProvider,
    RestProviderConfiguration,
    TransportAmbiguityError,
    TransportTimeoutError,
)
from agent_gateway.capability.models import CapabilityModelError


class StaticAuthorization:
    def __init__(self, result):
        self.result = result

    def decide(self, capability_request, context):
        return self.result


class ScriptedTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def send(self, capability_request):
        self.calls.append(capability_request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def decision(value=AuthorizationDecision.ALLOW, reason="POLICY_MATCH"):
    return AuthorizationResult((value,), DecisionReason(reason))


@pytest.fixture
def execution_identity():
    return PlatformExecutionIdentity("platform-execution-001")


@pytest.fixture
def capability_request(execution_identity):
    return CapabilityRequest(
        CapabilityIdentity("crm.customer.lookup"),
        "lookup",
        execution_identity,
        {"customer": "C-42"},
    )


@pytest.fixture
def context(execution_identity):
    return AuthorizationContext("employee-7", "tenant-1", execution_identity)


def make_provider(result):
    transport = ScriptedTransport(result)
    provider = RestProvider(
        RestProviderConfiguration(
            ProviderIdentity("provider.synthetic.rest"),
            "https://synthetic.invalid/capabilities/customer-lookup",
        ),
        transport,
    )
    return provider, transport


def execute(result, capability_request, context, authorization=None):
    provider, transport = make_provider(result)
    gateway = CapabilityGateway(
        StaticAuthorization(authorization or decision()), provider
    )
    return gateway.execute(capability_request, context), transport


def test_allow_invokes_provider_exactly_once_and_preserves_identities(
    capability_request, context
):
    response = ProviderResponse(
        200, {"name": "Ada"}, ProviderNativeRequestId("native-capability_request-9")
    )
    outcome, transport = execute(response, capability_request, context)

    assert len(transport.calls) == 1
    assert outcome.status is CapabilityStatus.SUCCEEDED
    assert outcome.execution_identity is capability_request.execution_identity
    assert outcome.capability is capability_request.capability
    assert outcome.provider == ProviderIdentity("provider.synthetic.rest")
    assert outcome.native_request_id == ProviderNativeRequestId(
        "native-capability_request-9"
    )
    assert (
        transport.calls[0].execution_identity is capability_request.execution_identity
    )


def test_deny_returns_normalized_denial_before_provider_invocation(
    capability_request, context
):
    outcome, transport = execute(
        ProviderResponse(200, {}),
        capability_request,
        context,
        decision(AuthorizationDecision.DENY),
    )

    assert transport.calls == []
    assert outcome.status is CapabilityStatus.DENIED
    assert outcome.authorization is AuthorizationDecision.DENY
    assert outcome.invocation.attempts == 0
    assert outcome.native_request_id is None
    assert outcome.diagnostic == "DENIED_POLICY_MATCH"


@pytest.mark.parametrize(
    ("authorization", "diagnostic"),
    [
        (None, "AUTHORIZATION_DECISION_MISSING"),
        (decision("MAYBE"), "AUTHORIZATION_DECISION_UNKNOWN"),
        (decision("ALLOW"), "AUTHORIZATION_DECISION_UNKNOWN"),
        (
            AuthorizationResult(
                (AuthorizationDecision.ALLOW, AuthorizationDecision.DENY),
                DecisionReason("CONFLICT"),
            ),
            "AUTHORIZATION_DECISION_AMBIGUOUS",
        ),
        (
            AuthorizationResult((), DecisionReason("EMPTY")),
            "AUTHORIZATION_DECISION_AMBIGUOUS",
        ),
    ],
)
def test_invalid_authorization_fails_closed(
    capability_request, context, authorization, diagnostic
):
    provider, transport = make_provider(ProviderResponse(200, {}))
    outcome = CapabilityGateway(StaticAuthorization(authorization), provider).execute(
        capability_request, context
    )
    assert transport.calls == []
    assert outcome.status is CapabilityStatus.DENIED
    assert outcome.diagnostic == diagnostic


def test_malformed_or_mismatched_authorization_context_fails_closed(
    capability_request, context
):
    provider, transport = make_provider(ProviderResponse(200, {}))
    gateway = CapabilityGateway(StaticAuthorization(decision()), provider)

    malformed = gateway.execute(capability_request, object())
    mismatched = gateway.execute(
        capability_request,
        replace(context, execution_identity=PlatformExecutionIdentity("other")),
    )

    assert transport.calls == []
    assert malformed.diagnostic == "AUTHORIZATION_CONTEXT_INVALID"
    assert mismatched.diagnostic == "AUTHORIZATION_CONTEXT_INVALID"


def test_authorization_exception_is_redacted_and_fails_closed(
    capability_request, context
):
    class ExplodingAuthorization:
        def decide(self, capability_request, context):
            raise RuntimeError("Bearer highly-sensitive-token")

    provider, transport = make_provider(ProviderResponse(200, {}))
    outcome = CapabilityGateway(ExplodingAuthorization(), provider).execute(
        capability_request, context
    )

    assert transport.calls == []
    assert outcome.diagnostic == "AUTHORIZATION_DECISION_UNAVAILABLE"
    assert "sensitive" not in repr(outcome)


@pytest.mark.parametrize(
    ("status_code", "expected_status", "diagnostic"),
    [
        (204, CapabilityStatus.SUCCEEDED, "CAPABILITY_INVOCATION_SUCCEEDED"),
        (404, CapabilityStatus.FAILED, "PROVIDER_CLIENT_ERROR"),
        (503, CapabilityStatus.FAILED, "PROVIDER_SERVER_ERROR"),
        (302, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"),
    ],
)
def test_rest_status_normalization(
    capability_request, context, status_code, expected_status, diagnostic
):
    outcome, transport = execute(
        ProviderResponse(status_code, {}), capability_request, context
    )
    assert len(transport.calls) == 1
    assert outcome.status is expected_status
    assert outcome.diagnostic == diagnostic


@pytest.mark.parametrize(
    ("response", "diagnostic"),
    [
        (object(), "PROVIDER_RESPONSE_MALFORMED"),
        (ProviderResponse(200, ["not", "a", "mapping"]), "PROVIDER_RESPONSE_MALFORMED"),
        (
            ProviderResponse(200, {}, content_type="text/plain"),
            "PROVIDER_CONTENT_UNSUPPORTED",
        ),
    ],
)
def test_malformed_or_unsupported_response_is_normalized(
    capability_request, context, response, diagnostic
):
    outcome, transport = execute(response, capability_request, context)
    assert len(transport.calls) == 1
    assert outcome.status is CapabilityStatus.FAILED
    assert outcome.diagnostic == diagnostic


@pytest.mark.parametrize(
    ("error", "ambiguity", "diagnostic"),
    [
        (
            TransportTimeoutError("token=do-not-leak"),
            Ambiguity.TIMEOUT_EFFECT_UNKNOWN,
            "PROVIDER_TIMEOUT_EFFECT_UNKNOWN",
        ),
        (
            TransportAmbiguityError("password=do-not-leak"),
            Ambiguity.TRANSPORT_EFFECT_UNKNOWN,
            "PROVIDER_TRANSPORT_EFFECT_UNKNOWN",
        ),
    ],
)
def test_ambiguous_transport_records_one_attempt_without_retry(
    capability_request, context, error, ambiguity, diagnostic
):
    outcome, transport = execute(error, capability_request, context)
    assert len(transport.calls) == 1
    assert outcome.status is CapabilityStatus.INDETERMINATE
    assert outcome.invocation.attempts == 1
    assert outcome.ambiguity is ambiguity
    assert outcome.retry_safe is False
    assert outcome.diagnostic == diagnostic
    assert "do-not-leak" not in repr(outcome)


def test_provider_exception_is_redacted_without_fallback_or_retry(
    capability_request, context
):
    outcome, transport = execute(
        RuntimeError("api_key=do-not-leak"), capability_request, context
    )
    assert len(transport.calls) == 1
    assert outcome.diagnostic == "PROVIDER_TRANSPORT_FAILED_REDACTED"
    assert "do-not-leak" not in repr(outcome)


def test_provider_native_id_cannot_substitute_for_platform_identity(
    capability_request, context
):
    response = ProviderResponse(
        200,
        {},
        ProviderNativeRequestId(capability_request.execution_identity.value),
    )
    outcome, transport = execute(response, capability_request, context)
    assert len(transport.calls) == 1
    assert outcome.execution_identity is capability_request.execution_identity
    assert outcome.native_request_id is None
    assert outcome.diagnostic == "PROVIDER_NATIVE_ID_INVALID"


@pytest.mark.parametrize("method", ["CONNECT", "TRACE", "get", ""])
def test_invalid_method_fails_closed_before_transport_construction(method):
    with pytest.raises(CapabilityModelError, match="method"):
        RestProviderConfiguration(
            ProviderIdentity("provider.synthetic.rest"),
            "https://synthetic.invalid/lookup",
            method=method,
        )


@pytest.mark.parametrize(
    "target",
    [
        "http://synthetic.invalid/lookup",
        "file:///etc/passwd",
        "https://user:password@synthetic.invalid/lookup",
        "synthetic.invalid/lookup",
    ],
)
def test_unsupported_target_fails_closed(target):
    with pytest.raises(CapabilityModelError, match="authorized HTTPS"):
        RestProviderConfiguration(ProviderIdentity("provider.synthetic.rest"), target)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"headers": {"Authorization": "Bearer do-not-leak"}},
        {"headers": {"X-Api-Key": "do-not-leak"}},
        {"headers": {"X-Custom": "Bearer do-not-leak-123"}},
    ],
)
def test_secret_like_serializable_configuration_is_rejected(kwargs):
    with pytest.raises(CapabilityModelError, match="secret-like"):
        RestProviderConfiguration(
            ProviderIdentity("provider.synthetic.rest"),
            "https://synthetic.invalid/lookup",
            **kwargs,
        )


def test_secret_like_request_data_is_rejected(execution_identity):
    with pytest.raises(CapabilityModelError, match="secret-like"):
        CapabilityRequest(
            CapabilityIdentity("crm.customer.lookup"),
            "lookup",
            execution_identity,
            {"access_token": "do-not-leak"},
        )

    with pytest.raises(CapabilityModelError, match="secret-like"):
        CapabilityRequest(
            CapabilityIdentity("crm.customer.lookup"),
            "lookup",
            execution_identity,
            {"nested": {"password": "do-not-leak"}},
        )


def test_response_size_boundary_fails_closed(capability_request, context):
    outcome, transport = execute(
        ProviderResponse(200, {"result": "x" * 70_000}), capability_request, context
    )
    assert len(transport.calls) == 1
    assert outcome.diagnostic == "PROVIDER_RESPONSE_MALFORMED"
    assert outcome.invocation.result is None


def test_caller_input_is_not_mutated(capability_request, context):
    arguments = {"customer": {"id": "C-42"}}
    original = deepcopy(arguments)
    local_request = CapabilityRequest(
        capability_request.capability,
        capability_request.operation,
        capability_request.execution_identity,
        arguments,
    )
    outcome, transport = execute(
        ProviderResponse(200, {"ok": True}), local_request, context
    )

    assert outcome.status is CapabilityStatus.SUCCEEDED
    assert arguments == original
    assert transport.calls[0].body["arguments"] == original


def test_provider_cannot_override_allow_decision(capability_request, context):
    outcome, _ = execute(
        ProviderResponse(200, {"provider_decision": "DENY", "ok": True}),
        capability_request,
        context,
    )
    assert outcome.authorization is AuthorizationDecision.ALLOW
    assert outcome.status is CapabilityStatus.SUCCEEDED


def test_provider_outcome_cannot_override_allow_decision(capability_request, context):
    legitimate, _ = make_provider(ProviderResponse(200, {"ok": True}))
    denied = replace(
        legitimate.invoke(capability_request),
        authorization=AuthorizationDecision.DENY,
    )

    class OverridingProvider:
        identity = legitimate.identity

        def invoke(self, capability_request):
            return denied

    outcome = CapabilityGateway(
        StaticAuthorization(decision()), OverridingProvider()
    ).execute(capability_request, context)
    assert outcome.authorization is AuthorizationDecision.ALLOW
    assert outcome.status is CapabilityStatus.FAILED
    assert outcome.diagnostic == "PROVIDER_EVIDENCE_INVALID"
