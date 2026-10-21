"""Characterize the formal planning path, not Kimi supervision.

Real local TLS/HTTP exchange; synthetic credentials/data; owner/BFF dependencies
are the explicit formal-assembly test doubles. Gates release in finally, so a
missing production deadline cannot leave a test worker or listener behind.
These assertions document limitations, not acceptance of real-model readiness.
"""

import asyncio
import json
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace as NS

import httpx
import pytest
from agent_console import plan_suggestion_runtime as runtime
from test_plan_suggestion_v2 import sample
from test_planning_runtime import formal as formal
from test_planning_runtime import send

REAL_EXCHANGE = runtime.OpenAIResponsesDraftTransport.exchange
REAL_RESOLVE = runtime.ExactFileOpenAICredentialResolver.resolve
REAL_BUILD = runtime.build_planning_runtime
REAL_PROVIDER_INIT = runtime.PlanningResponsesProvider.__init__


@pytest.fixture
def endpoint(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
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
    state = NS(
        mode="valid",
        requests=0,
        documents=[],
        accepted=threading.Event(),
        release=threading.Event(),
        stopped=threading.Event(),
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            state.documents.append(
                json.loads(self.rfile.read(int(self.headers["content-length"])))
            )
            state.requests += 1
            state.accepted.set()
            inner = {"kind": "NEEDS_CLARIFICATION", "questions": ["Synthetic date?"]}
            if state.mode == "invalid-inner":
                inner = {"unsupported": True}
            body = json.dumps(
                {
                    "id": "resp-local-323",
                    "usage": {
                        "input_tokens": 30,
                        "output_tokens": 12,
                        "total_tokens": 42,
                        "input_tokens_details": {"cached_tokens": 7},
                    },
                    "model": "mock-model-319",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(inner)}
                            ],
                        }
                    ],
                }
            ).encode()
            if state.mode == "invalid-json":
                body = b"not-json"
            if state.mode == "oversized":
                body = b"x" * 70000
            try:
                if state.mode in {"headers", "cancel"}:
                    state.release.wait(5)
                self.send_response(200)
                self.send_header("x-request-id", "req-local-323")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if state.mode == "body":
                    state.release.wait(5)
                if state.mode == "drip":
                    # Each inter-byte wait is below read timeout, cumulative > total.
                    size = 1
                    for offset in range(0, len(body), size):
                        self.wfile.write(body[offset : offset + size])
                        self.wfile.flush()
                        if state.stopped.wait(0.05):
                            return
                else:
                    self.wfile.write(body)
            except OSError:
                pass  # Client timeout closes its connection.

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = False
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    state.url = f"https://127.0.0.1:{server.server_port}/v1/responses"
    state.cert = cert
    try:
        yield state
    finally:
        state.release.set()
        state.stopped.set()
        server.shutdown()
        server.server_close()  # Joins all non-daemon handlers.
        thread.join(2)
        assert not thread.is_alive()
        assert server.socket.fileno() == -1


@pytest.fixture
def network(formal, endpoint, monkeypatch, request):
    # Only this explicit test seam permits local HTTPS in the production builder.
    monkeypatch.setattr(
        runtime,
        "build_planning_runtime",
        lambda **kw: REAL_BUILD(**kw, allow_local_https_mock=True),
    )
    monkeypatch.setattr(
        runtime.OpenAIResponsesDraftTransport, "exchange", REAL_EXCHANGE
    )
    monkeypatch.setattr(
        runtime.ExactFileOpenAICredentialResolver, "resolve", REAL_RESOLVE
    )
    document = formal.document
    document.update(
        executionClass="LOCAL_HTTPS_MOCK",
        responsesUrl=endpoint.url,
        tls={"caFile": str(endpoint.cert)},
        connectTimeoutSeconds=1,
        readTimeoutSeconds=1,
        totalTimeoutSeconds=1,
    )
    document.update(getattr(request, "param", {}))
    from pathlib import Path

    credential = Path(document["credential"]["file"])
    credential.write_text("synthetic-boundary-test-only")
    credential.chmod(0o600)
    formal.path.write_text(json.dumps(document))
    # Restore actual spawn path after the formal unit fixture's explicit seam.
    monkeypatch.setattr(
        runtime.PlanningResponsesProvider, "__init__", REAL_PROVIDER_INIT
    )
    client = formal.start()
    try:
        yield NS(client=client, state=formal, endpoint=endpoint)
    finally:
        endpoint.release.set()
        client.close()


def receipt(network, response):
    identity = response.json()["result"]["invocation"]["target"]["invocation_id"]
    # Owner/test inspection, not an added PLAN READ disclosure permission.
    assert "provider_receipt" not in response.json()["result"]
    assert "cost" not in response.json()["result"]
    return network.state.invocations.receipt(None, identity)


def result(response):
    assert response.status_code == 201, response.text
    return response.json()["result"]["result"]


@pytest.mark.parametrize(
    "network", [{"totalTimeoutSeconds": 5, "readTimeoutSeconds": 5}], indirect=True
)
@pytest.mark.parametrize("mode", ["headers", "body", "drip"])
def test_actual_local_https_deadline_reaps_and_replay_never_retries(
    network, mode, record_property
):
    from concurrent.futures import ThreadPoolExecutor

    # This case must reach the named real HTTPS phase, not test cold imports.
    # Startup remains inside total; a separate readiness gate fails explicitly
    # if it consumes the setup allowance. Shared startup tests retain short budgets.
    network.endpoint.mode = mode
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(send, network.client)
        reached = network.endpoint.accepted.wait(2.5)
        response = pending.result(timeout=7.5)
    value = result(response)
    assert time.monotonic() - started < 7.5
    assert value["technical_status"] == "OUTCOME_UNKNOWN"
    saved = receipt(network, response)
    record_property("deadline", saved["deadline"])
    assert reached, saved["deadline"]
    assert saved["deadline"]["reason"] == "TOTAL_DEADLINE"
    assert saved["deadline"]["stage"] == (
        "WAIT_HEADERS" if mode == "headers" else "READ_BODY"
    )
    assert 5 <= saved["deadline"]["decision_seconds"] < 5.5
    assert saved["deadline"]["reaped"]
    assert saved["deadline"]["cleanup_seconds"] <= 2
    assert network.endpoint.requests == 1
    assert result(send(network.client)) == value
    assert network.endpoint.requests == 1


@pytest.mark.parametrize(
    "mode,status,kind",
    [
        ("valid", "SUCCEEDED", "NEEDS_CLARIFICATION"),
        ("invalid-json", "FAILED", None),
        ("invalid-inner", "SUCCEEDED", "INVALID"),
        ("oversized", "FAILED", None),
    ],
)
def test_local_https_outputs_and_metering_are_independent(
    network, mode, status, kind, record_property
):
    network.endpoint.mode = mode
    response = send(network.client)
    value = result(response)
    saved = receipt(network, response)
    record_property("deadline", saved["deadline"])
    assert value["technical_status"] == status, saved["deadline"]
    assert value["kind"] == kind
    assert saved["deadline"]["reaped"]
    assert not value.get("proposal")
    assert network.endpoint.requests == 1


def test_permission_denial_starts_no_worker_and_zero_network(network, monkeypatch):
    from agent_console import responses_deadline

    def forbidden(*args, **kwargs):
        pytest.fail("Permission denial must precede worker creation")

    monkeypatch.setattr(responses_deadline, "supervise", forbidden)
    network.state.denied = True
    response = send(network.client)
    assert response.status_code == 404
    assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
    assert network.endpoint.requests == 0


def test_client_cancellation_reaps_and_persists_unknown(network, record_property):
    network.endpoint.mode = "cancel"

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=network.client.app),
            base_url="https://testserver",
        ) as client:
            task = asyncio.create_task(
                client.post(
                    "/api/workbench/v1/planning-v2/invocations",
                    json={"target": sample()["target"], "idempotency_key": "cancel"},
                    headers={"x-csrf-token": "test-csrf"},
                )
            )
            reached = await asyncio.to_thread(network.endpoint.accepted.wait, 3)
            record_property("endpoint_reached_before_cancel", reached)
            record_property("before_cancel_task_done", task.done())
            if task.done() and not task.cancelled() and task.exception() is None:
                record_property(
                    "deadline_before_cancel",
                    receipt(network, task.result())["deadline"],
                )
            assert reached, (
                receipt(network, task.result())["deadline"]
                if task.done() and not task.cancelled() and task.exception() is None
                else "endpoint not reached before cancellation"
            )
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(exercise())
    response = send(network.client, idempotency_key="cancel")
    assert result(response)["technical_status"] == "OUTCOME_UNKNOWN"
    d = receipt(network, response)["deadline"]
    assert d["reason"] == "CANCELLED"
    assert d["reaped"]
    assert network.endpoint.requests == 1


@pytest.mark.parametrize(
    "phase", ["DNS", "TCP", "TLS", "SEND_REQUEST", "VALIDATE_RESPONSE", "CLOSE"]
)
def test_formal_worker_phase_substitutes_are_bounded(
    network, monkeypatch, phase, record_property
):
    from agent_console import responses_deadline
    from deadline_test_clock import DeadlineClock
    from responses_deadline_test_jobs import NetworkPhaseJob

    original = responses_deadline.supervise
    clock = DeadlineClock()
    reached = network.endpoint.cert.parent / f"stalled-{phase}"
    loads = responses_deadline.json.loads

    def stage_message(data):
        message = loads(data)
        if message == {"stage": phase} and reached.exists():
            clock.after_stage_read()
        return message

    # Test the deadline decision at the actual worker phase, independently of
    # host scheduling. Real startup/HTTPS total-bound tests keep the real clock.
    monkeypatch.setattr(responses_deadline, "time", NS(monotonic=clock.monotonic))
    monkeypatch.setattr(
        responses_deadline,
        "json",
        NS(loads=stage_message, dumps=json.dumps),
    )

    def stage_supervise(job, configuration):
        return original(NetworkPhaseJob(job, phase, str(reached)), configuration)

    monkeypatch.setattr(responses_deadline, "supervise", stage_supervise)
    response = send(network.client)
    value = result(response)
    d = receipt(network, response)["deadline"]
    assert value["technical_status"] == "OUTCOME_UNKNOWN"
    record_property("deadline", d)
    assert d["stage"] == phase
    assert d["reason"] == "TOTAL_DEADLINE"
    assert d["reaped"]
    assert d["decision_seconds"] < 1.6
    assert not clock.wall_guard_fired
    assert reached.exists()  # the injected function ran, not only a phase label
    assert time.monotonic() - clock.started < clock.wall_limit + 2
    assert network.endpoint.requests == (
        1 if phase in {"VALIDATE_RESPONSE", "CLOSE"} else 0
    )


@pytest.mark.parametrize(
    "network", [{"totalTimeoutSeconds": 5, "readTimeoutSeconds": 5}], indirect=True
)
def test_actual_local_https_retains_separate_ids_and_usage(network):
    response = send(network.client)
    saved = receipt(network, response)
    m = saved["measurement"]
    assert m["provider_request_id"] == "req-local-323"
    assert m["provider_response_id"] == "resp-local-323"
    assert m["local_request_id"] != m["provider_request_id"]
    assert m["usage"]["input_tokens"] == 30
    assert m["usage"]["cached_tokens"] == 7
    assert m["settleable"]


def test_cleanup_failure_blocks_subsequent_dispatch(network, monkeypatch):
    from agent_console import responses_deadline

    calls = []

    def failed(*args, **kwargs):
        calls.append(True)
        raise responses_deadline.ResponsesBoundaryError(
            {"reason": "CLEANUP_FAILURE", "reaped": False}
        )

    monkeypatch.setattr(responses_deadline, "supervise", failed)
    first = send(network.client)
    assert result(first)["technical_status"] == "OUTCOME_UNKNOWN"
    second = send(network.client, idempotency_key="after-cleanup-failure")
    assert result(second)["technical_status"] == "OUTCOME_UNKNOWN"
    assert len(calls) == 1
    assert network.endpoint.requests == 0


def test_actual_tcp_peer_stalled_tls_is_reaped(network, monkeypatch, record_property):
    from dataclasses import replace
    from socketserver import BaseRequestHandler, ThreadingTCPServer

    from agent_console import responses_deadline

    accepted, release = threading.Event(), threading.Event()

    class SilentTLS(BaseRequestHandler):
        def handle(self):
            accepted.set()
            release.wait(4)

    peer = ThreadingTCPServer(("127.0.0.1", 0), SilentTLS)
    peer.daemon_threads = False
    thread = threading.Thread(target=peer.serve_forever)
    thread.start()
    original = responses_deadline.supervise

    def local_tls_peer(job, configuration):
        config = replace(
            configuration,
            responses_url=f"https://127.0.0.1:{peer.server_address[1]}/v1/responses",
        )
        return original(replace(job, configuration=config), config)

    monkeypatch.setattr(responses_deadline, "supervise", local_tls_peer)
    try:
        response = send(network.client)
        assert accepted.is_set()
        assert result(response)["technical_status"] == "OUTCOME_UNKNOWN"
        diagnostic = receipt(network, response)["deadline"]
        record_property("deadline", diagnostic)
        assert diagnostic["reaped"]
        assert diagnostic["stage"] == "CONNECT"
        assert network.endpoint.requests == 0
        assert result(send(network.client)) == result(response)
    finally:
        release.set()
        peer.shutdown()
        peer.server_close()
        thread.join(2)
        assert not thread.is_alive()
        assert peer.socket.fileno() == -1
