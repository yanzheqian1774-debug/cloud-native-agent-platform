"""Local process bookkeeping only; never execution or grant authority."""

import fcntl
import json
import os
import stat
import subprocess
from pathlib import Path

from .native_host_startup import digest, owned_file


def private_directory(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("HOST_SERVICE_DIRECTORY_UNSAFE")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("HOST_SERVICE_DIRECTORY_UNSAFE")
    return path


def lock(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("HOST_SERVICE_LOCK_UNSAFE")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BaseException:
        os.close(fd)
        raise


def write(path, value, *, exclusive=False):
    data = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    target = Path(path)
    temporary = (
        target
        if exclusive
        else target.with_name(target.name + ".tmp-" + str(os.getpid()))
    )
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if not exclusive:
            os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except BaseException:
        if not exclusive:
            temporary.unlink(missing_ok=True)
        raise


def read(path):
    return json.loads(owned_file(path))


def birth(pid):
    if type(pid) is not int or pid <= 1:
        raise ValueError("HOST_SERVICE_PID_INVALID")
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError("HOST_SERVICE_PROCESS_OBSERVATION_FAILED")
    return result.stdout.strip() or None


def worker_id(database_fingerprint, namespace, domain, principal, preparation):
    return (
        "exact-host-"
        + digest([database_fingerprint, namespace, domain, principal, preparation])[:40]
    )


def machine_lock_directory():
    """Canonical system path, independent of TMPDIR or service state placement."""
    return private_directory(
        Path("/tmp").resolve() / ("native-exact-host-service-" + str(os.getuid()))
    )
