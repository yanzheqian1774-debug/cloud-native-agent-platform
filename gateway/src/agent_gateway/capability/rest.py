"""Transport-injected REST Capability Provider Candidate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from .models import (
    MAX_HEADER_LENGTH,
    MAX_HEADERS,
    Ambiguity,
    AuthorizationDecision,
    CapabilityModelError,
    CapabilityOutcome,
    CapabilityRequest,
    CapabilityStatus,
    InvocationEvidence,
    ProviderIdentity,
    ProviderRequest,
    ProviderResponse,
    _contains_secret,
)

SUPPORTED_CONTENT_TYPES = frozenset({"application/json"})
SUPPORTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


class TransportTimeoutError(TimeoutError):
    """The transport timed out after an attempt may have begun."""


class TransportAmbiguityError(ConnectionError):
    """The transport cannot determine whether remote effects occurred."""


class RestTransport(Protocol):
    def send(self, request: ProviderRequest) -> ProviderResponse: ...


@dataclass(frozen=True, slots=True)
class RestProviderConfiguration:
    provider: ProviderIdentity
    target: str
    method: str = "POST"
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise CapabilityModelError("configured provider identity is invalid")
        parsed = urlparse(self.target)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or _contains_secret(self.target)
        ):
            raise CapabilityModelError("REST target must be an authorized HTTPS URL")
        if self.method not in SUPPORTED_METHODS:
            raise CapabilityModelError("REST method is unsupported")
        if (
            not isinstance(self.headers, Mapping)
            or len(self.headers) > MAX_HEADERS
            or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in self.headers.items()
            )
            or any(
                len(key) > MAX_HEADER_LENGTH or len(value) > MAX_HEADER_LENGTH
                for key, value in self.headers.items()
            )
            or _contains_secret(self.headers)
        ):
            raise CapabilityModelError("REST headers are invalid or secret-like")


class RestProvider:
    def __init__(
        self, configuration: RestProviderConfiguration, transport: RestTransport
    ):
        self._configuration = configuration
        self._transport = transport

    @property
    def identity(self) -> ProviderIdentity:
        return self._configuration.provider

    def invoke(self, request: CapabilityRequest) -> CapabilityOutcome:
        provider_request = ProviderRequest(
            provider=self.identity,
            execution_identity=request.execution_identity,
            method=self._configuration.method,
            target=self._configuration.target,
            headers=self._configuration.headers,
            body={"operation": request.operation, "arguments": dict(request.arguments)},
        )
        try:
            response = self._transport.send(provider_request)
        except TransportTimeoutError:
            return self._outcome(
                request,
                CapabilityStatus.INDETERMINATE,
                "PROVIDER_TIMEOUT_EFFECT_UNKNOWN",
                ambiguity=Ambiguity.TIMEOUT_EFFECT_UNKNOWN,
            )
        except TransportAmbiguityError:
            return self._outcome(
                request,
                CapabilityStatus.INDETERMINATE,
                "PROVIDER_TRANSPORT_EFFECT_UNKNOWN",
                ambiguity=Ambiguity.TRANSPORT_EFFECT_UNKNOWN,
            )
        except Exception:
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_TRANSPORT_FAILED_REDACTED"
            )
        if not isinstance(response, ProviderResponse):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
            )
        if response.native_request_id is not None and (
            response.native_request_id.value == request.execution_identity.value
        ):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_NATIVE_ID_INVALID"
            )
        if response.content_type not in SUPPORTED_CONTENT_TYPES:
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_CONTENT_UNSUPPORTED"
            )
        try:
            evidence = InvocationEvidence(
                attempts=1,
                http_status=response.status_code,
                result=response.body if 200 <= response.status_code < 300 else None,
            )
        except Exception:
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
            )
        if not isinstance(response.status_code, int) or isinstance(
            response.status_code, bool
        ):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
            )
        if 200 <= response.status_code < 300:
            status, diagnostic = (
                CapabilityStatus.SUCCEEDED,
                "CAPABILITY_INVOCATION_SUCCEEDED",
            )
        elif 400 <= response.status_code < 500:
            status, diagnostic = CapabilityStatus.FAILED, "PROVIDER_CLIENT_ERROR"
        elif 500 <= response.status_code < 600:
            status, diagnostic = CapabilityStatus.FAILED, "PROVIDER_SERVER_ERROR"
        else:
            status, diagnostic = CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
        return CapabilityOutcome(
            execution_identity=request.execution_identity,
            capability=request.capability,
            provider=self.identity,
            authorization=AuthorizationDecision.ALLOW,
            status=status,
            diagnostic=diagnostic,
            invocation=evidence,
            native_request_id=response.native_request_id,
        )

    def _outcome(
        self,
        request: CapabilityRequest,
        status: CapabilityStatus,
        diagnostic: str,
        *,
        ambiguity: Ambiguity = Ambiguity.NONE,
    ) -> CapabilityOutcome:
        return CapabilityOutcome(
            execution_identity=request.execution_identity,
            capability=request.capability,
            provider=self.identity,
            authorization=AuthorizationDecision.ALLOW,
            status=status,
            diagnostic=diagnostic,
            invocation=InvocationEvidence(attempts=1),
            ambiguity=ambiguity,
            retry_safe=False,
        )
