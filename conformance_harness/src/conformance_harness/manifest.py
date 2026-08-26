"""Fail-closed, resource-bounded manifest parsing and selection."""

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import Criterion, CriterionManifest, EvidenceClassification

SCHEMA_VERSION = "s5-test-005/v1"
KNOWN_CRITERION_TYPES = frozenset({"component", "integration"})
MAX_MANIFEST_BYTES = 256 * 1024
MAX_MANIFEST_CRITERIA = 256
MAX_STRUCTURE_DEPTH = 32
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+/-]{0,63}$")
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "type",
        "target",
        "profile",
        "version",
        "adapter",
        "applicable_profiles",
        "evidence_classification",
    }
)


class ManifestError(ValueError):
    """Manifest input is malformed or contains unsupported semantics."""


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ManifestError(f"{field_name} must be a non-empty trimmed string")
    return value


def _bounded_structure(value: object) -> None:
    pending = [(value, 0)]
    approximate_bytes = 0
    while pending:
        current, depth = pending.pop()
        if depth > MAX_STRUCTURE_DEPTH:
            raise ManifestError("manifest exceeds maximum nesting depth")
        if isinstance(current, Mapping):
            if not all(isinstance(key, str) for key in current):
                raise ManifestError("manifest object keys must be strings")
            approximate_bytes += sum(len(key.encode()) for key in current)
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
        elif isinstance(current, str):
            approximate_bytes += len(current.encode())
        else:
            approximate_bytes += 16
        if approximate_bytes > MAX_MANIFEST_BYTES:
            raise ManifestError("manifest exceeds maximum byte size")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ManifestError(f"duplicate manifest object field: {key}")
        value[key] = item
    return value


def parse_manifest(document: Mapping[str, Any]) -> CriterionManifest:
    if not isinstance(document, Mapping):
        raise ManifestError("manifest must be an object")
    _bounded_structure(document)
    if set(document) != {"schema_version", "criteria"}:
        raise ManifestError("manifest fields do not match the closed schema")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema_version")
    raw_criteria = document["criteria"]
    if not isinstance(raw_criteria, Sequence) or isinstance(raw_criteria, (str, bytes)):
        raise ManifestError("criteria must be an array")
    if len(raw_criteria) > MAX_MANIFEST_CRITERIA:
        raise ManifestError("manifest exceeds maximum criterion count")

    criteria: list[Criterion] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_criteria):
        if not isinstance(raw, Mapping) or set(raw) != REQUIRED_FIELDS:
            raise ManifestError(
                f"criterion[{index}] fields do not match the closed schema"
            )
        criterion_id = _required_string(raw["id"], f"criterion[{index}].id")
        if criterion_id in seen:
            raise ManifestError(f"duplicate criterion id: {criterion_id}")
        seen.add(criterion_id)
        criterion_type = _required_string(raw["type"], f"criterion[{index}].type")
        if criterion_type not in KNOWN_CRITERION_TYPES:
            raise ManifestError(f"unknown criterion type: {criterion_type}")
        version = _required_string(raw["version"], f"criterion[{index}].version")
        if VERSION_PATTERN.fullmatch(version) is None:
            raise ManifestError(f"criterion[{index}].version is malformed")
        try:
            classification = EvidenceClassification(raw["evidence_classification"])
        except (TypeError, ValueError) as exc:
            raise ManifestError(
                f"criterion[{index}].evidence_classification is unknown"
            ) from exc
        profiles = raw["applicable_profiles"]
        if not isinstance(profiles, list) or not profiles:
            raise ManifestError("applicable_profiles must be a non-empty array")
        normalized_profiles = tuple(
            _required_string(value, f"criterion[{index}].applicable_profiles")
            for value in profiles
        )
        if len(set(normalized_profiles)) != len(normalized_profiles):
            raise ManifestError("applicable_profiles must not contain duplicates")
        criteria.append(
            Criterion(
                criterion_id=criterion_id,
                criterion_type=criterion_type,
                target=_required_string(raw["target"], f"criterion[{index}].target"),
                profile=_required_string(raw["profile"], f"criterion[{index}].profile"),
                version=version,
                adapter=_required_string(raw["adapter"], f"criterion[{index}].adapter"),
                applicable_profiles=normalized_profiles,
                evidence_classification=classification,
            )
        )
    return CriterionManifest(
        SCHEMA_VERSION, tuple(sorted(criteria, key=lambda item: item.criterion_id))
    )


def load_manifest(path: Path) -> CriterionManifest:
    try:
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ManifestError("manifest exceeds maximum byte size")
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
        )
    except ManifestError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ManifestError(
            f"unable to load criterion manifest: {type(exc).__name__}"
        ) from exc
    return parse_manifest(document)


def select_criteria(
    manifest: CriterionManifest, selected_ids: Sequence[str] | None = None
) -> tuple[Criterion, ...]:
    if selected_ids is None:
        return manifest.criteria
    requested = tuple(selected_ids)
    if len(set(requested)) != len(requested):
        raise ManifestError("criterion selection contains duplicate ids")
    available = {criterion.criterion_id: criterion for criterion in manifest.criteria}
    unknown = sorted(set(requested).difference(available))
    if unknown:
        raise ManifestError(f"unknown selected criterion ids: {', '.join(unknown)}")
    return tuple(available[criterion_id] for criterion_id in sorted(requested))
