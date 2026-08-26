"""Disposable S5-SPIKE-008 authoring and dual-view fixture behavior.

The shapes in this module are internal mock candidates. They are not public
DTOs, contracts, persistence semantics, or production Console behavior.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "customer-complaint-quality-improvement.json"
)
EDITABLE_FIELDS = (
    "name",
    "role_title",
    "role_description",
    "business_responsibilities",
    "can_do",
    "cannot_do",
    "knowledge_scope",
)


def load_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    """Return an independent copy of the deterministic synthetic fixture."""
    return deepcopy(json.loads(path.read_text()))


def create_draft(fixture: dict[str, Any]) -> dict[str, Any]:
    """Create a separate editable draft without mutating published input."""
    published = fixture["authoring"]["published"]
    return {
        "draft_id": fixture["identities"]["draft_id"],
        "based_on_definition_id": published["definition_id"],
        "state": "DRAFT",
        "approval": "REQUIRED",
        "values": deepcopy({key: published[key] for key in EDITABLE_FIELDS}),
        "suggestions": [],
        "validation_issues": [],
    }


def apply_ai_suggestion(
    draft: dict[str, Any], suggestion: dict[str, Any]
) -> dict[str, Any]:
    """Return a new draft with an explicitly non-authoritative candidate."""
    result = deepcopy(draft)
    result["suggestions"].append(
        {
            "field": suggestion["field"],
            "candidate": deepcopy(suggestion["candidate"]),
            "status": "PENDING_HUMAN_REVIEW",
        }
    )
    result["state"] = "DIFF_PENDING_APPROVAL"
    return result


def accept_suggestion(draft: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Apply one candidate only through an explicit Human action."""
    result = deepcopy(draft)
    suggestion = result["suggestions"][index]
    if suggestion["field"] not in EDITABLE_FIELDS:
        raise ValueError("SUGGESTED_FIELD_NOT_EDITABLE")
    result["values"][suggestion["field"]] = deepcopy(suggestion["candidate"])
    suggestion["status"] = "HUMAN_ACCEPTED_IN_DRAFT"
    return result


def field_diff(
    published: dict[str, Any], draft: dict[str, Any]
) -> list[dict[str, Any]]:
    """Produce a stable field-ordered Diff between published and Draft values."""
    return [
        {
            "field": field,
            "published": deepcopy(published[field]),
            "draft": deepcopy(draft["values"][field]),
        }
        for field in EDITABLE_FIELDS
        if published[field] != draft["values"][field]
    ]


def validate_draft(draft: dict[str, Any]) -> list[dict[str, str]]:
    """Fail closed for empty required fields or unreviewed suggestions."""
    issues = []
    for field in ("name", "role_title", "role_description"):
        value = draft["values"].get(field)
        if not isinstance(value, str) or not value.strip():
            issues.append({"field": field, "code": "REQUIRED_VALUE_MISSING"})
    for field in ("business_responsibilities", "can_do", "cannot_do"):
        value = draft["values"].get(field)
        if not isinstance(value, list) or not value:
            issues.append({"field": field, "code": "NON_EMPTY_LIST_REQUIRED"})
    if any(item["status"] == "PENDING_HUMAN_REVIEW" for item in draft["suggestions"]):
        issues.append({"field": "suggestions", "code": "HUMAN_REVIEW_REQUIRED"})
    return issues


def approve_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Approve a valid Draft; invalid or pending input fails closed."""
    result = deepcopy(draft)
    issues = validate_draft(result)
    result["validation_issues"] = issues
    if issues:
        result["state"] = "DRAFT_INVALID"
        result["approval"] = "REQUIRED"
        return result
    result["state"] = "APPROVED_FOR_MOCK_PUBLISH"
    result["approval"] = "HUMAN_APPROVED"
    return result


def reject_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Keep rejected work visible and explicitly non-published."""
    result = deepcopy(draft)
    result["state"] = "DRAFT_REJECTED_NOT_PUBLISHED"
    result["approval"] = "HUMAN_REJECTED"
    return result


def mock_publish(published: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    """Return a mock version only after approval; no persistence occurs."""
    if draft["state"] != "APPROVED_FOR_MOCK_PUBLISH":
        raise ValueError("HUMAN_APPROVAL_REQUIRED")
    result = deepcopy(published)
    result.update(deepcopy(draft["values"]))
    result["version"] = "mock-v2"
    result["status"] = "APPROVED_MOCK_DEFINITION"
    result["publication"] = "IN_MEMORY_ONLY_NOT_PERSISTED"
    return result


def project_views(fixture: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return independent Product and Technical projections of one execution."""
    execution = fixture["execution"]
    product = deepcopy(fixture["views"]["product"])
    technical = deepcopy(fixture["views"]["technical"])
    product["platform_execution_identity"] = execution["platform_execution_identity"]
    technical["platform_execution_identity"] = execution["platform_execution_identity"]
    return product, technical
