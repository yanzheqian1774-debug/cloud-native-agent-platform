import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
from agent_console import runtime_profile_api, workflow_definition_api
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService

DATABASE_URL = os.environ.get("EMPLOYEE_IDENTITY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class Authorized:
    """Explicit trusted decisions for this scoped integration scenario."""

    def __init__(self, scope):
        self.scope = scope

    def require(self, scope, action, identity):
        if scope != self.scope:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        return f"human-approval:{action}:{identity}"


def setup_authority():
    with psycopg.connect(DATABASE_URL) as conn:
        for version in range(1, 13):
            conn.execute(next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text())
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL, migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql"
    )
    store = PostgresEmployeeDefinitionRepository(authority)
    store.migrate(MIGRATIONS / "0014_digital_employee_identity.sql")
    return authority, store


def publish_agent(scope, database_url=None):
    repo = PostgresAgentDefinitionRepository(
        database_url or DATABASE_URL,
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
    )
    repo.migrate()
    service = AgentDefinitionService(repo)
    agent_scope = service.scope(scope.namespace, scope.security_domain)
    try:
        row = service.create(
            agent_scope,
            "human:owner",
            "Quality Agent",
            {
                "title": "Quality Analyst",
                "duties": ["Analyze quality"],
                "capabilities": ["analysis"],
            },
        )
        identity = row["definitionId"]
        row = service.validate(
            agent_scope, identity, "human:owner", row["aggregateVersion"]
        )["definition"]
        revision = row["revisions"][0]
        row = service.review(
            agent_scope,
            identity,
            "human:reviewer",
            row["aggregateVersion"],
            revision["digest"],
            "APPROVE",
            "Reviewed exact role",
        )["definition"]
        row = service.publish(
            agent_scope,
            identity,
            "human:publisher",
            row["aggregateVersion"],
            revision["digest"],
            row["reviews"][0]["reviewId"],
        )
        return CompositionMember(
            MemberKind.AGENT, identity, revision["revisionId"], revision["digest"]
        )
    finally:
        repo.pool.close()


def publish_employee(store, scope, database_url=None):
    member = publish_agent(scope, database_url)
    revision = EmployeeRevision(
        scope,
        f"employee-definition:{uuid.uuid4().hex}",
        "employee-revision:1",
        "Quality owner",
        ("Investigate quality",),
        (member,),
    )
    service = EmployeeDefinitionService(store, Authorized(scope))
    current = service.create(
        revision, expected_version=0, command_id=f"create:{revision.definition_id}"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        current = service.decide(
            scope,
            revision.definition_id,
            revision.revision_id,
            revision.digest,
            action,
            expected_version=current["aggregateVersion"],
            command_id=f"{action}:{revision.definition_id}",
        )
    return revision, service, current


def publish_runtime_and_workflow(scope):
    migration = MIGRATIONS / "0007_workflow_runtime_profiles.sql"
    runtime_repository = PostgresRuntimeProfileRepository(
        DATABASE_URL, migration_path=migration
    )
    workflow_repository = PostgresWorkflowDefinitionRepository(
        DATABASE_URL, migration_path=migration
    )
    runtime_repository.migrate()
    workflow_repository.migrate()
    runtime_service = RuntimeProfileService(runtime_repository)
    runtime_scope = runtime_service.scope(scope.namespace, scope.security_domain)
    runtime = runtime_service.create(
        runtime_scope,
        "human:runtime-owner",
        "Employee compatibility runtime",
        {
            "provider": "OPENCLAW",
            "resources": {
                "cpuRequest": "100m",
                "cpuLimit": "500m",
                "memoryRequest": "128Mi",
                "memoryLimit": "512Mi",
            },
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
            "secretReferences": [],
            "openClawPackageRef": "openclaw://bounded/employee-compatibility@1",
        },
    )
    runtime_id = runtime["runtimeProfileId"]
    runtime = runtime_service.validate(
        runtime_scope, runtime_id, "human:runtime-owner", runtime["aggregateVersion"]
    )
    runtime_revision = runtime["revisions"][-1]
    runtime = runtime_service.review(
        runtime_scope,
        runtime_id,
        "human:runtime-reviewer",
        runtime["aggregateVersion"],
        runtime_revision["digest"],
        "APPROVE",
        "Exact compatibility review",
    )
    runtime_service.publish(
        runtime_scope,
        runtime_id,
        "human:runtime-publisher",
        runtime["aggregateVersion"],
        runtime_revision["digest"],
        runtime["reviews"][-1]["reviewId"],
    )

    workflow_service = WorkflowDefinitionService(
        workflow_repository, lambda _scope, _reference: True
    )
    workflow_scope = workflow_service.scope(scope.namespace, scope.security_domain)
    workflow = workflow_service.create(
        workflow_scope,
        "human:workflow-owner",
        "Employee compatibility workflow",
        {
            "description": "Validate exact composition compatibility",
            "inputs": ["request"],
            "outputs": ["result"],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": runtime_id,
                "revisionId": runtime_revision["revisionId"],
            },
            "tasks": [
                {
                    "taskId": "validate",
                    "name": "Validate composition",
                    "dependsOn": [],
                    "inputs": ["request"],
                    "outputs": ["result"],
                    "capabilityRequirements": ["composition-validation"],
                    "references": [],
                    "retryLimit": 1,
                    "timeoutSeconds": 300,
                    "failurePolicy": "FAIL_WORKFLOW",
                }
            ],
        },
    )
    workflow_id = workflow["workflowDefinitionId"]
    workflow = workflow_service.validate(
        workflow_scope,
        workflow_id,
        "human:workflow-owner",
        workflow["aggregateVersion"],
    )
    workflow_revision = workflow["revisions"][-1]
    workflow = workflow_service.review(
        workflow_scope,
        workflow_id,
        "human:workflow-reviewer",
        workflow["aggregateVersion"],
        workflow_revision["digest"],
        "APPROVE",
        "Exact compatibility review",
    )
    workflow_service.publish(
        workflow_scope,
        workflow_id,
        "human:workflow-publisher",
        workflow["aggregateVersion"],
        workflow_revision["digest"],
        workflow["reviews"][-1]["reviewId"],
    )
    return runtime_service, workflow_service


def test_real_publication_replay_cas_restart_and_immutability():
    authority, store = setup_authority()
    scope = ScopeIdentity(f"employee-{uuid.uuid4().hex}", "quality")
    try:
        revision, service, current = publish_employee(store, scope)
        assert current["published"] and not current["matchable"]
        assert revision.definition_id != revision.members[0].resource_id
        assert revision.revision_id != revision.members[0].revision_id
        assert revision.digest != revision.members[0].digest
        assert (
            service.decide(
                scope,
                revision.definition_id,
                revision.revision_id,
                revision.digest,
                "PUBLISH",
                expected_version=3,
                command_id=f"PUBLISH:{revision.definition_id}",
            )
            == current
        )
        with pytest.raises(
            EmployeeDefinitionError, match="IDEMPOTENCY_PAYLOAD_MISMATCH"
        ):
            service.decide(
                scope,
                revision.definition_id,
                revision.revision_id,
                "0" * 64,
                "PUBLISH",
                expected_version=3,
                command_id=f"PUBLISH:{revision.definition_id}",
            )
        with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
            service.read(
                ScopeIdentity("other", "quality"),
                revision.definition_id,
                revision.revision_id,
            )

        def race(action):
            try:
                service.decide(
                    scope,
                    revision.definition_id,
                    revision.revision_id,
                    revision.digest,
                    action,
                    expected_version=4,
                    command_id=f"race:{action}:{revision.definition_id}",
                )
                return "COMMITTED"
            except EmployeeDefinitionError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(race, ("GRANT_MATCH", "DENY_MATCH"))) == [
                "COMMITTED",
                "STALE_AGGREGATE_VERSION",
            ]
        before = service.read(scope, revision.definition_id, revision.revision_id)
        with (
            pytest.raises(psycopg.Error, match="IMMUTABLE_EMPLOYEE_HISTORY"),
            authority.pool.connection() as conn,
        ):
            conn.execute(
                "UPDATE digital_employee_definition.revisions SET digest=%s "
                "WHERE definition_id=%s",
                ("0" * 64, revision.definition_id),
            )
        assert (
            service.read(scope, revision.definition_id, revision.revision_id) == before
        )
        successor = replace(
            revision,
            revision_id="employee-revision:2",
            predecessor_revision_id=revision.revision_id,
        )
        service.create(
            successor,
            expected_version=5,
            command_id=f"successor:{revision.definition_id}",
        )
        historical = service.read(scope, revision.definition_id, revision.revision_id)
        assert historical["revision"] == before["revision"]
        authority.pool.close()
        authority = PostgresExecutionAuthorityRepository(
            DATABASE_URL,
            migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
        )
        assert (
            PostgresEmployeeDefinitionRepository(authority).read(
                scope, revision.definition_id, revision.revision_id
            )
            == historical
        )
    finally:
        authority.pool.close()


def test_real_mismatch_rolls_back_validation():
    authority, store = setup_authority()
    scope = ScopeIdentity(f"employee-{uuid.uuid4().hex}", "quality")
    try:
        member = publish_agent(scope)
        revision = EmployeeRevision(
            scope,
            "employee",
            "employee-v1",
            "Quality owner",
            ("Analyze quality",),
            (replace(member, digest="0" * 64),),
        )
        service = EmployeeDefinitionService(store, Authorized(scope))
        before = service.create(revision, expected_version=0, command_id="create")
        with pytest.raises(EmployeeDefinitionError, match="BOUND_RESOURCE_MISMATCH"):
            service.decide(
                scope,
                "employee",
                "employee-v1",
                revision.digest,
                "VALIDATE",
                expected_version=1,
                command_id="validate",
            )
        assert service.read(scope, "employee", "employee-v1") == before
    finally:
        authority.pool.close()


def test_real_agent_binding_digest_projection_is_accepted_without_history_rewrite(
    monkeypatch,
):
    authority, store = setup_authority()
    scope = ScopeIdentity(f"employee-binding-{uuid.uuid4().hex}", "quality")
    runtime_service, workflow_service = publish_runtime_and_workflow(scope)
    try:
        monkeypatch.setattr(runtime_profile_api, "_service", runtime_service)
        monkeypatch.setattr(workflow_definition_api, "_service", workflow_service)
        runtime_record_before = runtime_service.repository.get(
            runtime_service.scope(scope.namespace, scope.security_domain),
            runtime_service.repository.list(
                runtime_service.scope(scope.namespace, scope.security_domain)
            )[0]["runtimeProfileId"],
        )
        workflow_record_before = workflow_service.repository.get(
            workflow_service.scope(scope.namespace, scope.security_domain),
            workflow_service.repository.list(
                workflow_service.scope(scope.namespace, scope.security_domain)
            )[0]["workflowDefinitionId"],
        )
        runtime_resolution = runtime_profile_api.binding_resolver.resolve(
            scope, "runtime-profile", runtime_record_before["runtimeProfileId"]
        )
        workflow_resolution = workflow_definition_api.binding_resolver.resolve(
            scope, "workflow", workflow_record_before["workflowDefinitionId"]
        )
        assert runtime_resolution is not None and workflow_resolution is not None
        assert len(runtime_resolution.digest) == len(workflow_resolution.digest) == 64
        assert runtime_record_before["revisions"][-1]["digest"] == (
            "sha256:" + runtime_resolution.digest
        )
        assert workflow_record_before["revisions"][-1]["digest"] == (
            "sha256:" + workflow_resolution.digest
        )

        members = (
            publish_agent(scope),
            CompositionMember(
                MemberKind.WORKFLOW,
                workflow_resolution.resource_id,
                workflow_resolution.revision_id,
                workflow_resolution.digest,
            ),
            CompositionMember(
                MemberKind.RUNTIME_PROFILE,
                runtime_resolution.resource_id,
                runtime_resolution.revision_id,
                runtime_resolution.digest,
            ),
        )
        revision = EmployeeRevision(
            scope,
            f"employee-definition:{uuid.uuid4().hex}",
            "employee-revision:1",
            "Quality owner",
            ("Validate exact compatibility",),
            members,
        )
        employee_digest_before = revision.digest
        service = EmployeeDefinitionService(store, Authorized(scope))
        current = service.create(
            revision, expected_version=0, command_id=f"create:{revision.definition_id}"
        )
        stored_before = service.read(
            scope, revision.definition_id, revision.revision_id
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            current = service.decide(
                scope,
                revision.definition_id,
                revision.revision_id,
                employee_digest_before,
                action,
                expected_version=current["aggregateVersion"],
                command_id=f"{action}:{revision.definition_id}",
            )
        assert current["published"] is True
        assert current["digest"] == employee_digest_before
        assert stored_before["revision"]["members"] == revision.record["members"]
        assert (
            runtime_service.repository.get(
                runtime_service.scope(scope.namespace, scope.security_domain),
                runtime_resolution.resource_id,
            )
            == runtime_record_before
        )
        assert (
            workflow_service.repository.get(
                workflow_service.scope(scope.namespace, scope.security_domain),
                workflow_resolution.resource_id,
            )
            == workflow_record_before
        )

        for suffix, changed in (
            ("digest", {"digest": "0" * 64}),
            ("revision", {"revision_id": "workflow-revision:wrong"}),
            ("identity", {"resource_id": "workflow-definition:wrong"}),
        ):
            invalid_member = replace(members[1], **changed)
            invalid = replace(
                revision,
                definition_id=f"employee-definition:{suffix}:{uuid.uuid4().hex}",
                members=(members[0], invalid_member, members[2]),
            )
            invalid_current = service.create(
                invalid,
                expected_version=0,
                command_id=f"create:{invalid.definition_id}",
            )
            with pytest.raises(
                EmployeeDefinitionError,
                match=r"BOUND_RESOURCE_(?:MISMATCH|NOT_FOUND)",
            ):
                service.decide(
                    scope,
                    invalid.definition_id,
                    invalid.revision_id,
                    invalid.digest,
                    "VALIDATE",
                    expected_version=invalid_current["aggregateVersion"],
                    command_id=f"validate:{invalid.definition_id}",
                )
    finally:
        runtime_service.repository.pool.close()
        workflow_service.repository.pool.close()
        authority.pool.close()
