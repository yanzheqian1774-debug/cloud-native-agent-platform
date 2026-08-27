"""Internal Native execution evidence boundary."""

from .domain import (
    AuthorizationDecision,
    AuthorizedReference,
    EvidenceEventType,
    EvidenceValidationError,
    ExecutionEvidenceRecord,
    OutcomeClassification,
    ReferenceType,
    ReferenceVisibility,
    canonical_json,
)
from .ports import (
    AppendDisposition,
    AppendResult,
    AuthorizedEvidenceScope,
    EvidenceDigestConflict,
    EvidenceRepositoryError,
    EvidenceRepositoryUnavailable,
    EvidenceSchemaIncompatible,
    ExecutionEvidenceRepository,
)
from .sqlite import SQLiteExecutionEvidenceRepository

__all__ = [
    "AppendDisposition",
    "AppendResult",
    "AuthorizationDecision",
    "AuthorizedEvidenceScope",
    "AuthorizedReference",
    "EvidenceDigestConflict",
    "EvidenceEventType",
    "EvidenceRepositoryError",
    "EvidenceRepositoryUnavailable",
    "EvidenceSchemaIncompatible",
    "EvidenceValidationError",
    "ExecutionEvidenceRecord",
    "ExecutionEvidenceRepository",
    "OutcomeClassification",
    "ReferenceType",
    "ReferenceVisibility",
    "SQLiteExecutionEvidenceRepository",
    "canonical_json",
]
