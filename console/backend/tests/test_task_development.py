"""Controlled PostgreSQL verification of the approved 323 recovery exception."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.task_development import (
    DevelopmentRevision,
    DiagnosticAdmission,
    admit,
    revise,
)
from psycopg.types.json import Jsonb
from test_task_delegation import (
    assembled as assembled,
)
from test_task_delegation import (
    create_task_problem,
)
from test_task_delegation import (
    env as env,
)
from test_task_delegation import (
    repository as repository,
)


def setup(e):
    d = e.service.approve(e.contexts["approver"], e.spec)
    original = e.service.read(e.contexts["reader"], d)
    spec = DevelopmentRevision(
        original_digest=original["original_digest"],
        mode="UNTIL_COMPLETE_PAUSE_OR_REVOKE",
        accept_unknown_remote_processing_and_cost=True,
        synthetic_case_only=True,
        idempotency_key="continuous-323",
    )
    return d, spec


def planning(e, d, *, reason="WORKER_FAILURE", reaped=True, worker_pid=2147483647):
    problem = create_task_problem(e)
    store = PostgresPlanningInvocations(
        PostgresPlanningRepository(e.service.repository.pool)
    )
    scope = ScopeIdentity("tenant-a", "quality")
    target = {"problem": {"resource_id": problem.business_problem_id}}

    def claim(identity, key, target_override=None):
        store.claim(
            scope,
            "human:reader",
            key,
            "d" * 64,
            {
                "target": {
                    "invocation_id": identity,
                    "problem": target_override or target,
                }
            },
        )
        return NS(
            scope=e.first.scope,
            invocation_id=identity,
            profile_revision_id=e.budgets["planning"].profile.profile_revision_id,
        )

    b = e.budgets["planning"]
    quote = ProviderBudgetQuote(
        100, b.profile.maximum_output_tokens, 100 + b.profile.maximum_output_tokens
    )
    old = claim("old-unknown", "old-key")
    reservation = b.reserve("old-budget", old, quote)
    store.finish(scope, old.invocation_id, {"technical_status": "OUTCOME_UNKNOWN"})
    with e.service.repository.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.provider_receipts VALUES(%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                old.invocation_id,
                Jsonb(
                    {
                        "reservation_id": reservation,
                        "deadline": {
                            "reaped": reaped,
                            "worker_pid": worker_pid,
                            "reason": reason,
                        },
                    }
                ),
            ),
        )
    return b, quote, claim


def test_revision_independent_immutable_and_replay(env):
    e = env
    d, spec = setup(e)
    with pytest.raises(AuthorityError):
        revise(e.service, e.contexts["reader"], d, spec)
    first = revise(e.service, e.contexts["approver"], d, spec)
    assert revise(e.service, e.contexts["approver"], d, spec) == first
    with pytest.raises(AuthorityError, match="CONFLICT"):
        revise(
            e.service,
            e.contexts["approver"],
            d,
            spec.model_copy(update={"idempotency_key": "different"}),
        )
    assert e.service.read(e.contexts["reader"], d)["approval"] == e.spec.model_dump(
        mode="json"
    ) | {
        "purpose_policy": "problem-to-plan-task.v1",
        "purposes": e.service.read(e.contexts["reader"], d)["approval"]["purposes"],
    }
    e.service.repository.verify_existing_schema()


def test_exact_unknown_admission_preserves_liability_and_serialization(env):
    e = env
    d, spec = setup(e)
    b, quote, claim = planning(e, d)
    revise(e.service, e.contexts["approver"], d, spec)
    new = claim("new-successor", "new-key")
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        b.reserve("new-budget", new, quote)
    # Admission must precede the invocation claim; an existing key cannot be adopted.
    request = DiagnosticAdmission(
        request_key="next-key",
        unknown_invocation_ids=["old-unknown"],
        reason="inspect protocol",
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        permits = list(
            executor.map(
                lambda _: admit(e.service, e.contexts["reader"], d, request), range(2)
            )
        )
    assert permits[0] == permits[1]
    next_inv = claim("next-successor", "next-key")
    with ThreadPoolExecutor(max_workers=2) as executor:
        reservations = list(
            executor.map(lambda _: b.reserve("next-budget", next_inv, quote), range(2))
        )
    assert reservations[0] == reservations[1]
    third_request = request.model_copy(update={"request_key": "third-key"})
    admit(e.service, e.contexts["reader"], d, third_request)
    third = claim("third", "third-key")
    with pytest.raises(AuthorityError, match="PENDING_RESERVATION"):
        b.reserve("third-budget", third, quote)
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
        assert (
            c.execute(
                "SELECT record FROM workflow_planning.invocation_results "
                "WHERE invocation_id=%s",
                ("old-unknown",),
            ).fetchone()["record"]["technical_status"]
            == "OUTCOME_UNKNOWN"
        )
    e.service.revoke(e.contexts["approver"], d)
    with (
        pytest.raises(AuthorityError, match="INACTIVE"),
        b.dispatch_guard(next_inv, quote),
    ):
        pytest.fail("revoked dispatch")


@pytest.mark.parametrize(
    "reason,reaped", [("CLEANUP_FAILURE", True), ("WORKER_FAILURE", False)]
)
def test_cleanup_failure_or_unreaped_cannot_be_accepted(env, reason, reaped):
    e = env
    d, spec = setup(e)
    planning(e, d, reason=reason, reaped=reaped)
    revise(e.service, e.contexts["approver"], d, spec)
    with pytest.raises(AuthorityError, match="WORKER_NOT_REAPED"):
        admit(
            e.service,
            e.contexts["reader"],
            d,
            DiagnosticAdmission(
                request_key="successor",
                unknown_invocation_ids=["old-unknown"],
                reason="diagnose",
            ),
        )


def test_diagnostic_target_and_subject_are_exact(env):
    e = env
    d, spec = setup(e)
    b, quote, claim = planning(e, d)
    revise(e.service, e.contexts["approver"], d, spec)
    request = DiagnosticAdmission(
        request_key="successor",
        unknown_invocation_ids=["old-unknown"],
        reason="diagnose",
    )
    with pytest.raises(AuthorityError, match="NOT_FOUND"):
        admit(e.service, e.contexts["other"], d, request)
    admit(e.service, e.contexts["reader"], d, request)
    new = claim("successor", "successor", {"problem": {"resource_id": "foreign"}})
    with pytest.raises(AuthorityError):
        b.reserve("successor-budget", new, quote)


@pytest.mark.parametrize("env", [{"cost": 1}], indirect=True)
def test_continuous_revision_replaces_original_total_caps(env):
    from agent_console.draft_assistance import ObservationState, ProviderObservation

    e = env
    d, spec = setup(e)
    revise(e.service, e.contexts["approver"], d, spec)
    b, quote, claim = planning(e, d)
    # Three successors exceed the fixture's original two-call limit, while
    # UNKNOWN liabilities remain reserved and each active successor settles.
    for i in range(3):
        key = f"diagnostic-{i}"
        admit(
            e.service,
            e.contexts["reader"],
            d,
            DiagnosticAdmission(
                request_key=key,
                unknown_invocation_ids=["old-unknown"],
                reason="new evidence",
            ),
        )
        inv = claim(key, key)
        reservation = b.reserve(key, inv, quote)
        b.record_usage(
            key,
            reservation,
            ProviderObservation(
                f"observation-{i}",
                ObservationState.FAILED,
                input_tokens=10,
                output_tokens=10,
            ),
        )
        with e.service.repository.connection_scope() as c:
            c.execute(
                "INSERT INTO workflow_planning.invocation_results VALUES(%s,%s,%s,%s)",
                ("tenant-a", "quality", key, Jsonb({"technical_status": "SUCCEEDED"})),
            )
    with e.service.repository.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 4
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 3
        )


def test_continuous_revision_outlives_old_window_but_not_revocation(env):
    import time
    from datetime import UTC, datetime, timedelta

    from agent_console.task_delegation import active
    from test_task_delegation import submit

    e = env
    expires = datetime.now(UTC) + timedelta(seconds=0.5)
    e.spec = e.spec.model_copy(update={"expires_at": expires})
    d, spec = setup(e)
    revise(e.service, e.contexts["approver"], d, spec)
    while datetime.now(UTC) < expires:
        time.sleep(min(0.01, (expires - datetime.now(UTC)).total_seconds()))
    with e.service.repository.connection_scope() as c:
        assert active(c, d)[0]["expires_at"] == expires
    request = submit(e)
    assert e.service.authorize(e.contexts["reader"], d, request.request_id)
    e.service.revoke(e.contexts["approver"], d)
    with (
        e.service.repository.connection_scope() as c,
        pytest.raises(AuthorityError, match="INACTIVE"),
    ):
        active(c, d)


def test_revision_http_csrf_independent_signature(env):
    from agent_console.task_delegation_api import install_task_delegation_routes
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_creator_continuation_postgres import login

    e = env
    d, spec = setup(e)
    app = create_workbench_bff(
        e.sessions,
        None,
        WorkbenchBffPolicy("console.example", "https://console.example"),
        grant_administration=e.grants,
        route_installers=(install_task_delegation_routes(e.service),),
    )
    path = (
        "/api/workbench/v1/authorization/task-delegations/"
        + d
        + "/development-revision"
    )
    with TestClient(app, base_url="https://console.example") as client:
        token = login(client, "reader-controlled")
        assert (
            client.post(
                path,
                json=spec.model_dump(),
                headers={"origin": "https://console.example", "x-csrf-token": token},
            ).status_code
            != 200
        )
    with TestClient(app, base_url="https://console.example") as client:
        token = login(client, "approver-controlled")
        assert (
            client.post(
                path,
                json=spec.model_dump(),
                headers={"origin": "https://console.example"},
            ).status_code
            == 403
        )
        result = client.post(
            path,
            json=spec.model_dump(),
            headers={"origin": "https://console.example", "x-csrf-token": token},
        )
        assert result.status_code == 200, result.text
        assert result.json()["issuer_id"] == "human:approver"


@pytest.mark.parametrize("reason", ["PAUSED", "COMPLETED"])
def test_stop_is_attenuation_and_blocks_existing_grants(env, reason):
    from datetime import UTC, datetime

    from agent_console.draft_assistance_authorization import request_grant
    from agent_console.task_development import DevelopmentStop, stop
    from test_task_delegation import submit

    e = env
    d, spec = setup(e)
    revise(e.service, e.contexts["approver"], d, spec)
    request = submit(e)
    e.service.authorize(e.contexts["reader"], d, request.request_id)
    stop(e.service, e.contexts["reader"], d, DevelopmentStop(reason=reason))
    assert (
        e.grants.authorization.authorize_current(
            e.contexts["reader"], request_grant(e.first), now=datetime.now(UTC)
        )
        is None
    )
    with pytest.raises(AuthorityError, match="INACTIVE"):
        e.service.authorize(e.contexts["reader"], d, request.request_id)


def test_live_worker_blocks_despite_claimed_reap(env):
    import os

    e = env
    d, spec = setup(e)
    planning(e, d, worker_pid=os.getpid())
    revise(e.service, e.contexts["approver"], d, spec)
    with pytest.raises(AuthorityError, match="WORKER_NOT_REAPED"):
        admit(
            e.service,
            e.contexts["reader"],
            d,
            DiagnosticAdmission(
                request_key="successor",
                unknown_invocation_ids=["old-unknown"],
                reason="diagnose",
            ),
        )


def test_new_unknown_does_not_inherit_previous_permit(env):
    e = env
    d, spec = setup(e)
    b, quote, claim = planning(e, d)
    revise(e.service, e.contexts["approver"], d, spec)
    request = DiagnosticAdmission(
        request_key="second", unknown_invocation_ids=["old-unknown"], reason="diagnose"
    )
    admit(e.service, e.contexts["reader"], d, request)
    second = claim("second", "second")
    b.reserve("second-budget", second, quote)
    with e.service.repository.connection_scope() as c:
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES(%s,%s,%s,%s)",
            (
                "tenant-a",
                "quality",
                "second",
                Jsonb({"technical_status": "OUTCOME_UNKNOWN"}),
            ),
        )
    admit(
        e.service,
        e.contexts["reader"],
        d,
        request.model_copy(update={"request_key": "third"}),
    )
    third = claim("third", "third")
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        b.reserve("third-budget", third, quote)


def test_spawned_planning_transport_does_not_import_database_assembly():
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import agent_console.plan_suggestion_runtime; "
            'assert "psycopg" not in sys.modules; '
            'assert "agent_console.draft_assistance_bootstrap" not in sys.modules',
        ],
        env={**os.environ, "PYTHONPATH": os.pathsep.join(sys.path)},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_settlement_without_terminal_result_still_blocks_successor(env):
    from agent_console.draft_assistance import ObservationState, ProviderObservation

    e = env
    d, spec = setup(e)
    b, quote, claim = planning(e, d)
    revise(e.service, e.contexts["approver"], d, spec)
    request = DiagnosticAdmission(
        request_key="second", unknown_invocation_ids=["old-unknown"], reason="diagnose"
    )
    admit(e.service, e.contexts["reader"], d, request)
    second = claim("second", "second")
    reservation = b.reserve("second-budget", second, quote)
    b.record_usage(
        "second-usage",
        reservation,
        ProviderObservation(
            "second-observation",
            ObservationState.UNKNOWN,
            input_tokens=10,
            output_tokens=10,
        ),
    )
    admit(
        e.service,
        e.contexts["reader"],
        d,
        request.model_copy(update={"request_key": "third"}),
    )
    third = claim("third", "third")
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        b.reserve("third-budget", third, quote)
