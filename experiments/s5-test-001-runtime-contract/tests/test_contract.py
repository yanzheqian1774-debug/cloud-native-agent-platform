from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from generic_caller import execute  # noqa: E402
from providers import OpenClawProvider  # noqa: E402
from runtime_contract import RuntimeBinding  # noqa: E402


def test_same_generic_caller_supports_deferred_provider() -> None:
    calls = []

    def native(method, params):
        calls.append((method, params))
        return {"runId": "native-run-1"} if method == "submit" else {"status": "error"}

    binding = RuntimeBinding(
        "binding-b", "openclaw", "experimental.openclaw", "external"
    )
    outcome = execute(
        {binding.binding_id: OpenClawProvider(binding, native)},
        binding.binding_id,
        "hello",
    )
    assert outcome.kind.value == "failure"
    assert outcome.correlation_id.startswith("s5-test-001-")
    assert [call[0] for call in calls] == ["submit", "observe"]


def test_generic_caller_has_no_runtime_specific_vocabulary() -> None:
    source = (ROOT / "generic_caller.py").read_text().lower()
    forbidden = ("hermes", "openclaw", "gateway", "profile", "session", "runid", "kimi")
    assert all(word not in source for word in forbidden)


def test_binding_has_no_universal_runtime_instance() -> None:
    source = (ROOT / "runtime_contract.py").read_text().lower()
    assert "class runtimeinstance" not in source.replace(" ", "")
