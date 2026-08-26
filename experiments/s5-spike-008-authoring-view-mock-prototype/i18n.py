"""Message-key localization for the isolated S5-SPIKE-008 prototype."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_LOCALE = "en-US"
SUPPORTED_LOCALES = ("en-US", "zh-CN")
CATALOG_ROOT = Path(__file__).parent / "locales"


def load_catalog(locale: str) -> dict[str, str]:
    """Load one isolated mock catalog, or an empty catalog when unknown."""
    path = CATALOG_ROOT / f"{locale}.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def translate(
    locale: str, key: str, catalogs: dict[str, dict[str, str]] | None = None
) -> str:
    """Resolve selected locale, en-US default, then stable Message Key."""
    available = catalogs or {
        supported: load_catalog(supported) for supported in SUPPORTED_LOCALES
    }
    selected = available.get(locale, {})
    default = available.get(DEFAULT_LOCALE, {})
    return selected.get(key) or default.get(key) or key


def localized_business_content(fixture: dict[str, Any], locale: str) -> dict[str, Any]:
    """Project localized display content without changing execution evidence."""
    result = deepcopy(fixture)
    content = fixture["localized_content"].get(
        locale, fixture["localized_content"][DEFAULT_LOCALE]
    )
    for employee, localized in zip(
        result["directory"], content["employees"], strict=True
    ):
        for field in (
            "role_title",
            "role_description",
            "business_responsibilities",
            "can_do",
            "cannot_do",
            "knowledge_scope",
        ):
            employee[field] = deepcopy(localized[field])
    for step, label in zip(
        result["business_entry"]["work_plan"], content["work_plan"], strict=True
    ):
        step["label"] = label
    result["knowledge"]["collection"]["name"] = content["knowledge_collection"]
    for asset, localized in zip(
        result["knowledge"]["assets"], content["knowledge_assets"], strict=True
    ):
        asset["title"] = localized["title"]
        asset["citation"] = localized["citation"]
    result["display_locale"] = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    return result
