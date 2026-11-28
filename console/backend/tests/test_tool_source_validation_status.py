"""Pure status-boundary regressions: no database, runtime, process or network."""

from types import SimpleNamespace as NS

import pytest
from agent_console.execution_domain import record_digest
from agent_console.skill_executor import HttpReadOnlySkillExecutor
from agent_console.tool_source_validation import _fact


@pytest.mark.parametrize(
    ("status", "reason", "eligible"),
    [
        ("UNKNOWN", "TOOL_SOURCE_EXPECTATION_MISMATCH", False),
        ("NOT_EXECUTED", "TOOL_SOURCE_EXPECTATION_MISMATCH", False),
        ("FAILED", "TOOL_SOURCE_EXPECTATION_MISMATCH", True),
        ("FAILED", "TOOL_SOURCE_OUTPUT_INVALID", False),
        ("PASSED", "TOOL_SOURCE_EXPECTATION_MATCHED", True),
    ],
)
def test_complete_actual_and_proof_still_requires_terminal_source_outcome(
    monkeypatch, status, reason, eligible
):
    import agent_console.tool_source_validation as module

    inputs = {"value": 5}
    actual = {"total": 10}
    binding = NS(
        maximumInputBytes=65536,
        maximumOutputBytes=65536,
        runtime="reviewed-python-function.v1",
        runtimeRevision="registered-1",
        endpoint="http://127.0.0.1:1",
    )
    current = {
        "toolId": "tool:synthetic",
        "revisionId": "rev:exact",
        "digest": "a" * 64,
        "sourceDigest": "b" * 64,
        "record": {
            "operation": {
                "inputSchema": {"type": "object", "required": ["value"]},
                "outputSchema": {"type": "object", "required": ["total"]},
            }
        },
    }
    invocation = {
        "toolId": current["toolId"],
        "revisionId": current["revisionId"],
        "revisionDigest": current["digest"],
        "sourceDigest": current["sourceDigest"],
        "entrypoint": "known.py",
        "entrypointDigest": "c" * 64,
        "runtime": binding.runtime,
        "runtimeRevision": binding.runtimeRevision,
        "operation": "double",
        "inputDigest": record_digest(inputs),
        "arguments": inputs,
        "sourceBase64": "c3ludGhldGljIHVuaXQgZml4dHVyZQ==",
        "syntheticReadOnly": True,
    }
    executor = HttpReadOnlySkillExecutor(
        executor_id=binding.runtime,
        executor_revision=binding.runtimeRevision,
        endpoint=binding.endpoint,
    )
    execution = {
        k: invocation[k]
        for k in (
            "toolId",
            "revisionId",
            "revisionDigest",
            "sourceDigest",
            "entrypoint",
            "entrypointDigest",
            "runtime",
            "runtimeRevision",
            "operation",
            "inputDigest",
        )
    }
    execution.update(
        actualDigest=record_digest(actual),
        observationId="unit:observed",
        executorConfigurationDigest=executor.revision.configuration_digest,
    )
    request = {
        **{k: current[k] for k in ("toolId", "revisionId", "digest", "sourceDigest")},
        "executionRequestDigest": record_digest(invocation),
        "command": {
            "action": "test",
            "revisionId": current["revisionId"],
            "digest": current["digest"],
            "input": inputs,
            "expectedOutput": {"total": 999},
        },
    }
    result = {
        "status": status,
        "reasonCode": reason,
        "actual": actual,
        "actualExecution": True,
        "toolSourceInvoked": True,
        "verificationLevel": "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
        "sourceExecution": execution,
    }
    owner = NS(
        journal=NS(
            read=lambda _context, _key: {
                "claimed": True,
                "request": request,
                "result": result,
            }
        ),
        repository=object(),
        policy=NS(digest="d" * 64),
    )
    calls = []

    def source(*_args):
        calls.append("source-verified")
        return invocation

    monkeypatch.setattr(module, "source_request", source)
    proof = _fact(owner, NS(context=object()), current, binding, "original:key")
    assert (proof is not None) is eligible
    assert calls == (["source-verified"] if eligible else [])
    if eligible:
        assert proof["actualDigest"] == record_digest(actual)
        assert proof["commandKey"] == "original:key"
