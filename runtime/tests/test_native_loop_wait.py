"""Typed WAIT control-flow checks; not managed owner/host acceptance."""

from agent_runtime.native_loop_wait import LoopWaiting
from test_native_loop import Journal, Ports, run


class WaitingPorts(Ports):
    def decide(self, context, **kwargs):
        self.contexts.append(context)
        return {"action": "CLARIFY", "question": "Confirm the current scope?"}

    def defer_input(self, question, **kwargs):
        self.suspension = (question, kwargs)
        return LoopWaiting("attempt-1", "a" * 64)


def test_wait_is_not_an_input_result_or_terminal_root():
    ports, journal = WaitingPorts(), Journal()
    result = run(ports, journal)
    assert isinstance(result, LoopWaiting)
    assert "result" not in journal.rows["attempt-1"]
    assert "attempt-1:0:INPUT" not in journal.rows
    assert journal.rows["attempt-1:0:MODEL"]["result"]["action"] == "CLARIFY"
    assert len(ports.contexts) == 1
    assert ports.suspension[1]["frame"]["ordinal"] == 0
    assert not ports.calls


def test_owner_receipt_loss_preserves_root_without_fabricated_terminal():
    ports, journal = WaitingPorts(), Journal()
    ports.defer_input = lambda *_args, **_kwargs: None
    result = run(ports, journal)
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert "result" not in journal.rows["attempt-1"]
    assert "attempt-1:0:INPUT" not in journal.rows


def test_input_authority_is_not_bypassed_by_wait_adapter():
    ports = WaitingPorts()
    ports.denied = "INPUT"
    result = run(ports)
    assert result["reason"] == "AUTHORIZATION_DENIED"
    assert not hasattr(ports, "suspension")


def continuation(ports):
    from copy import deepcopy

    from agent_runtime.native_loop_wait import ContinuationFrame

    value = ports.suspension[1]["frame"]
    reply = {
        "question": ports.suspension[0],
        "answer": "production",
        "questionDigest": "b" * 64,
    }
    trace = deepcopy(value["trace"])
    trace[-1]["clarification"] = reply
    return ContinuationFrame(
        checkpoint_digest="a" * 64,
        root_digest=value["rootDigest"],
        next_ordinal=value["ordinal"] + 1,
        remaining_active_seconds=60.0,
        trace=tuple(trace),
        observations=(*value["observations"], {"kind": "USER_ANSWER", **reply}),
        seen=tuple(value["seen"]),
    )


def resume(ports, journal, frame):
    from agent_runtime.native_loop import NativeLoop
    from test_native_loop import TOOLS

    return NativeLoop(TOOLS, ports, journal).run_continuation(
        "attempt-1",
        "Investigate service reliability",
        ["Return evidence"],
        {"source": "synthetic-monitoring-v1"},
        frame,
    )


def test_continuation_starts_at_next_ordinal_without_replaying_first_model():
    waiting, journal = WaitingPorts(), Journal()
    run(waiting, journal)
    ports = Ports(abnormal=False)
    ports.enter_continuation = lambda *_: True  # Controlled owner entry only.
    result = resume(ports, journal, continuation(waiting))
    assert result["status"] == "SUCCEEDED"
    assert ports.calls == ["inspect"]
    assert len(waiting.contexts) == 1
    assert len(ports.contexts) == 2
    assert ports.contexts[0]["remainingDecisions"] == 7
    assert "attempt-1:1:MODEL" in journal.rows
    assert journal.rows["attempt-1:0:MODEL"]["result"]["action"] == "CLARIFY"


def test_repeated_entry_observes_without_mutating_original_root():
    from copy import deepcopy

    from agent_runtime.native_loop_wait import LoopContinuationObservation

    waiting, journal = WaitingPorts(), Journal()
    run(waiting, journal)
    before = deepcopy(journal.rows)
    ports = Ports()
    ports.enter_continuation = lambda *_: False
    result = resume(ports, journal, continuation(waiting))
    assert isinstance(result, LoopContinuationObservation)
    assert journal.rows == before
    assert not ports.contexts and not ports.calls


def test_reconstruction_uses_saved_verifier_feedback_without_recalling_ports():
    from copy import deepcopy

    import pytest
    from agent_runtime.native_loop import LoopBoundaryError, digest
    from agent_runtime.native_loop_wait import reconstruct_continuation

    class RejectedThenWait(WaitingPorts):
        def decide(self, context, **kwargs):
            self.contexts.append(context)
            if not context["observations"]:
                return {"action": "FINISH", "answer": {"unsupported": True}}
            return {"action": "CLARIFY", "question": "Which authorized scope?"}

        def verify(self, context, answer):
            return {"passed": False, "missing": "current scope"}

    ports, journal = RejectedThenWait(), Journal()
    assert isinstance(run(ports, journal), LoopWaiting)
    question = ports.suspension[0]
    action = {"action": "CLARIFY", "question": question}
    journal.claim("attempt-1:1:INPUT", digest(action))
    journal.finish(
        "attempt-1:1:INPUT",
        digest(action),
        {"question": question, "answer": "production", "questionDigest": "b" * 64},
    )
    receipts = {k: v for k, v in journal.rows.items() if k != "attempt-1"}
    args = dict(
        root=ports.suspension[1]["frame"]["root"],
        checkpoint_digest="a" * 64,
        ordinal=1,
        remaining_active_seconds=60.0,
    )
    frame = reconstruct_continuation(**args, receipts=receipts)
    assert len(ports.contexts) == 2
    assert frame.next_ordinal == 2
    assert frame.observations[0] == {
        "kind": "COMPLETION_REJECTED",
        "verification": {"passed": False, "missing": "current scope"},
    }
    assert frame.trace[0]["verification"]["missing"] == "current scope"
    changed = deepcopy(receipts)
    del changed["attempt-1:0:VERIFY"]
    with pytest.raises(LoopBoundaryError, match="RECEIPT_MISMATCH"):
        reconstruct_continuation(**args, receipts=changed)
    changed = deepcopy(receipts)
    changed["attempt-1:1:MODEL"]["requestDigest"] = "f" * 64
    with pytest.raises(LoopBoundaryError, match="RECEIPT_MISMATCH"):
        reconstruct_continuation(**args, receipts=changed)


class TypedWaitingPorts(WaitingPorts):
    def decide(self, context, **kwargs):
        value = super().decide(context, **kwargs)
        return {**value, "questionContractId": "c" * 64}


def test_old_ports_reject_typed_question_extension_without_opt_in():
    ports, journal = TypedWaitingPorts(), Journal()
    result = run(ports, journal)
    assert result["reason"] == "INVALID_CLARIFICATION"
    assert not hasattr(ports, "suspension")
    assert "attempt-1:0:INPUT" not in journal.rows


def test_typed_port_passes_validated_contract_to_atomic_wait_owner():
    ports, journal = TypedWaitingPorts(), Journal()
    contract = {"contractDigest": "c" * 64, "controlled": "owner-resolved"}
    checked = []

    def validate(identity):
        checked.append(identity)
        return contract

    ports.validate_question_contract = validate
    assert isinstance(run(ports, journal), LoopWaiting)
    assert checked == ["c" * 64]
    frame = ports.suspension[1]["frame"]
    assert frame["answerContract"] == contract
    assert frame["trace"][-1]["decision"]["questionContractId"] == "c" * 64
    assert len(ports.contexts) == 1
    assert "attempt-1:0:INPUT" not in journal.rows


def test_unavailable_typed_contract_cannot_register_question():
    ports = TypedWaitingPorts()

    def deny(_):
        raise ValueError("not a current authorized contract")

    ports.validate_question_contract = deny
    result = run(ports)
    assert result["reason"] == "INVALID_QUESTION_CONTRACT"
    assert not hasattr(ports, "suspension")
