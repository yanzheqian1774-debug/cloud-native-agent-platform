#!/usr/bin/env python3
"""Closed schema-v2 release contract validation and trust-boundary checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

SCHEMA_VERSION = 2
CONTRACT_TYPE = "V0_2_2_EXACT_DUAL_PROVENANCE_RELEASE"
PRODUCT_ROLE = "V0_2_2_PRODUCT_SUCCESSOR"
TOOL_ROLE = "V0_2_2_ACCEPTANCE_TOOL"
PAIRING_TYPE = "V0_2_2_EXACT_PRODUCT_ACCEPTANCE_TOOL_PAIRING_V1"
TOP_FIELDS = frozenset(
    {
        "schemaVersion",
        "contractType",
        "productProvenance",
        "acceptanceToolProvenance",
        "approvedPairing",
        "executionProfile",
    }
)
PRODUCT_FIELDS = frozenset(
    {
        "role",
        "sourceSha",
        "treeSha",
        "maintenanceBaseSha",
        "exactSourceCi",
        "journey",
        "reporter",
        "playwrightConfig",
        "frontendManifest",
    }
)
TOOL_FIELDS = frozenset(
    {
        "role",
        "sourceSha",
        "treeSha",
        "exactMainCi",
        "harness",
        "runner",
        "diagnosticSchemaVersion",
        "diagnosticSchemaSource",
    }
)
CI_FIELDS = frozenset(
    {
        "provider",
        "repository",
        "workflowIdentity",
        "runId",
        "runAttempt",
        "headSha",
        "conclusion",
    }
)
SOURCE_FIELDS = frozenset({"path", "blob"})
MANIFEST_FIELDS = frozenset({"path", "blob", "sha256"})
PAIRING_FIELDS = frozenset({"canonicalization", "digestAlgorithm", "pairingDigest"})
PROFILE_FIELDS = frozenset(
    {
        "mode",
        "images",
        "ports",
        "validationRolePolicy",
        "pythonInterpreter",
        "applicationSourceDirectories",
        "diagnosticRetentionPolicy",
        "migrations",
        "browser",
        "continuityMonitor",
    }
)
IMAGE_FIELDS = frozenset({"postgres", "qdrant"})
PORT_FIELDS = frozenset({"postgres", "qdrant", "backend", "frontend"})
ROLE_FIELDS = frozenset({"administrativeRole", "validationRole", "database"})
DIAGNOSTIC_FIELDS = frozenset(
    {"retainRaw", "retainSanitized", "scanCompressed", "disposeBrowserArtifacts"}
)
BROWSER_FIELDS = frozenset({"command", "journeyId"})
CONTINUITY_MONITOR_FIELDS = frozenset(
    {"contractVersion", "intervalSeconds", "maximumRuntimeSeconds", "sentinels"}
)
CONTINUITY_SENTINEL_FIELDS = frozenset(
    {"sentinelClass", "serviceUnit", "healthPort", "listenerPort", "listenerRequired"}
)
ENVELOPE_FIELDS = frozenset(
    {
        "provider",
        "repository",
        "workflowIdentity",
        "runId",
        "runAttempt",
        "headSha",
        "observedConclusion",
        "observationTimestamp",
        "verifierIdentity",
        "verifierVersion",
        "canonicalSnapshotDigest",
        "contractSchemaBlob",
        "contractInstanceSha256",
        "recomputedPairingDigest",
        "releaseGovernanceApprovalStatus",
    }
)
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
BLOB = GIT_SHA
RELATIVE_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9_.:/-]{1,160}\Z")
IMAGE = re.compile(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}\Z")
SELF_REFERENCE_NAMES = frozenset(
    {
        "contractCommitSha",
        "contractBlob",
        "contractDigest",
        "contractInstanceDigest",
        "evidenceEnvelopeDigest",
        "storageObject",
        "storageVersion",
        "approvalIdentity",
        "signatureIdentity",
    }
)
FROZEN_PRODUCT = {
    "sourceSha": "51fa5fcb266f1e58083c917dd4c99a02d9165c65",
    "treeSha": "ddab80db6d82680d139bc97edac12f521d50a30f",
    "maintenanceBaseSha": "4a4ebd69eff5d9559fd723432b8b6b335291417f",
    "runId": 33632966183,
    "runAttempt": 1,
    "provider": "GITHUB_ACTIONS",
    "repository": "yanzheqian1774-debug/cloud-native-agent-platform",
    "workflowIdentity": "CI",
    "paths": {
        "journey": (
            "console/frontend/tests/e2e/knowledge-workbench.spec.ts",
            "8225d3005727c230ff3a7fe1977095cab1186f6c",
        ),
        "reporter": (
            "console/frontend/tests/harness/structuredKnowledgeReporter.ts",
            "d8ecee758fb2fafece69c6550d5802493377c11e",
        ),
        "playwrightConfig": (
            "console/frontend/playwright.config.ts",
            "c1f076d67e96f0628b1c3ff349e3f06f0382b6fd",
        ),
        "frontendManifest": (
            "console/frontend/package-lock.json",
            "75928628f2ba51c5504158dd1bd18ed548c685c7",
        ),
    },
}


class ContractV2Error(ValueError):
    """A disclosure-safe schema, provenance, or trust-boundary failure."""


def fail(message: str) -> NoReturn:
    raise ContractV2Error(message)


def load_json_exact(data: str | bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        keys = [key for key, _ in items]
        if len(keys) != len(set(keys)):
            fail("release contract contains a duplicate field")
        return dict(items)

    try:
        value = json.loads(data, object_pairs_hook=pairs)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractV2Error("release contract is malformed") from exc
    if not isinstance(value, dict):
        fail("release contract must be an object")
    return value


def _exact(value: Any, fields: frozenset[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{label} has missing or unknown fields")
    return value


def _closed_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        fail(f"{label} is malformed")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not GIT_SHA.fullmatch(value):
        fail(f"{label} is malformed")
    return value


def _relative(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not RELATIVE_PATH.fullmatch(value)
        or Path(value).is_absolute()
        or ".." in Path(value).parts
    ):
        fail(f"{label} is not a repository-relative path")
    return value


def validate_ci(value: Any, head_sha: str, label: str) -> dict[str, Any]:
    ci = _exact(value, CI_FIELDS, label)
    for field in ("provider", "repository", "workflowIdentity"):
        _closed_string(ci[field], f"{label} {field}")
    if type(ci["runId"]) is not int or ci["runId"] <= 0:
        fail(f"{label} run ID is malformed")
    if type(ci["runAttempt"]) is not int or ci["runAttempt"] <= 0:
        fail(f"{label} run attempt is malformed")
    if ci["headSha"] != head_sha or ci["conclusion"] != "SUCCESS":
        fail(f"{label} does not bind the exact successful head")
    return ci


def validate_source(value: Any, label: str, manifest: bool = False) -> dict[str, Any]:
    source = _exact(value, MANIFEST_FIELDS if manifest else SOURCE_FIELDS, label)
    _relative(source["path"], f"{label} path")
    _sha(source["blob"], f"{label} blob")
    if manifest and (
        not isinstance(source["sha256"], str) or not DIGEST.fullmatch(source["sha256"])
    ):
        fail("frontend manifest generated digest is malformed")
    return source


def _reject_self_reference(value: Any) -> None:
    if isinstance(value, dict):
        if SELF_REFERENCE_NAMES.intersection(value):
            fail("contract instance contains prohibited self-reference")
        for child in value.values():
            _reject_self_reference(child)
    elif isinstance(value, list):
        for child in value:
            _reject_self_reference(child)


def _jcs(value: Any) -> str:
    """RFC 8785 for the deliberately restricted schema-2 JSON value domain."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if type(value) is int:
        if not -(2**53) + 1 <= value <= 2**53 - 1:
            fail("integer exceeds the RFC 8785 interoperable domain")
        return str(value)
    if isinstance(value, float):
        fail("floating-point values are outside the schema-2 domain")
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_jcs(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            fail("object key is not a string")
        # Python Unicode code-point order equals UTF-16 order for this schema's
        # ASCII-only key vocabulary, which validation closes before pairing.
        return (
            "{"
            + ",".join(f"{_jcs(key)}:{_jcs(value[key])}" for key in sorted(value))
            + "}"
        )
    fail("unsupported JSON value type")


def jcs_bytes(value: Any) -> bytes:
    return _jcs(value).encode("utf-8")


def pairing_preimage(product: dict[str, Any], tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "pairingType": PAIRING_TYPE,
        "productProvenance": product,
        "acceptanceToolProvenance": tool,
    }


def pairing_digest(product: dict[str, Any], tool: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(jcs_bytes(pairing_preimage(product, tool))).hexdigest()
    )


def validate_execution_profile(value: Any) -> dict[str, Any]:
    profile = _exact(value, PROFILE_FIELDS, "execution profile")
    if profile["mode"] != "LIVE_DEMO":
        fail("execution mode is unsupported")
    images = _exact(profile["images"], IMAGE_FIELDS, "images")
    if any(
        not isinstance(item, str) or not IMAGE.fullmatch(item)
        for item in images.values()
    ):
        fail("container image is not digest pinned")
    ports = _exact(profile["ports"], PORT_FIELDS, "ports")
    if any(
        type(port) is not int or not 1024 <= port <= 65535 for port in ports.values()
    ):
        fail("port is malformed")
    if len(set(ports.values())) != len(ports):
        fail("ports are duplicated")
    roles = _exact(
        profile["validationRolePolicy"], ROLE_FIELDS, "validation role policy"
    )
    for item in roles.values():
        _closed_string(item, "validation role value")
    interpreter = _relative(profile["pythonInterpreter"], "python interpreter")
    if not Path(interpreter).name.startswith("python"):
        fail("python interpreter is malformed")
    sources = profile["applicationSourceDirectories"]
    if (
        not isinstance(sources, list)
        or not sources
        or len(sources) != len(set(sources))
    ):
        fail("application source directories are malformed")
    for source in sources:
        _relative(source, "application source directory")
    diagnostics = _exact(
        profile["diagnosticRetentionPolicy"], DIAGNOSTIC_FIELDS, "diagnostic policy"
    )
    if diagnostics != {
        "retainRaw": False,
        "retainSanitized": True,
        "scanCompressed": True,
        "disposeBrowserArtifacts": True,
    }:
        fail("diagnostic policy is unsafe")
    migrations = profile["migrations"]
    if not isinstance(migrations, dict) or not migrations:
        fail("migration identities are malformed")
    for key, digest in migrations.items():
        if (
            not re.fullmatch(r"[0-9]{4}", key)
            or not isinstance(digest, str)
            or not DIGEST.fullmatch(digest)
        ):
            fail("migration identity is malformed")
    browser = _exact(profile["browser"], BROWSER_FIELDS, "browser")
    command = browser["command"]
    expected_command = [
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
    ]
    if command != expected_command:
        fail("browser command is malformed")
    _closed_string(browser["journeyId"], "browser journey")
    monitor = _exact(
        profile["continuityMonitor"],
        CONTINUITY_MONITOR_FIELDS,
        "continuity monitor",
    )
    if monitor["contractVersion"] != "SERVER_LOCAL_CONTINUITY_V1":
        fail("continuity monitor contract version is unsupported")
    interval = monitor["intervalSeconds"]
    maximum = monitor["maximumRuntimeSeconds"]
    if type(interval) is not int or not 1 <= interval <= 60:
        fail("continuity monitor interval is outside the accepted bound")
    if type(maximum) is not int or not interval <= maximum <= 21600:
        fail("continuity monitor runtime is outside the accepted bound")
    sentinels = monitor["sentinels"]
    if not isinstance(sentinels, list) or len(sentinels) != 2:
        fail("continuity sentinels are absent or incomplete")
    identities: set[str] = set()
    for value in sentinels:
        sentinel = _exact(value, CONTINUITY_SENTINEL_FIELDS, "continuity sentinel")
        identity = sentinel["sentinelClass"]
        if (
            identity not in {"PUBLIC", "ORIGINAL_STAGING"}
            or identity in identities
            or not isinstance(sentinel["serviceUnit"], str)
            or not IDENTIFIER.fullmatch(sentinel["serviceUnit"])
            or type(sentinel["healthPort"]) is not int
            or not 1 <= sentinel["healthPort"] <= 65535
            or type(sentinel["listenerPort"]) is not int
            or not 1 <= sentinel["listenerPort"] <= 65535
            or type(sentinel["listenerRequired"]) is not bool
        ):
            fail("continuity sentinel identity is malformed or unapproved")
        identities.add(identity)
    if identities != {"PUBLIC", "ORIGINAL_STAGING"}:
        fail("continuity sentinel set is unapproved")
    return profile


def validate_contract(value: Any) -> dict[str, Any]:
    contract = _exact(value, TOP_FIELDS, "schema-2 release contract")
    if (
        contract["schemaVersion"] != SCHEMA_VERSION
        or contract["contractType"] != CONTRACT_TYPE
    ):
        fail("schema-2 release contract identity is unsupported")
    _reject_self_reference(contract)
    product = _exact(
        contract["productProvenance"], PRODUCT_FIELDS, "product provenance"
    )
    tool = _exact(
        contract["acceptanceToolProvenance"], TOOL_FIELDS, "acceptance-tool provenance"
    )
    if product["role"] != PRODUCT_ROLE or tool["role"] != TOOL_ROLE:
        fail("product and acceptance-tool roles are invalid or swapped")
    for field in ("sourceSha", "treeSha", "maintenanceBaseSha"):
        _sha(product[field], f"product {field}")
    for field in ("sourceSha", "treeSha"):
        _sha(tool[field], f"acceptance-tool {field}")
    validate_ci(product["exactSourceCi"], product["sourceSha"], "product CI")
    validate_ci(tool["exactMainCi"], tool["sourceSha"], "acceptance-tool CI")
    for field in ("journey", "reporter", "playwrightConfig"):
        validate_source(product[field], f"product {field}")
    validate_source(product["frontendManifest"], "frontend manifest", manifest=True)
    for field in ("harness", "runner", "diagnosticSchemaSource"):
        validate_source(tool[field], f"acceptance-tool {field}")
    if tool["diagnosticSchemaVersion"] != 2:
        fail("diagnostic schema version is unsupported")
    validate_execution_profile(contract["executionProfile"])
    pairing = _exact(contract["approvedPairing"], PAIRING_FIELDS, "approved pairing")
    if (
        pairing["canonicalization"] != "RFC8785"
        or pairing["digestAlgorithm"] != "SHA-256"
    ):
        fail("pairing algorithm is unsupported")
    expected = pairing_digest(product, tool)
    if pairing["pairingDigest"] != expected:
        fail("approved pairing digest mismatch")
    return contract


def _git(args: list[str], workspace: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=workspace, capture_output=True, check=False, text=True
    )
    if result.returncode:
        fail("required immutable Git object is unavailable")
    return result.stdout.strip()


def _git_bytes(args: list[str], workspace: Path) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=workspace, capture_output=True, check=False
    )
    if result.returncode:
        fail("required immutable Git object is unavailable")
    return result.stdout


def verify_git_provenance(contract: dict[str, Any], workspace: Path) -> None:
    for label, provenance, sources in (
        (
            "product",
            contract["productProvenance"],
            ("journey", "reporter", "playwrightConfig", "frontendManifest"),
        ),
        (
            "acceptance-tool",
            contract["acceptanceToolProvenance"],
            ("harness", "runner", "diagnosticSchemaSource"),
        ),
    ):
        source_sha = provenance["sourceSha"]
        if _git(["rev-parse", f"{source_sha}^{{commit}}"], workspace) != source_sha:
            fail(f"{label} commit identity mismatch")
        if (
            _git(["rev-parse", f"{source_sha}^{{tree}}"], workspace)
            != provenance["treeSha"]
        ):
            fail(f"{label} tree identity mismatch")
        if label == "product":
            parents = _git(["show", "-s", "--format=%P", source_sha], workspace).split()
            if not parents or parents[0] != provenance["maintenanceBaseSha"]:
                fail("product direct maintenance ancestry mismatch")
        for field in sources:
            source = provenance[field]
            if (
                _git(["rev-parse", f"{source_sha}:{source['path']}"], workspace)
                != source["blob"]
            ):
                fail(f"{label} path/blob identity mismatch")
        if label == "product":
            manifest = provenance["frontendManifest"]
            generated = (
                "sha256:"
                + hashlib.sha256(
                    _git_bytes(["show", f"{source_sha}:{manifest['path']}"], workspace)
                ).hexdigest()
            )
            if generated != manifest["sha256"]:
                fail("product frontend manifest generated digest mismatch")


def validate_observed_ci(declared: dict[str, Any], observed: Any, label: str) -> None:
    observation = _exact(observed, CI_FIELDS, f"observed {label}")
    if observation != declared:
        fail(f"{label} authoritative observation mismatch")


def contract_instance_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def validate_evidence_envelope(
    value: Any,
    *,
    contract_data: bytes,
    schema_blob: str,
    pairing: str,
    observed_ci: dict[str, Any],
) -> dict[str, Any]:
    envelope = _exact(value, ENVELOPE_FIELDS, "Evidence envelope")
    for field in (
        "provider",
        "repository",
        "workflowIdentity",
        "verifierIdentity",
        "verifierVersion",
    ):
        _closed_string(envelope[field], f"Evidence envelope {field}")
    if type(envelope["runId"]) is not int or type(envelope["runAttempt"]) is not int:
        fail("Evidence envelope run identity is malformed")
    _sha(envelope["headSha"], "Evidence envelope head")
    try:
        datetime.fromisoformat(envelope["observationTimestamp"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ContractV2Error("Evidence envelope timestamp is malformed") from exc
    expected_observation = {
        "provider": envelope["provider"],
        "repository": envelope["repository"],
        "workflowIdentity": envelope["workflowIdentity"],
        "runId": envelope["runId"],
        "runAttempt": envelope["runAttempt"],
        "headSha": envelope["headSha"],
        "conclusion": envelope["observedConclusion"],
    }
    if expected_observation != observed_ci:
        fail("Evidence envelope authoritative CI observation mismatch")
    if envelope["observedConclusion"] != "SUCCESS":
        fail("Evidence envelope CI conclusion is not successful")
    if envelope["contractSchemaBlob"] != schema_blob:
        fail("Contract schema blob mismatch")
    if envelope["contractInstanceSha256"] != contract_instance_digest(contract_data):
        fail("Contract instance digest mismatch")
    if envelope["recomputedPairingDigest"] != pairing:
        fail("Evidence envelope pairing digest mismatch")
    if envelope["releaseGovernanceApprovalStatus"] != "APPROVED":
        fail("release governance approval is absent")
    snapshot = {
        key: value
        for key, value in envelope.items()
        if key != "canonicalSnapshotDigest"
    }
    if (
        envelope["canonicalSnapshotDigest"]
        != "sha256:" + hashlib.sha256(jcs_bytes(snapshot)).hexdigest()
    ):
        fail("Evidence envelope canonical snapshot digest mismatch")
    return envelope


def validate_frozen_product(contract: dict[str, Any]) -> None:
    product = contract["productProvenance"]
    for field in ("sourceSha", "treeSha", "maintenanceBaseSha"):
        if product[field] != FROZEN_PRODUCT[field]:
            fail("product is not the approved frozen successor")
    ci = product["exactSourceCi"]
    if (
        ci["runId"] != FROZEN_PRODUCT["runId"]
        or ci["runAttempt"] != FROZEN_PRODUCT["runAttempt"]
    ):
        fail("product CI is not the approved exact-source run")
    for field in ("provider", "repository", "workflowIdentity"):
        if ci[field] != FROZEN_PRODUCT[field]:
            fail("product CI identity is not approved")
    for field, (path, blob) in FROZEN_PRODUCT["paths"].items():
        source = product[field]
        if source["path"] != path or source["blob"] != blob:
            fail("product source identity is not approved")


def atomic_write(path: Path, data: bytes, *, seal_directory: bool = False) -> str:
    if path.exists():
        fail("Contract generator refuses overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o444)
        os.replace(temporary, path)
        if seal_directory:
            os.chmod(path.parent, 0o555)
    finally:
        if temporary.exists():
            temporary.unlink()
    return contract_instance_digest(data)
