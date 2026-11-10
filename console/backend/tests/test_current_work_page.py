from datetime import UTC, datetime

import pytest
from agent_console.workbench_current_work_page import CurrentWorkItem, directory_page
from agent_console.workbench_current_work_query import CurrentWorkQuery
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_pagination import WorkbenchCursorCodec
from pydantic import ValidationError
from test_workbench_pagination import context

NOW = datetime(2026, 11, 10, tzinfo=UTC)
CODEC = WorkbenchCursorCodec(b"p" * 32)


def item(name, initiator="human:alice", state="completed"):
    return CurrentWorkItem(
        workflowRunId=name,
        preparationDigest="a" * 64,
        title="检查交接材料",
        createdAt=NOW,
        initiatorId=initiator,
        executionState="SUCCEEDED",
        displayState=state,
        progressVersion=3,
        problemId="problem:one",
        problemRevisionId="revision:one",
        problemDigest="b" * 64,
        pendingQuestionCount=None,
        artifactCount=3,
        businessResolution=None,
        originConversationId=None,
        originVerified=False,
    )


def page(items, **values):
    query = CurrentWorkQuery(scopeFilter="visible", **values)
    return directory_page(
        items, query, CODEC, context(), generation=1, recovery_epoch=1, read_at=NOW
    )


def test_equal_time_keyset_pages_keep_counts_and_do_not_duplicate_runs():
    records = [item("run:a"), item("run:b"), item("run:c")]
    first = page(records, pageSize=2)
    assert [x["workflowRunId"] for x in first["items"]] == ["run:c", "run:b"]
    assert first["total"] == sum(first["counts"].values()) == 3
    second = page(records, pageSize=2, cursor=first["nextCursor"])
    assert [x["workflowRunId"] for x in second["items"]] == ["run:a"]
    assert second["total"] == sum(second["counts"].values()) == 3
    assert second["nextCursor"] is None
    # Reauthorization may remove the cursor's record before the next page.
    removed = page([records[0]], pageSize=2, cursor=first["nextCursor"])
    assert removed["total"] == 1
    assert removed["items"][0]["workflowRunId"] == "run:a"


def test_scope_search_state_counts_use_same_complete_set():
    records = [item("run:a"), item("run:b", "human:bob"), item("run:c", None, "failed")]
    query = CurrentWorkQuery(scopeFilter="initiated", query="交接", state="completed")
    result = directory_page(
        records, query, CODEC, context(), generation=1, recovery_epoch=1, read_at=NOW
    )
    assert result["total"] == result["counts"]["completed"] == 1
    assert result["items"][0]["workflowRunId"] == "run:a"
    assert page(records, query="不存在")["total"] == 0
    assert page(records, state="waiting")["items"] == []


def test_raw_rows_duplicate_runs_and_unzoned_time_are_rejected():
    with pytest.raises(TypeError, match="AUTHORIZED_PROJECTION_REQUIRED"):
        page([{"preparation": {"private": "body"}}])
    with pytest.raises(WorkbenchOwnerError, match="CURRENT_WORK_DUPLICATE_RUN"):
        page([item("same"), item("same")])
    value = item("one").model_dump()
    with pytest.raises(ValidationError):
        CurrentWorkItem.model_validate(value | {"createdAt": "2026-11-10T00:00:00"})
    with pytest.raises(ValidationError):
        CurrentWorkItem.model_validate(value | {"preparation": {"private": "body"}})


def test_unknown_question_coverage_survives_waiting_filter_and_paging():
    unknown = item("run:a").model_copy(
        update={"executionState": "RUNNING", "displayState": "unknown"}
    )
    complete = item("run:z")
    result = page([unknown, complete], pageSize=1)
    assert result["items"][0]["workflowRunId"] == "run:z"
    assert result["questionStatusComplete"] is False
    waiting = page([unknown, complete], state="waiting")
    assert waiting["total"] == 0 and waiting["items"] == []
    assert waiting["questionStatusComplete"] is False
    assert page([complete])["questionStatusComplete"] is True
    assert page([unknown], query="does not match")["questionStatusComplete"] is True
