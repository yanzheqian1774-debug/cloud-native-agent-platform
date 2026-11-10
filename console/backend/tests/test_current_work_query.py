from dataclasses import replace

import pytest
from agent_console.workbench_current_work_query import CurrentWorkQuery
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_pagination import WorkbenchCursorCodec
from pydantic import ValidationError
from test_workbench_pagination import context


@pytest.mark.parametrize(
    "values",
    [
        {"pageSize": 0},
        {"pageSize": 101},
        {"query": "x" * 201},
        {"state": "invented"},
        {"scopeFilter": "all-users"},
        {"cursor": ""},
        {"cursor": "x" * 2049},
        {"administrator": True},
    ],
)
def test_invalid_directory_parameters_are_rejected(values):
    with pytest.raises(ValidationError):
        CurrentWorkQuery.model_validate(values)


def test_verified_role_only_sets_default_and_retains_explicit_selection():
    for admin, default in [(True, "visible"), (False, "initiated")]:
        assert (
            CurrentWorkQuery()
            .resolved(verified_development_administrator=admin)
            .scopeFilter
            == default
        )
        for explicit in ["visible", "initiated"]:
            assert (
                CurrentWorkQuery(scopeFilter=explicit)
                .resolved(verified_development_administrator=admin)
                .scopeFilter
                == explicit
            )
    with pytest.raises(ValueError, match="CURRENT_WORK_SCOPE_UNRESOLVED"):
        CurrentWorkQuery().cursor_route(context(), generation=1, recovery_epoch=1)


def test_cursor_requires_same_principal_filters_generation_and_page_size():
    codec = WorkbenchCursorCodec(b"q" * 32)
    query = CurrentWorkQuery(scopeFilter="visible", query="交接")
    token = query.next_cursor(
        codec,
        context(),
        generation=1,
        recovery_epoch=1,
        created_at="2026-11-10T01:00:00+00:00",
        workflow_run_id="workflow-run:one",
    )
    page = query.model_copy(update={"cursor": token})
    assert page.after(codec, context(), generation=1, recovery_epoch=1) == (
        "2026-11-10T01:00:00+00:00",
        "workflow-run:one",
    )
    cases = [
        (page, replace(context(), principal_id="human:bob"), 1, 1),
        (page, context("tenant-b"), 1, 1),
        (page, context(), 2, 1),
        (page, context(), 1, 2),
    ]
    for change in [
        {"scopeFilter": "initiated"},
        {"query": "销售"},
        {"state": "completed"},
        {"pageSize": 50},
        {"cursor": token[:-1] + ("0" if token[-1] != "0" else "1")},
    ]:
        cases.append((page.model_copy(update=change), context(), 1, 1))
    for changed, ctx, generation, epoch in cases:
        with pytest.raises(WorkbenchOwnerError, match="REQUEST_INVALID"):
            changed.after(codec, ctx, generation=generation, recovery_epoch=epoch)
