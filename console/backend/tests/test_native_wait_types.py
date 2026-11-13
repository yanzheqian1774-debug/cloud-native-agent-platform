"""Checkpoint boundaries, not proof of the durable managed execution path."""

from datetime import UTC, datetime, timedelta

import pytest
from agent_console.native_wait_types import (
    ClaimObservation,
    ContinuationClaim,
    EffectReference,
    WaitCheckpoint,
    WaitIdentity,
)
from pydantic import ValidationError


def checkpoint(**changes):
    now = datetime(2026, 11, 14, tzinfo=UTC)
    values = dict(
        identity=WaitIdentity(
            namespace="n",
            security_domain="d",
            preparation_digest="a" * 64,
            workflow_run_id="run",
            task_id="task",
            attempt_id="attempt",
            command_id="command",
            skill_invocation_id="skill",
            principal_id="human",
            conversation_id="conversation",
        ),
        ordinal=0,
        root_key="skill:loop",
        root_digest="b" * 64,
        input_request_digest="c" * 64,
        question_key="skill:loop:0:INPUT",
        question_digest="d" * 64,
        worker_id="controlled-worker",
        startup_record_digest="e" * 64,
        executor_id="document",
        executor_revision="new",
        executor_configuration_digest="e" * 64,
        source_digest="f" * 64,
        model_profile_digest="1" * 64,
        scope_evidence_digest="2" * 64,
        completed_effects=(
            EffectReference(
                key="skill:loop:0:MODEL",
                request_digest="3" * 64,
                result_digest="4" * 64,
            ),
        ),
        remaining_active_milliseconds=45_000,
        maximum_decisions=8,
        created_at=now,
        human_expires_at=now + timedelta(hours=1),
        authority_expires_at=now + timedelta(hours=2),
    )
    values.update(changes)
    return WaitCheckpoint(**values)


def test_human_deadline_is_separate_from_remaining_active_time():
    value = checkpoint()
    assert (value.human_expires_at - value.created_at).total_seconds() == 3600
    assert value.remaining_active_milliseconds == 45_000
    assert value == WaitCheckpoint.model_validate_json(value.model_dump_json())
    assert len(value.digest) == 64


@pytest.mark.parametrize(
    "change",
    [
        {"remaining_active_milliseconds": 0},
        {"remaining_active_milliseconds": True},
        {"remaining_active_milliseconds": 600_001},
        {"maximum_decisions": 1},
        {"ordinal": True},
        {"created_at": datetime(2026, 11, 14)},
        {"human_expires_at": datetime(2026, 11, 14, tzinfo=UTC)},
        {"human_expires_at": datetime(2026, 11, 15, tzinfo=UTC)},
        {"question_key": "another:0:INPUT"},
        {"completed_effects": ()},
        {"root_digest": "not-a-digest"},
        {"unknown": "cannot become authority"},
    ],
)
def test_checkpoint_rejects_invalid_bounds(change):
    with pytest.raises(ValidationError):
        checkpoint(**change)


@pytest.mark.parametrize(
    "key",
    [
        "another:0:TOOL",
        "skill:loop:1:TOOL",
        "skill:loop:0:INPUT",
        "skill:loop:0:TOOL",
        "skill:loop:00:TOOL",
        "skill:loop:0:UNKNOWN",
    ],
)
def test_effect_references_cannot_add_other_or_future_work(key):
    ref = EffectReference(key=key, request_digest="3" * 64, result_digest="4" * 64)
    with pytest.raises(ValidationError):
        checkpoint(completed_effects=(*checkpoint().completed_effects, ref))


def test_duplicate_receipt_rejected():
    effects = checkpoint().completed_effects
    with pytest.raises(ValidationError):
        checkpoint(completed_effects=effects + effects)


def test_duplicate_claim_is_observation_not_new_ownership():
    claim = ContinuationClaim(
        checkpoint_digest="1" * 64,
        answer_digest="2" * 64,
        fence="3" * 64,
        worker_id="w",
        startup_record_digest="4" * 64,
    )
    observation = ClaimObservation(newly_claimed=False, claim=claim)
    assert not observation.newly_claimed
    with pytest.raises(ValidationError):
        ContinuationClaim(**{**claim.model_dump(), "generation": 2})


def test_running_success_does_not_repeat_accepted_facts():
    from types import SimpleNamespace

    from agent_console.skill_invocation_domain import InvocationState
    from agent_console.skill_invocation_postgres import (
        PostgresSkillInvocationRepository,
    )

    repository = object.__new__(PostgresSkillInvocationRepository)
    request = SimpleNamespace(
        invocation_id="job", resource_use=SimpleNamespace(resource_use_id="use")
    )
    now = datetime.now(UTC)
    facts = repository._terminal_facts(
        request,
        InvocationState.SUCCEEDED,
        "result",
        "a" * 64,
        now,
        already_running=True,
    )
    uses = repository._terminal_resource_facts(
        request,
        InvocationState.SUCCEEDED,
        "result",
        {"evidenceDigest": "a" * 64, "evidenceId": "e"},
        now,
        already_running=True,
    )
    assert [f.kind.value for f in facts] == ["INVOCATION_SUCCEEDED"]
    assert [f.kind.value for f in uses] == ["SUCCEEDED"]
    legacy = repository._terminal_facts(
        request, InvocationState.SUCCEEDED, "result", "a" * 64, now
    )
    assert [f.kind.value for f in legacy] == [
        "INVOCATION_ACCEPTED",
        "INVOCATION_RUNNING",
        "INVOCATION_SUCCEEDED",
    ]


def test_typed_wait_generic_answer_cannot_use_legacy_scope_confirmation(monkeypatch):
    from types import SimpleNamespace as NS

    from agent_console.native_wait_runtime import NativeWaitRuntimeSession

    calls = []
    monkeypatch.setattr(
        "agent_console.native_scope_answer.record_bound_answer",
        lambda *args: calls.append(args),
    )
    session = object.__new__(NativeWaitRuntimeSession)
    session.runtime = NS(durable_wait=NS(typedQuestions=True))
    library = NS(confirmed_scope=None)
    frame = NS(
        observations=[
            {"kind": "USER_ANSWER", "question": "请确认生产环境", "answer": "对"}
        ]
    )
    session.restore_library(library, frame)
    assert calls == [] and library.confirmed_scope is None
    session.runtime.durable_wait.typedQuestions = False
    session.restore_library(library, frame)
    assert len(calls) == 1
