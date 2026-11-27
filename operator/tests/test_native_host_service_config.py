"""Pinned deployment configuration only; no production composition is started."""

import hashlib
import json
from pathlib import Path

import pytest
from agent_operator import native_host_service_config as module
from agent_operator.native_host_service_config import Configuration
from agent_operator.native_host_service_state import write


@pytest.fixture
def configured(tmp_path, monkeypatch):
    loaded = Path(module.__file__).resolve()
    root = loaded.parents[3]
    names = (
        "native_host_service.py",
        "native_host_service_config.py",
        "native_host_service_discovery.py",
        "native_host_service_state.py",
        "native_host_service_child.py",
        "native_dispatch_host.py",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "source": str(root),
                "sourceHashes": {
                    str(loaded.with_name(n).relative_to(root)): hashlib.sha256(
                        loaded.with_name(n).read_bytes()
                    ).hexdigest()
                    for n in names
                },
            }
        )
    )
    from agent_console import bound_service_execution

    bridge_path = Path(bound_service_execution.__file__).resolve()
    manifest_value = json.loads(manifest.read_text())
    manifest_value["sourceHashes"][str(bridge_path.relative_to(root))] = hashlib.sha256(
        bridge_path.read_bytes()
    ).hexdigest()
    manifest.write_text(json.dumps(manifest_value))
    policy_files = {}
    for i, name in enumerate(
        (
            "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION",
            "NATIVE_DISPATCH_CONTINUATION_POLICY",
            "OWNED_BUSINESS_ADMISSION_POLICY",
        )
    ):
        path = tmp_path / f"policy-{i}.json"
        write(path, {"controlled": True})
        monkeypatch.setenv(name, str(path))
        policy_files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in (
        "NATIVE_LOOP_RUNTIME_FILE",
        "NATIVE_DURABLE_WAIT_CONFIGURATION",
        "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
        "NATIVE_HOST_SERVICE_LOCK_FD",
        "NATIVE_HOST_SERVICE_READY_FD",
        "NATIVE_HOST_SERVICE_CONTROL_FD",
        "NATIVE_HOST_STARTUP_CONFIGURATION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NATIVE_DISPATCH_PREPARED_SKILL", "registered-readonly-v1")
    value = {
        "enabled": True,
        "namespace": "ns",
        "securityDomain": "d",
        "principalId": "human:a",
        "stateDirectory": str(tmp_path / "state"),
        "manifestPath": str(manifest),
        "manifestDigest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "policyFiles": policy_files,
        "maxHosts": 2,
        "maxRestarts": 3,
        "pollSeconds": 1,
        "readinessSeconds": 2,
        "shutdownSeconds": 2,
    }
    config = tmp_path / "service.json"
    write(config, value)
    return config, value


def test_pins_actual_installed_files_and_current_policy(
    configured, monkeypatch, tmp_path
):
    path, _ = configured
    config = Configuration(path)
    config.verify()
    import os

    old = Path(os.environ["OWNED_BUSINESS_ADMISSION_POLICY"])
    old.write_text("changed")
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", False),
        ("maxHosts", 9),
        ("maxHosts", True),
        ("maxRestarts", 33),
        ("readinessSeconds", 30),
    ],
)
def test_invalid_or_disabled_never_starts(configured, field, value):
    path, config = configured
    config[field] = value
    write(path, config)
    with pytest.raises(ValueError):
        Configuration(path)


def test_ambient_unpinned_runtime_or_nested_launch_rejected(configured, monkeypatch):
    path, _ = configured
    monkeypatch.setenv("NATIVE_LOOP_RUNTIME_FILE", "/not/pinned")
    with pytest.raises(ValueError, match="POLICY_BINDING"):
        Configuration(path)
    monkeypatch.delenv("NATIVE_LOOP_RUNTIME_FILE")
    monkeypatch.setenv("NATIVE_HOST_SERVICE_CONTROL_FD", "9")
    with pytest.raises(ValueError, match="NESTED"):
        Configuration(path)


def test_durable_configuration_is_optional_but_must_be_pinned(
    configured, monkeypatch, tmp_path
):
    path, value = configured
    Configuration(path).verify()
    wait = tmp_path / "wait.json"
    write(wait, {"controlled": True})
    monkeypatch.setenv("NATIVE_DURABLE_WAIT_CONFIGURATION", str(wait))
    with pytest.raises(ValueError, match="POLICY_BINDING"):
        Configuration(path)
    value["policyFiles"]["NATIVE_DURABLE_WAIT_CONFIGURATION"] = hashlib.sha256(
        wait.read_bytes()
    ).hexdigest()
    write(path, value)
    config = Configuration(path)
    config.verify()
    wait.write_text("changed")
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


@pytest.mark.parametrize("durable", [False, True])
def test_preparation_roundtrip_pins_optional_wait_file(
    configured, monkeypatch, tmp_path, durable
):
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from agent_console.owned_business_policy import OwnedBusinessPolicy
    from agent_operator.native_host_service_prepare import prepare

    _, value = configured
    monkeypatch.setattr(
        OwnedBusinessPolicy,
        "load",
        lambda _: SimpleNamespace(
            enabled=True,
            expiresAt=datetime.now(UTC) + timedelta(hours=1),
            tenantId="ns",
            securityDomain="d",
            subjectId="human:a",
            digest="a" * 64,
        ),
    )
    wait = tmp_path / "optional-wait.json"
    if durable:
        write(wait, {"controlled": True})
        monkeypatch.setenv("NATIVE_DURABLE_WAIT_CONFIGURATION", str(wait))
    output = tmp_path / "prepared" / "service.json"
    prepare(value["manifestPath"], tmp_path / "new-state", output, enabled=True)
    config = Configuration(output)
    config.verify()
    assert (
        "NATIVE_DURABLE_WAIT_CONFIGURATION" in config.value["policyFiles"]
    ) is durable
    if durable:
        assert config.value["policyFiles"]["NATIVE_DURABLE_WAIT_CONFIGURATION"] == (
            hashlib.sha256(wait.read_bytes()).hexdigest()
        )
        wait.write_text("changed")
        with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
            config.verify()


def test_optional_ontology_correction_must_be_pinned(configured, monkeypatch, tmp_path):
    path, value = configured
    candidate = tmp_path / "correction.json"
    write(candidate, {"controlled": "correction"})
    monkeypatch.setenv("OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY", str(candidate))
    with pytest.raises(ValueError, match="POLICY_BINDING_REQUIRED"):
        Configuration(path)
    value["policyFiles"]["OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY"] = hashlib.sha256(
        candidate.read_bytes()
    ).hexdigest()
    write(path, value)
    config = Configuration(path)
    config.verify()
    write(candidate, {"controlled": "changed"})
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


def test_explicit_bound_service_policy_pins_and_exact_scope(
    configured, monkeypatch, tmp_path
):
    from agent_console.fixed_work_bound_policy import BoundServicePlanningPolicy
    from agent_operator.native_host_service_prepare import prepare

    path, value = configured
    document = service_document()
    BoundServicePlanningPolicy.model_validate(document)
    service = tmp_path / "service-policy.json"
    write(service, document)
    monkeypatch.setenv("NATIVE_BOUND_SERVICE_EXECUTION_POLICY", str(service))
    with pytest.raises(ValueError, match="MIXED_AUTHORITY_MODE"):
        Configuration(path)
    with pytest.raises(ValueError, match="MIXED_AUTHORITY_MODE"):
        prepare(
            value["manifestPath"], tmp_path / "blocked-state", tmp_path / "blocked.json"
        )
    monkeypatch.delenv("OWNED_BUSINESS_ADMISSION_POLICY")
    with pytest.raises(ValueError, match="POLICY_BINDING_REQUIRED"):
        Configuration(path)
    output = tmp_path / "service-prepared" / "configuration.json"
    prepare(value["manifestPath"], tmp_path / "service-state", output, enabled=True)
    config = Configuration(output)
    assert config.value["principalId"] == "service:exact"
    assert (
        config.value["policyFiles"]["NATIVE_BOUND_SERVICE_EXECUTION_POLICY"]
        == hashlib.sha256(service.read_bytes()).hexdigest()
    )
    changed = dict(config.value, principalId="service:other")
    write(output, changed)
    with pytest.raises(ValueError, match="BOUND_POLICY_SCOPE_MISMATCH"):
        Configuration(output)
    write(output, config.value)
    write(service, {**document, "credentialId": "another"})
    with pytest.raises(ValueError, match="PINNED_SOURCE_CHANGED"):
        config.verify()


def service_document():
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    ref = dict(resource_id="fixture", revision_id="r1", digest="a" * 64)
    document = dict(
        schemaVersion="fixed-work-service-planning.v2",
        policyId="bounded-service",
        enabled=True,
        tenantId="ns",
        securityDomain="d",
        subjectId="service:exact",
        credentialId="exact-credential",
        work=ref,
        target=dict(
            problem=ref,
            criteria=ref,
            criterion_revision_ids=["c1"],
            expected_problem_version=1,
        ),
        resourceSnapshot=ref,
        allowedEventIds=["event"],
        eventWindows={
            "event": [now.isoformat(), (now + timedelta(minutes=1)).isoformat()]
        },
        profileRevisionId="profile",
        profileDigest="b" * 64,
        model=ref,
        ledgerId="original-ledger",
        maximumInputTokens=100,
        maximumOutputTokens=100,
        expiresAt=(now + timedelta(hours=1)).isoformat(),
        sourceBindingDigest="c" * 64,
        scheduleWindow=dict(
            notBefore=now.isoformat(),
            expiresAt=(now + timedelta(minutes=1)).isoformat(),
            windowSeconds=60,
        ),
    )
    return document


@pytest.mark.parametrize("explicit_leaf", [False, True])
def test_real_reconciler_constructs_pinned_service_bridge_without_human_owner(
    tmp_path, monkeypatch, explicit_leaf
):
    from types import SimpleNamespace as NS
    from unittest.mock import Mock

    from agent_console import (
        authority_configuration,
        authority_postgres,
        authority_recovery,
        execution_postgres,
        grant_administration_application,
        native_wait_command_access,
        prepared_native_composition,
        readonly_continuation_worker,
    )
    from agent_console.bound_service_execution import BoundServiceExecutionBridge
    from agent_console.owned_business_work_reader import OwnedBusinessWorkReader
    from agent_operator import native_dispatch_reconciler as target

    class ReachedExactWaitComposition(Exception):
        pass

    service = tmp_path / "service.json"
    write(service, service_document())
    cfg = tmp_path / "authority.json"
    write(cfg, {})
    monkeypatch.delenv("OWNED_BUSINESS_ADMISSION_POLICY", raising=False)
    for key, value in {
        "NATIVE_DISPATCH_DATABASE_URL": "controlled-no-connection",
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION": str(cfg),
        "NATIVE_DISPATCH_EXECUTION_MIGRATION": str(tmp_path / "execution.sql"),
        "NATIVE_DISPATCH_SCHEMA_MIGRATION": str(tmp_path / "dispatch.sql"),
        "NATIVE_DISPATCH_WORKER_ID": "worker",
        "NATIVE_DISPATCH_PREPARED_SKILL": "registered-readonly-v1",
        "NATIVE_DISPATCH_CONTINUATION_POLICY": str(tmp_path / "continuation.json"),
        "NATIVE_BOUND_SERVICE_EXECUTION_POLICY": str(service),
    }.items():
        monkeypatch.setenv(key, value)
    import os

    leaf_environment = dict(os.environ)
    if explicit_leaf:
        monkeypatch.setenv("OWNED_BUSINESS_ADMISSION_POLICY", "/ambient-human")
    ambient_before = dict(os.environ)
    configuration = NS(
        database_url="controlled-no-connection",
        generation_path="gen",
        generation_digest="digest",
        migration_path="migration",
        recovery_control_path="control",
        database_fingerprint="db",
    )
    monkeypatch.setattr(
        authority_configuration.AuthorityRuntimeConfiguration,
        "from_mapping",
        lambda *_: configuration,
    )
    monkeypatch.setattr(
        authority_configuration.StaticAuthorityLoader,
        "load",
        lambda *args, **kwargs: NS(generation=1, digest="digest"),
    )
    repository = Mock()
    repository.active_generation.return_value = (1, "digest", 1)
    monkeypatch.setattr(
        authority_postgres,
        "PostgresAuthorityRepository",
        lambda *args, **kwargs: repository,
    )
    monkeypatch.setattr(
        execution_postgres,
        "PostgresExecutionAuthorityRepository",
        lambda *args, **kwargs: repository,
    )
    monkeypatch.setattr(authority_recovery, "HostRecoveryControl", lambda *_: Mock())
    reader = Mock()
    monkeypatch.setattr(
        grant_administration_application,
        "GenerationAuthorizationReader",
        lambda *args, **kwargs: reader,
    )
    runtime = NS(
        durable_wait=object(),
        subject="service:exact",
        service_credential_id="exact-credential",
    )
    composition = Mock(closeables=(runtime,))

    def composed(*args, **kwargs):
        if explicit_leaf:
            assert kwargs["environment"] == leaf_environment
            assert "OWNED_BUSINESS_ADMISSION_POLICY" not in kwargs["environment"]
        else:
            assert "environment" not in kwargs
        return Mock(), composition

    monkeypatch.setattr(prepared_native_composition, "compose", composed)
    monkeypatch.setattr(
        prepared_native_composition, "owner_authority_factory", lambda *args: Mock()
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("service composition must not construct Human admission")

    monkeypatch.setattr(OwnedBusinessWorkReader, "__init__", forbidden)

    def work_load(*args, **kwargs):
        assert "owned_business" not in kwargs
        bridge = kwargs["bound_service_execution"]
        assert isinstance(bridge, BoundServiceExecutionBridge)
        assert bridge.registry.authorization is reader
        assert bridge.registry._policy().subjectId == "service:exact"
        return NS(bound_service_execution=bridge, owned_business=None)

    monkeypatch.setattr(
        readonly_continuation_worker.ContinuationWork, "load", work_load
    )

    def reached(supplied_runtime, execution, work):
        assert supplied_runtime is runtime
        assert runtime.owned_business is None
        assert runtime.bound_service_execution is work.bound_service_execution
        assert execution is repository
        raise ReachedExactWaitComposition()

    monkeypatch.setattr(native_wait_command_access, "NativeWaitCommandAccess", reached)
    with pytest.raises(ReachedExactWaitComposition):
        target.build_native_dispatch_from_environment(
            **({"environment": leaf_environment} if explicit_leaf else {})
        )
    assert dict(os.environ) == ambient_before


def test_service_bridge_private_policy_is_pinned_without_database(tmp_path):
    from unittest.mock import Mock

    from agent_console.authority_contracts import AuthorityError
    from agent_console.bound_service_execution import BoundServiceExecutionBridge

    path = tmp_path / "service.json"
    write(path, service_document())
    bridge = BoundServiceExecutionBridge.load(path, Mock(), Mock())
    assert bridge.registry._policy().subjectId == "service:exact"
    path.write_text(path.read_text() + " ")
    with pytest.raises(AuthorityError, match="BINDING_INVALID"):
        bridge.registry._policy()
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(AuthorityError, match="BINDING_INVALID"):
        BoundServiceExecutionBridge.load(alias, Mock(), Mock())
    path.chmod(0o644)
    with pytest.raises(AuthorityError, match="BINDING_INVALID"):
        BoundServiceExecutionBridge.load(path, Mock(), Mock())


def test_explicit_leaf_environment_is_copied_and_not_ambient(configured, monkeypatch):
    import os

    path, _ = configured
    leaf_environment = dict(os.environ)
    monkeypatch.setenv("NATIVE_BOUND_SERVICE_EXECUTION_POLICY", "/ambient-service")
    before = dict(os.environ)
    config = Configuration(path, environment=leaf_environment)
    leaf_environment["OWNED_BUSINESS_ADMISSION_POLICY"] = "/later-mutation"
    config.verify()
    assert dict(os.environ) == before
    assert config.environment["OWNED_BUSINESS_ADMISSION_POLICY"] != "/later-mutation"
    with pytest.raises(TypeError):
        config.environment["OWNED_BUSINESS_ADMISSION_POLICY"] = "/mutation"
    with pytest.raises(ValueError, match="MIXED_AUTHORITY_MODE"):
        Configuration(path)


def test_explicit_empty_environment_never_borrows_ambient_owners(monkeypatch):
    import os
    from types import SimpleNamespace

    from agent_console.ontology_action_correction import ENV, project
    from agent_console.provider_budget_extension import configure_from_environment
    from agent_operator.native_dispatch_reconciler import (
        build_native_dispatch_from_environment,
    )

    for name in (
        "NATIVE_DISPATCH_DATABASE_URL",
        "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
        "OWNED_BUSINESS_ADMISSION_POLICY",
        "PROVIDER_BUDGET_EXTENSION_POLICY",
        ENV,
    ):
        monkeypatch.setenv(name, "/ambient-must-not-be-consumed")
    before = dict(os.environ)
    assert build_native_dispatch_from_environment(environment={}) is None
    configure_from_environment(object(), {})
    binding = SimpleNamespace(history_only=False)
    assert project(SimpleNamespace(environment={}), None, None, binding) is binding
    assert dict(os.environ) == before


@pytest.fixture
def configured_policy_set(configured, tmp_path):
    import os

    from agent_operator.native_host_policy_set_config import DI_SOURCES

    path, human = configured
    manifest_path = Path(human["manifestPath"])
    manifest = json.loads(manifest_path.read_text())
    root = Path(manifest["source"])
    for name in DI_SOURCES:
        manifest["sourceHashes"][name] = hashlib.sha256(
            (root / name).read_bytes()
        ).hexdigest()
    write(manifest_path, manifest)
    human = {
        **human,
        "manifestDigest": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    write(path, human)
    service_policy = tmp_path / "bound-policy.json"
    write(service_policy, service_document())
    service = {
        **human,
        "principalId": "service:exact",
        "policyFiles": {
            **{
                k: v
                for k, v in human["policyFiles"].items()
                if k != "OWNED_BUSINESS_ADMISSION_POLICY"
            },
            "NATIVE_BOUND_SERVICE_EXECUTION_POLICY": hashlib.sha256(
                service_policy.read_bytes()
            ).hexdigest(),
        },
    }
    service_path = tmp_path / "service-leaf.json"
    write(service_path, service)
    common = {
        **{k: os.environ[k] for k in human["policyFiles"]},
        "NATIVE_DISPATCH_PREPARED_SKILL": "registered-readonly-v1",
        "NATIVE_DISPATCH_DATABASE_URL": "postgresql://postgres@127.0.0.1:1/controlled",
    }
    environments = [
        common,
        {
            **{
                k: v
                for k, v in common.items()
                if k != "OWNED_BUSINESS_ADMISSION_POLICY"
            },
            "NATIVE_BOUND_SERVICE_EXECUTION_POLICY": str(service_policy),
        },
    ]
    leaves = []
    for kind, config, env in zip(
        ("HUMAN_OWNED", "BOUND_SERVICE"),
        (path, service_path),
        environments,
        strict=True,
    ):
        envpath = tmp_path / (kind + "-environment.json")
        write(envpath, env)
        leaves.append(
            {
                "kind": kind,
                "configurationPath": str(config),
                "configurationDigest": hashlib.sha256(config.read_bytes()).hexdigest(),
                "environmentPath": str(envpath),
                "environmentDigest": hashlib.sha256(envpath.read_bytes()).hexdigest(),
            }
        )
    target = tmp_path / "policy-set.json"
    value = {
        "schema": "native-exact-host-policy-set.v1",
        "enabled": True,
        "leaves": leaves,
    }
    write(target, value)
    return target, value


def test_typed_loader_pins_both_real_configurations_without_ambient_borrowing(
    configured_policy_set, monkeypatch
):
    import os

    from agent_operator.native_host_policy_set_config import PolicySetConfiguration

    path, value = configured_policy_set
    monkeypatch.setenv("NATIVE_BOUND_SERVICE_EXECUTION_POLICY", "/must-not-borrow")
    monkeypatch.setenv("PROVIDER_BUDGET_EXTENSION_POLICY", "/must-not-borrow")
    ambient = dict(os.environ)
    config = PolicySetConfiguration(path)
    assert len(config.leaves) == 2
    for scope, (kind, leaf) in config.leaves.items():
        assert scope[2] == leaf.value["principalId"]
        assert "PROVIDER_BUDGET_EXTENSION_POLICY" not in leaf.environment
        assert bool(leaf.environment.get("NATIVE_BOUND_SERVICE_EXECUTION_POLICY")) == (
            kind.value == "BOUND_SERVICE"
        )
    config.verify()
    assert dict(os.environ) == ambient
    envpath = Path(value["leaves"][1]["environmentPath"])
    write(envpath, {"NATIVE_DISPATCH_DATABASE_URL": "changed"})
    with pytest.raises(ValueError, match="PIN_CHANGED"):
        config.verify()


@pytest.mark.parametrize("fault", ["disabled", "kind", "unapproved-env", "database"])
def test_typed_loader_rejects_invalid_compositions(configured_policy_set, fault):
    from agent_operator.native_host_policy_set_config import PolicySetConfiguration

    path, value = configured_policy_set
    if fault == "disabled":
        value["enabled"] = False
    elif fault == "kind":
        value["leaves"][1]["kind"] = "HUMAN_OWNED"
    else:
        leaf = value["leaves"][1]
        envpath = Path(leaf["environmentPath"])
        env = json.loads(envpath.read_text())
        if fault == "unapproved-env":
            env["PYTHONPATH"] = "/unreviewed-imports"
        else:
            env["NATIVE_DISPATCH_DATABASE_URL"] = (
                "postgresql://postgres@127.0.0.1:1/other"
            )
        write(envpath, env)
        leaf["environmentDigest"] = hashlib.sha256(envpath.read_bytes()).hexdigest()
    write(path, value)
    with pytest.raises(ValueError, match="HOST_POLICY_SET"):
        PolicySetConfiguration(path)


def test_typed_loader_rejects_di_module_loaded_from_other_source(
    configured_policy_set, monkeypatch
):
    from types import SimpleNamespace

    from agent_operator import native_host_policy_set_config as target

    path, _ = configured_policy_set
    original = target.importlib.import_module

    def imported(name):
        if name == "agent_console.plan_suggestion_runtime":
            return SimpleNamespace(__file__="/other-tree/plan_suggestion_runtime.py")
        return original(name)

    monkeypatch.setattr(target.importlib, "import_module", imported)
    with pytest.raises(ValueError, match="SOURCE_ROOT_MISMATCH"):
        target.PolicySetConfiguration(path)


def test_typed_loader_pins_explicit_model_ca_and_rejects_missing_ca(
    configured_policy_set, tmp_path
):
    from agent_operator.native_host_policy_set_config import PolicySetConfiguration

    path, value = configured_policy_set
    ca = tmp_path / "controlled-ca.pem"
    ca.write_text("controlled-certificate-bytes")
    model = tmp_path / "model.json"
    write(model, {"tls": {"caFile": str(ca)}})
    loop = tmp_path / "loop.json"
    write(
        loop,
        {
            "modelRuntimeFile": str(model),
            "modelRuntimeDigest": hashlib.sha256(model.read_bytes()).hexdigest(),
        },
    )
    for leaf in value["leaves"]:
        envpath, cfgpath = (
            Path(leaf["environmentPath"]),
            Path(leaf["configurationPath"]),
        )
        env, cfg = json.loads(envpath.read_text()), json.loads(cfgpath.read_text())
        env["NATIVE_LOOP_RUNTIME_FILE"] = str(loop)
        cfg["policyFiles"]["NATIVE_LOOP_RUNTIME_FILE"] = hashlib.sha256(
            loop.read_bytes()
        ).hexdigest()
        write(envpath, env)
        write(cfgpath, cfg)
        leaf["environmentDigest"] = hashlib.sha256(envpath.read_bytes()).hexdigest()
        leaf["configurationDigest"] = hashlib.sha256(cfgpath.read_bytes()).hexdigest()
    write(path, value)
    selected = PolicySetConfiguration(path)
    assert str(ca) in selected.ca_files
    ca.write_text("changed")
    with pytest.raises(ValueError, match="TLS_CA_CHANGED"):
        selected.verify()
    ca.unlink()
    with pytest.raises(ValueError, match="TLS_CA_INVALID"):
        PolicySetConfiguration(path)
