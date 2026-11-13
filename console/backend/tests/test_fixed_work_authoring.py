"""Configuration is not an executable trigger or a grant."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from agent_console.fixed_work_authoring import AuthoringPolicy, SaveDraft, TriggerDraft
from agent_console.workbench_fixed_work import fixed_work_operations
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from pydantic import ValidationError


def body():
    return dict(
        workId="work:1",
        revisionId="revision:1",
        expectedVersion=0,
        commandId="save:1",
        title="交接检查",
        instruction="工作日检查交接资料",
        trigger=dict(
            kind="SCHEDULE",
            timezone="Asia/Shanghai",
            localTime="09:00",
            cadence="WEEKDAY",
        ),
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(enabled=True),
        dict(workId="unreadable/path"),
        dict(subjectId="other"),
        dict(
            trigger=dict(
                kind="SCHEDULE",
                timezone="Not/AZone",
                localTime="09:00",
                cadence="DAILY",
            )
        ),
        dict(expectedVersion=1),
        dict(instruction=" "),
    ],
)
def test_draft_rejects_execution_identity_and_invalid_configuration(change):
    with pytest.raises(ValidationError):
        SaveDraft.model_validate({**body(), **change})


def test_registry_has_no_trigger_enable_or_execution():
    operations = fixed_work_operations("/not-used", lambda: None)
    assert [(o.name, o.method) for o in operations] == [
        ("LIST_FIXED_WORK_DRAFTS", "GET"),
        ("SAVE_FIXED_WORK_DRAFT", "POST"),
        ("READ_FIXED_WORK_DRAFT", "GET"),
    ]
    path = {"team_id": "t", "team_revision_id": "r"}
    assert [
        (g.owner, g.action, g.exact_resource)
        for g in operations[1].grant_builder(None, path, {}, {})
    ] == [("TEAM", "READ", "team:t:r"), ("TEAM", "REVISE", "team:t:aggregate")]


def test_policy_default_off_expiry_and_subject():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    data = dict(
        schemaVersion="fixed-work-authoring-policy.v1",
        policyId="p",
        expiresAt="2027-01-01T00:00:00Z",
        scopes=[
            dict(
                tenantId="t",
                securityDomain="d",
                subjectId="u",
                teamId="team",
                teamRevisionId="r",
                teamDigest="a" * 64,
                operations=["READ", "SAVE"],
            )
        ],
    )
    context = SimpleNamespace(
        scope=SimpleNamespace(tenant_id="t", security_domain="d"), principal_id="u"
    )
    with pytest.raises(WorkbenchOwnerError):
        AuthoringPolicy.model_validate(data).require(context, "team", "r", "SAVE", now)
    policy = AuthoringPolicy.model_validate({**data, "enabled": True})
    assert policy.require(context, "team", "r", "SAVE", now).teamDigest == "a" * 64
    context.principal_id = "other"
    with pytest.raises(WorkbenchOwnerError):
        policy.require(context, "team", "r", "SAVE", now)
    context.principal_id = "u"
    with pytest.raises(WorkbenchOwnerError):
        policy.require(context, "team", "r", "SAVE", datetime(2028, 1, 1, tzinfo=UTC))


def test_event_is_only_description_and_forbids_schedule_fields():
    assert TriggerDraft(kind="EVENT", eventDescription="有新交接资料时").kind == "EVENT"
    with pytest.raises(ValidationError):
        TriggerDraft(kind="EVENT", eventDescription="事件", timezone="UTC")
