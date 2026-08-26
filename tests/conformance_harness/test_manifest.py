from pathlib import Path

import pytest

from conformance_harness.manifest import (
    ManifestError,
    load_manifest,
    parse_manifest,
    select_criteria,
)

FIXTURES = Path(__file__).parents[2] / "conformance_harness" / "fixtures"


def valid_document():
    return {
        "schema_version": "s5-test-005/v1",
        "criteria": [
            {
                "id": "Z-002",
                "type": "component",
                "target": "target",
                "profile": "profile",
                "version": "v1",
                "adapter": "adapter",
                "applicable_profiles": ["mvs-native"],
            },
            {
                "id": "A-001",
                "type": "integration",
                "target": "target",
                "profile": "profile",
                "version": "v1",
                "adapter": "adapter",
                "applicable_profiles": ["mvs-native"],
            },
        ],
    }


def test_repository_manifest_loads_in_deterministic_id_order() -> None:
    first = load_manifest(FIXTURES / "criteria.json")
    second = load_manifest(FIXTURES / "criteria.json")
    assert first == second
    assert [item.criterion_id for item in first.criteria] == sorted(
        item.criterion_id for item in first.criteria
    )


def test_selection_is_deterministic_and_does_not_mutate_caller_input() -> None:
    manifest = parse_manifest(valid_document())
    selected = ["Z-002", "A-001"]
    assert [item.criterion_id for item in select_criteria(manifest, selected)] == [
        "A-001",
        "Z-002",
    ]
    assert selected == ["Z-002", "A-001"]


def test_duplicate_ids_fail_closed() -> None:
    document = valid_document()
    document["criteria"][1]["id"] = "Z-002"
    with pytest.raises(ManifestError, match="duplicate criterion id"):
        parse_manifest(document)


def test_unknown_criterion_type_fails_closed() -> None:
    document = valid_document()
    document["criteria"][0]["type"] = "future"
    with pytest.raises(ManifestError, match="unknown criterion type"):
        parse_manifest(document)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("schema_version"),
        lambda value: value.update(extra=True),
        lambda value: value["criteria"][0].pop("adapter"),
        lambda value: value["criteria"][0].update(extra=True),
        lambda value: value.update(criteria="invalid"),
    ],
)
def test_malformed_manifests_fail_closed(mutation) -> None:
    document = valid_document()
    mutation(document)
    with pytest.raises(ManifestError):
        parse_manifest(document)


def test_missing_and_malformed_manifest_files_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        load_manifest(tmp_path / "missing.json")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(malformed)


def test_unknown_or_duplicate_selection_fails_closed() -> None:
    manifest = parse_manifest(valid_document())
    with pytest.raises(ManifestError, match="unknown selected"):
        select_criteria(manifest, ["UNKNOWN"])
    with pytest.raises(ManifestError, match="duplicate ids"):
        select_criteria(manifest, ["A-001", "A-001"])
