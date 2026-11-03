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


@pytest.mark.parametrize(
    "outcome",
    [
        "valid",
        "clarification",
        "invalid",
        "unknown",
        "denied",
        "budget",
        "input",
        "admission",
    ],
)
@pytest.mark.parametrize("modern_policy", [False, True])
def test_governed_invocation_replay_and_owner_facts(repository, outcome, modern_policy):  # noqa: F811
    now = datetime.now(UTC)
    sample = proposal()
    if modern_policy:
        from agent_console.plan_suggestion_domain import FlexiblePlanSemantics
        from test_planning_contracts import modern

        sample = sample.model_copy(
            update={"semantics": FlexiblePlanSemantics.model_validate(modern())}
        )
    scope = ScopeIdentity("tenant-a", "quality")
    principal = SimpleNamespace(principal_id="employee:17")
    observed = []

    class Authority:
        def require(self, principal, owner, action, resource):
            observed.append((owner, action, resource))
            return SimpleNamespace(decision_id="controlled-test-decision")

    class ModelAuthority:
        def authorize_use(self, scope, subject, use):
            if outcome == "denied":
                return None
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

        def suggest(self, request, binding, profile, business_context):
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

    class Budget(InMemoryProviderCallBudget):
        def reserve(self, *args):
            if outcome == "budget":
                from agent_console.draft_assistance import DraftAssistanceError

                raise DraftAssistanceError("PROVIDER_BUDGET_EXHAUSTED")
            return super().reserve(*args)

    app = SimpleNamespace(
        repository=repository,
        authority=Authority(),
        scope=lambda principal: scope,
        validate_target=lambda *args, **kwargs: None,
        current_input=lambda *args: {
            "title": "x" * 65536 if outcome == "input" else "Controlled test Problem"
        },
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
        budget=Budget(),
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
        target=sample.semantics.target,
        idempotency_key="same-key",
        policy=sample.semantics.policy if modern_policy else None,
    )
    if outcome in {"denied", "budget", "input"}:
        from agent_console.draft_assistance import DraftAssistanceError
        from agent_console.model_binding_resolution import ModelBindingResolutionFailure

        with pytest.raises(
            (DraftAssistanceError, ModelBindingResolutionFailure, PlanningError)
        ):
            service.begin(principal, request)
        assert provider.calls == 0
        if outcome == "budget":
            replay = service.begin(principal, request)
            assert replay["result"]["technical_status"] == "OUTCOME_UNKNOWN"
            assert provider.calls == 0
        return
    if outcome == "admission":
        from contextlib import nullcontext

        class ExactAdmission:
            ready = False
            record = None

            def prepare(self, request, record):
                self.record = self.record or record
                return {
                    "invocation": self.record,
                    "result": {
                        "technical_status": "AUTHORIZATION_PENDING",
                        "kind": None,
                    },
                    "admission": {"ready": self.ready},
                }

            def dispatch_guard(self, record):
                return nullcontext()

        service.exact_admission = ExactAdmission()
        pending = service.begin(principal, request)
        assert pending["result"]["technical_status"] == "AUTHORIZATION_PENDING"
        assert service.begin(principal, request) == pending
        assert (
            invocations.find_request(scope, principal.principal_id, "same-key") is None
        )
        assert provider.calls == 0
        service.exact_admission.ready = True
    result = service.begin(principal, request)
    assert service.begin(principal, request) == result
    assert provider.calls == 1
    if modern_policy:
        assert result["invocation"]["request"]["policy"] == request.policy.model_dump(
            mode="json"
        )
        assert result["invocation"]["submitted_at"]
        if outcome == "valid":
            assert result["result"]["generated_at"]
            assert result["result"]["validation"]["status"] == "DECLARED_CONTRACT_VALID"
            with repository.transaction(
                scope, result["result"]["proposal"]["proposal_id"], authorized=True
            ) as cursor:
                history = repository.history(
                    cursor, scope, result["result"]["proposal"]["proposal_id"]
                )
                assert history["conversation"][0]["request"][
                    "policy"
                ] == request.policy.model_dump(mode="json")
    assert result["facts_status"] == "RECORDED"
    target = result["invocation"]["target"]
    assert target["purpose"] == "CONFIRMED_PROBLEM_PLAN_SUGGESTION"
    assert target["variant"] == "FIRST_PROPOSAL"
    assert target["source_proposal"] is None
    expected = {
        "valid": "VALID_SUGGESTION",
        "admission": "VALID_SUGGESTION",
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
