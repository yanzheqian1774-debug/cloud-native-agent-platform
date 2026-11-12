import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from agent_console.request_timing import (
    _current,
    count,
    measured_context,
    observe_request,
    span,
)


def test_disabled_path_preserves_response_and_has_no_record(monkeypatch, caplog):
    monkeypatch.delenv("WORKBENCH_REQUEST_TIMING", raising=False)
    response = object()

    @observe_request
    async def endpoint(request, next_call):
        assert _current.get() is None
        return response

    assert asyncio.run(endpoint(None, None)) is response
    assert not caplog.records


def test_request_isolation_exception_and_sensitive_data(monkeypatch, caplog):
    monkeypatch.setenv("WORKBENCH_REQUEST_TIMING", "1")
    caplog.set_level("INFO", logger="uvicorn.error")

    @observe_request
    async def endpoint(request, next_call):
        with span("owner.handler"):
            count("directory.scanned")
            await asyncio.sleep(0)
            if request.fail:
                raise ValueError("secret-body")
        return SimpleNamespace(status_code=200)

    async def run():
        requests = [
            SimpleNamespace(
                state=SimpleNamespace(diagnostic_id=str(i)),
                scope={
                    "path": "/api/workbench/v1/resource-directory/knowledge/private",
                    "route": SimpleNamespace(path="/resource/{id}"),
                },
                fail=bool(i),
            )
            for i in range(2)
        ]
        return await asyncio.gather(
            *(endpoint(r, None) for r in requests), return_exceptions=True
        )

    results = asyncio.run(run())
    assert results[0].status_code == 200
    assert isinstance(results[1], ValueError)
    assert _current.get() is None
    records = [json.loads(r.message.split(" ", 1)[1]) for r in caplog.records]
    assert len(records) == 2
    assert {r["requestId"] for r in records} == {"0", "1"}
    for r in records:
        assert r["spans"]["directory.scanned"]["count"] == 1
        assert r["spans"]["owner.handler"]["count"] == 1
        assert "secret" not in json.dumps(r)


@pytest.mark.parametrize("suppressed", [False, True])
def test_context_preserves_cleanup_and_suppression(suppressed):
    calls = []

    @contextmanager
    def manager():
        calls.append("enter")
        try:
            yield "connection"
        except ValueError:
            calls.append("error")
            if not suppressed:
                raise
        finally:
            calls.append("exit")

    def run():
        with measured_context(manager(), "connection") as value:
            assert value == "connection"
            raise ValueError("rollback")

    if suppressed:
        run()
    else:
        with pytest.raises(ValueError, match="rollback"):
            run()
    assert calls == ["enter", "error", "exit"]


def test_real_bff_request_records_identity_without_credentials(monkeypatch, caplog):
    from test_workbench_bff import PREFIX, build_client, login

    monkeypatch.setenv("WORKBENCH_REQUEST_TIMING", "1")
    caplog.set_level("INFO", logger="uvicorn.error")
    client, _, _ = build_client()
    login(client)
    caplog.clear()
    response = client.get(f"{PREFIX}/session")
    assert response.status_code == 200
    records = [
        r.message for r in caplog.records if r.message.startswith("workbench_timing ")
    ]
    assert len(records) == 1
    record = json.loads(records[0].split(" ", 1)[1])
    assert record["spans"]["identity"]["count"] == 1
    assert record["status"] == 200
    assert record["requestId"]
    assert "opaque-session-secret" not in records[0]
    assert "human:alice" not in records[0]
    assert response.headers["Cache-Control"] == "no-store"
