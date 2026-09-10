from datetime import UTC, datetime, timedelta

import pytest
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
    DefinitionReference,
    DigitalEmployeeApplicationService,
    DigitalEmployeeError,
    InstanceLifecycle,
    InstanceRecord,
)
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.execution_postgres import (
    AppendDisposition,
    AssignmentId,
    DigitalEmployeeInstanceId,
    ScopeIdentity,
)

NOW = datetime(2026, 9, 3, tzinfo=UTC)
SCOPE = ScopeIdentity("tenant-a", "domain-a")


class Definitions:
    value = DefinitionReference("definition", "revision-1", "d" * 64, True, True)

    def resolve(self, scope, definition_id, revision_id):
        if (
            scope == SCOPE
            and definition_id == "definition"
            and revision_id == "revision-1"
        ):
            return self.value
        return None


class MemoryRepository:
    def __init__(self):
        self.instances = {}
        self.assignments = []

    def create_instance(self, value, command_id):
        key = (value.scope, value.instance_id)
        if key in self.instances:
            if self.instances[key] == value:
                return AppendDisposition.REPLAYED
            raise DigitalEmployeeError("INSTANCE_IDENTITY_CONFLICT")
        self.instances[key] = value
        return AppendDisposition.APPENDED

    def get_instance(self, scope, instance_id):
        return self.instances.get((scope, instance_id))

    def replace_instance(self, value, expected_version):
        current = self.get_instance(value.scope, value.instance_id)
        if current.version != expected_version:
            raise DigitalEmployeeError("STALE_INSTANCE_VERSION")
        self.instances[(value.scope, value.instance_id)] = value

    def create_assignment(self, value):
        if any(
            x.lifecycle is AssignmentLifecycle.ACTIVE
            and x.business_role == value.business_role
            for x in self.assignments
        ):
            raise DigitalEmployeeError("ACTIVE_ASSIGNMENT_CONFLICT")
        self.assignments.append(value)
        return AppendDisposition.APPENDED

    def assignments_for_instance(self, scope, instance_id):
        return tuple(self.assignments)


def create(service, **changes):
    values = dict(
        scope=SCOPE,
        instance_id=DigitalEmployeeInstanceId("employee-1"),
        definition_id="definition",
        definition_revision_id="revision-1",
        owner_id="owner",
        organization_id="org",
        command_id="create-1",
        now=NOW,
    )
    values.update(changes)
    return service.create_instance(**values)


def test_definition_identity_lifecycle_readback_and_scope():
    repository = MemoryRepository()
    service = DigitalEmployeeApplicationService(repository, Definitions())
    created, disposition = create(service)
    assert disposition is AppendDisposition.APPENDED
    assert created.definition.revision_id == "revision-1"
    assert create(service)[1] is AppendDisposition.REPLAYED
    disabled = service.transition(
        SCOPE,
        created.instance_id,
        InstanceLifecycle.DISABLED,
        expected_version=1,
        now=NOW + timedelta(seconds=1),
    )
    assert disabled.version == 2
    with pytest.raises(
        DigitalEmployeeError, match="INVALID_INSTANCE_LIFECYCLE_TRANSITION"
    ):
        service.transition(
            SCOPE, created.instance_id, InstanceLifecycle.DISABLED, expected_version=2
        )
    assert (
        repository.get_instance(ScopeIdentity("other", "domain-a"), created.instance_id)
        is None
    )


def test_unknown_and_ineligible_definition_fail_closed():
    service = DigitalEmployeeApplicationService(MemoryRepository(), Definitions())
    with pytest.raises(DigitalEmployeeError, match="DEFINITION_NOT_FOUND"):
        create(service, definition_revision_id="unknown")
    Definitions.value = DefinitionReference(
        "definition", "revision-1", "d" * 64, False, False
    )
    with pytest.raises(DigitalEmployeeError, match="DEFINITION_INELIGIBLE"):
        create(service)
    Definitions.value = DefinitionReference(
        "definition", "revision-1", "d" * 64, True, True
    )


def test_assignment_conflict_and_disabled_instance_rejection():
    repository = MemoryRepository()
    service = DigitalEmployeeApplicationService(repository, Definitions())
    instance, _ = create(service)
    assignment = AssignmentRecord(
        SCOPE,
        AssignmentId("assignment-1"),
        instance.instance_id,
        "user-1",
        "reviewer",
        AssignmentLifecycle.ACTIVE,
        NOW,
        None,
        1,
        "assign-1",
    )
    assert service.assign(assignment) is AppendDisposition.APPENDED
    with pytest.raises(DigitalEmployeeError, match="ACTIVE_ASSIGNMENT_CONFLICT"):
        service.assign(
            AssignmentRecord(
                SCOPE,
                AssignmentId("assignment-2"),
                instance.instance_id,
                "user-2",
                "reviewer",
                AssignmentLifecycle.ACTIVE,
                NOW,
                None,
                1,
                "assign-2",
            )
        )
    service.transition(
        SCOPE, instance.instance_id, InstanceLifecycle.DISABLED, expected_version=1
    )
    with pytest.raises(DigitalEmployeeError, match="INSTANCE_NOT_ASSIGNABLE"):
        service.assign(
            AssignmentRecord(
                SCOPE,
                AssignmentId("assignment-3"),
                instance.instance_id,
                "user-3",
                "operator",
                AssignmentLifecycle.ACTIVE,
                NOW,
                None,
                1,
                "assign-3",
            )
        )


class QueryResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class CallerConnection:
    def __init__(self, *rows):
        self.rows = list(rows)
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((statement, parameters))
        return QueryResult(self.rows.pop(0))


def instance_record():
    return InstanceRecord(
        SCOPE,
        DigitalEmployeeInstanceId("employee-instance:one"),
        2,
        DefinitionReference(
            "employee-definition:one",
            "employee-revision:v1",
            "d" * 64,
            True,
            True,
            "DIGITAL_EMPLOYEE_DEFINITION_V1",
        ),
        "human:owner",
        "organization:one",
        InstanceLifecycle.ENABLED,
        None,
        None,
        (),
        NOW,
        NOW,
    )


def test_workbench_instance_read_uses_only_the_caller_connection() -> None:
    value = instance_record()
    row = {
        "aggregate_version": value.version,
        "record": PostgresDigitalEmployeeRepository._instance_record(
            value, "command:private"
        ),
    }
    connection = CallerConnection(row)
    repository = PostgresDigitalEmployeeRepository(object())  # type: ignore[arg-type]

    result = repository.read_instance_for_workbench(
        connection, SCOPE, value.instance_id, authorized=True
    )

    assert result == value
    assert len(connection.calls) == 1
    statement, parameters = connection.calls[0]
    assert "digital_employee_instances" in statement
    assert "FOR SHARE" in statement
    assert parameters == ("tenant-a", "domain-a", "employee-instance:one")


def test_workbench_instance_read_denies_before_query() -> None:
    connection = CallerConnection()
    repository = PostgresDigitalEmployeeRepository(object())  # type: ignore[arg-type]

    with pytest.raises(DigitalEmployeeError, match="INSTANCE_NOT_FOUND"):
        repository.read_instance_for_workbench(
            connection,
            SCOPE,
            DigitalEmployeeInstanceId("employee-instance:one"),
            authorized=False,
        )

    assert connection.calls == []


def test_workbench_assignment_read_uses_caller_connection_and_parent_chain() -> None:
    value = AssignmentRecord(
        SCOPE,
        AssignmentId("employee-assignment:one"),
        DigitalEmployeeInstanceId("employee-instance:one"),
        "human:reviewer",
        "reviewer",
        AssignmentLifecycle.ACTIVE,
        NOW,
        None,
        3,
        "command:private",
    )
    row = {
        "assignment_id": str(value.assignment_id),
        "digital_employee_instance_id": str(value.instance_id),
        "record": {
            "assignee_id": value.assignee_id,
            "business_role": value.business_role,
            "lifecycle": value.lifecycle.value,
            "effective_from": value.effective_from.isoformat(),
            "effective_until": None,
            "version": value.version,
            "command_id": value.command_id,
            "predecessor_assignment_id": None,
        },
    }
    connection = CallerConnection(row)
    repository = PostgresDigitalEmployeeRepository(object())  # type: ignore[arg-type]

    result = repository.read_assignment_for_workbench(
        connection,
        SCOPE,
        value.instance_id,
        value.assignment_id,
        authorized=True,
    )

    assert result == value
    statement, parameters = connection.calls[0]
    assert "JOIN execution_authority.digital_employee_instances" in statement
    assert "FOR SHARE OF assignment,instance" in statement
    assert parameters == (
        "tenant-a",
        "domain-a",
        "employee-assignment:one",
        "employee-instance:one",
    )


def test_workbench_assignment_read_denies_before_query() -> None:
    connection = CallerConnection()
    repository = PostgresDigitalEmployeeRepository(object())  # type: ignore[arg-type]

    with pytest.raises(DigitalEmployeeError, match="ASSIGNMENT_NOT_FOUND"):
        repository.read_assignment_for_workbench(
            connection,
            SCOPE,
            DigitalEmployeeInstanceId("employee-instance:one"),
            AssignmentId("employee-assignment:one"),
            authorized=False,
        )

    assert connection.calls == []
