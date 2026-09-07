from dataclasses import replace

import pytest
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
)
from agent_console.execution_domain import ScopeIdentity


def revision():
    return EmployeeRevision(
        ScopeIdentity("scope", "domain"),
        "employee-definition",
        "employee-revision",
        "Analyst",
        ("Analyze quality",),
        (CompositionMember(MemberKind.AGENT, "agent", "agent-revision", "a" * 64),),
    )


def test_cardinality_and_canonical_composition():
    value = revision()
    knowledge = CompositionMember(
        MemberKind.KNOWLEDGE, "knowledge", "k-revision", "b" * 64
    )
    assert (
        replace(value, members=(*value.members, knowledge)).digest
        == replace(value, members=(knowledge, *value.members)).digest
    )
    with pytest.raises(EmployeeDefinitionError, match="PRIMARY_AGENT_CARDINALITY"):
        replace(value, members=(knowledge,))
    with pytest.raises(EmployeeDefinitionError, match="PRIMARY_AGENT_CARDINALITY"):
        replace(
            value,
            members=(*value.members, replace(value.members[0], resource_id="agent2")),
        )
    runtime = CompositionMember(
        MemberKind.RUNTIME_PROFILE, "profile", "profile-v1", "c" * 64
    )
    with pytest.raises(EmployeeDefinitionError, match="DEFAULT_RUNTIME_CARDINALITY"):
        replace(
            value,
            members=(*value.members, runtime, replace(runtime, resource_id="profile2")),
        )
    with pytest.raises(EmployeeDefinitionError, match="UNSUPPORTED_DIRECT_MEMBER"):
        CompositionMember("MODEL", "model", "model-v1", "d" * 64)
    assert (
        value.digest
        != replace(
            value, revision_id="successor", predecessor_revision_id=value.revision_id
        ).digest
    )


def test_denial_precedes_every_repository_operation():
    class Deny:
        def require(self, *args):
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")

    class Never:
        def __getattr__(self, name):
            pytest.fail(f"Unauthorized repository call: {name}")

    service = EmployeeDefinitionService(Never(), Deny())
    value = revision()
    for operation in (
        lambda: service.create(value, expected_version=0, command_id="create"),
        lambda: service.read(value.scope, value.definition_id, value.revision_id),
        lambda: service.list(value.scope),
        lambda: service.decide(
            value.scope,
            value.definition_id,
            value.revision_id,
            value.digest,
            "PUBLISH",
            expected_version=1,
            command_id="publish",
        ),
    ):
        with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
            operation()
