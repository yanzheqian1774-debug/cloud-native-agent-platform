"""Original BFF authoring/team/session owners; isolated database, no model/START."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest
import test_fixed_work_source_postgres as source_fixture
from agent_console.fixed_work_succession_postgres import compatible, migrate
from agent_console.workbench_fixed_work_succession import operations
from fastapi.testclient import TestClient
from test_fixed_work_authoring import body

pytestmark = source_fixture.pytestmark


@pytest.fixture
def app(monkeypatch, tmp_path):
    original = source_fixture.source_operations

    def routes(owner, enabled):
        return (*original(owner, enabled=enabled), *operations(owner))

    monkeypatch.setattr(source_fixture, "source_operations", routes)
    gen = source_fixture.app.__wrapped__(monkeypatch, tmp_path)
    value = next(gen)
    try:
        with value.authority.connection_scope() as c:
            migrate(c)
            compatible(c)
        yield value
    finally:
        gen.close()


def prepare(app, client, *, upgrade_employee=False):
    authoring = source_fixture.authoring
    teams = authoring.teams
    url, headers, policy = authoring.setup(app, client)
    saved = client.post(url, json=body(), headers=headers)
    assert saved.status_code == 201, saved.text
    draft = saved.json()["result"]
    chat = source_fixture.create_conversation(app, policy, "succession-chat")
    exact = url + "/work:1/revisions/revision:1"
    handoff = client.post(
        exact + "/conversation",
        json={
            "conversationId": chat,
            "workDigest": draft["digest"],
            "commandId": "source:1",
        },
        headers=headers,
    )
    assert handoff.status_code == 200, handoff.text
    before = client.get(
        teams.PREFIX + "/teams/team:quality/revisions/team-revision:1"
    ).json()["result"]["revision"]
    team = {
        "title": before["title"],
        "goal": before["goal"],
        "ownerId": before["owner_id"],
        "workLinks": [],
        "members": [
            {
                "employeeDefinitionId": m["employee_definition_id"],
                "employeeRevisionId": m["employee_revision_id"],
                "employeeDigest": m["employee_digest"],
                "responsibility": m["responsibility"],
                "handoff": m["handoff"],
            }
            for m in before["members"]
        ],
    }
    team.update(
        teamId="team:quality",
        revisionId="team-revision:2",
        predecessorRevisionId="team-revision:1",
        expectedVersion=1,
        commandId="team:next",
    )
    if upgrade_employee:
        member = team["members"][0]
        payload = teams.employee_fixture.create_body(
            app,
            command_id="employee-successor",
            definition_id=member["employeeDefinitionId"],
        )
        payload.update(
            employeeDefinitionRevisionId="employee-revision:v2",
            predecessorEmployeeRevisionId=member["employeeRevisionId"],
            expectedVersion=1,
            role="Updated quality owner",
        )
        revised = client.post(
            teams.PREFIX + "/employees", json=payload, headers=headers
        )
        assert revised.status_code == 201, revised.text
        employee = revised.json()["result"]
        member.update(
            employeeRevisionId=employee["employeeDefinitionRevisionId"],
            employeeDigest=employee["employeeDefinitionDigest"],
        )
        teams.allow(
            app,
            "EMPLOYEE",
            "READ",
            f"employee:{member['employeeDefinitionId']}:{member['employeeRevisionId']}",
            "employee-successor-read",
        )
    team["goal"] = "升级后的合成资料核对"
    team["members"][0]["responsibility"] += "(版本更新核对)"
    created = client.post(teams.PREFIX + "/teams", json=team, headers=headers)
    assert created.status_code == 201, created.text
    teams.allow(app, "TEAM", "READ", "team:team:quality:team-revision:2", "next-read")
    after = client.get(teams.PREFIX + "/teams/team:quality/revisions/team-revision:2")
    assert after.status_code == 200, after.text
    with app.authority.connection_scope() as c:
        row = c.execute(
            "SELECT digest FROM team_definition.revisions WHERE "
            "revision_id='team-revision:2'"
        ).fetchone()
    policy["scopes"].append(
        {
            **policy["scopes"][0],
            "teamRevisionId": "team-revision:2",
            "teamDigest": row["digest"],
        }
    )
    app.policy_path.write_text(json.dumps(policy))
    command = {
        "predecessor": handoff.json()["result"]["record"]["work"],
        "predecessorHandoffDigest": handoff.json()["result"]["digest"],
        "team": {
            "resource_id": "team:quality",
            "revision_id": "team-revision:2",
            "digest": row["digest"],
        },
        "commandId": "succession:1",
    }
    return exact, headers, command, chat, draft


@pytest.mark.parametrize("upgrade_employee", [False, True])
def test_original_owner_atomic_succession_replay_history_and_current(
    app, upgrade_employee
):
    with TestClient(app.application, base_url="https://console.example") as client:
        exact, h, command, chat, draft = prepare(
            app, client, upgrade_employee=upgrade_employee
        )
        p = client.post(exact + "/succession/preview", json=command, headers=h)
        assert p.status_code == 200, p.text
        command["previewDigest"] = p.json()["result"]["previewDigest"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _: client.post(
                        exact + "/succession", json=command, headers=h
                    ),
                    range(2),
                )
            )
        assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
        result = responses[0].json()["result"]
        assert responses[1].json()["result"] == result
        record = result["record"]
        assert record["conversationId"] == chat
        read = client.get(exact + "/succession/commands/succession:1")
        assert read.status_code == 200, read.text
        assert read.json()["result"] == result
        assert client.get(exact).json()["result"] == draft
        assert (
            client.post(
                exact.rsplit("/work:1/", 1)[0], json=body(), headers=h
            ).status_code
            == 409
        )
        assert client.get(exact + "/source").json()["result"]["state"] == "SUPERSEDED"
        work = record["work"]
        newbase = (
            exact.split("/fixed-work-drafts")[0].replace(
                "team-revision:1", "team-revision:2"
            )
            + "/fixed-work-drafts"
        )
        listing = client.get(newbase)
        assert listing.status_code == 200, listing.text
        assert len(listing.json()["result"]["items"]) == 1
        assert listing.json()["result"]["items"][0]["logicalWorkId"] == "work:1"
        oldbase = exact.split("/work:1/")[0]
        assert client.get(oldbase).json()["result"]["items"] == []
        current_url = (
            newbase + "/" + work["resource_id"] + "/revisions/" + work["revision_id"]
        )
        current = client.get(current_url)
        assert current.status_code == 200, current.text
        assert current.json()["result"]["configurationRevisionFixed"] is True
        attempted = {
            **body(),
            "workId": work["resource_id"],
            "revisionId": "not-an-unlinked-clone",
            "predecessorRevisionId": work["revision_id"],
            "expectedVersion": 1,
            "commandId": "ordinary-save-after-succession",
        }
        denied = client.post(newbase, json=attempted, headers=h)
        assert denied.status_code == 409, denied.text
        assert "SUCCESSION_CONFIGURATION_FIXED" in denied.text
        assert record["preview"]["employeeCompositions"]
        newread = client.get(
            newbase
            + "/"
            + work["resource_id"]
            + "/revisions/"
            + work["revision_id"]
            + "/source"
        )
        assert newread.status_code == 200, newread.text
        assert newread.json()["result"]["state"] == "AWAITING_CONFIRMED_TARGET"
        assert (
            newread.json()["result"]["handoff"]["record"]["schemaVersion"]
            == "fixed-work-conversation.v2"
        )
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_successions.transitions"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.heads"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_sources.handoffs"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_successions.bindings"
                ).fetchone()["n"]
                == 0
            )


def test_atomic_save_failure_rolls_back_successor_and_facts(app, monkeypatch):
    from agent_console import fixed_work_authoring_postgres as store

    with TestClient(app.application, base_url="https://console.example") as client:
        exact, h, command, _chat, _draft = prepare(app, client)
        p = client.post(exact + "/succession/preview", json=command, headers=h)
        assert p.status_code == 200, p.text
        command["previewDigest"] = p.json()["result"]["previewDigest"]
        original = store.save

        def fail(*a, **kw):
            original(*a, **kw)
            raise RuntimeError("after-original-save-before-transition")

        monkeypatch.setattr(store, "save", fail)
        with pytest.raises(RuntimeError, match="after-original-save"):
            client.post(exact + "/succession", json=command, headers=h)
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.heads"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_successions.transitions"
                ).fetchone()["n"]
                == 0
            )
        monkeypatch.setattr(store, "save", original)
        assert (
            client.post(exact + "/succession", json=command, headers=h).status_code
            == 201
        )


def test_original_message_wins_shared_chat_lock_and_rejects_transition(
    app, monkeypatch
):
    from threading import Event, current_thread
    from types import SimpleNamespace

    from agent_console.authority_contracts import AuthenticationSource

    with TestClient(app.application, base_url="https://console.example") as client:
        exact, h, command, chat, _draft = prepare(app, client)
        p = client.post(exact + "/succession/preview", json=command, headers=h)
        assert p.status_code == 200, p.text
        command["previewDigest"] = p.json()["result"]["previewDigest"]
        with app.authority.connection_scope() as c:
            row = c.execute(
                "SELECT tenant_id,security_domain,owner_id FROM "
                "private_conversation.conversations WHERE conversation_id=%s",
                (chat,),
            ).fetchone()
        ctx = SimpleNamespace(
            principal_id=row["owner_id"],
            scope=SimpleNamespace(
                tenant_id=row["tenant_id"], security_domain=row["security_domain"]
            ),
            authentication_source=AuthenticationSource.BROWSER_SESSION,
        )
        locked, release = Event(), Event()
        original = app.source.conversations.owned

        def hold(c, context, identity, lock=False):
            value = original(c, context, identity, lock)
            if lock and current_thread().name.startswith("message-writer"):
                locked.set()
                assert release.wait(10)
            return value

        monkeypatch.setattr(app.source.conversations, "owned", hold)
        head = app.source.conversations.head(ctx, chat)
        with (
            ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="message-writer"
            ) as messages,
            ThreadPoolExecutor(max_workers=1) as updates,
        ):
            first = messages.submit(
                app.source.conversations.mutate,
                ctx,
                chat,
                {
                    "expectedVersion": head["conversation"]["version"],
                    "content": "开始确认目标",
                    "focusLinkId": None,
                    "idempotencyKey": "first-message",
                },
                "message",
            )
            assert locked.wait(10)
            second = updates.submit(
                client.post, exact + "/succession", json=command, headers=h
            )
            release.set()
            assert first.result(timeout=10)["identity"]
            result = second.result(timeout=10)
        assert result.status_code == 409, result.text
        assert "CONVERSATION_NOT_EMPTY" in result.text
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_successions.transitions"
                ).fetchone()["n"]
                == 0
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.heads"
                ).fetchone()["n"]
                == 1
            )


@pytest.mark.parametrize("owner,action", [("TEAM", "REVISE"), ("EMPLOYEE", "READ")])
def test_exact_revise_surrender_refuses_commit_and_no_clone(app, owner, action):
    from agent_console.authority_contracts import (
        AuthenticationSource,
        GrantId,
        TrustedRequestContext,
    )
    from agent_console.grant_administration_application import GrantRevocationCommand

    with TestClient(app.application, base_url="https://console.example") as client:
        exact, h, command, _chat, _draft = prepare(app, client)
        p = client.post(exact + "/succession/preview", json=command, headers=h)
        assert p.status_code == 200, p.text
        command["previewDigest"] = p.json()["result"]["previewDigest"]
        with app.authority.connection_scope() as c:
            row = c.execute(
                "SELECT g.grant_id,s.session_id FROM "
                "authorization_admin.grants g CROSS JOIN "
                "browser_identity.sessions s WHERE "
                "g.subject_principal_id='human:alice' AND g.owner=%s AND "
                "g.action=%s AND s.principal_id='human:alice'",
                (owner, action),
            ).fetchone()
        assert row
        ctx = TrustedRequestContext(
            "human:alice",
            source_fixture.authoring.teams.employee_fixture.SCOPE,
            row["session_id"],
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        app.grants.revoke_grant(
            ctx,
            GrantRevocationCommand(
                GrantId(row["grant_id"]),
                "DUTY_REMOVED",
                "succession-surrender",
                surrender=True,
            ),
        )
        response = client.post(exact + "/succession", json=command, headers=h)
        assert response.status_code == 404, response.text
        with app.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_successions.transitions"
                ).fetchone()["n"]
                == 0
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM fixed_work_authoring.heads"
                ).fetchone()["n"]
                == 1
            )


def test_unrelated_corrupt_chain_does_not_block_exact_work_or_chat(app):
    """Explicit corruption injection in a disposable DB, never a product write."""
    from agent_console import fixed_work_succession_postgres as store
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError
    from psycopg.types.json import Jsonb

    with TestClient(app.application, base_url="https://console.example") as client:
        exact, headers, command, chat, _ = prepare(app, client)
        value = client.post(
            exact + "/succession/preview", json=command, headers=headers
        )
        assert value.status_code == 200, value.text
        command["previewDigest"] = value.json()["result"]["previewDigest"]
        committed = client.post(exact + "/succession", json=command, headers=headers)
        assert committed.status_code == 201, committed.text
        with app.authority.connection_scope() as c:
            scope = tuple(
                c.execute(
                    "SELECT namespace,security_domain FROM "
                    "fixed_work_successions.transitions"
                )
                .fetchone()
                .values()
            )
            # Bypass immutable and FK triggers only to represent damaged storage.
            c.execute(
                "ALTER TABLE fixed_work_successions.transitions DISABLE TRIGGER ALL"
            )
            c.execute(
                "INSERT INTO fixed_work_successions.transitions VALUES "
                "(%s,%s,'unrelated',1,'human:other','other-chat','old-other','r1',"
                "'new-other','r2','other-command',%s,%s,%s)",
                (*scope, "a" * 64, "b" * 64, Jsonb({"corrupt": True})),
            )
            c.execute(
                "ALTER TABLE fixed_work_successions.transitions ENABLE TRIGGER ALL"
            )
            assert (
                store.conversation_source(c, scope, chat)["record"]["conversationId"]
                == chat
            )
            with pytest.raises(WorkbenchOwnerError, match="RECORD_CHANGED"):
                store.rows(c, scope, work_id="new-other")
        replay = client.get(exact + "/succession/commands/succession:1")
        assert replay.status_code == 200, replay.text
        assert replay.json() == committed.json()
        old = client.get(exact + "/source")
        assert old.status_code == 200, old.text
        assert old.json()["result"]["state"] == "SUPERSEDED"
        listing = client.get(exact.split("/work:1/")[0])
        assert listing.status_code == 200, listing.text
        assert listing.json()["result"]["items"] == []
