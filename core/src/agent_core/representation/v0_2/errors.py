"""Internal errors for the v0.2 Core prototype."""


class CoreRepresentationError(ValueError):
    """Base error for invalid internal Core representation values."""


class InvalidDomainValueError(CoreRepresentationError):
    """A domain value violates a Core invariant."""


class InvalidBindingError(CoreRepresentationError):
    """A Runtime Binding is invalid or used in the wrong ownership seam."""


class InvalidNativeEvidenceError(CoreRepresentationError):
    """Native realization evidence is invalid."""


class InstanceNotFoundError(LookupError):
    """An Agent Instance does not exist in a repository."""


class DuplicateInstanceError(CoreRepresentationError):
    """A new Agent Instance reuses an existing Instance ID."""


class DefinitionOwnershipConflictError(CoreRepresentationError):
    """An update attempts to move an Instance to another Definition."""
