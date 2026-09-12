from dataclasses import replace

import pytest
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
    _same_sha256_digest,
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


@pytest.mark.parametrize(
    ("left", "right"),
    (
        ("a" * 64, "a" * 64),
        ("sha256:" + "a" * 64, "a" * 64),
        ("a" * 64, "sha256:" + "a" * 64),
    ),
)
def test_sha256_member_digest_encodings_are_strictly_equivalent(left, right):
    assert _same_sha256_digest(left, right)


@pytest.mark.parametrize(
    ("left", "right"),
    (
        ("a" * 64, "b" * 64),
        ("sha512:" + "a" * 64, "a" * 64),
        ("sha256:" + "a" * 63, "a" * 64),
        ("SHA256:" + "a" * 64, "a" * 64),
        ("sha256:" + "A" * 64, "a" * 64),
        ("sha256:sha256:" + "a" * 64, "a" * 64),
        (None, "a" * 64),
    ),
)
def test_sha256_member_digest_comparison_rejects_mismatch_and_malformed(left, right):
    assert not _same_sha256_digest(left, right)


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


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.row


class Connection:
    def __init__(self, row, facts=()):
        self.row = row
        self.facts = facts
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((statement, parameters))
        return Result(
            self.facts if "digital_employee_definition.facts" in statement else self.row
        )


def test_workbench_repository_read_is_exact_minimal_and_digest_checked() -> None:
    value = revision()
    connection = Connection(
        {"record": value.record, "digest": value.digest},
        (
            {
                "action": "CREATE",
                "revision_digest": value.digest,
                "ordinal": 1,
            },
        ),
    )

    result = PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
        connection,
        value.scope,
        value.definition_id,
        value.revision_id,
        authorized=True,
    )

    assert result == {
        "revision": value.record,
        "digest": value.digest,
        "publicationState": "NOT_PUBLISHED",
    }
    assert len(connection.calls) == 2
    statement, parameters = connection.calls[0]
    assert "digital_employee_definition.revisions" in statement
    assert "digital_employee_definition.facts" not in statement
    assert parameters == (
        value.scope.namespace,
        value.scope.security_domain,
        value.definition_id,
        value.revision_id,
    )
    assert "digital_employee_definition.facts" in connection.calls[1][0]

    corrupt = Connection({"record": value.record, "digest": "b" * 64})
    with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_RECORD_CORRUPT"):
        PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
            corrupt,
            value.scope,
            value.definition_id,
            value.revision_id,
            authorized=True,
        )


def test_workbench_repository_denies_before_query_and_bounds_missing_revision() -> None:
    value = revision()
    denied = Connection(None)
    with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
        PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
            denied,
            value.scope,
            value.definition_id,
            value.revision_id,
            authorized=False,
        )
    assert denied.calls == []

    missing = Connection(None)
    with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
        PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
            missing,
            value.scope,
            value.definition_id,
            "employee-revision:missing",
            authorized=True,
        )
    assert len(missing.calls) == 1

    wrong_scope = Connection(None)
    with pytest.raises(EmployeeDefinitionError, match="EMPLOYEE_NOT_FOUND"):
        PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
            wrong_scope,
            ScopeIdentity("other-tenant", "quality"),
            value.definition_id,
            value.revision_id,
            authorized=True,
        )
    assert wrong_scope.calls[0][1][:2] == ("other-tenant", "quality")
