# ruff: noqa: F811 -- Scoped PostgreSQL acceptance fixture setup.
"""Real owner lifecycle in throwaway PG; fixture Human facts are not acceptance."""

from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.authority_contracts import AuthorityScope, ExactGrant
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_postgres import PostgresKnowledgeRepository
from agent_console.prepared_resource_bundle import resource_content
from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
from agent_console.runtime_profile_service import RuntimeProfileService
from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
from agent_console.skill_mcp_service import SkillMcpService
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_prepared_resources import (
    OWNERS,
    PreparedResourceOwner,
    PreparedResourceTargets,
    ReviewPublication,
    reference,
)
from psycopg.rows import dict_row
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_execution_binding import upgrade


@pytest.fixture
def services(repository):
    upgrade(repository)
    root = Path(__file__).parents[1] / "migrations"
    with ExitStack() as stack:
        result = {}
        for kind, repo_type, service_type, path in (
            (
                "skill",
                PostgresSkillMcpRepository,
                SkillMcpService,
                "0002_skill_mcp_lifecycle.sql",
            ),
            (
                "runtime",
                PostgresRuntimeProfileRepository,
                RuntimeProfileService,
                "0007_workflow_runtime_profiles.sql",
            ),
            (
                "knowledge",
                PostgresKnowledgeRepository,
                KnowledgeLifecycleService,
                "0003_knowledge_operations.sql",
            ),
            (
                "agent",
                PostgresAgentDefinitionRepository,
                AgentDefinitionService,
                "0001_agent_definition_lifecycle.sql",
            ),
        ):
            repo = repo_type(repository.pool.conninfo, migration_path=root / path)
            stack.callback(repo.pool.close)
            repo.migrate()
            result[kind] = service_type(repo)
        yield result


def test_normal_owner_review_publication_exact_replay_and_rollback(
    repository, services
):
    content = resource_content()
    context = SimpleNamespace(
        principal_id="human:fixture-reviewer",
        scope=AuthorityScope("fixture324", "isolated"),
    )
    authority = SimpleNamespace(
        require=lambda *args: SimpleNamespace(decision_id="fixture-authority")
    )
    handler = PreparedResourceOwner(services)
    for kind, service in services.items():
        scope = service.scope("fixture324", "isolated")
        args = (
            (scope, "skill", "agent:fixture-preparer")
            if kind == "skill"
            else (scope, "agent:fixture-preparer")
        )
        created = service.create(*args, "隔离合成资源(测试)", content[kind])
        if kind == "knowledge":
            created = created["knowledge"]
        identity = created[
            {
                "skill": "resourceId",
                "runtime": "runtimeProfileId",
                "knowledge": "knowledgeId",
                "agent": "definitionId",
            }[kind]
        ]
        revision = created["revisions"][0]
        path = {"kind": kind, "identity": identity, "revision": revision["revisionId"]}
        payload = {
            "expectedVersion": 1,
            "digest": revision["digest"],
            "reason": "仅测试真实 owner 事务, 不代表实际人工签发",
            "idempotencyKey": "fixture-publish-" + kind,
        }
        ReviewPublication.model_validate(payload)
        with repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            assert WorkbenchGrantTargetValidator(
                None, additional=(PreparedResourceTargets(),)
            ).is_known_exact_target(
                context,
                ExactGrant(
                    OWNERS[kind],
                    "REVIEW_PUBLISH_RESOURCE",
                    reference(kind, identity, revision["revisionId"]),
                ),
                connection=c,
            )
            call = SimpleNamespace(
                operation="REVIEW_PREPARED_RESOURCE",
                context=context,
                authority=authority,
                connection=c,
                path=path,
                payload=payload,
            )
            with pytest.raises(RuntimeError, match="fixture rollback"), c.transaction():
                handler(call)
                raise RuntimeError("fixture rollback")
            owner_args = (
                (scope, "skill", identity) if kind == "skill" else (scope, identity)
            )
            assert service.repository.get(*owner_args)["lifecycleState"] == "DRAFT"
            result = handler(call)
            assert result["state"] == "PUBLISHED"
            if kind in {"runtime", "knowledge", "skill"}:
                from agent_console.plan_suggestion_domain import ExactReference
                from agent_console.prepared_execution_resources import published

                published(
                    c,
                    scope,
                    {"runtime": "RUNTIME", "knowledge": "KNOWLEDGE", "skill": "SKILL"}[
                        kind
                    ],
                    ExactReference(
                        resource_id=identity,
                        revision_id=revision["revisionId"],
                        digest=revision["digest"].removeprefix("sha256:"),
                    ),
                )
            assert handler(call) == result
            with pytest.raises(WorkbenchOwnerError, match="REPLAY_CONFLICT"):
                handler(
                    SimpleNamespace(
                        **{**vars(call), "payload": {**payload, "reason": "changed"}}
                    )
                )
        assert (
            service.repository.get(*owner_args)["publishedRevisionId"]
            == revision["revisionId"]
        )


def test_resource_draft_preparation_is_atomic_and_resume_does_not_recreate(
    repository, services
):
    import importlib.util

    script = (
        Path(__file__).resolve().parents[3] / "scripts/acceptance/s5_324_resources.py"
    )
    spec = importlib.util.spec_from_file_location("resource_preparation", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        assert all(
            r["state"] == "MISSING"
            for r in module.prepare(c, services, "fixture324", "isolated")["resources"]
        )
        with pytest.raises(RuntimeError), c.transaction():
            module.prepare(c, services, "fixture324", "isolated", write=True)
            raise RuntimeError("rollback")
        assert all(
            r["state"] == "MISSING"
            for r in module.prepare(c, services, "fixture324", "isolated")["resources"]
        )
        first = module.prepare(c, services, "fixture324", "isolated", write=True)
        assert {r["state"] for r in first["resources"]} == {"DRAFT"}
        assert (
            module.prepare(c, services, "fixture324", "isolated", write=True) == first
        )
        assert module.prepare(c, services, "fixture324", "isolated") == first


def test_prepared_employee_members_require_separate_exact_owner_reads():
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeRevision,
        MemberKind,
    )
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.workbench_employee import EmployeeDefinitionCommandOwnerAdapter

    revision = EmployeeRevision(
        ScopeIdentity("fixture324", "isolated"),
        "employee",
        "revision",
        "test role",
        ("bounded test",),
        tuple(
            CompositionMember(kind, kind.lower(), "v1", "a" * 64)
            for kind in (
                MemberKind.AGENT,
                MemberKind.SKILL,
                MemberKind.KNOWLEDGE,
                MemberKind.RUNTIME_PROFILE,
            )
        ),
    )
    seen = []
    call = SimpleNamespace(
        context=SimpleNamespace(
            principal_id="human:test", scope=AuthorityScope("fixture324", "isolated")
        ),
        authority=SimpleNamespace(
            require=lambda principal, owner, action, resource: seen.append(
                (owner, action, resource)
            )
        ),
    )
    adapter = EmployeeDefinitionCommandOwnerAdapter(None, prepared_resource_reads=True)
    adapter._require_member_reads(call, revision)
    assert seen == [
        ("AGENT", "READ", "agent:agent:v1"),
        ("SKILL", "READ_RESOURCE", "skill-invocation:prepared-resource:skill:v1"),
        ("KNOWLEDGE", "READ_RESOURCE", "knowledge:prepared-resource:knowledge:v1"),
        (
            "RUNTIME_PROFILE",
            "READ_RESOURCE",
            "runtime-profile:prepared-resource:runtime_profile:v1",
        ),
    ]
    with pytest.raises(WorkbenchOwnerError, match="MEMBER_AUTHORITY_UNAVAILABLE"):
        EmployeeDefinitionCommandOwnerAdapter(None)._require_member_reads(
            call, revision
        )

    def deny(principal, owner, action, resource):
        if owner == "KNOWLEDGE":
            raise PermissionError("exact knowledge denied")

    call.authority = SimpleNamespace(require=deny)
    with pytest.raises(PermissionError, match="exact knowledge denied"):
        adapter._require_member_reads(call, revision)


def test_engineering_employee_draft_has_no_human_decision(repository, services):
    import importlib.util

    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository

    scripts = Path(__file__).resolve().parents[3] / "scripts/acceptance"
    modules = []
    for name in ("s5_324_resources", "s5_324_employee_draft"):
        spec = importlib.util.spec_from_file_location(name, scripts / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        bundle = modules[0].prepare(c, services, "fixture324", "isolated", write=True)
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    try:
        first = modules[1].prepare(native, bundle)
        assert not first["published"]
        assert [f["action"] for f in first["facts"]] == ["CREATE"]
        assert modules[1].prepare(native, bundle) == first
    finally:
        native.pool.close()


def test_binding_uses_normal_published_owners_and_preserves_exact_instances(
    repository, services
):
    import importlib.util

    from agent_console.digital_employee_bootstrap import DigitalEmployeeProductAssembly
    from agent_console.digital_employee_postgres import (
        PostgresDigitalEmployeeRepository,
    )
    from agent_console.digital_employee_schemas import DecideEmployeeDefinition
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
    from test_execution_preparation import preparation

    scripts = Path(__file__).resolve().parents[3] / "scripts/acceptance"
    modules = []
    for name in ("s5_324_resources", "s5_324_employee_draft", "s5_324_binding"):
        spec = importlib.util.spec_from_file_location(name, scripts / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        bundle = modules[0].prepare(c, services, "fixture324", "isolated", write=True)
    native = PostgresExecutionAuthorityRepository(
        repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    try:
        employee = modules[1].prepare(native, bundle)
        semantics = preparation().semantics.model_dump(mode="json")
        with pytest.raises(ValueError, match="PUBLISHED_EXACT_EMPLOYEE_REQUIRED"):
            modules[2].assemble(native, bundle, employee, semantics)
        with native.pool.connection() as c, c.transaction():
            context = SimpleNamespace(
                principal_id="human:fixture-resource-review",
                scope=AuthorityScope("fixture324", "isolated"),
            )
            for resource in bundle["resources"]:
                PreparedResourceOwner(services)(
                    SimpleNamespace(
                        connection=c,
                        context=context,
                        authority=SimpleNamespace(
                            require=lambda *_: SimpleNamespace(
                                decision_id="fixture-owner-review"
                            )
                        ),
                        operation="REVIEW_PREPARED_RESOURCE",
                        path={
                            "kind": resource["kind"],
                            "identity": resource["identity"],
                            "revision": resource["revisionId"],
                        },
                        payload={
                            "expectedVersion": resource["aggregateVersion"],
                            "digest": resource["digest"],
                            "reason": "Synthetic test only; not Human acceptance",
                            "idempotencyKey": "fixture-" + resource["kind"],
                        },
                    )
                )
        assembly = DigitalEmployeeProductAssembly(
            None, PostgresDigitalEmployeeRepository(native)
        )
        scope = ScopeIdentity("fixture324", "isolated")
        for version, action in enumerate(("VALIDATE", "APPROVE", "PUBLISH"), 1):
            assembly.decide_definition(
                scope,
                "human:fixture-resource-review",
                employee["employeeDefinitionId"],
                action,
                DecideEmployeeDefinition(
                    employeeDefinitionRevisionId=employee[
                        "employeeDefinitionRevisionId"
                    ],
                    employeeDefinitionDigest=employee["employeeDefinitionDigest"],
                    expectedVersion=version,
                    commandId="fixture-employee-" + action,
                ),
            )
        first = modules[2].assemble(native, bundle, employee, semantics)
        assert modules[2].assemble(native, bundle, employee, semantics) == first
        assert len(first["mapping"]["participants"]) == 6
        with native.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) AS n "
                    "FROM execution_authority.digital_employee_instances"
                ).fetchone()["n"]
                == 2
            )
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.assignments"
                ).fetchone()["n"]
                == 7
            )
            assert (
                c.execute(
                    "SELECT count(*) AS n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 0
            )
    finally:
        native.pool.close()
