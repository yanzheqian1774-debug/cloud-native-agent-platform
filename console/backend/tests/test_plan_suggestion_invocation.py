"""D2 controlled-provider and durable owner facts; no external model calls."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_model_binding_resolution as model_fixture
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.draft_assistance_support import InMemoryProviderCallBudget
from agent_console.execution_domain import ScopeIdentity
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner
from agent_console.plan_suggestion_domain import ExactReference, PlanningError
from agent_console.plan_suggestion_invocation import PlanningProfile, PlanningRequest
from agent_console.plan_suggestion_service import PlanningSuggestionService
from test_plan_suggestion_v2 import proposal, repository  # noqa: F401


@pytest.mark.parametrize("outcome", ["valid", "clarification", "invalid", "unknown"])
def test_governed_invocation_replay_and_owner_facts(repository, outcome):  # noqa: F811
    now = datetime.now(UTC)
    sample = proposal()
    scope = ScopeIdentity("tenant-a", "quality")
    principal = SimpleNamespace(principal_id="employee:17")
    observed = []

    class Authority:
        def require(self, principal, owner, action, resource):
            observed.append((owner, action, resource))
            return SimpleNamespace(decision_id="controlled-test-decision")

    class ModelAuthority:
        def authorize_use(self, scope, subject, use):
            return model_fixture.authorization(
                scope=scope,
                subject=subject,
                use=use,
                issued_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(minutes=5),
            )

    class Provider:
        synthetic = True
        calls = 0

        def suggest(self, request, binding, profile):
            self.calls += 1
            if outcome == "unknown":
                raise TimeoutError
            if outcome == "invalid":
                return '{"kind":"VALID_SUGGESTION","semantics":{"madeUp":true}}'
            if outcome == "clarification":
                return json.dumps(
                    {"kind": "NEEDS_CLARIFICATION", "questions": ["统计日期?"]}
                )
            return json.dumps(
                {
                    "kind": "VALID_SUGGESTION",
                    "semantics": sample.semantics.model_dump(mode="json"),
                }
            )

    with repository.pool.connection() as conn:
        conn.execute(
            (
                Path(__file__).parents[1] / "migrations/0023_draft_assistance.sql"
            ).read_text()
        )
    invocations = PostgresPlanningInvocations(repository)
    invocations.migrate()
    provider = Provider()
    app = SimpleNamespace(
        repository=repository,
        authority=Authority(),
        scope=lambda principal: scope,
        validate_target=lambda *args, **kwargs: None,
    )
    service = PlanningSuggestionService(
        app,
        invocations,
        PlanningProfile(
            profile_revision_id="profile:1",
            profile_digest="e" * 64,
            model=ExactReference(
                resource_id="model:reviewer",
                revision_id="model-revision:7",
                digest="a" * 64,
            ),
            adapter_id="controlled-test",
            adapter_revision="1",
            maximum_output_tokens=8192,
            maximum_input_bytes=65536,
        ),
        model_authorizer=ModelAuthority(),
        model_resolver=model_fixture.RecordingResolver([]),
        budget=InMemoryProviderCallBudget(),
        quote=ProviderBudgetQuote(65536, 8192, 100),
        provider=provider,
        model_use_owner=PostgresPlanModelUseOwner(repository),
        commitment_key=b"323-controlled-test-commitment-key-not-a-secret",
        prepare_resources=lambda *args: ExactReference(
            resource_id="controlled-directory",
            revision_id="snapshot:1",
            digest="c" * 64,
        ),
    )
    request = PlanningRequest(
        target=sample.semantics.target, idempotency_key="same-key"
    )
    result = service.begin(principal, request)
    assert service.begin(principal, request) == result
    assert provider.calls == 1
    assert result["facts_status"] == "RECORDED"
    target = result["invocation"]["target"]
    assert target["purpose"] == "CONFIRMED_PROBLEM_PLAN_SUGGESTION"
    assert target["variant"] == "FIRST_PROPOSAL"
    assert target["source_proposal"] is None
    expected = {
        "valid": "VALID_SUGGESTION",
        "clarification": "NEEDS_CLARIFICATION",
        "invalid": "INVALID",
        "unknown": None,
    }
    assert result["result"]["kind"] == expected[outcome]
    if outcome == "unknown":
        assert result["result"]["technical_status"] == "OUTCOME_UNKNOWN"
    assert "raw" not in json.dumps(result)
    provider.synthetic = False
    new_request = request.model_copy(update={"idempotency_key": "new-real-key"})
    with pytest.raises(PlanningError, match="REAL_CALLS_DISABLED"):
        service.begin(principal, new_request)
    assert provider.calls == 1
