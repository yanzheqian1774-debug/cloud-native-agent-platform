"""Persistence-only values for v0.2.3 Execution Authority Track A."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from agent_core.execution_contract import CommandId, CommandResult, ScopeIdentity


class ExecutionPersistenceError(RuntimeError):
    reason_code = "EXECUTION_PERSISTENCE_ERROR"


class ExecutionConflict(ExecutionPersistenceError):
    reason_code = "EXECUTION_CONFLICT"


class ExecutionSchemaIncompatible(ExecutionPersistenceError):
    reason_code = "EXECUTION_SCHEMA_INCOMPATIBLE"


class ExecutionStorageUnavailable(ExecutionPersistenceError):
    reason_code = "EXECUTION_STORAGE_UNAVAILABLE"


class CutoverState(StrEnum):
    SQLITE_ACTIVE = "SQLITE_ACTIVE"
    IMPORTING = "IMPORTING"
    POSTGRES_ACTIVE = "POSTGRES_ACTIVE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"


class Writer(StrEnum):
    SQLITE = "SQLITE"
    NONE = "NONE"
    POSTGRES = "POSTGRES"


def record_digest(record: dict[str, Any]) -> str:
    payload = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class VersionedAggregate:
    scope: ScopeIdentity
    aggregate_id: str
    aggregate_version: int
    record: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise ExecutionPersistenceError("EXECUTION_SCOPE_REQUIRED")
        if not self.aggregate_id or not 1 <= len(self.aggregate_id.encode()) <= 200:
            raise ExecutionPersistenceError("EXECUTION_ID_INVALID")
        if isinstance(self.aggregate_version, bool) or self.aggregate_version < 1:
            raise ExecutionPersistenceError("EXECUTION_VERSION_INVALID")


@dataclass(frozen=True, slots=True)
class ImportCheckpoint:
    state: CutoverState
    writer: Writer
    source_backup_identity: str | None
    source_backup_digest: str | None
    last_storage_sequence: int
    last_record_id: str | None
    target_high_water: int
    importer_version: str
    verification_status: str
    checkpoint_version: int = 1

    def __post_init__(self) -> None:
        if self.checkpoint_version < 1:
            raise ExecutionPersistenceError("CHECKPOINT_VERSION_INVALID")


@dataclass(frozen=True, slots=True)
class CommandResultFact:
    command_id: CommandId
    ordinal: int
    result: CommandResult
    record: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.command_id, CommandId):
            raise ExecutionPersistenceError("COMMAND_ID_REQUIRED")
        if isinstance(self.ordinal, bool) or self.ordinal < 1:
            raise ExecutionPersistenceError("COMMAND_RESULT_ORDINAL_INVALID")
        if not isinstance(self.result, CommandResult):
            raise ExecutionPersistenceError("COMMAND_RESULT_INVALID")
