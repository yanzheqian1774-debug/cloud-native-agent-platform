"""Configuration diff boundaries; not persistence or actual source succession."""

from copy import deepcopy
from dataclasses import replace

import pytest
from agent_console.digital_employee_definition import digest
from agent_console.execution_domain import ScopeIdentity
from agent_console.fixed_work_succession import (
    SuccessionCommand,
    preview,
    successor_ids,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from pydantic import ValidationError
from test_team_definition import team


def facts():
    old = team()
    new = replace(
        old,
        revision_id="team-revision:2",
        predecessor_revision_id=old.revision_id,
        members=(
            replace(
                old.members[0],
                employee_revision_id="employee-revision:2",
                employee_digest="b" * 64,
            ),
        ),
    )
    record = {
        "workId": "work:1",
        "revisionId": "revision:1",
        "createdBy": "human:alice",
        "title": "交接资料核对",
        "instruction": "每天20:00核对已选合成资料; 不修改业务系统",
        "trigger": {
            "kind": "SCHEDULE",
            "timezone": "Asia/Shanghai",
            "localTime": "20:00",
            "cadence": "DAILY",
        },
        "team": {
            "teamId": old.team_id,
            "revisionId": old.revision_id,
            "digest": old.content_digest,
        },
    }
    saved = {"record": record, "digest": digest(record)}
    h = {
        "schemaVersion": "fixed-work-conversation.v1",
        "work": {
            "resource_id": record["workId"],
            "revision_id": record["revisionId"],
            "digest": saved["digest"],
        },
        "team": record["team"],
        "subjectId": "human:alice",
        "conversationId": "original-chat",
        "instructionDigest": digest(record["instruction"]),
        "mode": "TARGET_REVIEW_ONLY",
        "executionEnabled": False,
    }
    return saved, {"record": h, "digest": digest(h)}, old, new


def test_exact_version_diff_preserves_instruction_schedule_and_original_chat():
    saved, handoff, old, new = facts()
    original = deepcopy(saved)
    value = preview(saved, handoff, old, new, "human:alice", "original-chat")
    assert value["conversationId"] == "original-chat"
    assert value["preserved"]["trigger"]["localTime"] == "20:00"
    assert (
        value["memberChanges"][0]["before"]["employee_revision_id"]
        == "employee-revision:1"
    )
    assert (
        value["memberChanges"][0]["after"]["employee_revision_id"]
        == "employee-revision:2"
    )
    assert value["executionEnabled"] is False
    assert value["currentOwnerChecksRequired"] is True
    value["preserved"]["trigger"]["localTime"] = "08:00"
    assert saved == original


@pytest.mark.parametrize("change", ["actor", "chat", "body", "team", "branch", "scope"])
def test_wrong_source_identity_and_unrelated_team_are_not_updates(change):
    saved, handoff, old, new = facts()
    subject, chat = "human:alice", "original-chat"
    if change == "actor":
        subject = "human:administrator"
    elif change == "chat":
        chat = "another-chat"
    elif change == "body":
        saved["record"]["instruction"] = "changed instruction"
    elif change == "team":
        new = replace(new, team_id="team:unrelated")
    elif change == "branch":
        new = replace(new, predecessor_revision_id="team-revision:unrelated")
    elif change == "scope":
        new = replace(new, scope=ScopeIdentity("other-tenant", "isolated"))
    with pytest.raises(WorkbenchOwnerError):
        preview(saved, handoff, old, new, subject, chat)


def test_client_cannot_assert_actor_target_or_current_eligibility():
    _saved, handoff, _, new = facts()
    body = {
        "predecessor": handoff["record"]["work"],
        "predecessorHandoffDigest": handoff["digest"],
        "team": {
            "resource_id": new.team_id,
            "revision_id": new.revision_id,
            "digest": new.content_digest,
        },
        "commandId": "same-update-command",
    }
    SuccessionCommand.model_validate(body)
    for field in (
        "subjectId",
        "conversationId",
        "enabled",
        "target",
        "currentOwnerChecksPassed",
    ):
        with pytest.raises(ValidationError):
            SuccessionCommand.model_validate({**body, field: True})


def test_same_command_internal_ids_are_stable_and_scope_separated():
    scope = ("tenant", "domain")
    first = successor_ids(scope, "logical-work", "same-key")
    assert successor_ids(scope, "logical-work", "same-key") == first
    assert successor_ids(("other", "domain"), "logical-work", "same-key") != first
    assert successor_ids(scope, "other-logical-work", "same-key") != first
    assert successor_ids(scope, "logical-work", "different-key") != first
