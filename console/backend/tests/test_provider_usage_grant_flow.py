"""Formal Workbench + real authority PG; synthetic owner records, zero model IO."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import AuthorityRuntimeConfiguration
from agent_console.authority_foundation import initialize_authority_generation
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.draft_assistance_postgres import (
    PostgresContextualResourceUseOwner,
    PostgresDraftAssistanceRepository,
    PostgresDraftEvidenceOwner,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_model_use_postgres import PostgresPlanModelUseOwner
from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
from agent_console.provider_usage import grants
from agent_console.workbench_bootstrap import build_workbench_composition
from fastapi.testclient import TestClient
from test_draft_assistance import build, context
from test_plan_suggestion_v2 import repository as repository
from test_workbench_creator_continuation_postgres import login

ROOT = Path(__file__).parents[1] / "migrations"
PREFIX = "/api/workbench/v1"


@pytest.fixture
def assembled(repository, tmp_path, request):
    url = os.environ["PLANNING323_TEST_DATABASE_URL"]
    now = datetime.now(UTC)
    credentials = []
    for name, tenant in [
        ("reader", "tenant-a"),
        ("approver", "tenant-a"),
        ("other", "tenant-b"),
    ]:
        credentials.append(
            {
                "credentialId": "credential-" + name,
                "credentialSha256": hashlib.sha256(
                    (name + "-controlled").encode()
                ).hexdigest(),
                "principalId": "human:" + name,
                "tenantId": tenant,
                "securityDomain": "quality",
                "expiresAt": (now + timedelta(hours=2)).isoformat(),
                "authenticationSource": "BROWSER_BOOTSTRAP",
                # Both have DECIDE: prove self-approval is rejected.
                "grants": [
                    {
                        "owner": "GRANT_ADMIN",
                        "action": action,
                        "resource": f"grant-scope:{tenant}:quality",
                        "source": "STATIC_META",
                    }
                    for action in ("INSPECT", "DECIDE")
                ],
            }
        )
    generation = {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "usage-flow",
        "auditSource": "323-controlled-only",
        "credentials": credentials,
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
        "requestability": [
            {
                "owner": owner,
                "action": action,
                "resourcePrefix": prefix,
                "purpose": "USAGE_REVIEW",
            }
            for owner, action, prefix in [
                ("RESOURCE_USE", "READ", "resource-use:"),
                ("EVIDENCE", "READ_MEASUREMENT", "evidence-reference:"),
            ]
        ],
    }
    raw = json.dumps(generation).encode()
    (tmp_path / "generation.json").write_bytes(raw)
    for name in ["csrf", "continuation"]:
        (tmp_path / (name + ".key")).write_bytes(b"controlled-only-material" * 3)
    runtime = {
        "schemaVersion": "authority-foundation-runtime.v1",
        "databaseUrl": url,
        "migrationPath": str(ROOT / "0018_browser_session_grant_authority.sql"),
        "generationPath": str(tmp_path / "generation.json"),
        "generationDigest": hashlib.sha256(raw).hexdigest(),
        "csrfSigningKeyPath": str(tmp_path / "csrf.key"),
        "continuationSigningKeyPath": str(tmp_path / "continuation.key"),
        "recoveryControlPath": str(tmp_path / "control.json"),
        "databaseFingerprint": execution_database_fingerprint(url),
        "operatorId": "controlled-test-bootstrap",
    }
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(runtime))
    initialize_authority_generation(
        AuthorityRuntimeConfiguration.from_mapping(runtime),
        control_epoch=1,
        recovery_epoch=1,
        now=now,
    )
    problem = PostgresBusinessProblemRepository(
        url, migration_path=ROOT / "0013_business_problem_authority.sql"
    )
    request.addfinalizer(problem.pool.close)
    problem.migrate()
    draft_repo = PostgresDraftAssistanceRepository(
        url, migration_path=ROOT / "0023_draft_assistance.sql"
    )
    request.addfinalizer(draft_repo.close)
    draft_repo.migrate()
    uses = PostgresContextualResourceUseOwner(url)
    request.addfinalizer(uses.close)
    evidence = PostgresDraftEvidenceOwner(url)
    request.addfinalizer(evidence.close)
    draft, *_ = build(now=now)
    draft.repository = draft_repo
    draft.resource_use = uses
    draft.evidence = evidence
    # Seed only synthetic invocation via original service/owners, not authority SQL.
    outcome = draft.begin(context(), key="usage-flow", content="synthetic procurement")
    u = outcome.invocation.invocation_id
    draft._replace(outcome.invocation, measurement={"settleable": False, "usage": None})
    missing = draft.begin(context(), key="usage-not-observed", content="synthetic")
    invocations = PostgresPlanningInvocations(repository)
    invocations.migrate()
    scope = ScopeIdentity("tenant-a", "quality")
    for identity in ["planning-observed", "planning-not-observed"]:
        record = {
            "target": {"invocation_id": identity},
            "target_digest": "a" * 64,
            "binding": {},
            "authorization_decision_id": "controlled-provider-admission",
        }
        invocations.claim(scope, "human:reader", identity, "b" * 64, record)
        PostgresPlanModelUseOwner(repository).requested(scope, record)
    price = {"price_version_digest": "c" * 64}
    invocations.save_receipt(
        scope,
        "planning-observed",
        {
            "measurement": {"settleable": False, "usage": None},
            "pricing": price,
            "reservation_id": "controlled-reservation",
        },
    )
    budget = NS(
        pricing=lambda: price, owner=NS(read_settlement=lambda _: {"status": "PENDING"})
    )
    deps = PlanningInvocationDependencies(
        None, None, budget, None, None, b"k" * 32, None
    )
    composition = build_workbench_composition(
        runtime_configuration_path=path,
        allowed_host="console.example",
        allowed_origin="https://console.example",
        owner_database_url=url,
        agent_database_url=url,
        business_problems=NS(problems=problem),
        agent_definitions=NS(),
        employee_definitions=NS(),
        digital_employees=NS(),
        draft_assistance=draft,
        planning_v2_enabled=True,
        planning_invocations=deps,
    )
    request.addfinalizer(composition.close)
    yield composition.application, u, draft, missing.invocation.invocation_id


def headers(csrf, key):
    return {
        "origin": "https://console.example",
        "x-csrf-token": csrf,
        "idempotency-key": key,
    }


def request(client, csrf, kind, identity, key, indices=(0, 1)):
    members = grants(kind, identity)
    return client.post(
        PREFIX + "/authorization/grant-requests",
        headers=headers(csrf, key),
        json={
            "schemaVersion": "exact-grant-request.v1",
            "purpose": "USAGE_REVIEW",
            "requestedGrants": [
                {
                    "owner": members[i][0],
                    "action": members[i][1],
                    "resource": members[i][2],
                }
                for i in indices
            ],
        },
    )


@pytest.mark.parametrize("kind", ["understanding", "planning"])
@pytest.mark.parametrize("first", [0, 1])
def test_formal_request_independent_decision_and_usage(
    assembled, kind, first, record_property
):
    app, u, draft, missing = assembled
    identity = u if kind == "understanding" else "planning-observed"
    route = "draft-assistance" if kind == "understanding" else "planning-v2"
    path = f"{PREFIX}/{route}/invocations/{identity}/usage"
    with (
        TestClient(app, base_url="https://console.example") as reader,
        TestClient(app, base_url="https://console.example") as approver,
        TestClient(app, base_url="https://console.example") as other,
    ):
        csrf = login(reader, "reader-controlled")
        admin = login(approver, "approver-controlled")
        foreign = login(other, "other-controlled")
        denied = reader.get(path)
        assert denied.status_code == 404 and denied.json() == {
            "reasonCode": "PROVIDER_USAGE_NOT_FOUND"
        }
        for bad_kind, bad_id in [
            (kind, "invented"),
            ("planning" if kind == "understanding" else "understanding", identity),
            ("planning", "planning-not-observed"),
            ("understanding", missing),
        ]:
            response = request(reader, csrf, bad_kind, bad_id, bad_kind + bad_id)
            assert response.status_code == 404, response.text
        assert request(other, foreign, kind, identity, "cross-scope").status_code == 404
        decisions = []
        for index in [first, 1 - first]:
            key = f"exact-{kind}-{index}"
            created = request(reader, csrf, kind, identity, key, (index,))
            assert created.status_code == 202, created.text
            repeated = request(reader, csrf, kind, identity, key, (index,))
            assert repeated.json() == created.json()
            request_id = created.json()["requestId"]
            body = {
                "schemaVersion": "exact-grant-decision.v1",
                "expectedVersion": 1,
                "decision": "APPROVE",
                "reasonCategory": "CONTROLLED_REVIEW",
                "basisType": "TICKET",
                "basisReference": "S5-V023-ARCH-323-controlled",
                "notBefore": None,
                "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
            }
            endpoint = f"{PREFIX}/authorization/grant-requests/{request_id}/decisions"
            self_decision = reader.post(
                endpoint, headers=headers(csrf, key + "self"), json=body
            )
            assert self_decision.status_code != 201
            assert "SELF_APPROVAL" in self_decision.text
            approved = approver.post(
                endpoint, headers=headers(admin, key + "decision"), json=body
            )
            assert approved.status_code == 201, approved.text
            replay = approver.post(
                endpoint, headers=headers(admin, key + "decision"), json=body
            )
            assert replay.json() == approved.json()
            decisions.append({"request": created.json(), "decision": approved.json()})
            result = reader.get(path)
            assert result.status_code == (404 if index == first else 200), result.text
        assert result.json()["result"]["measurement"]["usage"] is None
        assert other.get(path).json() == denied.json()
        record_property(
            "usage_grant_flow",
            json.dumps(
                {
                    "kind": kind,
                    "invocation_id": identity,
                    "scope": ["tenant-a", "quality"],
                    "source": "CONTROLLED_OWNER_RECORDS_FORMAL_BFF_REAL_PG",
                    "approvals": decisions,
                    "usage": result.json(),
                    "external_model_calls": 0,
                },
                sort_keys=True,
            ),
        )
        assert draft.transport.dispatch_count == 2  # setup synthetic dispatch only
