"""Internal Native execution evidence boundary."""

from .domain import (
    AuthorizationDecision,
    EvidenceEventType,
    EvidenceValidationError,
    ExecutionEvidenceRecord,
    OutcomeClassification,
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
    "EvidenceDigestConflict",
    "EvidenceEventType",
    "EvidenceRepositoryError",
    "EvidenceRepositoryUnavailable",
    "EvidenceSchemaIncompatible",
    "EvidenceValidationError",
    "ExecutionEvidenceRecord",
    "ExecutionEvidenceRepository",
    "OutcomeClassification",
    "SQLiteExecutionEvidenceRepository",
    "canonical_json",
]
