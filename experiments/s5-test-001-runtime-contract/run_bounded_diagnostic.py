"""Exactly one ED-S5-001 diagnostic model submission."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from providers import HermesProvider
from runtime_contract import ExecutionRequest, RuntimeBinding


def main() -> int:
    model_key = os.environ.get("KIMI_CN_API_KEY")
    gateway_key = os.environ.get("HERMES_SPIKE_API_KEY")
    if not model_key or not gateway_key:
        print(json.dumps({"error": "credential source absent"}))
        return 2

    binding = RuntimeBinding(
        binding_id="binding-hermes-diagnostic",
        descriptor_id="hermes",
        provider_id="experimental.hermes",
        ownership_mode="managed",
        references={"model_binding": "kimi-coding-cn/kimi-k3"},
    )
    temporary = tempfile.TemporaryDirectory(prefix="ed-s5-001-diagnostic-")
    provider = HermesProvider(
        binding,
        name=f"ed-s5-001-diagnostic-{uuid4().hex[:8]}",
        data_dir=Path(temporary.name),
        gateway_key=gateway_key,
        model_key=model_key,
    )
    try:
        provider.configure()
        provider.start()
        runtime_available = provider.wait_available()
        if not runtime_available:
            print(json.dumps({"runtime_available": False}, indent=2))
            return 3
        preflight = provider.sanitized_preflight()
        request = ExecutionRequest(
            input_text=(
                "Return exactly one JSON object with no markdown: "
                '{"marker":"ED_S5_001_DIAGNOSTIC","status":"success"}'
            ),
            correlation_id=f"ed-s5-001-diagnostic-{uuid4().hex}",
        )
        # This is the exactly one authorized diagnostic model submission.
        http = provider.diagnostic_submit(request)
        print(
            json.dumps(
                {
                    "runtime_available": True,
                    "runtime_identity": provider.descriptor.artifact,
                    "runtime_version": provider.descriptor.version,
                    "credential_source": "PRESENT",
                    "preflight": preflight,
                    "correlation_id": request.correlation_id,
                    "http": http,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    finally:
        provider.cleanup()
        temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
