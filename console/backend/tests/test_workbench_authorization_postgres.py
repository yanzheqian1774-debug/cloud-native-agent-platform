from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, current_thread
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    BrowserSession,
    CredentialId,
    ExactGrant,
    GrantId,
    GrantSource,
    SessionId,
    TrustedRequestContext,
    VerifiedPrincipal,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    InstanceLifecycle,
    InstanceRecord,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import (
    AgentInstanceId,
    AssignmentId,
    AttemptId,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    PostgresExecutionAuthorityRepository,
    RuntimeInstanceId,
    TaskRunId,
    WorkflowRunId,
    canonical_bytes,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.workbench_agent import agent_operations
from agent_console.workbench_employee import (
    digital_employee_operations,
    employee_operations,
)
from agent_console.workbench_owner_authorization import (
    WorkbenchOwnerAuthorization,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_workflow import workflow_operations
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from agent_console.workflow_definition_service import WorkflowDefinitionService

DATABASE_URL = os.environ.get("AUTHORITY_I2_TEST_DATABASE_URL")
MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "0018_browser_session_grant_authority.sql"
)
WORKFLOW_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0007_workflow_runtime_profiles.sql"
)
EXECUTION_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0008_execution_runtime_authority.sql"
)
EMPLOYEE_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0014_digital_employee_identity.sql"
)
AGENT_MIGRATION = (
    Path(__file__).parents[1] / "migrations" / "0001_agent_definition_lifecycle.sql"
)


class FakeController:
    def __init__(self, generation: StaticAuthorityGeneration) -> None:
        self.generation = generation
        self.readiness = SimpleNamespace(recovery_epoch=1)

    @contextmanager
    def protected_request(self):
        yield self.generation


class FakeRepository:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    @contextmanager
    def connection_scope(self):
        yield self.connection


class FakeConnection:
    def __init__(self) -> None:
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)


class FakeReader:
    def __init__(self, allowed: tuple[bool, ...]) -> None:
        self.allowed = allowed
        self.connection = None
        self.configure_transaction = None

    def has_current_grants(self, context, grants, **values):
        self.connection = values["connection"]
        self.configure_transaction = values["configure_transaction"]
        return self.allowed


def generation(now: datetime) -> StaticAuthorityGeneration:
    return StaticAuthorityGeneration(
        generation=1,
        digest="a" * 64,
        policy_version="policy-1",
        audit_source="impl-305-test",
        credentials=(
            CredentialConfiguration(
                credential_id=CredentialId("credential-alice"),
                credential_sha256="b" * 64,
                principal_id="human:alice",
                scope=AuthorityScope("tenant-a", "quality"),
                expires_at=now + timedelta(days=1),
                authentication_source=GrantSource.BROWSER_BOOTSTRAP,
                grants=(),
            ),
        ),
        requestability=(),
        credential_revocation_tombstones=frozenset(),
    )


def context() -> TrustedRequestContext:
    return TrustedRequestContext(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        "session-one",
        AuthenticationSource.BROWSER_SESSION,
        "policy-1",
    )


def test_adapter_shares_authorization_connection_and_denies_atomically() -> None:
    now = datetime(2029, 1, 1, tzinfo=UTC)
    repository = FakeRepository()
    reader = FakeReader((True,))
    adapter = WorkbenchOwnerAuthorization(
        FakeController(generation(now)),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        reader,  # type: ignore[arg-type]
        clock=lambda: now,
    )
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1")
    result = adapter.execute(
        context(),
        (grant,),
        operation="READ_PROBLEM",
        payload={},
        path={"problem_id": "problem-1"},
        query={},
        handler=lambda call: call.connection,
    )
    assert result is repository.connection
    assert reader.connection is repository.connection
    assert reader.configure_transaction is False
    assert repository.connection.statements == [
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED"
    ]

    denied = WorkbenchOwnerAuthorization(
        FakeController(generation(now)),  # type: ignore[arg-type]
        repository,  # type: ignore[arg-type]
        FakeReader((False,)),  # type: ignore[arg-type]
        clock=lambda: now,
    )
    called = False

    def handler(call):
        nonlocal called
        called = True

    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        denied.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=handler,
        )
    assert not called


@pytest.fixture
def repository():
    if not DATABASE_URL:
        pytest.skip("305 exclusive real PostgreSQL 15 required")
    database_name = f"impl305_{uuid.uuid4().hex}"
    admin = psycopg.connect(DATABASE_URL, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = DATABASE_URL.rsplit("/", 1)[0] + f"/{database_name}"
    value = None
    try:
        value = PostgresAuthorityRepository(
            database_url, migration_path=MIGRATION, timeout=30.0
        )
        value.pool.resize(1, 8)
        value.migrate()
        yield value
    finally:
        if value is not None:
            value.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def seed(repository: PostgresAuthorityRepository):
    now = datetime.now(UTC)
    principal = VerifiedPrincipal(
        "human:alice",
        AuthorityScope("tenant-a", "quality"),
        CredentialId("credential-alice"),
        now + timedelta(days=1),
        "policy-1",
    )
    session = BrowserSession(
        SessionId("session-one"),
        principal,
        now,
        now,
        now + timedelta(minutes=30),
        now + timedelta(hours=8),
        1,
        1,
    )
    repository.create_session(session, hashlib.sha256(b"secret").hexdigest())
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:problem-1")
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.active_generation "
            "(generation,generation_digest,recovery_epoch,activated_by,activated_at) "
            "VALUES (1,%s,1,'operator:test',%s)",
            ("a" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES ('request-one','human:alice','tenant-a','quality',"
            "'READ_PROBLEM','APPROVED',%s,%s)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES ('decision-one','request-one','human:bob','meta-one',true,"
            "'ASSIGNED_DUTY','POLICY',%s,'policy-1','test',%s)",
            ("c" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES ('grant-one','decision-one','request-one',"
            "'human:alice','tenant-a','quality','BUSINESS_PROBLEM','READ',"
            "'business-problem:problem-1','POLICY',%s,'human:bob','meta-one',"
            "'policy-1','test',%s,%s,%s,1)",
            ("c" * 64, now - timedelta(minutes=1), now + timedelta(hours=1), now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES ('grant-one','human:alice','tenant-a','quality',"
            "'BUSINESS_PROBLEM','READ','business-problem:problem-1',%s,%s,1)",
            (now - timedelta(minutes=1), now + timedelta(hours=1)),
        )
        connection.execute("CREATE TABLE owner_effects (effect_id text PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE owner_replay_effects ("
            "idempotency_key text PRIMARY KEY,payload_digest text NOT NULL,"
            "result_record jsonb NOT NULL)"
        )
    static = generation(now)
    reader = GenerationAuthorizationReader(
        static, repository, repository, recovery_epoch=1
    )
    adapter = WorkbenchOwnerAuthorization(
        FakeController(static),  # type: ignore[arg-type]
        repository,
        reader,
        clock=lambda: now,
    )
    return now, grant, adapter


def seed_workflow_grant(
    repository: PostgresAuthorityRepository, now: datetime, grant: ExactGrant
) -> None:
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES ('request-workflow','human:alice','tenant-a','quality',"
            "'READ_WORKFLOW','APPROVED',%s,%s)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES ('decision-workflow','request-workflow','human:bob',"
            "'meta-workflow',true,'ASSIGNED_DUTY','POLICY',%s,'policy-1','test',%s)",
            ("e" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES ('grant-workflow','decision-workflow',"
            "'request-workflow','human:alice','tenant-a','quality',%s,%s,%s,"
            "'POLICY',%s,'human:bob','meta-workflow','policy-1','test',%s,%s,%s,1)",
            (
                grant.owner,
                grant.action,
                grant.exact_resource,
                "e" * 64,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES ('grant-workflow','human:alice','tenant-a','quality',"
            "%s,%s,%s,%s,%s,1)",
            (
                grant.owner,
                grant.action,
                grant.exact_resource,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        )


def seed_employee_grant(
    repository: PostgresAuthorityRepository, now: datetime, grant: ExactGrant
) -> None:
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES ('request-employee','human:alice','tenant-a','quality',"
            "'READ_EMPLOYEE','APPROVED',%s,%s)",
            (now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES ('decision-employee','request-employee','human:bob',"
            "'meta-employee',true,'ASSIGNED_DUTY','POLICY',%s,'policy-1','test',%s)",
            ("d" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES ('grant-employee','decision-employee',"
            "'request-employee','human:alice','tenant-a','quality',%s,%s,%s,"
            "'POLICY',%s,'human:bob','meta-employee','policy-1','test',%s,%s,%s,1)",
            (
                grant.owner,
                grant.action,
                grant.exact_resource,
                "d" * 64,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES ('grant-employee','human:alice','tenant-a','quality',"
            "%s,%s,%s,%s,%s,1)",
            (
                grant.owner,
                grant.action,
                grant.exact_resource,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        )


def seed_digital_employee_read_grant(
    repository: PostgresAuthorityRepository,
    now: datetime,
    grant: ExactGrant,
    *,
    key: str,
) -> GrantId:
    grant_id = GrantId(f"grant-{key}")
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES (%s,'human:alice','tenant-a','quality',%s,'APPROVED',%s,%s)",
            (f"request-{key}", f"READ_{key.upper()}", now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES (%s,%s,'human:bob',%s,true,'ASSIGNED_DUTY','POLICY',%s,"
            "'policy-1','test',%s)",
            (
                f"decision-{key}",
                f"request-{key}",
                f"meta-{key}",
                "f" * 64,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES (%s,%s,%s,'human:alice','tenant-a','quality',"
            "%s,%s,%s,'POLICY',%s,'human:bob',%s,'policy-1','test',%s,%s,%s,1)",
            (
                str(grant_id),
                f"decision-{key}",
                f"request-{key}",
                grant.owner,
                grant.action,
                grant.exact_resource,
                "f" * 64,
                f"meta-{key}",
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES (%s,'human:alice','tenant-a','quality',%s,%s,%s,%s,%s,1)",
            (
                str(grant_id),
                grant.owner,
                grant.action,
                grant.exact_resource,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        )
    return grant_id


def workflow_content(description: str) -> dict:
    return {
        "description": description,
        "tasks": [{"taskId": "collect", "name": "Collect", "dependsOn": []}],
        "inputs": [],
        "outputs": ["facts"],
        "runtimeProfile": {
            "kind": "RUNTIME_PROFILE",
            "resourceId": "runtime-profile:one",
            "revisionId": "runtime-profile-revision:one",
        },
    }


@pytest.mark.parametrize(
    ("operation_name", "revocation"),
    (
        ("READ_EMPLOYEE_INSTANCE", "grant"),
        ("READ_EMPLOYEE_ASSIGNMENT", "session"),
    ),
)
def test_instance_assignment_exact_reads_share_authorization_transaction(
    repository, monkeypatch, operation_name: str, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    execution_repository = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=EXECUTION_MIGRATION,
        timeout=30.0,
    )
    digital_repository = PostgresDigitalEmployeeRepository(execution_repository)
    try:
        execution_repository.migrate()
        scope = ScopeIdentity("tenant-a", "quality")
        instance = InstanceRecord(
            scope,
            DigitalEmployeeInstanceId("employee-instance:quality"),
            1,
            DefinitionReference(
                "employee-definition:quality",
                "employee-revision:v1",
                "d" * 64,
                True,
                True,
                "DIGITAL_EMPLOYEE_DEFINITION_V1",
            ),
            "human:owner",
            "organization:quality",
            InstanceLifecycle.ENABLED,
            "workspace:private",
            "model:private",
            ("policy:private",),
            now,
            now,
        )
        assignment = AssignmentRecord(
            scope,
            AssignmentId("employee-assignment:review"),
            instance.instance_id,
            "human:reviewer",
            "Quality reviewer",
            AssignmentLifecycle.ACTIVE,
            now,
            None,
            1,
            "command:private",
        )
        with execution_repository.pool.connection() as connection:
            connection.execute(
                "INSERT INTO execution_authority.digital_employee_instances "
                "(namespace,security_domain,digital_employee_instance_id,"
                "definition_revision_id,aggregate_version,record) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(instance.instance_id),
                    instance.definition.revision_id,
                    instance.version,
                    json.dumps(
                        digital_repository._instance_record(
                            instance, "instance-command:private"
                        )
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.assignments "
                "(namespace,security_domain,assignment_id,"
                "digital_employee_instance_id,approved_input_digest,record) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(assignment.assignment_id),
                    str(assignment.instance_id),
                    "a" * 64,
                    json.dumps(
                        {
                            "assignee_id": assignment.assignee_id,
                            "business_role": assignment.business_role,
                            "lifecycle": assignment.lifecycle.value,
                            "effective_from": assignment.effective_from.isoformat(),
                            "effective_until": None,
                            "version": assignment.version,
                            "command_id": assignment.command_id,
                            "predecessor_assignment_id": None,
                        }
                    ),
                ),
            )

        operation = next(
            item
            for item in digital_employee_operations(digital_repository)
            if item.name == operation_name
        )
        path = {
            "instance_id": str(instance.instance_id),
            "assignment_id": str(assignment.assignment_id),
        }
        grants = tuple(operation.grant_builder(context(), path, {}, {}))
        grant_key = (
            "instance" if operation_name == "READ_EMPLOYEE_INSTANCE" else "assignment"
        )
        grant_id = seed_digital_employee_read_grant(
            repository, now, grants[0], key=grant_key
        )

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        method_name = (
            "read_instance_for_workbench"
            if operation_name == "READ_EMPLOYEE_INSTANCE"
            else "read_assignment_for_workbench"
        )
        original_read = getattr(digital_repository, method_name)

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_read(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(digital_repository, method_name, capture_owner)
        result = adapter.execute(
            context(),
            grants,
            operation=operation.name,
            payload={},
            path=path,
            query={},
            handler=operation.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert "command:private" not in repr(result)
        assert "workspace:private" not in repr(result)
        assert "policy:private" not in repr(result)
        if operation_name == "READ_EMPLOYEE_INSTANCE":
            assert result["instanceId"] == str(instance.instance_id)
        else:
            assert result["assignmentId"] == str(assignment.assignment_id)
            assert result["instanceId"] == str(instance.instance_id)

        def protected_owner_query(*args, **kwargs):
            pytest.fail("protected Digital Employee owner query ran after denial")

        monkeypatch.setattr(digital_repository, method_name, protected_owner_query)
        wrong_path = dict(path)
        wrong_key = (
            "instance_id"
            if operation_name == "READ_EMPLOYEE_INSTANCE"
            else "assignment_id"
        )
        wrong_path[wrong_key] = f"{wrong_path[wrong_key]}:other"
        wrong_grants = tuple(operation.grant_builder(context(), wrong_path, {}, {}))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                wrong_grants,
                operation=operation.name,
                payload={},
                path=wrong_path,
                query={},
                handler=operation.handler,
            )

        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )
        monkeypatch.setattr(digital_repository, method_name, capture_owner)

        if operation_name == "READ_EMPLOYEE_ASSIGNMENT":
            with pytest.raises(WorkbenchOwnerError) as mismatch:
                adapter.execute(
                    context(),
                    grants,
                    operation=operation.name,
                    payload={},
                    path={**path, "instance_id": "employee-instance:other"},
                    query={},
                    handler=operation.handler,
                )
            assert mismatch.value.reason_code == "ASSIGNMENT_NOT_FOUND"

        if revocation == "grant":
            repository.revoke_grant(
                grant_id,
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key=f"revoke-{operation_name.lower()}",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )

        monkeypatch.setattr(digital_repository, method_name, protected_owner_query)
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )
    finally:
        execution_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_placement_exact_read_verifies_parent_chain_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    execution_repository = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=EXECUTION_MIGRATION,
        timeout=30.0,
    )
    digital_repository = PostgresDigitalEmployeeRepository(execution_repository)
    try:
        execution_repository.migrate()
        scope = ScopeIdentity("tenant-a", "quality")
        instance_id = DigitalEmployeeInstanceId("employee-instance:quality")
        assignment_id = AssignmentId("employee-assignment:review")
        workflow_id = WorkflowRunId("workflow-run:quality")
        task_id = TaskRunId("task-run:quality")
        attempt_id = AttemptId("attempt:quality")
        agent_id = AgentInstanceId("agent-instance:quality")
        runtime_id = RuntimeInstanceId("runtime-instance:quality")
        placement_id = PlacementId("placement:quality")
        request = PlacementRequest(
            PlacementRequestId("placement-request:quality"),
            scope,
            workflow_id,
            task_id,
            attempt_id,
            agent_id,
            "agent-revision:v1",
            "runtime-profile:v1",
            (),
            (),
            (),
            (),
            now,
        )
        decision = PlacementDecision.create(
            placement_id=placement_id,
            request_id=request.request_id,
            decision=PlacementDecisionKind.PLACED,
            runtime_instance_id=runtime_id,
            policy_version="policy:v1",
            compatibility_facts=("GPU_COMPATIBLE",),
            limitation_codes=("CAPACITY_LIMIT",),
            decided_at=now,
        )
        instance = InstanceRecord(
            scope,
            instance_id,
            1,
            DefinitionReference(
                "employee-definition:quality",
                "employee-revision:v1",
                "d" * 64,
                True,
                True,
                "DIGITAL_EMPLOYEE_DEFINITION_V1",
                "agent-definition:quality",
                "agent-revision:v1",
                "a" * 64,
            ),
            "human:owner",
            "organization:quality",
            InstanceLifecycle.ENABLED,
            None,
            None,
            (),
            now,
            now,
        )
        assignment = AssignmentRecord(
            scope,
            assignment_id,
            instance_id,
            "human:reviewer",
            "Quality reviewer",
            AssignmentLifecycle.ACTIVE,
            now,
            None,
            1,
            "assignment-command:private",
        )
        with execution_repository.pool.connection() as connection:
            connection.execute(
                "INSERT INTO execution_authority.digital_employee_instances "
                "(namespace,security_domain,digital_employee_instance_id,"
                "definition_revision_id,aggregate_version,record) "
                "VALUES (%s,%s,%s,%s,1,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(instance_id),
                    instance.definition.revision_id,
                    json.dumps(
                        digital_repository._instance_record(
                            instance, "instance-command:private"
                        )
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.assignments "
                "(namespace,security_domain,assignment_id,"
                "digital_employee_instance_id,approved_input_digest,record) "
                "VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(assignment_id),
                    str(instance_id),
                    "b" * 64,
                    json.dumps(
                        {
                            "assignee_id": assignment.assignee_id,
                            "business_role": assignment.business_role,
                            "lifecycle": assignment.lifecycle.value,
                            "effective_from": assignment.effective_from.isoformat(),
                            "effective_until": None,
                            "version": 1,
                            "command_id": assignment.command_id,
                        }
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.workflow_runs VALUES "
                "(%s,%s,%s,%s,'plan-revision:v1',NULL,NULL,'{}'::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(workflow_id),
                    str(assignment_id),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.task_runs VALUES "
                "(%s,%s,%s,%s,'{}'::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(task_id),
                    str(workflow_id),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.attempts VALUES "
                "(%s,%s,%s,%s,NULL,%s,'{}'::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(attempt_id),
                    str(task_id),
                    "c" * 64,
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.runtime_instances "
                "(namespace,security_domain,runtime_instance_id,current_generation,"
                "aggregate_version,record) VALUES (%s,%s,%s,1,1,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(runtime_id),
                    json.dumps({"current_generation": 1}),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.agent_instances "
                "(namespace,security_domain,agent_instance_id,agent_revision_id,"
                "runtime_instance_id,aggregate_version,record) "
                "VALUES (%s,%s,%s,%s,%s,1,%s::jsonb)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(agent_id),
                    "agent-revision:v1",
                    str(runtime_id),
                    json.dumps(
                        {
                            "agent_definition_id": "agent-definition:quality",
                            "agent_revision_id": "agent-revision:v1",
                            "agent_digest": "a" * 64,
                            "runtime_instance_id": str(runtime_id),
                        }
                    ),
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.placement_requests "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(request.request_id),
                    request.digest,
                    request.canonical_bytes,
                    str(attempt_id),
                    str(agent_id),
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO execution_authority.placement_decisions "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    str(placement_id),
                    str(request.request_id),
                    decision.decision.value,
                    str(runtime_id),
                    decision.digest,
                    json.dumps(json.loads(canonical_bytes(decision))["payload"]),
                    now,
                ),
            )

        operation = next(
            item
            for item in digital_employee_operations(digital_repository)
            if item.name == "READ_EMPLOYEE_PLACEMENT"
        )
        path = {
            "instance_id": str(instance_id),
            "assignment_id": str(assignment_id),
            "placement_id": str(placement_id),
        }
        query = {
            "attemptId": str(attempt_id),
            "agentInstanceId": str(agent_id),
        }
        grants = tuple(operation.grant_builder(context(), path, {}, query))
        grant_id = seed_digital_employee_read_grant(
            repository, now, grants[0], key=f"placement-{revocation}"
        )
        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_read = digital_repository.read_placement_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_read(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            digital_repository, "read_placement_for_workbench", capture_owner
        )
        result = adapter.execute(
            context(),
            grants,
            operation=operation.name,
            payload={},
            path=path,
            query=query,
            handler=operation.handler,
        )
        assert connections["owner"] is connections["authorization"]
        assert set(result) == {
            "placementId",
            "requestId",
            "decision",
            "runtimeInstanceId",
            "policyVersion",
            "compatibilityFacts",
            "limitationCodes",
            "decidedAt",
            "digest",
            "binding",
        }
        assert result["binding"] == {
            "instanceId": str(instance_id),
            "assignmentId": str(assignment_id),
            "attemptId": str(attempt_id),
            "agentInstanceId": str(agent_id),
        }
        assert result["digest"] == decision.digest

        wrong_parent = {**path, "assignment_id": "employee-assignment:other"}
        with pytest.raises(WorkbenchOwnerError, match="PLACEMENT_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=wrong_parent,
                query=query,
                handler=operation.handler,
            )

        original_active = digital_repository.active_attempts
        monkeypatch.setattr(
            digital_repository,
            "active_attempts",
            lambda *args, **kwargs: (),
        )
        with pytest.raises(WorkbenchOwnerError, match="PLACEMENT_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query=query,
                handler=operation.handler,
            )
        monkeypatch.setattr(digital_repository, "active_attempts", original_active)

        def protected_owner_query(*args, **kwargs):
            pytest.fail("protected Placement owner query ran after denial")

        monkeypatch.setattr(
            digital_repository,
            "read_placement_for_workbench",
            protected_owner_query,
        )
        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query=query,
                handler=operation.handler,
            )
        wrong_path = {**path, "placement_id": "placement:other"}
        wrong_grants = tuple(operation.grant_builder(context(), wrong_path, {}, query))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                wrong_grants,
                operation=operation.name,
                payload={},
                path=wrong_path,
                query=query,
                handler=operation.handler,
            )

        if revocation == "grant":
            repository.revoke_grant(
                grant_id,
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-placement",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query=query,
                handler=operation.handler,
            )
    finally:
        execution_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_employee_exact_read_uses_authorization_transaction_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    execution_repository = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=EXECUTION_MIGRATION,
        timeout=30.0,
    )
    employee_repository = PostgresEmployeeDefinitionRepository(execution_repository)
    try:
        execution_repository.migrate()
        employee_repository.migrate(EMPLOYEE_MIGRATION)
        scope = ScopeIdentity("tenant-a", "quality")
        first = EmployeeRevision(
            scope,
            "employee-definition:quality",
            "employee-revision:v1",
            "Quality owner",
            ("Review quality",),
            (
                CompositionMember(
                    MemberKind.AGENT,
                    "agent-definition:quality",
                    "agent-revision:v1",
                    "a" * 64,
                ),
            ),
        )
        second = EmployeeRevision(
            scope,
            first.definition_id,
            "employee-revision:v2",
            "Quality owner successor",
            ("Review quality", "Coordinate remediation"),
            first.members,
            first.revision_id,
        )
        with execution_repository.pool.connection() as connection:
            connection.execute(
                "INSERT INTO digital_employee_definition.definitions "
                "VALUES (%s,%s,%s,2)",
                (scope.namespace, scope.security_domain, first.definition_id),
            )
            for revision in (first, second):
                connection.execute(
                    "INSERT INTO digital_employee_definition.revisions "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        revision.definition_id,
                        revision.revision_id,
                        revision.predecessor_revision_id,
                        revision.digest,
                        json.dumps(revision.record),
                    ),
                )
            connection.execute(
                "INSERT INTO digital_employee_definition.facts "
                "(namespace,security_domain,definition_id,revision_id,action,"
                "ordinal,revision_digest,decision_id,command_id,payload_digest) "
                "VALUES (%s,%s,%s,%s,'CREATE',1,%s,'decision-create',"
                "'command-create',%s),(%s,%s,%s,%s,'PUBLISH',2,%s,"
                "'decision-publish','command-publish',%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    first.definition_id,
                    first.revision_id,
                    first.digest,
                    "1" * 64,
                    scope.namespace,
                    scope.security_domain,
                    first.definition_id,
                    first.revision_id,
                    first.digest,
                    "2" * 64,
                ),
            )

        operation = next(
            item
            for item in employee_operations(
                employee_repository, WorkbenchCursorCodec(b"k" * 32)
            )
            if item.name == "READ_EMPLOYEE_REVISION"
        )
        path = {
            "employee_definition_id": first.definition_id,
            "revision_id": first.revision_id,
        }
        grants = tuple(operation.grant_builder(context(), path, {}, {}))
        seed_employee_grant(repository, now, grants[0])

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_read = employee_repository.read_revision_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_read(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            employee_repository, "read_revision_for_workbench", capture_owner
        )
        result = adapter.execute(
            context(),
            grants,
            operation=operation.name,
            payload={},
            path=path,
            query={},
            handler=operation.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert result["employeeDefinitionRevisionId"] == first.revision_id
        assert first.digest == result["employeeDefinitionDigest"]
        assert result["publicationState"] == "PUBLISHED"
        assert second.revision_id not in repr(result)
        assert "predecessor" not in repr(result).lower()
        assert "facts" not in repr(result).lower()

        def protected_owner_query(*args, **kwargs):
            pytest.fail("protected Employee owner query ran after authorization denial")

        monkeypatch.setattr(
            employee_repository,
            "read_revision_for_workbench",
            protected_owner_query,
        )
        wrong_path = {**path, "revision_id": second.revision_id}
        wrong_grants = tuple(operation.grant_builder(context(), wrong_path, {}, {}))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                wrong_grants,
                operation=operation.name,
                payload={},
                path=wrong_path,
                query={},
                handler=operation.handler,
            )
        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )

        if revocation == "grant":
            repository.revoke_grant(
                GrantId("grant-employee"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-employee",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )

        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )
    finally:
        execution_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_agent_exact_read_uses_authorization_transaction_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    agent_repository = PostgresAgentDefinitionRepository(
        repository.pool.conninfo,
        migration_path=AGENT_MIGRATION,
        timeout=30.0,
    )
    try:
        agent_repository.migrate()
        service = AgentDefinitionService(agent_repository)
        scope = service.scope("tenant-a", "quality")
        created = service.create(
            scope,
            "human:alice",
            "Quality agent",
            {
                "title": "Quality analyst",
                "duties": ["Review quality"],
                "capabilities": ["quality.review"],
                "businessPurpose": "Prevent defects",
            },
        )
        revision = created["revisions"][0]
        operation = next(
            item
            for item in agent_operations(
                agent_repository, WorkbenchCursorCodec(b"k" * 32)
            )
            if item.name == "READ_AGENT_REVISION"
        )
        path = {
            "definition_id": created["definitionId"],
            "revision_id": revision["revisionId"],
        }
        grants = tuple(operation.grant_builder(context(), path, {}, {}))
        grant_id = seed_digital_employee_read_grant(
            repository, now, grants[0], key="agent"
        )

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_read = agent_repository.read_revision_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_read(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            agent_repository, "read_revision_for_workbench", capture_owner
        )
        result = adapter.execute(
            context(),
            grants,
            operation=operation.name,
            payload={},
            path=path,
            query={},
            handler=operation.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert result == {
            "definitionId": created["definitionId"],
            "revisionId": revision["revisionId"],
            "digest": revision["digest"],
            "name": "Quality agent",
            "role": {
                "title": "Quality analyst",
                "duties": ["Review quality"],
                "businessPurpose": "Prevent defects",
                "capabilities": ["quality.review"],
            },
        }
        assert "facts" not in repr(result).lower()
        assert "bindings" not in repr(result).lower()

        def protected_owner_query(*args, **kwargs):
            pytest.fail("protected Agent owner query ran after authorization denial")

        monkeypatch.setattr(
            agent_repository,
            "read_revision_for_workbench",
            protected_owner_query,
        )
        wrong_path = {**path, "revision_id": f"{revision['revisionId']}:other"}
        wrong_grants = tuple(operation.grant_builder(context(), wrong_path, {}, {}))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                wrong_grants,
                operation=operation.name,
                payload={},
                path=wrong_path,
                query={},
                handler=operation.handler,
            )
        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )

        if revocation == "grant":
            repository.revoke_grant(
                grant_id,
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-agent",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )
    finally:
        agent_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_agent_list_keyset_scope_independence_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    agent_repository = PostgresAgentDefinitionRepository(
        repository.pool.conninfo,
        migration_path=AGENT_MIGRATION,
        timeout=30.0,
    )
    try:
        agent_repository.migrate()
        service = AgentDefinitionService(agent_repository)
        scope = service.scope("tenant-a", "quality")

        def publish(name: str) -> tuple[dict, dict]:
            created = service.create(
                scope,
                "human:alice",
                name,
                {
                    "title": f"{name} title",
                    "duties": ["Review quality"],
                    "capabilities": ["quality.review"],
                    "businessPurpose": "Prevent defects",
                },
            )
            revision = created["revisions"][0]
            service.validate(scope, created["definitionId"], "human:alice", 1)
            reviewed = service.review(
                scope,
                created["definitionId"],
                "human:alice",
                2,
                revision["digest"],
                "APPROVE",
                "approved",
            )["definition"]
            published = service.publish(
                scope,
                created["definitionId"],
                "human:alice",
                3,
                revision["digest"],
                reviewed["reviews"][-1]["reviewId"],
            )["definition"]
            return published, revision

        first, first_revision = publish("Alpha agent")
        second, second_revision = publish("Zeta agent")
        successor = service.successor(scope, first["definitionId"], "human:alice", 4)[
            "definition"
        ]
        draft_revision_id = successor["currentDraftRevisionId"]

        codec = WorkbenchCursorCodec(b"k" * 32)
        operations = agent_operations(agent_repository, codec)
        listing = next(item for item in operations if item.name == "LIST_AGENTS")
        exact = next(item for item in operations if item.name == "READ_AGENT_REVISION")
        grants = tuple(listing.grant_builder(context(), {}, {}, {"pageSize": 1}))
        grant_id = seed_digital_employee_read_grant(
            repository, now, grants[0], key="agent-list"
        )

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_list = agent_repository.list_published_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_list(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            agent_repository, "list_published_for_workbench", capture_owner
        )
        first_page = adapter.execute(
            context(),
            grants,
            operation=listing.name,
            payload={},
            path={},
            query={"pageSize": 1},
            handler=listing.handler,
        )
        second_page = adapter.execute(
            context(),
            grants,
            operation=listing.name,
            payload={},
            path={},
            query={"pageSize": 1, "cursor": first_page["nextCursor"]},
            handler=listing.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert [
            first_page["items"][0]["definitionId"],
            second_page["items"][0]["definitionId"],
        ] == sorted(
            (first["definitionId"], second["definitionId"]),
            key=lambda value: value.encode("utf-8"),
        )
        first_item = next(
            item
            for item in (first_page["items"][0], second_page["items"][0])
            if item["definitionId"] == first["definitionId"]
        )
        assert first_item["revisionId"] == first_revision["revisionId"]
        assert first_item["revisionId"] != draft_revision_id
        assert second_page.get("nextCursor") is None
        assert "total" not in repr((first_page, second_page)).lower()
        assert "facts" not in repr((first_page, second_page)).lower()
        assert second_revision["digest"] in repr((first_page, second_page))

        def protected_list(*args, **kwargs):
            pytest.fail("protected Agent list query ran after authorization denial")

        monkeypatch.setattr(
            agent_repository, "list_published_for_workbench", protected_list
        )
        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=listing.name,
                payload={},
                path={},
                query={"pageSize": 1},
                handler=listing.handler,
            )

        def protected_exact(*args, **kwargs):
            pytest.fail("Agent exact owner query ran without READ authorization")

        monkeypatch.setattr(
            agent_repository, "read_revision_for_workbench", protected_exact
        )
        exact_path = {
            "definition_id": first["definitionId"],
            "revision_id": first_revision["revisionId"],
        }
        exact_grants = tuple(exact.grant_builder(context(), exact_path, {}, {}))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                exact_grants,
                operation=exact.name,
                payload={},
                path=exact_path,
                query={},
                handler=exact.handler,
            )

        if revocation == "grant":
            repository.revoke_grant(
                grant_id,
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-agent-list",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=listing.name,
                payload={},
                path={},
                query={"pageSize": 1},
                handler=listing.handler,
            )
    finally:
        agent_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_employee_list_keyset_scope_independence_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    execution_repository = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=EXECUTION_MIGRATION,
        timeout=30.0,
    )
    employee_repository = PostgresEmployeeDefinitionRepository(execution_repository)
    try:
        execution_repository.migrate()
        employee_repository.migrate(EMPLOYEE_MIGRATION)
        scope = ScopeIdentity("tenant-a", "quality")
        revisions = (
            EmployeeRevision(
                scope,
                "employee-definition:alpha",
                "employee-revision:v1",
                "Alpha owner",
                ("Review quality",),
                (
                    CompositionMember(
                        MemberKind.AGENT,
                        "agent-definition:quality",
                        "agent-revision:v1",
                        "a" * 64,
                    ),
                ),
            ),
            EmployeeRevision(
                scope,
                "employee-definition:zeta",
                "employee-revision:v1",
                "Zeta owner",
                ("Review quality",),
                (
                    CompositionMember(
                        MemberKind.AGENT,
                        "agent-definition:quality",
                        "agent-revision:v1",
                        "a" * 64,
                    ),
                ),
            ),
        )
        with execution_repository.pool.connection() as connection:
            for index, revision in enumerate(revisions, start=1):
                connection.execute(
                    "INSERT INTO digital_employee_definition.definitions "
                    "VALUES (%s,%s,%s,1)",
                    (scope.namespace, scope.security_domain, revision.definition_id),
                )
                connection.execute(
                    "INSERT INTO digital_employee_definition.revisions "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        revision.definition_id,
                        revision.revision_id,
                        revision.predecessor_revision_id,
                        revision.digest,
                        json.dumps(revision.record),
                    ),
                )
                connection.execute(
                    "INSERT INTO digital_employee_definition.facts "
                    "(namespace,security_domain,definition_id,revision_id,action,"
                    "ordinal,revision_digest,decision_id,command_id,payload_digest) "
                    "VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        revision.definition_id,
                        revision.revision_id,
                        "PUBLISH" if index == 1 else "CREATE",
                        revision.digest,
                        f"decision-list-{index}",
                        f"command-list-{index}",
                        str(index) * 64,
                    ),
                )

        codec = WorkbenchCursorCodec(b"k" * 32)
        operations = employee_operations(employee_repository, codec)
        listing = next(item for item in operations if item.name == "LIST_EMPLOYEES")
        exact = next(
            item for item in operations if item.name == "READ_EMPLOYEE_REVISION"
        )
        grants = tuple(listing.grant_builder(context(), {}, {}, {"pageSize": 1}))
        grant_id = seed_digital_employee_read_grant(
            repository, now, grants[0], key="employee-list"
        )

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_list = employee_repository.list_revisions_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_list(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            employee_repository, "list_revisions_for_workbench", capture_owner
        )
        first_page = adapter.execute(
            context(),
            grants,
            operation=listing.name,
            payload={},
            path={},
            query={"pageSize": 1},
            handler=listing.handler,
        )
        second_page = adapter.execute(
            context(),
            grants,
            operation=listing.name,
            payload={},
            path={},
            query={"pageSize": 1, "cursor": first_page["nextCursor"]},
            handler=listing.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert (
            first_page["items"][0]["employeeDefinitionId"] == revisions[0].definition_id
        )
        assert first_page["items"][0]["publicationState"] == "PUBLISHED"
        assert (
            second_page["items"][0]["employeeDefinitionId"]
            == revisions[1].definition_id
        )
        assert second_page["items"][0]["publicationState"] == "NOT_PUBLISHED"
        assert second_page.get("nextCursor") is None
        assert "total" not in repr((first_page, second_page)).lower()
        assert "responsibilities" not in repr((first_page, second_page)).lower()

        def protected_list(*args, **kwargs):
            pytest.fail("protected Employee list query ran after authorization denial")

        monkeypatch.setattr(
            employee_repository, "list_revisions_for_workbench", protected_list
        )
        wrong_scope = TrustedRequestContext(
            "human:alice",
            AuthorityScope("tenant-b", "quality"),
            "session-one",
            AuthenticationSource.BROWSER_SESSION,
            "policy-1",
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                wrong_scope,
                grants,
                operation=listing.name,
                payload={},
                path={},
                query={"pageSize": 1},
                handler=listing.handler,
            )

        def protected_exact(*args, **kwargs):
            pytest.fail("Employee exact owner query ran without READ authorization")

        monkeypatch.setattr(
            employee_repository, "read_revision_for_workbench", protected_exact
        )
        exact_path = {
            "employee_definition_id": revisions[0].definition_id,
            "revision_id": revisions[0].revision_id,
        }
        exact_grants = tuple(exact.grant_builder(context(), exact_path, {}, {}))
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                exact_grants,
                operation=exact.name,
                payload={},
                path=exact_path,
                query={},
                handler=exact.handler,
            )

        if revocation == "grant":
            repository.revoke_grant(
                grant_id,
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-employee-list",
                payload_digest="e" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=listing.name,
                payload={},
                path={},
                query={"pageSize": 1},
                handler=listing.handler,
            )
    finally:
        execution_repository.pool.close()


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_workflow_exact_read_uses_authorization_transaction_and_revocation(
    repository, monkeypatch, revocation: str
) -> None:
    now, _, adapter = seed(repository)
    workflow_repository = PostgresWorkflowDefinitionRepository(
        repository.pool.conninfo,
        migration_path=WORKFLOW_MIGRATION,
        timeout=30.0,
    )
    try:
        workflow_repository.migrate()
        service = WorkflowDefinitionService(workflow_repository)
        scope = service.scope("tenant-a", "quality")
        created = service.create(
            scope, "human:alice", "Workflow", workflow_content("first revision")
        )
        edited = service.edit(
            scope,
            created["workflowDefinitionId"],
            "human:alice",
            1,
            workflow_content("second revision"),
        )
        first_revision = created["revisions"][0]["revisionId"]
        second_revision = edited["revisions"][1]["revisionId"]
        operation = workflow_operations(service)[1]
        path = {
            "workflow_definition_id": created["workflowDefinitionId"],
            "revision_id": first_revision,
        }
        grants = tuple(operation.grant_builder(context(), path, {}, {}))
        assert len(grants) == 1
        seed_workflow_grant(repository, now, grants[0])

        connections = {}
        original_authorize = adapter.authorization.has_current_grants
        original_read = workflow_repository.read_revision_for_workbench

        def capture_authorization(*args, **kwargs):
            connections["authorization"] = kwargs["connection"]
            return original_authorize(*args, **kwargs)

        def capture_owner(connection, *args, **kwargs):
            connections["owner"] = connection
            return original_read(connection, *args, **kwargs)

        monkeypatch.setattr(
            adapter.authorization, "has_current_grants", capture_authorization
        )
        monkeypatch.setattr(
            workflow_repository, "read_revision_for_workbench", capture_owner
        )
        result = adapter.execute(
            context(),
            grants,
            operation=operation.name,
            payload={},
            path=path,
            query={},
            handler=operation.handler,
        )

        assert connections["owner"] is connections["authorization"]
        assert result["revision"]["revisionId"] == first_revision
        assert second_revision not in repr(result)

        if revocation == "grant":
            repository.revoke_grant(
                GrantId("grant-workflow"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-workflow",
                payload_digest="f" * 64,
                now=now,
            )
        else:
            repository.revoke_session(
                SessionId("session-one"),
                reason="LOGOUT",
                actor_id="human:alice",
                now=now,
            )

        def protected_owner_query(*args, **kwargs):
            pytest.fail("protected Workflow owner query ran after authorization denial")

        monkeypatch.setattr(
            workflow_repository,
            "read_revision_for_workbench",
            protected_owner_query,
        )
        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            adapter.execute(
                context(),
                grants,
                operation=operation.name,
                payload={},
                path=path,
                query={},
                handler=operation.handler,
            )
    finally:
        workflow_repository.pool.close()


def wait_for_database_waiters(
    repository: PostgresAuthorityRepository, minimum: int
) -> None:
    """Wait for PostgreSQL lock registration, not a guessed timing window."""
    deadline = time.monotonic() + 5
    with psycopg.connect(repository.pool.conninfo, autocommit=True) as connection:
        while time.monotonic() < deadline:
            total = connection.execute(
                "SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a "
                "USING (pid) WHERE a.datname=current_database() AND NOT l.granted"
            ).fetchone()[0]
            if total >= minimum:
                return
            time.sleep(0.01)
    pytest.fail(f"expected at least {minimum} PostgreSQL lock waiters")


def replaying_owner_handler(
    *,
    payload_digest: str,
    first_has_claim: Event,
    release_first: Event,
    replay_entered_claim: Event,
):
    def handler(call):
        is_first = current_thread().name.startswith("owner-effect")
        if not is_first:
            replay_entered_claim.set()
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 297))",
            ("workbench-owner-replay",),
        )
        if is_first:
            first_has_claim.set()
            assert release_first.wait(timeout=30)
        row = call.connection.execute(
            "SELECT payload_digest,result_record FROM owner_replay_effects "
            "WHERE idempotency_key='same-key' FOR UPDATE"
        ).fetchone()
        if row is not None:
            if row["payload_digest"] != payload_digest:
                raise WorkbenchOwnerError("BUSINESS_PROBLEM_CONFLICT", 409)
            return row["result_record"]
        result = {"effectId": "effect-one"}
        call.connection.execute(
            "INSERT INTO owner_replay_effects "
            "(idempotency_key,payload_digest,result_record) "
            "VALUES ('same-key',%s,%s::jsonb)",
            (payload_digest, json.dumps(result)),
        )
        return result

    return handler


def execute_replay_candidate(
    adapter: WorkbenchOwnerAuthorization,
    grant: ExactGrant,
    *,
    payload_digest: str,
    first_has_claim: Event,
    release_first: Event,
    replay_entered_claim: Event,
):
    return adapter.execute(
        context(),
        (grant,),
        operation="OWNER_REPLAY",
        payload={"payloadDigest": payload_digest},
        path={},
        query={},
        handler=replaying_owner_handler(
            payload_digest=payload_digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        ),
    )


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_revocation_serializes_after_owner_commit(repository, revocation: str) -> None:
    now, grant, adapter = seed(repository)
    handler_entered = Event()
    release_handler = Event()
    revocation_started = Event()

    def owner_call():
        def handler(call):
            handler_entered.set()
            assert release_handler.wait(timeout=5)
            call.connection.execute(
                "INSERT INTO owner_effects(effect_id) VALUES ('effect-one')"
            )
            return {"effectId": "effect-one"}

        return adapter.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=handler,
        )

    def revoke():
        revocation_started.set()
        if revocation == "grant":
            return repository.revoke_grant(
                GrantId("grant-one"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-one",
                payload_digest="d" * 64,
                now=now,
            )
        return repository.revoke_session(
            SessionId("session-one"),
            reason="LOGOUT",
            actor_id="human:alice",
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        effect_future = executor.submit(owner_call)
        assert handler_entered.wait(timeout=5)
        revoke_future = executor.submit(revoke)
        assert revocation_started.wait(timeout=5)
        with pytest.raises(TimeoutError):
            revoke_future.result(timeout=0.2)
        release_handler.set()
        assert effect_future.result(timeout=5) == {"effectId": "effect-one"}
        assert revoke_future.result(timeout=5)

    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM owner_effects"
            ).fetchone()["total"]
            == 1
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        adapter.execute(
            context(),
            (grant,),
            operation="READ_PROBLEM",
            payload={},
            path={},
            query={},
            handler=lambda call: {},
        )


@pytest.mark.parametrize("revocation", ["grant", "session"])
def test_waiting_same_payload_replays_once_before_revocation(
    repository, revocation: str
) -> None:
    now, grant, adapter = seed(repository)
    first_has_claim = Event()
    release_first = Event()
    replay_entered_claim = Event()
    revocation_started = Event()
    payload_digest = "e" * 64

    def invoke(digest: str):
        return execute_replay_candidate(
            adapter,
            grant,
            payload_digest=digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        )

    def revoke():
        revocation_started.set()
        if revocation == "grant":
            return repository.revoke_grant(
                GrantId("grant-one"),
                actor_id="human:bob",
                reason="DUTY_ENDED",
                idempotency_key="revoke-during-replay",
                payload_digest="f" * 64,
                now=now,
            )
        return repository.revoke_session(
            SessionId("session-one"),
            reason="LOGOUT",
            actor_id="human:alice",
            now=now,
        )

    with (
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-effect"
        ) as owner_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-replay"
        ) as replay_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-revoke"
        ) as revoke_executor,
    ):
        owner = owner_executor.submit(invoke, payload_digest)
        assert first_has_claim.wait(timeout=5)
        replay = replay_executor.submit(invoke, payload_digest)
        assert replay_entered_claim.wait(timeout=5)
        wait_for_database_waiters(repository, 1)
        revoke_future = revoke_executor.submit(revoke)
        assert revocation_started.wait(timeout=5)
        wait_for_database_waiters(repository, 2)
        release_first.set()

        expected = {"effectId": "effect-one"}
        assert owner.result(timeout=5) == expected
        assert replay.result(timeout=5) == expected
        assert revoke_future.result(timeout=5)

    assert replay_entered_claim.is_set()
    with repository.pool.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS total FROM owner_replay_effects"
            ).fetchone()["total"]
            == 1
        )
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        invoke(payload_digest)


def test_waiting_different_payload_conflicts_without_repeating_effect(
    repository,
) -> None:
    _, grant, adapter = seed(repository)
    first_has_claim = Event()
    release_first = Event()
    replay_entered_claim = Event()

    def invoke(digest: str):
        return execute_replay_candidate(
            adapter,
            grant,
            payload_digest=digest,
            first_has_claim=first_has_claim,
            release_first=release_first,
            replay_entered_claim=replay_entered_claim,
        )

    with (
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-effect"
        ) as owner_executor,
        ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="owner-replay"
        ) as replay_executor,
    ):
        owner = owner_executor.submit(invoke, "1" * 64)
        assert first_has_claim.wait(timeout=5)
        conflict = replay_executor.submit(invoke, "2" * 64)
        assert replay_entered_claim.wait(timeout=5)
        wait_for_database_waiters(repository, 1)
        release_first.set()

        assert owner.result(timeout=5) == {"effectId": "effect-one"}
        with pytest.raises(WorkbenchOwnerError) as raised:
            conflict.result(timeout=5)
        assert raised.value.reason_code == "BUSINESS_PROBLEM_CONFLICT"
        assert raised.value.status_code == 409

    assert replay_entered_claim.is_set()
    with repository.pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*) AS total,min(payload_digest) AS payload_digest "
            "FROM owner_replay_effects"
        ).fetchone()
    assert row == {"total": 1, "payload_digest": "1" * 64}
