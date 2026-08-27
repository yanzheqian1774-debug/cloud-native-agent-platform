"""Replaceable repository port and bounded failure vocabulary."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .domain import ExecutionEvidenceRecord


class EvidenceRepositoryError(RuntimeError):
    reason_code = "EVIDENCE_REPOSITORY_ERROR"


class EvidenceRepositoryUnavailable(EvidenceRepositoryError):
    reason_code = "EVIDENCE_REPOSITORY_UNAVAILABLE"


class EvidenceSchemaIncompatible(EvidenceRepositoryError):
    reason_code = "EVIDENCE_SCHEMA_INCOMPATIBLE"


class EvidenceDigestConflict(EvidenceRepositoryError):
    reason_code = "EVIDENCE_DIGEST_CONFLICT"


@dataclass(frozen=True, slots=True)
class AuthorizedEvidenceScope:
    namespace: str
    security_domain: str

    def __post_init__(self) -> None:
        if not self.namespace.strip() or not self.security_domain.strip():
            raise ValueError("AUTHORIZED_EVIDENCE_SCOPE_REQUIRED")


class AppendDisposition(StrEnum):
    APPENDED = "APPENDED"
    REPLAYED = "REPLAYED"


@dataclass(frozen=True, slots=True)
class AppendResult:
    disposition: AppendDisposition
    record: ExecutionEvidenceRecord


class ExecutionEvidenceRepository(Protocol):
    def append(self, record: ExecutionEvidenceRecord) -> AppendResult: ...

    def high_water_mark(self, scope: AuthorizedEvidenceScope) -> int: ...

    def read_execution(
        self,
        scope: AuthorizedEvidenceScope,
        platform_execution_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]: ...

    def read_subject(
        self,
        scope: AuthorizedEvidenceScope,
        workflow_identity: str,
        task_identity: str,
        *,
        through_high_water_mark: int,
    ) -> tuple[ExecutionEvidenceRecord, ...]: ...
