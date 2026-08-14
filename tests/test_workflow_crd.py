from pathlib import Path

import yaml

WORKFLOW_CRD_PATH = Path("manifests/crd/workflows.agentos.io.yaml")


def load_workflow_crd() -> dict:
    with WORKFLOW_CRD_PATH.open() as file:
        return yaml.safe_load(file)


def get_workflow_schema() -> dict:
    crd = load_workflow_crd()
    return crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]


def test_workflow_crd_basic_identity() -> None:
    crd = load_workflow_crd()

    assert crd["apiVersion"] == "apiextensions.k8s.io/v1"
    assert crd["kind"] == "CustomResourceDefinition"
    assert crd["metadata"]["name"] == "workflows.agentos.io"

    spec = crd["spec"]

    assert spec["group"] == "agentos.io"
    assert spec["scope"] == "Namespaced"
    assert spec["names"]["kind"] == "Workflow"
    assert spec["names"]["plural"] == "workflows"
    assert spec["names"]["shortNames"] == ["wf"]


def test_workflow_crd_requires_non_empty_tasks() -> None:
    schema = get_workflow_schema()
    workflow_spec = schema["properties"]["spec"]

    assert workflow_spec["required"] == ["tasks"]

    tasks = workflow_spec["properties"]["tasks"]

    assert tasks["type"] == "array"
    assert tasks["minItems"] == 1


def test_workflow_task_required_fields() -> None:
    schema = get_workflow_schema()

    task = schema["properties"]["spec"]["properties"]["tasks"]["items"]

    assert set(task["required"]) == {
        "name",
        "agentRef",
        "input",
    }

    assert task["properties"]["name"]["minLength"] == 1

    agent_ref = task["properties"]["agentRef"]
    assert agent_ref["required"] == ["name"]
    assert agent_ref["properties"]["name"]["minLength"] == 1

    task_input = task["properties"]["input"]
    assert task_input["required"] == ["prompt"]
    assert task_input["properties"]["prompt"]["minLength"] == 1


def test_workflow_task_dependency_model() -> None:
    schema = get_workflow_schema()

    task = schema["properties"]["spec"]["properties"]["tasks"]["items"]
    depends_on = task["properties"]["dependsOn"]

    assert depends_on["type"] == "array"
    assert depends_on["default"] == []
    assert depends_on["items"]["type"] == "string"
    assert depends_on["items"]["minLength"] == 1


def test_workflow_task_timeout() -> None:
    schema = get_workflow_schema()

    task = schema["properties"]["spec"]["properties"]["tasks"]["items"]
    timeout = task["properties"]["timeoutSeconds"]

    assert timeout["type"] == "integer"
    assert timeout["minimum"] == 1
    assert timeout["default"] == 300


def test_workflow_crd_phase_lifecycle() -> None:
    schema = get_workflow_schema()

    phase = schema["properties"]["status"]["properties"]["phase"]

    assert phase["enum"] == [
        "Pending",
        "Running",
        "Succeeded",
        "Failed",
    ]


def test_workflow_task_status_supports_visual_execution_states() -> None:
    schema = get_workflow_schema()

    task_status = schema["properties"]["status"]["properties"]["tasks"][
        "additionalProperties"
    ]
    properties = task_status["properties"]

    assert properties["phase"]["enum"] == [
        "Pending",
        "Running",
        "Succeeded",
        "Failed",
        "TimedOut",
        "Skipped",
    ]

    assert properties["taskRef"]["properties"]["name"]["type"] == "string"
    assert properties["reason"]["type"] == "string"
    assert properties["message"]["type"] == "string"


def test_workflow_status_supports_execution_summary() -> None:
    schema = get_workflow_schema()

    status = schema["properties"]["status"]["properties"]

    assert status["startedAt"]["format"] == "date-time"
    assert status["completedAt"]["format"] == "date-time"
    assert status["taskCount"]["type"] == "integer"
    assert status["taskCount"]["minimum"] == 0


def test_workflow_crd_has_status_subresource() -> None:
    crd = load_workflow_crd()

    version = crd["spec"]["versions"][0]

    assert version["subresources"] == {
        "status": {},
    }
