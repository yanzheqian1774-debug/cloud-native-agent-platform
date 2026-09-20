"""PostgreSQL: independent timeout change retains the original case and ledger."""

from dataclasses import dataclass, replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.task_cases import enroll
from agent_console.task_delegation import active, configured_limits
from agent_console.task_development import revise as develop
from agent_console.task_timeout_revision import (
    TimeoutRevision,
    effective_limits,
    revise,
)
from test_draft_assistance import context
from test_task_cases import spec as case_spec
from test_task_delegation import assembled as assembled
from test_task_delegation import create_task_problem
from test_task_delegation import env as env
from test_task_delegation import repository as repository
from test_task_development import planning, setup


@dataclass(frozen=True)
class Configuration:
    read_timeout_seconds: int
    total_timeout_seconds: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    connect_timeout_seconds: int = 5


def prepare(e):
    profile = e.synthetic.profile
    configuration = Configuration(30, 60, 65536, profile.maximum_output_tokens)
    b = e.budgets["planning"]
    limits = configured_limits(profile, configuration, b, planning=True)
    b.delegation_configuration = limits
    e.service.configurations["planning"] = limits
    e.spec = e.spec.model_copy(update={"planning": type(e.spec.planning)(**limits)})
    e.service.timeout_source = (profile, configuration, b)
    d, revision = setup(e)
    planning(e, d)
    develop(e.service, e.contexts["approver"], d, revision)
    enroll(e.service, e.contexts["approver"], d, case_spec(e))
    ready = e.synthetic.begin(
        context("human:reader"),
        key="timeout-cost",
        content="Synthetic monthly project model cost; no bills; planning only.",
        parent_context_id=e.second.context_id,
        parent_turn_id=e.second.turn_id,
        expected_parent_version=e.second.turn_version,
        predecessor_invocation_id=e.second.invocation_id,
    ).invocation
    problem = create_task_problem(e, "timeout-cost-problem", draft=ready)
    spec = TimeoutRevision(
        problem_id=problem.business_problem_id,
        original_configuration_digest=limits["configuration_digest"],
        previous_read_seconds=30,
        read_seconds=55,
        idempotency_key="read-55",
    )
    return d, spec, limits


def test_timeout_independent_replay_and_immutable_history(env):
    e = env
    d, spec, old = prepare(e)
    original = e.service.read(e.contexts["reader"], d)
    with pytest.raises(AuthorityError, match="SELF_APPROVAL"):
        revise(e.service, e.contexts["reader"], d, spec)
    first = revise(e.service, e.contexts["approver"], d, spec)
    assert revise(e.service, e.contexts["approver"], d, spec) == first
    readback = e.service.read(e.contexts["reader"], d)
    assert readback["timeout_revision"] == first
    assert readback | {"timeout_revision": None} == original
    with e.service.repository.connection_scope() as c:
        row, _ = active(c, d)
        new = effective_limits(c, row, "planning")
        assert new != old
        assert {k: v for k, v in new.items() if k != "configuration_digest"} == {
            k: v for k, v in old.items() if k != "configuration_digest"
        }
        assert (
            effective_limits(c, row, "understanding") == row["record"]["understanding"]
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT record FROM workflow_planning.invocation_results "
                "WHERE invocation_id='old-unknown'"
            ).fetchone()["record"]["technical_status"]
            == "OUTCOME_UNKNOWN"
        )
        with pytest.raises(AuthorityError, match="TARGET_DENIED"):
            from types import SimpleNamespace

            effective_limits(
                c, row, "planning", SimpleNamespace(invocation_id="old-unknown")
            )
    with pytest.raises(AuthorityError, match="CONFLICT"):
        revise(
            e.service,
            e.contexts["approver"],
            d,
            spec.model_copy(update={"idempotency_key": "another"}),
        )
    e.service.migrate()
    e.service.repository.verify_existing_schema()


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"problem_id": "problem"}, "TARGET_DENIED"),
        ({"original_configuration_digest": "f" * 64}, "CONFIGURATION_MISMATCH"),
        ({"read_seconds": 61}, "BOUNDS_INVALID"),
        ({"read_seconds": 30}, "BOUNDS_INVALID"),
        ({"previous_read_seconds": 29}, "BOUNDS_INVALID"),
    ],
)
def test_timeout_rejects_wrong_case_digest_or_bounds(env, change, reason):
    d, spec, _ = prepare(env)
    with pytest.raises(AuthorityError, match=reason):
        revise(env.service, env.contexts["approver"], d, spec.model_copy(update=change))


@pytest.mark.parametrize(
    "change",
    [
        {"total_timeout_seconds": 90},
        {"maximum_output_tokens": 999},
        {"connect_timeout_seconds": 10},
    ],
)
def test_timeout_cannot_hide_other_configuration_changes(env, change):
    d, spec, _ = prepare(env)
    p, config, b = env.service.timeout_source
    env.service.timeout_source = (p, replace(config, **change), b)
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        revise(env.service, env.contexts["approver"], d, spec)


def test_unsigned_runtime_change_denied_and_signed_runtime_matches(env):
    from test_task_delegation import submit

    e = env
    d, spec, old = prepare(e)
    p, config, b = e.service.timeout_source
    changed = replace(config, read_timeout_seconds=55)
    new = configured_limits(p, changed, b, planning=True)
    e.service.configurations["planning"] = new
    request = submit(e)
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        e.service.authorize(e.contexts["reader"], d, request.request_id)
    e.service.timeout_source = (p, changed, b)
    saved = revise(e.service, e.contexts["approver"], d, spec)
    assert saved["record"]["limits"] == new
    assert saved["record"]["original_limits"] == old
    e.service.authorize(e.contexts["reader"], d, request.request_id)


def test_timeout_revision_http_requires_csrf_and_independent_actor(env):
    from agent_console.task_delegation_api import install_task_delegation_routes
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_creator_continuation_postgres import login

    e = env
    d, spec, _ = prepare(e)
    app = create_workbench_bff(
        e.sessions,
        None,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        grant_administration=e.grants,
        route_installers=(install_task_delegation_routes(e.service),),
    )
    path = "/api/workbench/v1/authorization/task-delegations/" + d + "/timeout-revision"
    with TestClient(app, base_url="https://console.example") as client:
        token = login(client, "reader-controlled")
        assert (
            client.post(
                path,
                json=spec.model_dump(),
                headers={
                    "origin": "https://console.example",
                    "x-csrf-token": token,
                },
            ).status_code
            != 200
        )
    with TestClient(app, base_url="https://console.example") as client:
        token = login(client, "approver-controlled")
        assert (
            client.post(
                path,
                json=spec.model_dump(),
                headers={
                    "origin": "https://console.example",
                },
            ).status_code
            == 403
        )
        response = client.post(
            path,
            json=spec.model_dump(),
            headers={
                "origin": "https://console.example",
                "x-csrf-token": token,
            },
        )
        assert response.status_code == 200
        assert response.json()["issuer_id"] == "human:approver"


def test_signed_timeout_budget_requires_new_config_and_exact_cost_case(env):
    from types import SimpleNamespace

    from agent_console.draft_assistance import ProviderBudgetQuote
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
    from agent_console.plan_suggestion_postgres import PostgresPlanningRepository

    e = env
    d, spec, _ = prepare(e)
    saved = revise(e.service, e.contexts["approver"], d, spec)
    store = PostgresPlanningInvocations(
        PostgresPlanningRepository(e.service.repository.pool)
    )
    scope = ScopeIdentity("tenant-a", "quality")
    store.claim(
        scope,
        "human:reader",
        "cost-long-wait",
        "e" * 64,
        {
            "target": {
                "invocation_id": "cost-long-wait",
                "problem": {
                    "problem": {"resource_id": spec.problem_id},
                },
            },
        },
    )
    b = e.budgets["planning"]
    identity = SimpleNamespace(
        scope=e.first.scope,
        invocation_id="cost-long-wait",
        profile_revision_id=b.profile.profile_revision_id,
    )
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        b.reserve("cost-long-wait-budget", identity, quote)
    b.delegation_configuration = saved["record"]["limits"]
    assert b.reserve("cost-long-wait-budget", identity, quote)
    with e.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )
