# ruff: noqa: RUF001 -- Chinese UI text and explicit Chinese punctuation parsing.
"""Advisory configuration parsing, never model or execution acceptance."""

import pytest
from agent_console.fixed_work_natural_preview import preview_instruction


def test_explicit_weekday_time_and_timezone_without_defaults():
    result = preview_instruction("每个工作日北京时间上午9点半检查交接资料")
    assert result["candidateTrigger"] == {
        "kind": "SCHEDULE",
        "timezone": "Asia/Shanghai",
        "localTime": "09:30",
        "cadence": "WEEKDAY",
        "eventDescription": None,
    }
    assert result["issues"] == []
    assert result["modelInvoked"] is False and result["executionEnabled"] is False


def test_explicit_evening_and_missing_fields_remain_visible():
    result = preview_instruction("每天晚上9点检查资料")
    assert result["candidateTrigger"]["localTime"] == "21:00"
    assert result["candidateTrigger"]["timezone"] is None
    assert result["issues"]


@pytest.mark.parametrize(
    "text",
    [
        "不要每天9点执行",
        "例如每天9点执行",
        "每天9点或是10点执行",
        "每周一9点执行",
        "每天25点执行",
        "每天9点之前完成",
        "每天9点和10点执行",
        "每天工作日9点执行",
        "每天凌晨12点执行",
    ],
)
def test_ambiguity_never_replaces_saved_arrangement(text):
    old = {
        "kind": "SCHEDULE",
        "timezone": "Asia/Shanghai",
        "localTime": "08:00",
        "cadence": "WEEKDAY",
        "eventDescription": None,
    }
    result = preview_instruction(text, old)
    assert result["candidateTrigger"] == old
    assert result["issues"] and not result["derivedFields"]
    assert old["localTime"] == "08:00"


def test_event_is_only_literal_description_not_enabled_adapter():
    result = preview_instruction("当交接文档更新时，核对缺项")
    assert result["candidateTrigger"]["eventDescription"] == "交接文档更新"
    assert result["validation"] == "CONFIGURATION_STRUCTURE_ONLY"
    assert result["authorityGranted"] is False


def test_preview_owner_reads_exact_saved_configuration_without_saving():
    from dataclasses import dataclass

    from agent_console.workbench_fixed_work_preview import FixedWorkPreviewOwner

    @dataclass
    class Call:
        operation: str
        payload: dict
        query: dict
        path: dict

    calls = []
    old = {
        "kind": "SCHEDULE",
        "timezone": "Asia/Shanghai",
        "localTime": "08:00",
        "cadence": "WEEKDAY",
        "eventDescription": None,
    }

    def reader(call):
        calls.append(call)
        if call.operation == "LIST_FIXED_WORK_DRAFTS":
            return {
                "team": {"teamId": "t", "revisionId": "r", "digest": "a" * 64},
                "configurationCanSave": False,
            }
        assert call.operation == "READ_FIXED_WORK_DRAFT"
        assert call.path["work_id"] == "w" and call.path["revision_id"] == "v"
        return {"digest": "b" * 64, "draft": {"title": "Original", "trigger": old}}

    result = FixedWorkPreviewOwner(reader)(
        Call(
            "PREVIEW_FIXED_WORK_INSTRUCTION",
            {
                "instruction": "每天北京时间9点检查资料",
                "previous": {"workId": "w", "revisionId": "v", "digest": "b" * 64},
            },
            {},
            {"team_id": "t", "team_revision_id": "r"},
        )
    )
    assert result["previousTrigger"] == old
    assert result["candidateTrigger"]["localTime"] == "09:00"
    assert result["configurationCanSave"] is False
    assert [c.operation for c in calls] == [
        "LIST_FIXED_WORK_DRAFTS",
        "READ_FIXED_WORK_DRAFT",
    ]
    assert old["localTime"] == "08:00"


def test_preview_registration_is_default_off():
    from agent_console.workbench_fixed_work_preview import fixed_work_preview_operations

    assert fixed_work_preview_operations(None) == ()
