"""Generic Candidate v1 caller; runtime selection is registration/configuration."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import uuid4

from runtime_contract import ExecutionOutcome, ExecutionRequest, RuntimeProvider


def execute(
    providers: Mapping[str, RuntimeProvider],
    binding_id: str,
    input_text: str,
    timeout_ms: int = 180_000,
) -> ExecutionOutcome:
    provider = providers[binding_id]
    request = ExecutionRequest(
        input_text=input_text,
        correlation_id=f"s5-test-001-{uuid4().hex}",
    )
    submission = provider.submit(request)
    if submission.correlation_id != request.correlation_id:
        raise RuntimeError("Provider changed generic correlation")
    if submission.outcome is not None:
        return submission.outcome
    assert submission.handle is not None
    outcome = provider.await_outcome(submission.handle, timeout_ms)
    if outcome.correlation_id != request.correlation_id:
        raise RuntimeError("Provider changed terminal correlation")
    return outcome
