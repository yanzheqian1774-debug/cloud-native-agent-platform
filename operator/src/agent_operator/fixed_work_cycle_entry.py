"""Explicit standalone fixed-cycle CLI. No API import or implicit loop startup."""

import argparse
import json
import signal
from threading import Event


def execute(path, *, run=False, stop=None, observe=None):
    from agent_console.fixed_work_cycle_configuration import CycleConfiguration
    from agent_console.fixed_work_cycle_factory import build_cycle_process

    configuration = CycleConfiguration.load(path)
    if not configuration.enabled:
        return {"state": "DISABLED", "modelCalled": False, "executionStarted": False}
    process = build_cycle_process(configuration)
    try:
        report = process.check()
        if not run:
            return {"state": "CHECKED_ONLY", **report}
        if stop is None or observe is None:
            raise ValueError("FIXED_CYCLE_EXPLICIT_RUN_CONTROL_REQUIRED")
        process.run(stop, observe)
        return {"state": "STOPPED", "stopBoundary": "CURRENT_OWNER_CALL_RETURNED"}
    finally:
        process.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explicit bounded fixed work process")
    parser.add_argument("--configuration", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check-only", action="store_true")
    mode.add_argument("--run", action="store_true")
    args = parser.parse_args(argv)
    stop = Event()
    previous = {}
    if args.run:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, lambda *_: stop.set())

    def observation(rows):
        print(
            json.dumps(
                {
                    "events": [
                        {"eventId": r["eventId"], "stage": r["stage"]} for r in rows
                    ]
                }
            ),
            flush=True,
        )

    try:
        result = execute(
            args.configuration, run=args.run, stop=stop, observe=observation
        )
        print(json.dumps(result), flush=True)
        return 0
    except Exception:
        # Never leak private paths/DSNs or turn an uncertain owner error into retry.
        print(
            json.dumps(
                {
                    "state": "BLOCKED",
                    "reason": "FIXED_CYCLE_CHECK_OR_OWNER_FAILED",
                    "automaticRetry": False,
                }
            ),
            flush=True,
        )
        return 1
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
