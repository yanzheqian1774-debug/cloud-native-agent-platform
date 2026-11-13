"""Disposable PostgreSQL recovery checks; provider outcomes are fixtures only."""

from pathlib import Path

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_planning_recovery import (
    RecoveryRequest,
    migrate,
    prepare_observation,
    projection,
)
from agent_console.plan_suggestion_invocation import PlanningRequest
from psycopg.types.json import Jsonb
from test_conversation_planning_admission import (  # noqa: F401
    env,
    ordinary,
    pytestmark,
    setup,
)


def request(key):
    ref = dict(resource_id="ordinary-new-problem", revision_id="r1", digest="a" * 64)
    return PlanningRequest.model_validate(
        dict(
            target=dict(
                problem=ref,
                criteria={**ref, "resource_id": "criteria"},
                criterion_revision_ids=["criterion-1"],
                expected_problem_version=1,
            ),
            idempotency_key=key,
        )
    )


def prepare(e, req):
    return e.planning.prepare_record(
        e.reviewer,
        req,
        dict(
            request=req.model_dump(mode="json"),
            target=dict(
                invocation_id="inv:" + req.idempotency_key,
                suggestion_context_id="ctx:" + req.idempotency_key,
                request_revision=1,
                predecessor_invocation_id=None,
                input_commitment=req.idempotency_key,
                problem=req.target.model_dump(mode="json"),
            ),
        ),
    )


def make_unknown(e, original_request=None):
    migrate(e.planning)
    first = prepare(e, original_request or request("old"))
    with e.repo.connection_scope() as c:
        root = Path(__file__).parents[1] / "migrations"
        for name in (
            "0025_plan_suggestion.sql",
            "0026_plan_suggestion_invocation.sql",
            "0027_planning_provider_receipt.sql",
            "0046_private_conversation.sql",
        ):
            c.execute((root / name).read_text())
        c.execute(
            "INSERT INTO private_conversation.conversations(tenant_id,security_do"
            "main,conversation_id,owner_id,title,request_key,request_digest) VALU"
            "ES('s5-323-demo','isolated-real-demo','approved-conversation',%s,'fi"
            "xture','fixture','fixture')",
            (e.reviewer.principal_id,),
        )
        c.execute(
            "INSERT INTO workflow_planning.invocations VALUES('s5-323-demo','isol"
            "ated-real-demo','inv:old',%s,'old','fixture',%s)",
            (e.reviewer.principal_id, Jsonb(first["invocation"])),
        )
        c.execute(
            "INSERT INTO workflow_planning.invocation_results VALUES('s5-323-demo"
            "','isolated-real-demo','inv:old',%s)",
            (Jsonb(dict(technical_status="OUTCOME_UNKNOWN")),),
        )
        c.execute(
            "INSERT INTO workflow_planning.provider_receipts VALUES('s5-323-demo'"
            ",'isolated-real-demo','inv:old',%s)",
            (
                Jsonb(
                    dict(
                        deadline=dict(reaped=True, reason="CANCELLED"),
                        reservation_id="retained-reservation",
                    )
                ),
            ),
        )
        c.execute(
            "INSERT INTO draft_provider_budget.reservations VALUES "
            "('s5-323-demo','isolated-real-demo',%s,'retained-reservation','old-op',"
            "'inv:old',100,500,212992,%s,now())",
            (e.planning.configuration["ledger_id"], "f" * 64),
        )
    return e


@pytest.fixture
def unknown(ordinary):  # noqa: F811
    return make_unknown(ordinary)


def spec(**changes):
    return RecoveryRequest(
        **dict(
            conversation_id="approved-conversation",
            invocation_id="inv:old",
            idempotency_key="recover",
            **changes,
        )
    )


def test_fresh_key_denied_observation_pending_and_immutable_old(unknown):
    e = unknown
    with pytest.raises(AuthorityError, match="PLANNING_RECOVERY_REQUIRED"):
        prepare(e, request("bypass"))
    observed = prepare_observation(e.planning, e.reviewer, spec())
    assert prepare_observation(e.planning, e.reviewer, spec()) == observed
    assert (
        projection(e.planning, e.reviewer, observed["recovery_id"])["state"]
        == "OBSERVED"
    )
    pending = prepare(e, PlanningRequest.model_validate(observed["record"]["request"]))
    assert pending["admission"]["ready"] is False
    assert pending["admission"]["cumulative_call_cap"] == 20
    assert pending["admission"]["total_cost_cap_microusd"] == 1_000_000
    assert (
        projection(e.planning, e.reviewer, observed["recovery_id"])["state"]
        == "AUTHORIZATION_PENDING"
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT worst_case_cost_microusd FROM "
                "draft_provider_budget.reservations"
            ).fetchone()["worst_case_cost_microusd"]
            == 212992
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.invocations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT record FROM workflow_planning.invocation_results"
            ).fetchone()["record"]["technical_status"]
            == "OUTCOME_UNKNOWN"
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )


def test_other_conversation_and_second_key_cannot_recover(unknown):
    e = unknown
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        prepare_observation(
            e.planning,
            e.reviewer,
            spec().model_copy(update={"conversation_id": "other"}),
        )
    prepare_observation(e.planning, e.reviewer, spec())
    with pytest.raises(AuthorityError, match="ALREADY_BOUND"):
        prepare_observation(
            e.planning,
            e.reviewer,
            spec().model_copy(update={"idempotency_key": "second"}),
        )


def test_independent_signature_expiry_and_revocation_guards(unknown):
    from datetime import datetime, timedelta

    from agent_console.context_call_admission import ContextApproval, request_row
    from agent_console.conversation_planning_recovery import before_approve

    e = unknown
    observed = prepare_observation(e.planning, e.reviewer, spec())
    pending = prepare(e, PlanningRequest.model_validate(observed["record"]["request"]))
    identity = pending["admission"]["context_id"]
    with e.repo.connection_scope() as c:
        row = request_row(c, identity)
    expires = datetime.fromisoformat(observed["record"]["expires_at"])
    command = ContextApproval(
        request_digest=row["digest"],
        expires_at=expires,
        idempotency_key="independent-signature",
    )
    with pytest.raises(AuthorityError, match="SELF_APPROVAL_PROHIBITED"):
        e.planning.approve(e.reviewer, identity, command)
    # Exercise the new approval hook with exact evidence. The existing approval
    # owner independently verifies the administrator before entering this hook.
    with e.repo.connection_scope() as c:
        assert before_approve(e.planning, c, row, command.model_dump(mode="json"))
        with pytest.raises(AuthorityError, match="EXPIRY_EXTENSION_DENIED"):
            before_approve(
                e.planning,
                c,
                row,
                command.model_copy(
                    update={"expires_at": expires + timedelta(seconds=1)}
                ).model_dump(mode="json"),
            )
        old_context = c.execute(
            "SELECT context_id FROM authorization_admin.context_call_requests "
            "WHERE first_invocation_id='inv:old'"
        ).fetchone()["context_id"]
        c.execute(
            "INSERT INTO authorization_admin.context_call_revocations "
            "(admission_id,actor_id) SELECT admission_id,'operator:fixture' "
            "FROM authorization_admin.context_call_decisions WHERE context_id=%s",
            (old_context,),
        )
    with pytest.raises(AuthorityError, match="PREDECESSOR_REVOKED"):
        projection(e.planning, e.reviewer, observed["recovery_id"])
