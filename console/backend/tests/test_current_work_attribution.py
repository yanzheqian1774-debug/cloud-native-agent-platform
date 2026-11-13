"""Requester provenance and scope consistency; no model or running platform."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console import workbench_current_work as directory_module
from agent_console.workbench_current_work import CurrentWorkDirectory
from agent_console.workbench_current_work_attribution import requester
from agent_console.workbench_current_work_projection import project_runs
from agent_console.workbench_current_work_query import CurrentWorkQuery
from agent_console.workbench_pagination import WorkbenchCursorCodec
from test_current_work_projection import setup


def bound(row):
    row = deepcopy(row)
    row["initiators"] = ["human:operator"]
    row["attribution_sources"] = [
        {
            "contextId": "context:one",
            "subjectId": "human:alice",
            "recordSubjectId": "human:alice",
            "recordContextId": "context:one",
            "conversationId": "original",
            "conversationOwnerId": "human:alice",
            "conversationSchema": 1,
            "messageAuthorId": "human:alice",
            "messageSchema": 1,
            "messageIsUser": True,
            "messagePredatesRun": True,
            "invocation": {
                "contextId": "context:one",
                "state": "SUCCEEDED",
                "resultKind": "DRAFT_READY",
                "initiatingPrincipalId": "human:alice",
                "problemId": row["business_problem_id"],
                "problemRevisionId": row["problem_revision_id"],
                "problemDigest": row["problem_digest"],
            },
        }
    ]
    return row


def test_original_question_author_is_distinct_from_start_operator_and_journey(
    monkeypatch,
):
    call, raw = setup(monkeypatch)
    row = bound(raw)
    # The mutable journal now points elsewhere; immutable lineage remains usable.
    row["origins"] = []
    item = project_runs(call, [row], verified_administrator=False)[0]
    assert item.requestedById == "human:alice"
    assert item.attributionKind == "VERIFIED_REQUESTER"
    assert item.initiatorId == "human:operator"
    assert item.startedByIds == ["human:operator"]
    assert item.originConversationId is None
    row["initiators"] += ["human:other-operator"]
    item = project_runs(call, [row], verified_administrator=False)[0]
    assert item.requestedById == "human:alice" and item.initiatorId is None
    assert len(item.startedByIds) == 2


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("source", "subjectId", None),
        ("source", "recordSubjectId", "human:other"),
        ("source", "recordContextId", "wrong-context"),
        ("source", "conversationId", None),
        ("source", "conversationOwnerId", "human:operator"),
        ("source", "conversationSchema", 2),
        ("source", "messageAuthorId", "human:operator"),
        ("source", "messageSchema", 2),
        ("source", "messageIsUser", False),
        ("source", "messagePredatesRun", False),
        ("invocation", "contextId", "wrong-context"),
        ("invocation", "initiatingPrincipalId", "human:operator"),
        ("invocation", "state", "FAILED"),
        ("invocation", "resultKind", "DIRECT_ANSWER"),
        ("invocation", "problemId", "another-task"),
        ("invocation", "problemRevisionId", "newer-revision"),
        ("invocation", "problemDigest", "wrong-digest"),
    ],
)
def test_invalid_binding_never_falls_back_to_start_actor(
    monkeypatch, section, key, value
):
    call, raw = setup(monkeypatch)
    row = bound(raw)
    target = row["attribution_sources"][0]
    if section == "invocation":
        target = target["invocation"]
    target[key] = value
    item = project_runs(call, [row], verified_administrator=True)[0]
    assert item.requestedById is None and item.attributionKind == "UNVERIFIED"
    assert item.startedByIds == ["human:operator"]


def test_private_sources_and_ambiguous_origins_do_not_leak_requester(monkeypatch):
    _, raw = setup(monkeypatch)
    row = bound(raw)
    assert requester(row, "human:other", administrator=False).requested_by is None
    assert (
        requester(row, "human:other", administrator=True).requested_by == "human:alice"
    )
    row["attribution_sources"] *= 2
    assert requester(row, "human:alice", administrator=True).kind == "UNVERIFIED"
    row["attribution_sources"] = []
    assert requester(row, "human:alice", administrator=True).kind == "UNVERIFIED"
    row["origins"] = []
    assert requester(row, "human:alice", administrator=True).kind == "DIRECT_START"


def test_preselection_totals_and_pages_share_requester_and_direct_start_rules(
    monkeypatch,
):
    call, raw = setup(monkeypatch)
    # Include a delegated task, a direct-start legacy task and a damaged binding.
    delegated = bound(raw)
    legacy = deepcopy(raw)
    legacy["origins"] = []
    broken = bound(raw)
    broken["attribution_sources"][0]["messageAuthorId"] = "human:someone-else"
    broken["initiators"] = ["human:alice"]
    # Distinct fixed run identities without changing canonical preparations.
    from agent_console.workbench_current_work_page import directory_page
    from test_current_work_page import CODEC, NOW, item

    records = []
    for i, row in enumerate([delegated, legacy, broken]):
        attribution = requester(row, "human:alice", administrator=False)
        row["workflow_run_id"] = f"run:{i}"
        records.append(
            item(f"run:{i}").model_copy(
                update={
                    "requestedById": attribution.requested_by,
                    "attributionKind": attribution.kind,
                    "initiatorId": row["initiators"][0],
                    "startedByIds": row["initiators"],
                }
            )
        )
    rows = [delegated, legacy, broken]
    selected_ids = []
    monkeypatch.setattr(directory_module, "for_call", lambda call: False)
    monkeypatch.setattr(
        directory_module, "read_current_work_snapshot", lambda *a, **kw: rows
    )
    monkeypatch.setattr(directory_module, "readable_runs", lambda call, rows: rows)

    def projection(call, selected, **kwargs):
        selected_ids.append([r["workflow_run_id"] for r in selected])
        return [r for r in records if r.workflowRunId in selected_ids[-1]]

    monkeypatch.setattr(directory_module, "project_runs", projection)
    call = SimpleNamespace(
        context=call.context,
        connection=None,
        query={"scopeFilter": "initiated", "pageSize": 1},
        policy_generation=1,
        recovery_epoch=1,
    )
    directory = CurrentWorkDirectory(CODEC)
    first = directory(call)
    assert first["total"] == sum(first["counts"].values()) == 2
    assert selected_ids[0] == ["run:0", "run:1"]
    assert first["items"][0]["workflowRunId"] == "run:1"
    call.query["cursor"] = first["nextCursor"]
    second = directory(call)
    assert second["total"] == 2 and second["nextCursor"] is None
    assert second["items"][0]["workflowRunId"] == "run:0"
    visible = directory_page(
        records,
        CurrentWorkQuery(scopeFilter="visible"),
        CODEC,
        call.context,
        generation=1,
        recovery_epoch=1,
        read_at=NOW,
    )
    assert visible["total"] == 3  # damaged provenance does not hide authorized work


def test_old_cursor_scope_cannot_be_reused(monkeypatch):
    from agent_console.resource_use_domain import canonical_digest
    from agent_console.workbench_owner_authorization import WorkbenchOwnerError

    call, _ = setup(monkeypatch)
    codec = WorkbenchCursorCodec(b"k" * 32)
    query = CurrentWorkQuery(scopeFilter="initiated")
    old_route = "current-work:" + canonical_digest(
        [
            call.context.principal_id,
            1,
            1,
            "initiated",
            "",
            "all",
        ]
    )
    token = codec.mint(
        route=old_route,
        context=call.context,
        page_size=25,
        last_key=("2026-11-10T00:00:00+00:00", "run:old"),
    )
    assert query.cursor_route(call.context, generation=1, recovery_epoch=1) != old_route
    with pytest.raises(WorkbenchOwnerError):
        query.model_copy(update={"cursor": token}).after(
            codec, call.context, generation=1, recovery_epoch=1
        )


def test_unreadable_runs_are_removed_before_requester_projection(monkeypatch):
    call, raw = setup(monkeypatch)
    monkeypatch.setattr(directory_module, "for_call", lambda call: False)
    monkeypatch.setattr(
        directory_module, "read_current_work_snapshot", lambda *a, **kw: [raw]
    )
    monkeypatch.setattr(directory_module, "readable_runs", lambda call, rows: [])

    def forbidden(*args, **kwargs):
        raise AssertionError("unreadable run reached attribution")

    monkeypatch.setattr(directory_module, "requester", forbidden)
    call = SimpleNamespace(
        context=call.context,
        connection=None,
        query={},
        policy_generation=1,
        recovery_epoch=1,
    )
    result = CurrentWorkDirectory(WorkbenchCursorCodec(b"k" * 32))(call)
    assert result["items"] == [] and result["total"] == 0
