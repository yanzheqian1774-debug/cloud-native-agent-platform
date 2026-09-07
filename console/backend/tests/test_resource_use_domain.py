from datetime import UTC, datetime

import pytest
from agent_console.resource_use_domain import (
    EffectiveUseState,
    MeasurementAvailability,
    ResourceMeasurement,
    ResourceUseError,
    ResourceUseFact,
    ResourceUseFactKind,
    reduce_resource_use,
)


def fact(kind: ResourceUseFactKind, ordinal: int = 1) -> ResourceUseFact:
    now = datetime.now(UTC)
    return ResourceUseFact(
        f"fact:{ordinal}",
        "use:1",
        kind,
        "knowledge",
        f"observation:{ordinal}",
        "a" * 64,
        now,
        now,
    )


def measurement(availability, value):
    now = datetime.now(UTC)
    return ResourceMeasurement(
        "measurement:1",
        "use:1",
        "retrieval_count",
        value,
        "count",
        availability,
        "knowledge",
        "b" * 64,
        now,
        now,
        now,
        "AUTHORITATIVE",
        "EXACT",
        (),
        "EXACT",
        True,
        "NONE",
        (),
    )


def test_reducer_does_not_infer_selected_dispatch_or_success() -> None:
    snapshot = reduce_resource_use(
        "use:1",
        (fact(ResourceUseFactKind.SELECTED),),
        (),
        high_water=1,
    )
    assert snapshot.effective_state is EffectiveUseState.SELECTED


def test_conflicting_terminal_facts_fail_closed() -> None:
    snapshot = reduce_resource_use(
        "use:1",
        (
            fact(ResourceUseFactKind.SUCCEEDED),
            fact(ResourceUseFactKind.FAILED, 2),
        ),
        (),
        high_water=2,
    )
    assert snapshot.effective_state is EffectiveUseState.CONFLICTED
    assert snapshot.conflicts == (
        "CONFLICTING_TERMINAL_FACTS",
        "STATE_AFTER_TERMINAL",
    )


def test_no_result_is_a_distinct_terminal_state() -> None:
    snapshot = reduce_resource_use(
        "use:1", (fact(ResourceUseFactKind.NO_RESULT),), (), high_water=1
    )
    assert snapshot.effective_state is EffectiveUseState.NO_RESULT


def test_regression_and_conflicting_source_observation_fail_closed() -> None:
    now = datetime.now(UTC)
    conflict = ResourceUseFact(
        "fact:conflict",
        "use:1",
        ResourceUseFactKind.REQUESTED,
        "knowledge",
        "observation:1",
        "b" * 64,
        now,
        now,
    )
    snapshot = reduce_resource_use(
        "use:1",
        (fact(ResourceUseFactKind.DISPATCH_RECORDED), conflict),
        (),
        high_water=2,
    )
    assert snapshot.effective_state is EffectiveUseState.CONFLICTED
    assert snapshot.conflicts == (
        "CONFLICTING_SOURCE_OBSERVATION",
        "ILLEGAL_STATE_REGRESSION",
    )


def test_missing_measurement_is_null_not_zero() -> None:
    value = measurement(MeasurementAvailability.NOT_COLLECTED, None)
    assert value.value is None
    with pytest.raises(ResourceUseError, match="UNAVAILABLE_MEASUREMENT_MUST_BE_NULL"):
        measurement(MeasurementAvailability.NOT_COLLECTED, 0)


def test_measurement_only_history_is_rejected() -> None:
    with pytest.raises(ResourceUseError, match="RESOURCE_USE_STATE_FACT_REQUIRED"):
        reduce_resource_use(
            "use:1",
            (fact(ResourceUseFactKind.MEASUREMENT_RECORDED),),
            (measurement(MeasurementAvailability.MEASURED, 1),),
            high_water=1,
        )
