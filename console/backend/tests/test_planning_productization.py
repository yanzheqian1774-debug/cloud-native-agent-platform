"""New Chinese/finite repair boundaries, real PG invocation persistence when enabled."""

import json
from copy import deepcopy
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
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.plan_suggestion_invocation import PlanningProfile, PlanningRequest
from agent_console.plan_suggestion_service import PlanningSuggestionService
from agent_console.planning_adaptive import AdaptiveLimits, recovery, run
from agent_console.planning_language import issues
from agent_console.workbench_login import safe_return
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_planning_contracts import modern


def test_language_paths_do_not_translate_technical_identity():
    doc = {"kind": "VALID_SUGGESTION", "semantics": modern()}
    assert not issues(doc)
    doc["semantics"]["tasks"][0]["title"] = "Collect bills and report all missing data"
    assert issues(doc)[0]["path"] == ["semantics", "tasks", 0, "title"]
    doc["semantics"]["tasks"][0]["title"] = (
        "中 Collect bills and report all missing data"
    )
    assert issues(doc)
    doc["semantics"]["tasks"][0]["title"] = "收集API账单与Token用量, 预算8000元"
    assert not issues(doc)


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.test",
        "//evil.test",
        "/%2f/evil.test",
        "/work\\evil",
        "/api/workbench/v1/session",
        "/work\n",
        "/work/%0d%0a",
        "/work/../admin",
        "/work/%5cevil",
        "https://[",
    ],
)
def test_return_url_is_local_read_surface(value):
    assert safe_return(value) == "/work"


def test_safe_same_object_return():
    assert (
        safe_return("/work/planning/cost?revision=1&request=original")
        == "/work/planning/cost?revision=1&request=original"
    )


@pytest.mark.parametrize(
    "mode", ["repair", "reference", "repeat", "unknown", "deadline"]
)
def test_adaptive_preserves_attempts_and_replay_never_dispatches(repository, mode):  # noqa: F811
    scope = ScopeIdentity("tenant-a", "quality")
    principal = SimpleNamespace(principal_id="employee:17")
    now = datetime.now(UTC)
    semantics = modern()

    class Authority:
        def require(self, *args):
            return SimpleNamespace(decision_id="controlled-authority")

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

        def __init__(self):
            self.contexts = []

        def suggest(self, request, binding, profile, context):
            self.calls += 1
            self.contexts.append(deepcopy(context))
            if mode == "unknown":
                raise TimeoutError
            output = deepcopy(semantics)
            if mode == "reference" and self.calls == 1:
                output["tasks"][0]["employee_requirement_id"] = "not-declared"
            elif mode != "reference" and (self.calls == 1 or mode == "repeat"):
                output["tasks"][0]["title"] = (
                    "Collect billing records and usage details"
                )
            return json.dumps({"kind": "VALID_SUGGESTION", "semantics": output})

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
        scope=lambda p: scope,
        validate_target=lambda *a, **k: None,
        current_input=lambda *a: {"title": "合成费用案例, 预算8000元, 排除试验项目"},
    )
    profile = PlanningProfile(
        profile_revision_id="profile:1",
        profile_digest="e" * 64,
        model=ExactReference(
            resource_id="model:reviewer",
            revision_id="model-revision:7",
            digest="a" * 64,
        ),
        adapter_id="controlled",
        adapter_revision="1",
        maximum_output_tokens=8192,
        maximum_input_bytes=65536,
    )
    service = PlanningSuggestionService(
        app,
        invocations,
        profile,
        model_authorizer=ModelAuthority(),
        model_resolver=model_fixture.RecordingResolver([]),
        budget=InMemoryProviderCallBudget(),
        quote=ProviderBudgetQuote(65536, 8192, 100),
        provider=provider,
        model_use_owner=PostgresPlanModelUseOwner(repository),
        commitment_key=b"controlled-323-test-key-not-a-secret",
        prepare_resources=lambda *a: None,
    )
    request = PlanningRequest(
        target=semantics["target"],
        policy=semantics["policy"],
        output_language="zh-CN",
        idempotency_key="adaptive-root",
    )
    if mode == "deadline":
        ticks = iter([0, 0, 150])
        result = run(
            service, principal, request, AdaptiveLimits(), clock=lambda: next(ticks)
        )
        assert result["adaptive"]["stop_reason"] == "TOTAL_DEADLINE"
        assert provider.calls == 1
    else:
        result = service.begin_adaptive(principal, request)
        assert provider.calls == (1 if mode == "unknown" else 2)
        assert (
            result["adaptive"]["stop_reason"]
            == {
                "repair": "AWAIT_CONFIRMATION",
                "reference": "AWAIT_CONFIRMATION",
                "repeat": "NO_PROGRESS",
                "unknown": "OUTCOME_UNKNOWN",
            }[mode]
        )
    saved_calls = provider.calls
    again = service.begin_adaptive(principal, request)
    assert provider.calls == saved_calls
    assert again["result"] == result["result"]
    if mode in {"repair", "reference"}:
        assert provider.contexts[1]["validation_feedback"]["issues"][0]["path"] == [
            "semantics",
            "tasks",
            0,
            "title" if mode == "repair" else "employee_requirement_id",
        ]
        assert result["result"]["proposal"]["semantics"][
            "target"
        ] == request.target.model_dump(mode="json")
        assert (
            result["invocation"]["target"]["predecessor_invocation_id"]
            == result["adaptive"]["attempts"][0]["invocation_id"]
        )
    root = invocations.find_request(
        scope, principal.principal_id, request.idempotency_key
    )
    read = recovery(
        service, principal, request.idempotency_key, service.read(principal, root)
    )
    assert read["result"] == result["result"]
    assert provider.calls == saved_calls
    with repository.pool.connection() as conn:
        assert (
            conn.execute("SELECT count(*) FROM workflow_planning.plans").fetchone()[
                "count"
            ]
            == 0
        )


def test_language_repair_cannot_change_numbers_references_or_other_tasks():
    from agent_console.planning_repair import language_repair_issues

    source = {"title": "Budget 8000", "target": "immutable:1"}
    repaired = {"title": "预算8000", "target": "immutable:1"}
    assert not language_repair_issues(source, repaired, [["title"]])
    repaired["title"] = "预算10000"
    assert language_repair_issues(source, repaired, [["title"]])[0]["rule"] == (
        "REPAIR_PROTECTED_VALUE_CHANGED"
    )
    repaired["title"] = "预算8000"
    repaired["target"] = "other:2"
    assert language_repair_issues(source, repaired, [["title"]])[0]["rule"] == (
        "REPAIR_UNRELATED_STRUCTURE_CHANGED"
    )


def test_historical_translation_is_exact_and_non_authoritative():
    from agent_console.plan_suggestion_domain import ProposalRevision
    from agent_console.planning_translation import display_translation

    path = Path(__file__).parents[2] / "frontend/tests/e2e/fixtures/cost323.json"
    proposal = ProposalRevision.model_validate_json(path.read_text())
    original = proposal.model_dump(mode="json")
    translated = display_translation(proposal)
    assert translated is not None
    assert translated["metadata"]["source_digest"] == proposal.digest
    assert (
        translated["semantics"]["tasks"][0]["title"]
        != original["semantics"]["tasks"][0]["title"]
    )
    assert translated["semantics"]["target"] == original["semantics"]["target"]
    assert proposal.model_dump(mode="json") == original
    assert (
        display_translation(proposal.model_copy(update={"proposal_id": "another"}))
        is None
    )


def test_loop_deadline_combines_disconnect_without_clearing_parent():
    from threading import Event

    from agent_console.planning_adaptive import LoopCancellation

    parent = Event()
    cancellation = LoopCancellation(parent, 10, lambda: 9)
    assert not cancellation.is_set()
    parent.set()
    assert cancellation.is_set()
    parent.clear()
    assert LoopCancellation(parent, 10, lambda: 10).is_set()


def test_loop_cannot_advertise_less_than_supervisor_cleanup_bound():
    with pytest.raises(ValueError, match="PLANNING_LOOP_LIMIT_INVALID"):
        AdaptiveLimits(cleanup_seconds=0)


@pytest.mark.parametrize(
    "path",
    ["/digital-employees", "/skills", "/knowledge", "/agents", "/runtime-profiles"],
)
def test_resource_return_preserves_exact_query_without_allowing_api(path):
    destination = (
        path + "?employeeDefinitionId=employee%3Aa"
        "&employeeDefinitionRevisionId=revision%3Ab&section=overview"
    )
    assert safe_return(destination) == destination
    assert safe_return(path + "/../api") == "/work"
