"""Directory owner work must not monopolize the BFF event loop."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

from agent_console.workbench_bff import PREFIX
from test_current_work_route import client_for
from test_workbench_bff import login


def test_session_read_completes_while_directory_owner_is_held():
    entered, release = Event(), Event()

    def owner(call):
        entered.set()
        assert release.wait(5)
        return {"scope": call.context.principal_id}

    client, authorizer = client_for(owner)
    with client, ThreadPoolExecutor(max_workers=2) as workers:
        login(client)
        directory = workers.submit(client.get, PREFIX + "/current-work")
        assert entered.wait(2)
        try:
            session = workers.submit(client.get, PREFIX + "/session")
            response = session.result(timeout=1)
            assert response.status_code == 200
            assert not directory.done()
        finally:
            release.set()
        assert directory.result(timeout=2).json()["result"] == {"scope": "human:alice"}
    assert len(authorizer.calls) == 1


def test_queued_directory_reauthenticates_before_its_owner_transaction():
    from dataclasses import replace

    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from agent_console.workbench_current_work import operations
    from agent_console.workbench_pagination import WorkbenchCursorCodec
    from fastapi.testclient import TestClient
    from test_workbench_bff import AuthorizerStub, SessionStub

    entered, queued, release = Event(), Event(), Event()

    class ObservedSession(SessionStub):
        def authenticate_session(self, value):
            result = super().authenticate_session(value)
            if entered.is_set():
                queued.set()
            return result

    sessions, authorizer = ObservedSession(), AuthorizerStub()

    def owner(call):
        entered.set()
        assert release.wait(5)
        return {"originalOwner": True}

    operation = replace(operations(WorkbenchCursorCodec(b"c" * 32))[0], handler=owner)
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        operations=(operation,),
    )
    with TestClient(app, base_url="https://console.example") as client:
        login(client)
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(client.get, PREFIX + "/current-work")
            assert entered.wait(2)
            second = workers.submit(client.get, PREFIX + "/current-work")
            try:
                assert queued.wait(2)
                assert len(authorizer.calls) == 1
                assert not second.done()
                sessions.logged_out = True
            finally:
                release.set()
            assert first.result(timeout=2).status_code == 200
            assert second.result(timeout=2).status_code == 401
    assert len(authorizer.calls) == 1
