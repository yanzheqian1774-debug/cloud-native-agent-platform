from pathlib import Path

import pytest
from conformance_harness.manifest import (
    MAX_MANIFEST_BYTES,
    MAX_MANIFEST_CRITERIA,
    MAX_STRUCTURE_DEPTH,
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
                "evidence_classification": "TESTED",
            },
            {
                "id": "A-001",
                "type": "integration",
                "target": "target",
                "profile": "profile",
                "version": "v1",
                "adapter": "adapter",
                "applicable_profiles": ["mvs-native"],
                "evidence_classification": "SUPPORTED_CANDIDATE",
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
    ("field", "value", "message"),
    [
        ("version", "bad version", "version is malformed"),
        ("evidence_classification", "CERTIFIED", "classification is unknown"),
    ],
)
def test_malformed_version_and_classification_fail_closed(
    field: str, value: str, message: str
) -> None:
    document = valid_document()
    document["criteria"][0][field] = value
    with pytest.raises(ManifestError, match=message):
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


def test_empty_manifest_has_explicit_zero_criterion_behavior() -> None:
    manifest = parse_manifest({"schema_version": "s5-test-005/v1", "criteria": []})
    assert manifest.criteria == ()
    assert select_criteria(manifest) == ()


def test_manifest_criterion_limit_fails_closed() -> None:
    criterion = valid_document()["criteria"][0]
    document = {
        "schema_version": "s5-test-005/v1",
        "criteria": [
            {**criterion, "id": f"LIMIT-{index:04d}"}
            for index in range(MAX_MANIFEST_CRITERIA + 1)
        ],
    }
    with pytest.raises(ManifestError, match="maximum criterion count"):
        parse_manifest(document)


def test_manifest_depth_and_file_size_limits_fail_closed(tmp_path: Path) -> None:
    nested: object = "leaf"
    for _ in range(MAX_STRUCTURE_DEPTH + 1):
        nested = {"nested": nested}
    with pytest.raises(ManifestError, match="nesting depth"):
        parse_manifest(nested)  # type: ignore[arg-type]

    oversized = tmp_path / "oversized.json"
    oversized.write_text(" " * (MAX_MANIFEST_BYTES + 1), encoding="utf-8")
    with pytest.raises(ManifestError, match="maximum byte size"):
        load_manifest(oversized)

    document = valid_document()
    document["criteria"][0]["target"] = "x" * (MAX_MANIFEST_BYTES + 1)
    with pytest.raises(ManifestError, match="maximum byte size"):
        parse_manifest(document)


def test_duplicate_json_object_fields_fail_closed(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"s5-test-005/v1","schema_version":"duplicate","criteria":[]}',
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="duplicate manifest object field"):
        load_manifest(duplicate)


def test_manifest_input_is_defensively_copied() -> None:
    document = valid_document()
    manifest = parse_manifest(document)
    document["criteria"][0]["applicable_profiles"][0] = "changed"
    assert manifest.criteria[-1].applicable_profiles == ("mvs-native",)
