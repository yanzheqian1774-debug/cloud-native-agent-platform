"""Actual link_problem CAS must preserve the exact admitted result and lineage."""

# ruff: noqa: F401,F811 -- Existing disposable PostgreSQL owner fixtures.
import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import DraftScope
from agent_console.plan_suggestion_domain import ExactReference
from owned_business_consumer_support import configure_scope, prepare_source
from owned_business_planning_support import activate_created, planning_application
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted

pytestmark = [pgmark, pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)]


def target(e):
    r = e.created["revision"]
    return ExactReference(
        resource_id=r["business_problem_id"],
        revision_id=r["revision_id"],
        digest=r["digest"],
    )


def original(e):
    return e.draft.repository.get(
        DraftScope.from_context(e.context), e.business_result["invocationId"]
    )


def link(e, **overrides):
    r = e.created["revision"]
    return e.draft.link_problem(
        e.context,
        e.business_result["invocationId"],
        **{
            "problem_id": r["business_problem_id"],
            "problem_revision_id": r["revision_id"],
            "problem_digest": r["digest"],
            **overrides,
        },
    ).invocation


def facts(e):
    with e.repo.connection_scope() as c:
        return (
            c.execute(
                "SELECT record FROM authorization_admin.owned_business_admissions"
            ).fetchall(),
            c.execute("SELECT * FROM draft_provider_budget.reservations").fetchall(),
        )


@pytest.mark.parametrize(
    "owned_ready",
    [
        dict(mode=mode, prepare_source=prepare_source, configure_scope=configure_scope)
        for mode in (None, "SOURCE_SUCCESSOR")
    ],
    indirect=True,
)
def test_formal_link_allows_criteria_activation_and_planning_read(owned_created):
    e = owned_created
    before, calls, old = facts(e), len(e.calls), original(e)
    linked = link(e)
    assert linked.aggregate_version == old.aggregate_version + 1
    assert link(e) == linked
    with e.repo.connection_scope() as c:
        first = e.business_owner.work(c, e.context, target(e))
        e.business_owner.admit(c, e.context, linked.invocation_id)
        assert e.business_owner.work(c, e.context, target(e)) == first
    activate_created(e)
    assert e.business_detail["problem"]["current_state"] == "ACTIVE"
    assert e.business_detail["problem"]["aggregate_version"] > 1
    _, _, current = planning_application(e)
    assert current["target"]["problem"]["resource_id"] == target(e).resource_id
    with e.repo.connection_scope() as c:
        bound = e.business_planning.conversation_experience.require_source(
            e.business_planning, c, e.context, target(e).resource_id
        )[0]
        assert bound["understanding_input_source"] == e.business_result["inputSource"]
    assert facts(e) == before and len(e.calls) == calls
    assert original(e) == linked


@pytest.mark.parametrize(
    "change", ["problem", "revision", "digest", "extra_version", "measurement"]
)
def test_non_link_successors_are_not_adopted_as_same_result(owned_created, change):
    e = owned_created
    before = facts(e)
    if change == "measurement":
        r = e.created["revision"]
        e.draft._replace(
            original(e),
            problem_id=r["business_problem_id"],
            problem_revision_id=r["revision_id"],
            problem_digest=r["digest"],
            measurement={"unexpected": True},
        )
    elif change == "extra_version":
        e.draft._replace(link(e))
    else:
        key = {
            "problem": "problem_id",
            "revision": "problem_revision_id",
            "digest": "problem_digest",
        }[change]
        link(e, **{key: "different"})
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="RESULT_CHANGED"),
    ):
        e.business_owner.work(c, e.context, target(e))
    with (
        e.repo.connection_scope() as c,
        pytest.raises(AuthorityError, match="RESULT_CHANGED"),
    ):
        e.business_owner.admit(c, e.context, e.business_result["invocationId"])
    assert facts(e) == before
