"""Intentional exports for the internal, unfrozen A2 interface spine."""

from .builder import ExecutionEnvelopeBuilder, ExecutionIdentityMinter
from .envelope import InternalExecutionEnvelope, SourceTaskRef
from .errors import (
    AmbiguousInstanceSelectionError,
    DuplicateSelectionIdentityError,
    InterfaceSpineError,
    InvalidDefinitionProjectionError,
    InvalidSelectedInstanceError,
    MissingEffectiveBindingError,
    NativeIdentitySubstitutionError,
    NoEligibleInstanceError,
)
from .projection import DefinitionFacingRequest, project_definition
from .selection import (
    ROUTING_POLICY,
    DeterministicPrototypeInstanceSelector,
    InstanceSelectionRequest,
    InstanceSelector,
    RejectAmbiguousInstanceSelector,
    SelectedInstanceResult,
    select_deterministically,
)

__all__ = [
    "ROUTING_POLICY",
    "AmbiguousInstanceSelectionError",
    "DefinitionFacingRequest",
    "DeterministicPrototypeInstanceSelector",
    "DuplicateSelectionIdentityError",
    "ExecutionEnvelopeBuilder",
    "ExecutionIdentityMinter",
    "InstanceSelectionRequest",
    "InstanceSelector",
    "InterfaceSpineError",
    "InternalExecutionEnvelope",
    "InvalidDefinitionProjectionError",
    "InvalidSelectedInstanceError",
    "MissingEffectiveBindingError",
    "NativeIdentitySubstitutionError",
    "NoEligibleInstanceError",
    "RejectAmbiguousInstanceSelector",
    "SelectedInstanceResult",
    "SourceTaskRef",
    "project_definition",
    "select_deterministically",
]
