"""Restrict new modern proposals to the platform's existing planning-only scope."""

from .cost_execution_revision import (
    DELIVERY_SYNTHETIC_ONLY,
    EXECUTION_ONLY,
    PLANNING_ONLY,
    READ_ONLY_PLANNING,
    SYNTHETIC_ONLY,
)
from .plan_suggestion_domain import FlexiblePlanSemantics


def restrict_to_planning(semantics):
    if not isinstance(semantics, FlexiblePlanSemantics):
        return semantics
    if EXECUTION_ONLY in semantics.business_rules or any(
        marker in semantics.boundaries
        for marker in (SYNTHETIC_ONLY, DELIVERY_SYNTHETIC_ONLY)
    ):
        raise ValueError("PROVIDER_CANNOT_DECLARE_EXECUTION_SCOPE")
    document = semantics.model_dump(mode="json")
    for field, marker in (
        ("business_rules", PLANNING_ONLY),
        ("boundaries", READ_ONLY_PLANNING),
    ):
        if document[field].count(marker) > 1:
            raise ValueError("PLANNING_SCOPE_DUPLICATE")
        if marker not in document[field]:
            document[field].append(marker)
    # Do not trim user/model facts to fit the contract; overflow remains invalid.
    return FlexiblePlanSemantics.model_validate(document)
