"""323-only synthetic purchase fixture, created through canonical owner services."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.business_problem_domain import (
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
)
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_domain import PlanSemantics
from test_plan_suggestion_v2 import sample

MIGRATIONS = Path(__file__).parents[1] / "migrations"
SCOPE = ScopeIdentity("tenant-a", "quality")
PROBLEM_ID = "problem:323-purchase"


def seed(database, authority):
    now = datetime(2026, 9, 17, 2, tzinfo=UTC)
    problems = PostgresBusinessProblemRepository(
        database, migration_path=MIGRATIONS / "0013_business_problem_authority.sql"
    )
    problems.migrate()
    value = sample()
    problem = BusinessProblemRevision(
        SCOPE,
        PROBLEM_ID,
        PROBLEM_ID + ":1",
        1,
        None,
        "整理延期采购订单清单",
        "测试来源: 323五行合成采购样本。" + "\n".join(value["business_rules"]),
        "human:323",
        "human:323",
        now,
    )
    problems.create_problem(
        problem,
        idempotency_key="323-create",
        payload_digest=problem.digest,
        authorized=True,
    )
    criterion = SuccessCriterionRevision(
        SCOPE,
        "criterion:323-report",
        "criterion:323-report:1",
        1,
        None,
        CriterionType.EVIDENCE_PRESENCE,
        {"minimum_count": 1},
        ("REPORT",),
        "report-presence",
        "1",
        {"businessRules": value["business_rules"]},
        "human:323",
        now,
    )
    problems.add_criterion_revision(
        criterion,
        expected_version=None,
        idempotency_key="323-criterion",
        payload_digest=criterion.digest,
        authorized=True,
    )
    criteria = SuccessCriteriaSetRevision(
        SCOPE,
        "criteria:323:1",
        PROBLEM_ID,
        problem.revision_id,
        1,
        None,
        (criterion.revision_id,),
        "human:323",
        now,
    )
    problems.add_criteria_set_revision(
        criteria,
        expected_version=1,
        idempotency_key="323-set",
        payload_digest=criteria.digest,
        authorized=True,
    )
    current = problems.get_aggregate(SCOPE, PROBLEM_ID, authorized=True)
    version = problems.transition(
        SCOPE,
        PROBLEM_ID,
        BusinessProblemState.ACTIVE,
        actor_id="human:323",
        expected_version=current.aggregate_version,
        event_id="event:323-active",
        idempotency_key="323-active",
        payload_digest="f" * 64,
        authorized=True,
    )
    value["target"] = {
        "problem": {
            "resource_id": PROBLEM_ID,
            "revision_id": problem.revision_id,
            "digest": problem.digest,
        },
        "criteria": {
            "resource_id": PROBLEM_ID,
            "revision_id": criteria.set_revision_id,
            "digest": criteria.digest,
        },
        "criterion_revision_ids": [criterion.revision_id],
        "expected_problem_version": version,
    }
    agent_repo = PostgresAgentDefinitionRepository(
        database, migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql"
    )
    agent_repo.migrate()
    agents = AgentDefinitionService(agent_repo)
    agent_scope = agents.scope(SCOPE.namespace, SCOPE.security_domain)
    agent = agents.create(
        agent_scope,
        "human:323",
        "采购分析测试Agent",
        {
            "title": "采购分析",
            "duties": ["读取采购快照和汇总报告"],
            "capabilities": ["purchase.analysis"],
            "businessPurpose": "合成采购规划测试",
        },
    )
    agent_revision = agent["revisions"][0]
    agents.validate(agent_scope, agent["definitionId"], "human:323", 1)
    reviewed = agents.review(
        agent_scope,
        agent["definitionId"],
        "human:323-reviewer",
        2,
        agent_revision["digest"],
        "APPROVE",
        "TEST_ONLY",
    )["definition"]
    agents.publish(
        agent_scope,
        agent["definitionId"],
        "human:323",
        3,
        agent_revision["digest"],
        reviewed["reviews"][-1]["reviewId"],
    )
    employees = PostgresEmployeeDefinitionRepository(authority)
    employees.migrate(MIGRATIONS / "0014_digital_employee_identity.sql")

    class FixtureAuthorization:
        def require(self, *args):
            return "323-controlled-fixture-authoring"

    service = EmployeeDefinitionService(employees, FixtureAuthorization())
    employee = EmployeeRevision(
        SCOPE,
        "employee:323-purchase",
        "employee:323-purchase:1",
        "采购分析员",
        ("读取采购快照", "汇总与报告"),
        (
            CompositionMember(
                MemberKind.AGENT,
                agent["definitionId"],
                agent_revision["revisionId"],
                agent_revision["digest"],
            ),
        ),
    )
    state = service.create(
        employee, expected_version=0, command_id="323-employee-create"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        state = service.decide(
            SCOPE,
            employee.definition_id,
            employee.revision_id,
            employee.digest,
            action,
            expected_version=state["aggregateVersion"],
            command_id="323-employee-" + action,
        )
    exact = {
        "resource_id": employee.definition_id,
        "revision_id": employee.revision_id,
        "digest": employee.digest,
    }
    problems.pool.close()
    agent_repo.pool.close()
    return assemble(value, exact)


def assemble(value, exact):
    value["requirements"][0]["selected"] = exact
    value["requirements"][0]["preparation"] = (
        "真实owner中的已发布测试数字员工, 非企业生产目录"
    )
    value["requirements"].append(
        {
            "requirement_id": "validator",
            "kind": "EMPLOYEE",
            "name": "数据校验员",
            "purpose": "校验日期、异常和延期口径",
            "required": True,
            "preparation": "职责需求待准备, 不创建员工实例",
        }
    )
    skills = [
        ("dates", "日期校验", "检查缺失日期与来源冲突"),
        ("overdue", "延期计算", "按承诺日期与未交数量判断延期"),
        ("summary", "供应商汇总", "按供应商及数量单位汇总"),
        ("report", "报告生成", "整理清单、摘要与异常说明"),
    ]
    for identity, name, purpose in skills:
        value["requirements"].append(
            {
                "requirement_id": identity,
                "kind": "SKILL",
                "name": name,
                "purpose": purpose,
                "required": True,
                "preparation": "尚未选择精确发布版本",
            }
        )
    value["requirements"].append(
        {
            "requirement_id": "knowledge",
            "kind": "KNOWLEDGE",
            "name": "采购政策",
            "purpose": "可选补充依据",
            "required": False,
            "preparation": "本例以已确认标准为准",
        }
    )
    for index, task in enumerate(value["tasks"]):
        task["criterion_revision_ids"] = ["criterion:323-report:1"]
        task["employee_requirement_id"] = "validator" if index in (1, 2) else "employee"
        task["responsibility"] = (
            "校验与延期识别" if index in (1, 2) else "采购分析与报告"
        )
        task["requirement_ids"] = ["snapshot" if index == 0 else skills[index - 1][0]]
    result = PlanSemantics.model_validate(value).model_dump(mode="json")
    return SimpleNamespace(semantics=result, employee=exact)


def recover(database):
    """Read a partially seeded 323 fixture without recreating owner resources."""
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database, row_factory=dict_row) as connection:
        problem = connection.execute(
            "SELECT r.*,p.aggregate_version FROM business_problem_authority.problems p "
            "JOIN business_problem_authority.problem_revisions r ON "
            "(p.namespace,p.security_domain,p.current_revision_id)="
            "(r.namespace,r.security_domain,r.revision_id) "
            "WHERE p.business_problem_id=%s",
            (PROBLEM_ID,),
        ).fetchone()
        criteria = connection.execute(
            "SELECT * FROM business_problem_authority.criteria_sets "
            "WHERE business_problem_id=%s ORDER BY revision DESC LIMIT 1",
            (PROBLEM_ID,),
        ).fetchone()
        employee = connection.execute(
            "SELECT definition_id AS resource_id,revision_id,digest "
            "FROM digital_employee_definition.revisions WHERE definition_id=%s",
            ("employee:323-purchase",),
        ).fetchone()
    if not problem or not criteria or not employee:
        raise ValueError("323_PARTIAL_SEED_REQUIRES_INSPECTION")
    value = sample()
    value["target"] = {
        "problem": {
            "resource_id": PROBLEM_ID,
            "revision_id": problem["revision_id"],
            "digest": problem["digest"],
        },
        "criteria": {
            "resource_id": PROBLEM_ID,
            "revision_id": criteria["set_revision_id"],
            "digest": criteria["digest"],
        },
        "criterion_revision_ids": ["criterion:323-report:1"],
        "expected_problem_version": problem["aggregate_version"],
    }
    return assemble(value, employee)


def seed_model(database_url):
    """Create only a synthetic published model in the dedicated test database."""
    from agent_console.model_governance import (
        InvocationLimit,
        ModelConnectionProfileRevision,
        ModelDefinition,
        ModelEndpointRevision,
        ModelLifecycleAction,
        ModelLifecycleFact,
        ModelProviderRevision,
        ModelRevision,
        ModelScope,
        SecretReference,
    )
    from agent_console.model_governance_postgres import (
        PostgresModelGovernanceRepository,
    )

    real_provider = False
    responses_url = None
    ADAPTER_ID = "unused-real-adapter"
    ADAPTER_REVISION = "unused-real-revision"
    now = datetime.now(UTC)
    scope = ModelScope("tenant-a", "quality")
    definition = ModelDefinition(
        scope,
        "model:s5-323-synthetic",
        "team:draft-assistance",
        "human:fixture-owner",
        now,
    )
    provider = ModelProviderRevision(
        scope,
        "provider:s5-323-synthetic",
        "provider-revision:s5-323:1",
        ADAPTER_ID if real_provider else "adapter:deterministic-synthetic",
        ADAPTER_REVISION if real_provider else "adapter-revision:1",
        ("CHAT",),
        "human:fixture-owner",
        now,
    )
    endpoint = ModelEndpointRevision(
        scope,
        "endpoint:s5-323-synthetic",
        "endpoint-revision:s5-323:1",
        responses_url if real_provider else "https://synthetic.invalid/v1",
        "test-only",
        ("HTTPS", "NO_REDIRECT") if real_provider else ("SYNTHETIC",),
        "human:fixture-owner",
        now,
    )
    connection = ModelConnectionProfileRevision(
        scope,
        "connection-profile:s5-323-synthetic",
        "connection-profile-revision:s5-323:1",
        endpoint.identity,
        SecretReference(
            "secret-reference:s5-323-mock"
            if real_provider
            else "secret-reference:s5-323-none",
            "mock-v1" if real_provider else "synthetic-v1",
        ),
        2 if real_provider else 5,
        5 if real_provider else 30,
        "human:fixture-owner",
        now,
    )
    revision = ModelRevision(
        scope,
        definition.model_id,
        "model-revision:s5-323:1",
        1,
        None,
        provider.identity,
        endpoint.identity,
        connection.identity,
        "mock-model-321" if real_provider else "synthetic-problem-draft-v1",
        ("JSON_SCHEMA",),
        ("CHAT", "STRUCTURED_OUTPUT"),
        (
            InvocationLimit(
                "max_input_tokens", 10_000 if real_provider else 4096, "TOKEN"
            ),
            InvocationLimit("max_output_tokens", 1024, "TOKEN"),
        ),
        "human:fixture-owner",
        now,
    )
    repository = PostgresModelGovernanceRepository(
        database_url, migration_path=MIGRATIONS / "0019_model_governance.sql"
    )
    repository.migrate()
    repository.create(definition)
    repository.add_provider_revision(provider)
    repository.add_endpoint_revision(endpoint)
    repository.add_connection_profile_revision(connection)
    repository.add_revision(revision)
    repository.advance_head(
        scope,
        definition.model_id,
        revision.revision_id,
        expected_aggregate_version=1,
    )
    for ordinal, action in enumerate(
        (
            ModelLifecycleAction.VALIDATED,
            ModelLifecycleAction.HUMAN_REVIEWED,
            ModelLifecycleAction.PUBLISHED,
        ),
        1,
    ):
        repository.append_fact(
            ModelLifecycleFact(
                scope,
                f"model-fact:s5-323:{ordinal}",
                revision.identity,
                ordinal,
                action,
                "human:fixture-reviewer",
                f"decision:s5-323:{ordinal}",
                now,
            )
        )
    repository.close()

    return {
        "resource_id": revision.model_id,
        "revision_id": revision.revision_id,
        "digest": revision.digest,
    }
