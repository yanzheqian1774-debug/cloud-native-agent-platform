from datetime import UTC, datetime
from types import SimpleNamespace

from agent_console import workbench_current_work as module
from agent_console.workbench_current_work import CurrentWorkDirectory
from agent_console.workbench_pagination import WorkbenchCursorCodec
from test_current_work_page import item
from test_workbench_pagination import context


def test_only_returned_page_gets_outcome_verification_and_counts_stay_global(
    monkeypatch,
):
    rows = [
        {
            "workflow_run_id": f"run:{i:02}",
            "title": "交接",
            "initiators": ["human:alice"],
            "read_at": datetime.now(UTC),
        }
        for i in range(4)
    ]
    checks = []
    monkeypatch.setattr(module, "for_call", lambda call: True)
    monkeypatch.setattr(module, "read_current_work_snapshot", lambda *a, **kw: rows)
    monkeypatch.setattr(module, "readable_runs", lambda call, rows: rows)

    def project(call, selected, *, verified_administrator, include_outcomes=True):
        checks.append((include_outcomes, [r["workflow_run_id"] for r in selected]))
        return [
            item(r["workflow_run_id"]).model_copy(
                update={
                    "businessResolution": "UNDETERMINED" if include_outcomes else None,
                    "outcomeVersion": 1 if include_outcomes else None,
                }
            )
            for r in selected
        ]

    monkeypatch.setattr(module, "project_runs", project)
    call = SimpleNamespace(
        context=context(),
        connection=None,
        query={"scopeFilter": "visible", "pageSize": 2},
        policy_generation=1,
        recovery_epoch=1,
    )
    directory = CurrentWorkDirectory(WorkbenchCursorCodec(b"k" * 32))
    first = directory(call)
    assert first["total"] == first["counts"]["completed"] == 4
    assert checks == [
        (False, ["run:00", "run:01", "run:02", "run:03"]),
        (True, ["run:02", "run:03"]),
    ]
    assert all(r["businessResolution"] == "UNDETERMINED" for r in first["items"])
    checks.clear()
    call.query = {**call.query, "cursor": first["nextCursor"]}
    second = directory(call)
    assert second["total"] == 4
    assert checks[-1] == (True, ["run:00", "run:01"])
    assert second["nextCursor"] is None

    checks.clear()
    call.query = {"scopeFilter": "visible", "pageSize": 100}
    whole = directory(call)
    assert whole["total"] == len(whole["items"]) == 4
    assert checks == [(True, ["run:00", "run:01", "run:02", "run:03"])]
