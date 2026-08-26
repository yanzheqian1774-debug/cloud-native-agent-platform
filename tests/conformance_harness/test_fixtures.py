import json
from pathlib import Path

import pytest

from conformance_harness.fixtures import (
    MAX_FIXTURE_BYTES,
    MAX_FIXTURE_DEPTH,
    FixtureError,
    FixtureLoader,
)


def test_fixture_loading_is_deterministic_and_defensively_copied(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"nested": {"value": "original"}}), encoding="utf-8")
    loader = FixtureLoader(tmp_path)
    first = loader.load_json("fixture.json")
    first["nested"]["value"] = "changed"
    assert loader.load_json("fixture.json") == {"nested": {"value": "original"}}


@pytest.mark.parametrize("path", ["../fixture.json", "/tmp/fixture.json"])
def test_absolute_and_traversal_paths_are_rejected(tmp_path: Path, path: str) -> None:
    with pytest.raises(FixtureError, match="absolute and traversal"):
        FixtureLoader(tmp_path).load_json(path)


def test_missing_malformed_and_directory_fixtures_fail_closed(tmp_path: Path) -> None:
    loader = FixtureLoader(tmp_path)
    with pytest.raises(FixtureError, match="missing"):
        loader.load_json("missing.json")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    with pytest.raises(FixtureError, match="malformed"):
        loader.load_json("bad.json")
    (tmp_path / "directory").mkdir()
    with pytest.raises(FixtureError, match="file"):
        loader.load_json("directory")


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    (tmp_path / "escape.json").symlink_to(outside)
    with pytest.raises(FixtureError, match="outside"):
        FixtureLoader(tmp_path).load_json("escape.json")


def test_unsupported_file_type_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "fixture.yaml").write_text("id: fixture", encoding="utf-8")
    with pytest.raises(FixtureError, match="unsupported fixture file type"):
        FixtureLoader(tmp_path).load_json("fixture.yaml")


def test_oversized_and_deep_fixtures_fail_within_bounds(tmp_path: Path) -> None:
    (tmp_path / "oversized.json").write_text(
        json.dumps({"value": "x" * MAX_FIXTURE_BYTES}), encoding="utf-8"
    )
    with pytest.raises(FixtureError, match="maximum byte size"):
        FixtureLoader(tmp_path).load_json("oversized.json")

    nested: object = "leaf"
    for _ in range(MAX_FIXTURE_DEPTH + 1):
        nested = {"nested": nested}
    (tmp_path / "deep.json").write_text(json.dumps(nested), encoding="utf-8")
    with pytest.raises(FixtureError, match="nesting depth"):
        FixtureLoader(tmp_path).load_json("deep.json")


@pytest.mark.parametrize(
    "content",
    [
        {"id": "fixture", "access_token": "value"},
        {"id": "fixture", "value": "Bearer" + " opaque-value"},
        {"id": "fixture", "value": "-----BEGIN" + " PRIVATE KEY-----"},
        {"id": "fixture", "value": "sk-" + "x" * 16},
    ],
)
def test_credential_shaped_fixture_content_is_rejected(
    tmp_path: Path, content: dict[str, str]
) -> None:
    (tmp_path / "fixture.json").write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(FixtureError, match="credential-shaped"):
        FixtureLoader(tmp_path).load_json("fixture.json")


def test_duplicate_fixture_identities_fail_closed(tmp_path: Path) -> None:
    for name in ("first", "second"):
        (tmp_path / f"{name}.json").write_text(
            json.dumps({"id": "duplicate", "value": name}), encoding="utf-8"
        )
    with pytest.raises(FixtureError, match="duplicate fixture identity"):
        FixtureLoader(tmp_path).load_many(["first.json", "second.json"])


def test_loaded_nested_content_cannot_leak_state_between_calls(tmp_path: Path) -> None:
    (tmp_path / "fixture.json").write_text(
        json.dumps({"id": "fixture", "items": [{"value": "original"}]}),
        encoding="utf-8",
    )
    first = FixtureLoader(tmp_path).load_json("fixture.json")
    first["items"][0]["value"] = "changed"
    second = FixtureLoader(tmp_path).load_json("fixture.json")
    assert second["items"][0]["value"] == "original"


@pytest.mark.parametrize(
    "raw",
    [
        '{"id":"fixture","id":"duplicate"}',
        '{"id":"fixture","value":NaN}',
    ],
)
def test_duplicate_fields_and_non_finite_numbers_fail_closed(
    tmp_path: Path, raw: str
) -> None:
    (tmp_path / "fixture.json").write_text(raw, encoding="utf-8")
    with pytest.raises(FixtureError):
        FixtureLoader(tmp_path).load_json("fixture.json")
