"""Fail-closed criterion manifest parsing and deterministic selection."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .models import Criterion, CriterionManifest

SCHEMA_VERSION = "s5-test-005/v1"
KNOWN_CRITERION_TYPES = frozenset({"component", "integration"})
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "type",
        "target",
        "profile",
        "version",
        "adapter",
        "applicable_profiles",
    }
)


class ManifestError(ValueError):
    """Manifest input is malformed or contains unsupported semantics."""


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ManifestError(f"{field_name} must be a non-empty trimmed string")
    return value


def parse_manifest(document: Mapping[str, Any]) -> CriterionManifest:
    if not isinstance(document, Mapping):
        raise ManifestError("manifest must be an object")
    if set(document) != {"schema_version", "criteria"}:
        raise ManifestError("manifest fields do not match the closed schema")
    if document["schema_version"] != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema_version")
    raw_criteria = document["criteria"]
    if not isinstance(raw_criteria, Sequence) or isinstance(raw_criteria, (str, bytes)):
        raise ManifestError("criteria must be an array")

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
                version=_required_string(raw["version"], f"criterion[{index}].version"),
                adapter=_required_string(raw["adapter"], f"criterion[{index}].adapter"),
                applicable_profiles=normalized_profiles,
            )
        )
    return CriterionManifest(
        SCHEMA_VERSION, tuple(sorted(criteria, key=lambda item: item.criterion_id))
    )


def load_manifest(path: Path) -> CriterionManifest:
    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
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
