"""Process ownership primitives for supervised governed execution."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import stat
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import Any

from psycopg.conninfo import conninfo_to_dict


def execution_database_fingerprint(database_url: str) -> str:
    """Return a credential-free, process-stable identity for one database target."""
    values = conninfo_to_dict(database_url)
    semantic = {
        "dbname": values.get("dbname") or values.get("user") or "",
        "host": values.get("hostaddr") or values.get("host") or "local-socket",
        "port": values.get("port") or "5432",
        "service": values.get("service") or "",
    }
    encoded = json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(slots=True)
class _OwnershipEntry:
    lock: threading.Lock
    references: int = 0


class InvocationOwnershipRegistry:
    """Share invocation ownership across every application in this process."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._entries: dict[tuple[str, str], _OwnershipEntry] = {}

    @contextmanager
    def own(self, database_scope: str, invocation_id: str) -> Iterator[None]:
        key = (database_scope, invocation_id)
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _OwnershipEntry(threading.Lock())
                self._entries[key] = entry
            entry.references += 1
        try:
            with entry.lock:
                yield
        finally:
            with self._guard:
                entry.references -= 1
                if entry.references == 0 and self._entries.get(key) is entry:
                    del self._entries[key]


PROCESS_INVOCATION_OWNERSHIP = InvocationOwnershipRegistry()


class SupervisedRecoveryGuard:
    """Verify and continuously observe the supervisor-owned child lifetime."""

    def __init__(
        self,
        *,
        active: bool = False,
        database_fingerprint: str = "",
        supervisor_pid: int = 0,
        pipe_fd: int = -1,
    ) -> None:
        self._active = threading.Event()
        if active:
            self._active.set()
        self.database_fingerprint = database_fingerprint
        self.supervisor_pid = supervisor_pid
        self.pipe_fd = pipe_fd

    @classmethod
    def from_environment(cls) -> SupervisedRecoveryGuard:
        names = {
            "lock_fd": "GOVERNED_EXECUTION_SUPERVISION_LOCK_FD",
            "pipe_fd": "GOVERNED_EXECUTION_SUPERVISION_PIPE_FD",
            "token": "GOVERNED_EXECUTION_SUPERVISION_TOKEN",
        }
        if not any(os.environ.get(name) for name in names.values()):
            return cls()
        try:
            lock_fd = int(os.environ[names["lock_fd"]])
            pipe_fd = int(os.environ[names["pipe_fd"]])
            expected_token = os.environ[names["token"]]
            lock_stat = os.fstat(lock_fd)
            pipe_stat = os.fstat(pipe_fd)
            if not stat.S_ISREG(lock_stat.st_mode) or not stat.S_ISFIFO(
                pipe_stat.st_mode
            ):
                return cls()
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            handshake = cls._read_handshake(pipe_fd)
            if (
                handshake.get("schemaVersion") != "governed-supervision.v1"
                or not hmac.compare_digest(handshake.get("token", ""), expected_token)
                or handshake.get("lockDevice") != lock_stat.st_dev
                or handshake.get("lockInode") != lock_stat.st_ino
                or handshake.get("supervisorPid") != os.getppid()
            ):
                return cls()
            database_fingerprint = handshake.get("databaseFingerprint", "")
            if not database_fingerprint:
                return cls()
            guard = cls(
                active=True,
                database_fingerprint=database_fingerprint,
                supervisor_pid=handshake["supervisorPid"],
                pipe_fd=pipe_fd,
            )
            threading.Thread(
                target=guard._watch_supervisor,
                name="governed-execution-supervisor-watch",
                daemon=True,
            ).start()
            return guard
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return cls()

    @staticmethod
    def _read_handshake(pipe_fd: int) -> dict[str, Any]:
        encoded = bytearray()
        while len(encoded) <= 4096:
            chunk = os.read(pipe_fd, 1)
            if not chunk:
                raise ValueError("SUPERVISION_HANDSHAKE_INCOMPLETE")
            if chunk == b"\n":
                value = json.loads(encoded)
                if not isinstance(value, dict):
                    raise ValueError("SUPERVISION_HANDSHAKE_INVALID")
                return value
            encoded.extend(chunk)
        raise ValueError("SUPERVISION_HANDSHAKE_TOO_LARGE")

    def _watch_supervisor(self) -> None:
        try:
            while os.read(self.pipe_fd, 1):
                pass
        except OSError:
            pass
        finally:
            self._active.clear()
            with suppress(OSError):
                os.close(self.pipe_fd)

    def allows(self, database_url: str) -> bool:
        if not self._active.is_set() or os.getppid() != self.supervisor_pid:
            self._active.clear()
            return False
        try:
            return hmac.compare_digest(
                self.database_fingerprint,
                execution_database_fingerprint(database_url),
            )
        except (TypeError, ValueError):
            return False
