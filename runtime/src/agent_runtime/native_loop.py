"""Internal observation-driven loop; effects and persistence remain owner ports.

This module has no credentials, network, filesystem, database or execution
registry. Production composition must supply governed ports, including durable
claim-before-dispatch and supervised deadlines for every effect.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from time import monotonic
from typing import Any, Protocol


class LoopBoundaryError(ValueError):
    """A disclosure-safe boundary rejection, not an arbitrary provider error."""


def snapshot(value: Any, maximum: int = 65536) -> Any:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        if len(encoded.encode()) > maximum:
            raise LoopBoundaryError("CONTEXT_LIMIT")
        return json.loads(encoded)
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise LoopBoundaryError("INVALID_OR_OVERSIZED_CONTEXT") from None


def digest(value: Any) -> str:
    return sha256(
        json.dumps(snapshot(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Limits:
    maximum_decisions: int = 8
    total_seconds: float = 120
    maximum_context_bytes: int = 65536
    maximum_observation_bytes: int = 16384

    def __post_init__(self):
        if (
            type(self.maximum_decisions) is not int
            or not 1 <= self.maximum_decisions <= 32
            or isinstance(self.total_seconds, bool)
            or not isfinite(self.total_seconds)
            or not 1 <= self.total_seconds <= 600
            or not 1024 <= self.maximum_context_bytes <= 65536
            or not 128 <= self.maximum_observation_bytes <= 16384
        ):
            raise LoopBoundaryError("INVALID_LIMITS")


@dataclass(frozen=True)
class Tool:
    name: str
    revision: str
    digest: str
    description: str
    input_schema: Mapping
    validate: Callable[[dict], None]

    def descriptor(self):
        return snapshot(
            {
                "name": self.name,
                "revision": self.revision,
                "digest": self.digest,
                "description": self.description,
                "inputSchema": self.input_schema,
            }
        )


class OwnerJournal(Protocol):
    """Atomic and durable in production; scoped by principal/task/attempt.

    claim returns None only for a newly owned claim. Existing records are
    returned without mutation. finish binds to the same request digest.
    Exceptions are fail-closed; callers must never interpret them as absence.
    """

    def claim(self, key: str, request_digest: str) -> dict | None: ...
    def finish(self, key: str, request_digest: str, result: dict) -> None: ...


class GovernedPorts(Protocol):
    def decide(self, context: dict, *, key: str, remaining_seconds: float) -> dict:
        """Use governed model binding, admission, accounting and deadline."""
        ...

    def invoke(
        self, tool: Tool, arguments: dict, *, key: str, remaining_seconds: float
    ) -> dict:
        """Use exact resource owner with current authorization and deadline."""
        ...

    def authorize(self, kind: str, request: dict) -> bool:
        """Recheck current authority immediately before each dispatch."""
        ...

    def verify(self, context: dict, answer: dict) -> dict:
        """Independent completion check, never a model's self-declared success."""
        ...


class NativeLoop:
    def __init__(
        self,
        tools: tuple[Tool, ...],
        ports: GovernedPorts,
        journal: OwnerJournal,
        *,
        limits=None,
        clock=monotonic,
        cancelled=lambda: False,
    ):
        self.tools = {tool.name: tool for tool in tools}
        if (
            not tools
            or len(self.tools) != len(tools)
            or any(
                not tool.name or not tool.revision or not tool.digest for tool in tools
            )
        ):
            raise LoopBoundaryError("INVALID_TOOL_REGISTRY")
        self.ports, self.journal = ports, journal
        self.limits, self.clock, self.cancelled = limits or Limits(), clock, cancelled

    def run(self, identity: str, goal: str, criteria: list[str], context: dict):
        if (
            not identity
            or not goal
            or not criteria
            or not all(isinstance(item, str) and item for item in criteria)
        ):
            raise LoopBoundaryError("GOAL_AND_CRITERIA_REQUIRED")
        root = snapshot(
            {
                "identity": identity,
                "goal": goal,
                "criteria": criteria,
                "context": context,
                "tools": [t.descriptor() for t in self.tools.values()],
                "limits": vars(self.limits),
            },
            self.limits.maximum_context_bytes,
        )
        commitment = digest(root)
        try:
            authorized = self.ports.authorize("LOOP", snapshot(root))
        except Exception:
            authorized = False
        if authorized is not True:
            return {
                "status": "STOPPED",
                "reason": "AUTHORIZATION_DENIED",
                "trace": [],
                "answer": None,
            }
        try:
            previous = self.journal.claim(identity, commitment)
        except Exception:
            return {
                "status": "OUTCOME_UNKNOWN",
                "reason": "OWNER_RECONCILIATION_REQUIRED",
                "trace": [],
                "answer": None,
            }
        if previous is not None:
            if previous.get("requestDigest") != commitment:
                raise LoopBoundaryError("JOURNAL_IDENTITY_CONFLICT")
            # An unfinished owner claim is intentionally not resumed or replayed.
            return snapshot(
                previous.get("result")
                or {
                    "status": "OUTCOME_UNKNOWN",
                    "reason": "UNSETTLED_OWNER_CLAIM",
                    "trace": [],
                    "answer": None,
                },
                2_097_152,
            )
        started = self.clock()
        trace, observations, seen = [], [], set()

        def remaining():
            return self.limits.total_seconds - (self.clock() - started)

        def stop_reason():
            if self.cancelled():
                return "CANCELLED"
            if remaining() <= 0:
                return "DEADLINE"
            return None

        def finish(status, reason, answer=None):
            result = snapshot(
                {"status": status, "reason": reason, "trace": trace, "answer": answer},
                2_097_152,
            )
            try:
                self.journal.finish(identity, commitment, result)
            except Exception:
                return {
                    "status": "OUTCOME_UNKNOWN",
                    "reason": "OWNER_RECONCILIATION_REQUIRED",
                    "trace": trace,
                    "answer": None,
                }
            return result

        def effect(kind, ordinal, request, invoke):
            reason = stop_reason()
            if reason:
                raise LoopBoundaryError(reason)
            key = f"{identity}:{ordinal}:{kind}"
            request_hash = digest(request)
            try:
                authorized = self.ports.authorize(kind, snapshot(request))
            except Exception:
                raise LoopBoundaryError("AUTHORIZATION_UNAVAILABLE") from None
            if authorized is not True:
                raise LoopBoundaryError("AUTHORIZATION_DENIED")
            existing = self.journal.claim(key, request_hash)
            if existing is not None:
                raise LoopBoundaryError("UNSETTLED_OR_DUPLICATE_EFFECT")
            reason = stop_reason()
            if reason:
                raise LoopBoundaryError(reason)
            # Even a local exception after entry is uncertain; never retry it.
            try:
                result = invoke(key, remaining())
            except LoopBoundaryError as exc:
                if kind != "INPUT":
                    raise LoopBoundaryError("EFFECT_OUTCOME_UNKNOWN") from None
                self.journal.finish(
                    key, request_hash, {"status": "STOPPED", "reason": str(exc)}
                )
                raise
            except Exception:
                raise LoopBoundaryError("EFFECT_OUTCOME_UNKNOWN") from None
            result = snapshot(result, self.limits.maximum_observation_bytes)
            self.journal.finish(key, request_hash, result)
            reason = stop_reason()
            if reason:
                raise LoopBoundaryError(reason)
            return result

        try:
            for ordinal in range(self.limits.maximum_decisions):
                assembled = snapshot(
                    {
                        **root,
                        "observations": observations,
                        "remainingDecisions": self.limits.maximum_decisions - ordinal,
                    },
                    self.limits.maximum_context_bytes,
                )
                action = effect(
                    "MODEL",
                    ordinal,
                    assembled,
                    lambda key, seconds, assembled=assembled: self.ports.decide(
                        snapshot(assembled), key=key, remaining_seconds=seconds
                    ),
                )
                if not isinstance(action, dict):
                    raise LoopBoundaryError("INVALID_DECISION")
                kind = action.get("action")
                trace.append(
                    {
                        "step": ordinal,
                        "decision": action,
                        "observationDigest": digest(observations),
                    }
                )
                if kind == "CLARIFY":
                    if (
                        set(action) != {"action", "question"}
                        or not isinstance(action["question"], str)
                        or not action["question"].strip()
                        or len(action["question"]) > 1000
                    ):
                        raise LoopBoundaryError("INVALID_CLARIFICATION")
                    clarify = getattr(self.ports, "clarify", None)
                    if clarify is None:
                        return finish("NEEDS_INPUT", "CLARIFICATION_REQUIRED", action)
                    reply = effect(
                        "INPUT",
                        ordinal,
                        action,
                        lambda key, seconds, q=action["question"], fn=clarify: fn(
                            q, key=key, remaining_seconds=seconds
                        ),
                    )
                    observations.append({"kind": "USER_ANSWER", **snapshot(reply)})
                    trace[-1]["clarification"] = snapshot(reply)
                    continue
                if kind == "FINISH":
                    if set(action) != {"action", "answer"} or not isinstance(
                        action["answer"], dict
                    ):
                        raise LoopBoundaryError("INVALID_FINISH")
                    try:
                        verification = snapshot(
                            self.ports.verify(
                                snapshot(assembled), snapshot(action["answer"])
                            ),
                            4096,
                        )
                    except Exception:
                        raise LoopBoundaryError("VERIFICATION_UNAVAILABLE") from None
                    trace[-1]["verification"] = verification
                    if stop_reason():
                        return finish("STOPPED", stop_reason())
                    if (
                        isinstance(verification, dict)
                        and verification.get("passed") is True
                        and any(item["kind"] == "TOOL_RESULT" for item in observations)
                    ):
                        return finish("SUCCEEDED", "VERIFIED", action["answer"])
                    signature = digest([action, verification])
                    if signature in seen:
                        return finish("STOPPED", "NO_PROGRESS")
                    seen.add(signature)
                    observations.append(
                        {"kind": "COMPLETION_REJECTED", "verification": verification}
                    )
                    continue
                if kind != "TOOL" or set(action) != {"action", "tool", "arguments"}:
                    raise LoopBoundaryError("INVALID_DECISION")
                name, arguments = action["tool"], action["arguments"]
                if not isinstance(name, str) or name not in self.tools:
                    raise LoopBoundaryError("TOOL_NOT_ALLOWED")
                tool = self.tools[name]
                if not isinstance(arguments, dict):
                    raise LoopBoundaryError("INVALID_TOOL_ARGUMENTS")
                try:
                    tool.validate(snapshot(arguments))
                except Exception:
                    raise LoopBoundaryError("INVALID_TOOL_ARGUMENTS") from None
                signature = digest(
                    [
                        tool.descriptor(),
                        arguments,
                        [o for o in observations if o["kind"] == "USER_ANSWER"],
                    ]
                )
                if signature in seen:
                    return finish("STOPPED", "NO_PROGRESS")
                seen.add(signature)
                output = effect(
                    "TOOL",
                    ordinal,
                    {"tool": tool.descriptor(), "arguments": arguments},
                    lambda key, seconds, tool=tool, arguments=arguments: (
                        self.ports.invoke(
                            tool,
                            snapshot(arguments),
                            key=key,
                            remaining_seconds=seconds,
                        )
                    ),
                )
                if not isinstance(output, dict):
                    raise LoopBoundaryError("INVALID_TOOL_OBSERVATION")
                observation = {
                    "kind": "TOOL_RESULT",
                    "tool": tool.name,
                    "revision": tool.revision,
                    "digest": tool.digest,
                    "arguments": arguments,
                    "output": output,
                }
                observations.append(observation)
                trace[-1]["observation"] = observation
            return finish("STOPPED", "DECISION_LIMIT")
        except LoopBoundaryError as exc:
            reason = str(exc)
            uncertain = reason in {
                "EFFECT_OUTCOME_UNKNOWN",
                "UNSETTLED_OR_DUPLICATE_EFFECT",
            }
            return finish("OUTCOME_UNKNOWN" if uncertain else "STOPPED", reason)
        except Exception:
            # A failed journal/owner call may have committed. Preserve the root
            # claim for explicit reconciliation and do not fabricate a receipt.
            return {
                "status": "OUTCOME_UNKNOWN",
                "reason": "OWNER_RECONCILIATION_REQUIRED",
                "trace": trace,
                "answer": None,
            }
