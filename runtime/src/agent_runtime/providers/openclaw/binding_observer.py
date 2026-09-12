"""Read-only composite observer for persisted OpenClaw bindings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from agent_core.openclaw_binding import (
    AssociationStatus,
    OpenClawBindingObservation,
    OpenClawGenerationBinding,
    OpenClawRuntimeBinding,
)

from .models import OpenClawError, ReasonCode

EXACT_SOURCE_VERSION = "2026.7.1-2"


class OpenClawReadOnlyClient(Protocol):
    def read_only_rpc(
        self, method: str, params: dict[str, object]
    ) -> dict[str, object]: ...


class OpenClawBindingObserver:
    """Observe every persisted correlation without issuing provider effects."""

    def __init__(
        self,
        client: OpenClawReadOnlyClient,
        *,
        freshness: timedelta = timedelta(seconds=30),
    ) -> None:
        if freshness != timedelta(seconds=30):
            raise ValueError("OPENCLAW_OBSERVATION_FRESHNESS_UNSUPPORTED")
        self._client = client
        self._freshness = freshness

    def observe(
        self,
        binding: OpenClawRuntimeBinding,
        generation: OpenClawGenerationBinding,
        *,
        high_water: int,
        at: datetime | None = None,
    ) -> OpenClawBindingObservation:
        now = (at or datetime.now(UTC)).astimezone(UTC)
        flags = {
            "gateway": False,
            "agent": False,
            "workspace": False,
            "session": False,
        }
        try:
            health = self._client.read_only_rpc("health", {})
            status = self._client.read_only_rpc("status", {})
            flags["gateway"] = self._gateway_matches(health, status, binding)
            if not flags["gateway"]:
                return self._result(
                    binding,
                    generation,
                    high_water,
                    now,
                    AssociationStatus.MISMATCHED,
                    "OPENCLAW_GATEWAY_OR_VERSION_MISMATCH",
                    flags,
                )

            agents = self._client.read_only_rpc("agents.list", {}).get("agents")
            if not isinstance(agents, list):
                raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
            matches = [
                item
                for item in agents
                if isinstance(item, dict) and item.get("id") == binding.agent_id
            ]
            if len(matches) != 1:
                return self._result(
                    binding,
                    generation,
                    high_water,
                    now,
                    AssociationStatus.RECOVERY_REQUIRED,
                    "OPENCLAW_AGENT_MISSING_OR_AMBIGUOUS",
                    flags,
                )
            flags["agent"] = True
            workspace = matches[0].get("workspace")
            if (
                not isinstance(workspace, str)
                or Path(workspace).resolve()
                != Path(binding.canonical_workspace).resolve()
            ):
                return self._result(
                    binding,
                    generation,
                    high_water,
                    now,
                    AssociationStatus.MISMATCHED,
                    "OPENCLAW_WORKSPACE_MISMATCH",
                    flags,
                )
            self._client.read_only_rpc(
                "agents.files.list", {"agentId": binding.agent_id}
            )
            flags["workspace"] = True

            sessions = self._client.read_only_rpc(
                "sessions.list", {"agentId": binding.agent_id}
            ).get("sessions")
            if not isinstance(sessions, list):
                raise OpenClawError(ReasonCode.GATEWAY_PROTOCOL_ERROR.value)
            matched_sessions = [
                item
                for item in sessions
                if isinstance(item, dict)
                and item.get("key") == generation.session_key
                and item.get("sessionId") == generation.session_id
            ]
            if len(matched_sessions) != 1:
                return self._result(
                    binding,
                    generation,
                    high_water,
                    now,
                    AssociationStatus.RECOVERY_REQUIRED,
                    "OPENCLAW_SESSION_MISSING_OR_AMBIGUOUS",
                    flags,
                )
            described = self._client.read_only_rpc(
                "sessions.describe", {"key": generation.session_key}
            )
            fetched = self._client.read_only_rpc(
                "sessions.get",
                {
                    "key": generation.session_key,
                    "agentId": binding.agent_id,
                    "limit": 1,
                },
            )
            if not self._session_matches(
                described, generation
            ) or not self._session_matches(fetched, generation):
                return self._result(
                    binding,
                    generation,
                    high_water,
                    now,
                    AssociationStatus.MISMATCHED,
                    "OPENCLAW_SESSION_IDENTITY_MISMATCH",
                    flags,
                )
            flags["session"] = True
            return self._result(
                binding,
                generation,
                high_water,
                now,
                AssociationStatus.MATCHED,
                "OPENCLAW_COMPOSITE_ASSOCIATION_MATCHED",
                flags,
            )
        except OpenClawError as exc:
            reason = str(exc)
            association = (
                AssociationStatus.MISMATCHED
                if reason == ReasonCode.IDENTITY_MISMATCH.value
                else AssociationStatus.RECOVERY_REQUIRED
            )
            return self._result(
                binding,
                generation,
                high_water,
                now,
                association,
                reason,
                flags,
            )

    @staticmethod
    def _gateway_matches(
        health: dict[str, object],
        status: dict[str, object],
        binding: OpenClawRuntimeBinding,
    ) -> bool:
        event_loop = health.get("eventLoop")
        return (
            binding.source_version == EXACT_SOURCE_VERSION
            and status.get("runtimeVersion") == binding.source_version
            and isinstance(event_loop, dict)
            and event_loop.get("degraded") is False
        )

    @staticmethod
    def _session_matches(
        payload: dict[str, object], generation: OpenClawGenerationBinding
    ) -> bool:
        candidates = [payload]
        for key in ("session", "entry"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                candidates.append(nested)
        return any(
            candidate.get("key") == generation.session_key
            and candidate.get("sessionId") == generation.session_id
            for candidate in candidates
        )

    def _result(
        self,
        binding: OpenClawRuntimeBinding,
        generation: OpenClawGenerationBinding,
        high_water: int,
        now: datetime,
        status: AssociationStatus,
        reason: str,
        flags: dict[str, bool],
    ) -> OpenClawBindingObservation:
        return OpenClawBindingObservation(
            binding.scope,
            binding.runtime_instance_id,
            generation.generation,
            high_water,
            status,
            now,
            now + self._freshness,
            binding.source_version,
            reason,
            flags["gateway"],
            flags["agent"],
            flags["workspace"],
            flags["session"],
        )
