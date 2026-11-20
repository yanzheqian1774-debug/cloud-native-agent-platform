"""Projection boundary tests, using controlled authoring/grant/read fixtures."""

from datetime import UTC, datetime
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console.workbench_fixed_work import FixedWorkAuthoringOwner
from agent_console.workbench_fixed_work_activity import (
    FixedWorkActivityOwner,
    fixed_work_activity_operations,
)
from agent_console.workbench_owner_authorization import AuthorizedOwnerCall


class Authoring(FixedWorkAuthoringOwner):
    def __init__(self):
        pass

    def __call__(self, call):
        assert call.operation == "READ_FIXED_WORK_DRAFT"
        assert call.path["work_id"] == "work"
        return {"draft": {"workId": "work", "revisionId": "r"}, "digest": "d"}


def case(allow=True):
    c = N(
        execute=Mock(
            side_effect=[
                N(fetchone=lambda: {"name": "receipts"}),
                N(
                    fetchall=lambda: [
                        {
                            "event_id": "event",
                            "preparation_digest": "p",
                            "workflow_run_id": "run",
                            "recorded_at": datetime.now(UTC),
                        }
                    ]
                ),
            ]
        )
    )
    authority = N(current_action_grants=Mock(return_value=(allow,)), require=Mock())
    context = N(
        principal_id="human:reader", scope=N(tenant_id="t", security_domain="d")
    )
    call = AuthorizedOwnerCall(
        "READ_FIXED_WORK_ACTIVITY",
        context,
        c,
        {},
        {"work_id": "work"},
        {},
        (),
        authority,
        1,
        1,
    )
    return call


def test_default_off_has_no_routes():
    assert fixed_work_activity_operations(Authoring()) == ()
    (op,) = fixed_work_activity_operations(Authoring(), enabled=True)
    assert op.method == "GET"


def test_team_read_does_not_reveal_execution_without_exact_read(monkeypatch):
    read = Mock(side_effect=AssertionError("no progress read permitted"))
    monkeypatch.setattr(
        "agent_console.workbench_fixed_work_activity.PreparedExecutionStore.read", read
    )
    call = case(False)
    result = FixedWorkActivityOwner(Authoring())(call)
    assert result["items"] == []
    read.assert_not_called()
    call.authority.require.assert_not_called()
    assert result["automaticTriggerStatus"] == "NOT_OBSERVED"


def test_only_actual_progress_returned_with_exact_read(monkeypatch):
    monkeypatch.setattr(
        "agent_console.workbench_fixed_work_activity.PreparedExecutionStore.read",
        lambda *_: (N(digest="p"), N(state="RECOVERY_REQUIRED", version=4)),
    )
    call = case()
    result = FixedWorkActivityOwner(Authoring())(call)
    assert result["items"][0]["state"] == "RECOVERY_REQUIRED"
    assert result["items"][0]["runId"] == "run"
    assert call.authority.require.call_args.args[1:] == (
        "EXECUTION",
        "READ",
        "governed-execution:prepared:p",
    )


def test_mismatched_preparation_rejects_projection(monkeypatch):
    monkeypatch.setattr(
        "agent_console.workbench_fixed_work_activity.PreparedExecutionStore.read",
        lambda *_: (N(digest="other"), N(state="SUCCEEDED", version=4)),
    )
    with pytest.raises(Exception, match="FIXED_WORK_ACTIVITY_BINDING_CHANGED"):
        FixedWorkActivityOwner(Authoring())(case())
