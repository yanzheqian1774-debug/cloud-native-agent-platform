from datetime import UTC, datetime

import pytest
from agent_console.business_problem_domain import (
    TRANSITIONS,
    BusinessProblemError,
    BusinessProblemRevision,
    BusinessProblemState,
    CriterionType,
    PlanProblemBinding,
    SuccessCriteriaSetRevision,
    SuccessCriterionRevision,
    canonical_digest,
)
from agent_console.execution_domain import ScopeIdentity


def test_canonical_digest_is_order_independent_and_content_sensitive() -> None:
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})


def test_problem_revision_and_lineage_are_in_digest() -> None:
    now = datetime.now(UTC)
    scope = ScopeIdentity("tenant", "domain")
    first = BusinessProblemRevision(
        scope,
        "problem",
        "revision-1",
        1,
        None,
        "质量",
        "改善质量",
        "owner",
        "actor",
        now,
    )
    successor = BusinessProblemRevision(
        scope,
        "problem",
        "revision-2",
        2,
        first.revision_id,
        "质量",
        "改善交付质量",
        "owner",
        "actor",
        now,
    )
    assert first.digest != successor.digest
    assert successor.predecessor_revision_id == first.revision_id


@pytest.mark.parametrize(
    ("kind", "measurement"),
    [
        (CriterionType.DETERMINISTIC_BOOLEAN, {"expected": True}),
        (
            CriterionType.NUMERIC_THRESHOLD,
            {"operator": "LT", "threshold": 1, "unit": "percent"},
        ),
        (CriterionType.CATEGORICAL_RESULT, {"allowed_values": ["PASS"]}),
        (CriterionType.EVIDENCE_PRESENCE, {"minimum_count": 1}),
        (CriterionType.HUMAN_EVALUATED, {"rubric": "owner confirms"}),
        (CriterionType.NOT_MEASURABLE, {"reason": "NOT_MEASURABLE"}),
    ],
)
def test_supported_typed_measurements(
    kind: CriterionType, measurement: dict[str, object]
) -> None:
    value = SuccessCriterionRevision(
        ScopeIdentity("tenant", "domain"),
        "criterion",
        "criterion-revision",
        1,
        None,
        kind,
        measurement,
        ("EXECUTION",),
        "builtin",
        "v1",
        {"when": "always"},
        "actor",
        datetime.now(UTC),
    )
    assert len(value.digest) == 64


def test_invalid_measurement_is_rejected() -> None:
    with pytest.raises(
        BusinessProblemError, match="SUCCESS_CRITERION_MEASUREMENT_INVALID"
    ):
        SuccessCriterionRevision(
            ScopeIdentity("tenant", "domain"),
            "criterion",
            "revision",
            1,
            None,
            CriterionType.NUMERIC_THRESHOLD,
            {"threshold": "one"},
            (),
            "builtin",
            "v1",
            {},
            "actor",
            datetime.now(UTC),
        )


def test_invalid_criterion_type_has_stable_reason() -> None:
    with pytest.raises(BusinessProblemError, match="SUCCESS_CRITERION_TYPE_INVALID"):
        SuccessCriterionRevision(
            ScopeIdentity("tenant", "domain"),
            "criterion",
            "revision",
            1,
            None,
            "UNKNOWN",  # type: ignore[arg-type]
            {},
            (),
            "builtin",
            "v1",
            {},
            "actor",
            datetime.now(UTC),
        )


def test_set_order_and_exact_binding_are_digest_bound() -> None:
    now = datetime.now(UTC)
    scope = ScopeIdentity("tenant", "domain")
    criteria = SuccessCriteriaSetRevision(
        scope,
        "set-1",
        "problem",
        "problem-revision",
        1,
        None,
        ("criterion-a", "criterion-b"),
        "actor",
        now,
    )
    reversed_set = SuccessCriteriaSetRevision(
        scope,
        "set-2",
        "problem",
        "problem-revision",
        2,
        "set-1",
        ("criterion-b", "criterion-a"),
        "actor",
        now,
    )
    binding = PlanProblemBinding(
        scope,
        "binding",
        "plan",
        1,
        "a" * 64,
        "problem",
        "problem-revision",
        "b" * 64,
        criteria.set_revision_id,
        criteria.digest,
        "actor",
        now,
    )
    assert criteria.digest != reversed_set.digest
    assert binding.digest == canonical_digest(binding.digest_contract())


def test_lifecycle_includes_reopen_as_new_work() -> None:
    assert (
        BusinessProblemState.IN_PROGRESS in TRANSITIONS[BusinessProblemState.RESOLVED]
    )
    assert BusinessProblemState.IN_PROGRESS in TRANSITIONS[BusinessProblemState.CLOSED]
    assert BusinessProblemState.DRAFT not in TRANSITIONS[BusinessProblemState.CLOSED]
