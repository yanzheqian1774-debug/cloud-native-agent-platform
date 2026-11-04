# ruff: noqa: F401, F811 -- Real isolated owner fixtures; no live effects.
"""One atomic continuation uses actual grant/Plan/employee/Native queue owners."""

from datetime import timedelta
from pathlib import Path

import pytest
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.readonly_continuation import ReadonlyContinuation
from agent_console.readonly_continuation_policy import (
    ReadonlyContinuationPolicy,
    ReadonlyWork,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
def test_readonly_continuation_queues_one_run_and_get_replay_never_dispatches_again(
    automation,
    monkeypatch,
):
    a = automation
    assert a.run()["state"] == "READY"
    with a.repository.pool.connection() as c, c.transaction():
        original_call = AuthorizedOwnerCall(
            "SELECT_POLICY_EMPLOYEE_RESOURCES",
            a.subject,
            c,
            {
                "version": a.e.p.plan_version,
                "digest": a.e.p.plan_digest,
                "expectedProposalRevision": a.e.p.plan_version,
                "employee": next(
                    r.selected
                    for r in a.e.p.semantics.requirements
                    if r.kind == "EMPLOYEE"
                ).model_dump(mode="json"),
                "idempotencyKey": "isolated-planning-only-successor",
            },
            {"proposal_id": a.e.p.plan_id},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ()),
            1,
            1,
        )
        selection = a.automation.select_employee(original_call)
    source_version = selection["confirmation"]["plan"]["version"]
    assert (
        a.run(key="continuation-source-prep", version=source_version)["state"]
        == "READY"
    )
    native = PostgresExecutionAuthorityRepository(
        a.repository.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0008_execution_runtime_authority.sql",
    )
    try:
        native.migrate_native_dispatch(
            Path(__file__).parents[1] / "migrations/0022_native_execution_dispatch.sql"
        )
        from agent_console.prepared_result_review import migrate as migrate_review

        with a.repository.pool.connection() as c:
            migrate_review(c)
        policy = ReadonlyContinuationPolicy(
            policyId="isolated-execution-policy",
            policyVersion="1",
            enabled=True,
            works=(
                ReadonlyWork(
                    namespace=a.e.scope.namespace,
                    securityDomain=a.e.scope.security_domain,
                    subject=a.subject.principal_id,
                    problem=a.e.p.semantics.target.problem,
                    sourceContentDigests=a.policy.workScopes[0].sourceContentDigests,
                    case="sales",
                    nativeAgentName="isolated-test-sales",
                    expiresAt=a.automation.grants.clock() + timedelta(hours=1),
                ),
            ),
        )
        handler = ReadonlyContinuation(
            a.automation, policy, PreparedNativeCoordinator(native)
        )

        def act(read=False):
            with a.repository.pool.connection() as c, c.transaction():
                authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
                return handler(
                    AuthorizedOwnerCall(
                        "READ_READONLY_CONTINUATION"
                        if read
                        else "CONTINUE_READONLY_WORK",
                        a.subject,
                        c,
                        {"version": source_version},
                        {"proposal_id": a.e.p.plan_id},
                        {"version": source_version},
                        (),
                        authority,
                        1,
                        1,
                    )
                )

        from agent_console.authority_contracts import AuthorityError

        def footprint():
            with a.repository.pool.connection() as c:
                return tuple(
                    c.execute("SELECT count(*) n FROM " + table).fetchone()["n"]
                    for table in (
                        "execution_authority.digital_employee_instances",
                        "execution_authority.assignments",
                        "workflow_planning.plans",
                        "execution_authority.workflow_runs",
                        "execution_authority.prepared_candidates",
                        "authorization_admin.grant_decisions",
                    )
                )

        before = footprint()
        handler.policy = policy.model_copy(update={"enabled": False})
        with pytest.raises(AuthorityError, match="READONLY_WORK_DISABLED"):
            act()
        assert footprint() == before
        handler.policy = policy
        original_decide = a.automation.decide

        def deny_execution(call, members, *args, **kwargs):
            if any(g.owner == "EXECUTION" and g.action == "START" for g in members):
                raise AuthorityError("ISOLATED_EXECUTION_AUTHORIZATION_DENIED")
            return original_decide(call, members, *args, **kwargs)

        monkeypatch.setattr(a.automation, "decide", deny_execution)
        with pytest.raises(
            AuthorityError, match="ISOLATED_EXECUTION_AUTHORIZATION_DENIED"
        ):
            act()
        assert footprint() == before
        monkeypatch.setattr(a.automation, "decide", original_decide)
        value = act()
        assert value["receipt"]["instancesCreated"] == 2
        assert value["receipt"]["policyIssuer"] == "service:resource-preparation-policy"
        assert value["receipt"]["executionStarted"]
        for read in (True, False, True):
            assert act(read)["receipt"] == value["receipt"]
        with a.repository.pool.connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM "
                    "execution_authority.native_dispatch_commands"
                ).fetchone()["n"]
                == 1
            )
            assert (
                c.execute(
                    "SELECT to_regclass('workflow_planning.invocations') t"
                ).fetchone()["t"]
                is None
            )
        from agent_console.readonly_continuation_worker import (
            ContinuationDispatchRepository,
            ContinuationWork,
        )

        work = ContinuationWork(native, policy, lambda *args: None)
        eligible = work.dispatches()
        assert eligible == (
            (
                a.e.scope.namespace,
                a.e.scope.security_domain,
                "governed-execution:prepared:" + value["receipt"]["preparationDigest"],
            ),
        )
        assert work.evaluate_terminal() == {"evaluated": 0, "blocked": 0}
        assert (
            native.claim_next(
                "isolated-unrelated-worker",
                eligible_dispatches=(
                    (
                        a.e.scope.namespace,
                        a.e.scope.security_domain,
                        "governed-execution:prepared:unrelated",
                    ),
                ),
            )
            is None
        )
        with a.repository.pool.connection() as c:
            row = c.execute(
                "SELECT state,claim_generation FROM "
                "execution_authority.native_dispatch_commands"
            ).fetchone()
            assert row["state"] == "QUEUED" and row["claim_generation"] == 0
        assert (
            ContinuationDispatchRepository(native, work).claim_next(
                "isolated-continuation-worker"
            )
            is not None
        )
    finally:
        native.pool.close()
