# ruff: noqa: E501, F811, RUF001 -- Explicit isolated SQL fixture and Chinese boundary text.
"""D10 transactional owner checks on disposable PG; no real model/Kubernetes."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.business_problem_domain import (
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
)
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_application import PlanningApplication
from agent_console.plan_suggestion_domain import (
    ExactReference,
    PlanningConflict,
    PlanningError,
    ProblemTarget,
    ProposalRevision,
)
from agent_console.planning_candidates import discover, read_published
from agent_console.planning_source_change import (
    SourceChangeRequest,
    prepare,
    preview,
    read,
    validate_confirmation,
)
from agent_console.resource_use_domain import canonical_digest
from agent_console.sales_resource_bundle import source_document
from prepared_execution_support import seed
from psycopg.types.json import Jsonb
from test_execution_preparation import preparation
from test_plan_suggestion_v2 import repository  # noqa: F401


class Authority:
    denied = None

    def require(self, principal, owner, action, resource):
        if self.denied and (owner == self.denied or resource == self.denied):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return SimpleNamespace(decision_id="explicit-isolated-test-authority")


@pytest.fixture
def case(repository):
    root = Path(__file__).parents[3]
    source = source_document(
        (root / "examples/sales-diagnostic/synthetic-sales.csv").read_bytes()
    )
    scope = ScopeIdentity("controlled-324", "isolated")
    problems = PostgresBusinessProblemRepository(
        repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0013_business_problem_authority.sql",
    )
    problems.migrate()
    now = datetime.now(UTC)
    base = preparation().semantics.target
    problem = BusinessProblemRevision(
        scope,
        base.problem.resource_id,
        base.problem.revision_id,
        1,
        None,
        "销售诊断",
        "合成数据，无真实经营结论",
        "human:test",
        "human:test",
        now,
    )
    problems.create_problem(
        problem,
        idempotency_key="create",
        payload_digest=problem.digest,
        authorized=True,
    )
    for i, identity in enumerate(base.criterion_revision_ids):
        criterion = SuccessCriterionRevision(
            scope,
            "criterion:" + str(i),
            identity,
            1,
            None,
            CriterionType.DETERMINISTIC_BOOLEAN,
            {"expected": True},
            ("NATIVE_EXECUTION_ARTIFACT", "PUBLISHED_SYNTHETIC_SOURCE"),
            "SYNTHETIC_SALES",
            "1",
            {"check": "source", "sourceContentDigest": canonical_digest(source)},
            "human:test",
            now,
        )
        problems.add_criterion_revision(
            criterion,
            expected_version=None,
            idempotency_key="criterion:" + str(i),
            payload_digest=criterion.digest,
            authorized=True,
        )
    criteria = SuccessCriteriaSetRevision(
        scope,
        base.criteria.revision_id,
        problem.business_problem_id,
        problem.revision_id,
        1,
        None,
        base.criterion_revision_ids,
        "human:test",
        now,
    )
    problems.add_criteria_set_revision(
        criteria,
        expected_version=1,
        idempotency_key="set",
        payload_digest=criteria.digest,
        authorized=True,
    )
    problems.transition(
        scope,
        problem.business_problem_id,
        BusinessProblemState.ACTIVE,
        actor_id="human:test",
        expected_version=2,
        event_id="activate",
        idempotency_key="activate",
        payload_digest="b" * 64,
        authorized=True,
    )
    target = ProblemTarget(
        problem=ExactReference(
            resource_id=problem.business_problem_id,
            revision_id=problem.revision_id,
            digest=problem.digest,
        ),
        criteria=ExactReference(
            resource_id=problem.business_problem_id,
            revision_id=criteria.set_revision_id,
            digest=criteria.digest,
        ),
        criterion_revision_ids=base.criterion_revision_ids,
        expected_problem_version=3,
    )
    p = seed(repository, synthetic_skill="sales", target=target, source_boundary=True)
    with repository.pool.connection() as c:
        row = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
            (scope.namespace, scope.security_domain, p.source_snapshot.resource_id),
        ).fetchone()
        record = copy.deepcopy(row["record"])
        record["knowledgeId"] = "replacement"
        record["name"] = "可读替代来源"
        c.execute(
            "INSERT INTO knowledge_operation.knowledge VALUES(%s,%s,'replacement',1,%s)",
            (scope.namespace, scope.security_domain, Jsonb(record)),
        )
    principal = SimpleNamespace(
        principal_id="human:test",
        tenant_id=scope.namespace,
        security_domain=scope.security_domain,
    )
    authority = Authority()
    app = PlanningApplication(repository, problems, authority)
    request = SourceChangeRequest(
        plan_version=p.plan_version,
        plan_digest=p.plan_digest,
        expected_proposal_revision=p.plan_version,
        old_source=p.source_snapshot,
        new_source=p.source_snapshot.model_copy(update={"resource_id": "replacement"}),
        reason="用已发布的同内容文件来源替代；原结果保留",
        idempotency_key="source-change",
    )
    try:
        yield SimpleNamespace(
            p=p,
            app=app,
            request=request,
            scope=scope,
            principal=principal,
            authority=authority,
            source=source,
        )
    finally:
        problems.pool.close()


def test_discovery_is_scoped_authorized_exact_and_read_only(repository, case):
    e = case
    req = SimpleNamespace(
        kind="EMPLOYEE",
        requirement_id=e.p.semantics.requirements[0].requirement_id,
        selected=e.p.participants[0].definition,
    )
    with repository.pool.connection() as c:
        result = discover(
            c,
            e.scope,
            e.authority,
            e.principal,
            ProposalRevision(
                proposal_id="view",
                revision=1,
                predecessor_digest=None,
                invocation_id="fixture",
                semantics=e.p.semantics,
            ),
            req,
        )
        assert (
            len(result["candidates"]) == 1
            and result["candidates"][0]["assessment"]["status"]
            == "DECLARED_OPERATIONS_MATCH"
        )
        assert result["executionReady"] is False
        e.authority.denied = "EMPLOYEE"
        assert (
            discover(
                c,
                e.scope,
                e.authority,
                e.principal,
                SimpleNamespace(semantics=e.p.semantics),
                req,
            )["candidates"]
            == []
        )
        e.authority.denied = None
        foreign = ScopeIdentity("foreign", "isolated")
        assert (
            discover(
                c,
                foreign,
                e.authority,
                e.principal,
                SimpleNamespace(semantics=e.p.semantics),
                req,
            )["candidates"]
            == []
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.source_changes"
            ).fetchone()["n"]
            == 0
        )


def test_prepare_replay_confirm_refresh_and_original_approval_are_separate(
    repository, case
):
    e = case
    with repository.pool.connection() as c:
        _, info = preview(e.app, e.principal, c, e.p.plan_id, e.request)
        assert (
            info["state"] == "READY_FOR_SEPARATE_CONFIRMATION"
            and not info["contentChanged"]
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: prepare(e.app, e.principal, e.p.plan_id, e.request), range(2)
            )
        )
    assert results[0] == results[1]
    r = results[0]
    assert (
        r["proposal"]["invocation_id"] is None
        and r["proposal"]["origin"]["kind"] == "HUMAN_SOURCE_CHANGE"
    )
    original = e.p.semantics.model_dump_json()
    result = e.app.confirm(
        e.principal,
        e.p.plan_id,
        r["proposal"]["revision"],
        r["digest"],
        expected_plan_version=e.p.plan_version,
        key="confirm-source-change",
    )
    assert result["plan"]["version"] == e.p.plan_version + 1
    assert (
        e.app.confirm(
            e.principal,
            e.p.plan_id,
            r["proposal"]["revision"],
            r["digest"],
            expected_plan_version=e.p.plan_version,
            key="confirm-source-change",
        )
        == result
    )
    with repository.pool.connection() as c:
        assert read(e.app, e.principal, c, e.p.plan_id, r["requestId"]) == r
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.source_changes"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
    assert e.p.semantics.model_dump_json() == original
    assert "origin" not in ProposalRevision(
        proposal_id="legacy",
        revision=1,
        predecessor_digest=None,
        invocation_id="legacy",
        semantics=e.p.semantics,
    ).model_dump(mode="json")
    from agent_console.cost_execution_revision import (
        CostExecutionRevisionRequest,
        execution_successor,
    )
    from agent_console.plan_suggestion_domain import ConfirmedPlanRevision

    successor = ProposalRevision.model_validate(r["proposal"])
    plan = ConfirmedPlanRevision.model_validate(result["plan"])
    execution_request = CostExecutionRevisionRequest(
        case="sales",
        plan_version=plan.version,
        plan_digest=plan.digest,
        source_snapshot=e.request.new_source,
        mapping_digest="c" * 64,
        selections={
            x.requirement_id: x.selected
            for x in plan.semantics.requirements
            if x.required
        },
    )
    executable, _ = execution_successor(plan, successor, execution_request)
    assert (
        len(
            [
                s
                for s in executable.semantics.boundaries
                if s.startswith("隔离合成来源：")
            ]
        )
        == 1
    )
    with pytest.raises(PlanningConflict, match="SOURCE_CHANGE_MISMATCH"):
        execution_successor(
            plan,
            successor,
            execution_request.model_copy(
                update={"source_snapshot": e.request.old_source}
            ),
        )


def change_source(c, e, change):
    row = c.execute(
        "SELECT record FROM knowledge_operation.knowledge WHERE knowledge_id='replacement'"
    ).fetchone()
    record = row["record"]
    if change == "unpublished":
        record["publishedRevisionId"] = None
    elif change == "disabled":
        record["enabled"] = False
    elif change == "corrupt":
        record["revisions"][0]["content"]["documents"][0]["chunks"][0]["content"] += " "
    else:
        document = record["revisions"][0]["content"]["documents"][0]
        source = json.loads(document["chunks"][0]["content"])
        if change == "schema":
            source["schemaVersion"] = "synthetic-delivery-source.v1"
        elif change == "scope":
            source["periods"] = ["2026-08", "2026-10"]
        else:
            raw = (
                (
                    Path(__file__).parents[3]
                    / "examples/sales-diagnostic/synthetic-sales.csv"
                )
                .read_bytes()
                .replace(b"600,360", b"601,360")
            )
            source = source_document(raw)
        text = json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        import hashlib

        document["chunks"][0]["content"] = text
        document["contentDigest"] = hashlib.sha256(text.encode()).hexdigest()
    # Initial disposable owner fixture variants, never production mutations.
    c.execute(
        "UPDATE knowledge_operation.knowledge SET record=%s WHERE knowledge_id='replacement'",
        (Jsonb(record),),
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("unpublished", "VERSION_UNAVAILABLE"),
        ("disabled", "VERSION_UNAVAILABLE"),
        ("corrupt", "DOCUMENT_CORRUPT"),
        ("schema", "SCHEMA_INCOMPATIBLE"),
        ("scope", "SOURCE_INVALID"),
    ],
)
def test_invalid_sources_and_scopes_fail_before_successor(
    repository, case, change, reason
):
    e = case
    with repository.pool.connection() as c:
        change_source(c, e, change)
    with pytest.raises((PlanningError, PlanningConflict), match=reason):
        prepare(e.app, e.principal, e.p.plan_id, e.request)
    with repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.source_changes"
            ).fetchone()["n"]
            == 0
        )


def test_changed_content_is_persisted_as_blocked_not_confirmable(repository, case):
    e = case
    with repository.pool.connection() as c:
        change_source(c, e, "content")
    r = prepare(e.app, e.principal, e.p.plan_id, e.request)
    assert r["proposal"] is None and not r["confirmationRequired"]
    assert r["evidence"]["state"] == "BLOCKED_CRITERIA"
    assert r["evidence"]["criterionImpacts"]
    with repository.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM workflow_planning.proposals").fetchone()[
                "n"
            ]
            == 1
        )


def test_denial_stale_keys_and_revocation_do_not_replace_approved_source(
    repository, case
):
    e = case
    e.authority.denied = "KNOWLEDGE"
    with pytest.raises(AuthorityError):
        prepare(e.app, e.principal, e.p.plan_id, e.request)
    e.authority.denied = None
    with pytest.raises(PlanningConflict, match="HEAD_CHANGED"):
        prepare(
            e.app,
            e.principal,
            e.p.plan_id,
            e.request.model_copy(update={"expected_proposal_revision": 999}),
        )
    r = prepare(e.app, e.principal, e.p.plan_id, e.request)
    with pytest.raises(PlanningConflict, match="IDEMPOTENCY"):
        prepare(
            e.app,
            e.principal,
            e.p.plan_id,
            e.request.model_copy(update={"reason": "different"}),
        )
    e.authority.denied = "KNOWLEDGE"
    with pytest.raises(AuthorityError), repository.pool.connection() as c:
        validate_confirmation(
            e.app, e.principal, c, ProposalRevision.model_validate(r["proposal"])
        )


def test_changed_content_needs_existing_owner_criterion_successors_and_explicit_target(
    repository, case
):
    from dataclasses import replace

    e = case
    with repository.pool.connection() as c:
        change_source(c, e, "content")
        new_data, _ = read_published(c, e.scope, "KNOWLEDGE", e.request.new_source)
        source = json.loads(new_data["documents"][0]["chunks"][0]["content"])
    new_ids = []
    mapping = {}
    for identity in e.p.semantics.target.criterion_revision_ids:
        old = e.app.problems.get_criterion_revision(e.scope, identity, authorized=True)
        new = replace(
            old,
            revision_id=identity + ":2",
            revision=2,
            predecessor_revision_id=identity,
            applicability={
                **old.applicability,
                "sourceContentDigest": canonical_digest(source),
            },
            digest="",
        )
        e.app.problems.add_criterion_revision(
            new,
            expected_version=1,
            idempotency_key="revise:" + identity,
            payload_digest=new.digest,
            authorized=True,
        )
        new_ids.append(new.revision_id)
        mapping[identity] = new.revision_id
    target = e.p.semantics.target
    new_set = SuccessCriteriaSetRevision(
        e.scope,
        "set:changed-content",
        target.problem.resource_id,
        target.problem.revision_id,
        2,
        target.criteria.revision_id,
        tuple(new_ids),
        "human:test",
        datetime.now(UTC),
    )
    e.app.problems.add_criteria_set_revision(
        new_set,
        expected_version=3,
        idempotency_key="new-set",
        payload_digest=new_set.digest,
        authorized=True,
    )
    current = target.model_copy(
        update={
            "criteria": ExactReference(
                resource_id=target.problem.resource_id,
                revision_id=new_set.set_revision_id,
                digest=new_set.digest,
            ),
            "criterion_revision_ids": tuple(new_ids),
            "expected_problem_version": 4,
        }
    )
    request = e.request.model_copy(
        update={"new_target": current, "criterion_revision_map": mapping}
    )
    result = prepare(e.app, e.principal, e.p.plan_id, request)
    assert (
        result["evidence"]["contentChanged"]
        and result["evidence"]["state"] == "READY_FOR_SEPARATE_CONFIRMATION"
    )
    approved = e.app.confirm(
        e.principal,
        e.p.plan_id,
        result["proposal"]["revision"],
        result["digest"],
        expected_plan_version=e.p.plan_version,
        key="approve-new-criteria-source",
    )
    assert (
        approved["plan"]["semantics"]["target"]["criteria"]["revision_id"]
        == new_set.set_revision_id
    )
    assert tuple(
        approved["plan"]["semantics"]["tasks"][-1]["criterion_revision_ids"]
    ) == tuple(new_ids)
    assert e.app.problems.get_criterion_revision(
        e.scope, target.criterion_revision_ids[0], authorized=True
    ).applicability["sourceContentDigest"] == canonical_digest(e.source)


def test_historical_old_source_can_be_replaced_but_never_selected_for_new_execution(
    repository, case
):
    e = case
    with repository.pool.connection() as c:
        row = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE knowledge_id='controlled'"
        ).fetchone()
        record = row["record"]
        record["enabled"] = False
        record["publishedRevisionId"] = None
        c.execute(
            "UPDATE knowledge_operation.knowledge SET record=%s WHERE knowledge_id='controlled'",
            (Jsonb(record),),
        )
    result = prepare(e.app, e.principal, e.p.plan_id, e.request)
    assert result["evidence"]["state"] == "READY_FOR_SEPARATE_CONFIRMATION"
    with repository.pool.connection() as c:
        with pytest.raises(PlanningError, match="VERSION_UNAVAILABLE"):
            read_published(c, e.scope, "KNOWLEDGE", e.p.source_snapshot)
        assert read_published(
            c, e.scope, "KNOWLEDGE", e.p.source_snapshot, historical=True
        )
        assert read(e.app, e.principal, c, e.p.plan_id, result["requestId"]) == result


@pytest.mark.parametrize(
    "kind,owner,action,prefix",
    [
        ("EMPLOYEE", "EMPLOYEE", "READ", "employee:"),
        ("SKILL", "SKILL", "READ_RESOURCE", "skill-invocation:prepared-resource:"),
        ("KNOWLEDGE", "KNOWLEDGE", "READ_RESOURCE", "knowledge:prepared-resource:"),
        ("AGENT", "AGENT", "READ_RESOURCE", "agent:prepared-resource:"),
        (
            "RUNTIME",
            "RUNTIME_PROFILE",
            "READ_RESOURCE",
            "runtime-profile:prepared-resource:",
        ),
        ("WORKFLOW", "WORKFLOW", "READ", "workflow:"),
    ],
)
def test_each_discovery_owner_keeps_its_registered_exact_read_action(
    kind, owner, action, prefix
):
    from agent_console.planning_candidates import require_read

    calls = []
    authority = SimpleNamespace(
        require=lambda principal, o, a, r: calls.append((o, a, r))
    )
    require_read(
        authority,
        SimpleNamespace(),
        kind,
        ExactReference(resource_id="exact", revision_id="1", digest="a" * 64),
    )
    assert calls == [(owner, action, prefix + "exact:1")]


def test_current_criteria_selector_reads_existing_owner_without_writes(
    repository, case
):
    from agent_console.planning_source_change import current_target

    e = case
    with repository.pool.connection() as c:
        value = current_target(e.app, e.principal, c, e.p.plan_id, e.p.plan_version)
        assert value["target"] == e.p.semantics.target.model_dump(mode="json")
        assert value["criterionRevisionMap"] == {
            i: i for i in e.p.semantics.target.criterion_revision_ids
        }
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.source_changes"
            ).fetchone()["n"]
            == 0
        )
        e.authority.denied = "SUCCESS_CRITERION"
        with pytest.raises(AuthorityError):
            current_target(e.app, e.principal, c, e.p.plan_id, e.p.plan_version)


def test_source_change_records_cannot_be_updated_or_deleted(repository, case):
    import psycopg

    e = case
    r = prepare(e.app, e.principal, e.p.plan_id, e.request)
    with repository.pool.connection() as c:
        for sql in (
            "UPDATE workflow_planning.source_changes SET record=record",
            "DELETE FROM workflow_planning.source_changes",
        ):
            with (
                pytest.raises(psycopg.Error, match="PLANNING_IMMUTABLE"),
                c.transaction(),
            ):
                c.execute(sql)
        assert read(e.app, e.principal, c, e.p.plan_id, r["requestId"]) == r


def test_knowledge_source_family_is_read_authorized_metadata_without_document_body(
    repository, case
):
    e = case
    requirement = SimpleNamespace(
        kind="KNOWLEDGE",
        requirement_id="source-family-check",
        selected=e.p.source_snapshot,
    )
    with repository.pool.connection() as c:
        result = discover(
            c,
            e.scope,
            e.authority,
            e.principal,
            SimpleNamespace(semantics=e.p.semantics),
            requirement,
        )
        assert result["candidates"]
        assert all(
            row["assessment"]["sourceSchemas"] == ["sales-diagnostic-source.v1"]
            for row in result["candidates"]
        )
        assert all(
            isinstance(d["chunks"], int) and "content" not in d
            for row in result["candidates"]
            for d in row["assessment"]["configuration"]["documents"]
        )
        e.authority.denied = "KNOWLEDGE"
        assert (
            discover(
                c,
                e.scope,
                e.authority,
                e.principal,
                SimpleNamespace(semantics=e.p.semantics),
                requirement,
            )["candidates"]
            == []
        )
