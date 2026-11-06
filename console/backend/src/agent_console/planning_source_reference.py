# ruff: noqa: RUF001 -- Exact source boundary labels, never fuzzy prose matching.
"""Strict source text compatibility without changing recorded proposal content."""

from .plan_suggestion_domain import ExactReference, PlanningConflict

SOURCE_PREFIXES = ("隔离合成来源：", "仅使用隔离合成只读来源：")


def is_source_boundary(text):
    return text.startswith(SOURCE_PREFIXES)


def approved_source(semantics):
    lines = [text for text in semantics.boundaries if is_source_boundary(text)]
    if len(lines) != 1:
        raise PlanningConflict("SOURCE_CHANGE_EXACT_OLD_SOURCE_REQUIRED")
    line = lines[0]
    prefix = next(p for p in SOURCE_PREFIXES if line.startswith(p))
    try:
        identity, revision, digest = line[len(prefix) :].split("；")
        if not revision.startswith("修订：") or not digest.startswith("SHA256："):
            raise ValueError("source fields required")
        reference = ExactReference(
            resource_id=identity,
            revision_id=revision[len("修订：") :],
            digest=digest[len("SHA256：") :],
        )
    except ValueError as exc:
        raise PlanningConflict("SOURCE_CHANGE_OLD_SOURCE_INVALID") from exc
    selected = {
        r.selected
        for r in getattr(semantics, "requirements", ())
        if r.kind == "KNOWLEDGE" and r.selected is not None
    }
    if selected and selected != {reference}:
        raise PlanningConflict("SOURCE_CHANGE_SELECTION_MISMATCH")
    return reference
