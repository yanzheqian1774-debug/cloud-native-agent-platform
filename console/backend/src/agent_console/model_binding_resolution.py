"""Internal, fail-closed resolution of one exact authorized Model use.

The Model owner supplies exact, secret-free records. Authorization remains an
injected port and must complete before any owner lookup. Provider calls,
connection observations, Resource Use, and Evidence are outside this boundary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from agent_console.model_governance import (
    ConnectionProfileRevisionIdentity,
    EndpointRevisionIdentity,
    ModelEligibility,
    ProviderRevisionIdentity,
)

_DIGEST = re.compile(r"[0-9a-f]{64}")


class ModelBindingResolutionFailure(RuntimeError):
    """Stable failure that does not expose an unauthorized Model lookup."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _required(value: object, reason: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ModelBindingResolutionFailure(reason)


def _timestamp(value: object, reason: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None:
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


class ModelUseAction(StrEnum):
    BIND_MODEL = "BIND_MODEL"
    INVOKE_MODEL = "INVOKE_MODEL"


@dataclass(frozen=True, slots=True)
class ExactModelUse:
    binding: ExactModelBinding
    action: ModelUseAction
    exact_resource: str

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ExactModelBinding):
            raise ModelBindingResolutionFailure("MODEL_BINDING_REQUIRED")
        if not isinstance(self.action, ModelUseAction):
            raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")
        _required(self.exact_resource, "MODEL_AUTHORIZATION_INVALID")
        prefix = (
            "model:binding:"
            if self.action is ModelUseAction.BIND_MODEL
            else "model:invocation:"
        )
        suffix = (
            f":{self.binding.resource_id}:{self.binding.revision_id}:"
            f"{self.binding.digest}"
        )
        if (
            not self.exact_resource.startswith(prefix)
            or not self.exact_resource.endswith(suffix)
            or len(self.exact_resource) <= len(prefix) + len(suffix)
        ):
            raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")


@dataclass(frozen=True, slots=True)
class AuthorizedModelUse:
    """One current decision bound to a complete subject/scope/use tuple."""

    decision_id: str
    subject: ModelUseSubject
    scope: ModelConsumptionScope
    use: ExactModelUse
    policy_generation: int
    policy_version: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _required(self.decision_id, "MODEL_AUTHORIZATION_INVALID")
        _required(self.policy_version, "MODEL_AUTHORIZATION_INVALID")
        if (
            isinstance(self.policy_generation, bool)
            or not isinstance(self.policy_generation, int)
            or self.policy_generation < 1
        ):
            raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")
        _timestamp(self.issued_at, "MODEL_AUTHORIZATION_INVALID")
        _timestamp(self.expires_at, "MODEL_AUTHORIZATION_INVALID")
        if self.issued_at >= self.expires_at:
            raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")


@dataclass(frozen=True, slots=True)
class ResolvedModelBinding:
    """Exact, secret-free owner snapshot with typed lifecycle high-water."""

    scope: ModelConsumptionScope
    binding: ExactModelBinding
    provider: ProviderRevisionIdentity
    endpoint: EndpointRevisionIdentity
    connection_profile: ConnectionProfileRevisionIdentity
    eligibility: ModelEligibility

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, expected)
            for value, expected in (
                (self.provider, ProviderRevisionIdentity),
                (self.endpoint, EndpointRevisionIdentity),
                (self.connection_profile, ConnectionProfileRevisionIdentity),
                (self.eligibility, ModelEligibility),
            )
        ):
            raise ModelBindingResolutionFailure("MODEL_RESOLUTION_INVALID")


class ModelUseAuthorizer(Protocol):
    def authorize_use(
        self,
        scope: ModelConsumptionScope,
        subject: ModelUseSubject,
        use: ExactModelUse,
    ) -> AuthorizedModelUse | None: ...


class ExactModelResolver(Protocol):
    def resolve_exact(
        self, scope: ModelConsumptionScope, binding: ExactModelBinding
    ) -> ResolvedModelBinding | None: ...


def resolve_authorized_model_binding(
    scope: ModelConsumptionScope,
    subject: ModelUseSubject,
    use: ExactModelUse,
    *,
    authorizer: ModelUseAuthorizer | None,
    resolver: ExactModelResolver | None,
    evaluation_time: datetime,
) -> ResolvedModelBinding:
    """Authorize first, then resolve and validate one exact Model binding."""
    _timestamp(evaluation_time, "MODEL_AUTHORIZATION_INVALID")
    if authorizer is None:
        raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_UNAVAILABLE")
    authorization = authorizer.authorize_use(scope, subject, use)
    if authorization is None:
        raise ModelBindingResolutionFailure("MODEL_BINDING_NOT_FOUND")
    if (
        authorization.scope != scope
        or authorization.subject != subject
        or authorization.use != use
        or not (authorization.issued_at <= evaluation_time < authorization.expires_at)
    ):
        raise ModelBindingResolutionFailure("MODEL_AUTHORIZATION_INVALID")

    if resolver is None:
        raise ModelBindingResolutionFailure("MODEL_RESOLVER_UNAVAILABLE")
    binding = use.binding
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
    if resolved.eligibility.scope.namespace != scope.namespace or (
        resolved.eligibility.scope.security_domain != scope.security_domain
    ):
        raise ModelBindingResolutionFailure("MODEL_SCOPE_MISMATCH")
    if (
        resolved.eligibility.model.model_id != binding.resource_id
        or resolved.eligibility.model.revision_id != binding.revision_id
        or resolved.eligibility.model.digest != binding.digest
    ):
        raise ModelBindingResolutionFailure("MODEL_ELIGIBILITY_MISMATCH")
    if not resolved.eligibility.allows_new_use:
        raise ModelBindingResolutionFailure("MODEL_INELIGIBLE")
    return resolved
