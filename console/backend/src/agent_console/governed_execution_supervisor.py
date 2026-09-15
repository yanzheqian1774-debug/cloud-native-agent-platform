"""Single-host supervisor for the governed execution Uvicorn process."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import secrets
import select
import signal
import socket
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .governed_execution_ownership import execution_database_fingerprint

OVERLAP_EXIT = 75
CONFIGURATION_EXIT = 78
READINESS_TIMEOUT_SECONDS = 20.0


def _host_scope() -> str:
    value = socket.gethostname().encode()
    return hashlib.sha256(value).hexdigest()


def _state_dir() -> Path:
    return (
        Path(tempfile.gettempdir())
        / "cloud-native-agent-platform"
        / "governed-execution-supervision"
    )


def supervision_paths(database_url: str) -> tuple[Path, Path]:
    fingerprint = execution_database_fingerprint(database_url)
    prefix = f"governed-execution-{fingerprint[:24]}"
    state_dir = _state_dir()
    return state_dir / f"{prefix}.lock", state_dir / f"{prefix}.json"


def _secure_state_dir(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    details = resolved.stat()
    if (
        not stat.S_ISDIR(details.st_mode)
        or details.st_uid != os.getuid()
        or stat.S_IMODE(details.st_mode) & 0o077
    ):
        raise ValueError("SUPERVISION_STATE_DIRECTORY_UNSAFE")
    return resolved


def _write_status(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def _read_status(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("SUPERVISION_STATUS_INVALID")
    return value


def _open_and_lock(path: Path) -> int:
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    os.fchmod(descriptor, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(descriptor)
        raise
    return descriptor


def _read_ready(descriptor: int, timeout: float) -> dict[str, object]:
    ready, _, _ = select.select([descriptor], [], [], timeout)
    if not ready:
        raise ValueError("WORKBENCH_READINESS_TIMEOUT")
    encoded = bytearray()
    while len(encoded) <= 256_000:
        chunk = os.read(descriptor, 1)
        if not chunk:
            raise ValueError("WORKBENCH_READINESS_INCOMPLETE")
        if chunk == b"\n":
            value = json.loads(encoded)
            if not isinstance(value, dict):
                raise ValueError("WORKBENCH_READINESS_INVALID")
            return value
        encoded.extend(chunk)
    raise ValueError("WORKBENCH_READINESS_TOO_LARGE")


def _status_base(
    *,
    database_fingerprint: str,
    host_scope: str,
    lock_stat: os.stat_result,
) -> dict[str, object]:
    return {
        "schemaVersion": "governed-supervisor-state.v1",
        "databaseFingerprint": database_fingerprint,
        "hostScope": host_scope,
        "lockDevice": lock_stat.st_dev,
        "lockInode": lock_stat.st_ino,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--public-host", default="127.0.0.1")
    parser.add_argument("--public-port", type=int)
    parser.add_argument("--private-host", default="127.0.0.1")
    parser.add_argument("--private-port", type=int)
    parser.add_argument("--shutdown-timeout", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    dual_listener = (
        arguments.public_port is not None or arguments.private_port is not None
    )
    if dual_listener:
        if arguments.public_port is None or arguments.private_port is None:
            print("WORKBENCH_LISTENER_CONFIGURATION_INVALID", file=sys.stderr)
            return CONFIGURATION_EXIT
    elif arguments.port is None:
        print("GOVERNED_EXECUTION_PORT_REQUIRED", file=sys.stderr)
        return CONFIGURATION_EXIT
    database_url = os.environ.get("EXECUTION_DATABASE_URL", "")
    if not database_url:
        print("GOVERNED_EXECUTION_STORAGE_UNAVAILABLE", file=sys.stderr)
        return CONFIGURATION_EXIT
    try:
        _secure_state_dir(_state_dir())
        lock_path, status_path = supervision_paths(database_url)
        lock_fd = _open_and_lock(lock_path)
    except (OSError, TypeError, ValueError) as exc:
        print(
            "SUPERVISED_RECOVERY_PREDECESSOR_UNCONFIRMED " + str(exc),
            file=sys.stderr,
        )
        return OVERLAP_EXIT

    database_fingerprint = execution_database_fingerprint(database_url)
    host_scope = _host_scope()
    lock_stat = os.fstat(lock_fd)
    base = _status_base(
        database_fingerprint=database_fingerprint,
        host_scope=host_scope,
        lock_stat=lock_stat,
    )
    try:
        prior = _read_status(status_path)
        if prior is not None and any(
            prior.get(key) != value for key, value in base.items()
        ):
            raise ValueError("SUPERVISION_PREDECESSOR_IDENTITY_UNVERIFIED")
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        os.close(lock_fd)
        print(
            "SUPERVISED_RECOVERY_PREDECESSOR_UNCONFIRMED " + str(exc),
            file=sys.stderr,
        )
        return OVERLAP_EXIT

    read_fd, write_fd = os.pipe()
    token = secrets.token_hex(32)
    handshake = {
        **base,
        "schemaVersion": "governed-supervision.v1",
        "supervisorPid": os.getpid(),
        "token": token,
    }
    os.write(
        write_fd,
        json.dumps(handshake, sort_keys=True, separators=(",", ":")).encode() + b"\n",
    )
    environment = dict(os.environ)
    environment.update(
        {
            "GOVERNED_EXECUTION_SUPERVISION_LOCK_FD": str(lock_fd),
            "GOVERNED_EXECUTION_SUPERVISION_PIPE_FD": str(read_fd),
            "GOVERNED_EXECUTION_SUPERVISION_TOKEN": token,
        }
    )
    ready_read_fd = ready_write_fd = -1
    if dual_listener:
        ready_read_fd, ready_write_fd = os.pipe()
        environment["WORKBENCH_READINESS_FD"] = str(ready_write_fd)
        command = [
            sys.executable,
            "-m",
            "agent_console.workbench_dual_listener",
            "--public-host",
            arguments.public_host,
            "--public-port",
            str(arguments.public_port),
            "--private-host",
            arguments.private_host,
            "--private-port",
            str(arguments.private_port),
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "agent_console.app:app",
            "--host",
            arguments.host,
            "--port",
            str(arguments.port),
            "--workers",
            "1",
        ]
    try:
        child = subprocess.Popen(
            command,
            env=environment,
            pass_fds=tuple(
                value for value in (lock_fd, read_fd, ready_write_fd) if value >= 0
            ),
        )
    except OSError as exc:
        os.close(read_fd)
        os.close(write_fd)
        os.close(lock_fd)
        if ready_read_fd >= 0:
            os.close(ready_read_fd)
        if ready_write_fd >= 0:
            os.close(ready_write_fd)
        print("SUPERVISED_CHILD_START_FAILED " + str(exc), file=sys.stderr)
        return CONFIGURATION_EXIT
    os.close(read_fd)
    if ready_write_fd >= 0:
        os.close(ready_write_fd)
    _write_status(
        status_path,
        {
            **base,
            "state": "STARTING" if dual_listener else "RUNNING",
            "supervisorPid": os.getpid(),
            "childPid": child.pid,
        },
    )
    if dual_listener:
        try:
            ready = _read_ready(ready_read_fd, READINESS_TIMEOUT_SECONDS)
            if (
                ready.get("schemaVersion") != "workbench-dual-listener-ready.v1"
                or ready.get("pid") != child.pid
            ):
                raise ValueError("WORKBENCH_READINESS_INVALID")
            _write_status(
                status_path,
                {
                    **base,
                    "state": "RUNNING",
                    "supervisorPid": os.getpid(),
                    "childPid": child.pid,
                    "publicPort": arguments.public_port,
                    "privatePort": arguments.private_port,
                },
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=arguments.shutdown_timeout)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=arguments.shutdown_timeout)
            print("SUPERVISED_CHILD_START_FAILED " + str(exc), file=sys.stderr)
            os.close(write_fd)
            os.close(lock_fd)
            return CONFIGURATION_EXIT
        finally:
            os.close(ready_read_fd)

    stopping = False

    def stop_child(_signum, _frame) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        if child.poll() is None:
            child.terminate()

    signal.signal(signal.SIGINT, stop_child)
    signal.signal(signal.SIGTERM, stop_child)
    try:
        return_code = child.wait()
        _write_status(
            status_path,
            {
                **base,
                "state": "EXIT_CONFIRMED",
                "supervisorPid": os.getpid(),
                "childPid": child.pid,
                "childReturnCode": return_code,
            },
        )
        return return_code
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=arguments.shutdown_timeout)
        os.close(write_fd)
        os.close(lock_fd)


if __name__ == "__main__":
    raise SystemExit(run())
