"""Isolated account/conversation/admission owners; no real model invocation."""

# ruff: noqa: F401, F811
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import request_row
from agent_console.conversation_experience_admission import (
    ConversationExperienceAdmission,
    begin_bound,
)
from agent_console.conversation_planning_admission import ConversationPlanningAdmission
from agent_console.draft_assistance import DraftAssistanceError
from test_context_call_admission import env
from test_conversation_experience_admission import configure, prepare, pytestmark
from test_local_accounts_postgres import setup


def successor(e, path, document):
    previous = e.admission.experience.policy_digest
    value = {
        **document,
        "schemaVersion": "f3-conversation-experience.v3",
        "predecessorSchemaVersion": document["schemaVersion"],
        "predecessorPolicyDigest": previous,
        "ownedConversationUnderstanding": True,
    }
    path.write_text(json.dumps(value))
    e.admission.experience = ConversationExperienceAdmission(
        path, e.admission.configuration
    )
    assert e.admission.experience.policy_digest == previous
    return value


def conversation(e, *, owner=None, author=None, archived=False):
    with e.repo.connection_scope() as c:
        for name in (
            "0046_private_conversation.sql",
            "0047_conversation_action_facts.sql",
        ):
            c.execute((Path(__file__).parents[1] / "migrations" / name).read_text())
        c.execute(
            "INSERT INTO private_conversation.conversations "
            "(tenant_id,security_domain,conversation_id,owner_id,title,"
            "request_key,request_digest) "
            "VALUES('s5-323-demo','isolated-real-demo','new-own',%s,'own','new','d')",
            (owner or e.reviewer.principal_id,),
        )
        c.execute(
            "INSERT INTO private_conversation.messages "
            "(tenant_id,security_domain,conversation_id,message_id,sequence,"
            "author_id,content,disposition,request_key,request_digest) "
            "VALUES('s5-323-demo','isolated-real-demo','new-own',"
            "'actual-user-message',1,%s,'hello','GOAL_RECORDED','m','d')",
            (author or e.reviewer.principal_id,),
        )
        if archived:
            c.execute("UPDATE private_conversation.conversations SET archived_at=now()")


def test_owned_admission_preserves_original_budget_and_does_not_admit_business_work(
    env, tmp_path
):
    e = env
    invocation, owner, path, document = configure(e, tmp_path)
    conversation(e)
    value = successor(e, path, document)
    assert prepare(e, invocation, owner, "new-own")
    from test_recovery_bound_understanding import result

    result(e, invocation.invocation_id, state="SUCCEEDED", resultKind="DRAFT_READY")
    with e.repo.connection_scope() as c:
        row = request_row(c, invocation.context_id)
        assert row["record"]["scenario"] == "GENERAL_CONVERSATION_UNDERSTANDING"
        assert row["record"]["synthetic_only"] is False
        assert row["record"]["configuration"] == document["configuration"]
        assert (
            row["record"]["owned_understanding_policy_digest"]
            == e.admission.experience.understanding_policy_digest
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
        from agent_console.context_call_admission import bind_problem

        assert bind_problem(
            c,
            e.reviewer,
            {"revision": {"business_problem_id": "general-problem"}},
            invocation.invocation_id,
        )
        planner = ConversationPlanningAdmission(e.admission, e.admission.configuration)
        with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
            planner.require_source(e.admission, c, e.reviewer, "general-problem")
    assert e.admission.ready(e.reviewer, invocation)
    with e.repo.connection_scope() as c:
        c.execute("UPDATE private_conversation.conversations SET archived_at=now()")
    with pytest.raises(AuthorityError, match="CONVERSATION_BINDING_REQUIRED"):
        e.admission.ready(e.reviewer, invocation)
    assert json.loads(path.read_text()) == value


def test_exact_old_admission_stays_valid_under_explicit_successor(env, tmp_path):
    e = env
    invocation, owner, path, document = configure(e, tmp_path)
    prepare(e, invocation, owner)
    with e.repo.connection_scope() as c:
        before = request_row(c, invocation.context_id)
    successor(e, path, document)
    assert e.admission.ready(e.reviewer, invocation)
    assert prepare(e, invocation, owner)
    with e.repo.connection_scope() as c:
        assert request_row(c, invocation.context_id) == before


@pytest.mark.parametrize(
    "bad", ["owner", "author", "archived", "message", "missing_declaration"]
)
def test_preflight_rejects_before_claim_and_never_substitutes_identity(
    env, tmp_path, bad
):
    e = env
    _, _, path, document = configure(e, tmp_path)
    conversation(
        e,
        owner="another" if bad == "owner" else None,
        author="another" if bad == "author" else None,
        archived=bad == "archived",
    )
    if bad != "missing_declaration":
        successor(e, path, document)
    calls = []
    service = NS(
        authorization=NS(context_admission=e.admission),
        begin=lambda *a, **k: calls.append(k),
    )
    with pytest.raises(DraftAssistanceError, match="CONVERSATION_BINDING_REQUIRED"):
        begin_bound(
            service,
            e.reviewer,
            conversation="new-own",
            message_id="wrong" if bad == "message" else "actual-user-message",
            key="fresh",
            content="hello",
        )
    assert calls == []


def test_successor_must_preserve_exact_predecessor(env, tmp_path):
    e = env
    _, _, path, document = configure(e, tmp_path)
    successor(e, path, document)
    value = json.loads(path.read_text())
    value["authorizationDigest"] = "b" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(AuthorityError, match="PREDECESSOR_MISMATCH"):
        ConversationExperienceAdmission(path, e.admission.configuration)


def test_owned_successor_reuses_v2_allowance_and_deadline(env, tmp_path):
    from test_conversation_experience_admission import configure_successor

    e = env
    invocation, owner, path, allowance = configure_successor(e, tmp_path)
    document = json.loads(path.read_text())
    conversation(e)
    successor(e, path, document)
    assert prepare(e, invocation, owner, "new-own")
    with e.repo.connection_scope() as c:
        row = request_row(c, invocation.context_id)
        assert row["record"]["budget_allowance_id"] == allowance["allowanceId"]
        assert datetime.fromisoformat(
            row["record"]["ledger_expires_at"]
        ) == datetime.fromisoformat(allowance["expiresAt"])
        assert row["record"]["configuration"] == document["configuration"]
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
