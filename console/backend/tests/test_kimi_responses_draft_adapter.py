from __future__ import annotations

import json
import ssl
import subprocess
import threading
import time
from dataclasses import replace
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
)
from agent_console.draft_assistance_bootstrap import _profile as parse_runtime_profile
from agent_console.kimi_responses_draft_adapter import (
    ADAPTER_ID,
    ADAPTER_REVISION,
    OUTPUT_SCHEMA,
    PROTOCOL,
    ExactFileKimiCredentialResolver,
    KimiResponsesConfiguration,
    KimiResponsesDraftTransport,
)
from agent_console.model_binding_resolution import ExactModelBinding
from agent_console.openai_responses_draft_adapter import (
    ADAPTER_ID as OPENAI_ADAPTER_ID,
)

DIGEST = "a" * 64


class _KimiHandler(BaseHTTPRequestHandler):
    requests: ClassVar[list[dict[str, object]]] = []
    status = 200
    response: object = {}
    disconnect = False
    delay_seconds = 0.0
    chunk_delay = 0.0
    chunks = 1
    raw_response = None
    request_id = "req_kimi_mock_320"

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
        if type(self).delay_seconds:
            time.sleep(type(self).delay_seconds)
        payload = (
            type(self).raw_response
            if type(self).raw_response is not None
            else json.dumps(type(self).response).encode()
        )
        self.send_response(type(self).status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        if type(self).request_id is not None:
            self.send_header("x-request-id", type(self).request_id)
        if 300 <= type(self).status < 400:
            self.send_header("location", "https://redirect.invalid/v1/responses")
        self.end_headers()
        try:
            size = max(1, len(payload) // type(self).chunks)
            for offset in range(0, len(payload), size):
                self.wfile.write(payload[offset : offset + size])
                self.wfile.flush()
                if type(self).chunk_delay:
                    time.sleep(type(self).chunk_delay)
        except OSError:
            # Expected when the deadline supervisor closes its one connection.
            pass

    def log_message(self, _format, *_args):
        return


@pytest.fixture
def kimi_mock(tmp_path):
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
    _KimiHandler.requests = []
    _KimiHandler.status = 200
    _KimiHandler.response = {}
    _KimiHandler.disconnect = False
    _KimiHandler.delay_seconds = 0.0
    _KimiHandler.chunk_delay = 0.0
    _KimiHandler.chunks = 1
    _KimiHandler.raw_response = None
    _KimiHandler.request_id = "req_kimi_mock_320"
    server = ThreadingHTTPServer(("127.0.0.1", 0), _KimiHandler)
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
        "draft-profile-kimi-1",
        DIGEST,
        DraftScope("tenant-a", "quality"),
        ExactModelBinding("model-kimi", "model-revision-kimi-1", DIGEST),
        "provider-kimi",
        "provider-revision-kimi-1",
        DIGEST,
        "endpoint-kimi",
        "endpoint-revision-kimi-1",
        DIGEST,
        "connection-profile-kimi",
        "connection-profile-revision-kimi-1",
        DIGEST,
        ADAPTER_ID,
        ADAPTER_REVISION,
        maximum_output_tokens=4096,
        total_timeout_seconds=5,
    )


def _credential_file(tmp_path: Path) -> Path:
    path = tmp_path / "credential"
    path.write_text("fake-kimi-provider-key-320")
    path.chmod(0o600)
    return path


def _configuration(server, cert, credential_file, *, effort="low"):
    return KimiResponsesConfiguration(
        "LOCAL_HTTPS_MOCK",
        f"https://127.0.0.1:{server.server_port}/v1/responses",
        "mock-kimi-k3-320",
        "secret-reference:kimi-mock-320",
        "v1",
        "exact-file-resolver",
        "v1",
        credential_file,
        2,
        3,
        5,
        20_000,
        4096,
        64_000,
        1_000_000,
        2_000_000,
        effort,
        cert,
    )


def _resolver(configuration):
    return ExactFileKimiCredentialResolver(
        configuration,
        expected_profile_revision_id="draft-profile-kimi-1",
        expected_connection_profile_id="connection-profile-kimi",
        expected_connection_profile_revision_id="connection-profile-revision-kimi-1",
    )


def _completed(result, *, usage=None):
    return {
        "id": "resp_kimi_mock_320",
        "status": "completed",
        "model": "mock-kimi-k3-320",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": json.dumps(result)}],
            }
        ],
        "usage": usage
        if usage is not None
        else {
            "input_tokens": 80,
            "input_tokens_details": {"cached_tokens": 10},
            "output_tokens": 40,
            "output_tokens_details": {"reasoning_tokens": 20},
        },
    }


def _runtime_document(server, cert, tmp_path):
    return {
        "schemaVersion": "draft-assistance-runtime.v1",
        "transportKind": "REAL_PROVIDER",
        "scope": {"namespace": "tenant-a", "securityDomain": "quality"},
        "profileRevisionId": "draft-profile-kimi-1",
        "profileDigest": DIGEST,
        "model": {
            "id": "model-kimi",
            "revisionId": "model-revision-kimi-1",
            "digest": DIGEST,
        },
        "provider": {
            "id": "provider-kimi",
            "revisionId": "provider-revision-kimi-1",
            "digest": DIGEST,
        },
        "endpoint": {
            "id": "endpoint-kimi",
            "revisionId": "endpoint-revision-kimi-1",
            "digest": DIGEST,
        },
        "connectionProfile": {
            "id": "connection-profile-kimi",
            "revisionId": "connection-profile-revision-kimi-1",
            "digest": DIGEST,
        },
        "adapter": {"id": ADAPTER_ID, "revision": ADAPTER_REVISION},
        "outputSchemaVersion": "problem-draft-assistance-output.v1",
        "targetFormatVersion": "draft-assistance-target.v1",
        "maximumInputBytes": 32_768,
        "maximumOutputTokens": 4096,
        "totalTimeoutSeconds": 5,
        "pepperReference": "pepper:kimi-draft",
        "pepperVersion": "v1",
        "pepperFile": str(tmp_path / "pepper"),
        "providerProtocol": PROTOCOL,
        "executionClass": "LOCAL_HTTPS_MOCK",
        "responsesUrl": f"https://127.0.0.1:{server.server_port}/v1/responses",
        "nativeModelId": "mock-kimi-k3-320",
        "reasoningEffort": "low",
        "maximumInputTokens": 20_000,
        "maximumResponseBytes": 64_000,
        "connectTimeoutSeconds": 2,
        "readTimeoutSeconds": 3,
        "credential": {
            "reference": "secret-reference:kimi-mock-320",
            "version": "v1",
            "resolverId": "exact-file-resolver",
            "resolverRevision": "v1",
            "file": str(tmp_path / "credential"),
        },
        "tls": {"caFile": str(cert)},
        "budget": {
            "ledgerId": "s5-v023-impl-320-test",
            "currency": "USD",
            "callCap": 10,
            "totalCostCapMicrousd": 10_000_000,
            "inputPriceMicrousdPerMillionTokens": 1_000_000,
            "outputPriceMicrousdPerMillionTokens": 2_000_000,
        },
    }


def test_kimi_request_projection_is_exact_and_omits_openai_only_fields(kimi_mock):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(configuration)
    resolver = _resolver(configuration)
    _KimiHandler.response = _completed(
        {
            "kind": "DRAFT_READY",
            "clarificationQuestion": None,
            "title": "供应商质量改进",
            "description": "季度末前把来料缺陷率降到百分之一以内。",
        }
    )

    prepared = transport.prepare(
        invocation_id="invocation-kimi-1",
        content="供应商质量有问题",
        profile=_profile(),
    )
    credential = resolver.resolve(_profile(), "invocation-kimi-1")
    observation = transport.dispatch(
        invocation_id="invocation-kimi-1",
        request=prepared,
        credential=credential,
        profile=_profile(),
    )

    assert observation.state is ObservationState.SUCCEEDED
    assert observation.result_kind is DraftResultKind.DRAFT_READY
    assert transport.dispatch_count == resolver.calls == len(_KimiHandler.requests) == 1
    request = _KimiHandler.requests[0]
    assert request["path"] == "/v1/responses"
    assert request["authorization"] == "Bearer fake-kimi-provider-key-320"
    body = request["body"]
    assert body["model"] == "mock-kimi-k3-320"
    assert body["reasoning"] == {"effort": "low"}
    assert body["max_output_tokens"] == 4096
    assert body["background"] is body["store"] is False
    assert body["text"]["format"] == {
        "type": "json_schema",
        "name": "problem_draft_assistance_output",
        "strict": True,
        "schema": OUTPUT_SCHEMA,
    }
    for absent in (
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "truncation",
        "previous_response_id",
    ):
        assert absent not in body
    assert prepared.quote.input_token_upper_bound == len(prepared.payload)
    assert prepared.quote.output_token_ceiling == 4096
    assert "fake-kimi-provider-key-320" not in repr(credential)


@pytest.mark.parametrize("effort", ["low", "high", "max"])
def test_official_reasoning_effort_enumeration_is_accepted(kimi_mock, effort):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(
        server, cert, _credential_file(tmp_path), effort=effort
    )
    body = json.loads(
        KimiResponsesDraftTransport(configuration)
        .prepare(invocation_id="i", content="test", profile=_profile())
        .payload
    )
    assert body["reasoning"] == {"effort": effort}


def test_unknown_reasoning_effort_fails_closed(kimi_mock):
    server, cert, tmp_path = kimi_mock
    with pytest.raises(DraftAssistanceError, match="KIMI_RESPONSES_PROFILE_INVALID"):
        _configuration(server, cert, _credential_file(tmp_path), effort="medium")


@pytest.mark.parametrize(
    ("response", "state", "reason"),
    [
        (
            {
                "status": "completed",
                "model": "mock-kimi-k3-320",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "refusal", "refusal": "no"}],
                    }
                ],
            },
            ObservationState.FAILED,
            "PROVIDER_REFUSAL",
        ),
        (
            {
                "status": "incomplete",
                "model": "mock-kimi-k3-320",
                "incomplete_details": {"reason": "max_output_tokens"},
                "output": [],
            },
            ObservationState.FAILED,
            "PROVIDER_OUTPUT_TRUNCATED",
        ),
        (
            {
                "status": "failed",
                "model": "mock-kimi-k3-320",
                "error": {"code": "mock_failure", "message": "not persisted"},
                "output": [],
            },
            ObservationState.FAILED,
            "PROVIDER_RESPONSE_FAILED",
        ),
        (
            {
                "status": "in_progress",
                "model": "mock-kimi-k3-320",
                "output": [],
            },
            ObservationState.UNKNOWN,
            "PROVIDER_FOREGROUND_NONTERMINAL",
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
            ObservationState.FAILED,
            "OUTPUT_SCHEMA_INVALID",
        ),
    ],
)
def test_kimi_response_non_success_is_strict_and_never_retried(
    kimi_mock, response, state, reason
):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(configuration)
    resolver = _resolver(configuration)
    _KimiHandler.response = response
    observation = transport.dispatch(
        invocation_id="invocation-kimi-error",
        request=transport.prepare(
            invocation_id="invocation-kimi-error", content="test", profile=_profile()
        ),
        credential=resolver.resolve(_profile(), "invocation-kimi-error"),
        profile=_profile(),
    )
    assert observation.state is state
    assert observation.reason_code == reason
    assert len(_KimiHandler.requests) == transport.dispatch_count == 1


@pytest.mark.parametrize(
    "usage",
    [None, {"input_tokens": True, "output_tokens": -1}],
)
def test_missing_or_invalid_usage_is_not_fabricated(kimi_mock, usage):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(configuration)
    resolver = _resolver(configuration)
    response = _completed(
        {
            "kind": "NEEDS_CLARIFICATION",
            "clarificationQuestion": "请补充完成标准。",
            "title": None,
            "description": None,
        },
        usage=usage,
    )
    if usage is None:
        response.pop("usage")
    _KimiHandler.response = response
    observation = transport.dispatch(
        invocation_id="invocation-kimi-usage",
        request=transport.prepare(
            invocation_id="invocation-kimi-usage", content="test", profile=_profile()
        ),
        credential=resolver.resolve(_profile(), "invocation-kimi-usage"),
        profile=_profile(),
    )
    assert observation.state is ObservationState.SUCCEEDED
    assert observation.input_tokens is observation.output_tokens is None
    assert observation.result_kind is DraftResultKind.NEEDS_CLARIFICATION
    assert observation.clarification_question == "请补充完成标准。"


def test_redirect_disconnect_observe_and_cancel_do_not_retry(kimi_mock):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(configuration)
    resolver = _resolver(configuration)
    request = transport.prepare(invocation_id="i", content="test", profile=_profile())
    credential = resolver.resolve(_profile(), "i")

    _KimiHandler.status = 307
    redirected = transport.dispatch(
        invocation_id="i", request=request, credential=credential, profile=_profile()
    )
    assert redirected.reason_code == "PROVIDER_HTTP_REJECTED"
    assert len(_KimiHandler.requests) == 1

    _KimiHandler.status = 200
    _KimiHandler.disconnect = True
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="i2",
            request=transport.prepare(
                invocation_id="i2", content="test", profile=_profile()
            ),
            credential=credential,
            profile=_profile(),
        )
    assert len(_KimiHandler.requests) == transport.dispatch_count == 2
    calls = transport.dispatch_count
    assert transport.observe("req_kimi_mock_320").state is ObservationState.UNKNOWN
    assert transport.cancel("req_kimi_mock_320").state is ObservationState.UNKNOWN
    assert transport.dispatch_count == calls


def test_read_timeout_is_ambiguous_and_dispatched_once(kimi_mock):
    server, cert, tmp_path = kimi_mock
    credential_file = _credential_file(tmp_path)
    configuration = KimiResponsesConfiguration(
        "LOCAL_HTTPS_MOCK",
        f"https://127.0.0.1:{server.server_port}/v1/responses",
        "mock-kimi-k3-320",
        "secret-reference:kimi-mock-320",
        "v1",
        "exact-file-resolver",
        "v1",
        credential_file,
        1,
        1,
        5,
        20_000,
        4096,
        64_000,
        1_000_000,
        2_000_000,
        "low",
        cert,
    )
    transport = KimiResponsesDraftTransport(configuration)
    _KimiHandler.delay_seconds = 1.5
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="invocation-kimi-timeout",
            request=transport.prepare(
                invocation_id="invocation-kimi-timeout",
                content="test",
                profile=_profile(),
            ),
            credential=_resolver(configuration).resolve(
                _profile(), "invocation-kimi-timeout"
            ),
            profile=_profile(),
        )
    assert len(_KimiHandler.requests) == transport.dispatch_count == 1


def test_missing_ca_is_configuration_failure_before_dispatch(kimi_mock):
    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    invalid = KimiResponsesConfiguration(
        configuration.execution_class,
        configuration.responses_url,
        configuration.native_model_id,
        configuration.credential_reference,
        configuration.credential_version,
        configuration.credential_resolver_id,
        configuration.credential_resolver_revision,
        configuration.credential_file,
        configuration.connect_timeout_seconds,
        configuration.read_timeout_seconds,
        configuration.total_timeout_seconds,
        configuration.maximum_input_tokens,
        configuration.maximum_output_tokens,
        configuration.maximum_response_bytes,
        configuration.input_price_microusd_per_million_tokens,
        configuration.output_price_microusd_per_million_tokens,
        configuration.reasoning_effort,
        tmp_path / "missing-ca.pem",
    )
    transport = KimiResponsesDraftTransport(invalid)
    with pytest.raises(
        DraftAssistanceError, match="KIMI_RESPONSES_TLS_CONFIGURATION_INVALID"
    ):
        transport.dispatch(
            invocation_id="invocation-kimi-tls",
            request=transport.prepare(
                invocation_id="invocation-kimi-tls", content="test", profile=_profile()
            ),
            credential=_resolver(invalid).resolve(_profile(), "invocation-kimi-tls"),
            profile=_profile(),
        )
    assert transport.dispatch_count == 1
    assert transport.last_deadline_metrics.reaped


def test_kimi_profile_selection_is_exact_and_mixed_adapter_fails_closed(kimi_mock):
    server, cert, tmp_path = kimi_mock
    document = _runtime_document(server, cert, tmp_path)
    with pytest.raises(DraftAssistanceError, match="DRAFT_PROFILE_INVALID"):
        parse_runtime_profile(document)
    profile, _, configuration, budget = parse_runtime_profile(
        document, allow_local_https_mock=True
    )
    assert profile.adapter_id == ADAPTER_ID
    assert isinstance(configuration, KimiResponsesConfiguration)
    assert configuration.reasoning_effort == "low"
    assert budget["callCap"] == 10
    assert budget["totalCostCapMicrousd"] == 10_000_000

    for mutate in (
        lambda value: value.__setitem__("providerProtocol", "OPENAI_RESPONSES_V1"),
        lambda value: value["adapter"].__setitem__("id", OPENAI_ADAPTER_ID),
        lambda value: value.__setitem__("reasoningEffort", "medium"),
    ):
        mixed = _runtime_document(server, cert, tmp_path)
        mutate(mixed)
        with pytest.raises(DraftAssistanceError, match="DRAFT_PROFILE_INVALID"):
            parse_runtime_profile(mixed, allow_local_https_mock=True)


def test_untrusted_certificate_fails_during_tls_before_http_dispatch(kimi_mock):
    server, cert, tmp_path = kimi_mock
    configuration = replace(
        _configuration(server, cert, _credential_file(tmp_path)), ca_file=None
    )
    transport = KimiResponsesDraftTransport(configuration)
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS") as failure:
        transport.dispatch(
            invocation_id="untrusted-cert",
            request=transport.prepare(
                invocation_id="untrusted-cert", content="test", profile=_profile()
            ),
            credential=_resolver(configuration).resolve(_profile(), "untrusted-cert"),
            profile=_profile(),
        )
    assert isinstance(failure.value.__cause__, ssl.SSLCertVerificationError)
    assert transport.dispatch_count == 1
    assert _KimiHandler.requests == []


@pytest.mark.parametrize("branch", ["connect-timeout", "post-connect-deadline"])
def test_connect_timeout_and_independent_deadline_are_separate(
    kimi_mock, monkeypatch, branch
):
    from agent_console import kimi_responses_draft_adapter as adapter

    server, cert, tmp_path = kimi_mock
    configuration = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(configuration)
    events = []
    clock = [0.0]

    class Connection:
        sock = None

        def __init__(self, *args, timeout, **kwargs):
            assert timeout == configuration.connect_timeout_seconds

        def connect(self):
            events.append("connect")
            if branch == "connect-timeout":
                raise TimeoutError("deterministic connect timeout")
            clock[0] = configuration.total_timeout_seconds + 0.1

        def close(self):
            events.append("close")

    monkeypatch.setattr(adapter.http.client, "HTTPSConnection", Connection)
    monkeypatch.setattr(adapter.time, "monotonic", lambda: clock[0])
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS") as failure:
        transport._dispatch_once(
            invocation_id=branch,
            request=transport.prepare(
                invocation_id=branch, content="test", profile=_profile()
            ),
            credential=_resolver(configuration).resolve(_profile(), branch),
            profile=_profile(),
        )
    assert isinstance(failure.value.__cause__, TimeoutError)
    assert events == ["connect", "close"]
    assert transport.dispatch_count == 1
    assert _KimiHandler.requests == []


def test_kimi_credential_resolver_has_no_environment_fallback(kimi_mock, monkeypatch):
    server, cert, tmp_path = kimi_mock
    monkeypatch.setenv("MOONSHOT_API_KEY", "must-not-be-read")
    configuration = _configuration(server, cert, tmp_path / "missing")
    with pytest.raises(DraftAssistanceError, match="CREDENTIAL_RESOLUTION_FAILED"):
        _resolver(configuration).resolve(_profile(), "invocation-no-env")
    assert _KimiHandler.requests == []


# Fault injection below runs inside a fresh real spawned process. It does not
# claim actual stalled DNS/TCP/TLS integration evidence.
def _stalled_deadline_worker(channel, configuration, phase):
    import http.client
    import socket

    from agent_console.kimi_deadline import _worker

    def stall(*args, **kwargs):
        time.sleep(30)
        raise TimeoutError

    if phase == "dns":
        socket.getaddrinfo = stall
    elif phase == "tcp":
        socket.socket.connect = stall
    elif phase == "tls":
        ssl.SSLContext.wrap_socket = stall
    elif phase == "send":
        http.client.HTTPSConnection.request = stall
    elif phase == "headers":
        http.client.HTTPSConnection.getresponse = stall
    else:
        http.client.HTTPResponse.read = stall
    _worker(channel, configuration, phase)


def _stalled_receiver_worker(channel, configuration, phase):
    time.sleep(30)


def _partial_result_worker(channel, configuration, phase):
    from agent_console.kimi_deadline import _send

    _send(channel, {"connected": True})
    channel.sendall(b'{"result":')
    time.sleep(30)


@pytest.mark.parametrize("phase", ["dns", "tcp", "tls", "send", "headers", "body"])
def test_parent_deadline_kills_stalled_phase_and_reaps(
    kimi_mock, phase, record_property
):
    import os

    from agent_console.kimi_deadline import _supervise

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        total_timeout_seconds=2,
    )
    records = []
    started = time.monotonic()
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        _supervise(
            config,
            phase,
            KimiResponsesDraftTransport(config).prepare(
                invocation_id=phase,
                content="test",
                profile=replace(_profile(), total_timeout_seconds=2),
            ),
            _resolver(config).resolve(_profile(), phase),
            records.append,
            worker=_stalled_deadline_worker,
        )
    elapsed = time.monotonic() - started
    metric = records[0]
    from dataclasses import asdict

    record_property("deadline_metrics", json.dumps(asdict(metric)))
    expected = (
        "CONNECT_DEADLINE" if phase in {"dns", "tcp", "tls"} else "TOTAL_DEADLINE"
    )
    assert metric.reason == expected
    assert metric.reaped and metric.cleanup_seconds <= 1
    assert metric.decision_seconds >= (1 if expected == "CONNECT_DEADLINE" else 2)
    assert elapsed < (2 if expected == "CONNECT_DEADLINE" else 3)
    with pytest.raises(ProcessLookupError):
        os.kill(metric.worker_pid, 0)
    assert len(_KimiHandler.requests) == (1 if phase in {"headers", "body"} else 0)


def test_partial_ipc_cannot_block_parent_past_total(kimi_mock):
    from agent_console.kimi_deadline import _supervise

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        total_timeout_seconds=1,
    )
    records = []
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        _supervise(
            config, "ipc", None, None, records.append, worker=_partial_result_worker
        )
    assert records[0].reason == "TOTAL_DEADLINE"
    assert records[0].reaped and records[0].cleanup_seconds <= 1


@pytest.mark.parametrize(
    "now,connected,expected",
    [
        (0.9, False, None),
        (1.0, False, "CONNECT_DEADLINE"),
        (1.0, True, None),
        (1.999, True, None),
        (2.0, True, "TOTAL_DEADLINE"),
        (2.001, True, "TOTAL_DEADLINE"),
        (2.0, False, "TOTAL_DEADLINE"),
    ],
)
def test_deadline_wins_equality_and_readable_result_race(now, connected, expected):
    from agent_console.kimi_deadline import _check_deadline

    assert _check_deadline(now, 2.0, 1.0, connected) == expected


@pytest.mark.parametrize("mode", ["late-headers", "slow-body", "cumulative"])
def test_real_https_total_deadline_rejects_late_valid_json(
    kimi_mock, mode, record_property
):
    import os

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        connect_timeout_seconds=1,
        read_timeout_seconds=2,
        total_timeout_seconds=2,
    )
    _KimiHandler.response = _completed(
        {
            "kind": "NEEDS_CLARIFICATION",
            "clarificationQuestion": "Synthetic question",
            "title": None,
            "description": None,
        }
    )
    if mode == "late-headers":
        _KimiHandler.delay_seconds = 2.5
    elif mode == "slow-body":
        _KimiHandler.chunk_delay = 0.3
        _KimiHandler.chunks = 12
    else:
        _KimiHandler.delay_seconds = 0.9
        _KimiHandler.chunk_delay = 0.3
        _KimiHandler.chunks = 6
    transport = KimiResponsesDraftTransport(config)
    started = time.monotonic()
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="late-valid-json",
            profile=_profile(),
            request=transport.prepare(
                invocation_id="late-valid-json",
                content="test",
                profile=replace(_profile(), total_timeout_seconds=2),
            ),
            credential=_resolver(config).resolve(_profile(), "late-valid-json"),
        )
    elapsed = time.monotonic() - started
    metric = transport.last_deadline_metrics
    from dataclasses import asdict

    record_property("deadline_metrics", json.dumps(asdict(metric)))
    assert metric.reason == "TOTAL_DEADLINE"
    assert 2 <= metric.decision_seconds < 2.5
    assert metric.cleanup_seconds <= 1 and metric.reaped
    assert elapsed < 3
    assert transport.dispatch_count == len(_KimiHandler.requests) == 1
    with pytest.raises(ProcessLookupError):
        os.kill(metric.worker_pid, 0)


def test_worker_result_is_rejected_if_parent_validation_finishes_at_deadline(
    kimi_mock, monkeypatch
):
    from agent_console import kimi_deadline

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        total_timeout_seconds=1,
    )
    _KimiHandler.response = _completed(
        {
            "kind": "NEEDS_CLARIFICATION",
            "clarificationQuestion": "Synthetic",
            "title": None,
            "description": None,
        }
    )
    original = kimi_deadline.ProviderObservation

    def delayed_validation(**value):
        result = original(**value)
        time.sleep(1.05)
        return result

    monkeypatch.setattr(kimi_deadline, "ProviderObservation", delayed_validation)
    transport = KimiResponsesDraftTransport(config)
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="validation-race",
            profile=_profile(),
            request=transport.prepare(
                invocation_id="validation-race",
                content="test",
                profile=replace(_profile(), total_timeout_seconds=1),
            ),
            credential=_resolver(config).resolve(_profile(), "validation-race"),
        )
    assert transport.last_deadline_metrics.reason == "TOTAL_DEADLINE"
    assert transport.last_deadline_metrics.reaped
    assert transport.dispatch_count == len(_KimiHandler.requests) == 1


def _noisy_request_worker(channel, configuration, invocation_id):
    import os

    from agent_console.kimi_deadline import _worker

    def noisy_once(self, **kwargs):
        import resource

        assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
        os.write(1, b"synthetic-secret-must-not-log")
        os.write(2, b"synthetic-body-must-not-log")
        raise RuntimeError("synthetic-secret-must-not-log")

    KimiResponsesDraftTransport._dispatch_once = noisy_once
    _worker(channel, configuration, invocation_id)


def test_worker_silences_sensitive_diagnostics_and_leaves_no_secret_files(
    kimi_mock, capfd
):
    from agent_console.kimi_deadline import _supervise

    server, cert, tmp_path = kimi_mock
    config = _configuration(server, cert, _credential_file(tmp_path))
    before = set(tmp_path.rglob("*"))
    records = []
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        _supervise(
            config,
            "silent",
            KimiResponsesDraftTransport(config).prepare(
                invocation_id="silent", content="test", profile=_profile()
            ),
            _resolver(config).resolve(_profile(), "silent"),
            records.append,
            worker=_noisy_request_worker,
        )
    captured = capfd.readouterr()
    assert "synthetic-secret" not in captured.out + captured.err
    assert "synthetic-body" not in captured.out + captured.err
    assert set(tmp_path.rglob("*")) == before
    assert records[0].reaped


def test_worker_exits_on_parent_channel_loss_during_https_body(kimi_mock):
    import multiprocessing
    import socket

    from agent_console.kimi_deadline import _worker

    server, cert, tmp_path = kimi_mock
    config = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(config)
    _KimiHandler.delay_seconds = 2
    parent, child = socket.socketpair()
    from agent_console.kimi_deadline import _request_message

    process = multiprocessing.get_context("spawn").Process(
        target=_worker,
        args=(child, config, "parent-loss"),
    )
    try:
        process.start()
        child.close()
        parent.settimeout(1.5)
        parent.sendall(
            _request_message(
                transport.prepare(
                    invocation_id="parent-loss", content="test", profile=_profile()
                ),
                _resolver(config).resolve(_profile(), "parent-loss"),
            )
        )
        received = bytearray()
        until = time.monotonic() + 1.5
        while b'"connected": true' not in received and time.monotonic() < until:
            chunk = parent.recv(256)
            assert chunk
            received.extend(chunk)
        assert b'"connected": true' in received
        parent.close()  # EOF fault injection, equivalent to loss of parent endpoint.
        process.join(1)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        parent.close()
        child.close()
        if process.is_alive():
            process.kill()
            process.join(1)
        process.close()


def test_blocked_large_request_ipc_obeys_parent_deadline(kimi_mock):
    from agent_console.draft_assistance import (
        PreparedProviderRequest,
        ProviderBudgetQuote,
    )
    from agent_console.kimi_deadline import _supervise

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        maximum_input_tokens=1_000_000,
        connect_timeout_seconds=1,
        read_timeout_seconds=1,
        total_timeout_seconds=1,
    )
    request = PreparedProviderRequest(
        b"x" * 600_000, ProviderBudgetQuote(600_000, 4096, 608192)
    )
    records = []
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        _supervise(
            config,
            "dns",
            request,
            _resolver(config).resolve(_profile(), "ipc"),
            records.append,
            worker=_stalled_receiver_worker,
        )
    assert records[0].reason == "TOTAL_DEADLINE"
    assert records[0].decision_seconds < 1.5
    assert records[0].cleanup_seconds <= 1 and records[0].reaped


def test_cleanup_failure_never_returns_worker_success(kimi_mock, monkeypatch):
    from types import SimpleNamespace

    from agent_console import kimi_deadline

    server, cert, tmp_path = kimi_mock
    config = _configuration(server, cert, _credential_file(tmp_path))

    class UnreapableProcess:
        pid = 999999

        def __init__(self, *, target, args, name):
            self.channel = args[0]

        def start(self):
            kimi_deadline._send(self.channel, {"connected": True})
            kimi_deadline._send(
                self.channel,
                {
                    "result": {
                        "observation_id": "fake-valid",
                        "state": "SUCCEEDED",
                        "result_kind": "NEEDS_CLARIFICATION",
                        "clarification_question": "Synthetic",
                    }
                },
            )

        def is_alive(self):
            return True

        def kill(self):
            pass

        def join(self, timeout):
            assert 0 <= timeout <= 1

    monkeypatch.setattr(
        kimi_deadline.multiprocessing,
        "get_context",
        lambda method: SimpleNamespace(Process=UnreapableProcess),
    )
    # Fake process emulates kernel cleanup failure; no real PID is signalled.
    transport = KimiResponsesDraftTransport(config)
    request = transport.prepare(
        invocation_id="cleanup", content="test", profile=_profile()
    )
    credential = _resolver(config).resolve(_profile(), "cleanup")
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="cleanup",
            request=request,
            credential=credential,
            profile=_profile(),
        )
    assert transport.last_deadline_metrics.reason == "CLEANUP_FAILURE"
    assert not transport.last_deadline_metrics.reaped
    assert transport.last_deadline_metrics.worker_exit_status == "UNKNOWN"
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="cleanup-again",
            request=request,
            credential=credential,
            profile=_profile(),
        )
    assert transport.dispatch_count == 1


def test_supervised_transport_runs_from_backend_thread(kimi_mock):
    from concurrent.futures import ThreadPoolExecutor

    server, cert, tmp_path = kimi_mock
    config = _configuration(server, cert, _credential_file(tmp_path))
    transport = KimiResponsesDraftTransport(config)
    _KimiHandler.response = _completed(
        {
            "kind": "NEEDS_CLARIFICATION",
            "clarificationQuestion": "Synthetic",
            "title": None,
            "description": None,
        }
    )
    request = transport.prepare(
        invocation_id="thread", content="test", profile=_profile()
    )
    credential = _resolver(config).resolve(_profile(), "thread")
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(
            transport.dispatch,
            invocation_id="thread",
            request=request,
            credential=credential,
            profile=_profile(),
        ).result(timeout=6)
    assert result.state is ObservationState.SUCCEEDED
    assert transport.dispatch_count == len(_KimiHandler.requests) == 1
    assert transport.last_deadline_metrics.reaped
    assert transport.last_deadline_metrics.cleanup_seconds <= 1
    assert transport.last_deadline_metrics.decision_seconds < 5


@pytest.mark.parametrize(
    "fault,stage,category",
    [
        ("headers", "WAIT_HEADERS", "TIMEOUT"),
        ("body", "READ_BODY", "TIMEOUT"),
        ("disconnect", "WAIT_HEADERS", "REMOTE_DISCONNECT"),
    ],
)
def test_safe_worker_diagnostics_survive_parent_mapping(
    kimi_mock, fault, stage, category
):
    from dataclasses import asdict

    server, cert, tmp_path = kimi_mock
    config = replace(
        _configuration(server, cert, _credential_file(tmp_path)),
        connect_timeout_seconds=3,
        read_timeout_seconds=1,
        total_timeout_seconds=5,
    )
    if fault == "headers":
        _KimiHandler.delay_seconds = 1.5
    elif fault == "body":
        _KimiHandler.response = {"sentinel": "PRIVATE_RESPONSE_SENTINEL" * 50}
        _KimiHandler.chunks = 2
        _KimiHandler.chunk_delay = 1.5
    else:
        _KimiHandler.disconnect = True
    transport = KimiResponsesDraftTransport(config)
    with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
        transport.dispatch(
            invocation_id="safe-diagnostics",
            request=transport.prepare(
                invocation_id="safe-diagnostics",
                content="PRIVATE_REQUEST_SENTINEL",
                profile=_profile(),
            ),
            credential=_resolver(config).resolve(_profile(), "safe-diagnostics"),
            profile=_profile(),
        )
    metrics = transport.last_deadline_metrics
    assert metrics.failure_stage == stage
    assert metrics.exception_category == category
    assert metrics.reason == "WORKER_ERROR"
    assert metrics.reaped
    assert isinstance(metrics.worker_exit_status, int)
    assert metrics.stage_seconds[stage] >= 0
    assert transport.dispatch_count == len(_KimiHandler.requests) == 1
    serialized = json.dumps(asdict(metrics))
    assert "PRIVATE_" not in serialized
    assert "Bearer" not in serialized


def test_exception_categories_never_include_exception_text():
    from agent_console.kimi_deadline import exception_category

    class SecretException(Exception):
        pass

    assert exception_category(SecretException("PRIVATE_SECRET")) == "UNEXPECTED"
    assert exception_category(TimeoutError("PRIVATE_SECRET")) == "TIMEOUT"


@pytest.mark.parametrize("invalid_body", [False, True])
def test_non2xx_safe_diagnostic_crosses_worker_without_extra_dispatch(
    kimi_mock, invalid_body
):
    server, cert, directory = kimi_mock
    configuration = _configuration(server, cert, _credential_file(directory))
    transport = KimiResponsesDraftTransport(configuration)
    profile = _profile()
    credential = _resolver(configuration).resolve(profile, "diagnostic-once")
    _KimiHandler.status = 429
    _KimiHandler.response = {
        "error": {
            "type": "engine_overloaded_error",
            "message": "The engine is currently overloaded, please try again later",
        }
    }
    if invalid_body:
        _KimiHandler.raw_response = b"<html>unknown private server text</html>"
        _KimiHandler.request_id = None
    request = transport.prepare(
        invocation_id="diagnostic-once", content="Synthetic", profile=profile
    )
    result = transport.dispatch(
        invocation_id="diagnostic-once",
        request=request,
        credential=credential,
        profile=profile,
    )
    assert result.reason_code == "PROVIDER_RATE_LIMITED"
    assert len(_KimiHandler.requests) == transport.dispatch_count == 1
    assert transport.last_deadline_metrics.reaped
    diagnostic = transport.last_http_diagnostic
    assert diagnostic["http_status"] == 429
    if invalid_body:
        assert diagnostic["parse_failed"]
        assert diagnostic["provider_request_id"]["missing"]
        assert diagnostic["provider_request_id_header"] is None
        assert diagnostic["error"]["type"]["missing"]
        assert result.correlation == "http-429-diagnostic-once"
        assert "unknown private server text" not in json.dumps(diagnostic)
    else:
        assert diagnostic["error"]["type"]["value"] == "engine_overloaded_error"
        assert diagnostic["provider_request_id_header"] == "x-request-id"
    assert diagnostic["retry_after"]["missing"]
    assert diagnostic["error"]["code"]["missing"]
    assert "fake-kimi-provider-key-320" not in json.dumps(diagnostic)
