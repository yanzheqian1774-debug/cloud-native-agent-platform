from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generic_boundary import (  # noqa: E402
    EventKind,
    ExecutionEvent,
    ExecutionHandle,
    ExecutionOutcome,
    OutcomeKind,
)
from generic_caller import execute  # noqa: E402
from openclaw_provider import (  # noqa: E402
    OpenClawBinding,
    OpenClawProvider,
    ProviderError,
)


class FakeProvider:
    def observe(self):
        return ()

    def submit(self, request):
        assert request.input_text == "hello"
        handle = ExecutionHandle("opaque-correlation")
        return handle, ExecutionEvent(EventKind.ACCEPTED, handle.correlation_id)

    def await_outcome(self, handle, timeout_ms):
        assert timeout_ms == 123
        event = ExecutionEvent(EventKind.TERMINAL, handle.correlation_id)
        outcome = ExecutionOutcome(OutcomeKind.SUCCEEDED, handle.correlation_id)
        return event, outcome


def test_generic_caller_uses_only_generic_lifecycle() -> None:
    outcome = execute(FakeProvider(), "hello", timeout_ms=123)
    assert outcome.kind is OutcomeKind.SUCCEEDED
    assert outcome.correlation_id == "opaque-correlation"


def test_provider_requires_credential_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHECKPOINT_B_TOKEN", raising=False)
    provider = OpenClawProvider(
        cli=("unused",),
        binding=OpenClawBinding("ws://example.invalid", "native", "native-session"),
        token_env="CHECKPOINT_B_TOKEN",
    )
    with pytest.raises(ProviderError, match="credential reference"):
        provider.submit(type("Request", (), {"input_text": "hello"})())


def test_provider_sanitizes_native_missing_auth_error() -> None:
    native = 'FailoverError: No API key found for provider "example". /secret/path'
    assert (
        OpenClawProvider._sanitize_message(native)
        == "runtime dependency unavailable: model credential not configured"
    )


def test_generic_caller_has_no_openclaw_vocabulary() -> None:
    source = (ROOT / "generic_caller.py").read_text(encoding="utf-8").lower()
    forbidden = ("openclaw", "gateway", "websocket", "agentid", "sessionkey", "runid")
    assert all(term not in source for term in forbidden)
