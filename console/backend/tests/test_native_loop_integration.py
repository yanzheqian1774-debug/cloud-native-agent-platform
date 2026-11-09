# ruff: noqa: F811 -- Isolated PostgreSQL fixture composition.
"""Owner storage and executor boundary checks; real-provider acceptance is separate."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.native_diagnostic_tools import NativeDiagnosticTools
from agent_console.native_loop_journal import NativeLoopJournal
from agent_console.native_loop_provider import action_schema
from agent_console.native_loop_skill import NativeLoopSkillExecutor, executor_revision
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.tabular_diagnostic_skill import TabularDiagnosticSkillExecutor
from test_native_diagnostic_tools import REFERENCE, SOURCE
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_native_pipeline import (
    test_six_task_managed_skill_pipeline_restart_readback_and_no_redispatch as seed_pipeline,  # noqa: E501
)


def test_native_owner_journal_survives_restart_and_conflicts(repository, tmp_path):
    seed_pipeline(repository, tmp_path, "cost")
    with repository.pool.connection() as c, c.transaction():
        c.execute(
            (Path(__file__).parents[1] / "migrations/0050_native_loop.sql").read_text()
        )
        row = c.execute(
            "SELECT namespace,security_domain,skill_invocation_id FROM "
            "skill_invocation.invocations LIMIT 1"
        ).fetchone()
    scope = SimpleNamespace(
        namespace=row["namespace"], security_domain=row["security_domain"]
    )
    one = NativeLoopJournal(repository.pool, scope, row["skill_invocation_id"])
    assert one.claim("step", "a" * 64) is None
    two = NativeLoopJournal(repository.pool, scope, row["skill_invocation_id"])
    assert two.claim("step", "a" * 64)["result"] is None
    two.finish("step", "a" * 64, {"status": "recorded"})
    assert one.claim("step", "a" * 64)["result"] == {"status": "recorded"}
    two.finish("step", "a" * 64, {"status": "recorded"})
    with pytest.raises(AuthorityError):
        one.claim("step", "b" * 64)
    with pytest.raises(AuthorityError):
        two.finish("step", "a" * 64, {"status": "different"})


def test_v2_never_falls_back_to_a_scripted_model():
    inputs = {
        "synthetic": True,
        "sourceSnapshot": REFERENCE,
        "source": SOURCE,
        "dependencies": {},
        "schemaVersion": "tabular-diagnostic-input.v1",
    }
    read = NativeLoopSkillExecutor().invoke("read", "READ_DATA", inputs, 1000).output
    with pytest.raises(SkillExecutorFailure, match="MODEL_NOT_CONFIGURED"):
        NativeLoopSkillExecutor().invoke(
            "analysis", "ANALYZE_DATA", {**inputs, "dependencies": {"read": read}}, 1000
        )
    assert (
        "nativeLoop"
        not in TabularDiagnosticSkillExecutor()
        .invoke("old", "ANALYZE_DATA", {**inputs, "dependencies": {"read": read}}, 1000)
        .output
    )


def test_exact_revisions_cannot_be_mixed():
    def op(v):
        return {
            "executorId": v.executor_id,
            "executorRevision": v.executor_revision,
            "executorConfigurationDigest": v.configuration_digest,
        }

    first, second = (
        TabularDiagnosticSkillExecutor.revision,
        NativeLoopSkillExecutor.revision,
    )
    assert executor_revision([op(second)]) == second
    with pytest.raises(ValueError):
        executor_revision([op(first), op(second)])


def test_decision_contract_only_exposes_bound_tools_and_evidence():
    import json

    library = NativeDiagnosticTools(SOURCE, REFERENCE)
    schema = action_schema([t.descriptor() for t in library.tools])
    serialized = json.dumps(schema)
    assert "uniqueItems" not in serialized
    assert "reportDigest" in serialized
    choices = schema["properties"]["decision"]["anyOf"]
    assert [
        c["properties"]["tool"]["enum"][0] for c in choices if "tool" in c["properties"]
    ] == [t.name for t in library.tools]
