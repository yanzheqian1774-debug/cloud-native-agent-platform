from pathlib import Path

import yaml

TASK_CRD_PATH = Path("manifests/crd/tasks.agentos.io.yaml")


def load_task_crd() -> dict:
    with TASK_CRD_PATH.open() as file:
        return yaml.safe_load(file)


def test_task_crd_basic_identity() -> None:
    crd = load_task_crd()

    assert crd["apiVersion"] == "apiextensions.k8s.io/v1"
    assert crd["kind"] == "CustomResourceDefinition"
    assert crd["metadata"]["name"] == "tasks.agentos.io"

    spec = crd["spec"]

    assert spec["group"] == "agentos.io"
    assert spec["scope"] == "Namespaced"
    assert spec["names"]["kind"] == "Task"
    assert spec["names"]["plural"] == "tasks"


def test_task_crd_required_fields() -> None:
    crd = load_task_crd()

    schema = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    task_spec = schema["properties"]["spec"]

    assert set(task_spec["required"]) == {
        "agentRef",
        "input",
    }

    agent_ref = task_spec["properties"]["agentRef"]
    assert "name" in agent_ref["required"]

    task_input = task_spec["properties"]["input"]
    assert "prompt" in task_input["required"]

    prompt = task_input["properties"]["prompt"]
    assert prompt["minLength"] == 1


def test_task_crd_phase_lifecycle() -> None:
    crd = load_task_crd()

    schema = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
    phase = schema["properties"]["status"]["properties"]["phase"]

    assert phase["enum"] == [
        "Pending",
        "Running",
        "Succeeded",
        "Failed",
    ]


def test_task_crd_has_status_subresource() -> None:
    crd = load_task_crd()

    version = crd["spec"]["versions"][0]

    assert version["subresources"] == {
        "status": {},
    }
