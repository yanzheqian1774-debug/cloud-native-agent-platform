# ruff: noqa: F401,F811 -- Disposable PostgreSQL fixtures only.
from concurrent.futures import ThreadPoolExecutor

import pytest
from agent_console.conversation_journey import install
from agent_console.private_conversation import ConversationError
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from test_private_conversation import ctx, database, new, service


def test_journal_persists_and_claims_once_without_domain_effects(service):
    app = FastAPI()
    actor = ctx()

    def safe(request, action, write=False):
        if write and request.headers.get("x-csrf-token") != "test":
            return JSONResponse(status_code=403, content={"reasonCode": "CSRF"})
        try:
            return {"result": action(actor)}
        except ConversationError as e:
            return JSONResponse(status_code=e.status, content={"reasonCode": e.reason})

    install(app, service, safe)
    client = TestClient(app)
    identity = new(service)
    path = "/api/workbench/v1/conversations/" + identity + "/journey"
    assert client.get(path).json()["result"] == {"version": 0, "state": None}
    body = {"expectedVersion": 0, "state": {"phase": "UNDERSTAND", "pending": "one"}}
    assert client.post(path, json=body).status_code == 403
    with ThreadPoolExecutor(2) as pool:
        replies = list(
            pool.map(
                lambda _: client.post(
                    path, json=body, headers={"x-csrf-token": "test"}
                ),
                range(2),
            )
        )
    assert sorted(r.status_code for r in replies) == [200, 409]
    assert client.get(path).json()["result"]["state"] == body["state"]
    assert service.read(actor, identity)["messages"] == []
    assert service.read(actor, identity)["links"] == []
    actor = ctx("another")
    assert client.get(path).status_code == 404
    assert (
        client.post(
            path, json={**body, "expectedVersion": 1}, headers={"x-csrf-token": "test"}
        ).status_code
        == 404
    )
