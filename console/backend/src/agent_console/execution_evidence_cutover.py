"""Single-writer Evidence cutover and rollback barrier."""

from __future__ import annotations

from dataclasses import replace

from .execution_domain import (
    CutoverState,
    ExecutionPersistenceError,
    ImportCheckpoint,
    Writer,
)
from .execution_postgres import PostgresExecutionAuthorityRepository


class CutoverError(ExecutionPersistenceError):
    reason_code = "EVIDENCE_CUTOVER_ERROR"


class EvidenceCutoverCoordinator:
    def __init__(self, authority: PostgresExecutionAuthorityRepository) -> None:
        self.authority = authority

    def activate_postgres(
        self, *, sqlite_quiesced: bool, parity_verified: bool
    ) -> ImportCheckpoint:
        current = self.authority.load_checkpoint()
        if (
            not sqlite_quiesced
            or not parity_verified
            or current.state is not CutoverState.IMPORTING
            or current.writer is not Writer.NONE
            or current.verification_status != "PARITY_VERIFIED"
        ):
            return self._recovery(current, "CUTOVER_PRECONDITION_FAILED")
        return self.authority.replace_checkpoint(
            replace(
                current,
                state=CutoverState.POSTGRES_ACTIVE,
                writer=Writer.POSTGRES,
                verification_status="CUTOVER_VERIFIED",
            )
        )

    def rollback_to_sqlite(
        self,
        *,
        all_writers_stopped: bool,
        sqlite_backup_verified: bool,
        post_cutover_postgres_facts: int,
    ) -> ImportCheckpoint:
        current = self.authority.load_checkpoint()
        if post_cutover_postgres_facts:
            return self._recovery(current, "ROLLBACK_WOULD_DISCARD_FACTS")
        if not all_writers_stopped or not sqlite_backup_verified:
            return self._recovery(current, "ROLLBACK_PRECONDITION_FAILED")
        return self.authority.replace_checkpoint(
            replace(
                current,
                state=CutoverState.SQLITE_ACTIVE,
                writer=Writer.SQLITE,
                verification_status="ROLLBACK_VERIFIED",
            )
        )

    def assert_writer(self, writer: Writer) -> None:
        current = self.authority.load_checkpoint()
        if current.writer is not writer:
            raise CutoverError("NON_AUTHORITATIVE_WRITER")

    def _recovery(self, current: ImportCheckpoint, reason: str) -> ImportCheckpoint:
        self.authority.replace_checkpoint(
            replace(
                current,
                state=CutoverState.RECOVERY_REQUIRED,
                writer=Writer.NONE,
                verification_status=reason,
            )
        )
        raise CutoverError(reason)
