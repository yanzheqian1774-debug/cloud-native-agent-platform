from agent_operator.resources import (
    build_agent_deployment,
    build_agent_service,
    build_workflow_task,
)


def test_build_agent_deployment() -> None:
    deployment = build_agent_deployment(
        name="test-agent",
        namespace="agent-workloads",
        spec={
            "replicas": 2,
            "runtime": {"type": "native"},
            "model": {
                "provider": "mock",
                "name": "mock-model",
            },
        },
    )

    assert deployment["kind"] == "Deployment"
    assert deployment["metadata"]["name"] == "test-agent"
    assert deployment["metadata"]["namespace"] == "agent-workloads"
    assert deployment["spec"]["replicas"] == 2

    container = deployment["spec"]["template"]["spec"]["containers"][0]

    assert container["name"] == "agent"
    assert container["image"] == "enterprise-agent-runtime:v0.1-dev"
    assert container["imagePullPolicy"] == "IfNotPresent"
    assert container["ports"][0]["containerPort"] == 8080

    env = {item["name"]: item["value"] for item in container["env"]}

    assert env["AGENT_NAME"] == "test-agent"
    assert env["AGENT_NAMESPACE"] == "agent-workloads"
    assert env["AGENT_RUNTIME"] == "native"
    assert env["MODEL_PROVIDER"] == "mock"
    assert env["MODEL_NAME"] == "mock-model"

    assert container["livenessProbe"]["httpGet"]["path"] == "/healthz"
    assert container["readinessProbe"]["httpGet"]["path"] == "/readyz"


def test_build_agent_service() -> None:
    service = build_agent_service(
        name="test-agent",
        namespace="agent-workloads",
    )

    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "test-agent"
    assert service["metadata"]["namespace"] == "agent-workloads"

    assert service["spec"]["type"] == "ClusterIP"

    assert service["spec"]["selector"] == {
        "agentos.io/agent": "test-agent",
    }

    port = service["spec"]["ports"][0]

    assert port["name"] == "http"
    assert port["port"] == 8080
    assert port["targetPort"] == 8080
    assert port["protocol"] == "TCP"


def test_build_agent_deployment_with_openai_compatible_model() -> None:
    deployment = build_agent_deployment(
        name="real-agent",
        namespace="agent-workloads",
        spec={
            "replicas": 1,
            "runtime": {"type": "native"},
            "model": {
                "provider": "openai-compatible",
                "name": "test-model",
                "baseUrl": "https://example.com/v1",
                "secretRef": {
                    "name": "model-credentials",
                    "key": "api-key",
                },
            },
        },
    )

    container = deployment["spec"]["template"]["spec"]["containers"][0]

    env = {item["name"]: item for item in container["env"]}

    assert env["MODEL_PROVIDER"]["value"] == "openai-compatible"
    assert env["MODEL_NAME"]["value"] == "test-model"
    assert env["MODEL_BASE_URL"]["value"] == "https://example.com/v1"

    assert env["MODEL_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "model-credentials",
        "key": "api-key",
    }


def test_build_agent_deployment_with_identity_and_instructions() -> None:
    deployment = build_agent_deployment(
        name="researcher",
        namespace="agent-workloads",
        spec={
            "runtime": {
                "type": "native",
            },
            "model": {
                "provider": "mock",
                "name": "mock-model",
            },
            "identity": {
                "role": "researcher",
                "displayName": "Research Agent",
            },
            "instructions": {
                "systemPrompt": ("You are a research agent managed by AgentOS."),
            },
        },
    )

    container = deployment["spec"]["template"]["spec"]["containers"][0]

    env = {item["name"]: item for item in container["env"]}

    assert env["AGENT_ROLE"]["value"] == "researcher"
    assert env["AGENT_DISPLAY_NAME"]["value"] == "Research Agent"
    assert env["AGENT_SYSTEM_PROMPT"]["value"] == (
        "You are a research agent managed by AgentOS."
    )


def test_build_workflow_task() -> None:
    resource = build_workflow_task(
        workflow_name="research-workflow",
        namespace="agent-workloads",
        task_spec={
            "name": "research",
            "agentRef": {
                "name": "researcher-agent",
            },
            "input": {
                "prompt": "research this topic",
            },
            "timeoutSeconds": 300,
        },
    )

    assert resource["apiVersion"] == "agentos.io/v1alpha1"
    assert resource["kind"] == "Task"

    assert resource["metadata"]["name"] == "research-workflow-research"
    assert resource["metadata"]["namespace"] == "agent-workloads"

    assert resource["metadata"]["labels"] == {
        "app.kubernetes.io/managed-by": "agent-operator",
        "agentos.io/workflow": "research-workflow",
        "agentos.io/workflow-task": "research",
    }

    assert resource["spec"] == {
        "agentRef": {
            "name": "researcher-agent",
        },
        "input": {
            "prompt": "research this topic",
        },
        "timeoutSeconds": 300,
    }


def test_build_agent_deployment_uses_declared_runtime_image() -> None:
    spec = {
        "runtime": {
            "type": "native",
            "image": "enterprise-agent-runtime:test-image",
        },
        "model": {
            "provider": "mock",
            "name": "mock-model",
        },
        "replicas": 1,
    }

    deployment = build_agent_deployment(
        name="test-agent",
        namespace="agent-workloads",
        spec=spec,
    )

    container = deployment["spec"]["template"]["spec"]["containers"][0]

    assert container["image"] == "enterprise-agent-runtime:test-image"


def test_build_agent_deployment_uses_default_runtime_image() -> None:
    spec = {
        "runtime": {
            "type": "native",
        },
        "model": {
            "provider": "mock",
            "name": "mock-model",
        },
        "replicas": 1,
    }

    deployment = build_agent_deployment(
        name="test-agent",
        namespace="agent-workloads",
        spec=spec,
    )

    container = deployment["spec"]["template"]["spec"]["containers"][0]

    assert container["image"] == "enterprise-agent-runtime:v0.1-dev"
