"""Ordinary BFF handoff with real authoring/conversation stores; no model calls.

Conversation creation uses the existing owner with the isolated fixture's exact
ordinary principal. This does not claim a completed understanding/bind workflow.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_fixed_work_authoring_postgres as authoring
from agent_console.authority_contracts import AuthenticationSource
from agent_console.fixed_work_sources_postgres import compatible, migrate
from agent_console.private_conversation import PrivateConversations
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_fixed_work_source import (
    FixedWorkSourceOwner,
    source_operations,
)
from fastapi.testclient import TestClient
from test_fixed_work_authoring import body

pytestmark = authoring.pytestmark
ROOT = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def app(monkeypatch, tmp_path):
    owners = []
    original = authoring.fixed_work_operations

    def operations(path, clock, cursors):
        owner = FixedWorkSourceOwner(
            FixedWorkAuthoringOwner(path, clock, cursors), None, None
        )
        owners.append(owner)
        return (
            *original(path, clock, cursors),
            *source_operations(owner, enabled=True),
        )

    monkeypatch.setattr(authoring, "fixed_work_operations", operations)
    generator = authoring.app.__wrapped__(monkeypatch, tmp_path)
    value = next(generator)
    try:
        with value.authority.connection_scope() as c:
            c.execute((ROOT / "0046_private_conversation.sql").read_text())
            c.execute(
                "CREATE TABLE private_conversation.journeys (tenant_id text,"
                "security_domain text,conversation_id text,version bigint,state jsonb)"
            )
            migrate(c)
            compatible(c)
        value.source = owners[0]
        value.source.conversations = PrivateConversations(value.database_url, None)
        yield value
    finally:
        generator.close()


def create_conversation(app, policy, key, subject="human:alice"):
    p = policy["scopes"][0]
    context = SimpleNamespace(
        principal_id=subject,
        scope=SimpleNamespace(
            tenant_id=p["tenantId"], security_domain=p["securityDomain"]
        ),
        authentication_source=AuthenticationSource.BROWSER_SESSION,
    )
    return app.source.conversations.create(
        context, {"title": "固定工作理解", "idempotencyKey": key}
    )["conversation_id"]


def test_real_ordinary_handoff_replay_scope_and_no_authority_side_effect(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        url, headers, policy = authoring.setup(app, client)
        draft = client.post(url, json=body(), headers=headers)
        assert draft.status_code == 201, draft.text
        saved = draft.json()["result"]
        exact = url + "/work:1/revisions/revision:1"
        assert (
            client.get(exact + "/source").json()["result"]["state"] == "NO_CONVERSATION"
        )
        first = create_conversation(app, policy, "fixed-source-conversation")
        command = {
            "conversationId": first,
            "workDigest": saved["digest"],
            "commandId": "handoff:1",
        }
        with app.authority.connection_scope() as c:
            before = c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _: client.post(
                        exact + "/conversation", json=command, headers=headers
                    ),
                    range(2),
                )
            )
        response = responses[0]
        assert all(r.status_code == 200 for r in responses), [r.text for r in responses]
        assert responses[0].json()["result"] == responses[1].json()["result"]
        assert response.json()["result"]["record"]["mode"] == "TARGET_REVIEW_ONLY"
        assert (
            client.post(exact + "/conversation", json=command, headers=headers).json()[
                "result"
            ]
            == response.json()["result"]
        )
        current = client.get(exact + "/source")
        assert current.status_code == 200, current.text
        assert current.json()["result"]["state"] == "AWAITING_CONFIRMED_TARGET"
        other = create_conversation(app, policy, "other-conversation")
        conflict = client.post(
            exact + "/conversation",
            json={**command, "conversationId": other},
            headers=headers,
        )
        assert conflict.status_code == 409, conflict.text
        denied = client.post(
            exact + "/source",
            json={**command, "previewDigest": "f" * 64},
            headers=headers,
        )
        assert denied.status_code == 409, denied.text
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_sources.handoffs"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_sources.bindings"
                ).fetchone()["n"]
                == 0
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_decisions"
                ).fetchone()["n"]
                == before
            )
