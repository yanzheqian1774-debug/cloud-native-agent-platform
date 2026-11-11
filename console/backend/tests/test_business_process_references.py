"""Reference validation preserves scope, fixed versions and read authority."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.business_process_definition import BusinessProcessContent
from agent_console.workbench_business_process_references import (
    BusinessProcessReferences,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from test_business_process_definition import content


def setup_reference(kind):
    record = content().model_dump()
    reference = {
        "resource_id": f"{kind}:fixed",
        "revision_id": f"{kind}-revision:old",
        "digest": "a" * 64,
    }
    if kind == "knowledge":
        record["source_materials"] = [reference]
    else:
        record["activities"][0]["employee"] = reference
    value = BusinessProcessContent.model_validate(record)
    context = SimpleNamespace(
        principal_id="human:reader",
        scope=SimpleNamespace(tenant_id="tenant:one", security_domain="domain:one"),
    )
    call = AuthorizedOwnerCall(
        "SAVE_BUSINESS_PROCESS", context, object(), {}, {}, {}, (), Mock()
    )
    employees = Mock()
    employees.read_revision_for_workbench.return_value = {"digest": "a" * 64}
    reader = BusinessProcessReferences(employees, {"knowledge": object()})
    reader.resources = Mock(return_value={"revision": {"digest": "a" * 64}})
    return reader, call, value


@pytest.mark.parametrize("kind", ["employee", "knowledge"])
def test_reference_keeps_fixed_revision_and_current_scope(kind):
    reader, call, value = setup_reference(kind)
    reader.validate(call, value)
    principal = call.authority.require.call_args.args[0]
    assert principal.principal_id == "human:reader"
    assert call.authority.require.call_count == 1
    if kind == "employee":
        assert call.authority.require.call_args.args[1:] == (
            "EMPLOYEE",
            "READ",
            "employee:employee:fixed:employee-revision:old",
        )
        args = reader.employees.read_revision_for_workbench.call_args
        assert args.args[0] is call.connection
        assert args.args[1].namespace == "tenant:one"
        assert args.args[1].security_domain == "domain:one"
        assert args.args[2:] == ("employee:fixed", "employee-revision:old")
        assert args.kwargs == {"authorized": True}
    else:
        assert call.authority.require.call_args.args[1:] == (
            "KNOWLEDGE",
            "READ_RESOURCE",
            "knowledge:prepared-resource:knowledge:fixed:knowledge-revision:old",
        )
        request = reader.resources.call_args.args[0]
        assert request.context is call.context
        assert request.connection is call.connection
        assert request.path == {
            "kind": "knowledge",
            "identity": "knowledge:fixed",
            "revision": "knowledge-revision:old",
        }
    assert value.activities[0].responsible_role == "业务专员"


@pytest.mark.parametrize("kind", ["employee", "knowledge"])
def test_denial_prevents_owner_read(kind):
    reader, call, value = setup_reference(kind)
    call.authority.require.side_effect = AuthorityError("AUTHORIZATION_NOT_FOUND")
    with pytest.raises(
        WorkbenchOwnerError, match="BUSINESS_PROCESS_REFERENCE_NOT_FOUND"
    ):
        reader.validate(call, value)
    reader.resources.assert_not_called()
    reader.employees.read_revision_for_workbench.assert_not_called()


@pytest.mark.parametrize("kind", ["employee", "knowledge"])
def test_digest_mismatch_cannot_rebind_reference(kind):
    reader, call, value = setup_reference(kind)
    reader.resources.return_value = {"revision": {"digest": "b" * 64}}
    reader.employees.read_revision_for_workbench.return_value = {"digest": "b" * 64}
    with pytest.raises(
        WorkbenchOwnerError, match="BUSINESS_PROCESS_REFERENCE_VERSION_MISMATCH"
    ):
        reader.validate(call, value)


@pytest.mark.parametrize("kind", ["employee", "knowledge"])
def test_missing_adapter_rejects_references_but_not_unlinked_content(kind):
    _, call, value = setup_reference(kind)
    reader = BusinessProcessReferences()
    reader.validate(call, content())
    with pytest.raises(
        WorkbenchOwnerError, match="BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE"
    ):
        reader.validate(call, value)


@pytest.mark.parametrize("kind", ["employee", "knowledge"])
@pytest.mark.parametrize("state", ["DRAFT", "PUBLISHED"])
def test_publication_requires_fixed_reference_publication(kind, state):
    reader, call, value = setup_reference(kind)
    from dataclasses import replace

    connection = Mock()
    connection.execute.return_value.fetchone.return_value = {
        "record": {"enabled": True}
    }
    call = replace(call, connection=connection)
    reader.resources.return_value = {"revision": {"digest": "a" * 64, "state": state}}
    reader.employees.read_revision_for_workbench.return_value = {
        "digest": "a" * 64,
        "publicationState": state,
    }
    if state == "PUBLISHED":
        reader.validate(call, value, require_published=True)
    else:
        with pytest.raises(
            WorkbenchOwnerError, match="BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED"
        ):
            reader.validate(call, value, require_published=True)
    if kind == "knowledge":
        assert "FOR SHARE" in connection.execute.call_args.args[0]
        assert connection.execute.call_args.args[1] == (
            "tenant:one",
            "domain:one",
            "knowledge:fixed",
        )


@pytest.mark.parametrize(
    "record", [None, {"record": {"enabled": False}}, {"record": {"archived": True}}]
)
def test_publication_rejects_unavailable_knowledge_before_read(record):
    reader, call, value = setup_reference("knowledge")
    from dataclasses import replace

    connection = Mock()
    connection.execute.return_value.fetchone.return_value = record
    with pytest.raises(
        WorkbenchOwnerError, match="BUSINESS_PROCESS_REFERENCE_UNAVAILABLE"
    ):
        reader.validate(
            replace(call, connection=connection), value, require_published=True
        )
    reader.resources.assert_not_called()


def test_projection_deduplicates_and_hides_only_unreadable_reference_names():
    reader, call, employee_content = setup_reference("employee")
    _, _, source_content = setup_reference("knowledge")
    record = employee_content.model_dump(mode="json")
    record["source_materials"] = source_content.model_dump(mode="json")[
        "source_materials"
    ]
    record["activities"][1]["employee"] = record["activities"][0]["employee"]
    value = BusinessProcessContent.model_validate(record)
    reader.employees.read_revision_for_workbench.return_value = {
        "digest": "a" * 64,
        "revision": {"role": "文档助手"},
    }

    def authorize(principal, owner, action, resource):
        if owner == "KNOWLEDGE":
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    call.authority.require.side_effect = authorize
    result = reader.describe(call, value)
    assert result["executionAuthorized"] is False
    assert len(result["items"]) == 2
    assert result["items"][0]["status"] == "UNAVAILABLE"
    assert "name" not in result["items"][0]
    assert result["items"][1]["name"] == "文档助手"
    reader.resources.assert_not_called()
    assert reader.employees.read_revision_for_workbench.call_count == 1
    assert value.model_dump(mode="json") == record
