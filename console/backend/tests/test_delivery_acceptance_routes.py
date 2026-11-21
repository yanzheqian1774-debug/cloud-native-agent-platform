"""Default-off routes and exact dedicated authority, no database or model."""

import pytest
from agent_console.authority_configuration import validate_registered_grant
from agent_console.workbench_prepared_execution import (
    DeliveryDecision,
    prepared_execution_operations,
)
from pydantic import ValidationError


def test_default_off_and_explicit_action_grants():
    old = prepared_execution_operations()
    enabled = prepared_execution_operations(delivery_acceptance_enabled=True)
    assert len(enabled) == len(old) + 2
    assert not any("DELIVERY" in o.name for o in old)
    write = next(o for o in enabled if o.name == "DECIDE_PREPARED_DELIVERY")
    for action in ("ACCEPT_DELIVERY", "RETRACT_DELIVERY"):
        grants = write.grant_builder(None, {"digest": "a" * 64}, {"action": action}, {})
        assert len(grants) == 1 and grants[0].action == action
        assert grants[0].owner == "EXECUTION"
        assert grants[0].exact_resource == "governed-execution:prepared:" + "a" * 64
        validate_registered_grant(grants[0], allow_meta=False)


@pytest.mark.parametrize(
    "change",
    [
        {"action": "READ"},
        {"expectedVersion": True},
        {"authority": "admin"},
        {"packageDigest": "wrong"},
    ],
)
def test_command_does_not_accept_authority_or_coerced_cas(change):
    body = {
        "idempotencyKey": "one",
        "action": "ACCEPT_DELIVERY",
        "packageDigest": "a" * 64,
        "expectedVersion": 0,
    }
    with pytest.raises(ValidationError):
        DeliveryDecision.model_validate({**body, **change})


@pytest.mark.parametrize(
    "source", [None, {"resource_id": "other", "revision_id": "1", "digest": "a" * 64}]
)
def test_known_report_cannot_bind_a_different_or_missing_source(source):
    import json

    from agent_console.execution_preparation import ExecutionPreparationError
    from agent_console.prepared_delivery_acceptance import require_artifact_source

    expected = {"resource_id": "real", "revision_id": "1", "digest": "a" * 64}
    with pytest.raises(ExecutionPreparationError, match="SOURCE_MISMATCH"):
        require_artifact_source(
            json.dumps(
                {"schemaVersion": "document-review-output.v1", "sourceSnapshot": source}
            ),
            expected,
        )
    require_artifact_source(
        json.dumps(
            {"schemaVersion": "document-review-output.v1", "sourceSnapshot": expected}
        ),
        expected,
    )
    require_artifact_source("原始阶段文字", expected)
