"""Agent-facing experiment code with no REST/MCP semantic knowledge."""

from dataclasses import dataclass
from uuid import uuid4

from capability_contract import (
    CapabilityBinding,
    CapabilityIdentity,
    CapabilityProvider,
    CapabilityRequest,
    CapabilityResult,
    ErrorClass,
    ExecutionIdentity,
    ResultStatus,
)


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str


class BindingPolicy:
    def __init__(self, allowed: set[tuple[str, str, str]]) -> None:
        self._allowed = allowed

    def authorize(
        self, agent_id: str, binding: CapabilityBinding
    ) -> AuthorizationDecision:
        key = (agent_id, binding.capability.capability_id, binding.operation)
        return AuthorizationDecision(key in self._allowed, "binding-policy")


def execute(
    *,
    agent_id: str,
    binding: CapabilityBinding,
    provider: CapabilityProvider,
    policy: BindingPolicy,
    input_data: dict[str, object],
    correlation_id: str,
    invocation_id: str | None = None,
) -> CapabilityResult:
    execution = ExecutionIdentity(invocation_id or str(uuid4()), correlation_id)
    decision = policy.authorize(agent_id, binding)
    if not decision.allowed:
        return CapabilityResult(
            status=ResultStatus.DENIED,
            invocation_id=execution.invocation_id,
            correlation_id=correlation_id,
            error_class=ErrorClass.AUTHORIZATION_DENIED,
            message=decision.reason,
        )

    request = CapabilityRequest(
        capability=CapabilityIdentity(
            binding.capability.capability_id, binding.capability.version
        ),
        operation=binding.operation,
        input=input_data,
        execution=execution,
    )
    submission = provider.submit(request)
    if submission.outcome is not None:
        return submission.outcome
    return provider.observe(submission.handle)
