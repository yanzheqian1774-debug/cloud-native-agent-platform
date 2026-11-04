# ruff: noqa: F401, F811 -- Exact isolated owner fixture dependencies.
"""Directory uses session scope and current per-version grants, never default tenant."""

import pytest
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec
from agent_console.workbench_resource_directory import ResourceDirectory
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def act(a, handler, query, *, context=None):
    context = context or a.subject
    with a.repository.pool.connection() as c, c.transaction():
        return handler(
            AuthorizedOwnerCall(
                "READ_RESOURCE_DIRECTORY",
                context,
                c,
                {},
                {},
                query,
                (),
                AuthorizedOwnerAuthority(a.adapter, context, c, 1, ()),
                1,
                1,
            )
        )


def test_directory_filters_unreadable_inputs_and_paginates_only_readable_exact_versions(
    automation,
):
    a = automation
    handler = ResourceDirectory(
        {**a.services, "mcp": a.services["skill"]}, WorkbenchCursorCodec(b"x" * 32)
    )
    assert act(a, handler, {})["items"] == []
    assert a.run()["state"] == "READY"
    items, cursor = [], None
    for _ in range(4):
        page = act(
            a, handler, {"pageSize": 2, **({"cursor": cursor} if cursor else {})}
        )
        items += page["items"]
        cursor = page["nextCursor"]
        if not cursor:
            break
    assert len(items) == 4
    assert {v["kind"] for v in items} == {"skill", "agent", "knowledge", "runtime"}
    assert all(v["isCurrentPublished"] and not v["executionReady"] for v in items)
    assert {v["identity"] for v in items} == {r.resource_id for r in a.refs.values()}
    assert page["scope"] == {
        "tenantId": a.e.scope.namespace,
        "securityDomain": a.e.scope.security_domain,
    }
    assert act(a, handler, {"kind": "mcp"})["items"] == []
    assert act(a, handler, {"query": "unreadable-other-name"})["items"] == []


def test_directory_cursor_cannot_cross_filters_or_subject_and_get_has_no_new_work(
    automation,
):
    from dataclasses import replace

    a = automation
    a.run()
    handler = ResourceDirectory(a.services, WorkbenchCursorCodec(b"x" * 32))
    first = act(a, handler, {"pageSize": 1})
    assert first["nextCursor"]
    with pytest.raises(WorkbenchOwnerError):
        act(a, handler, {"pageSize": 1, "cursor": first["nextCursor"], "kind": "skill"})
    with pytest.raises(WorkbenchOwnerError):
        act(
            a,
            handler,
            {"pageSize": 1, "cursor": first["nextCursor"]},
            context=replace(a.subject, principal_id="different-user"),
        )
    for _ in range(3):
        act(a, handler, {})
    with a.repository.pool.connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.resource_automation"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            == 0
        )
