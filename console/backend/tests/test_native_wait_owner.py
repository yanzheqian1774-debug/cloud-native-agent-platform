# ruff: noqa: F811 -- Reuse disposable random-database owner fixture.
"""Real owner rows; controlled executor/model/authorization, not live acceptance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.execution_domain import ScopeIdentity
from agent_console.native_loop_journal import NativeLoopJournal
from agent_console.native_loop_runtime import COMMAND
from agent_console.native_wait_owner import NativeWaitOwner
from agent_console.native_wait_store import NativeWaitStore
from agent_console.native_wait_types import (
    EffectReference,
    StopObservation,
    WaitCheckpoint,
    WaitIdentity,
)
from agent_console.ontology_execution import parse_preparation
from agent_console.prepared_execution_lineage import prepared_attempt
from agent_console.skill_invocation_postgres import PostgresSkillInvocationRepository
from agent_console.synthetic_cost_skill import SyntheticCostSkillExecutor
from agent_runtime.native_loop import digest
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_native_pipeline import (
    test_six_task_managed_skill_pipeline_restart_readback_and_no_redispatch as pipeline,
)


class CheckpointSeeded(BaseException):
    """Stop the test driver after committed wait, not a production wait signal."""


@pytest.fixture
def waiting(repository, tmp_path, monkeypatch, request):
    result = SimpleNamespace(denied=False)
    typed_exit = getattr(request, "param", None) == "typed_exit"
    original = PostgresSkillInvocationRepository.prepare_dispatch

    def captured(repo, *args, **kwargs):
        result.skills = repo
        result.request, result.inputs = args[:2]
        return original(repo, *args, **kwargs)

    monkeypatch.setattr(PostgresSkillInvocationRepository, "prepare_dispatch", captured)

    def controlled_executor(_self, invocation_id, _operation, _inputs, _timeout):
        command = COMMAND.get()
        with repository.pool.connection() as c, c.transaction():
            row = prepared_attempt(c, command.scope, command.attempt_id)
            p = parse_preparation(row["preparation"])
            invocation = c.execute(
                "SELECT * FROM skill_invocation.invocations "
                "WHERE skill_invocation_id=%s",
                (invocation_id,),
            ).fetchone()
            c.execute(
                (
                    Path(__file__).parents[1] / "migrations/0050_native_loop.sql"
                ).read_text()
            )
            NativeWaitStore.migrate(c)
        journal = NativeLoopJournal(repository.pool, command.scope, invocation_id)
        root = invocation_id + ":loop"
        action = {"action": "CLARIFY", "question": "Which authorized scope?"}
        from agent_runtime.native_loop import Limits

        original_root = {
            "identity": root,
            "goal": "controlled review",
            "criteria": ["evidence"],
            "context": {},
            "tools": [],
            "limits": vars(Limits()),
        }
        model_request = {**original_root, "observations": [], "remainingDecisions": 8}
        journal.claim(root, digest(original_root))
        journal.claim(root + ":0:MODEL", digest(model_request))
        journal.finish(root + ":0:MODEL", digest(model_request), action)
        now = datetime.now(UTC)
        identity = WaitIdentity(
            namespace=p.namespace,
            security_domain=p.security_domain,
            preparation_digest=p.digest,
            workflow_run_id=p.run_id,
            task_id=row["task_id"],
            attempt_id=str(command.attempt_id),
            command_id=str(command.command_id),
            skill_invocation_id=invocation_id,
            principal_id=command.principal_id,
            conversation_id="controlled-original-conversation",
        )
        question = {
            "kind": "NATIVE_QUESTION",
            "question": action["question"],
            "questionKey": root + ":0:INPUT",
            "principal": command.principal_id,
            "workflowRunId": p.run_id,
            "expiresAt": (now + timedelta(hours=1)).isoformat(),
        }
        cp = WaitCheckpoint(
            identity=identity,
            ordinal=0,
            root_key=root,
            root_digest=digest(original_root),
            input_request_digest=digest(action),
            question_key=question["questionKey"],
            question_digest=digest(question),
            worker_id="controlled-worker",
            startup_record_digest="e" * 64,
            executor_id=invocation["executor_id"],
            executor_revision=invocation["executor_revision"],
            executor_configuration_digest=invocation["executor_configuration_digest"],
            source_digest=p.source_snapshot.digest,
            model_profile_digest="c" * 64,
            scope_evidence_digest="d" * 64,
            completed_effects=(
                EffectReference(
                    key=root + ":0:MODEL",
                    request_digest=digest(model_request),
                    result_digest=digest(action),
                ),
            ),
            remaining_active_milliseconds=50_000,
            maximum_decisions=8,
            created_at=now,
            human_expires_at=now + timedelta(hours=1),
            authority_expires_at=now + timedelta(hours=2),
        )

        def authorize(_c, supplied, _operation):
            if result.denied or supplied.identity != identity:
                raise AuthorityError("TEST_EXACT_AUTHORITY_DENIED")

        owner = NativeWaitOwner(authorize, result.skills)
        with repository.pool.connection() as c, c.transaction():
            saved_wait = owner.register(c, cp, question)
        result.owner, result.cp, result.question = owner, cp, question
        result.original_root = original_root
        result.repo = repository
        if typed_exit:
            return saved_wait
        raise CheckpointSeeded()

    if typed_exit:
        from agent_operator.native_dispatch_reconciler import NativeDispatchWorker

        original_run = NativeDispatchWorker.run_claim

        def observe_exit(worker, claim):
            outcome = original_run(worker, claim)
            if outcome.state == "DRAIN_FOR_INPUT":
                result.dispatch_outcome = outcome
                result.task = worker.kubernetes.read(
                    claim, worker.task_name(claim.command)
                )
                raise CheckpointSeeded()
            return outcome

        monkeypatch.setattr(NativeDispatchWorker, "run_claim", observe_exit)
        monkeypatch.setattr(
            SyntheticCostSkillExecutor, "accepts_durable_wait", True, raising=False
        )
    monkeypatch.setattr(SyntheticCostSkillExecutor, "invoke", controlled_executor)
    with pytest.raises(CheckpointSeeded):
        pipeline(repository, tmp_path, "cost")
    return result


def answer(e):
    cp = e.cp
    return {
        "kind": "NATIVE_ANSWER",
        "answer": "production",
        "conversationId": cp.identity.conversation_id,
        "principal": cp.identity.principal_id,
        "questionDigest": cp.question_digest,
    }


def stop(e):
    cp = e.cp
    return StopObservation(
        checkpoint_digest=cp.digest,
        command_id=cp.identity.command_id,
        worker_id="controlled-worker",
        startup_record_digest="e" * 64,
        process_identity_digest="f" * 64,
        exit_receipt_digest="1" * 64,
        stopped_at=datetime.now(UTC),
    )


def test_real_owner_wait_answer_stop_and_single_claim(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        assert e.owner.accept_answer(c, e.cp, answer(e)) == {
            "accepted": True,
            "replayed": False,
        }
        with pytest.raises(AuthorityError, match="NOT_RESUMABLE"):
            e.owner.claim_continuation(
                c,
                e.cp,
                worker_id="w",
                startup_record_digest="2" * 64,
                verify_worker=lambda *_: None,
            )
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)

    def claim():
        with e.repo.pool.connection() as c, c.transaction():
            return e.owner.claim_continuation(
                c,
                e.cp,
                worker_id="w",
                startup_record_digest="2" * 64,
                verify_worker=lambda *_: None,
            )

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(lambda _: claim(), range(2)))
    assert sum(o.newly_claimed for o in outcomes) == 1
    assert outcomes[0].claim == outcomes[1].claim
    with e.repo.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_wait_continuations"
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
            c.execute("SELECT state FROM skill_invocation.projections").fetchone()[
                "state"
            ]
            == "RUNNING"
        )
        assert (
            c.execute(
                "SELECT result FROM skill_invocation.native_loop_records "
                "WHERE record_key=%s",
                (e.cp.root_key,),
            ).fetchone()["result"]
            is None
        )


def test_current_denial_preserves_checkpoint_without_answer(waiting):
    e = waiting
    e.denied = True
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(AuthorityError, match="TEST_EXACT_AUTHORITY_DENIED"):
            e.owner.accept_answer(c, e.cp, answer(e))
        assert (
            c.execute(
                "SELECT state FROM skill_invocation.native_wait_heads"
            ).fetchone()["state"]
            == "QUIESCING"
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_loop_records "
                "WHERE record_key LIKE '%:answer'"
            ).fetchone()["n"]
            == 0
        )


def test_answer_conflict_stale_identity_and_expiry_do_not_advance(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(AuthorityError, match="ANSWER_BINDING_INVALID"):
            e.owner.accept_answer(c, e.cp, {**answer(e), "conversationId": "other"})
        e.owner.accept_answer(c, e.cp, answer(e))
        assert e.owner.accept_answer(c, e.cp, answer(e))["replayed"]
        with pytest.raises(AuthorityError, match="NATIVE_ANSWER_CONFLICT"):
            e.owner.accept_answer(c, e.cp, {**answer(e), "answer": "different"})
    e.owner.clock = lambda: e.cp.authority_expires_at
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(AuthorityError, match="NATIVE_WAIT_AUTHORITY_EXPIRED"):
            e.owner.claim_continuation(
                c,
                e.cp,
                worker_id="w",
                startup_record_digest="2" * 64,
                verify_worker=lambda *_: None,
            )
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_wait_continuations"
            ).fetchone()["n"]
            == 0
        )


def test_wrong_fence_and_startup_cannot_claim_effect(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        receipt = e.owner.claim_continuation(
            c,
            e.cp,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
        store = NativeWaitStore(c, e.cp.identity)
        with pytest.raises(AuthorityError, match="CONTINUATION_FENCED"):
            store.require_fence(
                receipt.claim, worker_id="other", startup_record_digest="2" * 64
            )
        with pytest.raises(AuthorityError, match="CONTINUATION_FENCED"):
            store.require_fence(
                receipt.claim, worker_id="w", startup_record_digest="3" * 64
            )
        assert (
            store.require_fence(
                receipt.claim, worker_id="w", startup_record_digest="2" * 64
            )["state"]
            == "CONTINUATION_CLAIMED"
        )


def test_register_replay_keeps_original_skill_job_and_facts(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        before = c.execute("SELECT count(*) n FROM skill_invocation.facts").fetchone()[
            "n"
        ]
        e.owner.register(c, e.cp, e.question)
        assert (
            c.execute("SELECT count(*) n FROM skill_invocation.facts").fetchone()["n"]
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_wait_checkpoints"
            ).fetchone()["n"]
            == 1
        )
        NativeWaitStore.migrate(c)


def test_effect_fence_and_journal_claim_share_transaction(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        receipt = e.owner.claim_continuation(
            c,
            e.cp,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
    with e.repo.pool.connection() as c, c.transaction():
        assert e.owner.enter_continuation(
            c,
            e.cp,
            receipt.claim,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
        assert not e.owner.enter_continuation(
            c,
            e.cp,
            receipt.claim,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
    args = dict(
        worker_id="w",
        startup_record_digest="2" * 64,
        key=e.cp.root_key + ":1:MODEL",
        request_digest="3" * 64,
        verify_worker=lambda *_: None,
    )
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(RuntimeError), c.transaction():
            assert e.owner.claim_effect(c, e.cp, receipt.claim, **args)["newlyClaimed"]
            raise RuntimeError("test rollback before dispatch")
        assert NativeWaitStore(c, e.cp.identity).head()["state"] == "ADVANCING"
        assert e.owner.claim_effect(c, e.cp, receipt.claim, **args)["newlyClaimed"]
        assert not e.owner.claim_effect(c, e.cp, receipt.claim, **args)["newlyClaimed"]
        assert NativeWaitStore(c, e.cp.identity).head()["state"] == "ADVANCING"


def test_fence_cannot_be_borrowed_for_changed_checkpoint_limits(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        receipt = e.owner.claim_continuation(
            c,
            e.cp,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
        changed = e.cp.model_copy(
            update={"maximum_decisions": 32, "remaining_active_milliseconds": 600_000}
        )
        with pytest.raises(AuthorityError, match="NATIVE_WAIT_BINDING_CHANGED"):
            e.owner.claim_effect(
                c,
                changed,
                receipt.claim,
                worker_id="w",
                startup_record_digest="2" * 64,
                key=e.cp.root_key + ":30:MODEL",
                request_digest="3" * 64,
                verify_worker=lambda *_: None,
            )
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_loop_records "
                "WHERE record_key=%s",
                (e.cp.root_key + ":30:MODEL",),
            ).fetchone()["n"]
            == 0
        )
        assert (
            NativeWaitStore(c, e.cp.identity).head()["state"] == "CONTINUATION_CLAIMED"
        )


def test_owner_reconstructs_from_actual_saved_receipts_without_dispatch(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.accept_answer(c, e.cp, answer(e))
        before = c.execute(
            "SELECT count(*) n FROM skill_invocation.native_loop_records"
        ).fetchone()["n"]
        frame = e.owner.read_continuation(c, e.cp, e.original_root)
        assert frame.next_ordinal == 1
        assert frame.remaining_active_seconds == 50
        assert frame.observations[-1]["answer"] == answer(e)["answer"]
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_loop_records"
            ).fetchone()["n"]
            == before
        )
        with pytest.raises(AuthorityError, match="NATIVE_WAIT_BINDING_CHANGED"):
            e.owner.read_continuation(c, e.cp, {**e.original_root, "goal": "different"})


def test_second_question_atomically_consumes_only_current_fence(waiting):
    e = waiting
    worker = dict(
        worker_id="next-worker",
        startup_record_digest="8" * 64,
        verify_worker=lambda *_: None,
    )
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        claim = e.owner.claim_continuation(c, e.cp, **worker).claim
        assert e.owner.enter_continuation(c, e.cp, claim, **worker)
    action = {"action": "CLARIFY", "question": "Confirm remaining business choice?"}
    key = e.cp.root_key + ":1:MODEL"
    with e.repo.pool.connection() as c, c.transaction():
        assert e.owner.claim_effect(
            c, e.cp, claim, key=key, request_digest="a" * 64, **worker
        )["newlyClaimed"]
        e.owner.finish_effect(
            c, e.cp, claim, key=key, request_digest="a" * 64, result=action, **worker
        )
        input_row = c.execute(
            "SELECT request_digest,result FROM skill_invocation.native_loop_records "
            "WHERE record_key=%s",
            (e.cp.question_key,),
        ).fetchone()
        now = datetime.now(UTC)
        question = {
            "kind": "NATIVE_QUESTION",
            "question": action["question"],
            "questionKey": e.cp.root_key + ":1:INPUT",
            "principal": e.cp.identity.principal_id,
            "workflowRunId": e.cp.identity.workflow_run_id,
            "expiresAt": e.cp.human_expires_at.isoformat(),
        }
        cp = e.cp.model_copy(
            update={
                "ordinal": 1,
                "question_key": question["questionKey"],
                "question_digest": digest(question),
                "input_request_digest": digest(action),
                "worker_id": worker["worker_id"],
                "startup_record_digest": worker["startup_record_digest"],
                "created_at": now,
                "remaining_active_milliseconds": 40_000,
                "completed_effects": (
                    *e.cp.completed_effects,
                    EffectReference(
                        key=e.cp.question_key,
                        request_digest=input_row["request_digest"],
                        result_digest=digest(input_row["result"]),
                    ),
                    EffectReference(
                        key=key, request_digest="a" * 64, result_digest=digest(action)
                    ),
                ),
            }
        )
        cp = WaitCheckpoint.model_validate_json(cp.model_dump_json())
        # Corrupt next question fails without completing the previous wait.
        with pytest.raises(AuthorityError), c.transaction():
            e.owner.next_question(
                c, e.cp, claim, cp, {**question, "question": "changed"}, **worker
            )
        assert NativeWaitStore(c, e.cp.identity).head()["state"] == "ADVANCING"
        result = e.owner.next_question(c, e.cp, claim, cp, question, **worker)
        assert result.checkpoint_digest == cp.digest
        assert NativeWaitStore(c, e.cp.identity).head()["state"] == "QUIESCING"
        with pytest.raises(AuthorityError, match="FENCED"):
            e.owner.claim_effect(
                c,
                e.cp,
                claim,
                key=e.cp.root_key + ":2:MODEL",
                request_digest="e" * 64,
                **worker,
            )
        assert (
            c.execute("SELECT count(*) n FROM skill_invocation.invocations").fetchone()[
                "n"
            ]
            == 1
        )


def test_provider_receipt_and_settlement_share_current_fence(waiting):
    e = waiting
    worker = dict(
        worker_id="next-worker",
        startup_record_digest="8" * 64,
        verify_worker=lambda *_: None,
    )
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        claim = e.owner.claim_continuation(c, e.cp, **worker).claim
        e.owner.enter_continuation(c, e.cp, claim, **worker)
        for kind in ("receipt", "settlement"):
            key = e.cp.root_key + ":1:MODEL:" + kind
            assert e.owner.claim_effect(
                c, e.cp, claim, key=key, request_digest="a" * 64, **worker
            )["newlyClaimed"]
            e.owner.finish_effect(
                c,
                e.cp,
                claim,
                key=key,
                request_digest="a" * 64,
                result={"kind": kind},
                **worker,
            )
        for key in (
            e.cp.root_key + ":0:MODEL:receipt",
            e.cp.root_key + ":1:TOOL:receipt",
            e.cp.root_key + ":1:INPUT",
        ):
            with pytest.raises(AuthorityError, match="EFFECT_KEY_MISMATCH"):
                e.owner.claim_effect(
                    c, e.cp, claim, key=key, request_digest="a" * 64, **worker
                )


@pytest.mark.parametrize("waiting", ["typed_exit"], indirect=True)
def test_typed_wait_crosses_actual_skill_transport_and_worker_without_terminal(waiting):
    e = waiting
    assert e.dispatch_outcome.state == "DRAIN_FOR_INPUT"
    assert e.task["status"]["phase"] == "Running"
    with e.repo.pool.connection() as c:
        snapshot = e.skills._snapshot(
            c,
            ScopeIdentity(e.cp.identity.namespace, e.cp.identity.security_domain),
            e.cp.identity.skill_invocation_id,
        )
        assert snapshot.state == "RUNNING"
        assert (
            c.execute("SELECT count(*) n FROM skill_invocation.invocations").fetchone()[
                "n"
            ]
            == 1
        )
        assert c.execute(
            "SELECT state,terminal_record "
            "FROM execution_authority.native_dispatch_commands "
            "WHERE command_id=%s",
            (e.cp.identity.command_id,),
        ).fetchone() == {"state": "EFFECT_STARTED", "terminal_record": None}


def test_same_accepted_job_readback_does_not_create_dispatch_or_accept_changed_inputs(
    waiting,
):
    from agent_console.native_wait_skill import accepted_job
    from agent_console.skill_invocation_domain import SkillInvocationError

    e = waiting
    # Existing fixture closes its composition on return; only use the still-open
    # disposable repository connection with the original snapshot reader.
    repo = SimpleNamespace(pool=e.repo.pool, _snapshot=e.skills._snapshot)
    with e.repo.pool.connection() as c:
        before = c.execute("SELECT count(*) n FROM skill_invocation.facts").fetchone()[
            "n"
        ]
    snapshot, started = accepted_job(repo, e.request, e.inputs)
    assert snapshot.state == "RUNNING"
    assert started.tzinfo is not None
    with pytest.raises(SkillInvocationError, match="ORIGINAL_JOB_CHANGED"):
        accepted_job(repo, e.request, {**e.inputs, "different": True})
    with e.repo.pool.connection() as c:
        assert (
            c.execute("SELECT count(*) n FROM skill_invocation.facts").fetchone()["n"]
            == before
        )


def test_durable_wait_projection_is_exact_read_only_and_preserves_owner_state(
    waiting, monkeypatch
):
    from types import SimpleNamespace

    from agent_console.execution_preparation_postgres import PreparedExecutionStore
    from agent_console.native_wait_projection import read_waits

    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        p, _ = PreparedExecutionStore(c).read(
            e.cp.identity.namespace,
            e.cp.identity.security_domain,
            e.cp.identity.workflow_run_id,
        )
        before = c.execute(
            "SELECT count(*) n FROM skill_invocation.native_wait_observations"
        ).fetchone()["n"]
        view = read_waits(c, p)
        assert view == [
            dict(
                invocationId=e.cp.identity.skill_invocation_id,
                questionKey=e.cp.question_key,
                questionDigest=e.cp.question_digest,
                state="QUIESCING",
                humanExpiresAt=e.cp.human_expires_at.isoformat(),
                answerSaved=False,
                stopConfirmed=False,
            )
        ]
        assert (
            read_waits(
                c,
                SimpleNamespace(
                    namespace=p.namespace,
                    security_domain=p.security_domain,
                    run_id="other-run",
                ),
            )
            == []
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM skill_invocation.native_wait_observations"
            ).fetchone()["n"]
            == before
        )
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
        e.owner.accept_answer(c, e.cp, answer(e))
        projected = read_waits(c, p)[0]
        assert projected["state"] == "ANSWER_SAVED"
        assert projected["answerSaved"] and projected["stopConfirmed"]
        assert "principal" not in projected and "startupRecordDigest" not in projected

        from agent_console import native_wait_projection

        class Later:
            @staticmethod
            def now(_):
                return e.cp.human_expires_at + timedelta(seconds=1)

        monkeypatch.setattr(native_wait_projection, "datetime", Later)
        assert read_waits(c, p)[0]["state"] == "ANSWER_SAVED"

        class AuthorityExpired:
            @staticmethod
            def now(_):
                return e.cp.authority_expires_at

        monkeypatch.setattr(native_wait_projection, "datetime", AuthorityExpired)
        assert read_waits(c, p)[0]["state"] == "BLOCKED"
        assert (
            c.execute(
                "SELECT state FROM skill_invocation.native_wait_heads"
            ).fetchone()["state"]
            == "ANSWER_SAVED"
        )


def test_on_time_answer_can_resume_after_human_deadline_but_not_authority(waiting):
    e = waiting
    with e.repo.pool.connection() as c, c.transaction():
        e.owner.accept_answer(c, e.cp, answer(e))
        e.owner.confirm_stopped(c, e.cp, stop(e), lambda *_: None)
    e.owner.clock = lambda: e.cp.human_expires_at + timedelta(seconds=1)
    with e.repo.pool.connection() as c, c.transaction():
        assert e.owner.accept_answer(c, e.cp, answer(e))["replayed"]
        claim = e.owner.claim_continuation(
            c,
            e.cp,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )
        assert claim.newly_claimed
    e.owner.clock = lambda: e.cp.authority_expires_at
    with (
        e.repo.pool.connection() as c,
        c.transaction(),
        pytest.raises(AuthorityError, match="AUTHORITY_EXPIRED"),
    ):
        e.owner.enter_continuation(
            c,
            e.cp,
            claim.claim,
            worker_id="w",
            startup_record_digest="2" * 64,
            verify_worker=lambda *_: None,
        )


def test_new_answer_after_human_deadline_is_rejected_without_receipt(waiting):
    e = waiting
    e.owner.clock = lambda: e.cp.human_expires_at
    with e.repo.pool.connection() as c, c.transaction():
        with pytest.raises(AuthorityError, match="NATIVE_WAIT_EXPIRED"):
            e.owner.accept_answer(c, e.cp, answer(e))
        assert (
            NativeWaitStore(c, e.cp.identity).observation(e.cp.digest, "ANSWER_SAVED")
            is None
        )
