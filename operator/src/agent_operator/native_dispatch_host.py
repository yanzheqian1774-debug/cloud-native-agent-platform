"""Native-only host of the standard Operator work loop; no Agent watch side effects."""

import logging
import os
import signal
from threading import Event

from .main import run_native_worker
from .native_dispatch_reconciler import build_native_dispatch_from_environment


def main():
    interval = float(os.environ.get("NATIVE_DISPATCH_POLL_SECONDS", "1"))
    if not 0.1 <= interval <= 60:
        raise ValueError("NATIVE_DISPATCH_POLL_SECONDS_INVALID")
    assembly = build_native_dispatch_from_environment()
    if assembly is None:
        raise ValueError("NATIVE_DISPATCH_CONFIGURATION_REQUIRED")
    try:
        if configuration := os.environ.get("NATIVE_HOST_STARTUP_CONFIGURATION"):
            from .native_host_startup import StartupObservation

            assembly.worker.startup_observation = StartupObservation(
                configuration, assembly
            )
    except Exception:
        assembly.close()
        raise
    stop = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _sig, _frame: stop.set())
    logging.basicConfig(level=logging.INFO)
    try:
        run_native_worker(assembly, stop, logging.getLogger(__name__), interval)
    finally:
        assembly.close()


if __name__ == "__main__":
    main()
