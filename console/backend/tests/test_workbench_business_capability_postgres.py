"""Real browser identity/CSRF/exact grants over isolated capability persistence."""

import json
import os
from contextlib import ExitStack
from dataclasses import replace

import pytest
import test_workbench_employee_commands_postgres as employee_fixture
from agent_console.business_capability import (
    BindingKind,
    CapabilityBinding,
    FixedReference,
)
from agent_console.business_capability_postgres import (
    PostgresBusinessCapabilityRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.workbench_business_capability import capability_operations
from fastapi.testclient import TestClient
from test_business_capability import capability
from test_workbench_team_postgres import allow, prepare_employee

URL = os.environ.get("CAPABILITY_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Dedicated PostgreSQL required")
PREFIX = "/api/workbench/v1/business-capabilities"


@pytest.fixture
def app(monkeypatch):
    if not URL:
        pytest.skip("Dedicated CAPABILITY_TEST_DATABASE_URL required")
    monkeypatch.setattr(employee_fixture, "DATABASE_URL", URL)
    original = employee_fixture.employee_operations
    original_bff = employee_fixture.create_workbench_bff
    database = []
    from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
    from agent_console.knowledge_postgres import PostgresKnowledgeRepository
    from agent_console.prepared_resource_bundle import resource_content
    from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
    from agent_console.skill_mcp_service import SkillMcpService

    stack, refs = ExitStack(), {}

    def operations(repository, cursors):
        database.append(repository.pool.conninfo)
        with repository.pool.connection() as connection:
            for name in (
                "0046_private_conversation.sql",
                "0047_conversation_action_facts.sql",
            ):
                connection.execute((employee_fixture.MIGRATIONS / name).read_text())
            from agent_console.capability_work_journal import migrate

            # Match the existing private-conversation ledger (no adapter column).
            connection.execute(
                "CREATE TABLE IF NOT EXISTS private_conversation.schema_migrations ("
                "version integer PRIMARY KEY, checksum text NOT NULL, "
                "applied_at timestamptz NOT NULL DEFAULT now())"
            )
            migrate(connection)
            migrate(connection)
        capabilities = PostgresBusinessCapabilityRepository(repository.pool)
        capabilities.migrate(
            employee_fixture.MIGRATIONS / "0052_business_capability.sql"
        )
        from agent_console.business_capability_publication_postgres import (
            CapabilityPublicationRepository,
        )

        CapabilityPublicationRepository(repository.pool).migrate(
            employee_fixture.MIGRATIONS / "0053_business_capability_publication.sql"
        )
        services = {}
        for kind, repo_type, service_type, migration, id_field in (
            (
                "skill",
                PostgresSkillMcpRepository,
                SkillMcpService,
                "0002_skill_mcp_lifecycle.sql",
                "resourceId",
            ),
            (
                "knowledge",
                PostgresKnowledgeRepository,
                KnowledgeLifecycleService,
                "0003_knowledge_operations.sql",
                "knowledgeId",
            ),
        ):
            resource_repo = repo_type(
                repository.pool.conninfo,
                migration_path=employee_fixture.MIGRATIONS / migration,
            )
            stack.callback(resource_repo.pool.close)
            resource_repo.migrate()
            service = service_type(resource_repo)
            services[kind] = service
            scope = service.scope(
                employee_fixture.SCOPE.tenant_id, employee_fixture.SCOPE.security_domain
            )
            args = (
                (scope, "skill", "human:fixture")
                if kind == "skill"
                else (scope, "human:fixture")
            )
            created = service.create(
                *args, "隔离能力绑定资料", resource_content()[kind]
            )
            if kind == "knowledge":
                created = created["knowledge"]
            revision = created["revisions"][0]
            refs[kind] = {
                "resource_id": created[id_field],
                "revision_id": revision["revisionId"],
                "digest": revision["digest"],
            }
        return (
            *original(repository, cursors),
            *capability_operations(capabilities, repository, services, cursors),
        )

    def with_conversations(*args, **kwargs):
        application = original_bff(
            *args, **kwargs, conversation_database_url=database[0]
        )
        application.state.test_authorizer = args[1]
        application.state.test_sessions = args[0]
        return application

    monkeypatch.setattr(employee_fixture, "create_workbench_bff", with_conversations)
    monkeypatch.setattr(employee_fixture, "employee_operations", operations)
    generator = employee_fixture.employee_workbench.__wrapped__()
    value = next(generator)
    try:
        value.capability_resources = refs
        yield value
    finally:
        stack.close()
        generator.close()


def body_for(employee, scope):
    value = replace(
        capability(),
        scope=scope,
        bindings=(
            CapabilityBinding(
                BindingKind.EMPLOYEE,
                FixedReference(
                    employee["employeeDefinitionId"],
                    employee["employeeDefinitionRevisionId"],
                    employee["employeeDefinitionDigest"],
                ),
                "核对交接材料并给出引用",
            ),
        ),
    )
    return {
        "revision": json.loads(json.dumps(value.canonical_record())),
        "expectedVersion": 0,
        "commandId": "save:1",
    }


def setup(client, app):
    csrf = employee_fixture.login(client, "alice-secret")
    employee = prepare_employee(app, client, csrf)
    session = client.get("/api/workbench/v1/session").json()["principal"]
    body = body_for(
        employee, ScopeIdentity(session["tenantId"], session["securityDomain"])
    )
    return employee_fixture.unsafe_headers(csrf), employee, body


def member_grant(app, employee):
    allow(
        app,
        "EMPLOYEE",
        "READ",
        f"employee:{employee['employeeDefinitionId']}:{employee['employeeDefinitionRevisionId']}",
        "member-read",
    )


def test_save_requires_capability_and_member_grants_and_rechecks_replay(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "cap-create",
        )
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404
        member_grant(app, employee)
        assert client.post(PREFIX, json=body).status_code == 403
        wrong = {
            **body,
            "revision": {
                **body["revision"],
                "scope": {"namespace": "other", "security_domain": "isolated"},
            },
        }
        assert client.post(PREFIX, json=wrong, headers=headers).status_code == 404
        original = body["revision"]["bindings"][0]
        wrong = {
            **body,
            "revision": {
                **body["revision"],
                "bindings": [
                    {
                        **original,
                        "reference": {**original["reference"], "digest": "f" * 64},
                    }
                ],
            },
        }
        assert client.post(PREFIX, json=wrong, headers=headers).status_code == 409
        response = client.post(PREFIX, json=body, headers=headers)
        assert response.status_code == 201, response.text
        assert response.json()["result"]["executionAuthorized"] is False
        assert client.post(PREFIX, json=body, headers=headers).json()["result"][
            "replayed"
        ]
        with app.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT count(*) n FROM business_capability.receipts"
                ).fetchone()["n"]
                == 1
            )
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='EMPLOYEE'"
            )
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404


def test_edit_keeps_old_revision_and_list_does_not_grant_read(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        member_grant(app, employee)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "cap-create",
        )
        first = client.post(PREFIX, json=body, headers=headers)
        assert first.status_code == 201, first.text
        identity = body["revision"]["capability_id"]
        old = body["revision"]["revision_id"]
        successor = {
            **body,
            "commandId": "save:2",
            "expectedVersion": 1,
            "revision": {
                **body["revision"],
                "revision_id": "capability-revision:2",
                "predecessor_revision_id": old,
                "title": "后继修改",
            },
        }
        assert client.post(PREFIX, json=successor, headers=headers).status_code == 404
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "REVISE",
            f"business-capability:{identity}:aggregate",
            "cap-revise",
        )
        response = client.post(PREFIX, json=successor, headers=headers)
        assert response.status_code == 201, response.text
        path = PREFIX + f"/{identity}/revisions/{old}"
        assert client.get(path).status_code == 404
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "READ",
            f"business-capability:{identity}:{old}",
            "cap-old-read",
        )
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["revision"] == body["revision"]
        assert response.json()["result"]["headRevisionId"] == "capability-revision:2"
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "LIST",
            "business-capability:collection",
            "cap-list",
        )
        listing = client.get(PREFIX)
        assert listing.status_code == 200, listing.text
        assert listing.json()["result"]["items"] == []
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "READ",
            f"business-capability:{identity}:capability-revision:2",
            "cap-head-read",
        )
        assert len(client.get(PREFIX).json()["result"]["items"]) == 1


def test_multikind_fixed_owner_reads_and_no_resource_mutations(app):
    from agent_console.workbench_resource_directory import target

    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        member_grant(app, employee)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "cap-create",
        )
        body["revision"]["bindings"] += [
            {"kind": kind.upper(), "reference": ref, "purpose": "只读材料检查"}
            for kind, ref in app.capability_resources.items()
        ]
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404
        for kind, ref in app.capability_resources.items():
            grant = target(kind, ref["resource_id"], ref["revision_id"])
            allow(app, grant.owner, grant.action, grant.exact_resource, kind + "-read")
        with app.authority.connection_scope() as conn:
            before = [
                conn.execute("SELECT record FROM " + table).fetchall()
                for table in (
                    "skill_mcp_resource.resources",
                    "knowledge_operation.knowledge",
                )
            ]
        response = client.post(PREFIX, json=body, headers=headers)
        assert response.status_code == 201, response.text
        identity, revision = (
            body["revision"]["capability_id"],
            body["revision"]["revision_id"],
        )
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "READ",
            f"business-capability:{identity}:{revision}",
            "cap-read",
        )
        read = client.get(PREFIX + f"/{identity}/revisions/{revision}")
        assert read.status_code == 200, read.text
        assert (
            read.json()["result"]["revision"]["bindings"]
            == body["revision"]["bindings"]
        )
        with app.authority.connection_scope() as conn:
            after = [
                conn.execute("SELECT record FROM " + table).fetchall()
                for table in (
                    "skill_mcp_resource.resources",
                    "knowledge_operation.knowledge",
                )
            ]
            assert before == after
            conn.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='KNOWLEDGE'"
            )
        assert (
            client.get(PREFIX + f"/{identity}/revisions/{revision}").status_code == 404
        )
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404


def test_new_capability_actions_reuse_existing_d12_role_without_ordinary_grants(
    monkeypatch,
):
    import test_development_administrator as d12
    from agent_console.authority_contracts import ExactGrant
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )

    monkeypatch.setattr(d12, "URL", URL)
    fixture = d12.setup.__wrapped__()
    repo, generation, sessions, reader = next(fixture)
    try:
        _, admin = sessions.authenticate_session(d12.login(sessions, "devadmin").value)
        _, ordinary = sessions.authenticate_session(d12.login(sessions).value)
        grants = tuple(
            ExactGrant("BUSINESS_CAPABILITY", action, resource)
            for action, resource in (
                ("CREATE", "business-capability:collection"),
                ("LIST", "business-capability:collection"),
                ("READ", "business-capability:future:revision"),
                ("REVISE", "business-capability:future:aggregate"),
            )
        )

        def check(context, authorization=reader):
            return authorization.has_current_grants(
                context, grants, now=sessions.clock(), generation=1, recovery_epoch=1
            )

        assert check(admin) == (True,) * 4
        assert check(ordinary) == (False,) * 4
        assert (
            check(
                replace(admin, scope=type(admin.scope)("foreign", "isolated-real-demo"))
            )
            == (False,) * 4
        )
        disabled = GenerationAuthorizationReader(
            replace(generation, development_administrator=False),
            repo,
            repo,
            recovery_epoch=1,
        )
        assert check(admin, disabled) == (False,) * 4
    finally:
        fixture.close()
