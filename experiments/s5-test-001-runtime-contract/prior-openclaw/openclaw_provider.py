"""OpenClaw-only translation behind the experimental generic boundary."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import uuid4

from generic_boundary import (
    EventKind,
    ExecutionEvent,
    ExecutionHandle,
    ExecutionOutcome,
    ExecutionRequest,
    Observation,
    OutcomeKind,
    TruthValue,
)


class ProviderError(RuntimeError):
    """A sanitized experimental Provider failure."""


@dataclass(frozen=True)
class OpenClawBinding:
    """Opaque-to-caller native binding data owned by this Provider."""

    gateway_url: str
    agent_id: str
    session_key: str


class OpenClawProvider:
    def __init__(
        self,
        *,
        cli: Sequence[str],
        binding: OpenClawBinding,
        token_env: str,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._cli = tuple(cli)
        self._binding = binding
        self._token_env = token_env
        self._environment = dict(environment or {})

    def observe(self) -> tuple[Observation, ...]:
        try:
            payload = self._call("health", {})
        except ProviderError as exc:
            return (
                Observation(
                    "InfrastructureAvailable", TruthValue.UNKNOWN, "external to probe"
                ),
                Observation("RuntimeAvailable", TruthValue.FALSE, str(exc)),
                Observation("ProtocolAvailable", TruthValue.FALSE, str(exc)),
                Observation(
                    "DependencyReady", TruthValue.UNKNOWN, "protocol unavailable"
                ),
            )
        gateway_ok = payload.get("ok") is True
        return (
            Observation(
                "InfrastructureAvailable",
                TruthValue.UNKNOWN,
                "Gateway RPC cannot prove host infrastructure availability",
            ),
            Observation(
                "RuntimeAvailable",
                TruthValue.TRUE if gateway_ok else TruthValue.UNKNOWN,
                "native health RPC returned"
                if gateway_ok
                else "health payload was inconclusive",
            ),
            Observation(
                "ProtocolAvailable",
                TruthValue.TRUE,
                "authenticated Gateway RPC completed",
            ),
            Observation(
                "DependencyReady",
                TruthValue.UNKNOWN,
                "health RPC does not prove model credential readiness",
            ),
        )

    def submit(
        self, request: ExecutionRequest
    ) -> tuple[ExecutionHandle, ExecutionEvent]:
        idempotency_key = f"s5-openclaw-{uuid4()}"
        native = self._call(
            "agent",
            {
                "message": request.input_text,
                "agentId": self._binding.agent_id,
                "sessionKey": self._binding.session_key,
                "idempotencyKey": idempotency_key,
            },
        )
        if native.get("status") not in {"accepted", "in_flight"}:
            raise ProviderError("runtime did not accept execution")
        correlation = self._required_string(native, "runId")
        handle = ExecutionHandle(correlation_id=correlation)
        event = ExecutionEvent(
            kind=EventKind.ACCEPTED,
            correlation_id=correlation,
            observed_at_ms=self._optional_int(native, "acceptedAt"),
            detail={"state": "accepted"},
        )
        return handle, event

    def await_outcome(
        self, handle: ExecutionHandle, timeout_ms: int
    ) -> tuple[ExecutionEvent, ExecutionOutcome]:
        native = self._call(
            "agent.wait",
            {"runId": handle.correlation_id, "timeoutMs": timeout_ms},
            timeout_ms=timeout_ms + 5_000,
        )
        status = str(native.get("status", "unknown"))
        outcome_kind = {
            "ok": OutcomeKind.SUCCEEDED,
            "error": OutcomeKind.FAILED,
            "cancelled": OutcomeKind.CANCELLED,
            "aborted": OutcomeKind.CANCELLED,
            "timeout": OutcomeKind.TIMED_OUT,
        }.get(status, OutcomeKind.UNKNOWN)
        message = self._sanitize_message(native.get("error"))
        ended_at = self._optional_int(native, "endedAt")
        event = ExecutionEvent(
            kind=EventKind.TERMINAL,
            correlation_id=handle.correlation_id,
            observed_at_ms=ended_at,
            detail={"state": outcome_kind.value},
        )
        outcome = ExecutionOutcome(
            kind=outcome_kind,
            correlation_id=handle.correlation_id,
            message=message,
            observed_at_ms=ended_at,
        )
        return event, outcome

    def _call(
        self, method: str, params: Mapping[str, object], timeout_ms: int = 15_000
    ) -> dict[str, object]:
        token = os.environ.get(self._token_env)
        if not token:
            raise ProviderError("Gateway credential reference is unresolved")
        command = [
            *self._cli,
            "gateway",
            "call",
            method,
            "--url",
            self._binding.gateway_url,
            "--token",
            token,
            "--params",
            json.dumps(params, separators=(",", ":")),
            "--timeout",
            str(timeout_ms),
            "--json",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=max(1, timeout_ms // 1_000 + 5),
            env={**os.environ, **self._environment},
        )
        if completed.returncode != 0:
            raise ProviderError(
                self._sanitize_message(completed.stderr) or "Gateway RPC failed"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderError("Gateway returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Gateway returned an unexpected payload")
        return payload

    @staticmethod
    def _required_string(payload: Mapping[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ProviderError(f"Gateway response omitted {key}")
        return value

    @staticmethod
    def _optional_int(payload: Mapping[str, object], key: str) -> int | None:
        value = payload.get(key)
        return value if isinstance(value, int) else None

    @staticmethod
    def _sanitize_message(value: object) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        first_line = value.strip().splitlines()[0]
        if "No API key found" in first_line:
            return "runtime dependency unavailable: model credential not configured"
        if "gateway" in first_line.lower():
            return "runtime protocol unavailable"
        return "runtime execution failed"
