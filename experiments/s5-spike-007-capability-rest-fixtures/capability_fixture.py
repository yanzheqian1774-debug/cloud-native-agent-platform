"""Disposable S5-SPIKE-007 Capability/REST fixture harness.

This module is experimental evidence, not a public Capability Contract or a
production Provider implementation.
"""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class CapabilityRequest:
    capability_id: str
    operation: str
    platform_execution_identity: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True)
class AuthorizationContext:
    subject_id: str
    tenant_id: str
    platform_execution_identity: str
    decision: Decision | str | None


@dataclass(frozen=True)
class ProviderResponse:
    status_code: int
    body: Any
    provider_request_id: str | None = None


@dataclass(frozen=True)
class CapabilityOutcome:
    status: str
    reason: str
    platform_execution_identity: str
    capability_id: str
    capability_provider_id: str
    provider_request_id: str | None
    result: Any
    provider_invoked: bool
    retry_safe: bool
    transport_ambiguous: bool


class TransportTimeout(TimeoutError):
    """Synthetic timeout where remote side effects cannot be determined."""


class TransportAmbiguity(ConnectionError):
    """Synthetic transport failure after invocation may have begun."""


class ScriptedRestProvider:
    """Deterministic synthetic REST double with bounded invocation evidence."""

    def __init__(self, provider_id: str, script: list[ProviderResponse | Exception]):
        self.provider_id = provider_id
        self._script = list(script)
        self.call_count = 0
        self.requests: list[dict[str, Any]] = []

    def invoke(self, request: CapabilityRequest) -> ProviderResponse:
        self.call_count += 1
        self.requests.append(
            {
                "capability_id": request.capability_id,
                "operation": request.operation,
                "platform_execution_identity": request.platform_execution_identity,
                "arguments": deepcopy(dict(request.arguments)),
            }
        )
        if self.call_count > len(self._script):
            raise AssertionError("UNSCRIPTED_PROVIDER_INVOCATION")
        step = self._script[self.call_count - 1]
        if isinstance(step, Exception):
            raise step
        return step


def frozen_arguments(arguments: Mapping[str, Any]) -> Mapping[str, Any]:
    """Copy caller data and expose a read-only top-level mapping."""

    return MappingProxyType(deepcopy(dict(arguments)))


def execute(
    request: CapabilityRequest,
    authorization: AuthorizationContext | None,
    provider: ScriptedRestProvider,
) -> CapabilityOutcome:
    """Apply authorization before one bounded Provider invocation."""

    rejection = _authorization_rejection(request, authorization)
    if rejection:
        return _outcome(request, provider, "DENIED", rejection, invoked=False)

    try:
        response = provider.invoke(request)
    except TransportTimeout:
        return _outcome(
            request,
            provider,
            "INDETERMINATE",
            "PROVIDER_TIMEOUT_EFFECT_UNKNOWN",
            invoked=True,
            ambiguous=True,
        )
    except TransportAmbiguity:
        return _outcome(
            request,
            provider,
            "INDETERMINATE",
            "PROVIDER_TRANSPORT_EFFECT_UNKNOWN",
            invoked=True,
            ambiguous=True,
        )

    if not isinstance(response.status_code, int) or not isinstance(response.body, dict):
        return _outcome(
            request, provider, "FAILED", "PROVIDER_RESPONSE_MALFORMED", invoked=True
        )
    if 200 <= response.status_code < 300:
        return _outcome(
            request,
            provider,
            "SUCCEEDED",
            "CAPABILITY_INVOCATION_SUCCEEDED",
            invoked=True,
            provider_request_id=response.provider_request_id,
            result=deepcopy(response.body),
        )
    if 400 <= response.status_code < 500:
        reason = "PROVIDER_CLIENT_ERROR"
    elif 500 <= response.status_code < 600:
        reason = "PROVIDER_SERVER_ERROR"
    else:
        reason = "PROVIDER_RESPONSE_MALFORMED"
    return _outcome(
        request,
        provider,
        "FAILED",
        reason,
        invoked=True,
        provider_request_id=response.provider_request_id,
    )


def _authorization_rejection(
    request: CapabilityRequest, authorization: AuthorizationContext | None
) -> str | None:
    if authorization is None or authorization.decision is None:
        return "AUTHORIZATION_DECISION_MISSING"
    if not authorization.subject_id or not authorization.tenant_id:
        return "AUTHORIZATION_CONTEXT_MALFORMED"
    if authorization.platform_execution_identity != request.platform_execution_identity:
        return "AUTHORIZATION_CONTEXT_IDENTITY_MISMATCH"
    if authorization.decision == Decision.DENY:
        return "AUTHORIZATION_DENIED"
    if authorization.decision != Decision.ALLOW:
        return "AUTHORIZATION_DECISION_AMBIGUOUS"
    return None


def _outcome(
    request: CapabilityRequest,
    provider: ScriptedRestProvider,
    status: str,
    reason: str,
    *,
    invoked: bool,
    ambiguous: bool = False,
    provider_request_id: str | None = None,
    result: Any = None,
) -> CapabilityOutcome:
    return CapabilityOutcome(
        status=status,
        reason=reason,
        platform_execution_identity=request.platform_execution_identity,
        capability_id=request.capability_id,
        capability_provider_id=provider.provider_id,
        provider_request_id=provider_request_id,
        result=result,
        provider_invoked=invoked,
        retry_safe=False,
        transport_ambiguous=ambiguous,
    )
