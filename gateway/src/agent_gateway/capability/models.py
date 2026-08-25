"""Immutable internal Capability candidate values.

These structures are deliberately unfrozen, non-serializing implementation
types. They are not a Core resource, public API, CRD, or universal Outcome.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from agent_core.representation.v0_2 import PlatformExecutionIdentity

MAX_REQUEST_BYTES = 65_536
MAX_EVIDENCE_BYTES = 65_536
MAX_HEADERS = 32
MAX_HEADER_LENGTH = 1_024
SECRET_MARKERS = frozenset(
    {"authorization", "credential", "password", "secret", "token", "apikey"}
)
SECRET_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    re.compile(r"(?i)^bearer\s+[a-z0-9._~+/=-]{8,}$"),
    re.compile(r"(?i)^(?:sk|rk|pk)[-_](?:test[-_])?[a-z0-9]{16,}$"),
)


class CapabilityModelError(ValueError):
    """Stable validation failure without caller data in its message."""


def _required(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise CapabilityModelError(f"{name} is required")


def _secret_key(value: str) -> bool:
    normalized = "".join(
        character for character in value.casefold() if character.isalnum()
    )
    return any(marker in normalized for marker in SECRET_MARKERS)


def _contains_secret(value: object) -> bool:
    stack = [value]
    seen: set[int] = set()
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if any(pattern.search(item) for pattern in SECRET_VALUE_PATTERNS):
                return True
        elif isinstance(item, Mapping):
            if id(item) in seen:
                raise CapabilityModelError("cyclic mappings are unsupported")
            seen.add(id(item))
            for key, nested in item.items():
                if isinstance(key, str) and _secret_key(key):
                    return True
                stack.append(nested)
        elif isinstance(item, (list, tuple)):
            if id(item) in seen:
                raise CapabilityModelError("cyclic sequences are unsupported")
            seen.add(id(item))
            stack.extend(item)
    return False


def _frozen_json_mapping(
    value: Mapping[str, Any], *, name: str, max_bytes: int
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise CapabilityModelError(f"{name} must be a string-keyed mapping")
    if _contains_secret(value):
        raise CapabilityModelError(f"{name} contains a secret-like key")
    try:
        copied = deepcopy(dict(value))
        encoded = json.dumps(copied, separators=(",", ":"), sort_keys=True).encode()
    except Exception:
        raise CapabilityModelError(f"{name} must contain bounded JSON values") from None
    if len(encoded) > max_bytes:
        raise CapabilityModelError(f"{name} exceeds the size boundary")
    return MappingProxyType(copied)


@dataclass(frozen=True, slots=True)
class CapabilityIdentity:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "capability identity")


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "provider identity")


@dataclass(frozen=True, slots=True)
class ProviderNativeRequestId:
    value: str

    def __post_init__(self) -> None:
        _required(self.value, "provider-native request ID")


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    capability: CapabilityIdentity
    operation: str
    execution_identity: PlatformExecutionIdentity
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.capability, CapabilityIdentity):
            raise CapabilityModelError("capability identity has the wrong type")
        _required(self.operation, "capability operation")
        if not isinstance(self.execution_identity, PlatformExecutionIdentity):
            raise CapabilityModelError("Platform Execution Identity is required")
        object.__setattr__(
            self,
            "arguments",
            _frozen_json_mapping(
                self.arguments, name="capability arguments", max_bytes=MAX_REQUEST_BYTES
            ),
        )


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    subject: str
    tenant: str
    execution_identity: PlatformExecutionIdentity
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _required(self.subject, "authorization subject")
        _required(self.tenant, "authorization tenant")
        if not isinstance(self.execution_identity, PlatformExecutionIdentity):
            raise CapabilityModelError("authorization Platform identity is required")
        object.__setattr__(
            self,
            "attributes",
            _frozen_json_mapping(
                self.attributes,
                name="authorization attributes",
                max_bytes=MAX_REQUEST_BYTES,
            ),
        )


class AuthorizationDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class DecisionReason:
    code: str

    def __post_init__(self) -> None:
        _required(self.code, "decision reason")
        if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.code) is None:
            raise CapabilityModelError("decision reason must be a stable code")


@dataclass(frozen=True, slots=True)
class AuthorizationResult:
    decisions: tuple[AuthorizationDecision | str, ...]
    reason: DecisionReason

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        if not isinstance(self.reason, DecisionReason):
            raise CapabilityModelError("authorization reason has the wrong type")


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    provider: ProviderIdentity
    execution_identity: PlatformExecutionIdentity
    method: str
    target: str
    headers: Mapping[str, str]
    body: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.provider, ProviderIdentity):
            raise CapabilityModelError("provider identity has the wrong type")
        if not isinstance(self.execution_identity, PlatformExecutionIdentity):
            raise CapabilityModelError("Provider request requires Platform identity")
        if self.method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise CapabilityModelError("REST method is unsupported")
        _required(self.target, "REST target")
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
        object.__setattr__(
            self,
            "body",
            _frozen_json_mapping(
                self.body, name="REST body", max_bytes=MAX_REQUEST_BYTES
            ),
        )


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    status_code: int
    body: Mapping[str, Any]
    native_request_id: ProviderNativeRequestId | None = None
    content_type: str = "application/json"


class CapabilityStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"


class Ambiguity(StrEnum):
    NONE = "NONE"
    TIMEOUT_EFFECT_UNKNOWN = "TIMEOUT_EFFECT_UNKNOWN"
    TRANSPORT_EFFECT_UNKNOWN = "TRANSPORT_EFFECT_UNKNOWN"


@dataclass(frozen=True, slots=True)
class InvocationEvidence:
    attempts: int
    http_status: int | None = None
    result: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.attempts not in {0, 1}:
            raise CapabilityModelError(
                "invocation evidence must contain zero or one attempt"
            )
        if self.result is not None:
            object.__setattr__(
                self,
                "result",
                _frozen_json_mapping(
                    self.result, name="result evidence", max_bytes=MAX_EVIDENCE_BYTES
                ),
            )


@dataclass(frozen=True, slots=True)
class CapabilityOutcome:
    execution_identity: PlatformExecutionIdentity
    capability: CapabilityIdentity
    provider: ProviderIdentity
    authorization: AuthorizationDecision
    status: CapabilityStatus
    diagnostic: str
    invocation: InvocationEvidence
    ambiguity: Ambiguity = Ambiguity.NONE
    native_request_id: ProviderNativeRequestId | None = None
    retry_safe: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.execution_identity, PlatformExecutionIdentity):
            raise CapabilityModelError("Outcome requires Platform identity")
        _required(self.diagnostic, "stable diagnostic")
        if self.native_request_id is not None and (
            self.native_request_id.value == self.execution_identity.value
        ):
            raise CapabilityModelError(
                "native request ID cannot replace Platform identity"
            )
