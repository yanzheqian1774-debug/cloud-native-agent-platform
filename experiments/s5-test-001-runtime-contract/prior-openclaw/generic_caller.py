"""Generic platform-side caller with no runtime-native vocabulary."""

from __future__ import annotations

from generic_boundary import ExecutionOutcome, ExecutionRequest, ExperimentalProvider


def execute(
    provider: ExperimentalProvider, input_text: str, timeout_ms: int = 30_000
) -> ExecutionOutcome:
    request = ExecutionRequest(input_text=input_text)
    handle, accepted = provider.submit(request)
    if accepted.correlation_id != handle.correlation_id:
        raise RuntimeError("Provider returned inconsistent correlation")
    terminal, outcome = provider.await_outcome(handle, timeout_ms)
    if terminal.correlation_id != handle.correlation_id:
        raise RuntimeError("Provider returned inconsistent terminal correlation")
    return outcome
