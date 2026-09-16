from __future__ import annotations

import json
import ssl
import subprocess
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    DraftAssistanceProfileRevision,
    DraftResultKind,
    DraftScope,
    ObservationState,
    draft_invocation_target,
)
from agent_console.draft_assistance_bootstrap import (
    GovernedProfileModelResolver,
)
from agent_console.draft_assistance_bootstrap import _profile as parse_runtime_profile
from agent_console.model_binding_resolution import (
    ExactModelBinding,
    ExactModelUse,
    ModelUseAction,
)
from agent_console.model_governance import (
    ExactProviderConfiguration,
    InvocationLimit,
    ModelConnectionProfileRevision,
    ModelDefinition,
    ModelEligibility,
    ModelEligibilityState,
    ModelEndpointRevision,
    ModelLifecycleHighWater,
    ModelProviderRevision,
    ModelRevision,
    ModelScope,
    SecretReference,
)
from agent_console.openai_responses_draft_adapter import (
    ADAPTER_ID,
    ADAPTER_REVISION,
    OUTPUT_SCHEMA,
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesConfiguration,
    OpenAIResponsesDraftTransport,
)

DIGEST = "a" * 64


class _ResponsesHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, object]]] = []
    status = 200
    response: object = {}
    disconnect = False

    def do_POST(self):
        body = self.rfile.read(int(self.headers["content-length"]))
        type(self).requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("authorization"),
                "body": json.loads(body),
            }
        )
        if type(self).disconnect:
            self.connection.shutdown(2)
            self.connection.close()
            return
        payload = json.dumps(type(self).response).encode()
        self.send_response(type(self).status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.send_header("x-request-id", "req_mock_319")
        if 300 <= type(self).status < 400:
            self.send_header("location", "https://redirect.invalid/v1/responses")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


@pytest.fixture
def mock_responses(tmp_path):
    cert = tmp_path / "server.crt"
    key = tmp_path / "server.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    _ResponsesHandler.requests = []
    _ResponsesHandler.status = 200
    _ResponsesHandler.response = {}
    _ResponsesHandler.disconnect = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ResponsesHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, cert, tmp_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _profile() -> DraftAssistanceProfileRevision:
    return DraftAssistanceProfileRevision(
        "draft-profile-real-1",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        ExactModelBinding("model-1", "model-revision-1", DIGEST),
        "provider-1",
        "provider-revision-1",
        DIGEST,
        "endpoint-1",
        "endpoint-revision-1",
        DIGEST,
        "connection-profile-1",
        "connection-profile-revision-1",
        DIGEST,
        ADAPTER_ID,
        ADAPTER_REVISION,
        maximum_output_tokens=128,
        total_timeout_seconds=5,
    )


def _configuration(server, cert, credential_file):
    return OpenAIResponsesConfiguration(
        "LOCAL_HTTPS_MOCK",
        f"https://127.0.0.1:{server.server_port}/v1/responses",
        "mock-model-319",
        "secret-reference:mock-319",
        "v1",
        "exact-file-resolver",
        "v1",
        credential_file,
        2,
        3,
        5,
        10_000,
        128,
        64_000,
        2_000_000,
        8_000_000,
        cert,
    )


def _credential_file(tmp_path):
    value = tmp_path / "credential"
    value.write_text("fake-provider-key-319")
    value.chmod(0o600)
    return value


def _completed(result):
    return {
        "id": "resp_mock_319",
        "status": "completed",
        "model": "mock-model-319",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(result)}],
            }
        ],
        "usage": {"input_tokens": 50, "output_tokens": 20},
    }


def test_governed_real_profile_resolves_provider_configuration_with_owner_scope():
    now = datetime(2029, 1, 1, tzinfo=UTC)
    scope = ModelScope("tenant-a", "quality")
    definition = ModelDefinition(
        scope, "model-1", "team:draft-assistance", "human:owner", now
    )
    provider = ModelProviderRevision(
        scope,
        "provider-1",
        "provider-revision-1",
        ADAPTER_ID,
        ADAPTER_REVISION,
        ("CHAT",),
        "human:owner",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        "endpoint-1",
        "endpoint-revision-1",
        "https://127.0.0.1:19445/v1/responses",
        "test-only",
        ("HTTPS", "NO_REDIRECT"),
        "human:owner",
        now,
    )
    connection = ModelConnectionProfileRevision(
        scope,
        "connection-profile-1",
        "connection-profile-revision-1",
        endpoint.identity,
        SecretReference("secret-reference:mock-319", "v1"),
        2,
        5,
        "human:owner",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        "model-revision-1",
        1,
        None,
        provider.identity,
        endpoint.identity,
        connection.identity,
        "mock-model-319",
        ("JSON_SCHEMA",),
        ("CHAT", "STRUCTURED_OUTPUT"),
        (
            InvocationLimit("max_input_tokens", 10_000, "TOKEN"),
            InvocationLimit("max_output_tokens", 128, "TOKEN"),
        ),
        "human:owner",
        now,
    )
    eligibility = ModelEligibility(
        scope,
        revision.identity,
        ModelEligibilityState.PUBLISHED_ENABLED,
        ModelLifecycleHighWater(3, "model-fact-3", DIGEST),
    )
    exact_configuration = ExactProviderConfiguration(
        scope, provider, endpoint, connection
    )

    class Repository:
        def __init__(self):
            self.scopes = []

        def _record_scope(self, value):
            assert isinstance(value, ModelScope)
            self.scopes.append(value)

        def get(self, owner_scope, model_id):
            self._record_scope(owner_scope)
            assert model_id == definition.model_id
            return definition

        def get_revision(self, owner_scope, model_id, revision_id):
            self._record_scope(owner_scope)
            assert (model_id, revision_id) == (
                revision.model_id,
                revision.revision_id,
            )
            return revision

        def read_lifecycle(self, owner_scope, model_id, revision_id):
            self._record_scope(owner_scope)
            assert (model_id, revision_id) == (
                revision.model_id,
                revision.revision_id,
            )
            return eligibility

        def resolve_exact(
            self, owner_scope, provider_identity, endpoint_identity, profile_identity
        ):
            self._record_scope(owner_scope)
            assert (
                provider_identity,
                endpoint_identity,
                profile_identity,
            ) == (provider.identity, endpoint.identity, connection.identity)
            return exact_configuration

    repository = Repository()
    profile = DraftAssistanceProfileRevision(
        "draft-profile-real-1",
        DIGEST,
        DraftScope(scope.namespace, scope.security_domain),
        ExactModelBinding(revision.model_id, revision.revision_id, revision.digest),
        provider.provider_id,
        provider.revision_id,
        provider.digest,
        endpoint.endpoint_id,
        endpoint.revision_id,
        endpoint.digest,
        connection.profile_id,
        connection.revision_id,
        connection.digest,
        ADAPTER_ID,
        ADAPTER_REVISION,
        maximum_output_tokens=128,
        total_timeout_seconds=5,
    )
    configuration = OpenAIResponsesConfiguration(
        "LOCAL_HTTPS_MOCK",
        endpoint.normalized_address_reference,
        revision.provider_native_model_id,
        connection.secret_reference.reference_id,
        connection.secret_reference.version,
        "exact-file-resolver",
        "v1",
        Path("/tmp/s5-v023-impl-319-fake-provider-key"),
        connection.connect_timeout_seconds,
        3,
        connection.request_timeout_seconds,
        10_000,
        128,
        64_000,
        2_000_000,
        8_000_000,
        Path("/tmp/s5-v023-impl-319-ca.pem"),
    )
    exact_use = ExactModelUse(
        profile.binding,
        ModelUseAction.INVOKE_MODEL,
        draft_invocation_target(
            "context-1", "turn-1", "invocation-1", "snapshot-1", profile.binding
        ),
    )

    resolved = GovernedProfileModelResolver(repository, configuration).resolve_exact(
        profile, exact_use
    )

    assert resolved.binding == profile.binding
    assert len(repository.scopes) == 6
    assert all(value == scope for value in repository.scopes)


def _real_runtime_document(server, cert, tmp_path):
    return {
        "schemaVersion": "draft-assistance-runtime.v1",
        "transportKind": "REAL_PROVIDER",
        "scope": {"namespace": "tenant-a", "securityDomain": "quality"},
        "profileRevisionId": "draft-profile-real-1",
        "profileDigest": DIGEST,
        "model": {"id": "model-1", "revisionId": "model-revision-1", "digest": DIGEST},
        "provider": {
            "id": "provider-1",
            "revisionId": "provider-revision-1",
            "digest": DIGEST,
        },
        "endpoint": {
            "id": "endpoint-1",
            "revisionId": "endpoint-revision-1",
            "digest": DIGEST,
        },
        "connectionProfile": {
            "id": "connection-profile-1",
            "revisionId": "connection-profile-revision-1",
            "digest": DIGEST,
        },
        "adapter": {"id": ADAPTER_ID, "revision": ADAPTER_REVISION},
        "outputSchemaVersion": "problem-draft-assistance-output.v1",
        "targetFormatVersion": "draft-assistance-target.v1",
        "maximumInputBytes": 16_384,
        "maximumOutputTokens": 128,
        "totalTimeoutSeconds": 5,
        "pepperReference": "pepper:draft",
        "pepperVersion": "v1",
        "pepperFile": str(tmp_path / "pepper"),
        "providerProtocol": "OPENAI_RESPONSES_V1",
        "executionClass": "LOCAL_HTTPS_MOCK",
        "responsesUrl": f"https://127.0.0.1:{server.server_port}/v1/responses",
        "nativeModelId": "mock-model-319",
        "maximumInputTokens": 10_000,
        "maximumResponseBytes": 64_000,
        "connectTimeoutSeconds": 2,
        "readTimeoutSeconds": 3,
        "credential": {
            "reference": "secret-reference:mock-319",
            "version": "v1",
            "resolverId": "exact-file-resolver",
            "resolverRevision": "v1",
            "file": str(tmp_path / "credential"),
        },
        "tls": {"caFile": str(cert)},
        "budget": {
            "ledgerId": "s5-v023-impl-319-test",
            "currency": "USD",
            "callCap": 2,
            "totalCostCapMicrousd": 10_000,
            "inputPriceMicrousdPerMillionTokens": 2_000_000,
            "outputPriceMicrousdPerMillionTokens": 8_000_000,
        },
    }


def test_real_adapter_sends_exact_foreground_schema_request_once(mock_responses):
    server, cert, tmp_path = mock_responses
    credential_file = _credential_file(tmp_path)
    configuration = _configuration(server, cert, credential_file)
    resolver = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    transport = OpenAIResponsesDraftTransport(configuration)
    _ResponsesHandler.response = _completed(
        {
            "kind": "DRAFT_READY",
            "clarificationQuestion": None,
            "title": "供应商质量改进",
            "description": "季度末前把来料缺陷率降到百分之一以内。",
        }
    )
    prepared = transport.prepare(
        invocation_id="invocation-1", content="供应商质量有问题", profile=_profile()
    )
    credential = resolver.resolve(_profile(), "invocation-1")
    observation = transport.dispatch(
        invocation_id="invocation-1",
        request=prepared,
        credential=credential,
        profile=_profile(),
    )

    assert observation.state is ObservationState.SUCCEEDED
    assert observation.result_kind is DraftResultKind.DRAFT_READY
    assert (
        transport.dispatch_count
        == resolver.calls
        == len(_ResponsesHandler.requests)
        == 1
    )
    request = _ResponsesHandler.requests[0]
    assert request["path"] == "/v1/responses"
    assert request["authorization"] == "Bearer fake-provider-key-319"
    body = request["body"]
    assert body["model"] == "mock-model-319"
    assert body["background"] is body["store"] is False
    assert body["tools"] == [] and body["tool_choice"] == "none"
    assert body["truncation"] == "disabled"
    assert "previous_response_id" not in body
    assert body["text"]["format"]["strict"] is True
    assert body["text"]["format"]["schema"] == OUTPUT_SCHEMA
    assert prepared.quote.input_token_upper_bound == len(prepared.payload)
    assert prepared.quote.input_token_upper_bound > len("供应商质量有问题".encode())
    assert prepared.quote.output_token_ceiling == 128
    assert (
        prepared.quote.worst_case_cost_microusd == len(prepared.payload) * 2 + 128 * 8
    )
    assert "fake-provider-key-319" not in repr(credential)


def test_invalid_usage_is_treated_as_missing_and_cannot_release_budget(
    mock_responses,
):
    server, cert, tmp_path = mock_responses
    credential_file = _credential_file(tmp_path)
    configuration = _configuration(server, cert, credential_file)
    transport = OpenAIResponsesDraftTransport(configuration)
    resolver = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    _ResponsesHandler.response = _completed(
        {
            "kind": "DRAFT_READY",
            "clarificationQuestion": None,
            "title": "供应商质量改进",
            "description": "季度末前把来料缺陷率降到百分之一以内。",
        }
    )
    _ResponsesHandler.response["usage"] = {
        "input_tokens": True,
        "output_tokens": -1,
    }
    observation = transport.dispatch(
        invocation_id="invocation-invalid-usage",
        request=transport.prepare(
            invocation_id="invocation-invalid-usage",
            content="供应商质量有问题",
            profile=_profile(),
        ),
        credential=resolver.resolve(_profile(), "invocation-invalid-usage"),
        profile=_profile(),
    )

    assert observation.state is ObservationState.SUCCEEDED
    assert observation.input_tokens is None
    assert observation.output_tokens is None


def test_local_https_mock_requires_explicit_test_composition_gate(mock_responses):
    server, cert, tmp_path = mock_responses
    document = _real_runtime_document(server, cert, tmp_path)
    with pytest.raises(DraftAssistanceError, match="DRAFT_PROFILE_INVALID"):
        parse_runtime_profile(document)
    profile, _, configuration, budget = parse_runtime_profile(
        document, allow_local_https_mock=True
    )
    assert profile.adapter_id == ADAPTER_ID
    assert configuration is not None
    assert configuration.execution_class == "LOCAL_HTTPS_MOCK"
    assert budget == {
        "ledgerId": "s5-v023-impl-319-test",
        "callCap": 2,
        "totalCostCapMicrousd": 10_000,
        "inputPriceMicrousdPerMillionTokens": 2_000_000,
        "outputPriceMicrousdPerMillionTokens": 8_000_000,
    }


def test_real_profile_rejects_unknown_nested_fields_and_non_integer_budget(
    mock_responses,
):
    server, cert, tmp_path = mock_responses
    document = _real_runtime_document(server, cert, tmp_path)
    document["model"]["displayName"] = "must-not-be-authority"
    with pytest.raises(DraftAssistanceError, match="DRAFT_PROFILE_INVALID"):
        parse_runtime_profile(document, allow_local_https_mock=True)

    document = _real_runtime_document(server, cert, tmp_path)
    document["budget"]["callCap"] = "2"
    with pytest.raises(DraftAssistanceError, match="DRAFT_PROFILE_INVALID"):
        parse_runtime_profile(document, allow_local_https_mock=True)


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            {
                "status": "completed",
                "model": "mock-model-319",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "no"}],
                    }
                ],
            },
            "PROVIDER_REFUSAL",
        ),
        (
            {
                "status": "incomplete",
                "model": "mock-model-319",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            },
            "PROVIDER_OUTPUT_TRUNCATED",
        ),
        (
            _completed(
                {
                    "kind": "DRAFT_READY",
                    "clarificationQuestion": None,
                    "title": None,
                    "description": "invalid",
                }
            ),
            "OUTPUT_SCHEMA_INVALID",
        ),
    ],
)
def test_real_adapter_classifies_non_success_without_retry(
    mock_responses, response, reason
):
    server, cert, tmp_path = mock_responses
    credential_file = _credential_file(tmp_path)
    configuration = _configuration(server, cert, credential_file)
    transport = OpenAIResponsesDraftTransport(configuration)
    resolver = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    _ResponsesHandler.response = response
    observation = transport.dispatch(
        invocation_id="invocation-error",
        request=transport.prepare(
            invocation_id="invocation-error", content="test", profile=_profile()
        ),
        credential=resolver.resolve(_profile(), "invocation-error"),
        profile=_profile(),
    )
    assert observation.state is ObservationState.FAILED
    assert observation.reason_code == reason
    assert len(_ResponsesHandler.requests) == transport.dispatch_count == 1


def test_redirect_and_transport_disconnect_are_never_retried(mock_responses):
    server, cert, tmp_path = mock_responses
    credential_file = _credential_file(tmp_path)
    configuration = _configuration(server, cert, credential_file)
    transport = OpenAIResponsesDraftTransport(configuration)
    resolver = ExactFileOpenAICredentialResolver(
        configuration,
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    prepared = transport.prepare(
        invocation_id="invocation-redirect", content="test", profile=_profile()
    )
    credential = resolver.resolve(_profile(), "invocation-redirect")
    _ResponsesHandler.status = 307
    redirected = transport.dispatch(
        invocation_id="invocation-redirect",
        request=prepared,
        credential=credential,
        profile=_profile(),
    )
    assert redirected.reason_code == "PROVIDER_HTTP_REJECTED"
    assert len(_ResponsesHandler.requests) == 1

    _ResponsesHandler.status = 200
    _ResponsesHandler.disconnect = True
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="invocation-disconnect",
            request=transport.prepare(
                invocation_id="invocation-disconnect",
                content="test",
                profile=_profile(),
            ),
            credential=credential,
            profile=_profile(),
        )
    assert len(_ResponsesHandler.requests) == transport.dispatch_count == 2


def test_foreground_observe_and_cancel_report_unsupported_without_network(
    mock_responses,
):
    server, cert, tmp_path = mock_responses
    credential_file = _credential_file(tmp_path)
    transport = OpenAIResponsesDraftTransport(
        _configuration(server, cert, credential_file)
    )
    observed = transport.observe("req_mock_319")
    cancelled = transport.cancel("req_mock_319")
    assert observed.state is cancelled.state is ObservationState.UNKNOWN
    assert observed.reason_code == "PROVIDER_OBSERVATION_UNSUPPORTED_FOREGROUND"
    assert cancelled.reason_code == "PROVIDER_CANCELLATION_UNSUPPORTED_FOREGROUND"
    assert _ResponsesHandler.requests == []


def test_credential_resolver_has_no_environment_fallback(mock_responses, monkeypatch):
    server, cert, tmp_path = mock_responses
    missing = tmp_path / "missing-credential"
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-read")
    resolver = ExactFileOpenAICredentialResolver(
        _configuration(server, cert, missing),
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    with pytest.raises(DraftAssistanceError, match="CREDENTIAL_RESOLUTION_FAILED"):
        resolver.resolve(_profile(), "invocation-no-env-fallback")
    assert _ResponsesHandler.requests == []


def test_credential_resolver_rejects_non_private_file(mock_responses):
    server, cert, tmp_path = mock_responses
    credential_file = tmp_path / "credential"
    credential_file.write_text("fake-provider-key-319")
    credential_file.chmod(0o644)
    resolver = ExactFileOpenAICredentialResolver(
        _configuration(server, cert, credential_file),
        expected_profile_revision_id="draft-profile-real-1",
        expected_connection_profile_id="connection-profile-1",
        expected_connection_profile_revision_id="connection-profile-revision-1",
    )
    with pytest.raises(DraftAssistanceError, match="CREDENTIAL_RESOLUTION_FAILED"):
        resolver.resolve(_profile(), "invocation-public-file")
