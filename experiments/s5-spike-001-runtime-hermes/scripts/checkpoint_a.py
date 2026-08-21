"""Run the experimental Checkpoint A happy-path probe three times."""

import json
import os
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

SPIKE = Path(__file__).parents[1]
sys.path.insert(0, str(SPIKE))

from harness.runtime_boundary import RuntimeRequest, RuntimeState  # noqa: E402
from provider.hermes import HermesProvider  # noqa: E402

IMAGE = (
    "nousresearch/hermes-agent@"
    "sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6"
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def main() -> int:
    api_key = os.environ.get("HERMES_SPIKE_API_KEY")
    if not api_key or len(api_key) < 8:
        print("HERMES_SPIKE_API_KEY must be set to an ephemeral value", file=sys.stderr)
        return 2

    evidence = SPIKE / "evidence" / "local"
    evidence.mkdir(parents=True, exist_ok=True)
    runs = []
    for index in range(1, 4):
        started = time.monotonic()
        record = {"run": index, "start_timestamp": now(), "image": IMAGE}
        with tempfile.TemporaryDirectory(prefix="s5-spike-001-") as data:
            provider = HermesProvider(
                name=f"s5-spike-001-{uuid.uuid4().hex[:8]}",
                image=IMAGE,
                data_dir=Path(data),
                api_key=api_key,
                host_port=18641 + index,
            )
            try:
                provider.provision()
                record["workload_creation_timestamp"] = now()
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    health = provider.health()
                    if health.state is RuntimeState.READY:
                        break
                    time.sleep(1)
                else:
                    raise TimeoutError("runtime did not become READY in 180s")
                record["runtime_ready_timestamp"] = now()
                record["time_to_ready_seconds"] = time.monotonic() - started
                invocation_started = time.monotonic()
                result = provider.invoke(
                    RuntimeRequest("Reply with exactly: checkpoint-a", uuid.uuid4().hex)
                )
                record["invocation_latency_seconds"] = (
                    time.monotonic() - invocation_started
                )
                record["invocation_output"] = result.output
                record["result"] = "PASS"
            except Exception as exc:  # evidence runner must preserve failure class
                record["result"] = "FAIL"
                record["error_type"] = type(exc).__name__
                record["error"] = str(exc)
            finally:
                provider.cleanup()
                record["cleanup_timestamp"] = now()
        runs.append(record)
    output = (
        evidence / f"checkpoint-a-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    output.write_text(json.dumps({"runs": runs}, indent=2) + "\n")
    print(output)
    return 0 if all(run["result"] == "PASS" for run in runs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
