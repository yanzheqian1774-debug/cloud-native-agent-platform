"""Actual BFF/source/adoption PG owners with Responses success receipt shape."""

# ruff: noqa: F401,F811 -- Reuse isolated database/session fixtures.
from dataclasses import replace

import pytest
from agent_console.draft_assistance import DraftResultKind, DraftScope
from agent_console.workbench_bff import PREFIX
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer
from test_understanding_adoption_source import select
from test_understanding_result_adoption import accepted_cleanup


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize("reaped", [True, False])
def test_actual_source_owner_accepts_only_completed_responses_cleanup(adopted, reaped):
    e = adopted
    select(e)
    owner = e.adoption_client.app.state.understanding_adoption
    transport = owner.routing.transport
    dispatch = transport.dispatch
    cleanup = {**accepted_cleanup(), "reaped": reaped}

    def observed(**kwargs):
        return replace(
            dispatch(**kwargs),
            result_kind=DraftResultKind.NEEDS_DATA,
            clarification_question=None,
            data_needs=["请确认资料中的适用范围。"],
            local_cleanup=cleanup,
        )

    transport.dispatch = observed
    path, actual = answer(e)
    raw_before = e.draft.repository.get(
        DraftScope.from_context(e.context), actual["invocationId"]
    )
    assert raw_before.local_cleanup == cleanup
    reservations = len(e.draft.budget.reservations)
    calls = len(e.calls)
    result = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert result.status_code == (200 if reaped else 409), result.text
    if reaped:
        read = e.adoption_client.get(PREFIX + path, params={"requestKey": "answer"})
        assert read.status_code == 200, read.text
        assert (
            read.json()["result"]["understanding"]["invocationId"]
            == actual["invocationId"]
        )
    else:
        assert (
            result.json()["reasonCode"] == "UNDERSTANDING_ADOPTION_RESULT_NOT_ADOPTABLE"
        )
    with e.repo.connection_scope() as c:
        assert c.execute(
            "SELECT count(*) n FROM draft_assistance.result_adoptions"
        ).fetchone()["n"] == int(reaped)
    assert (
        e.draft.repository.get(
            DraftScope.from_context(e.context), actual["invocationId"]
        )
        == raw_before
    )
    assert len(e.calls) == calls == 1
    assert len(e.draft.budget.reservations) == reservations
