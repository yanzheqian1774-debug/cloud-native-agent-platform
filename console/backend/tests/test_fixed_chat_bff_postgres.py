# ruff: noqa: F401,F811 -- Reuse the exact original immutable fixture and owners.
"""Mounted HTTP boundary over real isolated session/governance/grant owners."""

from types import SimpleNamespace

import pytest
import test_fixed_chat_delivery_postgres as original
from agent_console.authority_contracts import AuthorityError, ControlState
from agent_console.authority_foundation import (
    ActivationBarrier,
    AuthorityGenerationController,
    AuthorityReadiness,
)
from agent_console.authority_recovery import HostControlRecord, HostRecoveryControl
from agent_console.fixed_chat_api import install_fixed_chat
from agent_console.fixed_chat_read_access import FixedChatReadAccess
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from test_fixed_chat_delivery_postgres import automation, case, repository, services


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_actual_bff_mount_initial_receipt_replay_and_revocation(
    automation, monkeypatch, tmp_path
):
    a = automation
    control = HostRecoveryControl(tmp_path / "bff-control.json")
    control.replace(
        HostControlRecord(
            control_epoch=1,
            recovery_epoch=1,
            state=ControlState.ACTIVE,
            database_fingerprint="isolated-bff",
            generation=a.gen.generation,
            generation_digest=a.gen.digest,
            operator_id="operator:isolated-test",
        )
    )
    a.adapter.controller = AuthorityGenerationController(
        ActivationBarrier(a.gen),
        a.authority,
        control,
        AuthorityReadiness(a.gen.generation, a.gen.digest, 1, "isolated-bff"),
    )
    session_factory = original.BrowserSessionService
    captured = {}

    def sessions(*args, **kwargs):
        service = session_factory(*args, **kwargs)
        create = service.create_session

        def save(*args, **kwargs):
            secret = create(*args, **kwargs)
            captured.update(service=service, secret=secret.value)
            return secret

        service.create_session = save
        return service

    monkeypatch.setattr(original, "BrowserSessionService", sessions)
    prepare = FixedChatReadAccess.prepare
    calls = []

    def through_http(access, call, conversation, body):
        if call.operation == "READ_FIXED_CHAT_ACTIVITY":
            return prepare(access, call, conversation, body)
        if "client" not in captured:
            app = FastAPI()
            app.state.conversation_actions = SimpleNamespace(
                records=access.delivery.records
            )

            def authenticate(request):
                return captured["service"].authenticate_session(
                    request.headers.get("X-Session", "")
                )

            def csrf(request, session):
                captured["service"].verify_csrf(
                    request.headers.get("X-CSRF", ""), session
                )

            @app.exception_handler(WorkbenchOwnerError)
            def owner_error(request, exc):
                return JSONResponse(
                    {"reason": exc.reason_code}, status_code=exc.status_code
                )

            @app.exception_handler(AuthorityError)
            def authority_error(request, exc):
                return JSONResponse({"reason": str(exc)}, status_code=403)

            from agent_console.private_conversation import ConversationError

            @app.exception_handler(ConversationError)
            def conversation_error(request, exc):
                return JSONResponse({"reason": str(exc)}, status_code=409)

            install_fixed_chat(
                access.delivery.policy, a.adapter, a.automation, access.delivery.cursors
            )(app, authenticate, csrf, None)
            client = TestClient(app)
            session, _ = authenticate(
                SimpleNamespace(headers={"X-Session": captured["secret"]})
            )
            headers = {
                "X-Session": captured["secret"],
                "X-CSRF": captured["service"].issue_csrf(session),
            }
            captured.update(client=client, headers=headers)
        client, headers = captured["client"], captured["headers"]
        base = f"/api/workbench/v1/conversations/{conversation}/fixed-work-activity"
        captured["base"] = base
        params = dict(
            commandId=body.commandId,
            eventId=body.eventId,
            receiptDigest=body.receiptDigest,
        )
        if not calls:
            page = client.get(base, headers=headers)
            assert page.status_code == 200, page.text
            page = page.json()["result"]
            assert page["hasMore"] is False and page["nextCursor"] is None
            assert client.get(base, headers={}).status_code == 403
            assert (
                client.get(
                    base, headers=headers, params={"cursor": "tampered"}
                ).status_code
                != 200
            )
            first = client.get(base + "/read-access", headers=headers, params=params)
            assert first.status_code == 200, first.text
            first = first.json()["result"]
            assert (
                first["state"] == "NOT_PREPARED" and first["readTargetDigest"] is None
            )
            assert first["currentReadTargetDigest"] == body.readTargetDigest
            assert first["readTargetRelation"] == "INCOMPATIBLE"
            denied = client.post(
                base + "/read-access",
                headers={"X-Session": headers["X-Session"]},
                json=body.model_dump(mode="json"),
            )
            assert denied.status_code == 403, denied.text
        response = client.post(
            base + "/read-access", headers=headers, json=body.model_dump(mode="json")
        )
        calls.append(response.status_code)
        if response.status_code != 200:
            raise WorkbenchOwnerError(response.json()["reason"], response.status_code)
        result = response.json()["result"]
        status = client.get(base + "/read-access", headers=headers, params=params)
        assert status.status_code == 200, status.text
        assert status.json()["result"] == result
        return result

    monkeypatch.setattr(FixedChatReadAccess, "prepare", through_http)
    original.test_bound_committed_event_is_read_in_original_chat_without_human_model_lease(
        a, monkeypatch, tmp_path
    )
    assert calls[:3] == [
        200,
        200,
        200,
    ]  # Third is UNKNOWN after formal surrender, not success.
    assert calls[-1] != 200

    # Actual query/cursor over 21 additional coherent immutable history fixtures.
    # Not 21 actual service executions. Production fact validation stays on.
    from fixed_chat_paging_support import seed_history

    seed_history(a)
    client, headers, base = captured["client"], captured["headers"], captured["base"]
    one = client.get(base, headers=headers)
    assert one.status_code == 200, one.text
    one = one.json()["result"]
    assert len(one["items"]) == 20 and one["hasMore"] is True
    two = client.get(base, headers=headers, params={"cursor": one["nextCursor"]})
    assert two.status_code == 200, two.text
    two = two.json()["result"]
    assert (
        len(two["items"]) == 2 and two["hasMore"] is False and two["nextCursor"] is None
    )
    all_items = one["items"] + two["items"]
    assert len({i["eventId"] for i in all_items}) == 22
    assert [(i["scheduledAt"], i["eventId"]) for i in all_items] == sorted(
        [(i["scheduledAt"], i["eventId"]) for i in all_items], reverse=True
    )
    assert all(
        i["planningState"] == "REQUIRES_REVIEW"
        for i in all_items
        if i["phase"] == "PLANNING"
    )
