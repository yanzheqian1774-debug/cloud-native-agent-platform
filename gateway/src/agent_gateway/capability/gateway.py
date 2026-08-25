"""Authorization-before-invocation Capability orchestration."""

from .models import (
    Ambiguity,
    AuthorizationContext,
    AuthorizationDecision,
    CapabilityOutcome,
    CapabilityRequest,
    CapabilityStatus,
    InvocationEvidence,
)
from .ports import AuthorizationDecisionPort, CapabilityProvider


class CapabilityGateway:
    def __init__(
        self,
        authorization: AuthorizationDecisionPort,
        provider: CapabilityProvider,
    ) -> None:
        self._authorization = authorization
        self._provider = provider

    def execute(
        self, request: CapabilityRequest, context: AuthorizationContext
    ) -> CapabilityOutcome:
        if (
            not isinstance(context, AuthorizationContext)
            or context.execution_identity != request.execution_identity
        ):
            return self._denied(request, "AUTHORIZATION_CONTEXT_INVALID")
        try:
            result = self._authorization.decide(request, context)
        except Exception:
            return self._denied(request, "AUTHORIZATION_DECISION_UNAVAILABLE")
        if result is None:
            return self._denied(request, "AUTHORIZATION_DECISION_MISSING")
        decisions = result.decisions
        if len(decisions) != 1:
            return self._denied(request, "AUTHORIZATION_DECISION_AMBIGUOUS")
        decision = decisions[0]
        if not isinstance(decision, AuthorizationDecision):
            return self._denied(request, "AUTHORIZATION_DECISION_UNKNOWN")
        if decision is AuthorizationDecision.DENY:
            return self._denied(request, f"DENIED_{result.reason.code}")
        if decision is not AuthorizationDecision.ALLOW:
            return self._denied(request, "AUTHORIZATION_DECISION_UNKNOWN")
        try:
            outcome = self._provider.invoke(request)
        except Exception:
            return CapabilityOutcome(
                execution_identity=request.execution_identity,
                capability=request.capability,
                provider=self._provider.identity,
                authorization=AuthorizationDecision.ALLOW,
                status=CapabilityStatus.FAILED,
                diagnostic="PROVIDER_INVOCATION_FAILED_REDACTED",
                invocation=InvocationEvidence(attempts=1),
            )
        if (
            outcome.execution_identity != request.execution_identity
            or outcome.capability != request.capability
            or outcome.provider != self._provider.identity
            or outcome.authorization is not AuthorizationDecision.ALLOW
        ):
            return CapabilityOutcome(
                execution_identity=request.execution_identity,
                capability=request.capability,
                provider=self._provider.identity,
                authorization=AuthorizationDecision.ALLOW,
                status=CapabilityStatus.FAILED,
                diagnostic="PROVIDER_EVIDENCE_INVALID",
                invocation=InvocationEvidence(attempts=1),
            )
        return outcome

    def _denied(self, request: CapabilityRequest, diagnostic: str) -> CapabilityOutcome:
        return CapabilityOutcome(
            execution_identity=request.execution_identity,
            capability=request.capability,
            provider=self._provider.identity,
            authorization=AuthorizationDecision.DENY,
            status=CapabilityStatus.DENIED,
            diagnostic=diagnostic,
            invocation=InvocationEvidence(attempts=0),
            ambiguity=Ambiguity.NONE,
        )
