"""Owner reference validation; real storage/session coverage is separate."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_console import workbench_team_work as module
from agent_console.team_definition import TeamDefinitionError, TeamWorkReference


def link():
    return TeamWorkReference("run:1", "a" * 64, "problem:1", "revision:1", "b" * 64)


def row():
    return {
        "workflow_run_id": "run:1",
        "digest": "a" * 64,
        "business_problem_id": "problem:1",
        "problem_revision_id": "revision:1",
        "problem_digest": "b" * 64,
    }


def test_exact_grants_are_rechecked_on_each_save_attempt(monkeypatch):
    call = SimpleNamespace(authority=Mock())
    read = Mock(return_value=[row()])
    monkeypatch.setattr(module, "snapshot", read)
    for _ in range(2):
        module.validate_work_links(call, "principal", (link(),))
    assert call.authority.require.call_count == 4
    assert read.call_count == 2
    assert call.authority.require.call_args_list[0].args[1:] == (
        "EXECUTION",
        "READ",
        "governed-execution:prepared:" + "a" * 64,
    )


def test_revoked_authority_prevents_reference_read(monkeypatch):
    call = SimpleNamespace(authority=Mock())
    call.authority.require.side_effect = PermissionError("revoked")
    read = Mock()
    monkeypatch.setattr(module, "snapshot", read)
    with pytest.raises(PermissionError):
        module.validate_work_links(call, "principal", (link(),))
    read.assert_not_called()


@pytest.mark.parametrize(
    "field",
    [
        "workflow_run_id",
        "digest",
        "business_problem_id",
        "problem_revision_id",
        "problem_digest",
    ],
)
def test_any_changed_owner_coordinate_rejects_link(monkeypatch, field):
    call = SimpleNamespace(authority=Mock())
    monkeypatch.setattr(module, "snapshot", lambda _: [{**row(), field: "changed"}])
    with pytest.raises(TeamDefinitionError, match="TEAM_WORK_REFERENCE_UNAVAILABLE"):
        module.validate_work_links(call, "principal", (link(),))


def test_projection_does_not_infer_unlinked_work(monkeypatch):
    call = SimpleNamespace()
    monkeypatch.setattr(
        module,
        "snapshot",
        lambda _: [row(), {**row(), "workflow_run_id": "run:unlinked"}],
    )
    seen = []

    def authorized(_call, selected):
        seen.extend(selected)
        return []

    monkeypatch.setattr(module, "readable_runs", authorized)
    monkeypatch.setattr(module, "project_runs", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "for_call", lambda _: False)
    value = module.project_team_work(call, SimpleNamespace(work_links=(link(),)))
    assert seen == [row()]
    assert value == {"items": [], "linkedCount": 1, "unavailableCount": 1}
