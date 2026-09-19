"""Formal understanding composition + local HTTPS + exclusive PostgreSQL only."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.draft_assistance import DraftInvocationState
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_bootstrap import build_draft_assistance_composition
from agent_console.draft_assistance_support import (
    ExactProfileModelResolver,
    StaticDraftAuthorization,
)
from agent_console.provider_usage import grants
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_draft_assistance import context, resolved
from test_openai_responses_draft_adapter import (
    _completed,
    _credential_file,
    _real_runtime_document,
    _ResponsesHandler,
)
from test_openai_responses_draft_adapter import (
    mock_responses as mock_responses,
)
from test_plan_suggestion_v2 import repository as repository


@pytest.fixture
def assembled(repository, mock_responses):
    server, cert, tmp = mock_responses
    _credential_file(tmp)
    (tmp / "pepper").write_bytes(b"controlled-only-pepper" * 3)
    document = _real_runtime_document(server, cert, tmp)
    document["budget"].update(callCap=3, totalCostCapMicrousd=250000)
    path = tmp / "runtime.json"
    path.write_text(json.dumps(document))
    resources = []
    allowed = set()

    class Authorization(StaticDraftAuthorization):
        def require_usage(self, ctx, owner, action, resource):
            if (
                ctx.principal_id,
                ctx.scope.tenant_id,
                ctx.scope.security_domain,
                owner,
                action,
                resource,
            ) not in allowed:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def start(*, v2=False):
        if v2:
            from agent_console.draft_assistance_policy import (
                V2_SCHEMA_VERSION,
                policy_for,
            )

            document["adapter"]["revision"] = "v2"
            document["outputSchemaVersion"] = V2_SCHEMA_VERSION
            document["policyDigest"] = policy_for("v2", V2_SCHEMA_VERSION).digest
            document["maximumInputTokens"] = 32768
            path.write_text(json.dumps(document))
        composition = build_draft_assistance_composition(
            database_url=os.environ["PLANNING323_TEST_DATABASE_URL"],
            runtime_configuration_path=path,
            migrations_path=Path(__file__).parents[1] / "migrations",
            allow_local_https_mock=True,
        )
        resources.append(composition)
        service = composition.service
        service.authorization = Authorization()
        service.model_resolver = ExactProfileModelResolver(resolved())
        app = FastAPI()
        install_draft_assistance_routes(service)(
            app, lambda request: (None, context()), lambda *args: None, None
        )
        return service, TestClient(app)

    try:
        yield start, allowed
    finally:
        for resource in resources:
            resource.close()


def run(client):
    response = client.post(
        "/api/workbench/v1/draft-assistance/invocations",
        json={
            "idempotencyKey": "synthetic-metering",
            "content": "Synthetic procurement planning only",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["result"]


def response(usage, invalid=False):
    value = _completed(
        {
            "kind": "DRAFT_READY",
            "clarificationQuestion": None,
            "title": "Synthetic procurement",
            "description": "No execution",
        }
    )
    value["usage"] = usage
    if invalid:
        value["output"][0]["content"][0]["text"] = '{"invalid":true}'
    _ResponsesHandler.response = value


def authorize(allowed, identity):
    for grant in grants("understanding", identity):
        allowed.add(("human:alice", "tenant-a", "quality", *grant))


@pytest.mark.parametrize(
    "usage,settled",
    [
        (
            {
                "input_tokens": 50,
                "output_tokens": 20,
                "total_tokens": 70,
                "input_tokens_details": {"cached_tokens": 10},
            },
            True,
        ),
        (None, False),
        ({"input_tokens": 50}, False),
        ({"input_tokens": 50, "output_tokens": 20, "total_tokens": 71}, False),
        (
            {
                "input_tokens": 50,
                "output_tokens": 20,
                "input_tokens_details": {"cached_tokens": 51},
            },
            False,
        ),
    ],
)
def test_formal_usage_identity_persistence_and_independent_disclosure(
    assembled, usage, settled, record_property
):
    start, allowed = assembled
    _service, client = start()
    response(usage)
    result = run(client)
    identity = result["invocationId"]
    path = f"/api/workbench/v1/draft-assistance/invocations/{identity}/usage"
    denied = client.get(path)
    assert denied.status_code == 404
    assert denied.json() == {"reasonCode": "PROVIDER_USAGE_NOT_FOUND"}
    assert client.get(path.replace(identity, "absent")).json() == denied.json()
    # Invocation READ alone neither returns usage nor grants its disclosure.
    ordinary = client.get(path.removesuffix("/usage")).json()
    assert "req_mock_319" not in json.dumps(ordinary)
    assert "pricing" not in json.dumps(ordinary)
    authorize(allowed, identity)
    observed = client.get(path).json()["result"]
    assert observed["localCleanup"]["reaped"]
    assert "fake-provider-key" not in json.dumps(observed)
    assert "Synthetic procurement planning only" not in json.dumps(observed)
    record_property("usage_receipt", json.dumps(observed, sort_keys=True))
    m = observed["measurement"]
    assert m["local_request_id"] == identity
    assert m["provider_request_id"] == "req_mock_319"
    assert m["provider_response_id"] == "resp_mock_319"
    assert m["settleable"] is settled
    assert observed["settlement"]["status"] == (
        "ESTIMATE_SETTLED" if settled else "PENDING_RECONCILIATION"
    )
    assert observed["settlement"]["reservation_retained"] is not settled
    assert observed["pricing"]["input_price"] == 2000000
    assert len(observed["pricing"]["price_version_digest"]) == 64
    service2, client2 = start()
    assert client2.get(path).json()["result"] == observed
    assert service2.transport.dispatch_count == 0
    assert len(_ResponsesHandler.requests) == 1


def test_illegal_business_output_still_settles_reliable_usage(assembled):
    start, allowed = assembled
    _, client = start()
    response({"input_tokens": 50, "output_tokens": 20}, invalid=True)
    result = run(client)
    assert result["state"] == "FAILED"
    assert result["draft"] is None
    authorize(allowed, result["invocationId"])
    facts = client.get(
        f"/api/workbench/v1/draft-assistance/invocations/{result['invocationId']}/usage"
    ).json()["result"]
    assert facts["settlement"]["estimate_microusd"] == 260
    assert len(_ResponsesHandler.requests) == 1


def test_settlement_failure_restart_and_concurrent_repair_never_redispatches(
    assembled, monkeypatch
):
    start, allowed = assembled
    service, client = start()
    response({"input_tokens": 50, "output_tokens": 20})

    def unavailable(*args):
        raise RuntimeError("controlled transaction failure")

    monkeypatch.setattr(service.budget, "record_usage", unavailable)
    result = run(client)
    assert result["state"] == "SUCCEEDED"
    assert result["settlementStatus"] == "SETTLEMENT_WRITE_PENDING"
    assert result["reasonCode"] == "PROVIDER_BUDGET_SETTLEMENT_PENDING"
    identity = result["invocationId"]
    authorize(allowed, identity)
    service2, client2 = start()
    with ThreadPoolExecutor(max_workers=3) as pool:
        repaired = list(
            pool.map(lambda _: service2.observe(context(), identity), range(6))
        )
    assert all(
        item.invocation.state is DraftInvocationState.SUCCEEDED for item in repaired
    )
    assert service2.read(context(), identity).invocation.owner_write_reason_code is None
    value = client2.get(
        f"/api/workbench/v1/draft-assistance/invocations/{identity}/usage"
    ).json()["result"]
    assert value["settlement"]["estimate_microusd"] == 260
    assert len(_ResponsesHandler.requests) == 1
    assert service2.transport.dispatch_count == 0


def test_v2_formal_composition_preserves_usage_and_policy_context(assembled):
    from test_draft_assistance_policy import content
    from test_draft_assistance_policy import result as policy_result

    start, allowed = assembled
    service, client = start(v2=True)
    _ResponsesHandler.response = _completed(policy_result())
    result = client.post(
        "/api/workbench/v1/draft-assistance/invocations",
        json={"idempotencyKey": "synthetic-v2", "content": content()},
    )
    assert result.status_code == 201, result.text
    value = result.json()["result"]
    assert value["state"] == "SUCCEEDED"
    assert value["understanding"]
    assert value["settlementStatus"] == "ESTIMATE_SETTLED"
    assert service.profile.adapter_revision == "v2"
    assert len(_ResponsesHandler.requests) == 1
    authorize(allowed, value["invocationId"])
    facts = client.get(
        f"/api/workbench/v1/draft-assistance/invocations/{value['invocationId']}/usage"
    ).json()["result"]
    assert facts["measurement"]["provider_response_id"] == "resp_mock_319"


def test_formal_denial_starts_no_worker_or_https(assembled):
    from agent_console.draft_assistance import AuthorizationState

    start, _ = assembled
    service, client = start()
    service.authorization.state = AuthorizationState.DENIED
    result = client.post(
        "/api/workbench/v1/draft-assistance/invocations",
        json={"idempotencyKey": "denied", "content": "synthetic only"},
    )
    assert result.status_code == 201
    assert result.json()["result"]["state"] == "REJECTED"
    assert (
        result.json()["result"]["reasonCode"] == "DRAFT_ASSISTANCE_AUTHORIZATION_DENIED"
    )
    assert service.transport.dispatch_count == 0
    assert not _ResponsesHandler.requests
