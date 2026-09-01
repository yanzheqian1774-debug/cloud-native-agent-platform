"""Fail-closed minimum-disclosure extraction and generated-artifact scanning."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

EVIDENCE_FIELDS = frozenset(
    {
        "schemaVersion",
        "acceptanceState",
        "backendPid",
        "backendStartTimeNs",
        "backendRestartCount",
        "releaseEntryCount",
        "releaseManifestBeforeDigest",
        "releaseManifestAfterDigest",
        "completedAt",
    }
)

_FORBIDDEN_TEXT = (
    re.compile(r"(?i)postgres(?:ql)?://"),
    re.compile(r"(?i)\b(?:database_url|api_key|authorization|password|secret)\b"),
    re.compile(r"(?i)\b(?:bounded[-_]test[-_]key|placeholder[-_]key)\b"),
    re.compile(r"(?i)\b(?:source_text|prompt|environment)\b"),
    re.compile(r'(?i)["\'](?:content|vector|vectors|payload)["\']\s*:'),
    re.compile(r"\b(?:AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})\b"),
)


class DisclosureViolation(RuntimeError):
    """Raised without echoing the rejected value."""


def extract_allowlisted(record: dict[str, Any], requested: set[str]) -> dict[str, Any]:
    rejected = requested - EVIDENCE_FIELDS
    if rejected:
        raise DisclosureViolation(
            "evidence extraction requested a non-allowlisted field"
        )
    missing = requested - record.keys()
    if missing:
        raise DisclosureViolation("evidence extraction requested a missing field")
    return {key: record[key] for key in sorted(requested)}


def _scan_bytes(data: bytes) -> None:
    text = data.decode("utf-8", errors="ignore")
    if any(pattern.search(text) for pattern in _FORBIDDEN_TEXT):
        raise DisclosureViolation("generated artifact contains prohibited material")


def scan_artifact(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        return
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                _scan_bytes(archive.read(name))
        return
    _scan_bytes(path.read_bytes())


def scan_generated_artifacts(paths: list[Path]) -> None:
    for root in paths:
        if not root.exists():
            continue
        files = root.rglob("*") if root.is_dir() else [root]
        for path in files:
            scan_artifact(path)
