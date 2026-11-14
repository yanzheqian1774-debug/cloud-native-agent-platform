"""Controlled owner ports; exercise the actual relation reader, no model calls."""

from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from agent_console import conversation_relation_reader as module
from agent_console.authority_contracts import AuthorityError
from agent_console.private_conversation import ConversationError


def setup_reader(monkeypatch, state, *, cancellation=None, denied=False, missing=False):
    problem = dict(business_problem_id="problem", revision_id="r1", digest="a" * 64)
    exact = dict(resource_id="problem", revision_id="r1", digest="a" * 64)
    journal = {
        "version": 29,
        "state": {
            "phase": "RUNNING",
            "key": "journey",
            "problem": problem,
            "execution": "b" * 64,
            "confirmation": {"execution_status": "NOT_STARTED"},
        },
    }
    original = deepcopy(journal)
    monkeypatch.setattr(module, "_journal", lambda *a: deepcopy(journal))

    class Connection:
        def execute(self, sql, params):
            if "private_conversation.links" in sql:
                rows = [
                    {
                        "target": dict(
                            problemId="problem", revisionId="r1", problemDigest="a" * 64
                        )
                    }
                ]
            elif "context_call_objects" in sql:
                rows = [{"subject_id": "human:test", "conversation_id": "chat"}]
            elif "prepared_run_progress" in sql:
                rows = (
                    []
                    if missing
                    else [
                        {
                            "record": {
                                "state": state,
                                "cancellation_request_id": cancellation,
                            }
                        }
                    ]
                )
            else:
                raise AssertionError(sql)
            return NS(fetchall=lambda: rows, fetchone=lambda: rows[0] if rows else None)

    c = Connection()
    records = NS(scope=lambda ctx: ("tenant", "domain"), owned=lambda *a: None)
    owner = NS(
        read_problem=lambda *a, **kw: {
            "problem": {"current_revision_id": "r1"},
            "revisions": [{**problem, "title": "original", "description": "scope"}],
        }
    )
    p = NS(
        run_id="run", semantics=NS(target=NS(problem=NS(model_dump=lambda **kw: exact)))
    )
    import agent_console.native_interaction as native
    import agent_console.prepared_execution_application as app
    import agent_console.workbench_prepared_execution as prepared

    monkeypatch.setattr(prepared, "candidate", lambda *a: p)
    monkeypatch.setattr(app, "PreparedExecutionApplication", lambda *a: None)
    question = dict(
        question="confirm?",
        answer=None,
        expired=False,
        invocationId="inv",
        questionKey="q",
        questionDigest="d" * 64,
        expiresAt="2099-01-01T00:00:00Z",
    )
    monkeypatch.setattr(native, "progress", lambda *a: {"questions": [question]})
    calls = []

    class Authorizer:
        def execute(self, context, grants, **kw):
            calls.append(kw["operation"])
            if denied and kw["operation"] == "READ_NATIVE_PROGRESS":
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return kw["handler"](NS(connection=c, authority=object()))

    read = module.reader(NS(state=NS()), Authorizer(), owner, NS(records=records))
    context = NS(
        principal_id="human:test",
        scope=NS(tenant_id="tenant", security_domain="domain"),
    )
    return (
        lambda message: read(context, "chat", message, None),
        journal,
        original,
        calls,
    )


@pytest.mark.parametrize(
    "state,expected",
    [
        ("SUCCEEDED", "DONE"),
        ("FAILED", "FAILED"),
        ("CANCELLED", "CANCELLED"),
        ("RECOVERY_REQUIRED", "RECOVERY_REQUIRED"),
        ("unknown-future", "UNKNOWN"),
    ],
)
def test_followup_context_uses_execution_owner_not_journal(
    monkeypatch, state, expected
):
    read, journal, original, calls = setup_reader(monkeypatch, state)
    for message in ("next-followup", "independent-message"):
        result = read(message)
        assert result["input"]["stage"] == expected
        assert result["target"] is None
        assert result["currentQuestionToken"] is None
        assert result["input"]["currentQuestion"] is None
    assert journal == original
    assert calls == ["READ_CONVERSATION_ROUTING_CONTEXT", "READ_NATIVE_PROGRESS"] * 2


def test_running_question_remains_exact(monkeypatch):
    read, _, _, _ = setup_reader(monkeypatch, "RUNNING")
    result = read("answer")
    assert result["input"]["stage"] == "RUNNING"
    assert result["target"]["runId"] == "run"
    assert result["target"]["questionKey"] == "q"
    assert result["currentQuestionToken"]


def test_cancellation_never_becomes_answer_target(monkeypatch):
    read, _, _, _ = setup_reader(monkeypatch, "RUNNING", cancellation="cancel")
    result = read("answer")
    assert result["input"]["stage"] == "CANCEL_REQUESTED"
    assert result["target"] is None


@pytest.mark.parametrize("option", ["denied", "missing"])
def test_unreadable_progress_never_claims_complete(monkeypatch, option):
    read, journal, original, _ = setup_reader(
        monkeypatch, "SUCCEEDED", **{option: True}
    )
    with pytest.raises(ConversationError):
        read("followup")
    assert journal == original
