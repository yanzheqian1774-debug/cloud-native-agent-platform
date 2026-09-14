from __future__ import annotations

import hashlib
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantSource,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_employee import employee_operations
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_pagination import WorkbenchCursorCodec
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("EMPLOYEE_WORKBENCH_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="305 Employee Workbench PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"
SCOPE = AuthorityScope("tenant-a", "quality")


class Controller:
    def __init__(self, generation: StaticAuthorityGeneration) -> None:
        self.generation = generation
        self.readiness = SimpleNamespace(recovery_epoch=1)

    @contextmanager
    def protected_request(self):
        yield self.generation


def generation(now: datetime) -> StaticAuthorityGeneration:
    create = ExactGrant("EMPLOYEE", "CREATE", "employee:collection")

    def credential(name: str, *, can_create: bool = False):
        return CredentialConfiguration(
            CredentialId(f"credential-{name}"),
            hashlib.sha256(f"{name}-secret".encode()).hexdigest(),
            f"human:{name}",
            SCOPE,
            now + timedelta(hours=8),
            GrantSource.BROWSER_BOOTSTRAP,
            (
                (StaticGrant(create, GrantSource.BROWSER_BOOTSTRAP),)
                if can_create
                else ()
            ),
        )

    return StaticAuthorityGeneration(
        generation=1,
        digest="a" * 64,
        policy_version="policy-1",
        audit_source="impl-305-employee-workbench-test",
        credentials=(
            credential("alice", can_create=True),
            credential("bob"),
            credential("memberless"),
            credential("creator", can_create=True),
        ),
        requestability=(),
        credential_revocation_tombstones=frozenset(),
    )


def insert_dynamic_grant(
    repository: PostgresAuthorityRepository,
    now: datetime,
    *,
    principal: str,
    grant: ExactGrant,
    key: str,
) -> None:
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,purpose,"
            "state,created_at,decided_at) VALUES (%s,%s,%s,%s,%s,'APPROVED',%s,%s)",
            (
                f"request-{key}",
                principal,
                SCOPE.tenant_id,
                SCOPE.security_domain,
                f"EMPLOYEE_{grant.action}",
                now,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) VALUES (%s,%s,'human:admin',"
            "%s,true,'ASSIGNED_DUTY','POLICY',%s,'policy-1','test',%s)",
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
            "recovery_epoch) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'POLICY',%s,"
            "'human:admin',%s,'policy-1','test',%s,%s,%s,1)",
            (
                f"grant-{key}",
                f"decision-{key}",
                f"request-{key}",
                principal,
                SCOPE.tenant_id,
                SCOPE.security_domain,
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
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
            (
                f"grant-{key}",
                principal,
                SCOPE.tenant_id,
                SCOPE.security_domain,
                grant.owner,
                grant.action,
                grant.exact_resource,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        )


@pytest.fixture
def employee_workbench():
    original = DATABASE_URL or ""
    database_name = f"impl305_employee_{uuid.uuid4().hex}"
    admin = psycopg.connect(original, autocommit=True)
    admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = original.rsplit("/", 1)[0] + f"/{database_name}"
    authority = None
    agents = None
    try:
        with psycopg.connect(database_url) as connection:
            for version in range(1, 15):
                connection.execute(
                    next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
                )
        agents = PostgresAgentDefinitionRepository(
            database_url,
            migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
            timeout=30,
        )
        agents.migrate()
        agent_service = AgentDefinitionService(agents)
        agent_scope = agent_service.scope(SCOPE.tenant_id, SCOPE.security_domain)
        created_agent = agent_service.create(
            agent_scope,
            "human:agent-owner",
            "Quality agent",
            {
                "title": "Quality reviewer",
                "duties": ["Review quality"],
                "capabilities": ["quality.review"],
                "businessPurpose": "Prevent escaped defects",
            },
        )
        agent_revision = created_agent["revisions"][0]
        agent_service.validate(
            agent_scope, created_agent["definitionId"], "human:agent-owner", 1
        )
        reviewed = agent_service.review(
            agent_scope,
            created_agent["definitionId"],
            "human:agent-approver",
            2,
            agent_revision["digest"],
            "APPROVE",
            "approved",
        )["definition"]
        agent_service.publish(
            agent_scope,
            created_agent["definitionId"],
            "human:agent-owner",
            3,
            agent_revision["digest"],
            reviewed["reviews"][-1]["reviewId"],
        )

        authority = PostgresAuthorityRepository(
            database_url,
            migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
            timeout=30,
        )
        authority.pool.resize(1, 12)
        authority.migrate()
        now = datetime.now(UTC)
        static = generation(now)
        authority.activate_generation(
            1,
            static.digest,
            1,
            operator_id="operator:test",
            revoked_credentials=(),
            now=now,
        )
        sessions = BrowserSessionService(
            authority,
            StaticGenerationAuthenticator(static, source=GrantSource.BROWSER_BOOTSTRAP),
            BrowserSessionPolicy(
                login_nonce_lifetime=timedelta(minutes=5),
                idle_lifetime=timedelta(minutes=30),
                absolute_lifetime=timedelta(hours=8),
                csrf_lifetime=timedelta(minutes=10),
            ),
            csrf_signing_key=b"c" * 32,
            recovery_epoch=1,
        )
        authorization = GenerationAuthorizationReader(
            static, authority, authority, recovery_epoch=1
        )
        authorizer = WorkbenchOwnerAuthorization(
            Controller(static),  # type: ignore[arg-type]
            authority,
            authorization,
        )
        employees = PostgresEmployeeDefinitionRepository(authority)
        employees.migrate(MIGRATIONS / "0014_digital_employee_identity.sql")
        application = create_workbench_bff(
            sessions,
            authorizer,
            WorkbenchBffPolicy("console.example", "https://console.example"),
            operations=employee_operations(employees, WorkbenchCursorCodec(b"k" * 32)),
        )
        yield SimpleNamespace(
            application=application,
            authority=authority,
            database_url=database_url,
            now=now,
            agent_id=created_agent["definitionId"],
            agent_revision_id=agent_revision["revisionId"],
            agent_digest=agent_revision["digest"],
        )
    finally:
        if authority is not None:
            authority.close()
        if agents is not None:
            agents.pool.close()
        admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
            (database_name,),
        )
        admin.execute(f'DROP DATABASE "{database_name}"')
        admin.close()


def login(client: TestClient, credential: str) -> str:
    form = client.get(f"{PREFIX}/login")
    nonce = re.search(r'name="loginNonce" value="([^"]+)"', form.text)
    assert nonce is not None
    response = client.post(
        f"{PREFIX}/session",
        data={"loginNonce": nonce.group(1), "bootstrapCredential": credential},
        headers={"origin": "https://console.example"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return client.get(f"{PREFIX}/session").json()["csrfToken"]


def unsafe_headers(csrf: str) -> dict[str, str]:
    return {"origin": "https://console.example", "x-csrf-token": csrf}


def create_body(employee_workbench, *, command_id: str, definition_id: str):
    return {
        "employeeDefinitionId": definition_id,
        "employeeDefinitionRevisionId": "employee-revision:v1",
        "role": "Quality owner",
        "responsibilities": ["Review exact quality evidence"],
        "members": [
            {
                "kind": "AGENT",
                "resourceId": employee_workbench.agent_id,
                "revisionId": employee_workbench.agent_revision_id,
                "digest": employee_workbench.agent_digest,
            }
        ],
        "expectedVersion": 0,
        "commandId": command_id,
    }


def test_public_employee_lifecycle_uses_session_csrf_and_exact_current_grants(
    employee_workbench,
) -> None:
    employee_id = "employee-definition:public-quality"
    revision_id = "employee-revision:v1"
    aggregate = f"employee:{employee_id}:aggregate"
    exact = f"employee:{employee_id}:{revision_id}"
    agent = (
        f"agent:{employee_workbench.agent_id}:{employee_workbench.agent_revision_id}"
    )
    for principal, grant, key in (
        ("human:alice", ExactGrant("EMPLOYEE", "VALIDATE", aggregate), "validate"),
        ("human:alice", ExactGrant("EMPLOYEE", "PUBLISH", aggregate), "publish"),
        ("human:alice", ExactGrant("EMPLOYEE", "READ", exact), "read"),
        ("human:alice", ExactGrant("AGENT", "READ", agent), "alice-agent"),
        ("human:bob", ExactGrant("EMPLOYEE", "APPROVE", aggregate), "approve"),
        ("human:bob", ExactGrant("AGENT", "READ", agent), "bob-agent"),
        (
            "human:memberless",
            ExactGrant("EMPLOYEE", "VALIDATE", aggregate),
            "memberless-validate",
        ),
    ):
        insert_dynamic_grant(
            employee_workbench.authority,
            employee_workbench.now,
            principal=principal,
            grant=grant,
            key=key,
        )

    alice = TestClient(
        employee_workbench.application, base_url="https://console.example"
    )
    bob = TestClient(employee_workbench.application, base_url="https://console.example")
    memberless = TestClient(
        employee_workbench.application, base_url="https://console.example"
    )
    alice_csrf = login(alice, "alice-secret")
    bob_csrf = login(bob, "bob-secret")
    memberless_csrf = login(memberless, "memberless-secret")
    body = create_body(
        employee_workbench,
        command_id="employee-command:create-public",
        definition_id=employee_id,
    )

    no_csrf = alice.post(f"{PREFIX}/employees", json=body)
    assert no_csrf.status_code == 403
    assert no_csrf.json()["reasonCode"] == "CSRF_VALIDATION_FAILED"
    created = alice.post(
        f"{PREFIX}/employees", json=body, headers=unsafe_headers(alice_csrf)
    )
    assert created.status_code == 201
    created_result = created.json()["result"]
    assert created_result["lifecycleState"] == "DRAFT"
    assert set(created_result) == {
        "resourceKind",
        "employeeDefinitionId",
        "employeeDefinitionRevisionId",
        "employeeDefinitionDigest",
        "aggregateVersion",
        "lifecycleState",
    }
    replay = alice.post(
        f"{PREFIX}/employees", json=body, headers=unsafe_headers(alice_csrf)
    )
    assert replay.status_code == 201
    assert replay.json() == created.json()
    mismatch = alice.post(
        f"{PREFIX}/employees",
        json={**body, "role": "Changed role"},
        headers=unsafe_headers(alice_csrf),
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["reasonCode"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"

    path = f"{PREFIX}/employees/{employee_id}/revisions/{revision_id}"
    command = {
        "employeeDefinitionDigest": created_result["employeeDefinitionDigest"],
        "expectedVersion": 1,
        "commandId": "employee-command:validate",
    }
    denied_member = memberless.post(
        f"{path}/validation",
        json=command,
        headers=unsafe_headers(memberless_csrf),
    )
    assert denied_member.status_code == 404
    assert denied_member.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"

    validated = alice.post(
        f"{path}/validation", json=command, headers=unsafe_headers(alice_csrf)
    )
    assert validated.status_code == 200
    assert validated.json()["result"]["lifecycleState"] == "VALIDATED"
    assert validated.json()["result"]["aggregateVersion"] == 2

    alice_approve = alice.post(
        f"{path}/approvals",
        json={**command, "expectedVersion": 2, "commandId": "alice-approve"},
        headers=unsafe_headers(alice_csrf),
    )
    assert alice_approve.status_code == 404
    assert alice_approve.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
    stale = bob.post(
        f"{path}/approvals",
        json={**command, "expectedVersion": 1, "commandId": "stale-approve"},
        headers=unsafe_headers(bob_csrf),
    )
    assert stale.status_code == 409
    assert stale.json()["reasonCode"] == "STALE_AGGREGATE_VERSION"
    wrong_digest = bob.post(
        f"{path}/approvals",
        json={
            **command,
            "employeeDefinitionDigest": "0" * 64,
            "expectedVersion": 2,
            "commandId": "wrong-digest-approve",
        },
        headers=unsafe_headers(bob_csrf),
    )
    assert wrong_digest.status_code == 409
    assert wrong_digest.json()["reasonCode"] == "EMPLOYEE_REVISION_MISMATCH"

    with psycopg.connect(employee_workbench.database_url) as connection:
        connection.execute(
            "UPDATE agent_definition.definitions SET record=jsonb_set(record,"
            "'{enabled}','false'::jsonb) WHERE namespace=%s AND security_domain=%s "
            "AND definition_id=%s",
            (SCOPE.tenant_id, SCOPE.security_domain, employee_workbench.agent_id),
        )
    ineligible = bob.post(
        f"{path}/approvals",
        json={**command, "expectedVersion": 2, "commandId": "ineligible-approve"},
        headers=unsafe_headers(bob_csrf),
    )
    assert ineligible.status_code == 409
    assert ineligible.json()["reasonCode"] == "BOUND_RESOURCE_INELIGIBLE"
    with psycopg.connect(employee_workbench.database_url) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM digital_employee_definition.facts "
                "WHERE definition_id=%s",
                (employee_id,),
            ).fetchone()[0]
            == 2
        )
    retained = alice.get(path)
    assert retained.status_code == 200
    assert retained.json()["result"]["lifecycleState"] == "VALIDATED"

    with psycopg.connect(employee_workbench.database_url) as connection:
        connection.execute(
            "UPDATE agent_definition.definitions SET record=jsonb_set(record,"
            "'{enabled}','true'::jsonb) WHERE namespace=%s AND security_domain=%s "
            "AND definition_id=%s",
            (SCOPE.tenant_id, SCOPE.security_domain, employee_workbench.agent_id),
        )
    approved = bob.post(
        f"{path}/approvals",
        json={**command, "expectedVersion": 2, "commandId": "bob-approve"},
        headers=unsafe_headers(bob_csrf),
    )
    assert approved.status_code == 200
    assert approved.json()["result"]["lifecycleState"] == "APPROVED"
    published = alice.post(
        f"{path}/publication",
        json={**command, "expectedVersion": 3, "commandId": "alice-publish"},
        headers=unsafe_headers(alice_csrf),
    )
    assert published.status_code == 200
    assert published.json()["result"]["lifecycleState"] == "PUBLISHED"
    assert published.json()["result"]["aggregateVersion"] == 4

    refreshed = alice.get(path)
    assert refreshed.status_code == 200
    result = refreshed.json()["result"]
    assert result["lifecycleState"] == "PUBLISHED"
    assert result["publicationState"] == "PUBLISHED"
    assert (
        result["employeeDefinitionDigest"] == created_result["employeeDefinitionDigest"]
    )
    assert "facts" not in result
    assert "decisionId" not in repr(result)


def test_public_validation_rejects_exact_member_digest_mismatch(
    employee_workbench,
) -> None:
    employee_id = "employee-definition:member-mismatch"
    aggregate = f"employee:{employee_id}:aggregate"
    agent = (
        f"agent:{employee_workbench.agent_id}:{employee_workbench.agent_revision_id}"
    )
    for grant, key in (
        (ExactGrant("EMPLOYEE", "VALIDATE", aggregate), "mismatch-validate"),
        (ExactGrant("AGENT", "READ", agent), "mismatch-agent"),
    ):
        insert_dynamic_grant(
            employee_workbench.authority,
            employee_workbench.now,
            principal="human:alice",
            grant=grant,
            key=key,
        )
    alice = TestClient(
        employee_workbench.application, base_url="https://console.example"
    )
    csrf = login(alice, "alice-secret")
    body = create_body(
        employee_workbench,
        command_id="employee-command:member-mismatch",
        definition_id=employee_id,
    )
    body["members"][0]["digest"] = "0" * 64
    created = alice.post(f"{PREFIX}/employees", json=body, headers=unsafe_headers(csrf))
    assert created.status_code == 201
    result = created.json()["result"]
    validation = alice.post(
        f"{PREFIX}/employees/{employee_id}/revisions/employee-revision:v1/validation",
        json={
            "employeeDefinitionDigest": result["employeeDefinitionDigest"],
            "expectedVersion": 1,
            "commandId": "employee-command:member-mismatch-validate",
        },
        headers=unsafe_headers(csrf),
    )
    assert validation.status_code == 409
    assert validation.json()["reasonCode"] == "BOUND_RESOURCE_MISMATCH"
    with psycopg.connect(employee_workbench.database_url) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM digital_employee_definition.facts "
                "WHERE definition_id=%s",
                (employee_id,),
            ).fetchone()[0]
            == 1
        )


def test_public_create_confirmation_does_not_imply_read(employee_workbench) -> None:
    creator = TestClient(
        employee_workbench.application, base_url="https://console.example"
    )
    csrf = login(creator, "creator-secret")
    employee_id = "employee-definition:create-only"
    body = create_body(
        employee_workbench,
        command_id="employee-command:create-only",
        definition_id=employee_id,
    )
    created = creator.post(
        f"{PREFIX}/employees", json=body, headers=unsafe_headers(csrf)
    )
    assert created.status_code == 201
    assert created.json()["result"]["employeeDefinitionId"] == employee_id
    denied = creator.get(
        f"{PREFIX}/employees/{employee_id}/revisions/employee-revision:v1"
    )
    assert denied.status_code == 404
    assert denied.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"


def test_concurrent_public_create_replays_one_employee_revision(
    employee_workbench,
) -> None:
    application = employee_workbench.application
    alice = TestClient(application, base_url="https://console.example")
    csrf = login(alice, "alice-secret")
    cookie = alice.cookies.get(SESSION_COOKIE)
    assert cookie is not None
    body = create_body(
        employee_workbench,
        command_id="employee-command:concurrent-create",
        definition_id="employee-definition:concurrent",
    )

    def create_once(_):
        client = TestClient(application, base_url="https://console.example")
        client.cookies.set(SESSION_COOKIE, cookie)
        response = client.post(
            f"{PREFIX}/employees", json=body, headers=unsafe_headers(csrf)
        )
        assert response.status_code == 201
        return response.json()["result"]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(create_once, range(12)))

    assert len({item["employeeDefinitionDigest"] for item in results}) == 1
    assert {item["aggregateVersion"] for item in results} == {1}
    with psycopg.connect(employee_workbench.database_url) as connection:
        counts = connection.execute(
            "SELECT "
            "(SELECT count(*) FROM digital_employee_definition.revisions "
            "WHERE definition_id=%s) AS revisions,"
            "(SELECT count(*) FROM digital_employee_definition.facts "
            "WHERE definition_id=%s) AS facts",
            (body["employeeDefinitionId"], body["employeeDefinitionId"]),
        ).fetchone()
    assert counts == (1, 1)
