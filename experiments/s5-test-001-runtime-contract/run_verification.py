"""Run the bounded S5-TEST-001 live evidence sequence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from generic_caller import execute
from providers import HermesProvider, OpenClawProvider
from runtime_contract import OutcomeKind, RuntimeBinding, TruthValue

PROMPT = (
    "Return exactly one JSON object with no markdown: "
    '{"marker":"S5_TEST_001_OK","status":"success"}'
)


def safe_outcome(outcome):
    return {
        "kind": outcome.kind.value,
        "correlation_id": outcome.correlation_id,
        "output": outcome.output,
        "runtime_id": outcome.runtime_id,
        "provider_id": outcome.provider_id,
        "latency_ms": outcome.latency_ms,
        "usage": outcome.usage,
        "reason": outcome.reason,
    }


def run_hermes(model_key: str, label: str):
    binding = RuntimeBinding(
        binding_id=f"binding-hermes-{label}",
        descriptor_id="hermes",
        provider_id="experimental.hermes",
        ownership_mode="managed",
        references={"model_binding": "kimi-coding-cn/kimi-k3"},
    )
    temporary = tempfile.TemporaryDirectory(prefix=f"s5-test-001-{label}-")
    provider = HermesProvider(
        binding,
        name=f"s5-test-001-{label}-{uuid4().hex[:8]}",
        data_dir=Path(temporary.name),
        gateway_key=os.environ["HERMES_SPIKE_API_KEY"],
        model_key=model_key,
    )
    try:
        provider.configure()
        provider.start()
        available = provider.wait_available()
        observations = [
            {
                "name": item.name,
                "value": item.value.value,
                "reason": item.reason,
                "observed_at_ms": item.observed_at_ms,
            }
            for item in provider.observe()
        ]
        if not available:
            return {"label": label, "available": False, "observations": observations}
        outcome = execute({binding.binding_id: provider}, binding.binding_id, PROMPT)
        return {
            "label": label,
            "available": True,
            "observations": observations,
            "outcome": safe_outcome(outcome),
        }
    finally:
        provider.cleanup()
        temporary.cleanup()


def main() -> int:
    real_key = os.environ.get("KIMI_CN_API_KEY")
    gateway_key = os.environ.get("HERMES_SPIKE_API_KEY")
    if not real_key or not gateway_key:
        print(json.dumps({"error": "required credential references unresolved"}))
        return 2

    result = {"positive": run_hermes(real_key, "positive")}
    positive = result["positive"].get("outcome", {})
    if positive.get("kind") != OutcomeKind.SUCCESS.value:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 3

    result["negative"] = run_hermes("s5-test-001-intentionally-invalid", "negative")
    result["recovery"] = run_hermes(real_key, "recovery")

    openclaw_binding = RuntimeBinding(
        binding_id="binding-openclaw",
        descriptor_id="openclaw",
        provider_id="experimental.openclaw",
        ownership_mode="external",
        references={"accepted_evidence": "S5-SPIKE-002 Checkpoint B"},
    )

    def recorded_native(method, params):
        if method == "submit":
            return {"runId": "recorded-native-run"}
        return {"status": "error"}

    openclaw = OpenClawProvider(openclaw_binding, recorded_native)
    result["openclaw_substitutability"] = safe_outcome(
        execute(
            {openclaw_binding.binding_id: openclaw},
            openclaw_binding.binding_id,
            PROMPT,
        )
    )
    result["semantic_checks"] = {
        "negative_runtime_available": any(
            item["name"] == "RuntimeAvailable"
            and item["value"] == TruthValue.TRUE.value
            for item in result["negative"]["observations"]
        ),
        "negative_execution_failure": result["negative"].get("outcome", {}).get("kind")
        == OutcomeKind.FAILURE.value,
        "recovery_success": result["recovery"].get("outcome", {}).get("kind")
        == OutcomeKind.SUCCESS.value,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(result["semantic_checks"].values()) else 4


if __name__ == "__main__":
    raise SystemExit(main())
