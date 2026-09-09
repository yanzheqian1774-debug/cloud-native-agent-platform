"""Internal, fail-closed preparation for exact Model consumption.

This module does not own Models or define the external authorization vocabulary.
Callers must supply both an authorization result and a domain-owned exact resolver.
Provider connection and invocation evidence are deliberately outside this boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_DIGEST = re.compile(r"[0-9a-f]{64}")


class ModelBindingResolutionFailure(RuntimeError):
    """Stable failure that does not expose an unauthorized Model lookup."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _required(value: object, reason: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelBindingResolutionFailure(reason)


@dataclass(frozen=True, slots=True)
class ModelConsumptionScope:
    namespace: str
    security_domain: str

    def __post_init__(self) -> None:
        _required(self.namespace, "MODEL_SCOPE_REQUIRED")
        _required(self.security_domain, "MODEL_SCOPE_REQUIRED")


@dataclass(frozen=True, slots=True)
class ModelUseSubject:
    principal_id: str

    def __post_init__(self) -> None:
        _required(self.principal_id, "MODEL_SUBJECT_REQUIRED")


@dataclass(frozen=True, slots=True)
class ExactModelBinding:
    resource_id: str
    revision_id: str
    digest: str

    def __post_init__(self) -> None:
        _required(self.resource_id, "MODEL_IDENTITY_REQUIRED")
        _required(self.revision_id, "MODEL_REVISION_REQUIRED")
        if not isinstance(self.digest, str) or _DIGEST.fullmatch(self.digest) is None:
            raise ModelBindingResolutionFailure("MODEL_DIGEST_REQUIRED")


@dataclass(frozen=True, slots=True)
class AuthorizedModelUse:
    """Opaque authorization proof bound to one subject, scope, and exact binding.

    The external authority remains responsible for its owner/action/resource
    vocabulary. This value only prevents a consumer from applying a decision to a
    different subject, scope, revision, or digest.
    """

    decision_id: str
    subject: ModelUseSubject
    scope: ModelConsumptionScope
    binding: ExactModelBinding

    def __post_init__(self) -> None:
        _required(self.decision_id, "MODEL_AUTHORIZATION_INVALID")


@dataclass(frozen=True, slots=True)
class ResolvedModelBinding:
    """Exact, secret-free readback supplied by a future domain-owned resolver."""

    scope: ModelConsumptionScope
    binding: ExactModelBinding
    provider_reference: str
    connection_profile_reference: str
    published: bool
    enabled: bool
    configuration_available: bool

    def __post_init__(self) -> None:
        _required(self.provider_reference, "MODEL_PROVIDER_REFERENCE_REQUIRED")
        _required(
            self.connection_profile_reference,
            "MODEL_CONNECTION_PROFILE_REFERENCE_REQUIRED",
        )
        if not all(
            isinstance(value, bool)
            for value in (self.published, self.enabled, self.configuration_available)
        ):
            raise ModelBindingResolutionFailure("MODEL_RESOLUTION_INVALID")


class ModelUseAuthorizer(Protocol):
    def authorize_use(
        self,
        scope: ModelConsumptionScope,
        subject: ModelUseSubject,
        binding: ExactModelBinding,
    ) -> AuthorizedModelUse | None: ...


class ExactModelResolver(Protocol):
    def resolve_exact(
        self, scope: ModelConsumptionScope, binding: ExactModelBinding
    ) -> ResolvedModelBinding | None: ...


def resolve_authorized_model_binding(
    scope: ModelConsumptionScope,
    subject: ModelUseSubject,
    binding: ExactModelBinding,
    *,
    authorizer: ModelUseAuthorizer | None,
    resolver: ExactModelResolver | None,
) -> ResolvedModelBinding:
    """Authorize first, then resolve and validate one exact Model binding.

    No default, display-name, latest-revision, provider call, or Evidence lookup is
    permitted by this function.
    """
    if authorizer is None:
        raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_UNAVAILABLE")
    authorization = authorizer.authorize_use(scope, subject, binding)
    if authorization is None:
        raise ModelBindingResolutionFailure("MODEL_BINDING_NOT_FOUND")
    if (
        authorization.scope != scope
        or authorization.subject != subject
        or authorization.binding != binding
    ):
        raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")

    if resolver is None:
        raise ModelBindingResolutionFailure("MODEL_RESOLVER_UNAVAILABLE")
    resolved = resolver.resolve_exact(scope, binding)
    if resolved is None:
        raise ModelBindingResolutionFailure("MODEL_BINDING_NOT_FOUND")
    if resolved.scope != scope:
        raise ModelBindingResolutionFailure("MODEL_SCOPE_MISMATCH")
    if resolved.binding.resource_id != binding.resource_id:
        raise ModelBindingResolutionFailure("MODEL_IDENTITY_MISMATCH")
    if resolved.binding.revision_id != binding.revision_id:
        raise ModelBindingResolutionFailure("MODEL_REVISION_MISMATCH")
    if resolved.binding.digest != binding.digest:
        raise ModelBindingResolutionFailure("MODEL_DIGEST_MISMATCH")
    if not resolved.published:
        raise ModelBindingResolutionFailure("MODEL_UNPUBLISHED")
    if not resolved.enabled:
        raise ModelBindingResolutionFailure("MODEL_DISABLED")
    if not resolved.configuration_available:
        raise ModelBindingResolutionFailure("MODEL_CONFIGURATION_UNAVAILABLE")
    return resolved
