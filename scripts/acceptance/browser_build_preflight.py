#!/usr/bin/env python3
"""Create and verify an external identity for an immutable frontend build."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

APPROVED_BUILD_MODE = "LIVE_DEMO"
BUILD_IDENTITY_FIELDS = frozenset(
    {"schemaVersion", "buildModeIdentity", "frontendManifestDigest"}
)


class BuildPreflightError(RuntimeError):
    """A fail-closed build identity validation failure."""


def frontend_manifest_digest(root: Path) -> str:
    if not root.is_dir():
        raise BuildPreflightError("frontend build output is unavailable")
    files = [path for path in sorted(root.rglob("*")) if path.is_file()]
    if not files:
        raise BuildPreflightError("frontend build output is empty")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(root).as_posix().encode()
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def record_build_identity(root: Path, output: Path, build_mode: str) -> None:
    if build_mode != "live":
        raise BuildPreflightError("frontend build mode is not approved")
    if output.exists() or not output.parent.is_dir():
        raise BuildPreflightError("external build identity target is invalid")
    record = {
        "schemaVersion": 1,
        "buildModeIdentity": APPROVED_BUILD_MODE,
        "frontendManifestDigest": frontend_manifest_digest(root),
    }
    output.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")


def verify_build_identity(root: Path, identity_path: Path) -> dict[str, Any]:
    try:
        record = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BuildPreflightError("external build identity is unavailable") from exc
    if not isinstance(record, dict) or set(record) != BUILD_IDENTITY_FIELDS:
        raise BuildPreflightError("external build identity is not allowlisted")
    expected = {
        "schemaVersion": 1,
        "buildModeIdentity": APPROVED_BUILD_MODE,
        "frontendManifestDigest": frontend_manifest_digest(root),
    }
    if record != expected:
        raise BuildPreflightError("frontend build identity mismatch")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--build-mode", required=True)
    args = parser.parse_args()
    record_build_identity(args.frontend_root, args.output, args.build_mode)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildPreflightError:
        print("build identity preflight failed", flush=True)
        raise SystemExit(2) from None
