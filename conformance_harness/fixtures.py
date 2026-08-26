"""Deterministic, path-confined JSON fixture loading."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    """Fixture lookup or content failed closed."""


class FixtureLoader:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve(strict=True)
        if not self._root.is_dir():
            raise FixtureError("fixture root must be a directory")

    def load_json(self, relative_path: str) -> Any:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise FixtureError("absolute and traversal fixture paths are prohibited")
        try:
            resolved = (self._root / candidate).resolve(strict=True)
            resolved.relative_to(self._root)
        except (OSError, ValueError) as exc:
            raise FixtureError(
                "fixture path is missing or outside fixture root"
            ) from exc
        if not resolved.is_file():
            raise FixtureError("fixture path must identify a file")
        try:
            with resolved.open("r", encoding="utf-8") as stream:
                value = json.load(stream)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise FixtureError(f"malformed fixture: {type(exc).__name__}") from exc
        return deepcopy(value)
