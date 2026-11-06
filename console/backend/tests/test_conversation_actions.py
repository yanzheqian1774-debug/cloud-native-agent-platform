"""Continuous private C over actual draft/Problem/planning owners, isolated PG only."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
import test_model_binding_resolution as model_fixture
from agent_console.authority_contracts import AuthorityError
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.business_problem_schemas import (
    CreateCriteriaSetRevision,
    CreateCriterionRevision,
    TransitionBusinessProblem,
)
from agent_console.conversation_actions import reference
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_support import InMemoryProviderCallBudget
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner
from agent_console.plan_suggestion_api import install_planning_invocations
from agent_console.plan_suggestion_application import PlanningApplication
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.plan_suggestion_invocation import PlanningProfile
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.plan_suggestion_service import PlanningSuggestionService
from agent_console.workbench_bff import (
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_business_problem import (
    OwnerPrincipal,
    business_problem_operations,
)
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall
from agent_console.workbench_plan_suggestion import planning_operations
from fastapi.testclient import TestClient
from test_draft_assistance_postgres import _service
from test_private_conversation import database  # noqa: F401
from test_workbench_bff import SessionStub

MIGRATIONS = Path(__file__).parents[1] / "migrations"
ROOT = "/api/workbench/v1"


@pytest.fixture
def journey(database):  # noqa: F811
    with psycopg.connect(database) as c:
        for version in range(1, 13):
            c.execute(next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text())
    problems = PostgresBusinessProblemRepository(
        database,
        migration_path=MIGRATIONS / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=MIGRATIONS
        / "0020_business_problem_creator_receipt.sql",
    )
    problems.migrate()
    draft, dr, uses, evidence, transport = _service(database)

    class Authority:
        allowed = True

        def require(self, principal, owner, action, resource):
            if not self.allowed:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return SimpleNamespace(decision_id="controlled")

    authority = Authority()
    business = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(problems, object()), authority, None, None, None
    )
    plans = PostgresPlanningRepository(problems.pool)
    plans.migrate()
    invocations = PostgresPlanningInvocations(plans)
    invocations.migrate()
    planning_app = PlanningApplication(plans, problems, authority)

    class ModelAuthority:
        def authorize_use(self, scope, subject, use):
            now = datetime.now(UTC)
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
        outcome = "clarification"

        def suggest(self, *args):
            self.calls += 1
            if self.outcome == "unknown":
                raise TimeoutError
            if self.outcome == "invalid":
                return "{}"
            return json.dumps(
                {
                    "kind": "NEEDS_CLARIFICATION",
                    "questions": ["请集中确认统计日期和口径"],
                }
            )

    provider = Provider()
    planning = PlanningSuggestionService(
        planning_app,
        invocations,
        PlanningProfile(
            profile_revision_id="controlled",
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
        ),
        model_authorizer=ModelAuthority(),
        model_resolver=model_fixture.RecordingResolver([]),
        budget=InMemoryProviderCallBudget(),
        quote=ProviderBudgetQuote(65536, 8192, 100),
        provider=provider,
        model_use_owner=PostgresPlanModelUseOwner(plans),
        commitment_key=b"controlled-private-continuity-test",
        prepare_resources=lambda *args: ExactReference(
            resource_id="fixture", revision_id="1", digest="c" * 64
        ),
    )

    class Authorizer:
        def execute(self, ctx, grants, **kw):
            for grant in grants:
                authority.require(ctx, grant.owner, grant.action, grant.exact_resource)
            with problems.pool.connection() as connection:
                return kw["handler"](
                    AuthorizedOwnerCall(
                        operation=kw["operation"],
                        context=ctx,
                        connection=connection,
                        payload=kw["payload"],
                        path=kw["path"],
                        query=kw["query"],
                        decisions=(),
                        authority=authority,
                        policy_generation=1,
                        recovery_epoch=1,
                    )
                )

    sessions = SessionStub()

    def make(host="testserver", origin="https://testserver"):
        app = create_workbench_bff(
            sessions,
            Authorizer(),
            WorkbenchBffPolicy(host, origin),
            operations=business_problem_operations(business)
            + planning_operations(planning_app),
            conversation_database_url=database,
            route_installers=[
                install_draft_assistance_routes(draft),
                install_planning_invocations(lambda _: planning),
            ],
        )
        client = TestClient(app, base_url="https://testserver")
        client.cookies.set(SESSION_COOKIE, sessions.secret)
        return client, app

    client, app = make()
    principal = OwnerPrincipal("human:alice", "tenant-a", "quality")
    yield SimpleNamespace(
        client=client,
        app=app,
        make=make,
        sessions=sessions,
        draft=draft,
        transport=transport,
        provider=provider,
        authority=authority,
        planning=planning,
        business=business,
        principal=principal,
        dsn=database,
    )
    for resource in [dr, uses, evidence]:
        resource.close()
    problems.pool.close()


def post(j, path, body, headers=None, status=200):
    r = j.client.post(
        ROOT + path,
        json=body,
        headers={
            "origin": "https://testserver",
            "x-csrf-token": "csrf-token",
            **(headers or {}),
        },
    )
    assert r.status_code == status, r.text
    return r.json().get("result", r.json())


def read(j, c):
    return j.client.get(ROOT + "/conversations/" + c).json()["result"]


def create(j):
    return post(
        j, "/conversations", {"title": "Continuous", "idempotencyKey": str(uuid4())}
    )["conversation_id"]


def prepare(j, c, action, payload, source=None, version=0):
    current = read(j, c)
    message = post(
        j,
        f"/conversations/{c}/messages",
        {
            "idempotencyKey": str(uuid4()),
            "expectedVersion": current["conversation"]["version"],
            "content": "明确确认当前原入口动作",
        },
    )["identity"]
    body = {
        "idempotencyKey": str(uuid4()),
        "expectedVersion": read(j, c)["conversation"]["version"],
        "messageId": message,
        "action": action,
        "payload": payload,
        "source": source,
        "expectedOwnerVersion": version,
        "confirmed": True,
    }
    intent = post(j, f"/conversations/{c}/intents", body)["intentId"]
    return {"X-Conversation-ID": c, "X-Conversation-Intent": intent}, body


def draft_turn(j, c, previous=None):
    payload = {"idempotencyKey": str(uuid4()), "content": "改善质量,形成可验证目标"}
    if previous:
        payload.update(
            parentContextId=previous["contextId"],
            parentTurnId=previous["turnId"],
            expectedParentVersion=previous["turnVersion"],
            predecessorInvocationId=previous["invocationId"],
        )
    headers, body = prepare(
        j,
        c,
        "DRAFT",
        payload,
        reference("DRAFT", previous) if previous else None,
        previous["turnVersion"] if previous else 0,
    )
    result = post(j, "/draft-assistance/invocations", payload, headers, 201)
    return result, headers, body


def confirmed_problem(j, c):
    first, _, _ = draft_turn(j, c)
    second, _, _ = draft_turn(j, c, first)
    payload = {
        "title": "同一问题",
        "description": "受控测试目标",
        "ownerId": "human:alice",
        "idempotencyKey": str(uuid4()),
        "draftInvocationId": second["invocationId"],
    }
    headers, _ = prepare(
        j,
        c,
        "CREATE_PROBLEM",
        payload,
        reference("DRAFT", second),
        second["aggregateVersion"],
    )
    result = post(j, "/problems", payload, headers, 201)
    revision = result["revision"]
    p = revision["business_problem_id"]
    criterion = j.business.criterion(
        j.principal,
        CreateCriterionRevision(
            criterionType="HUMAN_EVALUATED",
            measurement={"rubric": "形成有证据的结果"},
            requiredEvidenceKinds=["REPORT"],
            evaluatorType="HUMAN",
            evaluatorVersion="1",
            applicability={},
            idempotencyKey=str(uuid4()),
        ),
    )["revision"]
    criteria = j.business.criteria_set(
        j.principal,
        p,
        CreateCriteriaSetRevision(
            problemRevisionId=revision["revision_id"],
            orderedCriterionRevisionIds=[criterion["revision_id"]],
            expectedVersion=1,
            idempotencyKey=str(uuid4()),
        ),
    )["revision"]
    detail = j.business.read_problem(j.principal, p)
    j.business.transition(
        j.principal,
        p,
        TransitionBusinessProblem(
            toState="ACTIVE",
            expectedVersion=detail["problem"]["aggregate_version"],
            idempotencyKey=str(uuid4()),
        ),
    )
    detail = j.business.read_problem(j.principal, p)
    target = {
        "problem": {
            "resource_id": p,
            "revision_id": revision["revision_id"],
            "digest": revision["digest"],
        },
        "criteria": {
            "resource_id": p,
            "revision_id": criteria["set_revision_id"],
            "digest": criteria["digest"],
        },
        "criterion_revision_ids": [criterion["revision_id"]],
        "expected_problem_version": detail["problem"]["aggregate_version"],
    }
    return target, headers


def planning_turn(j, c, target, predecessor=None):
    payload = {
        "target": target,
        "idempotency_key": str(uuid4()),
        "answers": ["统计日为本季度末"],
    }
    if predecessor:
        payload["predecessor_invocation_id"] = predecessor["invocation"]["target"][
            "invocation_id"
        ]
    source = {
        "kind": "PROBLEM",
        "target": {
            "problemId": target["problem"]["resource_id"],
            "revisionId": target["problem"]["revision_id"],
            "problemDigest": target["problem"]["digest"],
        },
    }
    headers, body = prepare(
        j, c, "PLANNING", payload, source, target["expected_problem_version"]
    )
    result = post(j, "/planning-v2/invocations", payload, headers, 201)
    return result, headers, body


def test_same_c_two_drafts_one_p_same_p_clarification_restart(journey):
    j = journey
    c = create(j)
    target, _ = confirmed_problem(j, c)
    first, _, _ = planning_turn(j, c, target)
    assert first["result"]["kind"] == "NEEDS_CLARIFICATION"
    second, _, _ = planning_turn(j, c, target, first)
    assert (
        first["invocation"]["target"]["suggestion_context_id"]
        == second["invocation"]["target"]["suggestion_context_id"]
    )
    data = read(j, c)
    assert len([m for m in data["messages"] if m.get("kind") == "ACTION_INTENT"]) == 5
    assert len([m for m in data["messages"] if m.get("kind") == "OWNER_RECEIPT"]) == 5
    assert len(data["links"]) == 1
    assert j.transport.dispatch_count == 2 and j.provider.calls == 2
    j.client, j.app = j.make()
    assert read(j, c) == data
    j.sessions.logged_out = True
    assert j.client.get(ROOT + "/conversations/" + c).status_code == 401
    j.sessions.logged_out = False
    assert read(j, c) == data
    with psycopg.connect(j.dsn) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM business_problem_authority.problems "
                "WHERE business_problem_id=%s",
                (target["problem"]["resource_id"],),
            ).fetchone()[0]
            == 1
        )


def test_concurrent_original_route_and_payload_mismatch(journey):
    j = journey
    c = create(j)
    payload = {"idempotencyKey": str(uuid4()), "content": "明确目标"}
    headers, body = prepare(j, c, "DRAFT", payload)
    wrong = j.client.post(
        ROOT + "/draft-assistance/invocations",
        json={**payload, "content": "不同内容"},
        headers={
            "origin": "https://testserver",
            "x-csrf-token": "csrf-token",
            **headers,
        },
    )
    assert wrong.status_code == 409

    def submit(_):
        return j.client.post(
            ROOT + "/draft-assistance/invocations",
            json=payload,
            headers={
                "origin": "https://testserver",
                "x-csrf-token": "csrf-token",
                **headers,
            },
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(submit, range(2))) == [201, 409]
    assert j.transport.dispatch_count == 1
    post(
        j,
        f"/conversations/{c}/intents",
        {**body, "payload": {**payload, "content": "changed"}},
        status=409,
    )


def test_lost_response_receipt_write_failure_no_replay(journey, monkeypatch):
    j = journey
    c = create(j)
    actions = j.app.state.conversation_actions
    original = actions.receipt
    monkeypatch.setattr(
        actions,
        "receipt",
        lambda *a, **k: (_ for _ in ()).throw(OSError("storage lost")),
    )
    result, headers, _ = draft_turn(j, c)
    assert j.transport.dispatch_count == 1
    assert not [m for m in read(j, c)["messages"] if m.get("kind") == "OWNER_RECEIPT"]
    monkeypatch.setattr(actions, "receipt", original)
    path = f"/conversations/{c}/intents/" + headers["X-Conversation-Intent"]
    before = len(read(j, c)["messages"])
    assert j.client.get(ROOT + path).json()["result"]["state"] == "SUCCEEDED"
    assert len(read(j, c)["messages"]) == before  # GET recovery is read-only.
    post(j, path + "/receipt", {})
    post(j, path + "/receipt", {})
    assert (
        len([m for m in read(j, c)["messages"] if m.get("kind") == "OWNER_RECEIPT"])
        == 1
    )
    assert j.transport.dispatch_count == 1
    assert result["invocationId"] in json.dumps(read(j, c))


def test_claim_without_safe_query_remains_unknown(journey):
    j = journey
    c = create(j)
    payload = {"idempotencyKey": str(uuid4()), "content": "x"}
    headers, body = prepare(j, c, "DRAFT", payload)
    from agent_console.private_conversation_api import IntentCommand

    canonical = IntentCommand.model_validate(body).payload
    j.app.state.conversation_actions.claim(
        j.sessions.context, c, headers["X-Conversation-Intent"], "DRAFT", canonical
    )
    path = f"/conversations/{c}/intents/" + headers["X-Conversation-Intent"]
    assert j.client.get(ROOT + path).json()["result"]["state"] == "UNKNOWN"
    post(j, path + "/receipt", {})
    assert j.transport.dispatch_count == 0
    post(j, "/draft-assistance/invocations", payload, headers, status=409)
    assert j.transport.dispatch_count == 0


def test_source_mismatch_revocation_cross_account_and_csrf(journey):
    j = journey
    c = create(j)
    result, _, _ = draft_turn(j, c)
    source = reference("DRAFT", result)
    path = f"/conversations/{c}/sources"
    body = {
        "idempotencyKey": str(uuid4()),
        "expectedVersion": read(j, c)["conversation"]["version"],
        "source": {**source, "turnVersion": 99},
    }
    post(j, path, body, status=409)
    bad = j.client.post(
        ROOT + path,
        json={**body, "source": source},
        headers={"origin": "https://testserver"},
    )
    assert bad.status_code == 403
    j.draft.authorization.readable = False
    assert all(
        m["facts"] == {"readable": False}
        for m in read(j, c)["messages"]
        if m.get("kind") == "SOURCE"
    )
    post(j, path, {**body, "source": source}, status=404)
    j.sessions.context = SimpleNamespace(
        principal_id="other", scope=j.sessions.context.scope
    )
    assert j.client.get(ROOT + "/conversations/" + c).status_code == 404


@pytest.mark.parametrize(
    "outcome,expected", [("unknown", "UNKNOWN"), ("invalid", "SUCCEEDED")]
)
def test_original_owner_unknown_and_invalid_are_preserved(journey, outcome, expected):
    j = journey
    c = create(j)
    target, _ = confirmed_problem(j, c)
    j.provider.outcome = outcome
    result, headers, _ = planning_turn(j, c, target)
    receipts = [
        m["facts"]
        for m in read(j, c)["messages"]
        if m.get("kind") == "OWNER_RECEIPT"
        and m["facts"]["intentId"] == headers["X-Conversation-Intent"]
    ]
    assert receipts[0]["state"] == expected
    if outcome == "invalid":
        assert receipts[0]["observation"]["resultKind"] == "INVALID"
    assert j.provider.calls == 1
    path = f"/conversations/{c}/intents/" + headers["X-Conversation-Intent"]
    post(j, path + "/receipt", {})
    assert j.provider.calls == 1 and result["result"]["kind"] in (None, "INVALID")


@pytest.mark.parametrize(
    "token,state", [("[FAIL]", "FAILED"), ("[UNKNOWN]", "UNKNOWN")]
)
def test_draft_owner_failed_or_unknown_never_reissued(journey, token, state):
    j = journey
    c = create(j)
    payload = {
        "idempotencyKey": str(uuid4()),
        "content": token + " explicit controlled outcome",
    }
    headers, _ = prepare(j, c, "DRAFT", payload)
    post(j, "/draft-assistance/invocations", payload, headers, 201)
    receipts = [
        m["facts"] for m in read(j, c)["messages"] if m.get("kind") == "OWNER_RECEIPT"
    ]
    assert receipts[0]["state"] == state
    post(j, "/draft-assistance/invocations", payload, headers, status=409)
    assert j.transport.dispatch_count == 1


def test_prepared_admission_continues_via_original_route_once(journey):
    from contextlib import nullcontext

    from agent_console.planning_contracts import PlanningPolicy

    j = journey
    c = create(j)
    target, _ = confirmed_problem(j, c)

    class Admission:
        ready = False
        record = None

        def prepare(self, request, record):
            self.record = self.record or record
            return {
                "invocation": self.record,
                "result": {"technical_status": "AUTHORIZATION_PENDING", "kind": None},
                "admission": {"ready": self.ready},
            }

        def recover(self, key):
            return {
                "invocation": self.record,
                "result": {"technical_status": "AUTHORIZATION_PENDING", "kind": None},
                "admission": {"ready": self.ready},
            }

        def dispatch_guard(self, record):
            return nullcontext()

    j.planning.exact_admission = Admission()
    policy = PlanningPolicy(
        mode="FREE",
        template=None,
        required_operations=[],
        prohibited_operations=[],
        business_acceptance_as_task=False,
    )
    payload = {
        "target": target,
        "idempotency_key": str(uuid4()),
        "policy": policy.model_dump(mode="json"),
    }
    source = {
        "kind": "PROBLEM",
        "target": {
            "problemId": target["problem"]["resource_id"],
            "revisionId": target["problem"]["revision_id"],
            "problemDigest": target["problem"]["digest"],
        },
    }
    headers, _ = prepare(
        j, c, "PLANNING", payload, source, target["expected_problem_version"]
    )
    result = post(j, "/planning-v2/invocations", payload, headers, 201)
    assert result["admission"]["ready"] is False and j.provider.calls == 0
    j.planning.exact_admission.ready = True
    headers, _ = prepare(
        j, c, "PLANNING_CONTINUE", payload, source, target["expected_problem_version"]
    )
    path = "/planning-v2/requests/" + payload["idempotency_key"] + "/continue"
    result = post(j, path, {}, headers)
    assert result["result"]["kind"] == "NEEDS_CLARIFICATION"
    receipts = [
        m["facts"] for m in read(j, c)["messages"] if m.get("kind") == "OWNER_RECEIPT"
    ]
    assert any(
        r["intentId"] == headers["X-Conversation-Intent"] and r["state"] == "SUCCEEDED"
        for r in receipts
    )
    post(j, path, {}, headers, status=409)
    assert j.provider.calls == 1


def test_readonly_request_recovery_checks_exact_payload(journey, monkeypatch):
    from agent_console.planning_contracts import PlanningPolicy

    j = journey
    c = create(j)
    target, _ = confirmed_problem(j, c)
    payload = {
        "target": target,
        "idempotency_key": str(uuid4()),
        "answers": ["原始回答"],
        "policy": PlanningPolicy(
            mode="FREE", business_acceptance_as_task=False
        ).model_dump(mode="json"),
    }
    source = {
        "kind": "PROBLEM",
        "target": {
            "problemId": target["problem"]["resource_id"],
            "revisionId": target["problem"]["revision_id"],
            "problemDigest": target["problem"]["digest"],
        },
    }
    headers, _ = prepare(
        j, c, "PLANNING", payload, source, target["expected_problem_version"]
    )
    actions = j.app.state.conversation_actions
    monkeypatch.setattr(
        actions,
        "remember_owner",
        lambda *a, **k: (_ for _ in ()).throw(OSError("lost local write")),
    )
    post(j, "/planning-v2/invocations", payload, headers, 201)
    path = "/conversations/" + c + "/intents/" + headers["X-Conversation-Intent"]
    assert j.client.get(ROOT + path).json()["result"]["state"] == "SUCCEEDED"
    assert j.provider.calls == 1
    # An older direct owner call with a different payload cannot be adopted.
    other = {**payload, "idempotency_key": str(uuid4())}
    post(j, "/planning-v2/invocations", other, status=201)
    different = {**other, "answers": ["different"]}
    headers, _ = prepare(
        j, c, "PLANNING", different, source, target["expected_problem_version"]
    )
    post(j, "/planning-v2/invocations", different, headers, status=409)
    path = "/conversations/" + c + "/intents/" + headers["X-Conversation-Intent"]
    assert j.client.get(ROOT + path).json()["result"]["state"] == "UNKNOWN"
    assert j.provider.calls == 2
