"""Package 7 deterministic supplier-quality Demo Scenario Pack tests."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
PACK = ROOT / "examples/s5-v0.2-supplier-quality"
SCENARIO = "s5-v0.2-supplier-quality-v1"
NAMESPACE = "s5-v02-supplier-quality-demo"
TENANT = "tenant-a"
DOMAIN = "supplier-quality"
PROVENANCE = {"DEMO_CONFIGURATION", "SYNTHETIC_HISTORY", "LIVE_EXECUTION"}
INPUTS = (
    "scenario-pack-v1.json",
    "namespace.yaml",
    "data/supplier-quality-cases-v1.json",
    "catalog/descriptors-v1.json",
    "catalog/published-roles-v1.json",
    "history/synthetic-history-v1.json",
    "knowledge/knowledge-pack-v1.json",
    "knowledge/8d-procedure-v1.md",
    "bootstrap.sh",
    "reset.sh",
)
KNOWLEDGE_CHECKSUMS = {
    "knowledge/knowledge-pack-v1.json": (
        "774528d7b501a77a19f2683bfaf9fa84790d3d82d83a8ab9d1e0e2f1c51c4154"
    ),
    "knowledge/8d-procedure-v1.md": (
        "b0920d209d3fe0c5cb7b6c5ada2b1698d6b52a3474b117895d8f6b3a2940e5b1"
    ),
}


def load_json(relative: str) -> dict:
    return json.loads((PACK / relative).read_text())


def canonical_digest(value: dict) -> str:
    semantic = dict(value)
    semantic.pop("canonicalDigest")
    payload = json.dumps(
        semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PACK / script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def exact_args(target: Path) -> tuple[str, ...]:
    return (
        "--scenario",
        SCENARIO,
        "--namespace",
        NAMESPACE,
        "--target-dir",
        str(target),
    )


def tree_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_fixed_schema_identity_namespace_version_and_digest() -> None:
    manifest = load_json("scenario-pack-v1.json")
    assert manifest["schemaVersion"] == "supplier-quality-scenario-pack.v1"
    assert manifest["scenarioId"] == SCENARIO
    assert manifest["scenarioVersion"] == "v1"
    assert manifest["namespace"] == NAMESPACE
    assert manifest["tenantId"] == TENANT
    assert manifest["securityDomain"] == DOMAIN
    assert manifest["canonicalDigest"] == canonical_digest(manifest)

    namespace = yaml.safe_load((PACK / "namespace.yaml").read_text())
    assert namespace["kind"] == "Namespace"
    assert namespace["metadata"]["name"] == NAMESPACE
    assert (
        namespace["metadata"]["labels"]["demo.platform.example/scenario-id"] == SCENARIO
    )


def test_checksums_cover_every_input_and_verify() -> None:
    declared = {}
    for line in (PACK / "checksums.sha256").read_text().splitlines():
        checksum, relative = line.split("  ", 1)
        assert re.fullmatch(r"[0-9a-f]{64}", checksum)
        declared[relative] = checksum
    assert set(declared) == set(INPUTS)
    for relative, expected in declared.items():
        assert hashlib.sha256((PACK / relative).read_bytes()).hexdigest() == expected


def test_scope_and_provenance_are_consistent_and_separated() -> None:
    configuration = [
        load_json("scenario-pack-v1.json"),
        load_json("data/supplier-quality-cases-v1.json"),
        load_json("catalog/descriptors-v1.json"),
        load_json("catalog/published-roles-v1.json"),
        load_json("knowledge/knowledge-pack-v1.json"),
    ]
    for item in configuration:
        assert item["tenantId"] == TENANT
        assert item["securityDomain"] == DOMAIN
        assert item["provenance"] == "DEMO_CONFIGURATION"

    history = load_json("history/synthetic-history-v1.json")
    assert history["provenance"] == "SYNTHETIC_HISTORY"
    assert history["liveExecutionEvidence"] is False
    assert all(
        record["provenance"] == "SYNTHETIC_HISTORY"
        and record["isLiveExecution"] is False
        for record in history["records"]
    )
    manifest = configuration[0]
    assert set(manifest["provenanceClasses"].values()) == PROVENANCE
    assert manifest["liveExecution"]["recordsIncluded"] == 0
    assert manifest["liveExecution"]["fixtureFallback"] == "PROHIBITED"


def test_data_is_sanitized_and_pack_grants_no_authority() -> None:
    cases = load_json("data/supplier-quality-cases-v1.json")
    assert cases["sanitation"] == {
        "containsPersonalData": False,
        "containsProductionData": False,
        "containsCredentials": False,
        "supplierNamesAreFictional": True,
    }
    assert all(
        case["supplierAlias"].startswith("Demo Supplier ") for case in cases["cases"]
    )
    manifest = load_json("scenario-pack-v1.json")
    assert not any(manifest["sideEffects"].values())
    roles = load_json("catalog/published-roles-v1.json")
    assert roles["publicationAuthorityIncluded"] is False
    assert roles["permissionGrantIncluded"] is False
    assert all(role["lifecycle"] == "PUBLISHED" for role in roles["roles"])
    assert all(role["matchability"] == "MATCHABLE" for role in roles["roles"])

    text = "\n".join((PACK / relative).read_text() for relative in INPUTS)
    secret_patterns = (
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        r"AKIA[0-9A-Z]{16}",
        r"ghp_[A-Za-z0-9]{30,}",
        r"(?i)(?:password|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"]+",
    )
    assert all(re.search(pattern, text) is None for pattern in secret_patterns)


def test_descriptors_and_roles_are_exactly_linked() -> None:
    descriptors = load_json("catalog/descriptors-v1.json")["descriptors"]
    roles = load_json("catalog/published-roles-v1.json")["roles"]
    descriptor_ids = {item["descriptorId"] for item in descriptors}
    assert len(descriptor_ids) == len(descriptors)
    assert {item["descriptorId"] for item in roles} == descriptor_ids
    assert all(item["capabilities"] == ["quality.read"] for item in descriptors)
    assert all(item["runtimes"] == ["native"] for item in descriptors)


def test_bootstrap_is_deterministic_idempotent_and_reproducible(tmp_path: Path) -> None:
    target = tmp_path / NAMESPACE
    first = run("bootstrap.sh", *exact_args(target))
    assert first.returncode == 0, first.stderr
    first_digest = tree_digest(target)
    second = run("bootstrap.sh", *exact_args(target))
    assert second.returncode == 0, second.stderr
    assert tree_digest(target) == first_digest
    assert (
        json.loads((target / "scenario-pack-v1.json").read_text())["scenarioId"]
        == SCENARIO
    )
    assert (target / "knowledge/8d-procedure-v1.md").read_bytes() == (
        PACK / "knowledge/8d-procedure-v1.md"
    ).read_bytes()


def test_bootstrap_refuses_implicit_broad_wildcard_and_cross_scope(
    tmp_path: Path,
) -> None:
    valid_target = tmp_path / NAMESPACE
    rejected = (
        (),
        ("--scenario", SCENARIO, "--namespace", NAMESPACE),
        exact_args(Path("relative") / NAMESPACE),
        exact_args(Path("/")),
        exact_args(tmp_path / "*" / NAMESPACE),
        (
            "--scenario",
            "other",
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(valid_target),
        ),
        (
            "--scenario",
            SCENARIO,
            "--namespace",
            "default",
            "--target-dir",
            str(valid_target),
        ),
        (
            "--scenario",
            SCENARIO,
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(tmp_path / "other"),
        ),
    )
    for args in rejected:
        result = run("bootstrap.sh", *args)
        assert result.returncode != 0
    assert not valid_target.exists()


def test_reset_is_exact_target_fail_closed_and_idempotent(tmp_path: Path) -> None:
    target = tmp_path / NAMESPACE
    assert run("bootstrap.sh", *exact_args(target)).returncode == 0
    confirmation = ("--confirm", f"{SCENARIO}@{NAMESPACE}")
    assert run("reset.sh", *exact_args(target)).returncode != 0
    assert target.exists()
    assert run("reset.sh", *exact_args(target), *confirmation).returncode == 0
    assert not target.exists()
    assert run("reset.sh", *exact_args(target), *confirmation).returncode == 0


def test_reset_rejects_wildcard_broad_default_cross_namespace_and_foreign_marker(
    tmp_path: Path,
) -> None:
    target = tmp_path / NAMESPACE
    confirmation = ("--confirm", f"{SCENARIO}@{NAMESPACE}")
    rejected = (
        (),
        exact_args(Path("relative") / NAMESPACE) + confirmation,
        exact_args(Path("/")) + confirmation,
        exact_args(tmp_path / "*" / NAMESPACE) + confirmation,
        (
            "--scenario",
            SCENARIO,
            "--namespace",
            "default",
            "--target-dir",
            str(target),
            *confirmation,
        ),
        (
            "--scenario",
            SCENARIO,
            "--namespace",
            NAMESPACE,
            "--target-dir",
            str(tmp_path / "foreign"),
            *confirmation,
        ),
        (*exact_args(target), "--confirm", f"other@{NAMESPACE}"),
    )
    for args in rejected:
        assert run("reset.sh", *args).returncode != 0

    target.mkdir()
    marker = target / ".scenario-pack-scope"
    marker.write_text(f"scenario={SCENARIO}\nnamespace=foreign\n")
    assert run("reset.sh", *exact_args(target), *confirmation).returncode != 0
    assert marker.exists()


def test_read_only_knowledge_files_match_baseline_and_are_not_writable_assets() -> None:
    declared = {
        relative: checksum
        for checksum, relative in (
            line.split("  ", 1)
            for line in (PACK / "checksums.sha256").read_text().splitlines()
        )
    }
    assert {
        relative: declared[relative] for relative in KNOWLEDGE_CHECKSUMS
    } == KNOWLEDGE_CHECKSUMS
    for relative, expected in KNOWLEDGE_CHECKSUMS.items():
        assert hashlib.sha256((PACK / relative).read_bytes()).hexdigest() == expected

    manifest_inputs = load_json("scenario-pack-v1.json")["inputs"]
    assert manifest_inputs["knowledgePack"] == "knowledge/knowledge-pack-v1.json"
    assert manifest_inputs["knowledgeDocument"] == "knowledge/8d-procedure-v1.md"

    bootstrap = (PACK / "bootstrap.sh").read_text().splitlines()
    knowledge_operations = [line.strip() for line in bootstrap if "/knowledge/" in line]
    assert knowledge_operations == [
        'cp "$script_dir/knowledge/knowledge-pack-v1.json" "$target_dir/knowledge/"',
        'cp "$script_dir/knowledge/8d-procedure-v1.md" "$target_dir/knowledge/"',
    ]
    assert "/knowledge/" not in (PACK / "reset.sh").read_text()


def test_scripts_are_executable_and_use_no_kubernetes_context() -> None:
    for script in ("bootstrap.sh", "reset.sh"):
        path = PACK / script
        assert os.access(path, os.X_OK)
        text = path.read_text()
        assert "kubectl" not in text
        assert "KUBECONFIG" not in text
        assert "--all" not in text
    assert shutil.which("sha256sum") is not None
