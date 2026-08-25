"""Replaceable internal ports for authorization and Capability invocation."""

from typing import Protocol

from .models import (
    AuthorizationContext,
    AuthorizationResult,
    CapabilityOutcome,
    CapabilityRequest,
    ProviderIdentity,
)


class AuthorizationDecisionPort(Protocol):
    def decide(
        self, request: CapabilityRequest, context: AuthorizationContext
    ) -> AuthorizationResult | None: ...


class CapabilityProvider(Protocol):
    @property
    def identity(self) -> ProviderIdentity: ...

    def invoke(self, request: CapabilityRequest) -> CapabilityOutcome: ...
