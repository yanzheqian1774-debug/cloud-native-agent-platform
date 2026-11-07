# ruff: noqa: F401,F811 -- Existing explicit UUID PostgreSQL fixtures.
"""Same-owner SQL and BFF checks; fixture authorities are never real acceptance."""

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from threading import Barrier
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.business_problem_domain import (
    CriterionType,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    FlexiblePlanSemantics,
    ProposalRevision,
)
from agent_console.planning_sales_supplement import (
    TASK_CHECKS,
    PlanningSalesSupplementOwner,
    SalesSupplementRequest,
)
from agent_console.prepared_skill_successor import PreparedSkillSuccessorOwner
from agent_console.prepared_skill_successor import grants as skill_grants
from agent_console.resource_management import ResourceManagement, target
from agent_console.resource_use_domain import canonical_digest
from agent_console.sales_gross_profit_candidate import revision_candidate
from agent_console.sales_gross_profit_evaluation import CHECKS, criterion_candidate
from agent_console.sales_gross_profit_integration import SOURCE_DIGEST, bounded_content
from agent_console.sales_supplement_composition import operations
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_prepared_resources import PreparedResourceOwner, reference
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import confirm, repository
from test_plan_suggestion_v2 import proposal as legacy_proposal
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_workbench_bff import SessionStub


class ExactFixtureAuthority:
    def __init__(self, actor, allowed=()):
        self.actor, self.allowed = actor, set(allowed)

    def require(self, principal, owner, action, resource):
        if (
            principal.principal_id != self.actor
            or (owner, action, resource) not in self.allowed
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return SimpleNamespace(decision_id="explicit-isolated-exact-grant-fixture")


def owner_call(a, handler, operation, payload, path, acl, context=None):
    with a.repository.pool.connection() as c, c.transaction():
        return handler(
            SimpleNamespace(
                context=context or a.subject,
                connection=c,
                operation=operation,
                payload=payload,
                path=path,
                query={},
                authority=acl,
            )
        )


class ExactFixtureBffAuthorizer:
    def __init__(self, a, acl):
        self.a, self.acl = a, acl

    def execute(self, context, grants, **values):
        for g in grants:
            self.acl.require(context, g.owner, g.action, g.exact_resource)
        return owner_call(
            self.a,
            values["handler"],
            values["operation"],
            values["payload"],
            values["path"],
            self.acl,
            context,
        )


def client(a, acl):
    sessions = SessionStub(a.subject.principal_id)
    sessions.context = a.subject
    app = create_workbench_bff(
        sessions,
        ExactFixtureBffAuthorizer(a, acl),
        WorkbenchBffPolicy("review.test", "https://review.test"),
        operations=operations(
            a.e.app, a.services, enabled=True, sales_v2_candidate=True
        ),
    )
    c = TestClient(app, base_url="https://review.test")
    c.cookies.set("__Host-workbench_session", sessions.secret)
    return c


def skill_request(a):
    ref = a.refs["skill"]
    service = a.services["skill"]
    rs = service.scope(a.subject.scope.tenant_id, a.subject.scope.security_domain)
    old = service.repository.get(rs, "skill", ref.resource_id)
    content = bounded_content(
        revision_candidate(
            ref.model_dump(mode="json"),
            old["revisions"][0]["content"],
            old["aggregateVersion"],
            a.refs["knowledge"].model_dump(mode="json"),
            SOURCE_DIGEST,
        )["candidateContent"]
    )
    body = {
        "expectedVersion": old["aggregateVersion"],
        "expectedPublishedDigest": ref.digest,
        "content": content,
        "reason": "Explicit isolated supplement draft only",
        "commandKey": "isolated-successor-key",
    }
    path = {"identity": ref.resource_id, "revision": ref.revision_id}
    acl = ExactFixtureAuthority(
        a.subject.principal_id,
        [
            (g.owner, g.action, g.exact_resource)
            for g in skill_grants(a.subject, path, body, {})
        ],
    )
    return SimpleNamespace(
        body=body,
        path=path,
        acl=acl,
        handler=PreparedSkillSuccessorOwner(service),
        old=deepcopy(old),
    )


def snapshot(a):
    with a.repository.pool.connection() as c:
        tables = [
            "workflow_planning.plans",
            "workflow_planning.proposals",
            "execution_authority.workflow_runs",
            "authorization_admin.grants",
        ]
        return {
            t: [
                r["h"]
                for r in c.execute(
                    "SELECT md5(row_to_json(t)::text) h FROM " + t + " t ORDER BY h"
                )
            ]
            for t in tables
        }


def test_prepared_skill_successor_bff_original_key_current_acl_and_history(
    automation, record_property
):
    a = automation
    s = skill_request(a)
    before = snapshot(a)
    with client(a, s.acl) as c:
        url = (
            "/api/workbench/v1/prepared-resources/skill/"
            + s.path["identity"]
            + "/revisions/"
            + s.path["revision"]
            + "/successors"
        )
        response = c.post(
            url,
            json=s.body,
            headers={"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"},
        )
        assert response.status_code == 200, response.text
        receipt = response.json()["result"]
        record_property("skill_successor_receipt_json", json.dumps(receipt))
        assert (
            receipt["state"] == "DRAFT"
            and not receipt["published"]
            and not receipt["executionStarted"]
        )
        assert receipt["draft"]["digest"] != receipt["contentDigest"]
        assert (
            c.post(
                url,
                json=s.body,
                headers={"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"},
            ).json()["result"]
            == receipt
        )
        assert (
            c.get(url + "/by-key/" + s.body["commandKey"]).json()["result"] == receipt
        )
        assert (
            c.post(
                url,
                json={**s.body, "reason": "different payload"},
                headers={"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"},
            ).status_code
            == 409
        )
        s.acl.allowed.remove(
            ("SKILL", "MANAGE_RESOURCE", target("skill", s.path["identity"]))
        )
        assert c.get(url + "/by-key/" + s.body["commandKey"]).status_code == 404
    record = a.services["skill"].repository.get(
        a.services["skill"].scope(a.e.scope.namespace, a.e.scope.security_domain),
        "skill",
        s.path["identity"],
    )
    assert record["revisions"][: len(s.old["revisions"])] == s.old["revisions"]
    assert record["publishedRevisionId"] == s.path["revision"]
    assert len(record["revisions"]) == len(s.old["revisions"]) + 2
    assert snapshot(a) == before
    with a.repository.pool.connection() as connection:
        call = SimpleNamespace(context=a.subject, connection=connection)
        assert not ResourceManagement(None, None, None).owned(
            call, "skill", s.path["identity"]
        )


@pytest.mark.parametrize(
    "bad",
    [
        "version",
        "digest",
        "foreign",
        "service",
        "missing-read",
        "draft",
        "blank-reason",
    ],
)
def test_prepared_skill_successor_rejects_before_mutation(automation, bad):
    a = automation
    s = skill_request(a)
    context = a.subject
    if bad == "version":
        s.body["expectedVersion"] += 1
    if bad == "digest":
        s.body["expectedPublishedDigest"] = "0" * 64
    if bad == "foreign":
        context = replace(context, principal_id="human:foreign")
    if bad == "service":
        context = replace(context, principal_id="service:policy")
    if bad == "missing-read":
        s.acl.allowed.remove(
            (
                "SKILL",
                "READ_RESOURCE",
                reference("skill", s.path["identity"], s.path["revision"]),
            )
        )
    if bad == "blank-reason":
        s.body["reason"] = " "
    service = a.services["skill"]
    rs = service.scope(a.e.scope.namespace, a.e.scope.security_domain)
    if bad == "draft":
        service.successor(
            rs,
            "skill",
            s.path["identity"],
            "human:fixture-setup",
            s.old["aggregateVersion"],
        )
    before = service.repository.get(rs, "skill", s.path["identity"])
    with pytest.raises((WorkbenchOwnerError, AuthorityError)):
        owner_call(
            a,
            s.handler,
            "PREPARE_PREPARED_SKILL_SUCCESSOR",
            s.body,
            s.path,
            s.acl,
            context,
        )
    assert service.repository.get(rs, "skill", s.path["identity"]) == before


def prepare_supplement_fixture(a, *, changed_role=False, bad_contract=False):
    old_employee = next(
        r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    )
    semantics = a.e.p.semantics.model_dump(mode="json")
    source = a.refs["knowledge"]
    skill = a.refs["skill"]
    template = semantics["requirements"][0]
    semantics["requirements"] = [
        {
            **template,
            "requirement_id": kind.lower(),
            "kind": kind,
            "selected": ref.model_dump(mode="json"),
        }
        for kind, ref in [
            ("EMPLOYEE", old_employee),
            ("KNOWLEDGE", source),
            ("SKILL", skill),
        ]
    ]
    kinds = {
        "read": ("READ_DATA", [], ["CONTEXT"], "SOURCE_SNAPSHOT"),
        "validate": ("VALIDATE_DATA", ["read"], ["SOURCE_SNAPSHOT"], "VALIDATED_DATA"),
        "summarize": ("SUMMARIZE", ["validate"], ["VALIDATED_DATA"], "SUMMARY"),
        "analyze": (
            "ANALYZE_DATA",
            ["validate", "summarize"],
            ["VALIDATED_DATA", "SUMMARY"],
            "ANALYSIS",
        ),
        "report": (
            "RENDER_REPORT",
            ["analyze", "summarize", "validate"],
            ["ANALYSIS", "SUMMARY", "VALIDATED_DATA"],
            "REPORT",
        ),
    }
    semantics["tasks"] = [
        {
            "task_id": k,
            "title": k,
            "responsibility": "Explicit synthetic fixture only",
            "employee_requirement_id": "employee",
            "depends_on": deps,
            "inputs": ["fixture input"],
            "outputs": ["fixture output"],
            "requirement_ids": ["employee", "knowledge", "skill"],
            "criterion_revision_ids": list(
                semantics["target"]["criterion_revision_ids"]
            ),
            "operation": op,
            "input_kinds": inputs,
            "output_kind": out,
        }
        for k, (op, deps, inputs, out) in kinds.items()
    ]
    semantics["stages"] = [
        {"stage_id": "all", "title": "saved synthetic plan", "task_ids": list(kinds)}
    ]
    with a.repository.transaction(a.e.scope, a.e.p.plan_id, authorized=True) as cursor:
        old_proposal = a.repository.proposal(
            cursor, a.e.scope, a.e.p.plan_id, a.e.p.plan_version
        )
        proposal = ProposalRevision(
            proposal_id=a.e.p.plan_id,
            revision=old_proposal.revision + 1,
            predecessor_digest=old_proposal.digest,
            invocation_id="explicit-fixture-saved-proposal-no-provider",
            semantics=FlexiblePlanSemantics.model_validate(semantics),
        )
        a.repository.add_proposal(cursor, a.e.scope, proposal)
    confirmed = confirm(
        a.repository,
        a.e.scope,
        proposal,
        "fixture-original-five-step",
        expected=a.e.p.plan_version,
    )
    old = ConfirmedPlanRevision.model_validate(confirmed["plan"])
    s = skill_request(a)
    if bad_contract:
        s.body["content"]["operations"][0]["ioLimits"]["maxInputBytes"] *= 2
    saved = owner_call(
        a, s.handler, "PREPARE_PREPARED_SKILL_SUCCESSOR", s.body, s.path, s.acl
    )
    # Explicit disposable owner setup, never a real publication or business Run.
    all_fixture = SimpleNamespace(
        require=lambda *_: SimpleNamespace(decision_id="explicit-isolated-setup")
    )
    owner_call(
        a,
        PreparedResourceOwner(a.services),
        "REVIEW_PREPARED_RESOURCE",
        {
            "expectedVersion": saved["aggregateVersion"],
            "digest": saved["draft"]["digest"],
            "reason": "isolated new-revision setup only",
            "idempotencyKey": "fixture-new-skill-publish",
        },
        {
            "kind": "skill",
            "identity": skill.resource_id,
            "revision": saved["draft"]["revision_id"],
        },
        all_fixture,
    )
    new_skill = ExactReference.model_validate(saved["draft"])
    employee_repo = PostgresEmployeeDefinitionRepository(a.repository)
    with a.repository.pool.connection() as c, c.transaction():
        before = employee_repo._read(
            c, a.e.scope, old_employee.resource_id, old_employee.revision_id
        )["revision"]
        members = tuple(
            CompositionMember(
                MemberKind(m["kind"]),
                new_skill.resource_id if m["kind"] == "SKILL" else m["resource_id"],
                new_skill.revision_id if m["kind"] == "SKILL" else m["revision_id"],
                new_skill.digest if m["kind"] == "SKILL" else m["digest"],
            )
            for m in before["members"]
        )
        revision = EmployeeRevision(
            a.e.scope,
            old_employee.resource_id,
            "employee-revision:explicit-supplement",
            before["role"] + (" changed" if changed_role else ""),
            tuple(before["responsibilities"]),
            members,
            old_employee.revision_id,
        )
        value = employee_repo.create_for_workbench(
            c,
            revision,
            expected_version=4,
            decision_id="fixture-setup",
            command_id="fixture-new-employee",
            authorized=True,
        )
        for action in ["VALIDATE", "APPROVE", "PUBLISH"]:
            value = employee_repo.decide_for_workbench(
                c,
                a.e.scope,
                revision.definition_id,
                revision.revision_id,
                revision.digest,
                action,
                expected_version=value["aggregateVersion"],
                decision_id="fixture-setup",
                command_id="fixture-supplement-employee-" + action,
                authorized=True,
            )
    new_employee = ExactReference(
        resource_id=revision.definition_id,
        revision_id=revision.revision_id,
        digest=revision.digest,
    )
    criteria = []
    for check in CHECKS:
        definition = criterion_candidate(check)
        r = SuccessCriterionRevision(
            a.e.scope,
            "criterion:supplement:" + check,
            "criterion-revision:supplement:" + check,
            1,
            None,
            CriterionType.DETERMINISTIC_BOOLEAN,
            definition["measurement"],
            tuple(definition["required_evidence_kinds"]),
            definition["evaluator_type"],
            definition["evaluator_version"],
            definition["applicability"],
            "human:test",
            datetime.now(UTC),
        )
        a.e.app.problems.add_criterion_revision(
            r,
            expected_version=None,
            idempotency_key="fixture-" + check,
            payload_digest=r.digest,
            authorized=True,
        )
        criteria.append(r.revision_id)
    previous = a.e.app.problems.list_criteria_set_revisions(
        a.e.scope, old.semantics.target.problem.resource_id, authorized=True
    )[-1]
    criterion_set = SuccessCriteriaSetRevision(
        a.e.scope,
        "criteria-set:explicit-supplement",
        old.semantics.target.problem.resource_id,
        old.semantics.target.problem.revision_id,
        previous.revision + 1,
        previous.set_revision_id,
        tuple(criteria),
        "human:test",
        datetime.now(UTC),
    )
    a.e.app.problems.add_criteria_set_revision(
        criterion_set,
        expected_version=3,
        idempotency_key="fixture-new-set",
        payload_digest=criterion_set.digest,
        authorized=True,
    )
    target = old.semantics.target.model_copy(
        update={
            "criteria": ExactReference(
                resource_id=criterion_set.business_problem_id,
                revision_id=criterion_set.set_revision_id,
                digest=criterion_set.digest,
            ),
            "criterion_revision_ids": tuple(criteria),
            "expected_problem_version": 4,
        }
    )
    spec = SalesSupplementRequest(
        plan_version=old.version,
        plan_digest=old.digest,
        expected_proposal_revision=proposal.revision,
        source_snapshot=source,
        new_target=target,
        employee=new_employee,
        skill=new_skill,
        reason="Same fixed goal and source; explicit v2 criterion/resource receipts",
        idempotency_key="fixture-sales-supplement-key",
    )
    allowed = (
        {("PLAN", x, "plan:v2:" + old.plan_id) for x in ["READ", "PREPARE", "APPROVE"]}
        | {
            (
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:" + target.problem.resource_id,
            ),
            (
                "SUCCESS_CRITERIA_SET",
                "READ",
                "success-criteria-set:" + target.problem.resource_id,
            ),
        }
        | {
            ("SUCCESS_CRITERION", "READ", "success-criterion:revision:" + x)
            for x in [*old.semantics.target.criterion_revision_ids, *criteria]
        }
    )
    allowed |= {
        ("EMPLOYEE", "READ", "employee:" + r.resource_id + ":" + r.revision_id)
        for r in [old_employee, new_employee]
    }
    allowed |= {
        ("SKILL", "READ_RESOURCE", reference("skill", r.resource_id, r.revision_id))
        for r in [skill, new_skill]
    }
    allowed.add(
        (
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source.resource_id, source.revision_id),
        )
    )
    return SimpleNamespace(
        old=old,
        spec=spec,
        acl=ExactFixtureAuthority(a.subject.principal_id, allowed),
        handler=PlanningSalesSupplementOwner(a.e.app),
        path={"proposal_id": old.plan_id},
    )


def test_same_case_supplement_real_receipt_confirmation_and_old_hashes(
    automation, record_property
):
    a = automation
    s = prepare_supplement_fixture(a)
    before = snapshot(a)
    result = owner_call(
        a,
        s.handler,
        "PREPARE_SALES_SUPPLEMENT",
        s.spec.model_dump(mode="json"),
        s.path,
        s.acl,
    )
    record_property("sales_supplement_receipt_json", json.dumps(result))
    assert (
        result["modelCalls"] == 0
        and not result["executionStarted"]
        and result["confirmation_required"]
    )
    assert result["proposal"]["invocation_id"] is None
    assert result["proposal"]["origin"]["kind"] == "HUMAN_RESOURCE_SUPPLEMENT"
    assert (
        result["proposal"]["semantics"]["business_rules"]
        == s.old.semantics.model_dump(mode="json")["business_rules"]
    )
    assert (
        owner_call(
            a,
            s.handler,
            "READ_SALES_SUPPLEMENT",
            {},
            s.path | {"request_key": s.spec.idempotency_key},
            s.acl,
        )
        == result
    )
    assert (
        owner_call(
            a,
            s.handler,
            "PREPARE_SALES_SUPPLEMENT",
            s.spec.model_dump(mode="json"),
            s.path,
            s.acl,
        )
        == result
    )
    after = snapshot(a)
    assert after["workflow_planning.plans"] == before["workflow_planning.plans"]
    assert set(before["workflow_planning.proposals"]) < set(
        after["workflow_planning.proposals"]
    )
    assert after["authorization_admin.grants"] == before["authorization_admin.grants"]
    assert (
        after["execution_authority.workflow_runs"]
        == before["execution_authority.workflow_runs"]
    )
    new_read = (
        "SKILL",
        "READ_RESOURCE",
        reference("skill", s.spec.skill.resource_id, s.spec.skill.revision_id),
    )
    s.acl.allowed.remove(new_read)
    with pytest.raises(AuthorityError):
        owner_call(
            a,
            s.handler,
            "READ_SALES_SUPPLEMENT",
            {},
            s.path | {"request_key": s.spec.idempotency_key},
            s.acl,
        )
    a.e.app.authority = s.acl
    with pytest.raises(AuthorityError):
        a.e.app.confirm(
            a.e.principal,
            s.old.plan_id,
            result["proposal"]["revision"],
            result["digest"],
            expected_plan_version=s.old.version,
            key="fixture-confirm-new",
        )
    assert snapshot(a)["workflow_planning.plans"] == before["workflow_planning.plans"]
    s.acl.allowed.add(new_read)
    confirmed = a.e.app.confirm(
        a.e.principal,
        s.old.plan_id,
        result["proposal"]["revision"],
        result["digest"],
        expected_plan_version=s.old.version,
        key="fixture-confirm-new",
    )
    assert confirmed["plan"]["version"] == s.old.version + 1
    assert set(before["workflow_planning.plans"]) < set(
        snapshot(a)["workflow_planning.plans"]
    )


@pytest.mark.parametrize(
    "bad",
    [
        "plan",
        "source",
        "problem",
        "old-criteria",
        "missing-criteria",
        "old-skill",
        "old-employee",
        "revoked",
        "service",
        "role",
        "contract",
        "key-conflict",
    ],
)
def test_same_source_supplement_fail_closed(automation, bad):
    a = automation
    s = prepare_supplement_fixture(
        a, changed_role=bad == "role", bad_contract=bad == "contract"
    )
    spec = s.spec
    ctx = a.subject
    if bad == "key-conflict":
        owner_call(
            a,
            s.handler,
            "PREPARE_SALES_SUPPLEMENT",
            spec.model_dump(mode="json"),
            s.path,
            s.acl,
        )
        spec = spec.model_copy(update={"reason": "conflicting same key"})
    if bad == "plan":
        spec = spec.model_copy(update={"plan_digest": "0" * 64})
    if bad == "source":
        spec = spec.model_copy(
            update={
                "source_snapshot": spec.source_snapshot.model_copy(
                    update={"digest": "0" * 64}
                )
            }
        )
    if bad == "problem":
        spec = spec.model_copy(
            update={
                "new_target": spec.new_target.model_copy(
                    update={
                        "problem": spec.new_target.problem.model_copy(
                            update={"digest": "0" * 64}
                        )
                    }
                )
            }
        )
    if bad == "old-criteria":
        spec = spec.model_copy(update={"new_target": s.old.semantics.target})
    if bad == "missing-criteria":
        spec = spec.model_copy(
            update={
                "new_target": spec.new_target.model_copy(
                    update={
                        "criteria": spec.new_target.criteria.model_copy(
                            update={"revision_id": "nonexistent-criterion-set"}
                        )
                    }
                )
            }
        )
    if bad in ["old-skill", "old-employee"]:
        kind = "SKILL" if bad == "old-skill" else "EMPLOYEE"
        spec = spec.model_copy(
            update={
                kind.lower(): next(
                    r.selected for r in s.old.semantics.requirements if r.kind == kind
                )
            }
        )
    if bad == "revoked":
        s.acl.allowed.remove(
            (
                "SKILL",
                "READ_RESOURCE",
                reference("skill", spec.skill.resource_id, spec.skill.revision_id),
            )
        )
    if bad == "service":
        ctx = replace(ctx, principal_id="service:policy")
    before = snapshot(a)
    with pytest.raises((WorkbenchOwnerError, AuthorityError)):
        owner_call(
            a,
            s.handler,
            "PREPARE_SALES_SUPPLEMENT",
            spec.model_dump(mode="json"),
            s.path,
            s.acl,
            ctx,
        )
    assert snapshot(a) == before


def test_default_closed_composition_and_no_unrelated_surface():
    assert operations(None, None) == ()
    with pytest.raises(AuthorityError):
        operations(object(), {"skill": object()}, enabled=True)


def test_optional_origin_preserves_predecessor_serialization_digest():
    # Golden produced from the unchanged 576f905d parent with these fixed IDs.
    old = legacy_proposal("legacy-proposal").model_copy(
        update={"invocation_id": "legacy-invocation"}
    )
    assert "origin" not in old.model_dump(mode="json")
    assert (
        old.digest == "8753e2459d2311dd9bb57abe564bd75ca49ef8cd0c02937de19fb8a232711f83"
    )


@pytest.mark.parametrize("kind", ["skill", "plan"])
def test_original_key_concurrency_is_one_transactional_receipt(automation, kind):
    a = automation
    s = skill_request(a) if kind == "skill" else prepare_supplement_fixture(a)
    operation = (
        "PREPARE_PREPARED_SKILL_SUCCESSOR"
        if kind == "skill"
        else "PREPARE_SALES_SUPPLEMENT"
    )
    payload = s.body if kind == "skill" else s.spec.model_dump(mode="json")
    before = snapshot(a)
    barrier = Barrier(2)

    def invoke():
        barrier.wait(timeout=10)
        return owner_call(a, s.handler, operation, payload, s.path, s.acl)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(invoke) for _ in range(2)]
        results = [f.result(timeout=30) for f in futures]
    assert results[0] == results[1]
    with a.repository.pool.connection() as c:
        prefix = (
            "prepared-skill-successor:"
            if kind == "skill"
            else "planning-sales-supplement:"
        )
        key = payload["commandKey" if kind == "skill" else "idempotency_key"]
        count = c.execute(
            "SELECT count(*) n FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
            "AND command_key=%s",
            (
                a.e.scope.namespace,
                a.e.scope.security_domain,
                a.subject.principal_id,
                prefix + key,
            ),
        ).fetchone()["n"]
        assert count == 1
    after = snapshot(a)
    for table in (
        "workflow_planning.plans",
        "execution_authority.workflow_runs",
        "authorization_admin.grants",
    ):
        assert after[table] == before[table]
    if kind == "skill":
        record = a.services["skill"].repository.get(
            a.services["skill"].scope(a.e.scope.namespace, a.e.scope.security_domain),
            "skill",
            s.path["identity"],
        )
        assert len(record["revisions"]) == len(s.old["revisions"]) + 2
    else:
        assert (
            len(after["workflow_planning.proposals"])
            == len(before["workflow_planning.proposals"]) + 1
        )


@pytest.mark.parametrize("kind", ["skill", "plan"])
def test_receipt_failure_rolls_back_all_preceding_owner_writes(
    automation, monkeypatch, kind
):
    import agent_console.planning_sales_supplement as plan_module
    import agent_console.prepared_skill_successor as skill_module

    a = automation
    s = skill_request(a) if kind == "skill" else prepare_supplement_fixture(a)
    before = snapshot(a)
    original = a.services["skill"].repository.get(
        a.services["skill"].scope(a.e.scope.namespace, a.e.scope.security_domain),
        "skill",
        a.refs["skill"].resource_id,
    )

    def fail_receipt(_):
        raise RuntimeError("isolated receipt persistence failure")

    monkeypatch.setattr(
        skill_module if kind == "skill" else plan_module, "Jsonb", fail_receipt
    )
    with pytest.raises(RuntimeError, match="receipt persistence"):
        owner_call(
            a,
            s.handler,
            "PREPARE_PREPARED_SKILL_SUCCESSOR"
            if kind == "skill"
            else "PREPARE_SALES_SUPPLEMENT",
            s.body if kind == "skill" else s.spec.model_dump(mode="json"),
            s.path,
            s.acl,
        )
    assert snapshot(a) == before
    assert (
        a.services["skill"].repository.get(
            a.services["skill"].scope(a.e.scope.namespace, a.e.scope.security_domain),
            "skill",
            a.refs["skill"].resource_id,
        )
        == original
    )


def test_supplement_bff_csrf_and_foreign_original_key(automation):
    a = automation
    s = prepare_supplement_fixture(a)
    body = s.spec.model_dump(mode="json")
    url = "/api/workbench/v1/planning-v2/" + s.old.plan_id + "/sales-supplements"
    before = snapshot(a)
    with client(a, s.acl) as c:
        assert c.post(url, json=body).status_code == 403
        assert snapshot(a) == before
        result = c.post(
            url,
            json=body,
            headers={"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"},
        )
        assert result.status_code == 200, result.text
        original = c.get(url + "/by-key/" + body["idempotency_key"])
        assert original.status_code == 200
        assert original.json()["result"] == result.json()["result"]
    # Even an independently authorized actor/scope cannot recover another receipt.
    for context in (
        replace(a.subject, principal_id="human:other-reviewer"),
        replace(a.subject, scope=replace(a.subject.scope, tenant_id="foreign")),
    ):
        acl = ExactFixtureAuthority(context.principal_id, s.acl.allowed)
        with pytest.raises(WorkbenchOwnerError, match="SUPPLEMENT_RECEIPT_NOT_FOUND"):
            owner_call(
                a,
                s.handler,
                "READ_SALES_SUPPLEMENT",
                {},
                s.path | {"request_key": body["idempotency_key"]},
                acl,
                context,
            )
