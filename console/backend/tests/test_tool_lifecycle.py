# ruff: noqa: F401,F811 -- Existing isolated PostgreSQL fixtures.
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import test_workbench_authorization_postgres as authority_fixture
from agent_console.execution_domain import ScopeIdentity
from agent_console.tool_definition_postgres import ToolStorageError
from agent_console.tool_lifecycle import ToolCommand, command, history
from test_tool_definition_postgres import owner, read, save
from test_workbench_authorization_postgres import repository as authority_repository


@pytest.fixture
def repository(monkeypatch):
    # Imported fixtures do not inherit their original module's environment wiring.
    # Reuse an explicitly configured release test pool; never a default socket.
    url = (
        authority_fixture.DATABASE_URL
        or os.environ.get("TOOL_DEFINITION_TEST_DATABASE_URL")
        or os.environ.get("AUTHORITY_I1_TEST_DATABASE_URL")
    )
    monkeypatch.setattr(authority_fixture, "DATABASE_URL", url)
    yield from authority_repository.__wrapped__()


def action(owner, scope, tool, kind, key, **values):
    current = read(owner, scope, tool)
    body = dict(
        action=kind,
        commandId=key,
        expectedVersion=current["aggregateVersion"],
        revisionId=current["revisionId"],
        digest=current["digest"],
        **values,
    )
    with owner.pool.connection() as c, c.transaction():
        return command(
            owner,
            c,
            scope,
            tool,
            ToolCommand(**body),
            actor_id="human:test",
            decision_id="decision:test",
        )


def create(owner, domain):
    scope = ScopeIdentity("tools", domain)
    tool = save(owner, scope, effects={"orders": "read-only"})["items"][0]["toolId"]
    return scope, tool, read(owner, scope, tool)


def test_publish_successor_edit_preserves_immutable_history(owner):
    scope, tool, old = create(owner, "lifecycle")
    with pytest.raises(ToolStorageError, match="VALIDATION_REQUIRED"):
        action(owner, scope, tool, "publish", "p:early")
    checked = action(owner, scope, tool, "validate", "v:one")
    assert checked["validation"]["executionVerified"] is False
    published = action(owner, scope, tool, "publish", "p:one")
    assert published["items"][0]["revisionId"] == old["revisionId"]
    with owner.pool.connection() as c, c.transaction():
        cmd = ToolCommand(
            action="publish",
            commandId="p:one",
            expectedVersion=1,
            revisionId=old["revisionId"],
            digest=old["digest"],
        )
        assert command(
            owner,
            c,
            scope,
            tool,
            cmd,
            actor_id="human:test",
            decision_id="decision:test",
        )["replayed"]
    new = action(owner, scope, tool, "successor", "s:one")["items"][0]
    assert new["revisionId"] != old["revisionId"]
    with owner.pool.connection() as c, c.transaction():
        owner.revise_draft(
            c,
            scope,
            tool,
            {
                "name": "changed",
                "purpose": "new",
                "sideEffect": "read-only",
                "inputSchema": {"type": "object"},
                "outputSchema": {"type": "object"},
            },
            expected_version=new["aggregateVersion"],
            command_id="e:one",
            actor_id="human:test",
            decision_id="decision:test",
        )
    with pytest.raises(ToolStorageError, match="VALIDATION_REQUIRED"):
        action(owner, scope, tool, "publish", "p:stale-check")
    assert read(owner, scope, tool, old["revisionId"])["record"] == old["record"]


def test_unmapped_api_test_never_copies_expected_to_actual(owner):
    scope, tool, _old = create(owner, "unmapped")
    result = action(
        owner,
        scope,
        tool,
        "test",
        "t:one",
        testName="invented",
        input={"region": "synthetic"},
        expectedOutput={"invented": "not actual"},
    )
    assert result["testResult"]["status"] == "NOT_EXECUTED"
    assert (
        result["testResult"]["actual"] is None
        and not result["testResult"]["actualExecution"]
    )
    assert result["testCase"]["expected"] == {"invented": "not actual"}
    with owner.pool.connection() as c:
        versions, receipts = history(owner, c, scope, tool)
    assert len(versions) == 1 and receipts[-1]["testResult"]["actual"] is None


def test_concurrent_publish_and_cross_scope_digest_guard(owner):
    scope, tool, old = create(owner, "race")
    action(owner, scope, tool, "validate", "v:race")

    def publish(n):
        try:
            with owner.pool.connection() as c, c.transaction():
                return command(
                    owner,
                    c,
                    scope,
                    tool,
                    ToolCommand(
                        action="publish",
                        commandId="race:" + str(n),
                        expectedVersion=1,
                        revisionId=old["revisionId"],
                        digest=old["digest"],
                    ),
                    actor_id="human:test",
                    decision_id="decision:test",
                )
        except ToolStorageError as e:
            return str(e)

    with ThreadPoolExecutor(max_workers=2) as pool:
        out = list(pool.map(publish, [1, 2]))
    assert sum(isinstance(x, dict) for x in out) == 1 and "TOOL_VERSION_CONFLICT" in out
    with pytest.raises(ToolStorageError):
        read(owner, ScopeIdentity("other", "race"), tool)
    with (
        owner.pool.connection() as c,
        c.transaction(),
        pytest.raises(ToolStorageError, match="EXACT_DIGEST"),
    ):
        command(
            owner,
            c,
            scope,
            tool,
            ToolCommand(
                action="validate",
                commandId="bad:digest",
                expectedVersion=2,
                revisionId=old["revisionId"],
                digest="0" * 64,
            ),
            actor_id="human:test",
            decision_id="decision:test",
        )


def test_employee_requires_published_exact_tool_preserves_old_binding(owner):
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeDefinitionError,
        MemberKind,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository as Employee,
    )

    scope, tool, old = create(owner, "member")
    member = CompositionMember(MemberKind.TOOL, tool, old["revisionId"], old["digest"])
    revision = SimpleNamespace(scope=scope, members=[member])
    with (
        owner.pool.connection() as c,
        pytest.raises(EmployeeDefinitionError, match="INELIGIBLE"),
    ):
        Employee.validate_members(c, revision)
    action(owner, scope, tool, "validate", "v:member")
    action(owner, scope, tool, "publish", "p:member")
    with owner.pool.connection() as c:
        Employee.validate_members(c, revision)
    action(owner, scope, tool, "successor", "s:member")
    with owner.pool.connection() as c:
        Employee.validate_members(c, revision)
    new = read(owner, scope, tool)
    revision.members = [
        CompositionMember(MemberKind.TOOL, tool, new["revisionId"], new["digest"])
    ]
    with (
        owner.pool.connection() as c,
        pytest.raises(EmployeeDefinitionError, match="INELIGIBLE"),
    ):
        Employee.validate_members(c, revision)

    # A later publication does not force an existing exact published reference
    # onto the new revision. The old immutable publication receipt remains proof.
    action(owner, scope, tool, "validate", "v:member-next")
    action(owner, scope, tool, "publish", "p:member-next")
    revision.members = [member]
    with (
        owner.pool.connection() as c,
        pytest.raises(EmployeeDefinitionError, match="INELIGIBLE"),
    ):
        Employee.validate_members(c, revision)
    assert read(owner, scope, tool, old["revisionId"])["digest"] == old["digest"]
