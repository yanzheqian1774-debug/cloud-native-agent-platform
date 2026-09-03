from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts/acceptance/release_runner.py"
SPEC = importlib.util.spec_from_file_location("release_runner", MODULE_PATH)
assert SPEC and SPEC.loader
release_runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_runner
SPEC.loader.exec_module(release_runner)
harness_module = sys.modules["isolated_browser_harness"]


def checked_contract() -> dict:
    contract = json.loads(
        (ROOT / "scripts/acceptance/release_contract.v1.json").read_text()
    )
    contract["identity"]["workspaceRoot"] = str(ROOT)
    return contract


def write_contract(tmp_path: Path, value: object, raw: str | None = None) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(raw if raw is not None else json.dumps(value), encoding="utf-8")
    return path


def test_checked_contract_is_strict_and_complete() -> None:
    contract = release_runner.load_contract(
        ROOT / "scripts/acceptance/release_contract.v1.json"
    )
    assert set(contract) == release_runner.TOP_FIELDS
    assert contract["build"]["mode"] == "LIVE_DEMO"
    assert all("@sha256:" in image for image in contract["images"].values())
    assert len(set(contract["ports"].values())) == 4


def test_schema_1_is_byte_identical_and_historical_semantics_are_unchanged() -> None:
    data = (ROOT / "scripts/acceptance/release_contract.v1.json").read_bytes()
    assert hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest() == ("f0fa75bac8222e2f084015069aca17cba0062c5d")
    assert {
        "v0.2.2-attempt-01",
        "v0.2.2-attempt-02",
        "v0.2.2-attempt-03",
        "v0.2.2-attempt-04",
        "v0.2.2-attempt-05",
    } == release_runner.HISTORICAL_SCHEMA_1_ATTEMPTS


def test_schema_2_runner_rejects_ancestor_only_tool_substitution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(),
        "preflight",
        tmp_path / "evidence.json",
        exact_dual_provenance=True,
    )
    calls = []

    def command(args, *_args, **_kwargs):
        calls.append(args)
        output = (
            runner.contract["product"]["treeSha"]
            if args[-1].endswith("^{tree}")
            else "0000000000000000000000000000000000000000"
        )
        return type("R", (), {"returncode": 0, "stdout": f"{output}\n".encode()})()

    monkeypatch.setattr(release_runner, "run_command", command)
    with pytest.raises(release_runner.RunnerError, match="exact identity mismatch"):
        runner.provenance()
    assert not any("merge-base" in call for call in calls)


def test_schema_2_runner_accepts_only_exact_tool_head(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(),
        "preflight",
        tmp_path / "evidence.json",
        exact_dual_provenance=True,
    )

    def command(args, *_args, **_kwargs):
        output = (
            runner.contract["product"]["treeSha"]
            if args[-1].endswith("^{tree}")
            else runner.contract["acceptanceToolSourceSha"]
        )
        return type("R", (), {"returncode": 0, "stdout": f"{output}\n".encode()})()

    monkeypatch.setattr(release_runner, "run_command", command)
    runner.provenance()


def test_new_attempt_rejects_schema_1_before_runner_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract_path = write_contract(tmp_path, checked_contract())
    invoked = False

    def forbidden_run(_self):
        nonlocal invoked
        invoked = True
        return 0

    monkeypatch.setattr(release_runner.Runner, "run", forbidden_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "release_runner.py",
            "preflight",
            "--contract",
            str(contract_path),
            "--evidence",
            str(tmp_path / "evidence.json"),
            "--attempt-id",
            "v0.2.2-attempt-06",
        ],
    )
    assert release_runner.main() == 2
    assert invoked is False


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.update(ambientProductionParameter="forbidden"),
        lambda c: c["build"].update(mode="test"),
        lambda c: c["images"].update(postgres="postgres:15-alpine"),
        lambda c: c["ports"].update(qdrant=c["ports"]["postgres"]),
        lambda c: c["validationRolePolicy"].update(validationRole='unsafe"role'),
        lambda c: c.update(pythonInterpreter="uvicorn"),
        lambda c: c.update(applicationSourceDirectories=["../private"]),
        lambda c: c["diagnosticRetentionPolicy"].update(retainRaw=True),
        lambda c: c["browser"]["command"].remove("--forbid-only"),
    ],
)
def test_contract_negative_controls_fail_without_echo(tmp_path: Path, mutation) -> None:
    contract = checked_contract()
    mutation(contract)
    with pytest.raises(release_runner.RunnerError) as error:
        release_runner.load_contract(write_contract(tmp_path, contract))
    assert error.value.category == "CONTRACT"
    assert 'unsafe"role' not in str(error.value)


def test_duplicate_and_malformed_contract_fail_closed(tmp_path: Path) -> None:
    raw = (ROOT / "scripts/acceptance/release_contract.v1.json").read_text()
    duplicate = raw.replace(
        '"schemaVersion": 1,', '"schemaVersion": 1, "schemaVersion": 1,', 1
    )
    with pytest.raises(release_runner.RunnerError):
        release_runner.load_contract(write_contract(tmp_path, {}, duplicate))
    with pytest.raises(release_runner.RunnerError):
        release_runner.load_contract(write_contract(tmp_path, {}, "{"))


def test_all_fault_injections_have_fixed_sanitized_categories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "micro-postgres", tmp_path / "evidence.json"
    )
    expected = {
        "name-conflict": "NAME_CONFLICT",
        "missing-image": "IMAGE",
        "invalid-mount": "MOUNT",
        "permission-failure": "PERMISSION",
        "storage-resource-failure": "RESOURCE",
        "invalid-configuration": "CONFIGURATION",
    }
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type(
            "R", (), {"returncode": 1, "stdout": b"", "stderr": b""}
        )(),
    )
    for fault, category in expected.items():
        runner.fault = fault
        with pytest.raises(release_runner.RunnerError) as error:
            runner.docker(["invalid"])
        assert error.value.category == category
        assert "invalid" not in str(error.value)
    runner.fault = "daemon-unavailable"
    with pytest.raises(release_runner.RunnerError, match="unavailable") as error:
        runner.docker(["info"])
    assert error.value.category == "DOCKER_DAEMON"


def test_port_collision_is_classified(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(),
        "micro-postgres",
        tmp_path / "evidence.json",
        "port-conflict",
    )
    monkeypatch.setattr(
        runner,
        "docker",
        lambda *_args, **_kwargs: type(
            "R",
            (),
            {
                "stdout": (
                    next(iter(runner.contract["images"].values())) + "\n"
                ).encode()
            },
        )(),
    )
    with pytest.raises(release_runner.RunnerError) as error:
        runner.docker_preflight()
    assert error.value.category == "PORT_CONFLICT"


def test_unowned_cleanup_attempt_fails_before_docker(tmp_path: Path) -> None:
    runner = release_runner.Runner(
        checked_contract(), "micro-postgres", tmp_path / "evidence.json"
    )
    with pytest.raises(release_runner.RunnerError, match="not runner-owned"):
        runner.verify_owned("somebody-elses-container")


def test_non_root_runner_fails_closed_without_mount_authority(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    monkeypatch.setattr(release_runner.os, "geteuid", lambda: 501)
    with pytest.raises(release_runner.RunnerError) as error:
        runner.select_validation_identity()
    assert error.value.code == "READ_ONLY_MOUNT_MISSING"


def test_root_probe_identity_is_forbidden(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    monkeypatch.setattr(release_runner.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        release_runner.pwd,
        "getpwnam",
        lambda _name: type("Identity", (), {"pw_uid": 0, "pw_gid": 0})(),
    )
    with pytest.raises(release_runner.RunnerError) as error:
        runner.select_validation_identity()
    assert error.value.code == "ROOT_PROBE_FORBIDDEN"


def test_mount_options_require_exact_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.candidate_dir = tmp_path / "candidate"
    runner.candidate_dir.mkdir()
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type(
            "R", (), {"returncode": 0, "stdout": b"/somebody/else ro\n"}
        )(),
    )
    with pytest.raises(release_runner.RunnerError) as error:
        runner.mount_options()
    assert error.value.code == "READ_ONLY_MOUNT_VERIFICATION_FAILED"


def test_mount_options_preserve_effective_ro_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.candidate_dir = tmp_path / "candidate"
    runner.candidate_dir.mkdir()
    output = f"{runner.candidate_dir} ro,nosuid,nodev\n".encode()
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type("R", (), {"returncode": 0, "stdout": output})(),
    )
    assert "ro" in runner.mount_options()


def prepared_mount_runner(tmp_path: Path) -> object:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    runner.runtime_dir.mkdir()
    runner.candidate_source_dir = runner.runtime_dir / "candidate-source"
    runner.candidate_source_dir.mkdir()
    runner.candidate_before = release_runner.release_manifest(
        runner.candidate_source_dir
    )
    return runner


def owned_candidate_runner(tmp_path: Path) -> object:
    contract = checked_contract()
    contract["identity"]["runtimeRoot"] = str(tmp_path / "runtime-root")
    runner = release_runner.Runner(
        contract, "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.ensure_runtime()
    assert runner.runtime_dir is not None
    runner.candidate_source_dir = runner.runtime_dir / "candidate-source"
    runner.candidate_source_dir.mkdir()
    return runner


def restore_candidate_permissions(runner: object) -> None:
    if runner.candidate_source_dir is None:
        return
    for path in (runner.candidate_source_dir, *runner.candidate_source_dir.rglob("*")):
        if not path.is_symlink() and path.is_dir():
            path.chmod(0o700)


def test_candidate_mode_normalization_positive_control(tmp_path: Path) -> None:
    runner = owned_candidate_runner(tmp_path)
    source = runner.candidate_source_dir / "package"
    source.mkdir()
    regular = source / "module.py"
    regular.write_text("value = 1\n", encoding="utf-8")
    executable = source / "entrypoint"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    regular.chmod(0o666)
    executable.chmod(0o777)
    try:
        before = sum(
            bool(path.lstat().st_mode & 0o222)
            for path in (
                runner.candidate_source_dir,
                *runner.candidate_source_dir.rglob("*"),
            )
            if not path.is_symlink()
        )
        assert before > 0
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
        runner.candidate_before = release_runner.release_manifest(
            runner.candidate_source_dir
        )
        assert stat.S_IMODE(regular.stat().st_mode) == 0o444
        assert stat.S_IMODE(executable.stat().st_mode) == 0o555
        assert stat.S_IMODE(source.stat().st_mode) == 0o555
        assert all(
            not path.lstat().st_mode & 0o222
            for path in (
                runner.candidate_source_dir,
                *runner.candidate_source_dir.rglob("*"),
            )
            if not path.is_symlink()
        )
        evidence_path = tmp_path / "evidence.candidate-mode-normalization.json"
        evidence = json.loads(evidence_path.read_text())
        assert set(evidence) == release_runner.MODE_NORMALIZATION_FIELDS
        assert evidence["writableBeforeCount"] == before
        assert evidence["writableAfterCount"] == 0
        assert evidence["executablePreservedCount"] == 1
        assert evidence["unsupportedEntryCount"] == 0
        assert all("/" not in str(value) for value in evidence.values())
        assert runner.candidate_before is not None
        release_runner.scan_generated_artifacts([evidence_path])
        harness_module.assert_immutable(runner.candidate_source_dir)
        harness = harness_module.Harness(
            type(
                "Args",
                (),
                {
                    "release_root": runner.candidate_source_dir,
                    "runtime_dir": tmp_path / "browser-runtime",
                    "backend_host": "127.0.0.1",
                    "backend_port": 18083,
                    "postgres_url": "postgresql://redacted@127.0.0.1:55483/test",
                    "qdrant_url": "http://127.0.0.1:56383",
                    "python_path": ".",
                    "journey_id": "s5-impl-083-mode-normalization",
                },
            )()
        )
        assert harness.before == runner.candidate_before
    finally:
        restore_candidate_permissions(runner)


def test_candidate_mode_normalization_rejects_escaping_symlink(
    tmp_path: Path,
) -> None:
    runner = owned_candidate_runner(tmp_path)
    (runner.candidate_source_dir / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
    assert error.value.code == "MODE_NORMALIZATION_SYMLINK_ESCAPE"


def test_candidate_mode_normalization_does_not_chmod_internal_symlink_target(
    tmp_path: Path,
) -> None:
    runner = owned_candidate_runner(tmp_path)
    target = runner.candidate_source_dir / "target"
    target.write_text("immutable", encoding="utf-8")
    link = runner.candidate_source_dir / "link"
    link.symlink_to("target")
    try:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
        assert link.is_symlink()
        assert stat.S_IMODE(target.stat().st_mode) == 0o444
    finally:
        restore_candidate_permissions(runner)


def test_candidate_mode_normalization_rejects_hard_link_to_outside(
    tmp_path: Path,
) -> None:
    runner = owned_candidate_runner(tmp_path)
    outside = tmp_path / "outside"
    outside.write_text("must not change", encoding="utf-8")
    original_mode = stat.S_IMODE(outside.stat().st_mode)
    os.link(outside, runner.candidate_source_dir / "linked")
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
    assert error.value.code == "MODE_NORMALIZATION_HARDLINK_REJECTED"
    assert stat.S_IMODE(outside.stat().st_mode) == original_mode


@pytest.mark.skipif(platform.system() == "Windows", reason="FIFO control is POSIX-only")
def test_candidate_mode_normalization_rejects_unsupported_file_type(
    tmp_path: Path,
) -> None:
    runner = owned_candidate_runner(tmp_path)
    os.mkfifo(runner.candidate_source_dir / "unsupported")
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
    assert error.value.code == "MODE_NORMALIZATION_UNSUPPORTED_ENTRY"
    evidence = json.loads(
        (tmp_path / "evidence.candidate-mode-normalization.json").read_text()
    )
    assert evidence["unsupportedEntryCount"] == 1


def test_candidate_mode_normalization_chmod_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = owned_candidate_runner(tmp_path)
    candidate_file = runner.candidate_source_dir / "candidate"
    candidate_file.write_text("content", encoding="utf-8")
    original_chmod = Path.chmod

    def fail_candidate_chmod(path: Path, mode: int) -> None:
        if path == candidate_file:
            raise PermissionError("/private/secret/path")
        original_chmod(path, mode)

    monkeypatch.setattr(Path, "chmod", fail_candidate_chmod)
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
    assert error.value.code == "MODE_NORMALIZATION_CHMOD_FAILED"
    assert "/private/secret/path" not in str(error.value)


def test_candidate_mode_normalization_ownership_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = owned_candidate_runner(tmp_path)
    (runner.candidate_source_dir / "candidate").write_text("content", encoding="utf-8")
    monkeypatch.setattr(release_runner.os, "chown", lambda *_args, **_kwargs: None)
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid() + 10000, os.getgid() + 10000)
    assert error.value.code == "MODE_NORMALIZATION_OWNERSHIP_MISMATCH"


def test_candidate_mode_normalization_traversal_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = owned_candidate_runner(tmp_path)

    def traversal_failure(*_args, **_kwargs):
        raise PermissionError("/private/secret/path")

    monkeypatch.setattr(release_runner.os, "walk", traversal_failure)
    with pytest.raises(release_runner.RunnerError) as error:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
    assert error.value.code == "MODE_NORMALIZATION_TRAVERSAL_FAILED"
    assert "/private/secret/path" not in str(error.value)


def test_candidate_mode_verification_rejects_removed_executable_bit(
    tmp_path: Path,
) -> None:
    runner = owned_candidate_runner(tmp_path)
    executable = runner.candidate_source_dir / "entrypoint"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    try:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
        executable.chmod(0o444)
        with pytest.raises(release_runner.RunnerError) as error:
            runner.verify_candidate_mode_normalization()
        assert error.value.code == "MODE_NORMALIZATION_VERIFICATION_FAILED"
    finally:
        restore_candidate_permissions(runner)


def test_candidate_mode_verification_rejects_writable_entry(tmp_path: Path) -> None:
    runner = owned_candidate_runner(tmp_path)
    candidate_file = runner.candidate_source_dir / "candidate"
    candidate_file.write_text("content", encoding="utf-8")
    try:
        runner.normalize_candidate_modes(os.getuid(), os.getgid())
        candidate_file.chmod(0o644)
        with pytest.raises(release_runner.RunnerError) as error:
            runner.verify_candidate_mode_normalization()
        assert error.value.code in {
            "MODE_NORMALIZATION_VERIFICATION_FAILED",
            "MODE_NORMALIZATION_WRITABLE_REMAINS",
        }
    finally:
        restore_candidate_permissions(runner)


def test_writable_mount_fails_as_mode_bits_only_boundary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = prepared_mount_runner(tmp_path)
    monkeypatch.setattr(runner, "select_validation_identity", lambda: (65534, 65534))
    monkeypatch.setattr(release_runner.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type("R", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(runner, "mount_options", lambda: {"rw"})
    with pytest.raises(release_runner.RunnerError) as error:
        runner.present_read_only_candidate()
    assert error.value.code == "MODE_BITS_ONLY_NOT_ENFORCED"


def test_mount_source_target_ownership_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = prepared_mount_runner(tmp_path)
    monkeypatch.setattr(runner, "select_validation_identity", lambda: (65534, 65534))
    monkeypatch.setattr(release_runner.shutil, "which", lambda _name: "/bin/tool")
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type("R", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(runner, "mount_options", lambda: {"ro"})
    with pytest.raises(release_runner.RunnerError) as error:
        runner.present_read_only_candidate()
    assert error.value.code == "READ_ONLY_MOUNT_VERIFICATION_FAILED"


def test_unowned_mount_target_cannot_be_unmounted(tmp_path: Path) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    runner.runtime_dir.mkdir()
    runner.candidate_dir = tmp_path / "somebody-elses-candidate"
    runner.candidate_mount_owned = True
    with pytest.raises(release_runner.RunnerError, match="not runner-owned"):
        runner.verify_mount_target_owned()


def test_denial_probe_preserves_fixed_write_classification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    runner.runtime_dir.mkdir()
    runner.candidate_dir = tmp_path / "candidate"
    runner.candidate_dir.mkdir()
    runner.validation_uid = 65534
    runner.validation_gid = 65534
    monkeypatch.setattr(runner, "mount_options", lambda: {"ro"})
    calls = iter(
        [
            type("R", (), {"returncode": 0, "stdout": b"65534\n"})(),
            type("R", (), {"returncode": 0, "stdout": b""})(),
        ]
    )
    monkeypatch.setattr(release_runner, "run_command", lambda *_a, **_k: next(calls))
    with pytest.raises(release_runner.RunnerError) as error:
        runner.denial_probes()
    assert error.value.code == "WRITE_UNEXPECTEDLY_SUCCEEDED"


def test_denial_probe_identity_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    runner.runtime_dir.mkdir()
    runner.candidate_dir = tmp_path / "candidate"
    runner.candidate_dir.mkdir()
    runner.validation_uid = 65534
    runner.validation_gid = 65534
    monkeypatch.setattr(runner, "mount_options", lambda: {"ro"})
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type(
            "R", (), {"returncode": 0, "stdout": b"1234\n"}
        )(),
    )
    with pytest.raises(release_runner.RunnerError) as error:
        runner.denial_probes()
    assert error.value.code == "VALIDATION_IDENTITY_MISMATCH"


def test_denial_probe_preserves_fixed_bytecode_classification(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    runner.runtime_dir.mkdir()
    runner.candidate_dir = tmp_path / "candidate"
    runner.candidate_dir.mkdir()
    runner.validation_uid = 65534
    runner.validation_gid = 65534
    monkeypatch.setattr(runner, "mount_options", lambda: {"ro"})
    calls = iter(
        [
            type("R", (), {"returncode": 0, "stdout": b"65534\n"})(),
            type("R", (), {"returncode": 1, "stdout": b""})(),
            type("R", (), {"returncode": 0, "stdout": b""})(),
        ]
    )
    monkeypatch.setattr(release_runner, "run_command", lambda *_a, **_k: next(calls))
    with pytest.raises(release_runner.RunnerError) as error:
        runner.denial_probes()
    assert error.value.code == "BYTECODE_UNEXPECTEDLY_SUCCEEDED"


@pytest.mark.skipif(
    platform.system() != "Linux" or os.geteuid() != 0,
    reason="real bind-remount control requires root in an isolated Linux environment",
)
def test_real_read_only_bind_mount_positive_control(tmp_path: Path) -> None:
    contract = checked_contract()
    contract["identity"]["runtimeRoot"] = str(tmp_path / "runtime-root")
    contract["pythonInterpreter"] = sys.executable
    runner = release_runner.Runner(
        contract, "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.ensure_runtime()
    assert runner.runtime_dir is not None
    runner.candidate_source_dir = runner.runtime_dir / "candidate-source"
    runner.candidate_source_dir.mkdir()
    (runner.candidate_source_dir / "probe.py").write_text(
        "value = 1\n", encoding="utf-8"
    )
    uid, gid = runner.select_validation_identity()
    for path in (
        runner.candidate_source_dir,
        *runner.candidate_source_dir.rglob("*"),
    ):
        os.chown(path, uid, gid)
        path.chmod(path.stat().st_mode | 0o600)
    runner.candidate_before = release_runner.release_manifest(
        runner.candidate_source_dir
    )
    try:
        runner.present_read_only_candidate()
        runner.denial_probes()
        runner.verify_candidate_manifest()
        runner.unmount_candidate()
        runner.write_candidate_manifests()
        assert runner.candidate_before == runner.candidate_mounted_after
        assert runner.candidate_before == runner.candidate_unmounted_after
        assert (
            runner.runtime_dir / "validation-runtime" / "authorized-cache"
        ).is_file()
    finally:
        if runner.candidate_mount_owned:
            runner.unmount_candidate()


def test_stage_records_are_exactly_allowlisted_and_do_not_echo_errors(
    tmp_path: Path,
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "preflight", tmp_path / "evidence.json"
    )

    def reject() -> None:
        raise release_runner.RunnerError("DISCLOSURE", "secret=/Users/operator/private")

    with pytest.raises(release_runner.RunnerError):
        runner.stage("nondisclosure-scan", reject)
    assert set(runner.records[0]) == release_runner.RECORD_FIELDS
    encoded = json.dumps(runner.records)
    assert "secret=" not in encoded
    assert "/Users/operator" not in encoded


def test_preflight_never_mutates_services(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "preflight", tmp_path / "evidence.json"
    )
    monkeypatch.setattr(runner, "provenance", lambda: None)
    monkeypatch.setattr(runner, "frontend_lock", lambda: None)
    monkeypatch.setattr(runner, "interpreter", lambda: None)
    monkeypatch.setattr(runner, "cleanup", lambda: None)
    monkeypatch.setattr(
        runner, "docker", lambda *_args, **_kwargs: pytest.fail("Docker was invoked")
    )
    assert runner.run() == 0
    records = json.loads((tmp_path / "evidence.json").read_text())
    assert len(records) == len(release_runner.STAGES)
    assert (
        next(r for r in records if r["stageId"] == "docker-preflight")["state"]
        == "NOT_APPLICABLE"
    )


def test_credential_file_mode_control(tmp_path: Path) -> None:
    credential = tmp_path / "credential"
    descriptor = os.open(credential, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    assert stat.S_IMODE(credential.stat().st_mode) == 0o600


def test_authorized_paths_have_no_host_psql_or_broad_cleanup() -> None:
    text = MODULE_PATH.read_text()
    assert '["psql"' not in text
    assert "pkill" not in text
    assert "killall" not in text
    assert "docker ps" not in text
    assert "rm -rf" not in text


def test_false_pg01_attribution_preserves_downstream_failure_and_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    cleaned: list[str] = []
    monkeypatch.setattr(runner, "provenance", lambda: None)
    monkeypatch.setattr(runner, "frontend_lock", lambda: None)
    monkeypatch.setattr(runner, "interpreter", lambda: None)
    monkeypatch.setattr(runner, "docker_preflight", lambda: None)
    monkeypatch.setattr(runner, "postgres_start", lambda: None)
    monkeypatch.setattr(runner, "postgres_provision", lambda: None)
    monkeypatch.setattr(runner, "apply_migrations", lambda: None)
    monkeypatch.setattr(
        runner,
        "qdrant_start",
        lambda: (_ for _ in ()).throw(
            release_runner.RunnerError("QDRANT", "downstream failure")
        ),
    )
    monkeypatch.setattr(runner, "cleanup", lambda: cleaned.append("container-removed"))
    assert runner.run() == 2
    records = json.loads((tmp_path / "evidence.json").read_text())
    failed = [record for record in records if record["state"] == "FAILED"]
    assert failed[0]["stageId"] == "qdrant-health"
    assert failed[0]["errorCategory"] == "QDRANT"
    assert records[-1]["stageId"] == "owned-cleanup"
    assert records[-1]["state"] == "PASSED"
    assert cleaned == ["container-removed"]
    assert all(record["errorCategory"] != "DOCKER_DAEMON" for record in records)


def test_cleanup_failure_does_not_overwrite_first_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "preflight", tmp_path / "evidence.json"
    )
    monkeypatch.setattr(
        runner,
        "provenance",
        lambda: (_ for _ in ()).throw(
            release_runner.RunnerError("PROVENANCE", "first failure")
        ),
    )
    monkeypatch.setattr(
        runner,
        "cleanup",
        lambda: (_ for _ in ()).throw(
            release_runner.RunnerError("OWNERSHIP", "cleanup failure")
        ),
    )
    assert runner.run() == 2
    records = json.loads((tmp_path / "evidence.json").read_text())
    assert records[0]["stageId"] == "provenance"
    assert records[0]["errorCategory"] == "PROVENANCE"
    assert records[-1]["errorCategory"] == "OWNERSHIP"


def test_all_four_modes_are_orchestrated_without_ambient_release_parameters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for mode in sorted(release_runner.MODES):
        runner = release_runner.Runner(
            checked_contract(), mode, tmp_path / f"{mode}.json"
        )
        called: list[str] = []
        for method in (
            "provenance",
            "frontend_lock",
            "interpreter",
            "docker_preflight",
            "postgres_start",
            "postgres_provision",
            "postgres_readiness",
            "apply_migrations",
            "qdrant_start",
            "continuity_before",
            "present_candidate",
            "build_candidate",
            "denial_probes",
            "browser_harness",
            "verify_diagnostics",
            "verify_candidate_manifest",
            "continuity_after",
            "cleanup",
        ):
            monkeypatch.setattr(
                runner,
                method,
                lambda method=method, called=called: called.append(method),
            )
        assert runner.run() == 0
        if mode in {"readiness-rehearsal", "private-acceptance-precheck"}:
            assert "qdrant_start" in called
            assert "browser_harness" in called
            assert "continuity_after" in called
        elif mode == "micro-postgres":
            assert "postgres_readiness" in called
            assert "qdrant_start" not in called
        else:
            assert "docker_preflight" not in called


def test_continuity_monitor_fails_closed_on_identity_drift(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = checked_contract()
    contract["continuitySentinels"] = [
        {
            "name": "public",
            "healthUrl": "http://127.0.0.1:19078/healthz",
            "pid": 1234,
            "startTime": "Mon Sep  2 00:00:00 2026",
        }
    ]
    runner = release_runner.Runner(contract, "preflight", tmp_path / "evidence.json")
    monkeypatch.setattr(
        release_runner,
        "run_command",
        lambda *_args, **_kwargs: type(
            "R", (), {"returncode": 0, "stdout": b"changed identity\n"}
        )(),
    )
    with pytest.raises(release_runner.RunnerError, match="identity drifted"):
        runner.sentinel_snapshot()


def test_migration_checksum_mismatch_fails_before_database_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    contract = checked_contract()
    contract["migrations"]["0001"] = "0" * 64
    runner = release_runner.Runner(
        contract, "readiness-rehearsal", tmp_path / "evidence.json"
    )
    monkeypatch.setattr(runner, "pg", lambda *_args: pytest.fail("database mutated"))
    with pytest.raises(release_runner.RunnerError) as error:
        runner.apply_migrations()
    assert error.value.category == "PROVENANCE"


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        ({"expected": 12, "unexpected": 0, "skipped": 0, "flaky": 0}, True),
        ({"expected": 12, "unexpected": 1, "skipped": 0, "flaky": 0}, False),
        ({"expected": 12, "unexpected": 0, "skipped": 1, "flaky": 0}, False),
        ({"expected": 0, "unexpected": 0, "skipped": 0, "flaky": 0}, False),
    ],
)
def test_browser_report_requires_tests_and_zero_failures_skips_or_flakes(
    stats: dict[str, int], expected: bool
) -> None:
    report = b"npm header\n" + json.dumps({"stats": stats}).encode()
    assert harness_module.verify_browser_report(report) is expected


def test_sanitized_browser_classifier_never_echoes_raw_output() -> None:
    prohibited = b"/Users/operator/private error-context request_body=secret"
    assert harness_module.sanitized_browser_failure_class(b"", prohibited) in {
        "COMMAND",
        "INVOCATION",
    }


def _first_failure() -> dict[str, object]:
    report = json.dumps(
        {
            "stats": {"expected": 4, "unexpected": 1},
            "suites": [
                {
                    "file": "agent-workbench.spec.ts",
                    "specs": [
                        {
                            "title": (
                                "creates a governed draft through the guided Builder"
                            ),
                            "tests": [
                                {
                                    "status": "unexpected",
                                    "results": [
                                        {
                                            "status": "failed",
                                            "errors": [
                                                {
                                                    "message": (
                                                        "expect(locator('#private'))"
                                                        ".toBeVisible()"
                                                    )
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ).encode()
    return harness_module.sanitized_first_failure_record(report, "journey-086", 0)


def test_runner_rejects_malformed_browser_failure_before_persistence(
    tmp_path: Path,
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "preflight", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    source = runner.runtime_dir / "browser-runtime/browser-first-failure.json"
    source.parent.mkdir(parents=True)
    malformed = _first_failure()
    malformed["rawMessage"] = "private assertion"
    source.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(release_runner.RunnerError) as error:
        runner.capture_browser_first_failure()
    assert error.value.category == "BROWSER_DIAGNOSTIC_GAP"
    assert not (tmp_path / "evidence.browser-first-failure.json").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schemaVersion=99),
        lambda value: value.pop("firstFailureOperationId"),
        lambda value: value.pop("httpStatusSourceClass"),
        lambda value: value.update(extraField="forbidden"),
        lambda value: value.update(
            httpStatusCategory="HTTP_5XX",
            httpStatusSourceClass="NO_STRUCTURED_HTTP_STATUS",
        ),
    ],
)
def test_runner_rejects_unsupported_partial_extra_and_contradictory_v2_records(
    tmp_path: Path, mutation
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "preflight", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    source = runner.runtime_dir / "browser-runtime/browser-first-failure.json"
    source.parent.mkdir(parents=True)
    record = _first_failure()
    mutation(record)
    source.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(release_runner.RunnerError) as error:
        runner.capture_browser_first_failure()
    assert error.value.category == "BROWSER_DIAGNOSTIC_GAP"


def test_browser_failure_is_persisted_before_owned_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    runner = release_runner.Runner(
        checked_contract(), "readiness-rehearsal", tmp_path / "evidence.json"
    )
    runner.runtime_dir = tmp_path / "runtime"
    source = runner.runtime_dir / "browser-runtime/browser-first-failure.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps(_first_failure()), encoding="utf-8")
    for name in (
        "provenance",
        "frontend_lock",
        "interpreter",
        "docker_preflight",
        "postgres_start",
        "postgres_provision",
        "apply_migrations",
        "qdrant_start",
        "continuity_before",
        "present_candidate",
        "build_candidate",
        "denial_probes",
    ):
        monkeypatch.setattr(runner, name, lambda: None)

    def fail_browser() -> None:
        record = runner.capture_browser_first_failure()
        raise release_runner.RunnerError(str(record["failureCategory"]), "sanitized")

    persisted = tmp_path / "evidence.browser-first-failure.json"
    monkeypatch.setattr(runner, "browser_harness", fail_browser)
    monkeypatch.setattr(
        runner,
        "cleanup",
        lambda: (
            persisted.is_file() or pytest.fail("cleanup preceded evidence persistence")
        ),
    )
    assert runner.run() == 2
    assert (
        json.loads(persisted.read_text())["firstFailureAssertionId"]
        == "AGENT_WORKBENCH_CREATE_GOVERNED_DRAFT"
    )
    records = json.loads((tmp_path / "evidence.json").read_text())
    assert (
        next(record for record in records if record["stageId"] == "browser-harness")[
            "errorCategory"
        ]
        == "BROWSER_ASSERTION"
    )
    assert records[-1]["stageId"] == "owned-cleanup"
