"""Real SQL and Workbench authorization for exact workflow provenance."""

import pytest
import test_workbench_business_capability_postgres as fixture
from agent_console.workbench_workflow import workflow_operations
from agent_console.workbench_workflow_authoring import authoring_operations
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService
from fastapi.testclient import TestClient
from test_workbench_team_postgres import allow

pytestmark = fixture.pytestmark


@pytest.fixture
def app(monkeypatch):
    original = fixture.capability_operations
    stores = []
    refs = []
    workflow_services = []
    runtime_references = []
    runtime_services = []

    def operations(repository, employees, services, cursors):
        store = PostgresWorkflowDefinitionRepository(
            repository.pool.conninfo,
            migration_path=fixture.employee_fixture.MIGRATIONS
            / "0007_workflow_runtime_profiles.sql",
        )
        stores.append(store)
        store.migrate()
        from agent_console.runtime_profile_postgres import (
            PostgresRuntimeProfileRepository,
        )
        from agent_console.runtime_profile_service import RuntimeProfileService
        from test_runtime_profile_service import native

        runtime_store = PostgresRuntimeProfileRepository(
            repository.pool.conninfo,
            migration_path=fixture.employee_fixture.MIGRATIONS
            / "0007_workflow_runtime_profiles.sql",
        )
        stores.append(runtime_store)
        runtime_store.migrate()
        runtime_service = RuntimeProfileService(runtime_store)
        runtime_services.append(runtime_service)
        runtime = runtime_service.create(
            runtime_service.scope("tenant-a", "quality"),
            "human:fixture",
            "隔离运行配置",
            native(),
        )
        runtime_references.append(
            {
                "kind": "RUNTIME_PROFILE",
                "resourceId": runtime["runtimeProfileId"],
                "revisionId": runtime["revisions"][0]["revisionId"],
                "digest": runtime["revisions"][0]["digest"],
            }
        )
        services["runtime"] = runtime_service
        service = WorkflowDefinitionService(store)
        workflow_services.append(service)
        scope = service.scope("tenant-a", "quality")
        flow = service.create(
            scope,
            "human:fixture",
            "真实来源流程",
            {
                "description": "核对交接责任",
                "tasks": [{"taskId": "one", "name": "核对责任", "dependsOn": []}],
                "inputs": ["交接说明"],
                "outputs": ["缺口清单"],
                "runtimeProfile": {
                    "kind": "RUNTIME_PROFILE",
                    "resourceId": "runtime:test",
                    "revisionId": "runtime-revision:test",
                },
            },
        )
        revision = flow["revisions"][0]
        assert revision["digest"].startswith("sha256:")
        refs.append(
            {
                "resource_id": flow["workflowDefinitionId"],
                "revision_id": revision["revisionId"],
                "digest": revision["digest"].removeprefix("sha256:"),
            }
        )
        return (
            *original(repository, employees, services, cursors, workflows=service),
            *workflow_operations(service),
            *authoring_operations(service, services),
        )

    monkeypatch.setattr(fixture, "capability_operations", operations)
    generator = fixture.app.__wrapped__(monkeypatch)
    value = next(generator)
    value.workflow_source = refs[0]
    value.workflow_service = workflow_services[0]
    value.runtime_reference = runtime_references[0]
    value.runtime_service = runtime_services[0]
    try:
        yield value
    finally:
        generator.close()
        for store in stores:
            store.pool.close()


def test_persisted_workflow_origin_reverse_lookup_and_permissions(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = fixture.setup(client, app)
        fixture.member_grant(app, employee)
        ref = app.workflow_source
        for action in ("CREATE", "LIST"):
            allow(
                app,
                "BUSINESS_CAPABILITY",
                action,
                "business-capability:collection",
                action,
            )
        allow(
            app,
            "WORKFLOW",
            "READ",
            f"workflow:{ref['resource_id']}:{ref['revision_id']}",
            "source-read",
        )
        for identity in ("a", "b", "hidden"):
            revision = {
                **body["revision"],
                "capability_id": identity,
                "revision_id": identity + ":v1",
                "origin": {
                    "kind": "WORKFLOW_REVISION",
                    "workflow": ref,
                    "preparation_digest": None,
                },
            }
            saved = client.post(
                fixture.PREFIX,
                json={
                    "revision": revision,
                    "expectedVersion": 0,
                    "commandId": "save:" + identity,
                },
                headers=headers,
            )
            assert saved.status_code == 201, saved.text
            if identity != "hidden":
                allow(
                    app,
                    "BUSINESS_CAPABILITY",
                    "READ",
                    f"business-capability:{identity}:{identity}:v1",
                    "read:" + identity,
                )
        query = {
            "workflowId": ref["resource_id"],
            "workflowRevision": ref["revision_id"],
            "workflowDigest": ref["digest"],
            "pageSize": 1,
        }
        first = client.get(fixture.PREFIX, params=query)
        assert first.status_code == 200, first.text
        data = first.json()["result"]
        assert [v["capabilityId"] for v in data["items"]] == ["a"]
        second = client.get(
            fixture.PREFIX, params={**query, "cursor": data["nextCursor"]}
        )
        assert second.status_code == 200, second.text
        assert [v["capabilityId"] for v in second.json()["result"]["items"]] == ["b"]
        assert second.json()["result"]["nextCursor"] is None
        wrong = client.get(fixture.PREFIX, params={**query, "workflowDigest": "0" * 64})
        assert wrong.status_code == 409, wrong.text
        partial = client.get(fixture.PREFIX, params={"workflowId": ref["resource_id"]})
        assert partial.status_code == 422
        # Original exact source remains readable using the owner's prefixed digest.
        read = client.get(
            "/api/workbench/v1/workflows/"
            + ref["resource_id"]
            + "/revisions/"
            + ref["revision_id"]
        )
        assert read.status_code == 200, read.text
        assert read.json()["result"]["revision"]["digest"] == "sha256:" + ref["digest"]

        unrelated_cursor = client.get(
            fixture.PREFIX, params={"pageSize": 1, "cursor": data["nextCursor"]}
        )
        assert unrelated_cursor.status_code == 422, unrelated_cursor.text
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='WORKFLOW' AND action='READ'"
            )
        revoked = client.get(fixture.PREFIX, params=query)
        assert revoked.status_code in (403, 404), revoked.text
        assert "items" not in revoked.json().get("result", {})


def test_authoring_receipt_and_workflow_share_transaction_and_replay(app):
    # Storage acceptance only; BFF command authorization remains separate.
    from types import SimpleNamespace
    from unittest.mock import Mock

    from agent_console.workbench_owner_authorization import WorkbenchOwnerError
    from agent_console.workflow_authoring import WorkflowAuthoring

    service = app.workflow_service
    command = {
        "action": "create",
        "commandKey": "atomic-create",
        "name": "事务验证流程",
        "content": {
            "tasks": [{"taskId": "check", "name": "检查"}],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": "runtime:test",
                "revisionId": "runtime:test-v1",
            },
        },
    }
    context = SimpleNamespace(
        principal_id="human:alice",
        scope=SimpleNamespace(tenant_id="tenant-a", security_domain="quality"),
    )
    handler = WorkflowAuthoring(service, lambda call, reference, published: True)
    prepare_receipts(app)

    def call(conn, payload=command):
        return SimpleNamespace(
            connection=conn, payload=payload, context=context, authority=Mock()
        )

    with app.authority.connection_scope() as conn:
        before = conn.execute(
            "SELECT count(*) n FROM workflow_definition.definitions"
        ).fetchone()["n"]
    with (
        pytest.raises(RuntimeError, match="rollback"),
        app.authority.connection_scope() as conn,
    ):
        handler.handle(call(conn))
        raise RuntimeError("rollback")
    with app.authority.connection_scope() as conn:
        assert (
            conn.execute(
                "SELECT count(*) n FROM workflow_definition.definitions"
            ).fetchone()["n"]
            == before
        )
        assert (
            conn.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands "
                "WHERE command_key='workflow-authoring:atomic-create'"
            ).fetchone()["n"]
            == 0
        )
        first = handler.handle(call(conn))
    with app.authority.connection_scope() as conn:
        second = handler.handle(call(conn))
        assert second["replayed"] is True
        assert second["workflowId"] == first["workflowId"]
        assert (
            conn.execute(
                "SELECT count(*) n FROM workflow_definition.definitions"
            ).fetchone()["n"]
            == before + 1
        )
        with pytest.raises(WorkbenchOwnerError):
            handler.handle(call(conn, {**command, "name": "different"}))
    with app.authority.connection_scope() as conn:
        denied = call(conn)
        denied.authority.require.side_effect = PermissionError("revoked")
        with pytest.raises(PermissionError):
            handler.handle(denied)


def prepare_receipts(app):
    # Install the exact production receipt DDL, including its immutable trigger.
    # This fixture intentionally does not install unrelated execution-plan tables.
    migrations = fixture.employee_fixture.MIGRATIONS
    function_sql = (
        (migrations / "0033_prepared_execution.sql")
        .read_text()
        .split(
            "CREATE OR REPLACE FUNCTION execution_authority.preparation_immutable()", 1
        )[1]
        .split("END $$;", 1)[0]
    )
    receipt_sql = (
        (migrations / "0034_prepared_execution_binding.sql")
        .read_text()
        .split("CREATE TABLE execution_authority.prepared_resource_commands", 1)[1]
    )
    with app.authority.connection_scope() as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS execution_authority")
        conn.execute(
            "CREATE OR REPLACE FUNCTION execution_authority.preparation_immutable()"
            + function_sql
            + "END $$;"
        )
        conn.execute(
            "CREATE TABLE execution_authority.prepared_resource_commands" + receipt_sql
        )


def test_trusted_authoring_login_csrf_resource_grants_and_receipt(app):
    from agent_console.workbench_resource_directory import target

    prepare_receipts(app)
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, _, _ = fixture.setup(client, app)
        reference = app.runtime_reference
        body = {
            "action": "create",
            "commandKey": "browser-create",
            "name": "受控流程",
            "content": {
                "tasks": [{"taskId": "check", "name": "核对"}],
                "runtimeProfile": reference,
            },
        }
        url = "/api/workbench/v1/workflows/commands"
        assert client.post(url, json=body, headers=headers).status_code in (403, 404)
        allow(app, "WORKFLOW", "CREATE", "workflow:collection", "create-flow")
        assert client.post(url, json=body, headers=headers).status_code in (403, 404)
        grant = target("runtime", reference["resourceId"], reference["revisionId"])
        allow(app, grant.owner, grant.action, grant.exact_resource, "runtime-read")
        assert client.post(url, json=body).status_code == 403
        response = client.post(url, json=body, headers=headers)
        assert response.status_code in (200, 201), response.text
        receipt = response.json()["result"]
        assert receipt["executionAuthorized"] is False
        second = client.post(url, json=body, headers=headers)
        assert second.status_code in (200, 201), second.text
        assert second.json()["result"]["workflowId"] == receipt["workflowId"]
        assert second.json()["result"]["replayed"] is True
        read = client.get(url + "/browser-create", params={"action": "create"})
        assert read.status_code == 200, read.text
        assert read.json()["result"]["workflowId"] == receipt["workflowId"]
        changed = client.post(url, json={**body, "name": "覆盖"}, headers=headers)
        assert changed.status_code == 409, changed.text
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='WORKFLOW' AND action='CREATE'"
            )
        assert client.get(
            url + "/browser-create", params={"action": "create"}
        ).status_code in (403, 404)


def test_trusted_workflow_full_lifecycle_and_revoked_dependency(app):
    from agent_console.workbench_resource_directory import target

    prepare_receipts(app)
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, _, _ = fixture.setup(client, app)
        ref = app.runtime_reference
        grant = target("runtime", ref["resourceId"], ref["revisionId"])
        allow(app, "WORKFLOW", "CREATE", "workflow:collection", "create-lifecycle")
        allow(app, grant.owner, grant.action, grant.exact_resource, "runtime-lifecycle")
        url = "/api/workbench/v1/workflows/commands"
        content = {
            "tasks": [{"taskId": "check", "name": "核对材料"}],
            "runtimeProfile": ref,
        }

        def post(command, expected=200):
            response = client.post(url, json=command, headers=headers)
            assert response.status_code == expected, response.text
            return response.json().get("result")

        created = post(
            {
                "action": "create",
                "commandKey": "flow-create",
                "name": "完整生命周期",
                "content": content,
            }
        )
        identity = created["workflowId"]
        aggregate = "workflow:aggregate:" + identity
        allow(app, "WORKFLOW", "MANAGE", aggregate, "manage-flow")
        allow(app, "WORKFLOW", "REVIEW_PUBLISH", aggregate, "publish-flow")
        allow(
            app,
            "WORKFLOW",
            "READ",
            f"workflow:{identity}:{created['revisionId']}",
            "read-flow",
        )
        validation = {
            "action": "validate",
            "commandKey": "flow-validate",
            "workflowId": identity,
            "expectedVersion": 1,
        }
        post(validation, 409)  # Draft runtime is readable, but not publishable.
        runtime = app.runtime_service
        scope = runtime.scope("tenant-a", "quality")
        runtime.validate(scope, ref["resourceId"], "human:fixture", 1)
        reviewed = runtime.review(
            scope,
            ref["resourceId"],
            "human:fixture",
            2,
            ref["digest"],
            "APPROVE",
            "isolated fixture",
        )
        runtime.publish(
            scope,
            ref["resourceId"],
            "human:fixture",
            3,
            ref["digest"],
            reviewed["reviews"][-1]["reviewId"],
        )
        assert post(validation)["aggregateVersion"] == 2
        detail_url = "/api/workbench/v1/workflows/" + identity + "/authoring"
        detail = client.get(detail_url)
        assert detail.status_code == 200, detail.text
        record = detail.json()["result"]["definition"]
        digest = record["revisions"][-1]["digest"]
        review = {
            "action": "review",
            "commandKey": "flow-review",
            "workflowId": identity,
            "expectedVersion": 2,
            "digest": digest,
            "reason": "核对固定引用",
        }
        post({**review, "digest": "0" * 64}, 409)
        assert post(review)["aggregateVersion"] == 3
        record = client.get(detail_url).json()["result"]["definition"]
        publication = {
            "action": "publish",
            "commandKey": "flow-publish",
            "workflowId": identity,
            "expectedVersion": 3,
            "digest": digest,
            "reviewId": record["reviews"][-1]["reviewId"],
        }
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='RUNTIME_PROFILE' AND action='READ_RESOURCE'"
            )
        response = client.post(url, json=publication, headers=headers)
        assert response.status_code in (403, 404), response.text
        assert (
            client.get(detail_url).json()["result"]["definition"]["aggregateVersion"]
            == 3
        )
        allow(
            app,
            grant.owner,
            grant.action,
            grant.exact_resource,
            "runtime-lifecycle-restored",
        )
        published = post(publication)
        assert (
            published["aggregateVersion"] == 4 and not published["executionAuthorized"]
        )
        old = client.get(detail_url).json()["result"]["definition"]["revisions"][0]
        successor = post(
            {
                "action": "successor",
                "commandKey": "flow-successor",
                "workflowId": identity,
                "expectedVersion": 4,
            }
        )
        assert successor["aggregateVersion"] == 5
        allow(
            app,
            "WORKFLOW",
            "READ",
            f"workflow:{identity}:{successor['revisionId']}",
            "read-successor",
        )
        edited = post(
            {
                "action": "edit",
                "commandKey": "flow-edit",
                "workflowId": identity,
                "expectedVersion": 5,
                "content": {**content, "description": "补充说明"},
            }
        )
        assert edited["aggregateVersion"] == 6
        allow(
            app,
            "WORKFLOW",
            "READ",
            f"workflow:{identity}:{edited['revisionId']}",
            "read-edited",
        )
        record = client.get(detail_url).json()["result"]["definition"]
        assert record["revisions"][0] == old
        comparison_url = "/api/workbench/v1/workflows/" + identity + "/comparison"
        comparison_query = {
            "leftRevisionId": old["revisionId"],
            "rightRevisionId": edited["revisionId"],
        }
        comparison = client.get(comparison_url, params=comparison_query)
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()["result"]["digestChanged"] is True
        assert comparison.json()["result"]["leftRevisionId"] == old["revisionId"]
        with app.authority.connection_scope() as conn:
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='WORKFLOW' AND action='READ' AND exact_resource=%s",
                (f"workflow:{identity}:{edited['revisionId']}",),
            )
        assert client.get(comparison_url, params=comparison_query).status_code in (
            403,
            404,
        )
        allow(
            app,
            "WORKFLOW",
            "READ",
            f"workflow:{identity}:{edited['revisionId']}",
            "restore-comparison-read",
        )

        post(
            {
                "action": "edit",
                "commandKey": "stale-edit",
                "workflowId": identity,
                "expectedVersion": 5,
                "content": content,
            },
            409,
        )
        assert post(publication)["replayed"] is True
        assert (
            client.get(detail_url).json()["result"]["definition"]["aggregateVersion"]
            == 6
        )
