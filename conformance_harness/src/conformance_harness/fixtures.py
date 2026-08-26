"""Deterministic, resource-bounded, path-confined JSON fixture loading."""

import json
import math
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any


class FixtureError(ValueError):
    """Fixture lookup or content failed closed."""


MAX_FIXTURE_BYTES = 64 * 1024
MAX_FIXTURE_DEPTH = 32
SUPPORTED_SUFFIXES = frozenset({".json"})
SENSITIVE_KEY = re.compile(
    r"(^|[_-])(authorization|cookie|credential|password|private[_-]?key|secret|token)([_-]|$)",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(bearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|AKIA[A-Z0-9]{12,})",
    re.IGNORECASE,
)


def _validate_content(value: object) -> None:
    pending = [(value, 0)]
    while pending:
        current, depth = pending.pop()
        if depth > MAX_FIXTURE_DEPTH:
            raise FixtureError("fixture exceeds maximum nesting depth")
        if isinstance(current, Mapping):
            for key, item in current.items():
                if not isinstance(key, str):
                    raise FixtureError("fixture object keys must be strings")
                if SENSITIVE_KEY.search(key):
                    raise FixtureError("credential-shaped fixture key is prohibited")
                pending.append((item, depth + 1))
        elif isinstance(current, list):
            pending.extend((item, depth + 1) for item in current)
        elif isinstance(current, str) and SENSITIVE_VALUE.search(current):
            raise FixtureError("credential-shaped fixture value is prohibited")
        elif isinstance(current, float) and not math.isfinite(current):
            raise FixtureError("non-finite fixture number is prohibited")
        elif current is not None and not isinstance(current, (str, int, float, bool)):
            raise FixtureError("unsupported fixture object type")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise FixtureError(f"duplicate fixture object field: {key}")
        value[key] = item
    return value


class FixtureLoader:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve(strict=True)
        if not self._root.is_dir():
            raise FixtureError("fixture root must be a directory")

    def load_json(self, relative_path: str) -> Any:
        candidate = Path(relative_path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise FixtureError("absolute and traversal fixture paths are prohibited")
        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise FixtureError("unsupported fixture file type")
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
            if resolved.stat().st_size > MAX_FIXTURE_BYTES:
                raise FixtureError("fixture exceeds maximum byte size")
            value = json.loads(
                resolved.read_text(encoding="utf-8"), object_pairs_hook=_unique_object
            )
            _validate_content(value)
        except FixtureError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
            raise FixtureError(f"malformed fixture: {type(exc).__name__}") from exc
        return deepcopy(value)

    def load_many(
        self, relative_paths: Sequence[str], *, identity_field: str = "id"
    ) -> tuple[Mapping[str, Any], ...]:
        loaded: list[Mapping[str, Any]] = []
        identities: set[str] = set()
        for relative_path in relative_paths:
            value = self.load_json(relative_path)
            if not isinstance(value, Mapping):
                raise FixtureError("identified fixture must be an object")
            identity = value.get(identity_field)
            if not isinstance(identity, str) or not identity:
                raise FixtureError("fixture identity must be a non-empty string")
            if identity in identities:
                raise FixtureError(f"duplicate fixture identity: {identity}")
            identities.add(identity)
            loaded.append(value)
        return tuple(loaded)
