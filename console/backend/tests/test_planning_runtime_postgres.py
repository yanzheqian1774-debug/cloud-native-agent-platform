"""Isolated configuration composition and durable budget, never provider IO."""

import json
import os
from pathlib import Path

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_suggestion_runtime import build_planning_runtime
from agent_console.plan_suggestion_service import PlanningBudgetIdentity
from test_plan_suggestion_v2 import repository  # noqa: F401


def test_formal_runtime_uses_durable_scoped_budget(repository, tmp_path):  # noqa: F811
    root = Path(__file__).parents[3]
    document = json.loads(
        (
            root / "docs/exec-plans/active/"
            "S5-V023-ARCH-323-PLANNING-RUNTIME.example.json"
        ).read_text()
    )
    pepper = tmp_path / "test-only-pepper"
    pepper.write_bytes(b"test-only-not-a-secret" * 2)
    document["pepperFile"] = str(pepper)
    path = tmp_path / "test-runtime.json"
    path.write_text(json.dumps(document))
    composition = build_planning_runtime(
        database_url=os.environ["PLANNING323_TEST_DATABASE_URL"],
        runtime_configuration_path=path,
        migrations_path=Path(__file__).parents[1] / "migrations",
    )
    try:
        deps = composition.dependencies
        assert deps.profile.real_calls_enabled is False
        identity = PlanningBudgetIdentity(
            ScopeIdentity("tenant-a", "quality"),
            "test-only-invocation",
            deps.profile.profile_revision_id,
        )
        first = deps.budget.reserve("operation1", identity, deps.quote)
        assert deps.budget.reserve("operation1", identity, deps.quote) == first
        with pytest.raises(DraftAssistanceError, match="PROVIDER_BUDGET_EXHAUSTED"):
            deps.budget.reserve(
                "operation2",
                PlanningBudgetIdentity(
                    identity.scope, "second", identity.profile_revision_id
                ),
                deps.quote,
            )
        assert deps.provider.transport.dispatch_count == 0
    finally:
        composition.close()
        composition.close()
