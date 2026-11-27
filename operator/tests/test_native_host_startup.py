"""Controlled startup observation, not an actual host/provider acceptance run."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.execution_domain import ExecutionConflict
from agent_console.native_host_provenance import lock_identity, require_claim
from agent_console.prepared_native_skill import PreparedNativeSkillCaller
from agent_operator import native_host_startup as startup
from agent_operator.native_dispatch_reconciler import ManagedSkillNativeTransport


def save(path, value):
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    files = {}
    for name in (
        "native_host_startup.py",
        "native_dispatch_host.py",
        "transport.py",
        "caller.py",
    ):
        p = tmp_path / name
        p.write_text(name)
        files[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(startup, "__file__", str(tmp_path / "native_host_startup.py"))
    monkeypatch.setattr(
        startup.inspect,
        "getfile",
        lambda kind: str(
            tmp_path
            / ("transport.py" if kind is ManagedSkillNativeTransport else "caller.py")
        ),
    )
    manifest = tmp_path / "manifest.json"
    mh = save(
        manifest, {"commit": "a" * 40, "source": str(tmp_path), "sourceHashes": files}
    )
    policy = tmp_path / "policy.json"
    ph = save(policy, {"fixture": True})
    monkeypatch.setenv("NATIVE_DISPATCH_AUTHORITY_CONFIGURATION", str(policy))
    monkeypatch.setenv("NATIVE_DISPATCH_PREPARED_SKILL", "registered-readonly-v1")
    monkeypatch.setenv("NATIVE_DISPATCH_WORKER_ID", "new-worker")
    cfg = {
        "workerId": "new-worker",
        "namespace": "test",
        "securityDomain": "team",
        "principalId": "human:test",
        "manifestPath": str(manifest),
        "manifestDigest": mh,
        "recordPath": str(tmp_path / "startup.json"),
        "policyFiles": {"NATIVE_DISPATCH_AUTHORITY_CONFIGURATION": ph},
        "authorizationResources": ["governed-execution:prepared:example"],
    }
    path = tmp_path / "configuration.json"
    save(path, cfg)
    transport = ManagedSkillNativeTransport(
        PreparedNativeSkillCaller.__new__(PreparedNativeSkillCaller)
    )
    assembly = SimpleNamespace(
        worker=SimpleNamespace(worker_id="new-worker", transport=transport),
        authority_repository=SimpleNamespace(
            active_generation=lambda: (2, "a" * 64, 1)
        ),
    )
    return path, cfg, assembly


def test_records_actual_process_and_loaded_files(setup):
    path, cfg, assembly = setup
    observed = startup.StartupObservation(path, assembly)
    value = observed.current()
    assert value["observation"]["pid"] == startup.os.getpid()
    assert value["observation"]["processBirth"]
    assert len(value["observation"]["adapterFiles"]) == 4
    assert json.loads(Path(cfg["recordPath"]).read_text()) == value
    with pytest.raises(FileExistsError):
        startup.StartupObservation(path, assembly)


@pytest.mark.parametrize(
    "target",
    [
        "manifest",
        "source",
        "policy",
        "record",
        "configuration",
        "environment",
        "process",
    ],
)
def test_detects_drift_before_claim(setup, target, monkeypatch):
    path, cfg, assembly = setup
    observed = startup.StartupObservation(path, assembly)
    if target == "environment":
        monkeypatch.setenv("NATIVE_DISPATCH_PREPARED_SKILL", "wrong")
    elif target == "process":
        monkeypatch.setattr(startup.os, "getpid", lambda: -1)
    else:
        p = {
            "manifest": Path(cfg["manifestPath"]),
            "source": path.parent / "caller.py",
            "policy": path.parent / "policy.json",
            "record": Path(cfg["recordPath"]),
            "configuration": path,
        }[target]
        p.write_text("changed")
    with pytest.raises(ValueError):
        observed.current()


@pytest.mark.parametrize(
    "change", ["worker", "manifest", "transport", "mode", "permissions"]
)
def test_bad_startup_never_registers(setup, change, monkeypatch):
    path, cfg, assembly = setup
    if change == "worker":
        assembly.worker.worker_id = "other"
    elif change == "manifest":
        cfg["manifestDigest"] = "0" * 64
        save(path, cfg)
    elif change == "transport":
        assembly.worker.transport = object()
    elif change == "mode":
        monkeypatch.setenv("NATIVE_DISPATCH_PREPARED_SKILL", "other")
    else:
        path.chmod(0o644)
    with pytest.raises(ValueError):
        startup.StartupObservation(path, assembly)
    assert not Path(cfg["recordPath"]).exists()


class Connection:
    def __init__(self, row):
        self.row = row
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [] if self.row is None else [self.row]


def test_claim_identity_and_exact_binding(setup):
    path, _, assembly = setup
    value = startup.StartupObservation(path, assembly).current()
    connection = Connection(None)
    lock_identity(connection, value, "new-worker")
    assert "pg_advisory_xact_lock" in connection.queries[0][0]
    with pytest.raises(ExecutionConflict, match="REUSED"):
        lock_identity(Connection({"startup": None}), value, "new-worker")
    command = SimpleNamespace(
        scope=SimpleNamespace(namespace="test", security_domain="team"),
        command_id="command",
        principal_id="human:test",
        authorization_resource="governed-execution:prepared:example",
    )
    claim = SimpleNamespace(
        worker_id="new-worker",
        command=command,
        claim_generation=SimpleNamespace(value=1),
    )
    require_claim(Connection({"record": {"hostStartup": value}}), claim, value)
    with pytest.raises(ExecutionConflict, match="MISMATCH"):
        require_claim(Connection(None), claim, value)
    with pytest.raises(ExecutionConflict, match="MISMATCH"):
        require_claim(Connection({"record": {"hostStartup": value}}), claim, None)
    with pytest.raises(ExecutionConflict, match="INVALID"):
        lock_identity(Connection(None), value, "other-worker")


def test_native_loop_nested_model_runtime_is_pinned(setup, monkeypatch):
    path, cfg, assembly = setup
    runtime = path.parent / "model-runtime.json"
    runtime_digest = save(runtime, {"fixture": "model configuration, no credential"})
    loop = path.parent / "loop.json"
    loop_digest = save(
        loop, {"modelRuntimeFile": str(runtime), "modelRuntimeDigest": runtime_digest}
    )
    monkeypatch.setenv("NATIVE_LOOP_RUNTIME_FILE", str(loop))
    with pytest.raises(ValueError):
        startup.StartupObservation(path, assembly)
    cfg["policyFiles"]["NATIVE_LOOP_RUNTIME_FILE"] = loop_digest
    save(path, cfg)
    observed = startup.StartupObservation(path, assembly)
    assert observed.current()["observation"]["launchDigest"]
    runtime.write_text("changed")
    with pytest.raises(ValueError):
        observed.current()


def test_registered_restart_keeps_logical_worker_and_new_startup(setup):
    path, cfg, assembly = setup
    original = startup.StartupObservation(path, assembly)
    prior = original.current()
    cfg["predecessorRecordPath"] = cfg["recordPath"]
    cfg["predecessorDigest"] = prior["digest"]
    cfg["recordPath"] = str(path.parent / "second-startup.json")
    save(path, cfg)
    current = startup.StartupObservation(path, assembly).current()
    assert current["observation"]["startupId"] != prior["observation"]["startupId"]
    assert current["observation"]["workerId"] == prior["observation"]["workerId"]
    assert current["observation"]["predecessorDigests"] == [prior["digest"]]
    assert json.loads(Path(cfg["predecessorRecordPath"]).read_text()) == prior


@pytest.mark.parametrize(
    "field", ["principalId", "authorizationResources", "predecessorDigest"]
)
def test_restart_cannot_change_predecessor_scope(setup, field):
    path, cfg, assembly = setup
    prior = startup.StartupObservation(path, assembly).current()
    cfg["predecessorRecordPath"] = cfg["recordPath"]
    cfg["predecessorDigest"] = prior["digest"]
    cfg["recordPath"] = str(path.parent / "rejected-startup.json")
    cfg[field] = (
        ["governed-execution:prepared:other"]
        if field == "authorizationResources"
        else "other"
    )
    save(path, cfg)
    with pytest.raises(ValueError):
        startup.StartupObservation(path, assembly)
    assert not Path(cfg["recordPath"]).exists()


def test_observe_only_receipt_is_exact_idempotent_and_not_terminal(setup):
    path, cfg, assembly = setup
    observed = startup.StartupObservation(path, assembly)
    registered = Path(cfg["recordPath"]).read_bytes()
    claim = SimpleNamespace(
        command=SimpleNamespace(command_id="original-command", digest="c" * 64),
        worker_id="new-worker",
        claim_generation=SimpleNamespace(value=3),
    )
    observed.observe_only_receipt(claim)
    observed.observe_only_receipt(claim)
    receipts = list(path.parent.glob("startup.json.observe-*.json"))
    assert len(receipts) == 1
    result = json.loads(receipts[0].read_text())
    assert result["commandId"] == "original-command"
    assert result["claimGeneration"] == 3
    assert result["effectInvocationAllowed"] is False
    assert "terminal" not in result
    assert Path(cfg["recordPath"]).read_bytes() == registered
    receipts[0].write_text("changed")
    with pytest.raises(ValueError):
        observed.observe_only_receipt(claim)


def test_owned_business_policy_is_required_and_immutable_when_enabled(
    setup, monkeypatch
):
    path, cfg, assembly = setup
    policy = path.parent / "owned-business.json"
    digest = save(policy, {"enabled": True, "fixture": "not deployed"})
    monkeypatch.setenv("OWNED_BUSINESS_ADMISSION_POLICY", str(policy))
    with pytest.raises(ValueError):
        startup.StartupObservation(path, assembly)
    cfg["policyFiles"]["OWNED_BUSINESS_ADMISSION_POLICY"] = digest
    save(path, cfg)
    observed = startup.StartupObservation(path, assembly)
    assert observed.files[str(policy)] == digest
    assert observed.current()["observation"]["launchDigest"]
    policy.write_text("changed policy")
    with pytest.raises(ValueError):
        observed.current()


def test_owned_business_policy_wrong_digest_or_missing_file_rejected(
    setup, monkeypatch
):
    path, cfg, assembly = setup
    policy = path.parent / "owned-business.json"
    save(policy, {"fixture": True})
    monkeypatch.setenv("OWNED_BUSINESS_ADMISSION_POLICY", str(policy))
    cfg["policyFiles"]["OWNED_BUSINESS_ADMISSION_POLICY"] = "0" * 64
    save(path, cfg)
    with pytest.raises(ValueError):
        startup.StartupObservation(path, assembly)
    policy.unlink()
    with pytest.raises((ValueError, OSError)):
        startup.StartupObservation(path, assembly)


@pytest.mark.parametrize("missing", [False, True])
def test_exact_service_local_budget_is_pinned_before_child_claim(
    setup, monkeypatch, missing
):
    from agent_console import bound_service_execution, service_local_budget

    path, cfg, assembly = setup
    root = path.parent
    manifest_path = Path(cfg["manifestPath"])
    manifest = json.loads(manifest_path.read_text())
    for module in (bound_service_execution, service_local_budget):
        target = root / (module.__name__.rsplit(".", 1)[1] + ".py")
        target.write_text("controlled installed source")
        monkeypatch.setattr(module, "__file__", str(target))
        manifest["sourceHashes"][target.name] = hashlib.sha256(
            target.read_bytes()
        ).hexdigest()
    cfg["manifestDigest"] = save(manifest_path, manifest)
    for key in (
        "NATIVE_BOUND_SERVICE_EXECUTION_POLICY",
        "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY",
    ):
        target = root / (key + ".json")
        digest = save(target, {"controlled": True})
        monkeypatch.setenv(key, str(target))
        cfg["policyFiles"][key] = digest
    local_key = "NATIVE_BOUND_SERVICE_LOCAL_BUDGET_POLICY"
    if missing:
        del cfg["policyFiles"][local_key]
    save(path, cfg)
    if missing:
        with pytest.raises(ValueError):
            startup.StartupObservation(path, assembly)
        assert not Path(cfg["recordPath"]).exists()
    else:
        observed = startup.StartupObservation(path, assembly)
        save(Path(startup.os.environ[local_key]), {"changed": True})
        with pytest.raises(ValueError):
            observed.current()
