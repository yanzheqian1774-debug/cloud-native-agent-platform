"""Transport-injected REST Capability Provider Candidate."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
from types import MappingProxyType
from typing import Protocol
from urllib.parse import urlparse, urlunparse

from .models import (
    MAX_EVIDENCE_BYTES,
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
    ProviderNativeRequestId,
    ProviderRequest,
    ProviderResponse,
    _contains_secret,
    _frozen_json_mapping,
)

SUPPORTED_CONTENT_TYPES = frozenset({"application/json"})
SUPPORTED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})


class TransportTimeoutError(TimeoutError):
    """The transport timed out after an attempt may have begun."""


class TransportAmbiguityError(ConnectionError):
    """The transport cannot determine whether remote effects occurred."""


class RestTransport(Protocol):
    """One-attempt seam; implementations must not redirect, retry, or retarget."""

    def send(self, request: ProviderRequest) -> ProviderResponse: ...


@dataclass(frozen=True, slots=True)
class RestProviderConfiguration:
    provider: ProviderIdentity
    target: str
    allowed_hosts: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    method: str = "POST"
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise CapabilityModelError("configured provider identity is invalid")
        parsed = urlparse(self.target)
        host = parsed.hostname
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or host is None
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or _contains_secret(self.target)
        ):
            raise CapabilityModelError("REST target must be an authorized HTTPS URL")
        try:
            port = parsed.port
        except ValueError:
            raise CapabilityModelError("REST target port is invalid") from None
        canonical_host = host.casefold().rstrip(".")
        if not canonical_host or host != canonical_host or port not in {None, 443}:
            raise CapabilityModelError("REST target is not canonical")
        try:
            ip_address(canonical_host)
        except ValueError:
            pass
        else:
            raise CapabilityModelError("literal-IP REST targets are unsupported")
        if (
            canonical_host == "localhost"
            or canonical_host.endswith((".localhost", ".local", ".internal"))
            or "." not in canonical_host
            or re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", canonical_host)
            is None
        ):
            raise CapabilityModelError("local or invalid REST target is unsupported")
        if not isinstance(self.allowed_hosts, tuple):
            raise CapabilityModelError("REST allowed hosts must be an immutable tuple")
        allowed_hosts = tuple(self.allowed_hosts)
        if (
            not allowed_hosts
            or any(
                not isinstance(item, str)
                or item != item.casefold().rstrip(".")
                or re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", item) is None
                for item in allowed_hosts
            )
            or canonical_host not in allowed_hosts
        ):
            raise CapabilityModelError("REST target host is not authorized")
        if not isinstance(self.allowed_operations, tuple):
            raise CapabilityModelError("REST operations must be an immutable tuple")
        operations = tuple(self.allowed_operations)
        if not operations or any(
            not isinstance(item, str)
            or re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", item) is None
            for item in operations
        ):
            raise CapabilityModelError("REST operation configuration is invalid")
        object.__setattr__(self, "allowed_hosts", allowed_hosts)
        object.__setattr__(self, "allowed_operations", operations)
        object.__setattr__(
            self,
            "target",
            urlunparse(("https", canonical_host, parsed.path or "/", "", "", "")),
        )
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
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


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
        if request.operation not in self._configuration.allowed_operations:
            return self._outcome(
                request,
                CapabilityStatus.FAILED,
                "REST_OPERATION_UNAUTHORIZED",
                attempts=0,
            )
        provider_request = ProviderRequest(
            provider=self.identity,
            execution_identity=request.execution_identity,
            method=self._configuration.method,
            target=self._configuration.target,
            headers=self._configuration.headers,
            body={"operation": request.operation, "arguments": dict(request.arguments)},
            follow_redirects=False,
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
        try:
            response_body = _frozen_json_mapping(
                response.body,
                name="REST response",
                max_bytes=MAX_EVIDENCE_BYTES,
            )
        except CapabilityModelError:
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
            )
        if response.native_request_id is not None and not isinstance(
            response.native_request_id, ProviderNativeRequestId
        ):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_RESPONSE_MALFORMED"
            )
        if response.native_request_id is not None and (
            response.native_request_id.value == request.execution_identity.value
        ):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_NATIVE_ID_INVALID"
            )
        if (
            not isinstance(response.content_type, str)
            or response.content_type not in SUPPORTED_CONTENT_TYPES
        ):
            return self._outcome(
                request, CapabilityStatus.FAILED, "PROVIDER_CONTENT_UNSUPPORTED"
            )
        try:
            evidence = InvocationEvidence(
                attempts=1,
                http_status=response.status_code,
                result=response_body if 200 <= response.status_code < 300 else None,
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
        attempts: int = 1,
    ) -> CapabilityOutcome:
        return CapabilityOutcome(
            execution_identity=request.execution_identity,
            capability=request.capability,
            provider=self.identity,
            authorization=AuthorizationDecision.ALLOW,
            status=status,
            diagnostic=diagnostic,
            invocation=InvocationEvidence(attempts=attempts),
            ambiguity=ambiguity,
            retry_safe=False,
        )
