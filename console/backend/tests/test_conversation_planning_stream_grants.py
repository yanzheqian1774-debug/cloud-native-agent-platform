"""Real BFF session/CSRF and persistent exact grants; no provider traffic."""

# ruff: noqa: F401, F811 -- Reuse isolated database fixtures.
import threading

import pytest
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.grant_administration_application import GrantRevocationCommand
from agent_console.model_stream_api import model_response, stream_authorization
from agent_console.response_stream import SINK
from agent_console.responses_deadline import CANCEL
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from fastapi import Request
from fastapi.testclient import TestClient
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_planning_admission import ordinary
from test_conversation_work_authorization import decisions, work
from test_local_accounts_postgres import login, setup


def test_after_only_backfills_missing_read_without_recreating_problem(
    work, monkeypatch
):
    e = work
    original = e.work._issue

    def previous_issue(context, resolve):
        def legacy(c):
            source, grants = resolve(c)
            return source, {
                g for g in grants if g.owner != "PLAN" or g.action != "READ"
            }

        return original(context, legacy)

    monkeypatch.setattr(e.work, "_issue", previous_issue)
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    before = decisions(e)
    monkeypatch.setattr(e.work, "_issue", original)
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    after = decisions(e)
    assert len(after) == len(before) + 1
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    assert decisions(e) == after


@pytest.mark.parametrize("mode", ["exact", "missing", "other", "revoked"])
def test_bff_stream_requires_current_exact_problem_read(work, setup, mode):
    e = work
    _, _, sessions, _ = setup
    secret = login(sessions, "reviewer324")
    session, context = sessions.authenticate_session(secret.value)
    if mode != "missing":
        e.work.after(context, "CREATE_PROBLEM", e.create, e.created)
    if mode == "revoked":
        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants "
                "WHERE owner='PLAN' AND action='READ'"
            ).fetchone()
        e.work.grants.revoke_grant(
            context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "stream-withdrawal",
                surrender=True,
            ),
        )
        # Replaying admission cannot restore a deliberately withdrawn read.
        e.work.after(context, "CREATE_PROBLEM", e.create, e.created)

    observed = threading.Event()
    calls, identities, cancelled = [], [], []
    target = "other-problem" if mode == "other" else "ordinary-new-problem"

    def read(principal, identity):
        identities.append((principal.principal_id, identity))
        allowed = e.work.grants.authorization.has_current_grant(
            principal,
            ExactGrant("PLAN", "READ", "plan:prepared:" + target),
            now=sessions.clock(),
            generation=e.work.grants.generation.generation,
            recovery_epoch=e.work.grants.recovery_epoch,
        )
        if not allowed:
            raise AuthorityError("READ_DENIED")
        observed.set()

    def action():
        calls.append("one-dispatch")
        SINK.get()({"invocationId": "isolated-planning", "stage": "CONNECT"})
        signal = CANCEL.get()
        for _ in range(100):
            if signal.wait(0.01) or observed.is_set():
                break
        cancelled.append(signal.is_set())
        return {"state": "CONTROLLED_OFFLINE_RESULT"}

    def install(app, authenticate, require_csrf, policy):
        @app.post(PREFIX + "/isolated-planning-stream")
        async def begin(request: Request):
            return await model_response(
                request,
                action,
                stream_authorization(request, authenticate, require_csrf, read),
            )

    app = create_workbench_bff(
        sessions,
        e.work.grants,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        route_installers=(install,),
    )
    with TestClient(app, base_url="https://console.example") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)
        response = client.post(
            PREFIX + "/isolated-planning-stream",
            headers={
                "origin": "https://console.example",
                "x-csrf-token": sessions.issue_csrf(session),
                "accept": "text/event-stream",
            },
        )
    assert response.status_code == 200
    assert calls == ["one-dispatch"]
    assert identities and set(identities) == {
        (context.principal_id, "isolated-planning")
    }
    if mode == "exact":
        assert len(identities) >= 2  # Progress and final result each recheck READ.
        assert "event: result" in response.text
        assert "event: error" not in response.text
        assert cancelled == [False]
    else:
        assert "event: error" in response.text
        assert "event: result" not in response.text
        assert cancelled == [True]
