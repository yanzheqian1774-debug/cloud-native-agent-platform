"""Core conformance only; scripted ports are not live-model acceptance."""

from copy import deepcopy

import pytest
from agent_runtime.native_loop import Limits, LoopBoundaryError, NativeLoop, Tool


class Journal:
    def __init__(self):
        self.rows = {}

    def claim(self, key, request_digest):
        if key in self.rows:
            return deepcopy(self.rows[key])
        self.rows[key] = {"requestDigest": request_digest}
        return None

    def finish(self, key, request_digest, result):
        assert self.rows[key]["requestDigest"] == request_digest
        self.rows[key]["result"] = deepcopy(result)


def validate(arguments):
    if set(arguments) != {"field"} or arguments["field"] not in {"latency", "errors"}:
        raise ValueError("invalid")


TOOLS = tuple(
    Tool(name, "1", name + "-digest", name, {"type": "object"}, validate)
    for name in ("inspect", "investigate")
)


class Ports:
    def __init__(self, abnormal=True):
        self.abnormal = abnormal
        self.calls = []
        self.contexts = []
        self.denied = None

    def authorize(self, kind, request):
        return kind != self.denied

    def decide(self, context, **kwargs):
        self.contexts.append(deepcopy(context))
        outputs = [x for x in context["observations"] if x["kind"] == "TOOL_RESULT"]
        if not outputs:
            return {
                "action": "TOOL",
                "tool": "inspect",
                "arguments": {"field": "latency"},
            }
        if outputs[-1]["output"].get("abnormal"):
            return {
                "action": "TOOL",
                "tool": "investigate",
                "arguments": {"field": "errors"},
            }
        return {
            "action": "FINISH",
            "answer": {"evidence": [x["tool"] for x in outputs]},
        }

    def invoke(self, tool, arguments, **kwargs):
        self.calls.append(tool.name)
        return (
            {"abnormal": self.abnormal}
            if tool.name == "inspect"
            else {"cause": "unverified"}
        )

    def verify(self, context, answer):
        tools = [
            x["tool"] for x in context["observations"] if x["kind"] == "TOOL_RESULT"
        ]
        return {"passed": answer["evidence"] == tools and bool(tools)}


def run(ports=None, journal=None, **kwargs):
    return NativeLoop(TOOLS, ports or Ports(), journal or Journal(), **kwargs).run(
        "attempt-1",
        "Investigate service reliability",
        ["Return evidence"],
        {"source": "synthetic-monitoring-v1"},
    )


@pytest.mark.parametrize(
    "abnormal,expected", [(True, ["inspect", "investigate"]), (False, ["inspect"])]
)
def test_observation_changes_next_action(abnormal, expected):
    ports = Ports(abnormal)
    result = run(ports)
    assert result["status"] == "SUCCEEDED"
    assert ports.calls == expected
    assert ports.contexts[1]["observations"][0]["output"] == {"abnormal": abnormal}


def test_terminal_replay_never_dispatches_again():
    ports, journal = Ports(), Journal()
    first = run(ports, journal)
    assert run(ports, journal) == first
    assert ports.calls == ["inspect", "investigate"]


def test_identity_conflict_fails_closed():
    journal = Journal()
    run(journal=journal)
    with pytest.raises(LoopBoundaryError, match="IDENTITY_CONFLICT"):
        NativeLoop(TOOLS, Ports(), journal).run("attempt-1", "other", ["criterion"], {})


def test_unsettled_root_never_replays():
    ports, journal = Ports(), Journal()
    run(ports, journal)
    journal.rows["attempt-1"].pop("result")
    ports.calls.clear()
    assert run(ports, journal)["status"] == "OUTCOME_UNKNOWN"
    assert not ports.calls


@pytest.mark.parametrize(
    "action,reason",
    [
        ({"action": "TOOL", "tool": "shell", "arguments": {}}, "TOOL_NOT_ALLOWED"),
        (
            {"action": "TOOL", "tool": "inspect", "arguments": {"command": "secret"}},
            "INVALID_TOOL_ARGUMENTS",
        ),
        ({"action": "FINISH", "answer": "done"}, "INVALID_FINISH"),
        ({"action": "CLARIFY", "question": ""}, "INVALID_CLARIFICATION"),
        (
            {"action": "TOOL", "tool": "inspect", "arguments": {}, "override": True},
            "INVALID_DECISION",
        ),
        ([], "INVALID_DECISION"),
    ],
)
def test_invalid_decision_cannot_invoke(action, reason):
    ports = Ports()
    ports.decide = lambda *args, **kwargs: action
    assert run(ports)["reason"] == reason
    assert not ports.calls


def test_failed_completion_feedback_reaches_decider():
    ports = Ports(False)
    original = ports.decide

    def decide(context, **kwargs):
        if not context["observations"]:
            return {"action": "FINISH", "answer": {"evidence": []}}
        return original(context, **kwargs)

    ports.decide = decide
    result = run(ports)
    assert result["status"] == "SUCCEEDED"
    assert ports.contexts[0]["observations"][0]["kind"] == "COMPLETION_REJECTED"


def test_model_cannot_finish_without_actual_tool_evidence():
    ports = Ports()
    ports.decide = lambda *args, **kwargs: {"action": "FINISH", "answer": {}}
    ports.verify = lambda *args: {"passed": True}
    result = run(ports)
    assert result["status"] != "SUCCEEDED"


def test_repeated_tool_does_not_execute_twice():
    ports = Ports()
    ports.decide = lambda *args, **kwargs: {
        "action": "TOOL",
        "tool": "inspect",
        "arguments": {"field": "latency"},
    }
    assert run(ports)["reason"] == "NO_PROGRESS"
    assert ports.calls == ["inspect"]


def test_tool_authority_rechecked_after_model():
    ports = Ports()
    ports.denied = "TOOL"
    assert run(ports)["reason"] == "AUTHORIZATION_DENIED"
    assert not ports.calls


def test_unknown_tool_effect_is_not_retried_or_exposed():
    ports, journal = Ports(), Journal()

    def invoke(*args, **kwargs):
        raise TimeoutError("secret-provider-body")

    ports.invoke = invoke
    result = run(ports, journal)
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert "secret" not in str(result)
    assert "result" not in journal.rows["attempt-1:0:TOOL"]
    assert run(ports, journal) == result


def test_cancellation_before_model():
    ports = Ports()
    assert run(ports, cancelled=lambda: True)["reason"] == "CANCELLED"
    assert not ports.contexts


def test_cancellation_after_model_prevents_tool():
    ports = Ports()
    assert run(ports, cancelled=lambda: bool(ports.contexts))["reason"] == "CANCELLED"
    assert not ports.calls


def test_deadline_after_model_prevents_tool():
    ports = Ports()
    assert (
        run(ports, clock=lambda: 200 if ports.contexts else 0)["reason"] == "DEADLINE"
    )
    assert not ports.calls


def test_step_limit():
    result = run(limits=Limits(maximum_decisions=1))
    assert result["reason"] == "DECISION_LIMIT"
    assert result["answer"] is None


def test_oversized_observation_stops_before_another_model_call():
    ports = Ports()
    ports.invoke = lambda *args, **kwargs: {"data": "x" * 20000}
    assert run(ports)["status"] != "SUCCEEDED"
    assert len(ports.contexts) == 1


def test_journal_failure_cannot_dispatch():
    class Broken(Journal):
        def claim(self, key, request_digest):
            if ":MODEL" in key:
                raise OSError("sensitive database location")
            return super().claim(key, request_digest)

    ports = Ports()
    result = run(ports, Broken())
    assert result["reason"] == "OWNER_RECONCILIATION_REQUIRED"
    assert "sensitive" not in str(result)
    assert not ports.contexts


def test_revoked_authority_prevents_terminal_result_read():
    ports, journal = Ports(), Journal()
    assert run(ports, journal)["status"] == "SUCCEEDED"
    ports.denied = "LOOP"
    result = run(ports, journal)
    assert result["reason"] == "AUTHORIZATION_DENIED"
    assert result["answer"] is None


def test_failed_root_claim_is_sanitized():
    class Broken(Journal):
        def claim(self, key, request_digest):
            raise OSError("private-dsn")

    result = run(journal=Broken())
    assert result["reason"] == "OWNER_RECONCILIATION_REQUIRED"
    assert "private-dsn" not in str(result)


def test_model_cannot_modify_completion_context():
    ports = Ports(False)
    original = ports.decide

    def mutate(context, **kwargs):
        action = original(context, **kwargs)
        context["criteria"].clear()
        context["observations"].clear()
        return action

    ports.decide = mutate
    result = run(ports)
    assert result["status"] == "SUCCEEDED"
    assert all(context["criteria"] == ["Return evidence"] for context in ports.contexts)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_deadline_configuration_must_be_finite(value):
    with pytest.raises(LoopBoundaryError):
        Limits(total_seconds=value)


def test_deadline_during_authorization_prevents_dispatch():
    ports = Ports()
    elapsed = [0]

    def authorize(kind, request):
        if kind == "MODEL":
            elapsed[0] = 121
        return True

    ports.authorize = authorize
    result = run(ports, clock=lambda: elapsed[0])
    assert result["reason"] == "DEADLINE"
    assert not ports.contexts


def test_boundary_terminal_write_failure_is_unknown_and_sanitized():
    class Broken(Journal):
        def finish(self, key, request_digest, result):
            if key == "attempt-1":
                raise OSError("private-dsn")
            super().finish(key, request_digest, result)

    result = run(journal=Broken(), cancelled=lambda: True)
    assert result["reason"] == "OWNER_RECONCILIATION_REQUIRED"
    assert result["status"] == "OUTCOME_UNKNOWN"
    assert "private-dsn" not in str(result)
