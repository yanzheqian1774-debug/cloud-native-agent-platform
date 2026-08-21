"""Close ED-S5-001 with one real, ephemeral Kimi completion."""

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

SPIKE = Path(__file__).parents[1]
sys.path.insert(0, str(SPIKE))

from harness.runtime_boundary import RuntimeRequest, RuntimeState  # noqa: E402
from provider.hermes import HermesProvider  # noqa: E402

IMAGE = (
    "nousresearch/hermes-agent@"
    "sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6"
)
MARKER = "ED_S5_001_OK"


def main() -> int:
    gateway_key = os.environ.get("HERMES_SPIKE_API_KEY")
    if not gateway_key or len(gateway_key) < 8:
        print("ephemeral gateway authentication is absent", file=sys.stderr)
        return 2
    if not os.environ.get("KIMI_CN_API_KEY"):
        print("ephemeral model credential is absent", file=sys.stderr)
        return 2

    correlation_id = f"ed-s5-001-{uuid.uuid4().hex}"
    request = RuntimeRequest(
        input=(
            "Return exactly one JSON object with no markdown: "
            '{"marker":"ED_S5_001_OK","status":"success"}'
        ),
        correlation_id=correlation_id,
    )
    with tempfile.TemporaryDirectory(prefix="s5-spike-001-ed-") as data:
        provider = HermesProvider(
            name=f"s5-spike-001-ed-{uuid.uuid4().hex[:8]}",
            image=IMAGE,
            data_dir=Path(data),
            api_key=gateway_key,
            host_port=18680,
            inference_provider="kimi-coding-cn",
            model="kimi-k3",
            model_credential_env="KIMI_CN_API_KEY",
        )
        started = time.monotonic()
        try:
            provider.configure()
            provider.bind_model_credential()
            provider.provision()
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if provider.health().state is RuntimeState.READY:
                    break
                time.sleep(0.5)
            else:
                raise TimeoutError("Hermes runtime did not become available")

            invocation_started = time.monotonic()
            result = provider.invoke(request)
            invocation_seconds = time.monotonic() - invocation_started
            total_seconds = time.monotonic() - started
            marker_observed = MARKER in result.output
            evidence = provider.last_invocation_evidence or {}
            print(
                json.dumps(
                    {
                        "real_hermes": True,
                        "provider": "kimi-coding-cn",
                        "configured_model": "kimi-k3",
                        "correlation_id": result.correlation_id,
                        "runtime_id": evidence.get("runtime_id"),
                        "runtime_model": evidence.get("runtime_model"),
                        "finish_reason": evidence.get("finish_reason"),
                        "http_status": evidence.get("http_status"),
                        "usage": evidence.get("usage"),
                        "invocation_seconds": round(invocation_seconds, 3),
                        "total_seconds": round(total_seconds, 3),
                        "marker_observed": marker_observed,
                        "normalized_output": result.output,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0 if marker_observed else 1
        finally:
            provider.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
