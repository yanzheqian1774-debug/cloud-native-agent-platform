"""Replaceable allowlisted HTTP executor for governed READ_ONLY Skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .resource_use_domain import canonical_digest
from .skill_invocation_domain import ExecutorRevision, SkillInvocationError


class SkillExecutorFailure(SkillInvocationError):
    def __init__(self, code: str, *, outcome_unknown: bool) -> None:
        super().__init__(code)
        self.outcome_unknown = outcome_unknown


@dataclass(frozen=True, slots=True)
class SkillExecutorResult:
    accepted: bool
    output: dict[str, Any]
    provider_observation_id: str


class SkillExecutor(Protocol):
    revision: ExecutorRevision

    def invoke(
        self,
        invocation_id: str,
        operation: str,
        inputs: dict[str, Any],
        timeout_ms: int,
    ) -> SkillExecutorResult: ...


class SkillExecutorRegistry:
    """Composition-owned allowlist; requests never supply an endpoint."""

    def __init__(self, executors: tuple[SkillExecutor, ...]) -> None:
        self._executors = {
            (item.revision.executor_id, item.revision.executor_revision): item
            for item in executors
        }
        if len(self._executors) != len(executors):
            raise SkillInvocationError("EXECUTOR_REGISTRY_CONFLICT")

    def resolve(self, revision: ExecutorRevision) -> SkillExecutor:
        value = self._executors.get((revision.executor_id, revision.executor_revision))
        if (
            value is None
            or value.revision.configuration_digest != revision.configuration_digest
        ):
            raise SkillInvocationError("EXECUTOR_REVISION_UNAVAILABLE")
        return value


class HttpReadOnlySkillExecutor:
    """Calls one composition-configured deterministic HTTP operation boundary."""

    def __init__(
        self,
        *,
        executor_id: str,
        executor_revision: str,
        endpoint: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not endpoint.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise SkillInvocationError("EXECUTOR_ENDPOINT_NOT_ALLOWLISTED")
        self.endpoint = endpoint.rstrip("/")
        self.transport = transport
        self.revision = ExecutorRevision(
            executor_id,
            executor_revision,
            canonical_digest(
                {
                    "adapter": "http-read-only-skill-executor.v1",
                    "endpoint": self.endpoint,
                }
            ),
        )

    def invoke(
        self,
        invocation_id: str,
        operation: str,
        inputs: dict[str, Any],
        timeout_ms: int,
    ) -> SkillExecutorResult:
        request = {
            "schemaVersion": "read-only-skill-request.v1",
            "invocationId": invocation_id,
            "operation": operation,
            "input": inputs,
        }
        try:
            with httpx.Client(
                transport=self.transport, timeout=timeout_ms / 1000.0
            ) as client:
                response = client.post(
                    f"{self.endpoint}/v1/read-only/invoke", json=request
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SkillExecutorFailure(
                "SKILL_EXECUTOR_OUTCOME_UNKNOWN", outcome_unknown=True
            ) from exc
        if response.status_code != 200:
            raise SkillExecutorFailure("SKILL_EXECUTOR_REJECTED", outcome_unknown=False)
        try:
            body = response.json()
        except ValueError as exc:
            raise SkillExecutorFailure(
                "SKILL_EXECUTOR_RESPONSE_INVALID", outcome_unknown=False
            ) from exc
        if (
            not isinstance(body, dict)
            or body.get("schemaVersion") != "read-only-skill-response.v1"
            or body.get("invocationId") != invocation_id
            or body.get("accepted") is not True
            or not isinstance(body.get("output"), dict)
            or not isinstance(body.get("observationId"), str)
            or not body["observationId"]
        ):
            raise SkillExecutorFailure(
                "SKILL_EXECUTOR_RESPONSE_INVALID", outcome_unknown=False
            )
        return SkillExecutorResult(True, body["output"], body["observationId"])
