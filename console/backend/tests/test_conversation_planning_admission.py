"""Isolated owner integration: ordinary planning does not borrow admin authority."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import bind_problem
from agent_console.conversation_planning_admission import (
    ConversationPlanningAdmission,
    limits,
)
from agent_console.planning_call_admission import (
    BoundPlanningAdmission,
    PlanningCallAdmission,
)
from test_context_call_admission import env  # noqa: F401
from test_conversation_experience_admission import (  # noqa: F401
    configure,
    prepare,
    pytestmark,
)
from test_local_accounts_postgres import setup  # noqa: F401


@pytest.fixture
def ordinary(env, tmp_path):  # noqa: F811
    e = env
    invocation, owner, path, _ = configure(e, tmp_path)
    prepare(e, invocation, owner)
    # Provider-success fixture only; this test does not claim a real model call.
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_assistance.invocation_versions "
            "SELECT namespace,security_domain,invocation_id,"
            "aggregate_version+1,'SUCCEEDED',"
            'record || \'{"state":"SUCCEEDED","resultKind":"DRAFT_READY"}\'::jsonb '
            ",now() FROM draft_assistance.invocation_versions "
            "WHERE invocation_id=%s ORDER BY aggregate_version DESC LIMIT 1",
            (invocation.invocation_id,),
        )
        assert bind_problem(
            c,
            e.reviewer,
            {"revision": {"business_problem_id": "ordinary-new-problem"}},
            invocation.invocation_id,
        )
    service = PlanningCallAdmission(
        e.admission.delegation, dict(e.admission.configuration)
    )
    service.migrate()
    service.conversation_experience = ConversationPlanningAdmission(
        e.admission, service.configuration
    )
    e.planning, e.source, e.policy_path = service, invocation, path
    return e


def planned(e, key="new-plan", problem="ordinary-new-problem", commitment=None):
    request = SimpleNamespace(
        idempotency_key=key,
        target=SimpleNamespace(problem=SimpleNamespace(resource_id=problem)),
    )
    record = {
        "request": {"idempotency_key": key},
        "target": {
            "invocation_id": "planning-invocation:" + key,
            "suggestion_context_id": "planning-context:" + key,
            "input_commitment": commitment or key,
            "problem": {"problem": {"resource_id": problem}},
        },
    }
    return e.planning.prepare_record(e.reviewer, request, record)


def test_prepares_once_same_budget_and_retains_independent_grant_gate(ordinary):
    e = ordinary
    result = planned(e)
    assert result["admission"]["ready"]
    assert result["admission"]["cumulative_call_cap"] == 20
    assert result["admission"]["total_cost_cap_microusd"] == 1_000_000
    assert planned(e) == result
    with pytest.raises(AuthorityError, match="PAYLOAD_CONFLICT"):
        planned(e, commitment="changed-target")
    with (
        pytest.raises(AuthorityError, match="GRANTS_REQUIRED"),
        BoundPlanningAdmission(e.planning, e.reviewer).dispatch_guard(
            result["invocation"]
        ),
    ):
        pytest.fail("Call admission must not create plan/model grants")
    with e.repo.connection_scope() as c:
        rows = c.execute(
            "SELECT * FROM authorization_admin.context_call_decisions "
            "ORDER BY created_at"
        ).fetchall()
        assert len(rows) == 2
        assert rows[1]["expires_at"] <= rows[0]["expires_at"]
        row = c.execute(
            "SELECT * FROM authorization_admin.context_call_requests "
            "WHERE context_id=%s",
            (result["admission"]["context_id"],),
        ).fetchone()
        assert not row["record"].get("development_administrator")
        assert limits(
            c, row, SimpleNamespace(ledger_id=e.planning.configuration["ledger_id"])
        ) == (20, 1_000_000)
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM "
                "authorization_admin.planning_call_preparations"
            ).fetchone()["n"]
            == 1
        )


def test_wrong_problem_changed_policy_and_revoked_source_fail_closed(ordinary):
    e = ordinary
    with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
        planned(e, problem="somebody-elses-problem")
    text = e.policy_path.read_text()
    e.policy_path.write_text(text.replace("a" * 64, "b" * 64))
    with pytest.raises(AuthorityError, match="POLICY_CHANGED"):
        planned(e)
    e.policy_path.write_text(text)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) SELECT admission_id,'operator:test' FROM "
            "authorization_admin.context_call_decisions"
        )
    with pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"):
        planned(e)


def test_unsettled_source_blocks_but_another_context_does_not(ordinary):
    e = ordinary
    ledger = e.planning.configuration["ledger_id"]
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_provider_budget.reservations VALUES "
            "('s5-323-demo','isolated-real-demo',%s,'pending','pending-op',%s,100,500,1000,%s,now())",
            (ledger, e.invocation.invocation_id, "f" * 64),
        )
    assert planned(e)["admission"]["ready"]
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_provider_budget.reservations VALUES "
            "('s5-323-demo','isolated-real-demo',%s,'pending2','pending-op2',%s,"
            "100,500,1000,%s,now())",
            (ledger, e.source.invocation_id, "f" * 64),
        )
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        planned(e, key="second-plan")
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        planned(e)


def test_revoked_planning_and_raised_allowance_are_not_renewed(ordinary):
    e = ordinary
    result = planned(e)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) SELECT admission_id,'operator:test' FROM "
            "authorization_admin.context_call_decisions WHERE context_id=%s",
            (result["admission"]["context_id"],),
        )
    with pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"):
        planned(e)
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        ConversationPlanningAdmission(
            e.admission, {**e.planning.configuration, "calls": 100}
        )
    assert result["admission"]["maximum_new_calls"] == 1
