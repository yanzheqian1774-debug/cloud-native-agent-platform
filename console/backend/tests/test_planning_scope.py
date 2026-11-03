"""Narrow platform scope without coercing provider graph or mutating old plans."""

import pytest
from agent_console.cost_execution_revision import (
    EXECUTION_ONLY,
    PLANNING_ONLY,
    READ_ONLY_PLANNING,
)
from agent_console.plan_suggestion_domain import FlexiblePlanSemantics, PlanSemantics
from agent_console.planning_scope import restrict_to_planning
from pydantic import ValidationError
from test_plan_suggestion_v2 import sample
from test_planning_contracts import modern


def test_scope_only_appends_restrictions_and_preserves_provider_semantics():
    source = FlexiblePlanSemantics.model_validate(modern())
    bounded = restrict_to_planning(source)
    assert bounded.business_rules == (*source.business_rules, PLANNING_ONLY)
    assert bounded.boundaries == (*source.boundaries, READ_ONLY_PLANNING)
    assert PLANNING_ONLY not in source.business_rules
    for field in type(source).model_fields.keys() - {"business_rules", "boundaries"}:
        assert getattr(bounded, field) == getattr(source, field)
    assert restrict_to_planning(bounded) == bounded
    assert bounded.digest != source.digest


def test_provider_cannot_claim_execution_and_duplicate_markers_stay_invalid():
    source = modern()
    source["business_rules"].append(EXECUTION_ONLY)
    with pytest.raises(ValueError, match="CANNOT_DECLARE_EXECUTION"):
        restrict_to_planning(FlexiblePlanSemantics.model_validate(source))
    source = modern()
    source["boundaries"] += [READ_ONLY_PLANNING, READ_ONLY_PLANNING]
    with pytest.raises(ValueError, match="SCOPE_DUPLICATE"):
        restrict_to_planning(FlexiblePlanSemantics.model_validate(source))


def test_scope_never_drops_existing_facts_to_fit_limits_and_legacy_is_unchanged():
    source = modern()
    source["business_rules"] = [f"业务规则{i}" for i in range(32)]
    with pytest.raises(ValidationError):
        restrict_to_planning(FlexiblePlanSemantics.model_validate(source))
    legacy = PlanSemantics.model_validate(sample())
    assert restrict_to_planning(legacy) is legacy
