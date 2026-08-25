"""Internal bridge from current Kubernetes resources to the A2 identity spine."""

from .interpreter import (
    CompatibilityInterpreterError,
    ConflictingIdentityEvidenceError,
    InvalidLegacyEvidenceError,
    MissingDefinitionError,
    interpret_legacy_task,
)

__all__ = [
    "CompatibilityInterpreterError",
    "ConflictingIdentityEvidenceError",
    "InvalidLegacyEvidenceError",
    "MissingDefinitionError",
    "interpret_legacy_task",
]
