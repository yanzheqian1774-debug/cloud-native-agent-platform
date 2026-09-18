"""Characterize the formal planning path, not Kimi supervision.

Real local TLS/HTTP exchange; synthetic credentials/data; owner/BFF dependencies
are the explicit formal-assembly test doubles. Gates release in finally, so a
missing production deadline cannot leave a test worker or listener behind.
These assertions document limitations, not acceptance of real-model readiness.
"""

import asyncio
import http.client
import json
import socket
import ssl
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace as NS

import httpx
import pytest
from agent_console import plan_suggestion_runtime as runtime
from agent_console.plan_suggestion_invocation import PlanningProviderResult
from test_plan_suggestion_v2 import sample
from test_planning_runtime import formal as formal
from test_planning_runtime import send

REAL_EXCHANGE = runtime.OpenAIResponsesDraftTransport.exchange
REAL_RESOLVE = runtime.ExactFileOpenAICredentialResolver.resolve
REAL_BUILD = runtime.build_planning_runtime


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
        accepted=threading.Event(),
        release=threading.Event(),
        stopped=threading.Event(),
    )

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["content-length"]))
            state.requests += 1
            state.accepted.set()
            inner = {"kind": "NEEDS_CLARIFICATION", "questions": ["Synthetic date?"]}
            if state.mode == "invalid-inner":
                inner = {"unsupported": True}
            body = json.dumps(
                {
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
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if state.mode == "body":
                    state.release.wait(5)
                if state.mode == "drip":
                    # Each inter-byte wait is below read timeout, cumulative > total.
                    size = (len(body) + 5) // 6
                    for offset in range(0, len(body), size):
                        self.wfile.write(body[offset : offset + size])
                        self.wfile.flush()
                        if state.stopped.wait(0.25):
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
def network(formal, endpoint, monkeypatch):
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
    from pathlib import Path

    credential = Path(document["credential"]["file"])
    credential.write_text("synthetic-boundary-test-only")
    credential.chmod(0o600)
    formal.path.write_text(json.dumps(document))
    connections, responses = [], []
    original_response = http.client.HTTPConnection.getresponse

    def getresponse(self):
        response = original_response(self)
        responses.append(response)
        return response

    monkeypatch.setattr(http.client.HTTPConnection, "getresponse", getresponse)
    original_init = http.client.HTTPSConnection.__init__

    def init(self, host, *args, **kwargs):
        assert host == "127.0.0.1", "No external endpoint permitted"
        original_init(self, host, *args, **kwargs)
        connections.append(self)

    monkeypatch.setattr(http.client.HTTPSConnection, "__init__", init)
    client = formal.start()
    try:
        yield NS(
            client=client,
            state=formal,
            endpoint=endpoint,
            connections=connections,
            responses=responses,
        )
    finally:
        endpoint.release.set()
        client.close()
        for response in responses:
            response.close()  # Test hygiene even when ownership assertion fails.
        assert all(connection.sock is None for connection in connections)


def result(response):
    assert response.status_code == 201, response.text
    return response.json()["result"]["result"]


@pytest.mark.parametrize("mode", ["headers", "body"])
def test_real_local_socket_timeout_is_unknown_and_replay_does_not_retry(network, mode):
    network.endpoint.mode = mode
    started = time.monotonic()
    value = result(send(network.client))
    assert 0.8 <= time.monotonic() - started < 4
    assert value["technical_status"] == "OUTCOME_UNKNOWN"
    assert value["reason"] == "PROVIDER_OUTCOME_UNKNOWN"
    assert result(send(network.client)) == value
    assert network.endpoint.requests == 1
    assert all(c.sock is None for c in network.connections)


@pytest.mark.parametrize("phase", ["dns", "tcp", "tls", "send", "close"])
def test_phase_gate_exposes_missing_independent_deadline(network, monkeypatch, phase):
    entered, release = threading.Event(), threading.Event()
    owner, name = {
        "dns": (socket, "getaddrinfo"),
        "tcp": (socket.socket, "connect"),
        "tls": (ssl.SSLContext, "wrap_socket"),
        "send": (http.client.HTTPSConnection, "request"),
        "close": (http.client.HTTPSConnection, "close"),
    }[phase]
    original = getattr(owner, name)

    def gate(*args, **kwargs):
        entered.set()
        assert release.wait(5), "Test gate was not released"
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, gate)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(send, network.client)
        try:
            assert entered.wait(3)
            time.sleep(1.1)
            # Caller, not a supervised worker: deadline does not release it.
            assert not future.done()
            assert network.endpoint.requests == (1 if phase == "close" else 0)
        finally:
            release.set()
        value = result(future.result(timeout=4))
    assert value["technical_status"] == (
        "OUTCOME_UNKNOWN" if phase in {"dns", "tcp", "tls"} else "SUCCEEDED"
    )
    assert network.endpoint.requests == (0 if phase in {"dns", "tcp", "tls"} else 1)


def test_slow_body_can_complete_after_configured_total(network, record_property):
    network.endpoint.mode = "drip"
    started = time.monotonic()
    value = result(send(network.client))
    elapsed = time.monotonic() - started
    record_property("elapsed_seconds", elapsed)
    assert elapsed > 1
    assert value["technical_status"] == "SUCCEEDED"
    assert value["kind"] == "NEEDS_CLARIFICATION"
    assert network.endpoint.requests == 1


@pytest.mark.parametrize(
    "mode,status,kind",
    [("invalid-json", "FAILED", None), ("invalid-inner", "SUCCEEDED", "INVALID")],
)
def test_invalid_outputs_are_not_proposals(network, mode, status, kind):
    network.endpoint.mode = mode
    value = result(send(network.client))
    assert value["technical_status"] == status
    assert value["kind"] == kind
    assert not value.get("proposal")
    assert network.endpoint.requests == 1


def test_validation_time_has_no_total_deadline(network, monkeypatch):
    original = PlanningProviderResult.model_validate_json

    def delayed(*args, **kwargs):
        time.sleep(1.1)
        return original(*args, **kwargs)

    monkeypatch.setattr(PlanningProviderResult, "model_validate_json", delayed)
    started = time.monotonic()
    assert result(send(network.client))["technical_status"] == "SUCCEEDED"
    assert time.monotonic() - started > 1
    assert all(c.sock is None for c in network.connections)


def test_permission_denial_has_zero_model_network_calls(network):
    network.state.denied = True
    response = send(network.client)
    assert response.status_code == 404
    assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
    assert network.connections == []
    assert network.endpoint.requests == 0


def test_client_cancellation_does_not_cancel_inflight_sync_exchange(
    network, monkeypatch
):
    network.endpoint.mode = "cancel"
    finished = threading.Event()
    original = network.state.invocations.finish

    def finish(*args, **kwargs):
        value = original(*args, **kwargs)
        finished.set()
        return value

    monkeypatch.setattr(network.state.invocations, "finish", finish)

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
            try:
                assert await asyncio.to_thread(network.endpoint.accepted.wait, 3)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert not finished.wait(0.1)
                assert any(c.sock is not None for c in network.connections)
            finally:
                network.endpoint.release.set()
                assert await asyncio.to_thread(finished.wait, 3)
            # There is no planning cancellation endpoint or remote cancel claim.
            response = await client.post(
                "/api/workbench/v1/planning-v2/invocations/x/cancel"
            )
            assert response.status_code == 404

    asyncio.run(exercise())
    assert (
        result(send(network.client, idempotency_key="cancel"))["technical_status"]
        == "SUCCEEDED"
    )
    assert network.endpoint.requests == 1


def test_real_tls_peer_that_never_handshakes_times_out(network, monkeypatch):
    from socketserver import BaseRequestHandler, ThreadingTCPServer

    accepted, release = threading.Event(), threading.Event()

    class SilentPeer(BaseRequestHandler):
        def handle(self):
            accepted.set()
            release.wait(4)

    peer = ThreadingTCPServer(("127.0.0.1", 0), SilentPeer)
    peer.daemon_threads = False
    thread = threading.Thread(target=peer.serve_forever)
    thread.start()
    original = http.client.HTTPSConnection.connect

    def local_peer(self):
        self.port = peer.server_address[1]
        return original(self)

    monkeypatch.setattr(http.client.HTTPSConnection, "connect", local_peer)
    try:
        value = result(send(network.client))
        assert accepted.is_set()
        assert value["technical_status"] == "OUTCOME_UNKNOWN"
        assert network.endpoint.requests == 0
        assert result(send(network.client)) == value
    finally:
        release.set()
        peer.shutdown()
        peer.server_close()
        thread.join(2)
        assert not thread.is_alive()
        assert peer.socket.fileno() == -1


@pytest.mark.parametrize("mode", ["body", "oversized"])
def test_exchange_explicitly_closes_detached_response_stream(network, mode):
    network.endpoint.mode = mode
    value = result(send(network.client))
    assert value["technical_status"] == (
        "OUTCOME_UNKNOWN" if mode == "body" else "FAILED"
    )
    assert len(network.responses) == 1
    assert network.responses[0].isclosed(), (
        "Connection: close transfers stream ownership to response"
    )
