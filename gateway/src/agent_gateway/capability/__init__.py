"""Bounded internal Capability Gateway and REST Provider Candidate."""

from .gateway import CapabilityGateway
from .models import (
    Ambiguity,
    AuthorizationContext,
    AuthorizationDecision,
    AuthorizationResult,
    CapabilityIdentity,
    CapabilityOutcome,
    CapabilityRequest,
    CapabilityStatus,
    DecisionReason,
    InvocationEvidence,
    ProviderIdentity,
    ProviderNativeRequestId,
    ProviderRequest,
    ProviderResponse,
)
from .ports import AuthorizationDecisionPort, CapabilityProvider
from .rest import (
    RestProvider,
    RestProviderConfiguration,
    RestTransport,
    TransportAmbiguityError,
    TransportTimeoutError,
)

__all__ = [
    "Ambiguity",
    "AuthorizationContext",
    "AuthorizationDecision",
    "AuthorizationDecisionPort",
    "AuthorizationResult",
    "CapabilityGateway",
    "CapabilityIdentity",
    "CapabilityOutcome",
    "CapabilityProvider",
    "CapabilityRequest",
    "CapabilityStatus",
    "DecisionReason",
    "InvocationEvidence",
    "ProviderIdentity",
    "ProviderNativeRequestId",
    "ProviderRequest",
    "ProviderResponse",
    "RestProvider",
    "RestProviderConfiguration",
    "RestTransport",
    "TransportAmbiguityError",
    "TransportTimeoutError",
]
