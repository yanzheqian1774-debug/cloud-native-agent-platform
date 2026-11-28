"""New narrow actual-source → validation → independent publication checks."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.digital_employee_definition import MemberKind
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from agent_console.workbench_tool_definitions import tool_definition_operations
from test_tool_source_execution import (
    OTHER_CODE,
    package,
    result,
)
from test_tool_source_execution import (
    owner as owner,
)
from test_tool_source_execution import (
    rig as rig,
)


def operation(rig, name, *, payload=None, current=None, testing=None):
    current = current or rig.current
    routes = tool_definition_operations(
        rig.owner, None, source_testing=testing or rig.testing
    )
    route = next(o for o in routes if o.name == name)
    with rig.owner.pool.connection() as c, c.transaction():
        call = NS(
            operation=name,
            context=rig.context,
            connection=c,
            authority=rig.authority,
            payload=payload or {},
            path={"tool_id": current["toolId"]},
            query={"revision": current["revisionId"]},
        )
        return route.handler(call)


def lifecycle(rig, action, *, current=None, testing=None, key=None):
    current = current or rig.current
    return operation(
        rig,
        "TOOL_LIFECYCLE_COMMAND",
        current=current,
        testing=testing,
        payload={
            "action": action,
            "commandId": key or action + ":source",
            "expectedVersion": current["aggregateVersion"],
            "revisionId": current["revisionId"],
            "digest": current["digest"],
        },
    )


def test_real_source_contract_not_expected_enables_validate_publish_exact_candidate(
    rig,
):
    observed = result(rig.run(expected={"total": 999, "count": 2}))
    assert observed["status"] == "FAILED" and observed["actual"]["total"] == 5
    validated = lifecycle(rig, "validate")
    assert validated["validation"]["resolvedIssues"] == [
        "PLUGIN_RUNTIME_VALIDATION_REQUIRED"
    ]
    assert validated["validation"]["sourceExecutionVerified"] is True
    published = lifecycle(rig, "publish")
    assert published["items"][0]["revisionId"] == rig.current["revisionId"]
    read = operation(rig, "READ_TOOL_DRAFT")
    assert read["effectiveBlockingIssues"] == []
    assert read["record"]["operation"]["blockingIssues"] == [
        "PLUGIN_RUNTIME_VALIDATION_REQUIRED"
    ]
    assert read["sourceValidation"]["executionAuthorized"] is False
    candidates = operation(rig, "TOOL_EMPLOYEE_CANDIDATES")
    assert candidates["items"][0]["digest"] == rig.current["digest"]
    # Exercise the actual existing Tool member eligibility consumer; no relaxation.
    member = NS(
        kind=MemberKind.TOOL,
        resource_id=rig.current["toolId"],
        revision_id=rig.current["revisionId"],
        digest=rig.current["digest"],
    )
    with rig.owner.pool.connection() as c:
        PostgresEmployeeDefinitionRepository.validate_members(
            c, NS(scope=rig.scope, members=[member])
        )
    assert len(rig.calls) == 1


def test_without_exact_real_execution_runtime_blocker_remains(rig):
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(rig, "validate")
    assert not rig.calls


def test_unknown_claim_cannot_validate_even_if_user_expected_matches(rig):
    rig.mode[0] = "lost"
    assert result(rig.run())["status"] == "UNKNOWN"
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(rig, "validate")
    assert len(rig.calls) == 1


@pytest.mark.parametrize(
    "field",
    [
        "runtimeRevision",
        "entrypointDigest",
        "digest",
        "sourceDigest",
        "subject",
        "expiresAt",
    ],
)
def test_current_binding_change_cannot_reuse_old_actual(rig, field):
    rig.run()
    changes = {field: "0" * 64}
    if field == "runtimeRevision":
        changes[field] = "registered-2"
    elif field == "subject":
        changes[field] = "human:other"
    elif field == "expiresAt":
        changes[field] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    newtest = rig.policy(**changes)
    with pytest.raises(WorkbenchOwnerError, match="TOOL_SOURCE_RUNTIME"):
        lifecycle(rig, "validate", testing=newtest)
    assert len(rig.calls) == 1


def test_changed_source_new_binding_without_new_execution_cannot_inherit_validation(
    rig,
):
    rig.run()
    lifecycle(rig, "validate")
    new = rig.install(package(OTHER_CODE), {"sum": 1})
    newtest = rig.policy(new, OTHER_CODE)
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(
            rig, "validate", current=new, testing=newtest, key="validate:new-source"
        )
    with pytest.raises(WorkbenchOwnerError):
        lifecycle(
            rig, "publish", current=new, testing=newtest, key="publish:new-source"
        )
    assert len(rig.calls) == 1


@pytest.mark.parametrize("action", ["READ", "TEST", "VALIDATE"])
def test_current_own_tool_permission_required_for_validation(rig, action):
    rig.run()
    rig.authority.denied.add(action)
    with pytest.raises((WorkbenchOwnerError, AuthorityError)):
        lifecycle(rig, "validate")
    assert len(rig.calls) == 1


def test_test_permission_never_grants_publish_and_revocation_after_validate_rechecked(
    rig,
):
    rig.run()
    lifecycle(rig, "validate")
    rig.authority.denied.add("PUBLISH")
    with pytest.raises(AuthorityError):
        lifecycle(rig, "publish")
    rig.authority.denied = {"TEST"}
    with pytest.raises(WorkbenchOwnerError, match="VALIDATION_UNAVAILABLE"):
        lifecycle(rig, "publish")
    assert len(rig.calls) == 1


def test_real_execution_without_prior_validate_cannot_publish(rig):
    rig.run()
    with pytest.raises(WorkbenchOwnerError, match="TOOL_VALIDATION_REQUIRED"):
        lifecycle(rig, "publish")
    assert len(rig.calls) == 1


def test_other_source_blocker_is_not_resolved_by_any_runtime_evidence():
    from agent_console.tool_definition_postgres import ToolStorageError
    from agent_console.tool_lifecycle import validate_contract

    record = {
        "operation": {
            "blockingIssues": [
                "REFERENCE_ADAPTER_REQUIRED",
                "PLUGIN_RUNTIME_VALIDATION_REQUIRED",
            ]
        }
    }
    with pytest.raises(ToolStorageError, match="UNSUPPORTED_SOURCE"):
        validate_contract(record, {"sourceDigest": "test-only-proof"})


def test_passed_flag_without_exact_source_execution_evidence_never_resolves(rig):
    # Synthetic negative: append an owner's malformed fact; browser cannot write facts.
    saved = {
        "toolId": rig.current["toolId"],
        "revisionId": rig.current["revisionId"],
        "digest": rig.current["digest"],
        "sourceDigest": rig.current["sourceDigest"],
        "command": {
            "action": "test",
            "revisionId": rig.current["revisionId"],
            "digest": rig.current["digest"],
            "input": {"values": [2, 3]},
        },
    }
    rig.journal.claim(rig.context, "fake-passed", "synthetic-negative", saved, 20)
    rig.journal.finish(
        rig.context,
        "fake-passed",
        {
            "status": "PASSED",
            "actualExecution": True,
            "toolSourceInvoked": True,
            "verificationLevel": "ISOLATED_EXACT_TOOL_SOURCE_EXECUTION",
            "actual": {"total": 5, "count": 2},
        },
    )
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(rig, "validate")
    assert not rig.calls


def test_saved_edit_same_source_new_revision_needs_its_own_actual(rig):
    rig.run()
    with rig.owner.pool.connection() as c, c.transaction():
        rig.owner.revise_draft(
            c,
            rig.scope,
            rig.current["toolId"],
            {
                "name": "edited",
                "purpose": "changed definition",
                "inputSchema": rig.current["record"]["operation"]["inputSchema"],
                "outputSchema": rig.current["record"]["operation"]["outputSchema"],
                "sideEffect": "read-only",
            },
            expected_version=1,
            command_id="edit:same-source",
            actor_id=rig.context.principal_id,
            decision_id="decision:synthetic",
        )
        newer = rig.owner.read(c, rig.scope, rig.current["toolId"])
    assert newer["sourceDigest"] == rig.current["sourceDigest"]
    test = rig.policy(newer)
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(rig, "validate", current=newer, testing=test)
    assert len(rig.calls) == 1


def test_publish_rechecks_current_runtime_after_earlier_exact_validation(rig):
    rig.run()
    lifecycle(rig, "validate")
    changed = rig.policy(runtimeRevision="registered-2")
    with pytest.raises(WorkbenchOwnerError, match="EVIDENCE_REQUIRED"):
        lifecycle(rig, "publish", testing=changed)
    assert len(rig.calls) == 1
