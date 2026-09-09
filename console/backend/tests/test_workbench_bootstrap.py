from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from agent_console import app as console_app
from agent_console import workbench_bootstrap
from agent_console.authority_contracts import AuthorityError
from fastapi import FastAPI, HTTPException


def runtime_file(tmp_path, database_url: str):
    path = tmp_path / "authority-runtime.json"
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "authority-foundation-runtime.v1",
                "databaseUrl": database_url,
                "migrationPath": str(tmp_path / "0018.sql"),
                "generationPath": str(tmp_path / "generation.json"),
                "generationDigest": "a" * 64,
                "csrfSigningKeyPath": str(tmp_path / "csrf.key"),
                "continuationSigningKeyPath": str(tmp_path / "continuation.key"),
                "recoveryControlPath": str(tmp_path / "recovery.json"),
                "databaseFingerprint": "workbench-test",
                "operatorId": "operator:test",
            }
        )
    )
    return path


def test_composition_registers_business_and_read_only_workflow_operations(
    tmp_path, monkeypatch
) -> None:
    captured = {}
    foundation = SimpleNamespace(
        generation_controller=object(),
        repository=object(),
        grants=SimpleNamespace(authorization=object()),
        sessions=object(),
        close=lambda: None,
    )
    monkeypatch.setattr(
        workbench_bootstrap, "build_authority_foundation", lambda *args: foundation
    )

    def capture(_sessions, _authorizer, _policy, *, operations):
        captured["operations"] = operations
        return FastAPI()

    monkeypatch.setattr(workbench_bootstrap, "create_workbench_bff", capture)
    database_url = "postgresql://db.example/platform"
    composition = workbench_bootstrap.build_workbench_composition(
        runtime_configuration_path=runtime_file(tmp_path, database_url),
        allowed_host="console.example",
        allowed_origin="https://console.example",
        owner_database_url=database_url,
        workflow_database_url=database_url,
        business_problems=SimpleNamespace(),
        employee_definitions=SimpleNamespace(),
        workflows=SimpleNamespace(),
    )

    assert composition.foundation is foundation
    operations = captured["operations"]
    assert len(operations) == 16
    assert [(item.name, item.method, item.path) for item in operations[-3:]] == [
        (
            "READ_EMPLOYEE_REVISION",
            "GET",
            "/api/workbench/v1/employees/{employee_definition_id}/revisions/{revision_id}",
        ),
        ("LIST_WORKFLOWS", "GET", "/api/workbench/v1/workflows"),
        (
            "READ_WORKFLOW_REVISION",
            "GET",
            "/api/workbench/v1/workflows/{workflow_definition_id}/revisions/{revision_id}",
        ),
    ]
    assert not any(
        item.name.startswith(("CREATE_WORKFLOW", "EDIT_WORKFLOW", "PUBLISH_WORKFLOW"))
        for item in operations
    )


def test_composition_keeps_existing_business_routes_without_optional_workflow(
    tmp_path, monkeypatch
) -> None:
    captured = {}
    foundation = SimpleNamespace(
        generation_controller=object(),
        repository=object(),
        grants=SimpleNamespace(authorization=object()),
        sessions=object(),
        close=lambda: None,
    )
    monkeypatch.setattr(
        workbench_bootstrap, "build_authority_foundation", lambda *args: foundation
    )

    def capture(_sessions, _authorizer, _policy, *, operations):
        captured["operations"] = operations
        return FastAPI()

    monkeypatch.setattr(workbench_bootstrap, "create_workbench_bff", capture)
    database_url = "postgresql://db.example/platform"
    workbench_bootstrap.build_workbench_composition(
        runtime_configuration_path=runtime_file(tmp_path, database_url),
        allowed_host="console.example",
        allowed_origin="https://console.example",
        owner_database_url=database_url,
        business_problems=SimpleNamespace(),
        employee_definitions=SimpleNamespace(),
    )

    operations = captured["operations"]
    assert len(operations) == 14
    assert any(item.name == "READ_EMPLOYEE_REVISION" for item in operations)
    assert not any(
        item.name in {"LIST_WORKFLOWS", "READ_WORKFLOW_REVISION"} for item in operations
    )


def test_configured_workflow_cannot_silently_degrade_when_service_is_unavailable(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        workbench_bootstrap,
        "build_authority_foundation",
        lambda *args: pytest.fail("authority foundation must not open"),
    )

    with pytest.raises(AuthorityError, match="WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"):
        workbench_bootstrap.build_workbench_composition(
            runtime_configuration_path=runtime_file(
                tmp_path, "postgresql://db.example/platform"
            ),
            allowed_host="console.example",
            allowed_origin="https://console.example",
            owner_database_url="postgresql://db.example/platform",
            workflow_database_url="postgresql://db.example/platform",
            business_problems=SimpleNamespace(),
            employee_definitions=SimpleNamespace(),
        )


def test_app_does_not_require_optional_workflow_for_existing_composition(
    monkeypatch,
) -> None:
    built = {}
    application = FastAPI()
    monkeypatch.setenv("WORKBENCH_AUTHORITY_RUNTIME_FILE", "/tmp/authority.json")
    monkeypatch.setenv("WORKBENCH_ALLOWED_HOST", "console.example")
    monkeypatch.setenv("WORKBENCH_ALLOWED_ORIGIN", "https://console.example")
    monkeypatch.setenv("EXECUTION_DATABASE_URL", "postgresql://db.example/platform")
    monkeypatch.delenv("WORKFLOW_RUNTIME_DATABASE_URL", raising=False)
    monkeypatch.setattr(console_app, "_business_problem_application", object())
    monkeypatch.setattr(
        console_app,
        "_digital_employee_assembly",
        SimpleNamespace(employee_definitions=object()),
    )
    monkeypatch.setattr(console_app, "_workbench_composition", None)
    monkeypatch.setattr(console_app, "workbench_app", None)
    monkeypatch.setattr(console_app, "_workbench_startup_error", "WORKBENCH_DISABLED")
    monkeypatch.setattr(
        console_app.workflow_definition_api,
        "get_service",
        lambda: pytest.fail("optional Workflow service must not be required"),
    )

    def build(**values):
        built.update(values)
        return SimpleNamespace(application=application)

    monkeypatch.setattr(workbench_bootstrap, "build_workbench_composition", build)

    console_app._configure_workbench()

    assert console_app.workbench_app is application
    assert built["workflow_database_url"] == ""
    assert built["workflows"] is None
    assert built["employee_definitions"] is not None


def test_app_fails_closed_when_configured_workflow_service_is_unavailable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("WORKBENCH_AUTHORITY_RUNTIME_FILE", "/tmp/authority.json")
    monkeypatch.setenv("WORKBENCH_ALLOWED_HOST", "console.example")
    monkeypatch.setenv("WORKBENCH_ALLOWED_ORIGIN", "https://console.example")
    monkeypatch.setenv("EXECUTION_DATABASE_URL", "postgresql://db.example/platform")
    monkeypatch.setenv(
        "WORKFLOW_RUNTIME_DATABASE_URL", "postgresql://db.example/platform"
    )
    monkeypatch.setattr(console_app, "_business_problem_application", object())
    monkeypatch.setattr(
        console_app,
        "_digital_employee_assembly",
        SimpleNamespace(employee_definitions=object()),
    )
    monkeypatch.setattr(console_app, "_workbench_composition", None)
    monkeypatch.setattr(console_app, "workbench_app", None)
    monkeypatch.setattr(console_app, "_workbench_startup_error", "WORKBENCH_DISABLED")
    monkeypatch.setattr(
        console_app.workflow_definition_api,
        "get_service",
        lambda: (_ for _ in ()).throw(HTTPException(503)),
    )
    monkeypatch.setattr(
        workbench_bootstrap,
        "build_workbench_composition",
        lambda **values: pytest.fail("composition must not build"),
    )

    console_app._configure_workbench()

    assert console_app.workbench_app is None
    assert console_app._workbench_startup_error == (
        "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"
    )


def test_composition_rejects_workflow_database_outside_authorization_transaction(
    tmp_path, monkeypatch
) -> None:
    built = False

    def unexpected(*args):
        nonlocal built
        built = True

    monkeypatch.setattr(workbench_bootstrap, "build_authority_foundation", unexpected)

    with pytest.raises(AuthorityError, match="OWNER_TRANSACTION_UNAVAILABLE") as raised:
        workbench_bootstrap.build_workbench_composition(
            runtime_configuration_path=runtime_file(
                tmp_path, "postgresql://authority:secret@db.example/platform"
            ),
            allowed_host="console.example",
            allowed_origin="https://console.example",
            owner_database_url="postgresql://owner:secret@db.example/platform",
            workflow_database_url="postgresql://workflow:secret@db.example/workflow",
            business_problems=SimpleNamespace(),
            employee_definitions=SimpleNamespace(),
            workflows=SimpleNamespace(),
        )

    assert not built
    assert "secret" not in str(raised.value)
