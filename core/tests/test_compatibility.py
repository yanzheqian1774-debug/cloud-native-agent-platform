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


def test_rollback_limits_core_consumers_to_component_only_adapter():
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

    assert {
        path.relative_to(REPOSITORY_ROOT).as_posix() for path in prototype_imports
    } == {
        "operator/src/agent_operator/identity_adapter.py",
        "operator/tests/test_identity_adapter.py",
    }
