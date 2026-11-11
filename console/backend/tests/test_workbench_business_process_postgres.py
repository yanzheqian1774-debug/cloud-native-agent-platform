"""Real sessions, current grants, CSRF and business drafts on disposable PostgreSQL."""

import os
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
import test_workbench_employee_commands_postgres as fixture
from agent_console.authority_contracts import AuthorityScope
from agent_console.business_process_postgres import PostgresBusinessProcessRepository
from agent_console.business_process_publication_postgres import (
    BusinessProcessPublicationRepository,
)
from agent_console.workbench_business_process import business_process_operations
from fastapi.testclient import TestClient
from test_business_process_definition import architecture, content
from test_workbench_team_postgres import allow

URL = os.environ.get("BUSINESS_PROCESS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
ROOT = "/api/workbench/v1/business-processes"


@pytest.fixture
def app(monkeypatch, request):
    monkeypatch.setattr(fixture, "DATABASE_URL", URL)
    original = fixture.employee_operations
    services = {}

    def operations(employees, cursors):
        repository = PostgresBusinessProcessRepository(employees.pool)
        repository.migrate(fixture.MIGRATIONS / "0056_business_process.sql")
        BusinessProcessPublicationRepository(employees.pool).migrate(
            fixture.MIGRATIONS / "0057_business_process_publication.sql"
        )
        from agent_console.business_process_relations_postgres import (
            BusinessProcessRelationRepository,
        )

        BusinessProcessRelationRepository(employees.pool).migrate(
            fixture.MIGRATIONS / "0058_business_capability_relations.sql"
        )
        from agent_console.business_process_relation_withdrawals import (
            BusinessRelationWithdrawalRepository,
        )

        BusinessRelationWithdrawalRepository(employees.pool).migrate(
            fixture.MIGRATIONS / "0059_business_relation_withdrawals.sql"
        )
        if getattr(request, "param", None) == "knowledge":
            from agent_console.knowledge_lifecycle_service import (
                KnowledgeLifecycleService,
            )
            from agent_console.knowledge_postgres import PostgresKnowledgeRepository

            store = PostgresKnowledgeRepository(
                employees.pool.conninfo,
                migration_path=fixture.MIGRATIONS / "0003_knowledge_operations.sql",
            )
            store.migrate()
            services["knowledge"] = KnowledgeLifecycleService(store)
        return (
            *original(employees, cursors),
            *business_process_operations(
                repository, cursors, employees=employees, services=services
            ),
        )

    monkeypatch.setattr(fixture, "employee_operations", operations)
    generator = fixture.employee_workbench.__wrapped__()
    value = next(generator)
    value.reference_services = services
    try:
        yield value
    finally:
        for service in services.values():
            service.repository.pool.close()
        generator.close()


def command(kind="PROCESS", identity="process:1", key="create:1"):
    return {
        "kind": kind,
        "objectId": "architecture" if kind == "ARCHITECTURE" else identity,
        "expectedVersion": 0,
        "commandId": key,
        "content": (architecture() if kind == "ARCHITECTURE" else content()).model_dump(
            mode="json"
        ),
    }


def grant_basics(app):
    for action, target, key in [
        ("REVISE", "business-process:architecture", "architecture-edit"),
        ("READ", "business-process:architecture", "architecture-read"),
        ("LIST", "business-process:collection", "list"),
        ("CREATE", "business-process:collection", "create"),
    ]:
        allow(app, "BUSINESS_PROCESS", action, target, key)


def test_scope_maintainer_cannot_read_or_change_another_tenant(app, monkeypatch):
    with (
        TestClient(app.application, base_url="https://console.example") as writer,
        TestClient(app.application, base_url="https://console.example") as foreign,
    ):
        headers = fixture.unsafe_headers(fixture.login(writer, "alice-secret"))
        foreign_headers = fixture.unsafe_headers(
            fixture.login(foreign, "foreign-secret")
        )
        grant_basics(app)
        save_architecture(app, writer, headers)
        response = writer.post(ROOT + "/commands", json=command(), headers=headers)
        assert response.status_code == 200
        saved = response.json()["result"]
        with monkeypatch.context() as isolated:
            isolated.setattr(fixture, "SCOPE", AuthorityScope("tenant-b", "quality"))
            for action in ("LIST", "READ_SCOPE", "MAINTAIN_SCOPE"):
                allow(
                    app,
                    "BUSINESS_PROCESS",
                    action,
                    "business-process:collection",
                    "foreign-" + action,
                    principal="human:foreign",
                )
        assert foreign.get(ROOT).json()["result"]["items"] == []
        assert foreign.get(ROOT + "/process:1").status_code == 404
        assert (
            foreign.get(
                ROOT + "/process:1", params={"revision": saved["revisionId"]}
            ).status_code
            == 404
        )
        assert foreign.get(ROOT + "/commands/create:1").status_code == 404
        change = {**command(key="foreign-revise"), "expectedVersion": 1}
        refused = foreign.post(ROOT + "/commands", json=change, headers=foreign_headers)
        # The foreign scope has no version 1: optimistic concurrency rejects it.
        # The same response for a nonexistent identity reveals no other-tenant data.
        unknown = foreign.post(
            ROOT + "/commands",
            json={
                **change,
                "objectId": "process:absent",
                "commandId": "foreign-absent",
            },
            headers=foreign_headers,
        )
        assert refused.status_code == unknown.status_code == 409
        denied_body, absent_body = refused.json(), unknown.json()
        assert denied_body.pop("requestId")
        assert absent_body.pop("requestId")
        assert (
            denied_body
            == absent_body
            == {"reasonCode": "BUSINESS_PROCESS_VERSION_CONFLICT"}
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.revisions"
                ).fetchone()["n"]
                == 2
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts"
                ).fetchone()["n"]
                == 2
            )


def save_architecture(app, client, headers):
    response = client.post(
        ROOT + "/commands",
        json=command("ARCHITECTURE", key="architecture:1"),
        headers=headers,
    )
    assert response.status_code == 200, response.text
    saved = response.json()["result"]
    allow(
        app,
        "BUSINESS_PROCESS",
        "READ",
        f"business-process:ARCHITECTURE:architecture:{saved['revisionId']}",
        "read-architecture-" + saved["revisionId"],
    )
    return saved


def test_real_identity_csrf_save_read_and_original_receipt(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        assert client.get(ROOT).status_code == 401
        csrf = fixture.login(client, "alice-secret")
        headers = fixture.unsafe_headers(csrf)
        assert (
            client.post(ROOT + "/commands", json=command(), headers=headers).status_code
            == 404
        )
        grant_basics(app)
        empty = client.get(ROOT + "/architecture").json()["result"]
        assert empty["aggregateVersion"] == 0 and empty["record"]["content"] == {
            "domains": [],
            "groups": [],
        }
        assert client.post(ROOT + "/commands", json=command()).status_code == 403
        save_architecture(app, client, headers)
        response = client.post(ROOT + "/commands", json=command(), headers=headers)
        assert response.status_code == 200, response.text
        saved = response.json()["result"]
        assert saved["executionAuthorized"] is False
        replay = client.post(
            ROOT + "/commands", json=command(), headers=headers
        ).json()["result"]
        assert replay["revisionId"] == saved["revisionId"] and replay["replayed"]
        assert client.get(ROOT + "/commands/create:1").json()["result"] == saved
        assert client.get(ROOT + "/process:1").status_code == 404
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ",
            f"business-process:PROCESS:process:1:{saved['revisionId']}",
            "read-process",
        )
        detail = client.get(ROOT + "/process:1").json()["result"]
        assert detail["record"]["content"] == content().model_dump(mode="json")
        assert client.get(ROOT).json()["result"]["items"][0]["processId"] == "process:1"
        invalid = {**command(), "actorId": "human:admin"}
        assert (
            client.post(ROOT + "/commands", json=invalid, headers=headers).status_code
            == 422
        )


def test_revocation_blocks_replay_and_original_receipt(app):
    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as admin,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        assert (
            client.post(ROOT + "/commands", json=command(), headers=headers).status_code
            == 200
        )
        fixture.login(admin, "admin-secret")
        with app.authority.pool.connection() as conn:
            session = conn.execute(
                "SELECT session_id FROM browser_identity.sessions "
                "WHERE principal_id='human:admin'"
            ).fetchone()["session_id"]
        app.grants.revoke_grant(
            fixture.TrustedRequestContext(
                "human:admin",
                fixture.SCOPE,
                session,
                fixture.AuthenticationSource.BROWSER_SESSION,
                "policy-1",
            ),
            fixture.GrantRevocationCommand(
                fixture.GrantId("grant-create"), "DUTY_REMOVED", "revoke-process-create"
            ),
        )
        assert (
            client.post(ROOT + "/commands", json=command(), headers=headers).status_code
            == 404
        )
        assert client.get(ROOT + "/commands/create:1").status_code == 404
        assert (
            client.get(
                ROOT + "/editor-access",
                params={"kind": "PROCESS", "action": "CREATE", "objectId": ""},
            ).status_code
            == 404
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts "
                    "WHERE kind='PROCESS'"
                ).fetchone()["n"]
                == 1
            )


def test_directory_filters_and_signed_cursor_do_not_expose_unreadable_process(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        for index in range(3):
            body = command(identity=f"process:{index}", key=f"create:{index}")
            result = client.post(ROOT + "/commands", json=body, headers=headers).json()[
                "result"
            ]
            if index != 1:
                allow(
                    app,
                    "BUSINESS_PROCESS",
                    "READ",
                    f"business-process:PROCESS:process:{index}:{result['revisionId']}",
                    f"read-{index}",
                )
        first = client.get(ROOT, params={"pageSize": 2, "query": "交付"}).json()[
            "result"
        ]
        assert [item["processId"] for item in first["items"]] == ["process:0"]
        assert first["nextCursor"]
        second = client.get(
            ROOT, params={"pageSize": 2, "query": "交付", "cursor": first["nextCursor"]}
        ).json()["result"]
        assert [item["processId"] for item in second["items"]] == ["process:2"]
        assert (
            client.get(
                ROOT,
                params={"pageSize": 2, "query": "other", "cursor": first["nextCursor"]},
            ).status_code
            == 422
        )
        assert (
            client.get(ROOT, params={"domainId": "other"}).json()["result"]["items"]
            == []
        )
        assert client.get(ROOT, params={"query": "%"}).json()["result"]["items"] == []


def test_reference_adapter_gap_rejected_without_partial_save(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        body = command()
        body["content"]["source_materials"] = [
            {
                "resource_id": "knowledge:unknown",
                "revision_id": "r1",
                "digest": "a" * 64,
            }
        ]
        response = client.post(ROOT + "/commands", json=body, headers=headers)
        assert (
            response.status_code == 422
            and response.json()["reasonCode"]
            == "BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE"
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.definitions "
                    "WHERE kind='PROCESS'"
                ).fetchone()["n"]
                == 0
            )


def test_editor_access_is_read_only_and_checks_specific_current_write_grant(app):
    query = {"kind": "PROCESS", "action": "CREATE", "objectId": ""}
    with TestClient(app.application, base_url="https://console.example") as client:
        assert client.get(ROOT + "/editor-access", params=query).status_code == 401
        fixture.login(client, "alice-secret")
        assert client.get(ROOT + "/editor-access", params=query).status_code == 404
        grant_basics(app)
        result = client.get(ROOT + "/editor-access", params=query)
        assert result.status_code == 200
        assert result.json()["result"] == {
            **query,
            "allowed": True,
            "executionAuthorized": False,
        }
        assert (
            client.get(
                ROOT + "/editor-access",
                params={
                    "kind": "PROCESS",
                    "action": "REVISE",
                    "objectId": "process:not-granted",
                },
            ).status_code
            == 404
        )
        assert (
            client.get(
                ROOT + "/editor-access",
                params={
                    "kind": "ARCHITECTURE",
                    "action": "CREATE",
                    "objectId": "architecture",
                },
            ).status_code
            == 422
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.definitions"
                ).fetchone()["n"]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts"
                ).fetchone()["n"]
                == 0
            )


def revoke(app, admin, grant_key, command_key):
    fixture.login(admin, "admin-secret")
    with app.authority.pool.connection() as conn:
        session = conn.execute(
            "SELECT session_id FROM browser_identity.sessions "
            "WHERE principal_id='human:admin' ORDER BY issued_at DESC LIMIT 1"
        ).fetchone()["session_id"]
    app.grants.revoke_grant(
        fixture.TrustedRequestContext(
            "human:admin",
            fixture.SCOPE,
            session,
            fixture.AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        ),
        fixture.GrantRevocationCommand(
            fixture.GrantId("grant-" + grant_key), "DUTY_REMOVED", command_key
        ),
    )


def test_scope_maintainer_and_reader_follow_new_revisions_without_new_grants(app):
    with (
        TestClient(app.application, base_url="https://console.example") as writer,
        TestClient(app.application, base_url="https://console.example") as reader,
        TestClient(app.application, base_url="https://console.example") as outsider,
    ):
        headers = fixture.unsafe_headers(fixture.login(writer, "alice-secret"))
        reader_headers = fixture.unsafe_headers(fixture.login(reader, "bob-secret"))
        fixture.login(outsider, "memberless-secret")
        grant_basics(app)
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ_SCOPE",
            "business-process:collection",
            "writer-read-scope",
        )
        allow(
            app,
            "BUSINESS_PROCESS",
            "MAINTAIN_SCOPE",
            "business-process:collection",
            "writer-maintain-scope",
        )
        allow(
            app,
            "BUSINESS_PROCESS",
            "LIST",
            "business-process:collection",
            "reader-list",
            principal="human:bob",
        )
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ_SCOPE",
            "business-process:collection",
            "reader-read-scope",
            principal="human:bob",
        )
        architecture_result = save_architecture(app, writer, headers)
        first_response = writer.post(
            ROOT + "/commands", json=command(), headers=headers
        )
        assert first_response.status_code == 200, first_response.text
        first = first_response.json()["result"]
        assert writer.get(ROOT + "/process:1").status_code == 200
        assert (
            reader.get(
                ROOT + "/architecture",
                params={"revision": architecture_result["revisionId"]},
            ).status_code
            == 200
        )
        assert reader.get(ROOT + "/process:1").status_code == 200
        assert outsider.get(ROOT + "/process:1").status_code == 404
        assert (
            reader.get(
                ROOT + "/editor-access",
                params={"kind": "PROCESS", "action": "REVISE", "objectId": "process:1"},
            ).status_code
            == 404
        )
        revised = command(key="revise:1")
        revised["expectedVersion"] = 1
        revised["content"]["purpose"] = "普通维护者补充核对范围"
        assert (
            reader.post(
                ROOT + "/commands", json=revised, headers=reader_headers
            ).status_code
            == 404
        )
        response = writer.post(ROOT + "/commands", json=revised, headers=headers)
        assert response.status_code == 200, response.text
        second = response.json()["result"]
        assert second["aggregateVersion"] == 2
        assert (
            reader.get(ROOT + "/process:1").json()["result"]["record"]["content"][
                "purpose"
            ]
            == revised["content"]["purpose"]
        )
        assert (
            reader.get(
                ROOT + "/process:1", params={"revision": first["revisionId"]}
            ).json()["result"]["record"]["content"]["purpose"]
            != revised["content"]["purpose"]
        )
        assert (
            reader.get(ROOT).json()["result"]["items"][0]["revisionId"]
            == second["revisionId"]
        )
        assert writer.get(ROOT + "/commands/revise:1").status_code == 200
        assert reader.get(ROOT + "/commands/revise:1").status_code == 404


def test_scope_role_never_overrides_exact_revocation_and_scope_revoke_takes_effect(app):
    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as admin,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ_SCOPE",
            "business-process:collection",
            "scope-read",
        )
        allow(
            app,
            "BUSINESS_PROCESS",
            "MAINTAIN_SCOPE",
            "business-process:collection",
            "scope-maintain",
        )
        save_architecture(app, client, headers)
        saved = client.post(ROOT + "/commands", json=command(), headers=headers).json()[
            "result"
        ]
        exact_read = f"business-process:PROCESS:process:1:{saved['revisionId']}"
        allow(app, "BUSINESS_PROCESS", "READ", exact_read, "specific-read")
        assert client.get(ROOT + "/process:1").status_code == 200
        revoke(app, admin, "specific-read", "revoke-specific-read")
        assert client.get(ROOT + "/process:1").status_code == 404
        assert client.get(ROOT).json()["result"]["items"] == []
        allow(
            app,
            "BUSINESS_PROCESS",
            "REVISE",
            "business-process:process:1:aggregate",
            "specific-edit",
        )
        revoke(app, admin, "specific-edit", "revoke-specific-edit")
        revised = command(key="revise:blocked")
        revised["expectedVersion"] = 1
        assert (
            client.post(ROOT + "/commands", json=revised, headers=headers).status_code
            == 404
        )
        # Another process has no exact revocation; its current scope role decides.
        other = command(identity="process:2", key="create:2")
        assert (
            client.post(ROOT + "/commands", json=other, headers=headers).status_code
            == 200
        )
        other["expectedVersion"] = 1
        other["commandId"] = "revise:2"
        assert (
            client.post(ROOT + "/commands", json=other, headers=headers).status_code
            == 200
        )
        revoke(app, admin, "scope-maintain", "revoke-scope-maintain")
        assert (
            client.post(ROOT + "/commands", json=other, headers=headers).status_code
            == 404
        )
        assert client.get(ROOT + "/commands/revise:2").status_code == 404
        revoke(app, admin, "scope-read", "revoke-scope-read")
        assert client.get(ROOT + "/process:2").status_code == 404


def test_definition_validation_uses_fixed_authorized_architecture_and_never_writes(app):
    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as admin,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        fixed = save_architecture(app, client, headers)
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ_SCOPE",
            "business-process:collection",
            "validation-reader",
        )
        body = command()
        body["content"]["activities"][0]["human_boundary"] = None
        response = client.post(ROOT + "/commands", json=body, headers=headers)
        assert response.status_code == 200
        saved = response.json()["result"]
        # Changing the live architecture must not rewrite old validation context.
        changed = {
            **command("ARCHITECTURE", key="architecture:2"),
            "expectedVersion": 1,
            "content": {"domains": [], "groups": []},
        }
        assert (
            client.post(ROOT + "/commands", json=changed, headers=headers).status_code
            == 200
        )
        detail = client.get(
            ROOT + "/process:1", params={"revision": saved["revisionId"]}
        )
        assert detail.status_code == 200
        value = detail.json()["result"]
        assert value["architecture"]["revisionId"] == fixed["revisionId"]
        assert value["architecture"]["digest"] == fixed["digest"]
        validation = value["definitionValidation"]
        assert validation["status"] == "INCOMPLETE"
        assert validation["executionAuthorized"] is False
        assert [(i["code"], i["path"]) for i in validation["issues"]] == [
            ("ACTIVITY_FACT_MISSING", "activities.0.human_boundary")
        ]
        revoke(
            app,
            admin,
            "read-architecture-" + fixed["revisionId"],
            "deny-fixed-architecture",
        )
        denied = client.get(
            ROOT + "/process:1", params={"revision": saved["revisionId"]}
        )
        assert denied.status_code == 404 and "definitionValidation" not in denied.text
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts"
                ).fetchone()["n"]
                == 3
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.revisions"
                ).fetchone()["n"]
                == 3
            )


def test_publication_keeps_current_release_while_draft_changes_and_rechecks_authority(
    app,
):
    with (
        TestClient(app.application, base_url="https://console.example") as client,
        TestClient(app.application, base_url="https://console.example") as admin,
        TestClient(app.application, base_url="https://console.example") as reader,
    ):
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        fixture.login(reader, "bob-secret")
        grant_basics(app)
        save_architecture(app, client, headers)
        for action in ("READ_SCOPE", "MAINTAIN_SCOPE"):
            allow(
                app,
                "BUSINESS_PROCESS",
                action,
                "business-process:collection",
                "publisher-" + action,
            )
        initial = client.post(
            ROOT + "/commands", json=command(), headers=headers
        ).json()["result"]
        publish = {
            "objectId": "process:1",
            "revisionId": initial["revisionId"],
            "digest": initial["digest"],
            "expectedVersion": 1,
            "commandId": "publish:1",
        }
        assert (
            client.post(
                ROOT + "/publications", json=publish, headers=headers
            ).status_code
            == 404
        )
        allow(
            app, "BUSINESS_PROCESS", "PUBLISH", "business-process:collection", "publish"
        )
        mismatch = {**publish, "digest": "f" * 64}
        assert (
            client.post(
                ROOT + "/publications", json=mismatch, headers=headers
            ).status_code
            == 409
        )
        result = client.post(ROOT + "/publications", json=publish, headers=headers)
        assert result.status_code == 200, result.text
        published = result.json()["result"]
        assert (
            published["publicationVersion"] == 1
            and published["executionAuthorized"] is False
        )
        assert published["contentVersion"] == 1 and published["state"] == "PUBLISHED"
        assert (
            client.get(ROOT + "/process:1/publication-state").json()["result"]["draft"]
            is None
        )
        replay = client.post(
            ROOT + "/publications", json=publish, headers=headers
        ).json()["result"]
        assert replay == {**published, "replayed": True}
        assert (
            client.post(
                ROOT + "/publications",
                json={**publish, "commandId": "publish:duplicate"},
                headers=headers,
            ).status_code
            == 409
        )
        modified = {**command(key="save:2"), "expectedVersion": 1}
        modified["content"]["activities"][0]["human_boundary"] = None
        draft = client.post(ROOT + "/commands", json=modified, headers=headers).json()[
            "result"
        ]
        state = client.get(ROOT + "/process:1/publication-state").json()["result"]
        assert state["published"]["revisionId"] == initial["revisionId"]
        assert state["draft"]["revisionId"] == draft["revisionId"]
        incomplete = {
            **publish,
            "revisionId": draft["revisionId"],
            "digest": draft["digest"],
            "expectedVersion": 2,
            "commandId": "publish:incomplete",
        }
        denied = client.post(ROOT + "/publications", json=incomplete, headers=headers)
        assert denied.status_code == 422
        assert denied.json()["reasonCode"] == "BUSINESS_PROCESS_DEFINITION_INCOMPLETE"
        assert (
            client.post(
                ROOT + "/publications",
                json={**publish, "commandId": "publish:stale"},
                headers=headers,
            ).status_code
            == 409
        )
        # Original result remains recoverable even after a later draft was saved.
        assert (
            client.get(ROOT + "/publications/publish:1").json()["result"] == published
        )
        modified["content"]["activities"][0]["human_boundary"] = (
            "已确认本活动无人工保留事项"
        )
        modified.update(expectedVersion=2, commandId="save:3")
        final = client.post(ROOT + "/commands", json=modified, headers=headers).json()[
            "result"
        ]
        final_command = {
            **publish,
            "revisionId": final["revisionId"],
            "digest": final["digest"],
            "expectedVersion": 3,
            "commandId": "publish:2",
        }
        result = client.post(
            ROOT + "/publications", json=final_command, headers=headers
        )
        assert result.status_code == 200, result.text
        latest = result.json()["result"]
        assert latest["publicationVersion"] == 2
        state = client.get(ROOT + "/process:1/publication-state").json()["result"]
        assert state["published"] == latest and state["draft"] is None
        assert client.get(
            ROOT + "/process:1", params={"revision": initial["revisionId"]}
        ).json()["result"]["record"]["content"] == content().model_dump(mode="json")
        allow(
            app,
            "BUSINESS_PROCESS",
            "PUBLISH",
            "business-process:collection",
            "reader-publish",
            principal="human:bob",
        )
        assert reader.get(ROOT + "/publications/publish:1").status_code == 404
        history = client.get(
            ROOT + "/process:1", params={"revision": initial["revisionId"]}
        ).json()["result"]
        assert history["publicationState"]["selectedState"] == "HISTORICAL_PUBLISHED"
        assert client.get(ROOT).json()["result"]["items"][0]["state"] == "PUBLISHED"
        allow(
            app,
            "BUSINESS_PROCESS",
            "READ",
            f"business-process:PROCESS:process:1:{initial['revisionId']}",
            "history-only",
        )
        revoke(app, admin, "publisher-READ_SCOPE", "revoke-read-scope")
        restricted = client.get(
            ROOT + "/process:1", params={"revision": initial["revisionId"]}
        )
        assert restricted.status_code == 200
        state = restricted.json()["result"]["publicationState"]
        assert state["currentStateAvailable"] is False
        assert state["selectedState"] == "PUBLISHED_VERSION"
        assert state["published"] is None and state["draft"] is None
        assert final["revisionId"] not in restricted.text
        revoke(app, admin, "publish", "revoke-publish")
        assert client.get(ROOT + "/publications/publish:1").status_code == 404
        assert (
            client.post(
                ROOT + "/publications", json=final_command, headers=headers
            ).status_code
            == 404
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == 2
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts"
                ).fetchone()["n"]
                == 4
            )


def test_concurrent_publish_and_save_preserve_release_and_history(
    app,
):
    with (
        TestClient(app.application, base_url="https://console.example") as first,
        TestClient(app.application, base_url="https://console.example") as second,
    ):
        headers = [
            fixture.unsafe_headers(fixture.login(c, "alice-secret"))
            for c in (first, second)
        ]
        grant_basics(app)
        save_architecture(app, first, headers[0])
        for action in ("READ_SCOPE", "MAINTAIN_SCOPE", "PUBLISH"):
            allow(
                app,
                "BUSINESS_PROCESS",
                action,
                "business-process:collection",
                "concurrent-" + action,
            )
        initial = first.post(
            ROOT + "/commands", json=command(), headers=headers[0]
        ).json()["result"]
        publish = {
            "objectId": "process:1",
            "revisionId": initial["revisionId"],
            "digest": initial["digest"],
            "expectedVersion": 1,
            "commandId": "publish:one",
        }
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(c.post, ROOT + "/publications", json=publish, headers=h)
                for c, h in zip((first, second), headers, strict=True)
            ]
            results = [f.result(timeout=30) for f in futures]
        assert [r.status_code for r in results] == [200, 200]
        assert sorted(r.json()["result"]["replayed"] for r in results) == [False, True]
        draft_command = {**command(key="save:second"), "expectedVersion": 1}
        draft = first.post(
            ROOT + "/commands", json=draft_command, headers=headers[0]
        ).json()["result"]
        next_publish = {
            **publish,
            "revisionId": draft["revisionId"],
            "digest": draft["digest"],
            "expectedVersion": 2,
            "commandId": "publish:two",
        }
        next_save = {**command(key="save:third"), "expectedVersion": 2}
        with ThreadPoolExecutor(max_workers=2) as executor:
            publication = executor.submit(
                first.post,
                ROOT + "/publications",
                json=next_publish,
                headers=headers[0],
            )
            saving = executor.submit(
                second.post, ROOT + "/commands", json=next_save, headers=headers[1]
            )
            result, saved = publication.result(timeout=30), saving.result(timeout=30)
        assert saved.status_code == 200
        assert result.status_code in {200, 409}
        state = first.get(ROOT + "/process:1/publication-state").json()["result"]
        assert state["draft"]["revisionId"] == saved.json()["result"]["revisionId"]
        assert (
            state["published"]["revisionId"]
            == (draft if result.status_code == 200 else initial)["revisionId"]
        )
        with app.authority.pool.connection() as conn:
            expected = 2 if result.status_code == 200 else 1
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == expected
            )
            with (
                pytest.raises(
                    psycopg.errors.RaiseException,
                    match="BUSINESS_PROCESS_IMMUTABLE_RECORD",
                ),
                conn.transaction(),
            ):
                conn.execute(
                    "UPDATE business_process.publications SET actor_id='human:other'"
                )


def test_publication_does_not_certify_unadapted_resource_references(app):
    from agent_console.business_process_definition import BusinessProcessContent
    from agent_console.execution_domain import ScopeIdentity

    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        for action in ("READ_SCOPE", "PUBLISH"):
            allow(
                app,
                "BUSINESS_PROCESS",
                action,
                "business-process:collection",
                "reference-" + action,
            )
        candidate = content().model_dump(mode="json")
        candidate["source_materials"] = [
            {
                "resource_id": "knowledge:one",
                "revision_id": "revision:one",
                "digest": "a" * 64,
            }
        ]
        # Simulate an imported fixed record. Public save already rejects these until C.
        with app.authority.pool.connection() as conn, conn.transaction():
            saved = PostgresBusinessProcessRepository.save_process(
                conn,
                ScopeIdentity(fixture.SCOPE.tenant_id, fixture.SCOPE.security_domain),
                "process:external",
                BusinessProcessContent.model_validate(candidate),
                expected_version=0,
                command_id="imported",
                actor_id="human:alice",
                decision_id="decision:import-test",
            )
        response = client.post(
            ROOT + "/publications",
            headers=headers,
            json={
                "objectId": saved["objectId"],
                "revisionId": saved["revisionId"],
                "digest": saved["digest"],
                "expectedVersion": 1,
                "commandId": "publish:external",
            },
        )
        assert response.status_code == 422
        assert (
            response.json()["reasonCode"]
            == "BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE"
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == 0
            )


def test_fixed_employee_reference_requires_read_and_matching_digest(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        allow(
            app,
            "AGENT",
            "READ",
            f"agent:{app.agent_id}:{app.agent_revision_id}",
            "reference-agent",
        )
        employee_id = "employee-definition:business-reference"
        created = client.post(
            "/api/workbench/v1/employees",
            json=fixture.create_body(
                app,
                command_id="employee-command:business-reference",
                definition_id=employee_id,
            ),
            headers=headers,
        )
        assert created.status_code == 201, created.text
        employee = created.json()["result"]
        body = command(key="fixed-employee-save")
        reference = {
            "resource_id": employee_id,
            "revision_id": employee["employeeDefinitionRevisionId"],
            "digest": employee["employeeDefinitionDigest"],
        }
        body["content"]["activities"][0]["employee"] = reference
        denied = client.post(ROOT + "/commands", json=body, headers=headers)
        assert denied.status_code == 404, denied.text
        allow(
            app,
            "EMPLOYEE",
            "READ",
            f"employee:{employee_id}:{reference['revision_id']}",
            "reference-employee",
        )
        reference["digest"] = "0" * 64
        mismatch = client.post(ROOT + "/commands", json=body, headers=headers)
        assert mismatch.status_code == 422, mismatch.text
        assert (
            mismatch.json()["reasonCode"]
            == "BUSINESS_PROCESS_REFERENCE_VERSION_MISMATCH"
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts "
                    "WHERE kind='PROCESS'"
                ).fetchone()["n"]
                == 0
            )
        reference["digest"] = employee["employeeDefinitionDigest"]
        saved = client.post(ROOT + "/commands", json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        assert saved.json()["result"]["executionAuthorized"] is False
        with app.authority.pool.connection() as conn:
            record = conn.execute(
                "SELECT record FROM business_process.revisions WHERE kind='PROCESS'"
            ).fetchone()["record"]
            activity = record["content"]["activities"][0]
            assert activity["employee"] == reference
            assert activity["responsible_role"] == "业务专员"
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.receipts "
                    "WHERE kind='PROCESS'"
                ).fetchone()["n"]
                == 1
            )
        for action in ("READ_SCOPE", "PUBLISH"):
            allow(
                app,
                "BUSINESS_PROCESS",
                action,
                "business-process:collection",
                "employee-business-" + action,
            )
        result = saved.json()["result"]
        publication = {
            "objectId": result["objectId"],
            "revisionId": result["revisionId"],
            "digest": result["digest"],
            "expectedVersion": 1,
            "commandId": "publish:employee-business",
        }
        rejected = client.post(
            ROOT + "/publications", json=publication, headers=headers
        )
        assert rejected.status_code == 422, rejected.text
        assert (
            rejected.json()["reasonCode"] == "BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED"
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == 0
            )
        aggregate = f"employee:{employee_id}:aggregate"
        for action in ("VALIDATE", "PUBLISH"):
            allow(app, "EMPLOYEE", action, aggregate, "employee-lifecycle-" + action)
        allow(
            app,
            "EMPLOYEE",
            "APPROVE",
            aggregate,
            "employee-lifecycle-approve",
            principal="human:bob",
        )
        allow(
            app,
            "AGENT",
            "READ",
            f"agent:{app.agent_id}:{app.agent_revision_id}",
            "reference-agent-bob",
            principal="human:bob",
        )
        path = (
            f"/api/workbench/v1/employees/{employee_id}/revisions/"
            f"{reference['revision_id']}"
        )
        change = {
            "employeeDefinitionDigest": reference["digest"],
            "expectedVersion": 1,
            "commandId": "validate:reference",
        }
        validated = client.post(path + "/validation", json=change, headers=headers)
        assert validated.status_code == 200, validated.text
        with TestClient(
            app.application, base_url="https://console.example"
        ) as reviewer:
            reviewer_headers = fixture.unsafe_headers(
                fixture.login(reviewer, "bob-secret")
            )
            approved = reviewer.post(
                path + "/approvals",
                json={**change, "expectedVersion": 2, "commandId": "approve:reference"},
                headers=reviewer_headers,
            )
            assert approved.status_code == 200, approved.text
        published = client.post(
            path + "/publication",
            json={**change, "expectedVersion": 3, "commandId": "publish:reference"},
            headers=headers,
        )
        assert published.status_code == 200, published.text
        published_process = client.post(
            ROOT + "/publications", json=publication, headers=headers
        )
        assert published_process.status_code == 200, published_process.text
        assert published_process.json()["result"]["executionAuthorized"] is False
        replay = client.post(ROOT + "/publications", json=publication, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["result"]["replayed"] is True
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == 1
            )


@pytest.mark.parametrize("app", ["knowledge"], indirect=True)
def test_real_knowledge_reference_publication_and_archive_boundary(app):
    service = app.reference_services["knowledge"]
    scope = service.scope(fixture.SCOPE.tenant_id, fixture.SCOPE.security_domain)
    knowledge = service.create(
        scope,
        "human:alice",
        "工单说明(合成测试)",
        {
            "sourceId": "source:business-reference",
            "documentId": "document:guide",
            "provenance": "human:alice",
            "content": "核对工单后由责任人交接。",
        },
    )["knowledge"]
    identity = knowledge["knowledgeId"]
    revision = knowledge["revisions"][0]
    with TestClient(app.application, base_url="https://console.example") as client:
        headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
        grant_basics(app)
        save_architecture(app, client, headers)
        for action in ("READ_SCOPE", "PUBLISH"):
            allow(
                app,
                "BUSINESS_PROCESS",
                action,
                "business-process:collection",
                "knowledge-process-" + action,
            )
        body = command(key="knowledge-linked-save")
        reference = {
            "resource_id": identity,
            "revision_id": revision["revisionId"],
            "digest": revision["digest"],
        }
        body["content"]["source_materials"] = [reference]
        denied = client.post(ROOT + "/commands", json=body, headers=headers)
        assert denied.status_code == 404, denied.text
        allow(
            app,
            "KNOWLEDGE",
            "READ_RESOURCE",
            f"knowledge:prepared-resource:{identity}:{revision['revisionId']}",
            "knowledge-read",
        )
        saved = client.post(ROOT + "/commands", json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        result = saved.json()["result"]
        publication = {
            "objectId": result["objectId"],
            "revisionId": result["revisionId"],
            "digest": result["digest"],
            "expectedVersion": 1,
            "commandId": "knowledge-process-publish",
        }
        not_published = client.post(
            ROOT + "/publications", json=publication, headers=headers
        )
        assert not_published.status_code == 422, not_published.text
        assert (
            not_published.json()["reasonCode"]
            == "BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED"
        )
        service.validate(scope, identity, "human:alice", 1)
        service.review(scope, identity, "human:bob", 2, revision["digest"])
        service.publish(scope, identity, "human:alice", 3, revision["digest"])
        published = client.post(
            ROOT + "/publications", json=publication, headers=headers
        )
        assert published.status_code == 200, published.text
        assert published.json()["result"]["executionAuthorized"] is False
        service.archive(scope, identity, "human:alice", 4)
        body.update(
            objectId="process:archived-reference", commandId="archived-source-save"
        )
        archived_draft = client.post(ROOT + "/commands", json=body, headers=headers)
        assert archived_draft.status_code == 200, archived_draft.text
        changed = archived_draft.json()["result"]
        refused = client.post(
            ROOT + "/publications",
            json={
                **publication,
                "objectId": changed["objectId"],
                "revisionId": changed["revisionId"],
                "digest": changed["digest"],
                "commandId": "archived-source-publish",
            },
            headers=headers,
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["reasonCode"] == "BUSINESS_PROCESS_REFERENCE_UNAVAILABLE"
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.publications"
                ).fetchone()["n"]
                == 1
            )
            contents = conn.execute(
                "SELECT record FROM business_process.revisions WHERE kind='PROCESS'"
            ).fetchall()
            assert len(contents) == 2
            assert all(
                row["record"]["content"]["source_materials"] == [reference]
                for row in contents
            )
        detail = client.get(
            ROOT + "/" + result["objectId"], params={"revision": result["revisionId"]}
        )
        assert detail.status_code == 200, detail.text
        available = detail.json()["result"]
        assert available["referenceDetails"]["items"] == [
            {
                "kind": "knowledge",
                "reference": reference,
                "status": "AVAILABLE",
                "name": "工单说明(合成测试)",
            }
        ]
        with TestClient(app.application, base_url="https://console.example") as admin:
            revoke(app, admin, "knowledge-read", "revoke-knowledge-projection")
        unreadable = client.get(
            ROOT + "/" + result["objectId"], params={"revision": result["revisionId"]}
        )
        assert unreadable.status_code == 200, unreadable.text
        retained = unreadable.json()["result"]
        assert retained["record"] == available["record"]
        assert retained["digest"] == available["digest"]
        assert retained["referenceDetails"]["items"] == [
            {"kind": "knowledge", "reference": reference, "status": "UNAVAILABLE"}
        ]


def relation_fixture(app, client):
    from dataclasses import replace

    from agent_console.business_capability_postgres import (
        PostgresBusinessCapabilityRepository,
    )
    from agent_console.execution_domain import ScopeIdentity
    from test_business_capability import capability

    headers = fixture.unsafe_headers(fixture.login(client, "alice-secret"))
    grant_basics(app)
    save_architecture(app, client, headers)
    for action in ("READ_SCOPE", "MAINTAIN_SCOPE"):
        allow(
            app,
            "BUSINESS_PROCESS",
            action,
            "business-process:collection",
            "relation-" + action,
        )
    saved = client.post(ROOT + "/commands", json=command(), headers=headers)
    assert saved.status_code == 200, saved.text
    process = saved.json()["result"]
    store = PostgresBusinessCapabilityRepository(app.authority.pool)
    store.migrate(fixture.MIGRATIONS / "0052_business_capability.sql")
    value = replace(
        capability(),
        scope=ScopeIdentity(fixture.SCOPE.tenant_id, fixture.SCOPE.security_domain),
    )
    with app.authority.pool.connection() as conn, conn.transaction():
        store.save(
            conn,
            value,
            expected_version=0,
            command_id="capability-fixture",
            actor_id="human:alice",
            decision_id="decision:fixture",
        )
    allow(
        app,
        "BUSINESS_CAPABILITY",
        "READ",
        f"business-capability:{value.capability_id}:{value.revision_id}",
        "relation-cap-read",
    )
    body = {
        "relation": {
            "relation_id": "relation:document",
            "relation_revision_id": "relation-revision:1",
            "relation_type": "SUPPORTS_ACTIVITY",
            "process": {
                "resource_id": process["objectId"],
                "revision_id": process["revisionId"],
                "digest": process["digest"],
            },
            "activity_ids": ["collect"],
            "capability": {
                "resource_id": value.capability_id,
                "revision_id": value.revision_id,
                "digest": value.content_digest,
            },
            "coverage_description": "核对交接说明; 实际执行仍需独立验证。",
        },
        "expectedVersion": 0,
        "commandId": "relation-command:1",
    }
    return headers, body


def relation_query(relation, side):
    ref = relation["process" if side == "PROCESS" else "capability"]
    return {
        "side": side,
        "identity": ref["resource_id"],
        "revision": ref["revision_id"],
        "digest": ref["digest"],
    }


def test_capability_relation_fixed_versions_bidirectional_history_and_invalid_coverage(
    app,
):
    endpoint = ROOT + "/capability-relations"
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, body = relation_fixture(app, client)
        created = client.post(endpoint, json=body, headers=headers)
        assert created.status_code == 200, created.text
        replay = client.post(endpoint, json=body, headers=headers)
        assert replay.status_code == 200, replay.text
        assert replay.json()["result"]["replayed"] is True
        successor = {
            **body,
            "expectedVersion": 1,
            "commandId": "relation-command:2",
            "relation": {
                **body["relation"],
                "relation_revision_id": "relation-revision:2",
                "coverage_description": "增加输出依据核对。",
            },
        }
        changed = client.post(endpoint, json=successor, headers=headers)
        assert changed.status_code == 200, changed.text
        for side in ("PROCESS", "CAPABILITY"):
            result = client.get(endpoint, params=relation_query(body["relation"], side))
            assert result.status_code == 200, result.text
            values = result.json()["result"]["items"]
            assert [value["relationVersion"] for value in values] == [1, 2]
            assert values[0]["record"] == body["relation"]
            assert values[0]["capabilityTitle"] == "检查交接材料"
            assert values[0]["processName"] == "供应商交付评审"
            assert values[0]["activities"] == [
                {"activityId": "collect", "name": "收集资料"}
            ]
            assert all(value["executionAuthorized"] is False for value in values)
        query = {**relation_query(body["relation"], "CAPABILITY"), "pageSize": 1}
        first_page = client.get(endpoint, params=query).json()["result"]
        assert [item["relationVersion"] for item in first_page["items"]] == [1]
        assert first_page["nextCursor"]
        second_page = client.get(
            endpoint, params={**query, "cursor": first_page["nextCursor"]}
        ).json()["result"]
        assert [item["relationVersion"] for item in second_page["items"]] == [2]
        assert second_page["nextCursor"] is None
        original = client.get(endpoint + "/relation:document/relation-revision:1")
        assert original.status_code == 200, original.text
        assert original.json()["result"]["record"] == body["relation"]
        receipt = client.get(endpoint + "/commands/relation-command:1")
        assert receipt.status_code == 200, receipt.text
        invalid = {
            **body,
            "commandId": "relation-command:invalid",
            "expectedVersion": 2,
            "relation": {
                **body["relation"],
                "relation_revision_id": "relation-revision:3",
                "activity_ids": ["absent"],
            },
        }
        refused = client.post(endpoint, json=invalid, headers=headers)
        assert refused.status_code == 422, refused.text
        assert refused.json()["reasonCode"] == "BUSINESS_RELATION_PROCESS_INVALID"
        assert (
            client.post(
                endpoint, json={**body, "commandId": "stale-relation"}, headers=headers
            ).status_code
            == 409
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.capability_relations"
                ).fetchone()["n"]
                == 2
            )


def test_derived_relation_maintenance_and_reverse_read_revocation(
    app,
):
    endpoint = ROOT + "/capability-relations"
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, body = relation_fixture(app, client)
        body["relation"]["relation_type"] = "DERIVED_FROM_PROCESS"
        assert client.post(endpoint, json=body, headers=headers).status_code == 404
        ref = body["relation"]["capability"]
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "REVISE",
            f"business-capability:{ref['resource_id']}:aggregate",
            "relation-cap-revise",
        )
        created = client.post(endpoint, json=body, headers=headers)
        assert created.status_code == 200, created.text
        with TestClient(app.application, base_url="https://console.example") as admin:
            revoke(app, admin, "relation-READ_SCOPE", "revoke-relation-process-read")
        assert (
            client.get(endpoint + "/relation:document/relation-revision:1").status_code
            == 404
        )
        reverse = client.get(
            endpoint, params=relation_query(body["relation"], "CAPABILITY")
        )
        assert reverse.status_code == 200, reverse.text
        assert reverse.json()["result"]["items"] == []
        assert client.get(endpoint + "/commands/relation-command:1").status_code == 404
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.capability_relations"
                ).fetchone()["n"]
                == 1
            )
            origin = conn.execute(
                "SELECT record FROM business_capability.revisions"
            ).fetchone()["record"]["origin"]
            assert origin["kind"] == "INDEPENDENT"


def test_concurrent_relation_command_is_once_and_facts_are_immutable(app):
    endpoint = ROOT + "/capability-relations"
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, body = relation_fixture(app, client)
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(
                workers.map(
                    lambda _: client.post(endpoint, json=body, headers=headers),
                    range(2),
                )
            )
        assert all(response.status_code == 200 for response in responses), [
            r.text for r in responses
        ]
        assert (
            sum(
                response.json()["result"].get("replayed", False)
                for response in responses
            )
            == 1
        )
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.capability_relations"
                ).fetchone()["n"]
                == 1
            )
        with (
            pytest.raises(psycopg.errors.RaiseException),
            app.authority.pool.connection() as conn,
            conn.transaction(),
        ):
            conn.execute(
                "UPDATE business_process.capability_relations "
                "SET actor_id='human:other'"
            )


def test_relation_withdrawal_is_once_preserves_history_and_blocks_new_revisions(app):
    endpoint = ROOT + "/capability-relations"
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, body = relation_fixture(app, client)
        created = client.post(endpoint, json=body, headers=headers)
        assert created.status_code == 200, created.text
        saved = created.json()["result"]
        withdraw = {
            key: saved[key] for key in ("relationId", "relationRevisionId", "digest")
        }
        withdraw.update(
            expectedVersion=1,
            commandId="withdraw:1",
            reason="业务范围调整; 保留原设计记录。",
        )
        stale = client.post(
            endpoint + "/withdrawals",
            json={**withdraw, "expectedVersion": 2},
            headers=headers,
        )
        assert stale.status_code == 409
        blank = client.post(
            endpoint + "/withdrawals",
            json={**withdraw, "reason": "  "},
            headers=headers,
        )
        assert blank.status_code == 422
        conflict = client.post(
            endpoint + "/withdrawals",
            json={**withdraw, "commandId": body["commandId"]},
            headers=headers,
        )
        assert conflict.status_code == 409
        with ThreadPoolExecutor(max_workers=2) as workers:
            replies = list(
                workers.map(
                    lambda _: client.post(
                        endpoint + "/withdrawals", json=withdraw, headers=headers
                    ),
                    range(2),
                )
            )
        assert all(reply.status_code == 200 for reply in replies), [
            reply.text for reply in replies
        ]
        assert (
            sum(reply.json()["result"].get("replayed", False) for reply in replies) == 1
        )
        receipt = client.get(endpoint + "/withdrawals/withdraw:1")
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["result"]["state"] == "WITHDRAWN"
        historical = client.get(
            endpoint + "/relation:document/relation-revision:1"
        ).json()["result"]
        assert historical["record"] == body["relation"]
        assert historical["digest"] == saved["digest"]
        assert historical["isCurrentRelationRevision"] is True
        assert historical["withdrawal"]["state"] == "WITHDRAWN"
        assert (
            client.post(endpoint, json=body, headers=headers).json()["result"][
                "replayed"
            ]
            is True
        )
        successor = {
            **body,
            "commandId": "relation:after-withdraw",
            "expectedVersion": 1,
            "relation": {
                **body["relation"],
                "relation_revision_id": "relation-revision:2",
            },
        }
        rejected = client.post(endpoint, json=successor, headers=headers)
        assert rejected.status_code == 409
        assert rejected.json()["reasonCode"] == "BUSINESS_RELATION_WITHDRAWN_CONFLICT"
        for side in ("PROCESS", "CAPABILITY"):
            items = client.get(
                endpoint, params=relation_query(body["relation"], side)
            ).json()["result"]["items"]
            assert len(items) == 1 and items[0]["withdrawal"]["state"] == "WITHDRAWN"
        with app.authority.pool.connection() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.relation_withdrawals"
                ).fetchone()["n"]
                == 1
            )
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_process.capability_relations"
                ).fetchone()["n"]
                == 1
            )
        with (
            pytest.raises(psycopg.errors.RaiseException),
            app.authority.pool.connection() as conn,
            conn.transaction(),
        ):
            conn.execute("DELETE FROM business_process.relation_withdrawals")
        with TestClient(app.application, base_url="https://console.example") as admin:
            revoke(app, admin, "relation-MAINTAIN_SCOPE", "revoke-withdraw-maintain")
        assert client.get(endpoint + "/withdrawals/withdraw:1").status_code == 404
        assert (
            client.get(endpoint + "/relation:document/relation-revision:1").status_code
            == 200
        )
