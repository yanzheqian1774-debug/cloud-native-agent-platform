"""Formal app/workbench/runtime/service assembly with controlled infrastructure.

No socket or credential reads: the network and owner stores are explicit test seams.
The separate PostgreSQL planning tests exercise real transaction/authorization owners.
"""

import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
import test_model_binding_resolution as model_fixture
from agent_console import app
from agent_console import plan_suggestion_bootstrap as boot
from agent_console import plan_suggestion_runtime as runtime
from agent_console import workbench_bootstrap as wb
from agent_console.authority_contracts import AuthorityError
from agent_console.plan_suggestion_application import PlanningApplication
from agent_console.plan_suggestion_domain import PlanningConflict
from agent_console.plan_suggestion_policy import POLICY_DIGEST, VERSION
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_openai_responses_draft_adapter import _real_runtime_document
from test_plan_suggestion_v2 import sample
from test_workbench_bootstrap import runtime_file


class Store:
    def __init__(self, *args, **kwargs):
        self.ledger_id = "test-ledger"
        self.profile = kwargs.get(
            "profile", NS(profile_revision_id="test", profile_digest="e" * 64)
        )
        self.input_price = self.output_price = 1
        self.rows = {}
        self.pool = self

    def migrate(self):
        pass

    def migrate_and_configure(self):
        pass

    def record_usage(self, *args):
        pass

    def read_settlement(self, *args):
        return {"status": "ESTIMATE_SETTLED"}

    def close(self):
        pass

    def reserve(self, *args):
        return "test-reservation"

    @contextmanager
    def transaction(self, *args, **kwargs):
        yield NS(connection=self)


class Invocations(Store):
    def save_receipt(self, scope, identity, receipt):
        self.rows[identity]["receipt"] = receipt

    def receipt(self, scope, identity):
        return self.rows[identity].get("receipt")

    def find_request(self, scope, actor, key, commitment):
        for identity, row in self.rows.items():
            if row["key"] == key:
                if row["commitment"] != commitment:
                    raise PlanningConflict("PLANNING_IDEMPOTENCY_CONFLICT")
                return identity
        return None

    def claim(self, scope, actor, key, commitment, record):
        self.rows[record["target"]["invocation_id"]] = {
            "key": key,
            "commitment": commitment,
            "invocation": record,
            "result": {"technical_status": "OUTCOME_UNKNOWN", "kind": None},
        }
        return record, True

    def finish(self, scope, identity, result, proposal=None, validate=None):
        if validate:
            validate(None)
        self.rows[identity]["result"] = result

    def read(self, scope, identity, actor):
        row = self.rows[identity]
        return {"invocation": row["invocation"], "result": row["result"]}


class Facts:
    def __init__(self, *args):
        pass

    def requested(self, *args):
        pass

    def observed(self, *args):
        pass

    def status(self, *args):
        return "RECORDED"


@pytest.fixture
def formal(tmp_path, monkeypatch):
    state = NS(mode="valid", calls=[], denied=False, version=3)
    # This fixture replaces network/credential/storage only; boundary tests restore
    # the actual spawned provider and loopback HTTPS separately.
    original_init = runtime.PlanningResponsesProvider.__init__

    def provider_init(self, *args):
        original_init(self, *args)
        self.isolation_enabled = False

    monkeypatch.setattr(runtime.PlanningResponsesProvider, "__init__", provider_init)
    database = "postgresql://test-only.invalid/isolated323"
    authority = runtime_file(tmp_path, database)
    document = _real_runtime_document(NS(server_port=443), None, tmp_path)
    document.update(
        {
            "schemaVersion": "planning-runtime.v1",
            "executionClass": "REAL_PROVIDER",
            "responsesUrl": "https://provider.invalid/v1/responses",
            "tls": {"caFile": None},
            "realCallsEnabled": True,
            "outputSchemaVersion": "plan-suggestion-output.v1",
            "targetFormatVersion": "plan-suggestion-target.v1",
            "policyDigest": POLICY_DIGEST,
            "maximumInputTokens": 65536,
            "maximumOutputTokens": 8192,
            "model": {
                "id": "model:reviewer",
                "revisionId": "model-revision:7",
                "digest": "a" * 64,
            },
        }
    )
    (tmp_path / "pepper").write_bytes(b"test-only-not-a-secret" * 2)
    path = tmp_path / "planning.json"
    path.write_text(json.dumps(document))
    state.path = path
    state.document = document
    for name, value in {
        "WORKBENCH_AUTHORITY_RUNTIME_FILE": str(authority),
        "WORKBENCH_ALLOWED_HOST": "testserver",
        "WORKBENCH_ALLOWED_ORIGIN": "https://testserver",
        "EXECUTION_DATABASE_URL": database,
        "AGENT_DEFINITION_DATABASE_URL": database,
        "PLANNING_V2_ENABLED": "true",
        "PLANNING_RUNTIME_FILE": str(path),
    }.items():
        monkeypatch.setenv(name, value)
    for name in ("WORKFLOW_RUNTIME_DATABASE_URL", "DRAFT_ASSISTANCE_RUNTIME_FILE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "_business_problem_application": NS(problems=Store()),
        "_digital_employee_assembly": NS(
            employee_definitions=Store(), repository=Store()
        ),
        "_agent_definition_service": NS(repository=Store()),
        "_workbench_composition": None,
        "_draft_assistance_composition": None,
        "workbench_app": None,
        "_workbench_startup_error": "TEST",
    }.items():
        monkeypatch.setattr(app, name, value)
    monkeypatch.setattr(runtime, "create_model_repository", Store)
    monkeypatch.setattr(runtime, "create_provider_budget", Store)
    monkeypatch.setattr(
        runtime, "PlanningModelResolver", lambda *_: model_fixture.RecordingResolver([])
    )
    monkeypatch.setattr(
        runtime.ExactFileOpenAICredentialResolver, "resolve", lambda *_: NS()
    )
    monkeypatch.setattr(wb, "PostgresPlanningRepository", Store)
    invocations = Invocations()
    monkeypatch.setattr(boot, "PostgresPlanningInvocations", lambda *_: invocations)
    monkeypatch.setattr(boot, "PostgresPlanModelUseOwner", Facts)
    state.invocations = invocations

    def validate(self, principal, target, connection, current=True):
        if current and target.expected_problem_version != state.version:
            raise PlanningConflict("PLANNING_TARGET_STALE")

    monkeypatch.setattr(PlanningApplication, "validate_target", validate)
    monkeypatch.setattr(
        PlanningApplication,
        "current_input",
        lambda *_: {
            "title": "Synthetic procurement",
            "description": "No business data",
        },
    )
    context = NS(
        principal_id="employee:17",
        scope=NS(tenant_id="tenant-a", security_domain="quality"),
    )

    class Authority:
        def authorize_current(self, *args, **kwargs):
            if state.denied:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return NS(decision_id="test-exact")

    class ModelAuthority:
        def __init__(self, *args):
            pass

        def authorize_use(self, scope, subject, use):
            now = datetime.now(UTC)
            return model_fixture.authorization(
                scope=scope,
                subject=subject,
                use=use,
                issued_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(minutes=1),
            )

    monkeypatch.setattr(boot, "ModelUseAuthorizationAdapter", ModelAuthority)
    foundation = NS(
        generation_controller=NS(),
        repository=NS(),
        sessions=NS(),
        grants=NS(
            authorization=Authority(),
            clock=lambda: None,
            identity_factory=lambda _: "test",
        ),
        continuation_owner=NS(signing_key=b"x" * 32),
        close=lambda: None,
    )
    monkeypatch.setattr(
        wb, "build_authority_foundation", lambda *_args, **_kw: foundation
    )

    def bff(*args, route_installers, **kwargs):
        api = FastAPI()

        def csrf(request, session):
            if request.headers.get("x-csrf-token") != "test-csrf":
                from fastapi import HTTPException

                raise HTTPException(403)

        for install in route_installers:
            install(api, lambda _: (NS(), context), csrf, NS())
        return api

    monkeypatch.setattr(wb, "create_workbench_bff", bff)

    def exchange(self, *, invocation_id, request, credential):
        state.calls.append(json.loads(request.payload))
        if state.mode == "timeout":
            raise TimeoutError("private provider detail must not leak")
        if state.mode == "http":
            return 503, b"private provider body", "test", 1
        semantics = sample()
        semantics["target"] = json.loads(
            state.calls[-1]["input"][0]["content"][0]["text"]
        )["target"]
        if state.mode == "cycle":
            semantics["tasks"][0]["depends_on"] = ["T3b"]
        if state.mode == "reference":
            semantics["tasks"][0]["requirement_ids"] = ["missing"]
        if state.mode == "late":
            state.version += 1
        result = {"kind": "VALID_SUGGESTION", "semantics": semantics}
        if state.mode == "clarification":
            result = {"kind": "NEEDS_CLARIFICATION", "questions": ["统计日期?"]}
        if state.mode == "invalid":
            result = {"untrusted": True}
        response = {
            "model": document["nativeModelId"],
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(result)}],
                }
            ],
        }
        return 200, json.dumps(response).encode(), "test", 1

    monkeypatch.setattr(runtime.OpenAIResponsesDraftTransport, "exchange", exchange)

    def start():
        app._configure_workbench()
        return TestClient(app.get_workbench_app())

    state.start = start
    return state


def send(client, **changes):
    body = {"target": sample()["target"], "idempotency_key": "test-request"}
    body.update(changes)
    return client.post(
        "/api/workbench/v1/planning-v2/invocations",
        json=body,
        headers={"x-csrf-token": "test-csrf"},
    )


@pytest.mark.parametrize(
    "mode,kind,status",
    [
        ("valid", "VALID_SUGGESTION", "SUCCEEDED"),
        ("clarification", "NEEDS_CLARIFICATION", "SUCCEEDED"),
        ("invalid", "INVALID", "SUCCEEDED"),
        ("cycle", "INVALID", "SUCCEEDED"),
        ("reference", "INVALID", "SUCCEEDED"),
        ("timeout", None, "OUTCOME_UNKNOWN"),
        ("http", None, "FAILED"),
    ],
)
def test_formal_app_to_planning_service_and_responses(formal, mode, kind, status):
    formal.mode = mode
    client = formal.start()
    result = send(client)
    assert result.status_code == 201, result.text
    payload = result.json()["result"]
    assert payload["result"]["kind"] == kind
    assert payload["result"]["technical_status"] == status
    assert send(client).json() == result.json()
    assert len(formal.calls) == 1
    assert "private provider" not in result.text
    assert payload["invocation"]["target"]["policy_version"] == VERSION
    assert payload["invocation"]["policy_digest"] == POLICY_DIGEST
    assert formal.calls[0]["store"] is False
    assert formal.calls[0]["text"]["format"]["strict"] is True
    assert "approval" not in payload["result"]


@pytest.mark.parametrize("case", ["missing", "invalid", "disabled", "denied", "stale"])
def test_formal_app_fail_closed_before_network(formal, monkeypatch, case):
    if case == "missing":
        monkeypatch.delenv("PLANNING_RUNTIME_FILE")
    elif case == "invalid":
        formal.path.write_text("{}")
    elif case == "disabled":
        formal.document["realCallsEnabled"] = False
        formal.path.write_text(json.dumps(formal.document))
    elif case == "denied":
        formal.denied = True
    elif case == "stale":
        formal.version = 4
    response = send(formal.start())
    assert response.status_code in {503, 404, 409}, response.text
    assert formal.calls == []
    assert (
        response.json()["reasonCode"]
        == {
            "missing": "PLANNING_NOT_CONFIGURED",
            "invalid": "PLANNING_CONFIGURATION_INVALID",
            "disabled": "PLANNING_REAL_CALLS_DISABLED",
            "denied": "AUTHORIZATION_NOT_FOUND",
            "stale": "PLANNING_TARGET_STALE",
        }[case]
    )


def test_clarification_successor_context_and_late_target(formal):
    client = formal.start()
    formal.mode = "clarification"
    first = send(client).json()["result"]
    identity = first["invocation"]["target"]["invocation_id"]
    formal.mode = "valid"
    second = send(
        client,
        idempotency_key="answer",
        predecessor_invocation_id=identity,
        answers=["2026-09-18; use corrected current scope"],
    )
    assert second.status_code == 201
    context = json.loads(formal.calls[-1]["input"][0]["content"][0]["text"])
    assert context["answers"] == ["2026-09-18; use corrected current scope"]
    assert context["context"]["planning_context"]["previous_questions"]
    formal.mode = "late"
    response = send(client, idempotency_key="late")
    assert response.status_code == 409
    assert response.json()["reasonCode"] == "PLANNING_TARGET_STALE"
    assert (
        send(client, idempotency_key="late").json()["result"]["result"][
            "technical_status"
        ]
        == "OUTCOME_UNKNOWN"
    )
    assert len(formal.calls) == 3


def test_correction_successor_uses_current_problem_and_criteria(formal, monkeypatch):
    from agent_console.plan_suggestion_domain import ExactReference
    from test_plan_suggestion_v2 import proposal

    source = proposal()
    monkeypatch.setattr(Store, "proposal", lambda *_: source, raising=False)
    formal.version = 4
    current = sample()["target"]
    current["expected_problem_version"] = 4
    current["problem"]["revision_id"] = "problem:2"
    current["criteria"]["revision_id"] = "criteria:2"
    client = formal.start()
    response = send(
        client,
        target=current,
        source_proposal=ExactReference(
            resource_id=source.proposal_id,
            revision_id=str(source.revision),
            digest=source.digest,
        ).model_dump(mode="json"),
        answers=["Correction: company A only"],
    )
    assert response.status_code == 201, response.text
    payload = json.loads(formal.calls[-1]["input"][0]["content"][0]["text"])
    assert payload["target"] == current
    assert payload["context"]["planning_context"]["source_proposal"]["revision"] == 1
    assert response.json()["result"]["result"]["proposal"]["revision"] == 2


def test_formal_csrf_rejects_without_provider(formal):
    response = formal.start().post(
        "/api/workbench/v1/planning-v2/invocations",
        json={"target": sample()["target"], "idempotency_key": "csrf"},
    )
    assert response.status_code == 403
    assert formal.calls == []


def test_runtime_schema_rejects_mock_and_wrong_policy(formal):
    from pathlib import Path

    from agent_console.plan_suggestion_domain import PlanningError

    for changes in (
        {"executionClass": "LOCAL_HTTPS_MOCK"},
        {"policyDigest": "f" * 64},
        {"realCallsEnabled": "true"},
    ):
        formal.path.write_text(json.dumps({**formal.document, **changes}))
        with pytest.raises(PlanningError, match="PLANNING_CONFIGURATION_INVALID"):
            runtime.build_planning_runtime(
                database_url="test",
                runtime_configuration_path=formal.path,
                migrations_path=Path(__file__).parents[1] / "migrations",
            )
    assert formal.calls == []
