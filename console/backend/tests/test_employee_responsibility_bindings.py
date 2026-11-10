from dataclasses import replace

import pytest
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeRevision,
    MemberKind,
    ResponsibilityBinding,
    digest,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.workbench_bff_schemas import WorkbenchCreateEmployeeDefinition


def fixture():
    return EmployeeRevision(
        ScopeIdentity("scope", "domain"),
        "employee",
        "revision",
        "Reviewer",
        ("Check rollback", "Check evidence"),
        (
            CompositionMember(MemberKind.AGENT, "agent", "a1", "a" * 64),
            CompositionMember(MemberKind.SKILL, "skill", "s1", "b" * 64),
            CompositionMember(MemberKind.KNOWLEDGE, "knowledge", "k1", "c" * 64),
        ),
    )


def test_old_records_and_digests_remain_exact():
    value = fixture()
    expected = {
        "schemaVersion": "digital-employee-composition.v1",
        "namespace": "scope",
        "securityDomain": "domain",
        "definitionId": "employee",
        "revisionId": "revision",
        "role": "Reviewer",
        "responsibilities": ("Check rollback", "Check evidence"),
        "members": [
            {
                "kind": "AGENT",
                "resource_id": "agent",
                "revision_id": "a1",
                "digest": "a" * 64,
            },
            {
                "kind": "KNOWLEDGE",
                "resource_id": "knowledge",
                "revision_id": "k1",
                "digest": "c" * 64,
            },
            {
                "kind": "SKILL",
                "resource_id": "skill",
                "revision_id": "s1",
                "digest": "b" * 64,
            },
        ],
        "predecessorRevisionId": None,
    }
    assert value.record == expected
    assert value.digest == digest(expected)
    assert EmployeeRevision.from_record(expected) == replace(
        value, members=(value.members[0], value.members[2], value.members[1])
    )


def test_associations_roundtrip_and_canonical_order():
    value = fixture()
    bindings = (
        ResponsibilityBinding(value.responsibilities[0], value.members[1]),
        ResponsibilityBinding(value.responsibilities[1], value.members[2]),
    )
    mapped = replace(value, responsibility_bindings=bindings)
    assert mapped.record["schemaVersion"] == "digital-employee-composition.v2"
    assert mapped.digest != value.digest
    assert EmployeeRevision.from_record(mapped.record).digest == mapped.digest
    assert (
        replace(mapped, responsibility_bindings=bindings[::-1]).digest == mapped.digest
    )
    assert replace(mapped, responsibility_bindings=bindings[:1]).digest != mapped.digest


@pytest.mark.parametrize(
    "failure",
    [
        "missing_duty",
        "duplicate_duty",
        "missing_resource",
        "changed_revision",
        "changed_digest",
        "internal_member",
        "duplicate_binding",
    ],
)
def test_invalid_associations_rejected(failure):
    value = fixture()
    member = value.members[1]
    duty = value.responsibilities[0]
    if failure == "missing_duty":
        duty = "Another duty"
    if failure == "duplicate_duty":
        value = replace(value, responsibilities=(duty, duty))
    if failure == "missing_resource":
        member = replace(member, resource_id="another")
    if failure == "changed_revision":
        member = replace(member, revision_id="s2")
    if failure == "changed_digest":
        member = replace(member, digest="d" * 64)
    if failure == "internal_member":
        member = value.members[0]
    bindings = (ResponsibilityBinding(duty, member),)
    if failure == "duplicate_binding":
        bindings *= 2
    with pytest.raises(
        EmployeeDefinitionError, match=r"INVALID_.*RESPONSIBILITY_BINDING"
    ):
        replace(value, responsibility_bindings=bindings)


@pytest.mark.parametrize("schema", ["unknown", "digital-employee-composition.v2"])
def test_unknown_or_empty_new_schema_rejected(schema):
    record = {**fixture().record, "schemaVersion": schema}
    with pytest.raises(
        EmployeeDefinitionError, match="INVALID_EMPLOYEE_COMPOSITION_SCHEMA"
    ):
        EmployeeRevision.from_record(record)


def test_old_schema_cannot_hide_binding_payload():
    record = {**fixture().record, "responsibilityBindings": []}
    with pytest.raises(
        EmployeeDefinitionError, match="INVALID_EMPLOYEE_COMPOSITION_SCHEMA"
    ):
        EmployeeRevision.from_record(record)


def test_wire_command_defaults_to_legacy_and_accepts_exact_binding():
    member = {
        "kind": "SKILL",
        "resourceId": "skill",
        "revisionId": "s1",
        "digest": "b" * 64,
    }
    command = dict(
        employeeDefinitionId="employee",
        employeeDefinitionRevisionId="revision",
        role="Reviewer",
        responsibilities=["Check rollback"],
        members=[member],
        expectedVersion=0,
        commandId="create",
    )
    assert WorkbenchCreateEmployeeDefinition(**command).responsibilityBindings is None
    parsed = WorkbenchCreateEmployeeDefinition(
        **command,
        responsibilityBindings=[{"responsibility": "Check rollback", "member": member}],
    )
    assert parsed.responsibilityBindings[0].member.revisionId == "s1"
