"""Compare planning input to server-retained understanding provenance.

This does not grant READ access or validate a generated execution plan.
Historical understanding records without provenance are not backfilled.
"""

from types import SimpleNamespace

from .authority_contracts import AuthorityError
from .plan_suggestion_domain import ExactReference, PlanningError
from .planning_source_reference import approved_source, is_source_boundary


class PlanningSourceMismatch(ValueError):
    """Generated semantics do not preserve the requested exact source."""


def require_output_source(request, semantics):
    boundaries = [
        line
        for answer in request.answers
        for line in answer.splitlines()
        if is_source_boundary(line)
    ]
    if not boundaries:
        return  # General planning without an exact source remains supported.
    try:
        expected = approved_source(SimpleNamespace(boundaries=boundaries))
        if approved_source(semantics) != expected:
            raise ValueError("source differs")
    except (ValueError, PlanningError) as exc:
        raise PlanningSourceMismatch("PLANNING_OUTPUT_SOURCE_MISMATCH") from exc


def require_same_source(metadata, request):
    if metadata is None:
        return
    try:
        expected = ExactReference.model_validate(metadata["source"])
        boundaries = [
            line
            for answer in request["answers"]
            for line in answer.splitlines()
            if is_source_boundary(line)
        ]
        actual = approved_source(SimpleNamespace(boundaries=boundaries))
        if actual != expected:
            raise ValueError("source differs")
    except (KeyError, TypeError, AttributeError, ValueError, PlanningError) as exc:
        raise AuthorityError("CONTEXT_ADMISSION_SOURCE_MISMATCH") from exc
