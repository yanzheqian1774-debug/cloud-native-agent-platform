from agent_operator.resources import build_agent_deployment


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

    # assert container["name"] == "agent"
    # assert container["image"] == "nginx:1.27-alpine"
    # assert container["imagePullPolicy"] == "IfNotPresent"

    assert container["image"] == "enterprise-agent-runtime:v0.1"
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
