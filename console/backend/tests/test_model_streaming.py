import asyncio
import io
import json
import threading
import time
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.kimi_responses_draft_adapter import KimiResponsesDraftTransport
from agent_console.model_stream_api import model_response
from agent_console.response_stream import SINK, emit, preview, read_response
from agent_console.responses_deadline import CANCEL
from test_kimi_responses_draft_adapter import (
    _completed,
    _configuration,
    _credential_file,
    _KimiHandler,
    _profile,
    _resolver,
)
from test_kimi_responses_draft_adapter import (
    kimi_mock as kimi_mock,
)


def event(value):
    return ("data: " + json.dumps(value, ensure_ascii=False) + "\n\n").encode()


def response(data):
    r = io.BytesIO(data)
    r.status = 200
    r.getheader = lambda _: "text/event-stream"
    return r


def test_sse_preserves_final_usage_and_exposes_only_business_text():
    final = {
        "id": "r1",
        "status": "completed",
        "usage": {"input_tokens": 7, "output_tokens": 9},
        "output": [],
    }
    raw = event({"type": "response.created"}) + event(
        {"type": "response.reasoning_text.delta", "delta": "hidden-secret"}
    )
    raw += b": ping\n\n" + event(
        {"type": "response.output_text.delta", "delta": '{"description":"检查上线'}
    )
    raw += event(
        {
            "type": "response.output_text.delta",
            "delta": '说明","reasoning":"hidden-secret"}',
        }
    ) + event({"type": "response.completed", "response": final})
    seen = []
    assert (
        json.loads(
            read_response(response(raw), NS(maximum_response_bytes=10000), seen.append)
        )
        == final
    )
    assert any(x["preview"] == "检查上线" for x in seen)
    assert seen[-1]["preview"] == "检查上线说明" and seen[-1]["completed"]
    assert "hidden-secret" not in json.dumps(seen)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"data: [DONE]\n\n",
        event({"type": "response.failed"}),
        event({"type": "response.output_text.delta", "delta": "partial"}),
        b"data: broken\n\n",
        event({"type": "response.completed", "response": {"status": "in_progress"}}),
        b"x" * 10001,
    ],
)
def test_incomplete_stream_never_becomes_final(raw):
    with pytest.raises((OSError, ValueError)):
        read_response(response(raw), NS(maximum_response_bytes=10000), lambda _: None)


def test_preview_lexes_strings_without_leaking_reasoning_or_escaped_keys():
    assert (
        preview('{"reasoning":"secret", "description":"safe\\n中文", "title":"标题"}')
        == "safe\n中文\n标题"
    )
    assert preview('{"reasoning":"\\"description\\":\\"secret\\""}') == ""
    assert preview('{"description":"hello\\u4') == ""


def test_real_tls_stream_arrives_before_completion_and_has_one_request(
    kimi_mock, monkeypatch
):
    server, cert, tmp = kimi_mock
    seen = []
    final = _completed(
        {
            "kind": "NEEDS_CLARIFICATION",
            "question": "Which source?",
            "title": None,
            "description": None,
        }
    )

    def post(self):
        doc = json.loads(self.rfile.read(int(self.headers["content-length"])))
        seen.append(doc)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(event({"type": "response.created"}))
        self.wfile.flush()
        self.wfile.write(
            event(
                {
                    "type": "response.output_text.delta",
                    "delta": '{"description":"流式检查',
                }
            )
        )
        self.wfile.flush()
        time.sleep(0.7)
        self.wfile.write(event({"type": "response.completed", "response": final}))
        self.wfile.flush()

    monkeypatch.setattr(_KimiHandler, "do_POST", post)
    config = _configuration(server, cert, _credential_file(tmp))
    transport = KimiResponsesDraftTransport(config)
    p = _profile()
    credential = _resolver(config).resolve(p, "stream-one")
    request = transport.prepare(invocation_id="stream-one", content="test", profile=p)
    progress = []
    start = time.monotonic()
    token = SINK.set(lambda x: progress.append((time.monotonic() - start, x)))
    try:
        result = transport.dispatch(
            invocation_id="stream-one",
            request=request,
            credential=credential,
            profile=p,
        )
    finally:
        SINK.reset(token)
    assert len(seen) == 1 and seen[0]["stream"] is True
    assert (
        result.measurement["settleable"]
        and result.measurement["usage"]["input_tokens"] == 80
    )
    assert any(
        x.get("preview") == "流式检查"
        and at < result.local_cleanup["decision_seconds"] - 0.4
        for at, x in progress
    )
    assert result.local_cleanup["stream"]["completed"]


def test_delayed_headers_use_versioned_read_limit_without_retry(kimi_mock, monkeypatch):
    server, cert, tmp = kimi_mock
    calls = []

    def post(self):
        self.rfile.read(int(self.headers["content-length"]))
        calls.append(time.monotonic())
        time.sleep(1.3)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(
                event(
                    {
                        "type": "response.completed",
                        "response": _completed(
                            {
                                "kind": "NEEDS_CLARIFICATION",
                                "question": "source?",
                                "title": None,
                                "description": None,
                            }
                        ),
                    }
                )
            )
            self.wfile.flush()
        except OSError:
            pass

    monkeypatch.setattr(_KimiHandler, "do_POST", post)
    config = _configuration(server, cert, _credential_file(tmp))
    p = _profile()
    credential = _resolver(config).resolve(p, "limits")
    for identity, limit in [("old-independent", 1), ("new-independent", 3)]:
        transport = KimiResponsesDraftTransport(
            replace(config, read_timeout_seconds=limit)
        )
        req = transport.prepare(invocation_id=identity, content="test", profile=p)
        if limit == 1:
            with pytest.raises(DraftAssistanceError, match="TRANSPORT_AMBIGUOUS"):
                transport.dispatch(
                    invocation_id=identity,
                    request=req,
                    credential=credential,
                    profile=p,
                )
        else:
            assert transport.dispatch(
                invocation_id=identity, request=req, credential=credential, profile=p
            ).measurement["settleable"]
    assert len(calls) == 2


def test_stream_api_progress_precedes_owner_result_and_disconnect_cancels_once():
    async def check(disconnect):
        calls = []
        cancelled = threading.Event()
        checks = []

        def action():
            calls.append(1)
            emit({"kind": "stream", "invocationId": "exact", "preview": "生成中"})
            end = time.monotonic() + 0.8
            while time.monotonic() < end:
                if CANCEL.get().is_set():
                    cancelled.set()
                    return {"result": {"state": "UNKNOWN"}}
                time.sleep(0.01)
            return {"result": {"state": "DONE"}}

        r = await model_response(
            NS(headers={"accept": "text/event-stream"}), action, checks.append
        )
        chunks = []
        async for chunk in r.body_iterator:
            chunks.append(chunk)
            if disconnect and "生成中" in chunk:
                await r.body_iterator.aclose()
                break
        assert calls == [1] and "exact" in checks
        if disconnect:
            assert cancelled.is_set() and not any("event: result" in x for x in chunks)
        else:
            assert next(i for i, x in enumerate(chunks) if "生成中" in x) < next(
                i for i, x in enumerate(chunks) if "event: result" in x
            )

    asyncio.run(check(False))
    asyncio.run(check(True))


def test_stream_auth_failure_never_dispatches_and_revocation_hides_preview():
    async def denied():
        calls = []

        def authorize(_):
            raise PermissionError

        with pytest.raises(PermissionError):
            await model_response(
                NS(headers={"accept": "text/event-stream"}),
                lambda: calls.append(1),
                authorize,
            )
        assert not calls

    async def revoked():
        cancelled = threading.Event()
        calls = []

        def action():
            calls.append(1)
            emit(
                {
                    "kind": "stream",
                    "invocationId": "private",
                    "preview": "must-not-disclose",
                }
            )
            while not CANCEL.get().is_set():
                time.sleep(0.01)
            cancelled.set()
            return {"result": {"state": "UNKNOWN"}}

        def authorize(identity):
            if identity:
                raise PermissionError

        r = await model_response(
            NS(headers={"accept": "text/event-stream"}), action, authorize
        )
        chunks = [chunk async for chunk in r.body_iterator]
        assert (
            calls == [1]
            and cancelled.is_set()
            and "must-not-disclose" not in "".join(chunks)
        )
        assert "event: error" in "".join(chunks)

    asyncio.run(denied())
    asyncio.run(revoked())


def test_local_tls_headers_after_31_seconds_succeed_once_with_55_second_limit(
    kimi_mock, monkeypatch, record_property
):
    """Synthetic TLS evidence for the exact old 30 s boundary, not provider SLA."""
    server, cert, tmp = kimi_mock
    calls = []

    def post(self):
        self.rfile.read(int(self.headers["content-length"]))
        calls.append(time.monotonic())
        time.sleep(31)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        self.wfile.write(
            event(
                {
                    "type": "response.completed",
                    "response": _completed(
                        {
                            "kind": "NEEDS_CLARIFICATION",
                            "question": "source?",
                            "title": None,
                            "description": None,
                        }
                    ),
                }
            )
        )
        self.wfile.flush()

    monkeypatch.setattr(_KimiHandler, "do_POST", post)
    config = replace(
        _configuration(server, cert, _credential_file(tmp)),
        read_timeout_seconds=55,
        total_timeout_seconds=60,
    )
    profile = replace(_profile(), total_timeout_seconds=60)
    transport = KimiResponsesDraftTransport(config)
    request = transport.prepare(
        invocation_id="one-31-second-request", content="test", profile=profile
    )
    credential = _resolver(config).resolve(profile, "one-31-second-request")
    started = time.monotonic()
    result = transport.dispatch(
        invocation_id="one-31-second-request",
        request=request,
        credential=credential,
        profile=profile,
    )
    elapsed = time.monotonic() - started
    record_property("controlled_tls_delay_seconds", 31)
    record_property("elapsed_seconds", elapsed)
    record_property("wire_requests", len(calls))
    assert 31 <= elapsed < 55 and len(calls) == 1
    assert result.measurement["settleable"] and result.local_cleanup["reaped"]


def test_revocation_after_preview_blocks_final_disclosure_without_redispatch():
    async def check():
        calls, reads = [], []

        def action():
            calls.append(1)
            emit({"kind": "stream", "invocationId": "exact", "preview": "provisional"})
            time.sleep(0.4)
            return {"result": {"private": "final-do-not-disclose"}}

        def authorize(identity):
            if identity:
                reads.append(identity)
                if len(reads) > 1:
                    raise PermissionError

        r = await model_response(
            NS(headers={"accept": "text/event-stream"}), action, authorize
        )
        data = "".join([chunk async for chunk in r.body_iterator])
        assert calls == [1] and reads == ["exact", "exact"]
        assert "provisional" in data and "final-do-not-disclose" not in data
        assert "event: error" in data

    asyncio.run(check())


def test_token_envelopes_do_not_consume_final_body_budget():
    final = {"status": "completed", "output": [], "usage": {"output_tokens": 6000}}
    raw = b"".join(
        event(
            {"type": "response.output_text.delta", "delta": "a", "item_id": "r" * 250}
        )
        for _ in range(6000)
    ) + event({"type": "response.completed", "response": final})
    assert len(raw) > 64000 * 8
    assert (
        json.loads(
            read_response(
                response(raw),
                NS(maximum_response_bytes=64000, maximum_output_tokens=8192),
                lambda _: None,
            )
        )
        == final
    )


def test_stream_event_limit_still_rejects_unbounded_empty_events():
    raw = event({"type": "response.created"}) * 1025
    with pytest.raises(OSError, match="EVENT_LIMIT"):
        read_response(
            response(raw),
            NS(maximum_response_bytes=10000, maximum_output_tokens=1),
            lambda _: None,
        )


def test_stream_identity_does_not_touch_session_but_owner_revocation_is_live():
    from agent_console.model_stream_api import stream_authorization

    authenticated, checked = [], []
    identity = object()
    allowed = True

    def authenticate(request):
        authenticated.append(request)
        return "session", identity

    def read(context, invocation):
        assert context is identity
        checked.append(invocation)
        if not allowed:
            raise PermissionError("revoked")

    authorize = stream_authorization(
        "request", authenticate, lambda request, session: None, read
    )
    authorize(None)
    authorize("invocation")
    authorize("invocation")
    allowed = False
    with pytest.raises(PermissionError):
        authorize("invocation")
    assert authenticated == ["request"]
    assert checked == ["invocation"] * 3
