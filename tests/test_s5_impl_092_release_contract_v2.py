from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/acceptance/release_contract_v2.py"
SPEC = importlib.util.spec_from_file_location("release_contract_v2", MODULE_PATH)
assert SPEC and SPEC.loader
contract_v2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract_v2)


def ci(head: str, run_id: int) -> dict[str, object]:
    return {
        "provider": "GITHUB_ACTIONS",
        "repository": "yanzheqian1774-debug/cloud-native-agent-platform",
        "workflowIdentity": "CI",
        "runId": run_id,
        "runAttempt": 1,
        "headSha": head,
        "conclusion": "SUCCESS",
    }


def source(path: str, blob: str) -> dict[str, str]:
    return {"path": path, "blob": blob}


def contract() -> dict[str, object]:
    product_sha = contract_v2.FROZEN_PRODUCT["sourceSha"]
    product = {
        "role": contract_v2.PRODUCT_ROLE,
        "sourceSha": product_sha,
        "treeSha": contract_v2.FROZEN_PRODUCT["treeSha"],
        "maintenanceBaseSha": contract_v2.FROZEN_PRODUCT["maintenanceBaseSha"],
        "exactSourceCi": ci(product_sha, 33632966183),
        "journey": source(*contract_v2.FROZEN_PRODUCT["paths"]["journey"]),
        "reporter": source(*contract_v2.FROZEN_PRODUCT["paths"]["reporter"]),
        "playwrightConfig": source(
            *contract_v2.FROZEN_PRODUCT["paths"]["playwrightConfig"]
        ),
        "frontendManifest": {
            **source(*contract_v2.FROZEN_PRODUCT["paths"]["frontendManifest"]),
            "sha256": (
                "sha256:3b8af617257ca08e77c0cfe2879026bad5a8203b972639ca8ad77d6250bec98c"
            ),
        },
    }
    tool_sha = "9a515446f9f7baf551b6f3d5762fac9a70dac27a"
    tool = {
        "role": contract_v2.TOOL_ROLE,
        "sourceSha": tool_sha,
        "treeSha": "b117eab25a107458840282aa771ebcd7dce8c8eb",
        "exactMainCi": ci(tool_sha, 33620228849),
        "harness": source(
            "scripts/acceptance/isolated_browser_harness.py",
            "074b66fbf054d76892f0434158c6d34308322caf",
        ),
        "runner": source(
            "scripts/acceptance/release_runner.py",
            "6b26134e9d7098dcdce331cc1d9233de00e4879a",
        ),
        "diagnosticSchemaVersion": 2,
        "diagnosticSchemaSource": source(
            "docs/engineering/ISOLATED_BROWSER_ACCEPTANCE.md",
            "c7a4b9d83eb60ae997acf7d520a4fe281a6da91a",
        ),
    }
    v1 = json.loads((ROOT / "scripts/acceptance/release_contract.v1.json").read_text())
    profile = {
        "mode": v1["build"]["mode"],
        "images": v1["images"],
        "ports": v1["ports"],
        "validationRolePolicy": v1["validationRolePolicy"],
        "pythonInterpreter": v1["pythonInterpreter"],
        "applicationSourceDirectories": v1["applicationSourceDirectories"],
        "diagnosticRetentionPolicy": v1["diagnosticRetentionPolicy"],
        "migrations": {
            key: f"sha256:{value}" for key, value in v1["migrations"].items()
        },
        "browser": {
            "command": [
                "npm",
                "--prefix",
                "console/frontend",
                "run",
                "test:e2e",
                "--",
                "--workers",
                "1",
                "--retries",
                "0",
                "--forbid-only",
                "--reporter",
                "json,./tests/harness/structuredKnowledgeReporter.ts",
            ],
            "journeyId": "s5-impl-092-successor-acceptance",
        },
    }
    pairing = {
        "canonicalization": "RFC8785",
        "digestAlgorithm": "SHA-256",
        "pairingDigest": contract_v2.pairing_digest(product, tool),
    }
    return {
        "schemaVersion": 2,
        "contractType": contract_v2.CONTRACT_TYPE,
        "productProvenance": product,
        "acceptanceToolProvenance": tool,
        "approvedPairing": pairing,
        "executionProfile": profile,
    }


def test_exact_pairing_is_jcs_deterministic_and_git_objects_match() -> None:
    value = contract()
    assert contract_v2.validate_contract(copy.deepcopy(value)) == value
    shuffled = json.loads(json.dumps(value, sort_keys=True))
    assert contract_v2.jcs_bytes(shuffled) == contract_v2.jcs_bytes(value)
    assert value["approvedPairing"]["pairingDigest"] == contract_v2.pairing_digest(
        value["productProvenance"], value["acceptanceToolProvenance"]
    )
    contract_v2.validate_frozen_product(value)
    contract_v2.verify_git_provenance(value, ROOT)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c["productProvenance"].update(treeSha="0" * 40),
        lambda c: c["acceptanceToolProvenance"].update(treeSha="0" * 40),
        lambda c: c["acceptanceToolProvenance"].update(
            sourceSha="811d0688ffd87208f2718df9dd808f7f061f3a73"
        ),
        lambda c: c["productProvenance"].update(
            sourceSha="9a515446f9f7baf551b6f3d5762fac9a70dac27a"
        ),
        lambda c: c["productProvenance"].update(
            sourceSha="4a4ebd69eff5d9559fd723432b8b6b335291417f"
        ),
        lambda c: c["productProvenance"]["journey"].update(blob="0" * 40),
        lambda c: c["productProvenance"]["reporter"].update(blob="0" * 40),
        lambda c: c["productProvenance"]["playwrightConfig"].update(blob="0" * 40),
        lambda c: c["acceptanceToolProvenance"]["harness"].update(blob="0" * 40),
        lambda c: c["acceptanceToolProvenance"]["runner"].update(blob="0" * 40),
        lambda c: c["acceptanceToolProvenance"]["diagnosticSchemaSource"].update(
            blob="0" * 40
        ),
        lambda c: c["productProvenance"].update(role=contract_v2.TOOL_ROLE),
        lambda c: c["approvedPairing"].update(pairingDigest="sha256:" + "0" * 64),
        lambda c: c["productProvenance"]["exactSourceCi"].update(conclusion="FAILED"),
        lambda c: c["productProvenance"]["exactSourceCi"].update(headSha="0" * 40),
        lambda c: c["productProvenance"]["exactSourceCi"].update(runAttempt=2),
        lambda c: c.update(extra="forbidden"),
        lambda c: c["executionProfile"].update(workspaceRoot="/Users/private"),
        lambda c: c.update(contractDigest="sha256:" + "0" * 64),
    ],
)
def test_provenance_and_contract_negative_controls_fail_closed(mutation) -> None:
    value = contract()
    mutation(value)
    if value["approvedPairing"]["pairingDigest"] != "sha256:" + "0" * 64:
        value["approvedPairing"]["pairingDigest"] = contract_v2.pairing_digest(
            value["productProvenance"], value["acceptanceToolProvenance"]
        )
    with pytest.raises(contract_v2.ContractV2Error):
        validated = contract_v2.validate_contract(value)
        contract_v2.validate_frozen_product(validated)
        contract_v2.verify_git_provenance(validated, ROOT)


def test_duplicate_missing_mixed_and_branch_identities_fail_closed() -> None:
    raw = json.dumps(contract())
    with pytest.raises(contract_v2.ContractV2Error):
        contract_v2.load_json_exact(
            raw.replace('"schemaVersion": 2', '"schemaVersion": 2, "schemaVersion": 2')
        )
    for value in (
        {**contract(), "schemaVersion": 1},
        {key: value for key, value in contract().items() if key != "executionProfile"},
    ):
        with pytest.raises(contract_v2.ContractV2Error):
            contract_v2.validate_contract(value)
    value = contract()
    value["productProvenance"]["sourceSha"] = "release/v0.2.2-maintenance"
    with pytest.raises(contract_v2.ContractV2Error):
        contract_v2.validate_contract(value)


def test_generator_atomic_permissions_refusal_and_digest(tmp_path: Path) -> None:
    value = contract()
    data = contract_v2.jcs_bytes(value) + b"\n"
    output = tmp_path / "sealed" / "contract.json"
    digest = contract_v2.atomic_write(output, data)
    assert digest == "sha256:" + hashlib.sha256(data).hexdigest()
    assert stat.S_IMODE(output.stat().st_mode) == 0o444
    with pytest.raises(contract_v2.ContractV2Error, match="refuses overwrite"):
        contract_v2.atomic_write(output, data)
    assert not any(name in data for name in (b"password", b"credential", b"/Users/"))


def test_external_generator_canonicalizes_and_can_seal_directory(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "explicit-input.json"
    input_path.write_text(json.dumps(contract(), indent=2), encoding="utf-8")
    directory = tmp_path / "sealed"
    output = directory / "contract.json"
    result = subprocess.run(
        [
            sys.executable,
            ROOT / "scripts/acceptance/generate_release_contract_v2.py",
            "--input",
            input_path,
            "--output",
            output,
            "--seal-directory",
        ],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    try:
        emitted = json.loads(result.stdout)
        assert emitted["contractInstanceSha256"] == (
            contract_v2.contract_instance_digest(output.read_bytes())
        )
        assert output.read_bytes() == contract_v2.jcs_bytes(contract()) + b"\n"
        assert stat.S_IMODE(output.stat().st_mode) == 0o444
        assert stat.S_IMODE(directory.stat().st_mode) == 0o555
    finally:
        directory.chmod(0o755)


def test_ci_and_evidence_envelope_are_externally_verified() -> None:
    value = contract()
    tool_ci = value["acceptanceToolProvenance"]["exactMainCi"]
    contract_v2.validate_observed_ci(tool_ci, copy.deepcopy(tool_ci), "tool CI")
    with pytest.raises(contract_v2.ContractV2Error):
        contract_v2.validate_observed_ci(
            tool_ci, {**tool_ci, "runAttempt": 2}, "tool CI"
        )
    data = contract_v2.jcs_bytes(value) + b"\n"
    envelope = {
        "provider": tool_ci["provider"],
        "repository": tool_ci["repository"],
        "workflowIdentity": tool_ci["workflowIdentity"],
        "runId": tool_ci["runId"],
        "runAttempt": tool_ci["runAttempt"],
        "headSha": tool_ci["headSha"],
        "observedConclusion": tool_ci["conclusion"],
        "observationTimestamp": "2026-09-02T00:00:00Z",
        "verifierIdentity": "release-governance",
        "verifierVersion": "1",
        "canonicalSnapshotDigest": "",
        "contractSchemaBlob": "1" * 40,
        "contractInstanceSha256": contract_v2.contract_instance_digest(data),
        "recomputedPairingDigest": value["approvedPairing"]["pairingDigest"],
        "releaseGovernanceApprovalStatus": "APPROVED",
    }
    snapshot = {
        key: item for key, item in envelope.items() if key != "canonicalSnapshotDigest"
    }
    envelope["canonicalSnapshotDigest"] = (
        "sha256:" + hashlib.sha256(contract_v2.jcs_bytes(snapshot)).hexdigest()
    )
    contract_v2.validate_evidence_envelope(
        envelope,
        contract_data=data,
        schema_blob="1" * 40,
        pairing=value["approvedPairing"]["pairingDigest"],
        observed_ci=tool_ci,
    )
    for field in (
        "contractSchemaBlob",
        "contractInstanceSha256",
        "recomputedPairingDigest",
    ):
        changed = copy.deepcopy(envelope)
        changed[field] = (
            "0" * 40 if field == "contractSchemaBlob" else "sha256:" + "0" * 64
        )
        with pytest.raises(contract_v2.ContractV2Error):
            contract_v2.validate_evidence_envelope(
                changed,
                contract_data=data,
                schema_blob="1" * 40,
                pairing=value["approvedPairing"]["pairingDigest"],
                observed_ci=tool_ci,
            )
