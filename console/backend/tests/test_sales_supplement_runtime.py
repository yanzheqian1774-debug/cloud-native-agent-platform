# ruff: noqa: F401,F811 -- Reuse unchanged disposable UUID fixtures.
"""Actual entrypoint flags and compatible close profile; no actual runtime login."""

from types import SimpleNamespace

import pytest
from agent_console import app as console_app
from agent_console import workbench_bootstrap
from agent_console.resource_management import target
from agent_console.sales_supplement_composition import operations
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_plan_suggestion import planning_operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_sales_supplement_owners import (
    ExactFixtureBffAuthorizer,
    prepare_supplement_fixture,
    snapshot,
)
from test_workbench_bff import SessionStub
from test_workbench_bootstrap import runtime_file


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, (False, False)),
        (
            {
                "SALES_GROSS_PROFIT_V2_CANDIDATE": "false",
                "SALES_SUPPLEMENT_CANDIDATE": "false",
            },
            (False, False),
        ),
        ({"SALES_GROSS_PROFIT_V2_CANDIDATE": "true"}, (True, False)),
        (
            {
                "SALES_GROSS_PROFIT_V2_CANDIDATE": "true",
                "SALES_SUPPLEMENT_CANDIDATE": "true",
            },
            (True, True),
        ),
        ({"SALES_SUPPLEMENT_CANDIDATE": "true"}, None),
        ({"SALES_GROSS_PROFIT_V2_CANDIDATE": "yes"}, None),
        ({"SALES_SUPPLEMENT_CANDIDATE": " false "}, None),
    ],
)
def test_actual_app_entrypoint_defaults_forwards_and_rejects(
    monkeypatch, values, expected
):
    for key in (
        "SALES_GROSS_PROFIT_V2_CANDIDATE",
        "SALES_SUPPLEMENT_CANDIDATE",
        "WORKFLOW_RUNTIME_DATABASE_URL",
        "PLANNING_RUNTIME_FILE",
        "DRAFT_ASSISTANCE_RUNTIME_FILE",
        "PREPARED_EXECUTION_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("WORKBENCH_AUTHORITY_RUNTIME_FILE", "/tmp/fixture-not-read.json")
    monkeypatch.setenv("WORKBENCH_ALLOWED_HOST", "review.test")
    monkeypatch.setenv("WORKBENCH_ALLOWED_ORIGIN", "https://review.test")
    monkeypatch.setattr(console_app, "_business_problem_application", object())
    monkeypatch.setattr(
        console_app,
        "_digital_employee_assembly",
        SimpleNamespace(employee_definitions=object(), repository=object()),
    )
    monkeypatch.setattr(
        console_app, "_agent_definition_service", SimpleNamespace(repository=object())
    )
    # Restore globals after testing the real function, not a cloned source fragment.
    monkeypatch.setattr(console_app, "_workbench_composition", None)
    monkeypatch.setattr(console_app, "_draft_assistance_composition", None)
    monkeypatch.setattr(console_app, "workbench_app", None)
    monkeypatch.setattr(console_app, "_workbench_startup_error", "WORKBENCH_DISABLED")
    captured = []
    application = FastAPI()

    def capture(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(application=application)

    monkeypatch.setattr(workbench_bootstrap, "build_workbench_composition", capture)
    console_app._configure_workbench()
    if expected is None:
        assert not captured
        assert console_app.workbench_app is None
        assert console_app._workbench_startup_error == "WORKBENCH_AUTHORITY_UNAVAILABLE"
    else:
        assert console_app.workbench_app is application
        assert len(captured) == 1
        assert (
            captured[0]["sales_v2_candidate"],
            captured[0]["sales_supplement_candidate"],
        ) == expected


def mode_client(a, acl, *, enabled):
    a.e.app.sales_supplement_candidate = enabled
    sessions = SessionStub(a.subject.principal_id)
    sessions.context = a.subject
    application = create_workbench_bff(
        sessions,
        ExactFixtureBffAuthorizer(a, acl),
        WorkbenchBffPolicy("review.test", "https://review.test"),
        operations=(
            *operations(
                a.e.app, a.services, enabled=enabled, sales_v2_candidate=enabled
            ),
            *planning_operations(a.e.app),
        ),
    )
    client = TestClient(application, base_url="https://review.test")
    client.cookies.set("__Host-workbench_session", sessions.secret)
    return client


HEADERS = {"Origin": "https://review.test", "X-CSRF-Token": "csrf-token"}


def test_close_profile_keeps_old_new_records_exact_acl_and_blocks_new_writes(
    automation, record_property
):
    a = automation
    s = prepare_supplement_fixture(a)
    base = "/api/workbench/v1/planning-v2/" + s.old.plan_id
    path = base + "/sales-supplements"
    body = s.spec.model_dump(mode="json")
    before = snapshot(a)
    with mode_client(a, s.acl, enabled=True) as client:
        created = client.post(path, json=body, headers=HEADERS)
        assert created.status_code == 200, created.text
        result = created.json()["result"]
    assert result["proposal"]["origin"]["kind"] == "HUMAN_RESOURCE_SUPPLEMENT"
    after_creation = snapshot(a)
    assert (
        after_creation["workflow_planning.plans"] == before["workflow_planning.plans"]
    )
    confirmation = {
        "version": result["proposal"]["revision"],
        "digest": result["digest"],
        "expectedPlanVersion": s.old.version,
        "idempotencyKey": "close-test-confirm",
    }
    receipt_path = path + "/by-key/" + s.spec.idempotency_key
    s.acl.allowed.add(
        ("SKILL", "MANAGE_RESOURCE", target("skill", s.spec.skill.resource_id))
    )
    with mode_client(a, s.acl, enabled=False) as client:
        assert client.get(receipt_path).json()["result"] == result
        old = client.get(base, params={"version": s.old.source_proposal_revision})
        new = client.get(base, params={"version": result["proposal"]["revision"]})
        assert old.status_code == new.status_code == 200
        assert old.json()["result"]["proposal"]["invocation_id"] is not None
        assert new.json()["result"]["digest"] == result["digest"]
        # Same owner receipt, current authority; this does not republish the draft.
        original_skill = a.refs["skill"]
        skill_path = (
            "/api/workbench/v1/prepared-resources/skill/"
            + original_skill.resource_id
            + "/revisions/"
            + original_skill.revision_id
            + "/successors"
        )
        saved_skill = client.get(skill_path + "/by-key/isolated-successor-key")
        assert saved_skill.status_code == 200
        assert saved_skill.json()["result"]["published"] is False
        assert client.post(path, json=body, headers=HEADERS).status_code == 404
        assert client.post(skill_path, json={}, headers=HEADERS).status_code == 404
        blocked = client.post(base + "/confirm", json=confirmation, headers=HEADERS)
        assert blocked.status_code == 409
        assert blocked.json()["reasonCode"] == "SALES_SUPPLEMENT_WRITES_DISABLED"
        assert snapshot(a) == after_creation
        permission = ("PLAN", "READ", "plan:v2:" + s.old.plan_id)
        s.acl.allowed.remove(permission)
        assert client.get(receipt_path).status_code == 404
        assert (
            client.get(
                base, params={"version": result["proposal"]["revision"]}
            ).status_code
            == 404
        )
        s.acl.allowed.add(permission)
        criterion = (
            "SUCCESS_CRITERION",
            "READ",
            "success-criterion:revision:" + s.spec.new_target.criterion_revision_ids[0],
        )
        s.acl.allowed.remove(criterion)
        assert client.get(receipt_path).status_code == 404
        s.acl.allowed.add(criterion)
    with mode_client(a, s.acl, enabled=True) as client:
        confirmed = client.post(base + "/confirm", json=confirmation, headers=HEADERS)
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["result"]["plan"]["version"] == s.old.version + 1
    after_confirmation = snapshot(a)
    with mode_client(a, s.acl, enabled=False) as client:
        history = client.get(base + "/history")
        assert history.status_code == 200, history.text
        assert len(history.json()["result"]["plans"]) == s.old.version + 1
        assert client.get(receipt_path).json()["result"] == result
        assert snapshot(a) == after_confirmation
    assert set(before["workflow_planning.plans"]) < set(
        after_confirmation["workflow_planning.plans"]
    )
    assert set(before["workflow_planning.proposals"]) < set(
        after_confirmation["workflow_planning.proposals"]
    )
    for table in ("authorization_admin.grants", "execution_authority.workflow_runs"):
        assert before[table] == after_confirmation[table]
    record_property(
        "compatible_close_profile",
        "old/new proposal and confirmed Plan readable; exact ACL enforced; "
        "no record deletion",
    )


def test_closed_composition_exposes_only_existing_authorized_get_ports():
    assert operations(None, None) == ()
    routes = operations(object(), {"skill": object()})
    assert [(r.name, r.method) for r in routes] == [
        ("READ_PREPARED_SKILL_SUCCESSOR", "GET"),
        ("READ_SALES_SUPPLEMENT", "GET"),
    ]


@pytest.mark.parametrize("enabled", [False, True])
def test_real_bootstrap_carries_mode_to_owner_and_routes(
    automation, monkeypatch, tmp_path, enabled
):
    a = automation
    for key in (
        "BUSINESS_ONTOLOGY_ENABLED",
        "BOUNDED_TASK_AUTHORIZATION_ROOTS",
        "RESOURCE_PREPARATION_POLICY",
        "READONLY_CONTINUATION_POLICY",
        "RESOURCE_MANAGEMENT_POLICY",
    ):
        monkeypatch.delenv(key, raising=False)
    captured = {}
    foundation = SimpleNamespace(
        generation_controller=object(),
        repository=object(),
        grants=SimpleNamespace(
            authorization=object(),
            clock=lambda: None,
            identity_factory=lambda _: "isolated-bootstrap",
        ),
        sessions=object(),
        continuation_owner=SimpleNamespace(signing_key=b"k" * 32),
        close=lambda: None,
    )
    monkeypatch.setattr(
        workbench_bootstrap,
        "build_authority_foundation",
        lambda *args, **kwargs: foundation,
    )

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return FastAPI()

    monkeypatch.setattr(workbench_bootstrap, "create_workbench_bff", capture)
    dsn = a.repository.pool.conninfo
    workbench_bootstrap.build_workbench_composition(
        runtime_configuration_path=runtime_file(tmp_path, dsn),
        allowed_host="review.test",
        allowed_origin="https://review.test",
        owner_database_url=dsn,
        agent_database_url=dsn,
        business_problems=SimpleNamespace(problems=a.e.app.problems),
        agent_definitions=a.services["agent"].repository,
        employee_definitions=object(),
        digital_employees=object(),
        planning_v2_enabled=True,
        prepared_execution_coordinator=SimpleNamespace(repository=a.repository),
        prepared_resource_services=a.services,
        sales_v2_candidate=enabled,
        sales_supplement_candidate=enabled,
    )
    routes = {r.name: r for r in captured["operations"]}
    assert (
        routes["CONFIRM_PLAN_V2"].handler.application.sales_supplement_candidate
        is enabled
    )
    assert "READ_SALES_SUPPLEMENT" in routes
    assert "READ_PREPARED_SKILL_SUCCESSOR" in routes
    assert ("PREPARE_SALES_SUPPLEMENT" in routes) is enabled
    assert ("PREPARE_PREPARED_SKILL_SUCCESSOR" in routes) is enabled
