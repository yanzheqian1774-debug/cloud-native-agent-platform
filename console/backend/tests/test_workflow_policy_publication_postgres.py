"""Real D12 sessions/authority/Workflow/runtime owners, random disposable DB only.

The validated input/runtime are fixture setup via original lifecycle services;
publication/reference checks, immutable receipts, rollback and replay are real.
No model, execution, or provider dependency is composed.
"""

# ruff: noqa: F401,F811 -- pytest fixture registration
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_workflow_authoring import authoring_operations
from agent_console.workbench_workflow_policy import (
    WorkflowPolicyPublication,
    policy_publication_operations,
)
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService
from fastapi.testclient import TestClient
from psycopg.errors import RaiseException
from test_development_administrator import URL, login, setup
from test_runtime_profile_service import native
from test_workbench_employee_commands_postgres import Controller
from test_workflow_definition_service import content

pytestmark = pytest.mark.skipif(not URL, reason="disposable PostgreSQL required")
ROOT = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def policy_env(setup):
    repo, generation, sessions, reader = setup
    workflow_repo = PostgresWorkflowDefinitionRepository(
        repo.pool.conninfo, migration_path=ROOT / "0007_workflow_runtime_profiles.sql"
    )
    runtime_repo = PostgresRuntimeProfileRepository(
        repo.pool.conninfo, migration_path=ROOT / "0007_workflow_runtime_profiles.sql"
    )
    workflow_repo.migrate()
    runtime_repo.migrate()
    runtime = RuntimeProfileService(runtime_repo)
    scope = runtime.scope("s5-323-demo", "isolated-real-demo")
    actor = "human:development-admin"
    r = runtime.create(scope, actor, "fixture runtime", native())
    rid = r["runtimeProfileId"]
    r = runtime.validate(scope, rid, actor, 1)
    rev = r["revisions"][-1]
    r = runtime.review(
        scope, rid, actor, 2, rev["digest"], "APPROVE", "fixture exact review"
    )
    runtime.publish(scope, rid, actor, 3, rev["digest"], r["reviews"][-1]["reviewId"])
    workflow = WorkflowDefinitionService(workflow_repo, lambda *_: True)
    value = content()
    value["runtimeProfile"] = dict(
        kind="RUNTIME_PROFILE",
        resourceId=rid,
        revisionId=rev["revisionId"],
        digest=rev["digest"],
    )
    w = workflow.create(scope, actor, "fixture Workflow", value)
    identity = w["workflowDefinitionId"]
    w = workflow.validate(scope, identity, actor, 1)
    # Production receipt DDL and trigger; unrelated execution tables are absent.
    function = (
        (ROOT / "0033_prepared_execution.sql")
        .read_text()
        .split(
            "CREATE OR REPLACE FUNCTION execution_authority.preparation_immutable()", 1
        )[1]
        .split("END $$;", 1)[0]
    )
    receipt = (
        (ROOT / "0034_prepared_execution_binding.sql")
        .read_text()
        .split("CREATE TABLE execution_authority.prepared_resource_commands", 1)[1]
    )
    with repo.connection_scope() as c:
        c.execute("CREATE SCHEMA execution_authority")
        c.execute(
            "CREATE OR REPLACE FUNCTION execution_authority.preparation_immutable()"
            + function
            + "END $$;"
        )
        c.execute(
            "CREATE TABLE execution_authority.prepared_resource_commands" + receipt
        )
    auth = WorkbenchOwnerAuthorization(Controller(generation), repo, reader)
    services = {"runtime": runtime}
    app = create_workbench_bff(
        sessions,
        auth,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(
            *authoring_operations(workflow, services, policy_publication_enabled=True),
            *policy_publication_operations(workflow, services, enabled=True),
        ),
    )
    secret = login(sessions, "devadmin")
    session, ctx = sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": sessions.issue_csrf(session),
    }
    command = dict(
        action="policy-publish",
        workflowId=identity,
        expectedVersion=2,
        digest=w["revisions"][-1]["digest"],
        commandKey="same-command",
    )
    try:
        with TestClient(app, base_url="https://testserver") as client:
            client.cookies.set(SESSION_COOKIE, secret.value)
            yield SimpleNamespace(
                repo=repo,
                generation=generation,
                auth=auth,
                sessions=sessions,
                context=ctx,
                client=client,
                headers=headers,
                command=command,
                workflow=workflow,
                services=services,
                scope=scope,
                runtime_id=rid,
            )
    finally:
        workflow_repo.pool.close()
        runtime_repo.pool.close()


def test_current_role_publish_read_replay_and_role_disable(policy_env):
    e = policy_env
    path = PREFIX + "/workflows/policy-publications"
    result = e.client.post(path, headers=e.headers, json=e.command)
    assert result.status_code == 200, result.text
    receipt = result.json()["result"]
    assert receipt["policyReview"]["policyBasis"]["type"] == "DEVELOPMENT_ADMINISTRATOR"
    assert receipt["policyReview"]["actor"] == e.context.principal_id
    assert receipt["executionAuthorized"] is False
    replay = e.client.post(path, headers=e.headers, json=e.command)
    assert replay.status_code == 200, replay.text
    assert replay.json()["result"] == {**receipt, "replayed": True}
    assert (
        e.client.get(
            path + "/same-command", params={"workflowId": e.command["workflowId"]}
        ).status_code
        == 200
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_requests"
            ).fetchone()["n"]
            == 0
        )
        with pytest.raises(RaiseException), c.transaction():
            c.execute(
                "UPDATE execution_authority.prepared_resource_commands "
                "SET digest='fake'"
            )
    e.auth.authorization = GenerationAuthorizationReader(
        replace(e.generation, development_administrator=False),
        e.repo,
        e.repo,
        recovery_epoch=1,
    )
    assert e.client.post(path, headers=e.headers, json=e.command).status_code in (
        403,
        404,
    )
    assert e.client.get(
        path + "/same-command", params={"workflowId": e.command["workflowId"]}
    ).status_code in (403, 404)


def test_policy_binding_rollback_and_current_reference_failure(policy_env):
    e = policy_env
    owner = WorkflowPolicyPublication(e.workflow, e.services)
    grant = ExactGrant(
        "WORKFLOW", "REVIEW_PUBLISH", "workflow:aggregate:" + e.command["workflowId"]
    )

    def invoke(body, fail=False):
        def handle(call):
            result = owner(call)
            if fail:
                raise RuntimeError("after-publication")
            return result

        return e.auth.execute(
            e.context,
            (grant,),
            operation="PUBLISH_WORKFLOW_POLICY",
            payload=body,
            path={},
            query={},
            handler=handle,
        )

    with pytest.raises(Exception, match="VALIDATED_TARGET_REQUIRED"):
        invoke({**e.command, "digest": "f" * 64})
    with pytest.raises(RuntimeError, match="after-publication"):
        invoke(e.command, True)
    unchanged = e.workflow.repository.get(e.scope, e.command["workflowId"])
    assert unchanged["aggregateVersion"] == 2 and "policyReviews" not in unchanged
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands"
            ).fetchone()["n"]
            == 0
        )
    receipt = invoke(e.command)
    # Repository retains published exact revision; simulate current owner disabled
    # dependency as a real runtime aggregate update, not bypassing reference checks.
    r = e.services["runtime"].repository.get(e.scope, e.runtime_id)
    e.services["runtime"].repository.replace(
        {**r, "aggregateVersion": r["aggregateVersion"] + 1, "enabled": False},
        expected_version=r["aggregateVersion"],
        fact={"factId": "fixture-disabled", "event": "FIXTURE_DISABLED"},
    )
    with pytest.raises(Exception, match="REFERENCE"):
        invoke(e.command)
    assert receipt["executionAuthorized"] is False


def test_browser_cannot_supply_basis_and_other_account_cannot_read_receipt(policy_env):
    e = policy_env
    path = PREFIX + "/workflows/policy-publications"
    forged = e.client.post(
        path,
        headers=e.headers,
        json={**e.command, "policyBasis": {"type": "DEVELOPMENT_ADMINISTRATOR"}},
    )
    assert forged.status_code == 422
    assert e.client.post(path, headers=e.headers, json=e.command).status_code == 200
    ordinary = login(e.sessions, "reviewer324")
    e.client.cookies.set(SESSION_COOKIE, ordinary.value)
    session, _ = e.sessions.authenticate_session(ordinary.value)
    headers = {**e.headers, "x-csrf-token": e.sessions.issue_csrf(session)}
    assert e.client.get(
        path + "/same-command", params={"workflowId": e.command["workflowId"]}
    ).status_code in (403, 404)
    assert e.client.post(path, headers=headers, json=e.command).status_code in (
        403,
        404,
    )
    e.sessions.logout(ordinary.value, actor_id="human:demo323-approver")
    assert (
        e.client.get(
            path + "/same-command", params={"workflowId": e.command["workflowId"]}
        ).status_code
        == 401
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.prepared_resource_commands"
            ).fetchone()["n"]
            == 1
        )
