"""Explicit failures for the internal A2 identity spine."""

from agent_core.representation.v0_2 import CoreRepresentationError


class InterfaceSpineError(CoreRepresentationError):
    """Base error for A2 projection, selection, and envelope construction."""


class InvalidDefinitionProjectionError(InterfaceSpineError):
    """A Definition-facing logical address is incomplete or invalid."""


class NoEligibleInstanceError(InterfaceSpineError):
    """No eligible Instance exists for a Definition."""


class AmbiguousInstanceSelectionError(InterfaceSpineError):
    """Several candidates exist but the configured policy cannot choose."""


class InvalidSelectedInstanceError(InterfaceSpineError):
    """A selected Instance violates Definition or lifecycle constraints."""


class DuplicateSelectionIdentityError(InterfaceSpineError):
    """The eligible collection repeats an Instance identity."""


class MissingEffectiveBindingError(InterfaceSpineError):
    """A selected Instance has no effective Runtime Binding."""


class NativeIdentitySubstitutionError(InterfaceSpineError):
    """Native evidence was supplied in place of Platform identity."""
