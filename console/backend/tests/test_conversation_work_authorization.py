"""Isolated policy/grant owner integration; no live model or business execution."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.business_problem_authorization import problem_resource
from agent_console.conversation_planning_admission import ConversationPlanningAdmission
from agent_console.conversation_work_authorization import ConversationWorkAuthorization
from agent_console.draft_assistance_authorization import model_grant
from test_context_call_admission import env  # noqa: F401
from test_conversation_experience_admission import pytestmark  # noqa: F401
from test_conversation_planning_admission import ordinary  # noqa: F401
from test_local_accounts_postgres import setup  # noqa: F401


@pytest.fixture
def work(ordinary):  # noqa: F811
    e = ordinary
    e.planning.configuration = {
        **e.planning.configuration,
        "model_target": model_grant(e.source).exact_resource,
    }
    e.planning.conversation_experience = ConversationPlanningAdmission(
        e.admission, e.planning.configuration
    )
    e.work = ConversationWorkAuthorization(e.planning)
    e.expected = {
        ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource()),
        ExactGrant(
            "BUSINESS_PROBLEM", "READ", problem_resource("ordinary-new-problem")
        ),
        ExactGrant(
            "BUSINESS_PROBLEM", "TRANSITION", problem_resource("ordinary-new-problem")
        ),
        ExactGrant("PLAN", "PREPARE", "plan:prepare:ordinary-new-problem"),
        ExactGrant(
            "MODEL_GOVERNANCE", "INVOKE_MODEL", e.planning.configuration["model_target"]
        ),
    }
    grants = e.work.grants
    generation = replace(
        grants.generation,
        requestability=tuple(
            RequestabilityRule(g.owner, g.action, g.exact_resource, e.work._purpose(g))
            for g in e.expected
        ),
    )
    grants._generation_provider = lambda: generation
    # Explicit target-validator port fixture; database grants/identity/lineage are real.
    grants.target_validator = SimpleNamespace(
        is_known_exact_target=lambda ctx, g, **kw: g in e.expected
    )
    e.create = {
        "ownerId": e.reviewer.principal_id,
        "draftInvocationId": e.source.invocation_id,
    }
    e.created = {"revision": {"business_problem_id": "ordinary-new-problem"}}
    return e


def decisions(e):
    with e.repo.connection_scope() as c:
        return c.execute(
            "SELECT * FROM authorization_admin.grant_decisions ORDER BY decision_id"
        ).fetchall()


def test_create_and_exact_planning_permissions_are_durable_and_idempotent(work):
    e = work
    expected = (ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource()),)
    e.work.before(e.reviewer, "CREATE_PROBLEM", e.create, {}, expected)
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    first = decisions(e)
    assert len(first) == 4
    assert {r["basis_type"] for r in first} == {"POLICY"}
    assert {r["issuer_principal_id"] for r in first} == {
        "policy:f3-conversation-experience"
    }
    e.work.before(e.reviewer, "CREATE_PROBLEM", e.create, {}, expected)
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    assert decisions(e) == first
    with e.repo.connection_scope() as c:
        assert all(
            e.work.grants.authorization.has_current_grants(
                e.reviewer,
                tuple(
                    e.expected
                    - {
                        ExactGrant(
                            "BUSINESS_PROBLEM",
                            "TRANSITION",
                            problem_resource("ordinary-new-problem"),
                        )
                    }
                ),
                now=datetime.now(UTC),
                generation=e.work.grants.generation.generation,
                recovery_epoch=e.work.grants.recovery_epoch,
                connection=c,
                configure_transaction=False,
            )
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


def test_false_draft_other_owner_and_unrelated_resource_cannot_obtain_grants(work):
    e = work
    expected = (ExactGrant("BUSINESS_PROBLEM", "CREATE", problem_resource()),)
    for payload, reason in [
        ({**e.create, "draftInvocationId": "not-a-draft"}, "DRAFT_INVALID"),
        ({**e.create, "ownerId": e.business.principal_id}, "SCOPE_DENIED"),
    ]:
        with pytest.raises(AuthorityError, match=reason):
            e.work.before(e.reviewer, "CREATE_PROBLEM", payload, {}, expected)
    with pytest.raises(AuthorityError, match="EXACT_TARGET_DENIED"):
        e.work.before(
            e.reviewer,
            "CREATE_PROBLEM",
            e.create,
            {},
            (ExactGrant("EMPLOYEE", "CREATE", "employee:collection"),),
        )
    with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
        e.work.after(
            e.reviewer,
            "CREATE_PROBLEM",
            e.create,
            {"revision": {"business_problem_id": "unrelated"}},
        )
    assert decisions(e) == []


def test_policy_change_and_unrelated_operations_do_not_create_permissions(work):
    e = work
    e.work.before(e.business, "CREATE_PROBLEM", e.create, {}, ())
    e.work.before(e.reviewer, "READ_PROBLEM", {}, {"problem_id": "unrelated"}, ())
    e.work.before(
        e.reviewer, "CREATE_PROBLEM", {"ownerId": e.reviewer.principal_id}, {}, ()
    )
    assert decisions(e) == []
    original = e.policy_path.read_text()
    e.policy_path.write_text(original.replace("a" * 64, "b" * 64))
    with pytest.raises(AuthorityError, match="POLICY_CHANGED"):
        e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    assert decisions(e) == []


def test_transition_does_not_regrant_a_revoked_read_permission(work):
    from agent_console.grant_administration_application import GrantRevocationCommand

    e = work
    e.work.after(e.reviewer, "CREATE_PROBLEM", e.create, e.created)
    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE o"
            "wner='BUSINESS_PROBLEM' AND action='READ'"
        ).fetchone()
    e.work.grants.revoke_grant(
        e.reviewer,
        GrantRevocationCommand(
            grant["grant_id"], "TEST_WITHDRAWAL", "withdraw-read", surrender=True
        ),
    )
    e.work.before(
        e.reviewer,
        "TRANSITION_PROBLEM",
        {"toState": "ACTIVE"},
        {"problem_id": "ordinary-new-problem"},
        (
            ExactGrant(
                "BUSINESS_PROBLEM", "READ", problem_resource("ordinary-new-problem")
            ),
            ExactGrant(
                "BUSINESS_PROBLEM",
                "TRANSITION",
                problem_resource("ordinary-new-problem"),
            ),
        ),
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM authorization_admin.grants WH"
                "ERE owner='BUSINESS_PROBLEM' AND action='READ'"
            ).fetchone()["n"]
            == 1
        )
        assert not e.work.grants.authorization.has_current_grants(
            e.reviewer,
            (
                ExactGrant(
                    "BUSINESS_PROBLEM", "READ", problem_resource("ordinary-new-problem")
                ),
            ),
            now=datetime.now(UTC),
            generation=e.work.grants.generation.generation,
            recovery_epoch=e.work.grants.recovery_epoch,
            connection=c,
            configure_transaction=False,
        )[0]


def test_criteria_permissions_require_same_original_problem_context(work):
    e = work
    from agent_console.business_problem_authorization import (
        criteria_resource,
        criterion_resource,
        criterion_revision_resource,
    )
    from agent_console.workbench_business_problem import (
        _criteria_set_write,
        _criterion_write,
    )

    additions = {
        *(
            ExactGrant("SUCCESS_CRITERION", a, criterion_resource())
            for a in ("CREATE", "READ")
        ),
        *(
            ExactGrant(
                "SUCCESS_CRITERIA_SET", a, criteria_resource("ordinary-new-problem")
            )
            for a in ("CREATE", "READ")
        ),
        ExactGrant(
            "SUCCESS_CRITERION",
            "READ",
            criterion_revision_resource("new-criterion-revision"),
        ),
    }
    e.expected |= additions
    generation = replace(
        e.work.grants.generation,
        requestability=tuple(
            RequestabilityRule(g.owner, g.action, g.exact_resource, e.work._purpose(g))
            for g in e.expected
        ),
    )
    e.work.grants._generation_provider = lambda: generation
    payload = {"problemId": "ordinary-new-problem"}
    e.work.before(
        e.reviewer,
        "WRITE_CRITERION",
        payload,
        {},
        _criterion_write(e.reviewer, {}, payload, {}),
    )
    path = {"problem_id": "ordinary-new-problem"}
    payload = {"orderedCriterionRevisionIds": ["new-criterion-revision"]}
    expected = _criteria_set_write(e.reviewer, path, payload, {})
    before = decisions(e)
    with pytest.raises(AuthorityError, match="CRITERION_TARGET_DENIED"):
        e.work.before(e.reviewer, "WRITE_CRITERIA_SET", payload, path, expected)
    assert decisions(e) == before
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO authorization_admin.context_call_objects VALUES "
            "('s5-323-demo','isolated-real-demo','SUCCESS_CRITERION',%s,%s,%s)",
            ("new-criterion-revision", e.source.context_id, e.source.invocation_id),
        )
    e.work.before(e.reviewer, "WRITE_CRITERIA_SET", payload, path, expected)
    assert len(decisions(e)) == len(before) + 3
    e.work.before(e.reviewer, "WRITE_CRITERIA_SET", payload, path, expected)
    assert len(decisions(e)) == len(before) + 3


def test_concurrent_tabs_share_the_same_exact_permission_decisions(work):
    from concurrent.futures import ThreadPoolExecutor

    e = work
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                e.work.after, e.reviewer, "CREATE_PROBLEM", e.create, e.created
            )
            for _ in range(2)
        ]
        for future in futures:
            future.result(timeout=60)
    assert len(decisions(e)) == 3
