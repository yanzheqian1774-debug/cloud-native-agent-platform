"""323 controlled planning semantics and real PostgreSQL transaction acceptance."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_domain import (
    PlanningConflict,
    PlanningError,
    PlanSemantics,
    ProposalRevision,
)
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from psycopg_pool import ConnectionPool
from pydantic import ValidationError


def sample():
    """Synthetic plan only: no order data or execution results are asserted."""
    ids = ("T1", "T2a", "T2b", "T3a", "T3b")
    titles = ("读取快照", "校验数据", "识别延期", "供应商汇总", "生成报告")
    ref = {"resource_id": "problem", "revision_id": "problem:1", "digest": "a" * 64}
    return {
        "scenario": "OVERDUE_PURCHASE_ORDERS",
        "target": {
            "problem": ref,
            "criteria": {**ref, "resource_id": "problem"},
            "criterion_revision_ids": ["criterion:1"],
            "expected_problem_version": 3,
        },
        "title": "整理延期采购订单清单",
        "business_rules": [
            "2026-09-17 / Asia/Shanghai, 承诺日期严格早于判定日",
            "仅授权范围未关闭未取消且未交量大于零的明细",
            "按来源、公司、订单、明细、分期去重; 冲突与缺日期单列",
            "按供应商和单位汇总, 不跨单位相加",
        ],
        "boundaries": ["只读, 不修改订单, 不催交, 不发通知"],
        "stages": [
            {"stage_id": "S1", "title": "读取快照", "task_ids": ["T1"]},
            {"stage_id": "S2", "title": "校验与延期识别", "task_ids": ["T2a", "T2b"]},
            {"stage_id": "S3", "title": "汇总与报告", "task_ids": ["T3a", "T3b"]},
        ],
        "tasks": [
            {
                "task_id": identity,
                "title": titles[i],
                "responsibility": "采购分析职责",
                "employee_requirement_id": "employee",
                "depends_on": list(ids[i - 1 : i]),
                "inputs": ["冻结订单快照" if i == 0 else f"A{i}"],
                "outputs": [f"A{i + 1}"],
                "requirement_ids": ["snapshot"],
                "criterion_revision_ids": ["criterion:1"],
            }
            for i, identity in enumerate(ids)
        ],
        "requirements": [
            {
                "requirement_id": "employee",
                "kind": "EMPLOYEE",
                "name": "采购分析员",
                "purpose": "承担采购分析与报告职责",
                "required": True,
                "preparation": "待选择已发布数字员工",
            },
            {
                "requirement_id": "snapshot",
                "kind": "MCP",
                "name": "采购快照",
                "purpose": "提供授权范围内冻结采购数据",
                "required": True,
                "preparation": "准备只读采购接口或披露冻结导出替代路线",
            },
        ],
    }


def proposal(identity=None):
    return ProposalRevision(
        proposal_id=identity or uuid4().hex,
        revision=1,
        predecessor_digest=None,
        invocation_id=uuid4().hex,
        semantics=PlanSemantics.model_validate(sample()),
    )


def test_immutable_and_untrusted_readiness():
    value = proposal()
    with pytest.raises(ValidationError):
        value.semantics.title = "changed"
    invalid = sample()
    invalid["requirements"][0]["status"] = "MATCHED"
    with pytest.raises(ValidationError):
        PlanSemantics.model_validate(invalid)


@pytest.mark.parametrize("mutation", ["cycle", "missing", "duplicate", "case"])
def test_graph_rejects(mutation):
    value = sample()
    if mutation == "cycle":
        value["tasks"][0]["depends_on"] = ["T3b"]
    elif mutation == "missing":
        value["tasks"][0]["requirement_ids"] = ["does-not-exist"]
    elif mutation == "duplicate":
        value["tasks"][1]["task_id"] = "T1"
    else:
        value["stages"][1]["task_ids"] = ["T2b", "T2a"]
    with pytest.raises(ValidationError):
        PlanSemantics.model_validate(value)


@pytest.fixture
def repository(monkeypatch):
    url = os.environ.get("PLANNING323_TEST_DATABASE_URL")
    if not url:
        pytest.skip("323 exclusive PostgreSQL required")
    from pathlib import Path

    import psycopg
    from psycopg import sql

    name = "planning323_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        isolated_url = url.rsplit("/", 1)[0] + "/" + name
        monkeypatch.setenv("PLANNING323_TEST_DATABASE_URL", isolated_url)
        try:
            with psycopg.connect(isolated_url) as connection:
                for version in range(1, 13):
                    connection.execute(
                        next(
                            (Path(__file__).parents[1] / "migrations").glob(
                                f"{version:04d}_*.sql"
                            )
                        ).read_text()
                    )
            with ConnectionPool(isolated_url, min_size=1, max_size=6) as pool:
                repository = PostgresPlanningRepository(pool)
                repository.migrate()
                yield repository
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def confirm(repo, scope, value, key, expected=0, fail=None):
    with repo.transaction(scope, value.proposal_id, authorized=True) as cursor:
        return repo.confirmation(
            cursor,
            scope,
            value,
            actor="test-actor",
            key=key,
            expected_plan_version=expected,
            authority_basis="TEST_EXACT_GRANT",
            before_commit=fail,
        )


def test_atomic_concurrent_replay_history_isolation(repository):
    repo = repository
    scope = ScopeIdentity("test-323-" + uuid4().hex, "test")
    value = proposal()
    with repo.transaction(scope, value.proposal_id, authorized=True) as cursor:
        repo.add_proposal(cursor, scope, value)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda key: confirm(repo, scope, value, key), ("a", "b", "c", "d")
            )
        )
    assert all(r == results[0] for r in results)
    assert confirm(repo, scope, value, "a") == results[0]
    with pytest.raises(PlanningConflict, match="IDEMPOTENCY"):
        confirm(repo, scope, value, "a", expected=99)
    semantics = value.semantics.model_dump()
    semantics["title"] = "修订采购计划"
    successor = ProposalRevision(
        proposal_id=value.proposal_id,
        revision=2,
        predecessor_digest=value.digest,
        invocation_id=uuid4().hex,
        semantics=PlanSemantics.model_validate(semantics),
    )
    with repo.transaction(scope, value.proposal_id, authorized=True) as cursor:
        repo.add_proposal(cursor, scope, successor)
    with pytest.raises(PlanningConflict, match="HEAD"):
        confirm(repo, scope, successor, "stale", expected=0)
    second = confirm(repo, scope, successor, "next", expected=1)
    assert second["plan"]["version"] == 2
    assert second["plan"]["predecessor_digest"] == results[0]["digest"]
    # New adapter reads durable history; no cached authority.
    reader = PostgresPlanningRepository(repo.pool)
    with reader.transaction(scope, value.proposal_id, authorized=True) as cursor:
        assert reader.read_plan(cursor, scope, value.proposal_id, 1) == results[0]
    foreign = ScopeIdentity("foreign", "test")
    with (
        reader.transaction(foreign, value.proposal_id, authorized=True) as cursor,
        pytest.raises(PlanningError, match="NOT_FOUND"),
    ):
        reader.read_plan(cursor, foreign, value.proposal_id, 1)


def test_confirmation_rollback(repository):
    scope = ScopeIdentity("test-323-" + uuid4().hex, "test")
    value = proposal()
    with repository.transaction(scope, value.proposal_id, authorized=True) as cursor:
        repository.add_proposal(cursor, scope, value)

    def fail():
        raise RuntimeError("injected failure before commit")

    with pytest.raises(RuntimeError, match="injected"):
        confirm(repository, scope, value, "rollback", fail=fail)
    with repository.transaction(scope, value.proposal_id, authorized=True) as cursor:
        for table in ("plans", "approvals", "commands"):
            from psycopg import sql

            count = cursor.execute(
                sql.SQL(
                    "SELECT count(*) AS n FROM workflow_planning.{} WHERE namespace=%s"
                ).format(sql.Identifier(table)),
                (scope.namespace,),
            ).fetchone()["n"]
            assert count == 0
    assert confirm(repository, scope, value, "rollback")["plan"]["version"] == 1


def test_resource_unknown_optional_and_required_gap():
    from agent_console.plan_suggestion_resources import PlanningResourceResolver

    data = sample()
    data["requirements"].extend(
        [
            {
                "requirement_id": "policy",
                "kind": "KNOWLEDGE",
                "name": "可选政策",
                "purpose": "附加背景",
                "required": False,
                "preparation": "本例不强制",
            },
            {
                "requirement_id": "unqueried",
                "kind": "SKILL",
                "name": "日期校验",
                "purpose": "校验日期",
                "required": True,
                "preparation": "核对真实版本",
                "selected": {
                    "resource_id": "skill",
                    "revision_id": "skill:1",
                    "digest": "b" * 64,
                },
            },
        ]
    )
    value = ProposalRevision(
        proposal_id=uuid4().hex,
        revision=1,
        predecessor_digest=None,
        invocation_id=uuid4().hex,
        semantics=PlanSemantics.model_validate(data),
    )
    snapshot = PlanningResourceResolver({}).resolve(None, value)
    states = {o.requirement_id: o.status for o in snapshot.observations}
    assert states == {
        "employee": "MISSING",
        "snapshot": "MISSING",
        "policy": "NOT_REQUIRED",
        "unqueried": "UNKNOWN",
    }
    assert snapshot.pending_required(value) == ("employee", "snapshot", "unqueried")
    assert (
        value.digest
        == ProposalRevision.model_validate_json(value.model_dump_json()).digest
    )


def test_real_problem_criteria_validation_and_stale_confirmation(repository):
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from agent_console.business_problem_domain import (
        BusinessProblemRevision,
        BusinessProblemState,
        CriterionType,
        SuccessCriteriaSetRevision,
        SuccessCriterionRevision,
    )
    from agent_console.business_problem_postgres import (
        PostgresBusinessProblemRepository,
    )
    from agent_console.governed_execution_authorization import GovernedPrincipal
    from agent_console.plan_suggestion_application import PlanningApplication
    from psycopg.rows import dict_row

    class ExactTestAuthority:
        def __init__(self):
            self.grants = set()

        def require(self, principal, owner, action, resource):
            if (principal.principal_id, owner, action, resource) not in self.grants:
                raise PlanningError("TEST_NOT_AUTHORIZED")

    url = os.environ["PLANNING323_TEST_DATABASE_URL"]
    migrations = Path(__file__).parents[1] / "migrations"
    problems = PostgresBusinessProblemRepository(
        url, migration_path=migrations / "0013_business_problem_authority.sql"
    )
    try:
        problems.migrate()
        identity = uuid4().hex
        scope = ScopeIdentity("323-" + identity, "test")
        now = datetime.now(UTC)
        principal = GovernedPrincipal(
            "author", scope.namespace, "test", "test-only", now + timedelta(hours=1)
        )
        problem = BusinessProblemRevision(
            scope,
            identity,
            identity + ":1",
            1,
            None,
            "采购",
            "测试采购问题",
            "author",
            "author",
            now,
        )
        problems.create_problem(
            problem, idempotency_key="create", payload_digest="a" * 64, authorized=True
        )
        criterion = SuccessCriterionRevision(
            scope,
            "criterion-" + identity,
            "criterion-" + identity + ":1",
            1,
            None,
            CriterionType.EVIDENCE_PRESENCE,
            {"minimum_count": 1},
            ("REPORT",),
            "evidence",
            "1",
            {},
            "author",
            now,
        )
        problems.add_criterion_revision(
            criterion,
            expected_version=None,
            idempotency_key="criterion",
            payload_digest="b" * 64,
            authorized=True,
        )
        criteria = SuccessCriteriaSetRevision(
            scope,
            "set-" + identity,
            identity,
            problem.revision_id,
            1,
            None,
            (criterion.revision_id,),
            "author",
            now,
        )
        problems.add_criteria_set_revision(
            criteria,
            expected_version=1,
            idempotency_key="set",
            payload_digest="c" * 64,
            authorized=True,
        )
        aggregate = problems.get_aggregate(scope, identity, authorized=True)
        # A freshly confirmed UI draft is still DRAFT, even with saved criteria.
        # Do not let an acceptance fixture silently skip the activation gate.
        assert aggregate.current_state is BusinessProblemState.DRAFT
        draft_authority = ExactTestAuthority()
        for owner, resource in (
            ("BUSINESS_PROBLEM", f"business-problem:{identity}"),
            ("SUCCESS_CRITERIA_SET", f"success-criteria-set:{identity}"),
        ):
            draft_authority.grants.add(("author", owner, "READ", resource))
        draft_app = PlanningApplication(repository, problems, draft_authority)
        with (
            repository.transaction(scope, identity, authorized=True) as cursor,
            pytest.raises(
                PlanningConflict,
                match="PLANNING_CONFIRMED_PROBLEM_AND_CRITERIA_REQUIRED",
            ),
        ):
            draft_app.current_input(principal, identity, cursor.connection)
        version = problems.transition(
            scope,
            identity,
            BusinessProblemState.ACTIVE,
            actor_id="author",
            expected_version=aggregate.aggregate_version,
            event_id=uuid4().hex,
            idempotency_key="active",
            payload_digest="d" * 64,
            authorized=True,
        )
        data = sample()
        data["requirements"].append(
            {
                **data["requirements"][0],
                "requirement_id": "data-checker",
                "name": "数据核验职责",
                "purpose": "校验输入及延期规则; 仅职责需求, 不绑定实例",
            }
        )
        for task in data["tasks"]:
            if task["task_id"] in {"T2a", "T2b"}:
                task["employee_requirement_id"] = "data-checker"
                task["responsibility"] = "数据核验职责"
        data["target"] = {
            "problem": {
                "resource_id": identity,
                "revision_id": problem.revision_id,
                "digest": problem.digest,
            },
            "criteria": {
                "resource_id": identity,
                "revision_id": criteria.set_revision_id,
                "digest": criteria.digest,
            },
            "criterion_revision_ids": [criterion.revision_id],
            "expected_problem_version": version,
        }
        for task in data["tasks"]:
            task["criterion_revision_ids"] = [criterion.revision_id]
        value = ProposalRevision(
            proposal_id=uuid4().hex,
            revision=1,
            predecessor_digest=None,
            invocation_id=uuid4().hex,
            semantics=PlanSemantics.model_validate(data),
        )
        authority = ExactTestAuthority()
        for owner, action, resource in (
            ("PLAN", "PREPARE", f"plan:v2:{value.proposal_id}"),
            ("PLAN", "APPROVE", f"plan:v2:{value.proposal_id}"),
            ("PLAN", "READ", f"plan:v2:{value.proposal_id}"),
            ("BUSINESS_PROBLEM", "READ", f"business-problem:{identity}"),
            ("SUCCESS_CRITERIA_SET", "READ", f"success-criteria-set:{identity}"),
            (
                "SUCCESS_CRITERION",
                "READ",
                f"success-criterion:revision:{criterion.revision_id}",
            ),
        ):
            authority.grants.add(("author", owner, action, resource))
        app = PlanningApplication(repository, problems, authority)
        app.save_suggestion(principal, value)
        result = app.confirm(
            principal,
            value.proposal_id,
            1,
            value.digest,
            expected_plan_version=0,
            key="confirm",
        )
        assert app.read(principal, value.proposal_id, 1) == result
        assert {
            task["employee_requirement_id"]
            for task in result["plan"]["semantics"]["tasks"]
        } == {"employee", "data-checker"}
        # A changed current Problem cannot invalidate response-loss replay or history.
        problems.transition(
            scope,
            identity,
            BusinessProblemState.IN_PROGRESS,
            actor_id="author",
            expected_version=version,
            event_id=uuid4().hex,
            idempotency_key="progress",
            payload_digest="e" * 64,
            authorized=True,
        )
        assert (
            app.confirm(
                principal,
                value.proposal_id,
                1,
                value.digest,
                expected_plan_version=0,
                key="confirm",
            )
            == result
        )
        stale = value.model_copy(update={"proposal_id": uuid4().hex})
        authority.grants.add(
            ("author", "PLAN", "PREPARE", f"plan:v2:{stale.proposal_id}")
        )
        with pytest.raises(PlanningConflict, match="STALE"):
            app.save_suggestion(principal, stale)
        authority.grants.clear()
        with pytest.raises(PlanningError, match="NOT_AUTHORIZED"):
            app.read(principal, value.proposal_id, 1)
        # Restore pool row shape expected by migration tests sharing the database.
        with repository.pool.connection() as connection:
            connection.row_factory = dict_row
    finally:
        problems.pool.close()
