import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from agent_runtime.providers.openclaw import (
    EXACT_TARGET,
    EnvironmentSecretReferenceResolver,
    OpenClawProductionConfig,
    OpenClawProductionTransport,
)
from agent_runtime.providers.openclaw.models import (
    ExecutionLinkage,
    ExecutionRequest,
    OpenClawError,
    ReasonCode,
    RuntimeBinding,
    RuntimeMode,
    SessionAffinity,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value))


def _fixture(tmp_path: Path) -> OpenClawProductionConfig:
    manifest = tmp_path / "target.json"
    lock = tmp_path / "package-lock.json"
    node = tmp_path / "node"
    entrypoint = tmp_path / "openclaw.mjs"
    client_config = tmp_path / "client.json"
    client_state = tmp_path / "client-state"
    workspace = tmp_path / "agent-workspace"
    node.touch()
    entrypoint.touch()
    client_state.mkdir()
    workspace.mkdir()
    _write_json(
        manifest,
        {
            "provider": "openclaw",
            "runtime_exact_version": EXACT_TARGET.version,
            "runtime_tag_commit": EXACT_TARGET.tag_commit,
            "npm_integrity": EXACT_TARGET.package_integrity,
            "profile": "external-single-gateway-isolated-agent-workspace",
        },
    )
    _write_json(
        lock,
        {
            "lockfileVersion": 3,
            "packages": {
                "node_modules/openclaw": {
                    "version": EXACT_TARGET.version,
                    "integrity": EXACT_TARGET.package_integrity,
                }
            },
        },
    )
    _write_json(
        client_config,
        {
            "gateway": {
                "mode": "remote",
                "remote": {
                    "url": "ws://127.0.0.1:19314",
                    "token": "${OPENCLAW_GATEWAY_TOKEN}",
                },
            }
        },
    )
    return OpenClawProductionConfig(
        manifest,
        lock,
        node,
        entrypoint,
        client_config,
        client_state,
        "platform-agent",
        workspace,
        "secret-ref:openclaw-gateway",
    )


class SuccessfulRunner:
    def __init__(self, config: OpenClawProductionConfig) -> None:
        self.config = config
        self.calls: list[tuple[tuple[str, ...], dict[str, str], float]] = []

    def __call__(self, argv, env, timeout):
        self.calls.append((argv, dict(env), timeout))
        if argv[-1] == "--version" and len(argv) == 2:
            output = "v22.23.1"
        elif argv[-1] == "--version":
            output = f"OpenClaw {EXACT_TARGET.version} ({EXACT_TARGET.tag_commit[:7]})"
        else:
            method = argv[4]
            output = json.dumps(
                {
                    "health": {"eventLoop": {"degraded": False}},
                    "status": {"runtimeVersion": EXACT_TARGET.version},
                    "agents.list": {
                        "agents": [
                            {
                                "id": "platform-agent",
                                "workspace": str(self.config.agent_workspace),
                            }
                        ]
                    },
                }[method]
            )
        return subprocess.CompletedProcess(argv, 0, output, "")


def _transport(tmp_path: Path):
    config = _fixture(tmp_path)
    runner = SuccessfulRunner(config)
    transport = OpenClawProductionTransport(
        config,
        EnvironmentSecretReferenceResolver(
            "secret-ref:openclaw-gateway",
            environment={"OPENCLAW_GATEWAY_TOKEN": "fixture-token"},
        ),
        runner=runner,
    )
    return config, runner, transport


def test_preflight_validates_exact_target_auth_readiness_and_workspace(
    tmp_path: Path,
) -> None:
    _, runner, transport = _transport(tmp_path)

    assert transport.preflight() == EXACT_TARGET
    assert [call[0][4] for call in runner.calls if "call" in call[0]] == [
        "health",
        "status",
        "agents.list",
    ]
    for argv, environment, _ in runner.calls:
        assert "fixture-token" not in argv
        if "call" in argv:
            assert environment["OPENCLAW_GATEWAY_TOKEN"] == "fixture-token"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("integrity", ReasonCode.PACKAGE_INTEGRITY_MISMATCH),
        ("version", ReasonCode.VERSION_UNSUPPORTED),
        ("node", ReasonCode.NODE_VERSION_UNSUPPORTED),
        ("config", ReasonCode.CONFIGURATION_MISSING),
    ],
)
def test_preflight_failures_are_distinct_and_happen_before_gateway_calls(
    tmp_path: Path, mutation: str, code: ReasonCode
) -> None:
    config = _fixture(tmp_path)
    if mutation == "integrity":
        lock = json.loads(config.package_lock_path.read_text())
        lock["packages"]["node_modules/openclaw"]["integrity"] = "sha512-wrong"
        _write_json(config.package_lock_path, lock)
    elif mutation == "version":
        manifest = json.loads(config.manifest_path.read_text())
        manifest["runtime_exact_version"] = "2026.7.2"
        _write_json(config.manifest_path, manifest)
    elif mutation == "config":
        _write_json(config.client_config_path, {"gateway": {"mode": "local"}})

    runner = SuccessfulRunner(config)
    if mutation == "node":
        original = runner.__call__

        def unsupported_node(argv, env, timeout):
            if argv[-1] == "--version" and len(argv) == 2:
                return subprocess.CompletedProcess(argv, 0, "v22.22.2", "")
            return original(argv, env, timeout)

        command_runner = unsupported_node
    else:
        command_runner = runner
    transport = OpenClawProductionTransport(
        config,
        EnvironmentSecretReferenceResolver(
            "secret-ref:openclaw-gateway",
            environment={"OPENCLAW_GATEWAY_TOKEN": "fixture-token"},
        ),
        runner=command_runner,
    )

    with pytest.raises(OpenClawError, match=code.value):
        transport.preflight()
    assert not any("call" in call[0] for call in runner.calls)


@pytest.mark.parametrize(
    ("stderr", "code"),
    [
        ("authentication failed", ReasonCode.GATEWAY_AUTHENTICATION_FAILED),
        ("ECONNREFUSED", ReasonCode.GATEWAY_UNAVAILABLE),
        ("unexpected gateway response", ReasonCode.GATEWAY_PROTOCOL_ERROR),
    ],
)
def test_gateway_failures_are_sanitized(
    tmp_path: Path, stderr: str, code: ReasonCode
) -> None:
    config = _fixture(tmp_path)
    successful = SuccessfulRunner(config)

    def failing_rpc(argv, env, timeout):
        if "call" in argv:
            return subprocess.CompletedProcess(argv, 1, "", stderr)
        return successful(argv, env, timeout)

    transport = OpenClawProductionTransport(
        config,
        EnvironmentSecretReferenceResolver(
            "secret-ref:openclaw-gateway",
            environment={"OPENCLAW_GATEWAY_TOKEN": "fixture-token"},
        ),
        runner=failing_rpc,
    )

    with pytest.raises(OpenClawError, match=code.value) as failure:
        transport.preflight()
    assert stderr not in str(failure.value)
    assert "fixture-token" not in str(failure.value)


def test_lifecycle_and_execution_are_explicitly_unsupported_without_mapping(
    tmp_path: Path,
) -> None:
    _, runner, transport = _transport(tmp_path)
    binding = RuntimeBinding(
        "tenant-a",
        "domain-a",
        "runtime-1",
        "placement-1",
        1,
        RuntimeMode.STATELESS,
        SessionAffinity.NONE,
    )
    request = ExecutionRequest(
        ExecutionLinkage(
            "workflow-1", "task-1", "attempt-1", "agent-1", "runtime-1", "placement-1"
        ),
        "input-reference",
        "idempotency-key",
    )

    lifecycle_calls = (
        lambda: transport.start(binding),
        lambda: transport.observe_runtime(binding),
        lambda: transport.stop(binding),
        lambda: transport.replace(replace(binding, generation=2)),
    )
    for call in lifecycle_calls:
        with pytest.raises(
            OpenClawError, match=ReasonCode.RUNTIME_LIFECYCLE_UNSUPPORTED.value
        ):
            call()
    for call in (
        lambda: transport.execute(request),
        lambda: transport.observe_execution(request),
    ):
        with pytest.raises(OpenClawError, match=ReasonCode.EXECUTION_UNSUPPORTED.value):
            call()
    assert runner.calls == []


def test_recovery_read_seam_rejects_every_write_rpc_before_process_call(
    tmp_path: Path,
) -> None:
    _, runner, transport = _transport(tmp_path)

    for method in (
        "agents.create",
        "agents.update",
        "agents.delete",
        "sessions.create",
        "sessions.patch",
        "sessions.delete",
        "sessions.abort",
        "chat.abort",
    ):
        with pytest.raises(
            OpenClawError, match=ReasonCode.GATEWAY_PROTOCOL_ERROR.value
        ):
            transport.read_only_rpc(method, {})
    assert runner.calls == []
