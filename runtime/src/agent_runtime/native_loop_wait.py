"""Internal positive wait receipt, deliberately distinct from a loop result."""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoopWaiting:
    invocation_id: str
    checkpoint_digest: str

    def __post_init__(self):
        if (
            not isinstance(self.invocation_id, str)
            or not 1 <= len(self.invocation_id) <= 500
            or not isinstance(self.checkpoint_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", self.checkpoint_digest)
        ):
            raise ValueError("INVALID_DURABLE_WAIT_RECEIPT")


@dataclass(frozen=True, slots=True)
class LoopContinuationObservation(LoopWaiting):
    """An existing continuation is being observed; this caller must not run it."""


@dataclass(frozen=True, slots=True)
class ContinuationFrame:
    """Reconstructed by the owner from immutable receipts, never user input."""

    checkpoint_digest: str
    root_digest: str
    next_ordinal: int
    remaining_active_seconds: float
    trace: tuple[dict, ...]
    observations: tuple[dict, ...]
    seen: tuple[str, ...]


def reconstruct_continuation(
    *, root, checkpoint_digest, ordinal, remaining_active_seconds, receipts
):
    """Rebuild loop state from actual completed receipts, without invoking ports.

    The backend owner checks scope/authority/checkpoint/fence and immutable record
    commitments before calling this deterministic adapter. Every request digest
    here is also recomputed against the original assembled input.
    """
    from .native_loop import LoopBoundaryError, digest, snapshot

    root = snapshot(root)
    identity = root["identity"]
    maximum = root["limits"]["maximum_decisions"]
    if type(ordinal) is not int or not 0 <= ordinal < maximum - 1:
        raise LoopBoundaryError("OWNER_CONTINUATION_ORDINAL_INVALID")
    tools = {tool["name"]: tool for tool in root["tools"]}
    observations, trace, seen, used = [], [], set(), set()

    def read(step, kind, request):
        key = f"{identity}:{step}:{kind}"
        value = receipts.get(key)
        if (
            not isinstance(value, dict)
            or value.get("requestDigest") != digest(request)
            or value.get("result") is None
        ):
            raise LoopBoundaryError("OWNER_CONTINUATION_RECEIPT_MISMATCH")
        used.add(key)
        return snapshot(value["result"])

    for step in range(ordinal + 1):
        assembled = {
            **root,
            "observations": observations,
            "remainingDecisions": maximum - step,
        }
        action = read(step, "MODEL", assembled)
        if not isinstance(action, dict):
            raise LoopBoundaryError("OWNER_CONTINUATION_DECISION_INVALID")
        entry = {
            "step": step,
            "decision": action,
            "observationDigest": digest(observations),
        }
        trace.append(entry)
        kind = action.get("action")
        if kind == "CLARIFY" and set(action) in (
            {"action", "question"},
            {"action", "question", "questionContractId"},
        ):
            reply = read(step, "INPUT", action)
            if (
                not isinstance(reply, dict)
                or reply.get("question") != action["question"]
                or not reply.get("answer")
            ):
                raise LoopBoundaryError("OWNER_CONTINUATION_ANSWER_REQUIRED")
            if "questionContractId" in action and (
                not isinstance(reply.get("answerContract"), dict)
                or reply["answerContract"].get("contractDigest")
                != action["questionContractId"]
                or not isinstance(reply.get("verifiedInterpretation"), dict)
            ):
                raise LoopBoundaryError("OWNER_CONTINUATION_ANSWER_CONTRACT_CHANGED")
            observations.append({"kind": "USER_ANSWER", **reply})
            entry["clarification"] = reply
        elif kind == "TOOL" and set(action) == {"action", "tool", "arguments"}:
            tool = tools.get(action["tool"])
            if tool is None:
                raise LoopBoundaryError("OWNER_CONTINUATION_TOOL_CHANGED")
            arguments = action["arguments"]
            output = read(step, "TOOL", {"tool": tool, "arguments": arguments})
            signature = digest(
                [
                    tool,
                    arguments,
                    [o for o in observations if o["kind"] == "USER_ANSWER"],
                ]
            )
            if signature in seen:
                raise LoopBoundaryError("OWNER_CONTINUATION_TERMINAL_HISTORY")
            seen.add(signature)
            observation = {
                "kind": "TOOL_RESULT",
                "tool": tool["name"],
                "revision": tool["revision"],
                "digest": tool["digest"],
                "arguments": arguments,
                "output": output,
            }
            observations.append(observation)
            entry["observation"] = observation
        elif kind == "FINISH" and set(action) == {"action", "answer"}:
            verification = read(
                step, "VERIFY", {"context": assembled, "answer": action["answer"]}
            )
            if not isinstance(verification, dict) or (
                verification.get("passed") is True
                and any(o["kind"] == "TOOL_RESULT" for o in observations)
            ):
                raise LoopBoundaryError("OWNER_CONTINUATION_TERMINAL_HISTORY")
            signature = digest([action, verification])
            if signature in seen:
                raise LoopBoundaryError("OWNER_CONTINUATION_TERMINAL_HISTORY")
            seen.add(signature)
            entry["verification"] = verification
            observations.append(
                {"kind": "COMPLETION_REJECTED", "verification": verification}
            )
        else:
            raise LoopBoundaryError("OWNER_CONTINUATION_DECISION_INVALID")
    if trace[-1]["decision"]["action"] != "CLARIFY" or used != set(receipts):
        raise LoopBoundaryError("OWNER_CONTINUATION_RECEIPT_SET_CHANGED")
    return ContinuationFrame(
        checkpoint_digest=checkpoint_digest,
        root_digest=digest(root),
        next_ordinal=ordinal + 1,
        remaining_active_seconds=remaining_active_seconds,
        trace=tuple(trace),
        observations=tuple(observations),
        seen=tuple(sorted(seen)),
    )
