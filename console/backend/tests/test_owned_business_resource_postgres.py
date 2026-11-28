# ruff: noqa: F401, F811 -- Import actual disposable PostgreSQL owner fixtures.
"""Real resource/grant/continuation owners; admission port is a controlled fixture.

No real model, Kubernetes, existing admission DB, or business system is touched.
The companion admission package supplies independent persistent-owner coverage.
"""

from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.readonly_continuation import ReadonlyContinuation
from agent_console.readonly_continuation_policy import ReadonlyContinuationPolicy
from agent_console.readonly_continuation_worker import ContinuationWork
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_automatic_document_inputs import documents
from test_owned_business_resource_adapter import Scope
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def bind_owned(a):
    employee = next(
        r.selected for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    )
    source = a.refs["knowledge"]
    scope = Scope(
        source=source,
        sourceContentDigest=a.policy.workScopes[0].sourceContentDigests[0],
        employees=(employee,),
        agents=(a.refs["agent"],),
        skills=(a.refs["skill"],),
        runtimes=(a.refs["runtime"],),
        # This controlled standing scope explicitly includes the complete test
        # contract, not just the operations chosen by this particular Plan.
        operations=(
            "READ_DATA",
            "VALIDATE_DATA",
            "SUMMARIZE",
            "ANALYZE_DATA",
            "RENDER_REPORT",
        ),
        case="sales",
        nativeAgentName="isolated-test-sales",
    )
    binding = NS(
        admission_id="controlled-admission",
        record_digest="d" * 64,
        policy_digest="e" * 64,
        generation=1,
        tenant_id=a.subject.scope.tenant_id,
        security_domain=a.subject.scope.security_domain,
        subject_id=a.subject.principal_id,
        scope=scope,
        problem=a.e.p.semantics.target.problem,
        expires_at=a.policy.workScopes[0].expiresAt,
    )
    state = {"revoked": False, "reads": 0}

    def work(c, context, problem, *, source_digest=None, history=False, plan=None):
        assert c is not None
        assert context.principal_id == binding.subject_id and problem == binding.problem
        assert source_digest in (None, scope.sourceContentDigest)
        if plan is not None:
            from agent_console.planning_source_change import approved_source

            assert plan.plan_id == a.e.p.plan_id
            assert plan.semantics.target.problem == binding.problem
            assert approved_source(plan.semantics) == scope.source
        state["reads"] += 1
        if state["revoked"]:
            raise AuthorityError("OWNED_BUSINESS_ADMISSION_REVOKED")
        return binding

    a.automation.policy = a.policy.model_copy(update={"workScopes": ()})
    a.automation.owned_business = NS(work=work)
    return binding, state


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_owned_exact_preparation_and_revocation_before_grants(automation):
    a = automation
    binding, state = bind_owned(a)
    ready = a.run()
    assert ready["state"] == "READY", (ready, a.errors)
    assert ready["ownedBusiness"]["admissionId"] == binding.admission_id
    assert a.run(read=True) == ready
    with a.repository.pool.connection() as c:
        count = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
    state["revoked"] = True
    for read in (True, False):
        with pytest.raises(AuthorityError, match="ADMISSION_REVOKED"):
            a.run(read=read)
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == count
        )


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_owned_continuation_and_worker_use_same_saved_binding(automation):
    a = automation
    binding, state = bind_owned(a)
    assert a.run()["state"] == "READY"
    with a.repository.pool.connection() as c, c.transaction():
        selection = a.automation.select_employee(
            AuthorizedOwnerCall(
                "SELECT_POLICY_EMPLOYEE_RESOURCES",
                a.subject,
                c,
                {
                    "version": a.e.p.plan_version,
                    "digest": a.e.p.plan_digest,
                    "expectedProposalRevision": a.e.p.plan_version,
                    "employee": binding.scope.employees[0].model_dump(mode="json"),
                    "idempotencyKey": "owned-selection",
                },
                {"proposal_id": a.e.p.plan_id},
                {},
                (),
                AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
                1,
                1,
            )
        )
    version = selection["confirmation"]["plan"]["version"]
    assert a.run(key="owned-execution-preparation", version=version)["state"] == "READY"
    native = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    try:
        native.migrate_native_dispatch(
            Path(__file__).parents[1] / "migrations/0022_native_execution_dispatch.sql"
        )
        from agent_console.prepared_result_review import migrate

        with a.repository.pool.connection() as c:
            migrate(c)
        policy = ReadonlyContinuationPolicy(
            policyId="owned-readonly", policyVersion="1", enabled=True, works=()
        )
        handler = ReadonlyContinuation(
            a.automation, policy, PreparedNativeCoordinator(native)
        )

        def act(read=False):
            with a.repository.pool.connection() as c, c.transaction():
                return handler(
                    AuthorizedOwnerCall(
                        "READ_READONLY_CONTINUATION"
                        if read
                        else "CONTINUE_READONLY_WORK",
                        a.subject,
                        c,
                        {"version": version},
                        {"proposal_id": a.e.p.plan_id},
                        {"version": version},
                        (),
                        AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
                        1,
                        1,
                    )
                )

        value = act()
        assert value["receipt"]["ownedBusiness"]["admissionId"] == binding.admission_id
        assert act(True)["receipt"] == act()["receipt"] == value["receipt"]

        def authority(c, command):
            assert command.principal_id == a.subject.principal_id
            return a.subject, AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())

        work = ContinuationWork(
            native, policy, authority, owned_business=a.automation.owned_business
        )
        expected = (
            (
                a.e.scope.namespace,
                a.e.scope.security_domain,
                "governed-execution:prepared:" + value["receipt"]["preparationDigest"],
            ),
        )
        assert work.dispatches() == expected
        assert ContinuationWork(native, policy, authority).dispatches() == ()
        state["revoked"] = True
        assert work.dispatches() == ()
        with pytest.raises(AuthorityError, match="ADMISSION_REVOKED"):
            act()
        with a.repository.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 1
            )
            row = c.execute(
                "SELECT state,claim_generation FROM "
                "execution_authority.native_dispatch_commands"
            ).fetchone()
            assert row == {"state": "QUEUED", "claim_generation": 0}
    finally:
        native.pool.close()


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_owned_automatic_selection_never_scans_or_chooses_unapproved_latest(
    automation, monkeypatch
):
    from test_problem_resource_coverage import invoke

    a = automation
    binding, state = bind_owned(a)
    assert a.run()["state"] == "READY"

    def no_scan(*_, **__):
        raise AssertionError("owned scope must use exact approved revisions")

    monkeypatch.setattr("agent_console.problem_resource_coverage.identities", no_scan)
    report = invoke(a, "READ_PROBLEM_RESOURCE_COVERAGE")
    assert report["selection"] == binding.scope.employees[0].model_dump(mode="json")
    assert len(report["candidates"]) == 1
    result = invoke(a, "SELECT_PROBLEM_RESOURCES")
    assert result["ownedBusiness"]["admissionId"] == binding.admission_id
    assert invoke(a, "READ_PROBLEM_RESOURCE_SELECTION") == result
    state["revoked"] = True
    with pytest.raises(AuthorityError, match="ADMISSION_REVOKED"):
        invoke(a, "READ_PROBLEM_RESOURCE_SELECTION")


@pytest.mark.parametrize("documents", [True], indirect=True)
def test_owned_document_rules_use_actual_published_contract_without_named_old_work(
    documents,
):
    from agent_console.owned_business_resource_adapter import OwnedResourceWork
    from test_automatic_document_inputs import run_test

    d = documents
    approved = d.automation.continuation.policy.works[0]
    business = Scope(
        source=d.refs["knowledge"],
        sourceContentDigest=d.work.sourceContentDigests[0],
        skills=(d.refs["skill"],),
        operations=("READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RENDER_REPORT"),
        documentRules=approved.documentRules,
    )
    d.work = OwnedResourceWork(
        **d.work.model_dump(),
        admissionId="controlled-document-admission",
        admissionRecordDigest="d" * 64,
        admissionPolicyDigest="e" * 64,
        businessScope=business,
    )
    d.automation.continuation.policy = d.automation.continuation.policy.model_copy(
        update={"works": ()}
    )

    def current(context, problem, now, *, connection, source_digest, plan=None):
        assert connection is not None and context == d.context
        assert problem == d.work.problem
        assert source_digest == d.work.sourceContentDigests[0]
        assert plan is None, "this legacy fixture has no adopted Plan"
        return d.work

    d.automation.work = current
    result = run_test(d)
    assert result["passed"] and result["modelCalls"] == 0
    assert len(result["tests"]) == 4
    assert [event[0] for event in d.events] == ["decide", "require"]
    assert all(test["actualExecution"] for test in result["tests"])


@pytest.mark.parametrize("automation", ["new", "existing"], indirect=True)
def test_owned_rejects_unpublished_or_unapproved_members_without_new_grants(automation):
    from agent_console.plan_suggestion_domain import ExactReference

    a = automation
    binding, _ = bind_owned(a)
    if a.mode == "existing":
        binding.scope = binding.scope.model_copy(
            update={
                "skills": (
                    ExactReference(
                        resource_id="not-approved", revision_id="v1", digest="a" * 64
                    ),
                )
            }
        )
    with a.repository.pool.connection() as c:
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
    with pytest.raises(
        AuthorityError,
        match=r"OWNED_BUSINESS_(PUBLISHED_EMPLOYEE_REQUIRED|RESOURCE_NOT_AUTHORIZED)",
    ):
        a.run()
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_owned_actual_skill_test_cannot_run_an_unapproved_extra_operation(automation):
    a = automation
    binding, _ = bind_owned(a)
    unused = set(binding.scope.operations) - {
        t.operation for t in a.e.p.semantics.tasks
    }
    assert unused, "fixture must exercise a contract operation absent from its Plan"
    excluded = sorted(unused)[0]
    binding.scope = binding.scope.model_copy(
        update={
            "operations": tuple(op for op in binding.scope.operations if op != excluded)
        }
    )
    result = a.run()
    assert result["state"] == "PARTIALLY_READY"
    skill = next(item for item in result["resources"] if item["kind"] == "skill")
    assert skill["state"] == "BLOCKED"
    assert skill["reason"] == "OWNED_BUSINESS_TEST_OPERATION_NOT_AUTHORIZED"
    assert result["executionStarted"] is False and result["modelCalls"] == 0
