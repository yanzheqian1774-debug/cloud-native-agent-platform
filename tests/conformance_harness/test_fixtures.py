import json
from pathlib import Path

import pytest

from conformance_harness.fixtures import FixtureError, FixtureLoader


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
