# ruff: noqa: F811, E501 -- Original random-database fixtures and exact SQL.
"""Real WAIT/dispatch rows, controlled independent delegation port (not BFF)."""

from datetime import UTC, datetime

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_preparation_postgres import PreparedExecutionStore
from agent_console.fixed_question_types import QuestionIdentity, QuestionPresentation
from agent_console.native_wait_owner import NativeWaitOwner
from agent_runtime.native_loop import digest
from test_native_wait_owner import repository, stop, waiting  # noqa: F401


def presentation(e):
    cp, i = e.cp, e.cp.identity
    with e.repo.pool.connection() as c:
        p, _ = PreparedExecutionStore(c).read(
            i.namespace, i.security_domain, i.workflow_run_id
        )
    identity = QuestionIdentity(
        tenantId=i.namespace,
        securityDomain=i.security_domain,
        conversationId=i.conversation_id,
        bindingDigest="1" * 64,
        work={
            "resource_id": "controlled-work",
            "revision_id": "r1",
            "digest": "2" * 64,
        },
        eventId="controlled-event",
        receiptDigest="3" * 64,
        preparationDigest=i.preparation_digest,
        runId=i.workflow_run_id,
        taskId=i.task_id,
        attemptId=i.attempt_id,
        commandId=i.command_id,
        invocationId=i.skill_invocation_id,
        questionKey=cp.question_key,
        questionDigest=cp.question_digest,
        checkpointDigest=cp.digest,
        sourceSnapshot=p.source_snapshot,
        executionSubject=i.principal_id,
        serviceCredentialId="fixture-credential",
        generation=1,
        recoveryEpoch=1,
    )
    from agent_console.fixed_question_context import snapshot

    return QuestionPresentation(
        presentationId="controlled-presentation",
        identity=identity,
        actorId="human:original-owner",
        commandId="controlled-present",
        requestDigest="4" * 64,
        policyDigest="5" * 64,
        issuerId="service:issuer",
        grantRequestId="controlled-request",
        grantDecisionId="controlled-decision",
        grantId="controlled-grant",
        focusLinkId="controlled-focus",
        currentQuestionToken=snapshot(
            "controlled-presentation", identity, e.question, ""
        )["currentQuestionToken"],
        question=e.question,
        createdAt=datetime.now(UTC),
        expiresAt=cp.human_expires_at,
    )


def answer(p):
    return dict(
        kind="NATIVE_DELEGATED_ANSWER",
        answer="production",
        conversationId=p.identity.conversationId,
        actorId=p.actorId,
        executionSubject=p.identity.executionSubject,
        questionDigest=p.identity.questionDigest,
        presentationDigest=p.digest,
    )


@pytest.mark.parametrize("waiting", ["service"], indirect=True)
def test_separate_actor_one_original_wait_and_continuation(waiting):
    e = waiting
    p = presentation(e)
    allowed = True
    calls = []

    def verify(c, cp, value):
        calls.append((c, cp.digest, value.actorId))
        if not allowed:
            raise AuthorityError("CONTROLLED_QUESTION_ANSWER_REVOKED")
        return p

    owner = NativeWaitOwner(
        e.owner.authorize, e.owner.skill_repository, authorize_delegated_answer=verify
    )
    with e.repo.pool.connection() as c, c.transaction():
        assert owner.accept_delegated_answer(c, e.cp, answer(p)) == {
            "accepted": True,
            "replayed": False,
        }
        assert owner.accept_delegated_answer(c, e.cp, answer(p)) == {
            "accepted": True,
            "replayed": True,
        }
        assert all(item[0] is c for item in calls)
        saved = c.execute(
            "SELECT result FROM skill_invocation.native_loop_records WHERE record_key=%s",
            (e.cp.question_key + ":answer",),
        ).fetchone()["result"]
        assert saved["actorId"] == "human:original-owner"
        assert saved["executionSubject"] == "service:fixed-question-test"
        assert "principal" not in saved
        owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        frame = owner.read_continuation(c, e.cp, e.original_root)
        assert frame is not None
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_loop_records WHERE record_key=%s",
                (e.cp.question_key + ":answer",),
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute("SELECT count(*) n FROM skill_invocation.invocations").fetchone()[
                "n"
            ]
            == 1
        )
        assert (
            c.execute(
                "SELECT principal_id FROM execution_authority.native_dispatch_commands"
            ).fetchone()["principal_id"]
            == p.identity.executionSubject
        )
    allowed = False
    with (
        e.repo.pool.connection() as c,
        c.transaction(),
        pytest.raises(AuthorityError, match="QUESTION_ANSWER_REVOKED"),
    ):
        owner.accept_delegated_answer(c, e.cp, answer(p))


@pytest.mark.parametrize("waiting", ["service"], indirect=True)
def test_default_off_and_wrong_actor_question_checkpoint_are_no_writes(waiting):
    e = waiting
    p = presentation(e)
    owner = NativeWaitOwner(
        e.owner.authorize,
        e.owner.skill_repository,
        authorize_delegated_answer=lambda *_: p,
    )
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(AuthorityError, match="DELEGATION_NOT_ENABLED"):
            e.owner.accept_delegated_answer(c, e.cp, answer(p))
        for changed in (
            {"actorId": "human:other"},
            {"questionDigest": "9" * 64},
            {"executionSubject": "service:other"},
            {"presentationDigest": "9" * 64},
            {"principal": p.identity.executionSubject},
        ):
            with pytest.raises(AuthorityError, match="DELEGATED_ANSWER_INVALID"):
                owner.accept_delegated_answer(c, e.cp, {**answer(p), **changed})
        tampered = e.cp.model_copy(update={"remaining_active_milliseconds": 600000})
        with pytest.raises(AuthorityError, match="QUESTION_NOT_CURRENT"):
            owner.accept_delegated_answer(c, tampered, answer(p))
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_loop_records WHERE record_key=%s",
                (e.cp.question_key + ":answer",),
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT state FROM skill_invocation.native_wait_heads"
            ).fetchone()["state"]
            == "QUIESCING"
        )
        assert digest(e.question) == e.cp.question_digest
