"""Isolated owner integration: ordinary planning does not borrow admin authority."""

from pathlib import Path
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
from psycopg.types.json import Jsonb
from test_context_call_admission import env  # noqa: F401
from test_conversation_experience_admission import (  # noqa: F401
    configure,
    prepare,
    pytestmark,
)
from test_conversation_planning_source import SOURCE, boundary
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


def planned(
    e,
    key="new-plan",
    problem="ordinary-new-problem",
    commitment=None,
    answers=(),
    predecessor=None,
    planning_context=None,
    revision=1,
):
    request = SimpleNamespace(
        idempotency_key=key,
        target=SimpleNamespace(problem=SimpleNamespace(resource_id=problem)),
    )
    record = {
        "request": {
            "idempotency_key": key,
            "answers": list(answers),
            "predecessor_invocation_id": predecessor,
        },
        "target": {
            "invocation_id": "planning-invocation:" + key,
            "suggestion_context_id": planning_context or "planning-context:" + key,
            "predecessor_invocation_id": predecessor,
            "request_revision": revision,
            "input_commitment": commitment or key,
            "problem": {"problem": {"resource_id": problem}},
        },
    }
    return e.planning.prepare_record(e.reviewer, request, record)


def clarification(e, kind="NEEDS_CLARIFICATION"):
    first = planned(e)
    with e.repo.connection_scope() as c:
        migrations = Path(__file__).parents[1] / "migrations"
        for name in ("0025_plan_suggestion.sql", "0026_plan_suggestion_invocation.sql"):
            c.execute((migrations / name).read_text())
        c.execute(
            "INSERT INTO workflow_planning.invocations VALUES "
            "('s5-323-demo','isolated-real-demo','planning-invocation:new-plan',"
            "%s,'new-plan','fixture-digest',%s)",
            (e.reviewer.principal_id, Jsonb(first["invocation"])),
        )
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES "
            "('s5-323-demo','isolated-real-demo','planning-invocation:new-plan',%s)",
            (Jsonb({"technical_status": "SUCCEEDED", "kind": kind}),),
        )
    return first


def continued(e, key="clarification", **changes):
    return planned(
        e,
        key=key,
        **{
            "predecessor": "planning-invocation:new-plan",
            "planning_context": "planning-context:new-plan",
            "revision": 2,
            **changes,
        },
    )


def test_clarification_has_separate_admission_same_context_and_no_duplicate(ordinary):
    e = ordinary
    first = clarification(e)
    result = continued(e)
    assert result["admission"]["context_id"] != first["admission"]["context_id"]
    assert (
        result["invocation"]["target"]["suggestion_context_id"]
        == "planning-context:new-plan"
    )
    assert result["admission"]["cumulative_call_cap"] == 20
    assert result["admission"]["total_cost_cap_microusd"] == 1_000_000
    assert continued(e) == result
    with pytest.raises(AuthorityError, match="SUCCESSOR_ALREADY_PREPARED"):
        continued(e, key="different-key-same-answer")
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) SELECT admission_id,'operator:test' "
            "FROM authorization_admin.context_call_decisions WHERE context_id=%s",
            (first["admission"]["context_id"],),
        )
    with pytest.raises(AuthorityError, match="ADMISSION_REQUIRED"):
        continued(e)


@pytest.mark.parametrize("kind", ["INVALID", "VALID_SUGGESTION"])
def test_only_clarification_result_can_continue_without_proposal(ordinary, kind):
    clarification(ordinary, kind)
    with pytest.raises(AuthorityError, match="CLARIFICATION_REQUIRED"):
        continued(ordinary)


def test_clarification_cannot_change_context_or_skip_revision(ordinary):
    clarification(ordinary)
    for changes in ({"planning_context": "another-context"}, {"revision": 3}):
        with pytest.raises(AuthorityError, match="CLARIFICATION_REQUIRED"):
            continued(ordinary, **changes)


def test_unsettled_planning_predecessor_cannot_continue(ordinary):
    e = ordinary
    clarification(e)
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_provider_budget.reservations VALUES "
            "('s5-323-demo','isolated-real-demo',%s,'pending','pending-op',"
            "'planning-invocation:new-plan',100,500,1000,%s,now())",
            (e.planning.configuration["ledger_id"], "f" * 64),
        )
    with pytest.raises(AuthorityError, match="OUTCOME_UNKNOWN"):
        continued(e)


def retain_source(e, source):
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_assistance.invocation_versions "
            "SELECT namespace,security_domain,invocation_id,"
            "aggregate_version+1,'SUCCEEDED',record || %s,now() "
            "FROM draft_assistance.invocation_versions WHERE invocation_id=%s "
            "ORDER BY aggregate_version DESC LIMIT 1",
            (Jsonb({"inputSource": {"source": source}}), e.source.invocation_id),
        )


def test_source_substitution_rejected_before_preparation_and_budget(ordinary):
    e = ordinary
    retain_source(e, SOURCE)
    with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
        planned(e, answers=[boundary({**SOURCE, "digest": "b" * 64})])
    with e.repo.connection_scope() as c:
        for table in (
            "authorization_admin.planning_call_preparations",
            "draft_provider_budget.reservations",
        ):
            assert c.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
    result = planned(e, answers=[boundary(SOURCE)])
    assert result["admission"]["ready"]
    assert planned(e, answers=[boundary(SOURCE)]) == result
    with e.repo.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.context_call_requests "
            "WHERE context_id=%s",
            (result["admission"]["context_id"],),
        ).fetchone()
        assert row["record"]["understanding_input_source"] == {"source": SOURCE}
        row["record"]["understanding_input_source"]["source"]["digest"] = "b" * 64
        with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
            e.planning.conversation_experience.require(e.planning, c, e.reviewer, row)


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


def test_planning_cannot_substitute_source_allowance_or_raise_cap(ordinary):
    from copy import deepcopy

    e = ordinary
    result = planned(e)
    with e.repo.connection_scope() as c:
        row = c.execute(
            "SELECT * FROM authorization_admin.context_call_requests "
            "WHERE context_id=%s",
            (result["admission"]["context_id"],),
        ).fetchone()
        budget = SimpleNamespace(ledger_id=e.planning.configuration["ledger_id"])
        changed = deepcopy(row)
        changed["record"]["budget_allowance_id"] = "unrelated-allowance"
        with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
            limits(c, changed, budget)
        changed = deepcopy(row)
        changed["record"]["configuration"]["calls"] = 100
        with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
            limits(c, changed, budget)
        # Understanding and planning may use different configured profiles.
        changed = deepcopy(row)
        changed["record"]["configuration"]["profile_revision_id"] = "planning-profile"
        assert limits(c, changed, budget) == (20, 1_000_000)
