from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_current_task_target_remains_definition_facing():
    task_schema = yaml.safe_load(
        (REPOSITORY_ROOT / "manifests/crd/tasks.agentos.io.yaml").read_text()
    )
    spec = task_schema["spec"]["versions"][0]["schema"]["openAPIV3Schema"][
        "properties"
    ]["spec"]

    assert spec["required"] == ["agentRef", "input"]
    assert spec["properties"]["agentRef"]["required"] == ["name"]
    assert "instanceRef" not in spec["properties"]


def test_rollback_limits_core_consumers_to_exact_authorized_paths():
    production_roots = {
        "manifests",
        "operator",
        "runtime",
        "gateway",
        "console",
        "workflow",
    }
    prototype_imports = []
    for root_name in production_roots:
        for path in (REPOSITORY_ROOT / root_name).rglob("*.py"):
            if "agent_core" in path.read_text():
                prototype_imports.append(path)

    discovered_imports = {
        path.relative_to(REPOSITORY_ROOT).as_posix() for path in prototype_imports
    }
    authorized_gateway_imports = {
        "gateway/src/agent_gateway/capability/models.py",
        "gateway/tests/test_capability_gateway.py",
    }
    authorized_console_imports = {
        "console/backend/src/agent_console/app.py",
        "console/backend/src/agent_console/execution_snapshot.py",
        "console/backend/src/agent_console/preview_service.py",
        "console/backend/src/agent_console/shared_views.py",
        "console/backend/tests/test_execution_evidence_security.py",
        "console/backend/tests/test_execution_snapshot.py",
        "console/backend/tests/test_preview_api.py",
        "console/backend/tests/test_shared_views.py",
    }

    assert discovered_imports == {
        *authorized_gateway_imports,
        *authorized_console_imports,
        "operator/src/agent_operator/compatibility_interpreter/interpreter.py",
        "operator/src/agent_operator/execution_coordinator.py",
        "operator/src/agent_operator/identity_adapter.py",
        "operator/src/agent_operator/runtime_identity_translation.py",
        "operator/src/agent_operator/runtime_kubernetes_observer.py",
        "operator/src/agent_operator/runtime_manager.py",
        "operator/src/agent_operator/task_controller.py",
        "operator/tests/test_compatibility_interpreter.py",
        "operator/tests/test_execution_coordinator.py",
        "operator/tests/test_identity_adapter.py",
    }
    assert {
        path for path in discovered_imports if path.startswith("gateway/")
    } == authorized_gateway_imports
    assert {
        path for path in discovered_imports if path.startswith("console/")
    } == authorized_console_imports
    assert "console/backend/src/agent_console/repository.py" not in discovered_imports
