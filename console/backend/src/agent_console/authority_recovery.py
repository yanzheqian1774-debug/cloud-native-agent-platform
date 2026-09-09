"""Owner-restricted host-local activation and recovery serving gate."""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from agent_console.authority_contracts import AuthorityError, ControlState

CONTROL_SCHEMA_VERSION = "authority-host-control.v1"


@dataclass(frozen=True, slots=True)
class HostControlRecord:
    control_epoch: int
    recovery_epoch: int
    state: ControlState
    database_fingerprint: str
    generation: int
    generation_digest: str
    operator_id: str

    def __post_init__(self) -> None:
        if (
            self.control_epoch < 1
            or self.recovery_epoch < 1
            or self.generation < 1
            or not self.database_fingerprint
            or len(self.generation_digest) != 64
            or not self.operator_id
        ):
            raise AuthorityError("AUTHORITY_CONTROL_INVALID")


class HostRecoveryControl:
    """Durable control record outside database backup and supervisor temp state."""

    def __init__(self, path: Path) -> None:
        if not path.is_absolute() or path.name in {"", ".", ".."}:
            raise AuthorityError("AUTHORITY_CONTROL_INVALID")
        self.path = path

    def read(self) -> HostControlRecord:
        try:
            file_stat = self.path.lstat()
            if stat.S_ISLNK(file_stat.st_mode):
                raise AuthorityError("AUTHORITY_CONTROL_INVALID")
            if (
                file_stat.st_uid != os.geteuid()
                or stat.S_IMODE(file_stat.st_mode) != 0o600
            ):
                raise AuthorityError("AUTHORITY_CONTROL_INVALID")
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.pop("schemaVersion", None) != CONTROL_SCHEMA_VERSION:
                raise AuthorityError("AUTHORITY_CONTROL_INVALID")
            if set(document) != {
                "control_epoch",
                "recovery_epoch",
                "state",
                "database_fingerprint",
                "generation",
                "generation_digest",
                "operator_id",
            }:
                raise AuthorityError("AUTHORITY_CONTROL_INVALID")
            document["state"] = ControlState(document["state"])
            return HostControlRecord(**document)
        except AuthorityError:
            raise
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AuthorityError("AUTHORITY_CONTROL_INVALID") from exc

    def replace(self, record: HostControlRecord) -> None:
        previous = self.read() if self.path.exists() else None
        if previous is not None and (
            record.control_epoch <= previous.control_epoch
            or record.recovery_epoch < previous.recovery_epoch
            or record.generation < previous.generation
        ):
            raise AuthorityError("AUTHORITY_CONTROL_EPOCH_STALE")
        self._atomic_write(record)

    def require_ready(
        self,
        *,
        database_fingerprint: str,
        generation: int,
        generation_digest: str,
        recovery_epoch: int,
    ) -> HostControlRecord:
        record = self.read()
        if (
            record.state is not ControlState.ACTIVE
            or record.database_fingerprint != database_fingerprint
            or record.generation != generation
            or record.generation_digest != generation_digest
            or record.recovery_epoch != recovery_epoch
        ):
            raise AuthorityError("AUTHORITY_RECOVERY_REQUIRED")
        return record

    def _atomic_write(self, record: HostControlRecord) -> None:
        parent = self.path.parent
        if not parent.is_dir() or parent.is_symlink():
            raise AuthorityError("AUTHORITY_CONTROL_INVALID")
        payload = {
            "schemaVersion": CONTROL_SCHEMA_VERSION,
            **asdict(record),
            "state": record.state.value,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        temporary = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{self.path.name}.", dir=parent
            )
            temporary = Path(name)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
            directory = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError as exc:
            raise AuthorityError("AUTHORITY_CONTROL_UNAVAILABLE") from exc
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


class RecoveryRepository(Protocol):
    def reconcile_recovery(self, **values: object) -> None: ...

    def complete_recovery(self, **values: object) -> None: ...


class RecoveryCoordinator:
    """Controlled restore sequence; never claims to detect an arbitrary rollback."""

    def __init__(
        self, control: HostRecoveryControl, repository: RecoveryRepository
    ) -> None:
        self.control = control
        self.repository = repository

    def reconcile(
        self,
        *,
        control_epoch: int,
        recovery_epoch: int,
        database_fingerprint: str,
        generation: int,
        generation_digest: str,
        migration_version: int,
        operator_id: str,
        audit_continuity_digest: str,
        now: datetime,
    ) -> HostControlRecord:
        closed = HostControlRecord(
            control_epoch=control_epoch,
            recovery_epoch=recovery_epoch,
            state=ControlState.RECOVERY_CLOSED,
            database_fingerprint=database_fingerprint,
            generation=generation,
            generation_digest=generation_digest,
            operator_id=operator_id,
        )
        self.control.replace(closed)
        self.repository.reconcile_recovery(
            recovery_epoch=recovery_epoch,
            database_fingerprint=database_fingerprint,
            generation=generation,
            generation_digest=generation_digest,
            migration_version=migration_version,
            operator_id=operator_id,
            audit_continuity_digest=audit_continuity_digest,
            now=now,
        )
        self.repository.complete_recovery(
            recovery_epoch=recovery_epoch,
            generation=generation,
            generation_digest=generation_digest,
            operator_id=operator_id,
            now=now,
        )
        active = HostControlRecord(
            control_epoch=control_epoch + 1,
            recovery_epoch=recovery_epoch,
            state=ControlState.ACTIVE,
            database_fingerprint=database_fingerprint,
            generation=generation,
            generation_digest=generation_digest,
            operator_id=operator_id,
        )
        self.control.replace(active)
        return active
