"""Inherited-lock/parent-pipe handshake for the opt-in exact-host service."""

import json
import os
import select
import threading


def ready_and_watch(observation, stop):
    names = (
        "NATIVE_HOST_SERVICE_LOCK_FD",
        "NATIVE_HOST_SERVICE_CONTROL_FD",
        "NATIVE_HOST_SERVICE_READY_FD",
    )
    values = [os.environ.get(name) for name in names]
    if not any(values):
        return
    if not all(values):
        raise ValueError("HOST_SERVICE_HANDSHAKE_INCOMPLETE")
    lock_fd, control_fd, ready_fd = map(int, values)
    os.fstat(lock_fd)  # Retained for the entire child lifetime, including parent death.
    value = observation.current()
    payload = (
        json.dumps({"pid": os.getpid(), "startupDigest": value["digest"]}).encode()
        + b"\n"
    )
    os.write(ready_fd, payload)
    os.close(ready_fd)
    # No claim/effect before supervisor verifies the immutable startup record.
    if not select.select([control_fd], [], [], 30)[0] or os.read(control_fd, 1) != b"G":
        raise ValueError("HOST_SERVICE_START_NOT_CONFIRMED")

    def watch():
        try:
            while os.read(control_fd, 1):
                pass
        finally:
            stop.set()  # Finish current owner operation; never start another poll.
            os.close(control_fd)

    threading.Thread(target=watch, name="native-host-parent-watch", daemon=True).start()
