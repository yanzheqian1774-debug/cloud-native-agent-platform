"""Agent-facing experiment code with no REST/MCP semantic knowledge."""

from dataclasses import dataclass

from capability_contract import (
    CapabilityBinding,
    CapabilityIdentity,
    CapabilityProvider,
    CapabilityRequest,
    CapabilityResult,
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
) -> CapabilityResult:
    decision = policy.authorize(agent_id, binding)
    if not decision.allowed:
        return CapabilityResult(
            status=ResultStatus.DENIED,
            correlation_id=correlation_id,
            error_code="capability_not_authorized",
            message=decision.reason,
        )

    request = CapabilityRequest(
        capability=CapabilityIdentity(
            binding.capability.capability_id, binding.capability.version
        ),
        operation=binding.operation,
        input=input_data,
        correlation_id=correlation_id,
    )
    handle = provider.start(request)
    return provider.result(handle)
