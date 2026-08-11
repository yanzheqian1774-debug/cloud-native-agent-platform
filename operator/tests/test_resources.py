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

    assert container["name"] == "agent"
    assert container["image"] == "nginx:1.27-alpine"
    assert container["imagePullPolicy"] == "IfNotPresent"
