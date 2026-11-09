"""Production exact read-only instance/assignment binding using existing owners.

Caller supplies its real actor and current exact authorization checks. Every
write shares the caller connection; no approval, Run, dispatch or evaluator.
"""

import json
import re

from agent_console.digital_employee_bootstrap import DigitalEmployeeProductAssembly
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
)
from agent_console.execution_domain import ScopeIdentity, VersionedAggregate
from agent_console.execution_preparation import ResourceBinding, TaskParticipation
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.prepared_execution_resources import published
from agent_console.resource_use_domain import canonical_digest, stable_id


def ensure_aggregate(authority, kind, value):
    existing = authority.get_aggregate(kind, value.scope, value.aggregate_id)
    if existing is None:
        authority.create_aggregate(kind, value)
    elif existing != value:
        raise ValueError("EXACT_RUNTIME_BINDING_CONFLICT")


def assemble(
    authority,
    connection,
    bundle,
    employee,
    semantics,
    *,
    principal,
    authorize,
    plan_digest,
    agent_name,
    sales_v2_candidate=False,
):
    """Atomic DB-only preparation under exact caller grants, never a Run/effect."""
    if (bundle["namespace"], bundle["securityDomain"]) != (
        principal.tenant_id,
        principal.security_domain,
    ):
        raise ValueError("READONLY_ASSEMBLY_SCOPE_MISMATCH")
    if not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?", agent_name):
        raise ValueError("READONLY_NATIVE_AGENT_NAME_REQUIRED")
    with connection.transaction():
        return _assemble(
            authority.for_transaction(connection),
            bundle,
            employee,
            semantics,
            actor=principal.principal_id,
            authorize=authorize,
            plan_digest=plan_digest,
            agent_name=agent_name,
            sales_v2_candidate=sales_v2_candidate,
        )


def _assemble(
    authority,
    bundle,
    employee,
    semantics,
    *,
    actor,
    authorize,
    plan_digest,
    agent_name,
    sales_v2_candidate=False,
):
    case = bundle.get("case", "cost")
    if case not in ("delivery", "sales", "tabular"):
        raise ValueError("RESOURCE_CASE_UNSUPPORTED")
    scope = ScopeIdentity(bundle["namespace"], bundle["securityDomain"])
    if not re.fullmatch(r"[0-9a-f]{64}", plan_digest) or not actor:
        raise ValueError("EXACT_PLAN_AND_ACTOR_REQUIRED")
    authorize(
        "EMPLOYEE",
        "READ",
        "employee:"
        + employee["employeeDefinitionId"]
        + ":"
        + employee["employeeDefinitionRevisionId"],
    )
    assembly = DigitalEmployeeProductAssembly(
        None, PostgresDigitalEmployeeRepository(authority)
    )
    definition = assembly.get_definition(
        scope,
        actor,
        employee["employeeDefinitionId"],
        employee["employeeDefinitionRevisionId"],
    )
    if (
        not definition["published"]
        or definition["employeeDefinitionDigest"]
        != employee["employeeDefinitionDigest"]
    ):
        raise ValueError("PUBLISHED_EXACT_EMPLOYEE_REQUIRED")
    from .task_member_binding import bind_steps, resource_groups

    groups = resource_groups(bundle["resources"])
    refs = {kind: values[0] for kind, values in groups.items()}
    from .workbench_prepared_resources import OWNERS, reference

    for kind, values in groups.items():
        for ref in values:
            authorize(
                OWNERS[kind],
                "READ_RESOURCE",
                reference(kind, ref.resource_id, ref.revision_id),
            )
    authorize(
        "AGENT",
        "READ",
        "agent:" + refs["agent"].resource_id + ":" + refs["agent"].revision_id,
    )
    from .digital_employee_definition import EmployeeRevision

    with authority.pool.connection() as c:
        exact = assembly.employee_definitions._read(
            c,
            scope,
            employee["employeeDefinitionId"],
            employee["employeeDefinitionRevisionId"],
        )
        revision = EmployeeRevision.from_record(exact["revision"])
        expected = {
            (
                m.kind.value,
                m.resource_id,
                m.revision_id,
                m.digest.removeprefix("sha256:"),
            )
            for m in revision.members
        }
        actual = {
            (
                "RUNTIME_PROFILE" if kind == "runtime" else kind.upper(),
                ref.resource_id,
                ref.revision_id,
                ref.digest,
            )
            for kind, values in groups.items()
            for ref in values
        }
        if expected != actual:
            raise ValueError("EXACT_EMPLOYEE_MEMBER_MAPPING_REQUIRED")
        assembly.employee_definitions.validate_members(c, revision)
        skills = [(ref, published(c, scope, "SKILL", ref)) for ref in groups["skill"]]
        source_content = published(c, scope, "KNOWLEDGE", refs["knowledge"])
        from .plan_suggestion_domain import FlexiblePlanSemantics
        from .planning_source_change import approved_source

        if (
            approved_source(FlexiblePlanSemantics.model_validate(semantics))
            != refs["knowledge"]
        ):
            raise ValueError("READONLY_ASSEMBLY_SOURCE_MISMATCH")
        documents = source_content.get("documents", [])
        if len(documents) != 1 or len(documents[0].get("chunks", [])) != 1:
            raise ValueError("READONLY_ASSEMBLY_SINGLE_SOURCE_REQUIRED")
        source = json.loads(documents[0]["chunks"][0]["content"])
        from .resource_automation_policy import source_digest

        source_digest(source_content)
        expected_schema = (
            "tabular-diagnostic-source.v1"
            if case == "tabular"
            else "sales-diagnostic-source.v1"
            if case == "sales"
            else "synthetic-delivery-source.v1"
        )
        if (
            source.get("schemaVersion") != expected_schema
            or source.get("synthetic") is not True
        ):
            raise ValueError("READONLY_ASSEMBLY_SOURCE_FAMILY_MISMATCH")
        profile = published(c, scope, "RUNTIME", refs["runtime"])
        if profile["provider"] != "NATIVE_KUBERNETES":
            raise ValueError("NATIVE_PROFILE_REQUIRED")
    bindings = bind_steps(
        FlexiblePlanSemantics.model_validate(semantics),
        skills,
        source_schema=expected_schema,
        case=case,
        sales_v2_candidate=sales_v2_candidate,
    )
    seed = canonical_digest(
        {
            "scope": [scope.namespace, scope.security_domain],
            "planDigest": plan_digest,
            "employee": definition["employeeDefinitionDigest"],
            "resources": (
                {k: v.model_dump(mode="json") for k, v in refs.items()}
                if all(len(values) == 1 for values in groups.values())
                else {
                    k: [v.model_dump(mode="json") for v in values]
                    for k, values in groups.items()
                }
            ),
        }
    )
    instance_ids = {
        role: stable_id("prepared-readonly-instance", seed, role)
        for role in ("root", "analyst")
    }
    authorize("INSTANCE", "CREATE", "instance:collection")
    instances = {}
    for role, identity in instance_ids.items():
        assembly.create_instance(
            scope,
            actor,
            CreateDigitalEmployeeInstance(
                instanceId=identity,
                employeeDefinitionId=definition["employeeDefinitionId"],
                employeeDefinitionRevisionId=definition["employeeDefinitionRevisionId"],
                commandId=stable_id("prepared-readonly-instantiate", seed, role),
                workspaceReference=f"isolated-synthetic-{case}",
                policyReferences=["ISOLATED_SYNTHETIC_READ_ONLY"],
            ),
        )
        instances[role] = assembly.get_instance(scope, identity)
    runtime_id = stable_id("prepared-readonly-runtime", seed)
    agent_id = stable_id("prepared-readonly-agent", seed)
    ensure_aggregate(
        authority,
        "runtime_instance",
        VersionedAggregate(
            scope,
            runtime_id,
            1,
            {
                "current_generation": 1,
                "classification": "NATIVE",
                "profile": refs["runtime"].model_dump(mode="json"),
                "execution_mode": "EXISTING_NATIVE_WORKER_MANAGED_SKILL",
                "isolation": "ISOLATED_SYNTHETIC_READ_ONLY",
            },
        ),
    )
    ensure_aggregate(
        authority,
        "agent_instance",
        VersionedAggregate(
            scope,
            agent_id,
            1,
            {
                "agent_revision_id": refs["agent"].revision_id,
                "agent_definition_id": refs["agent"].resource_id,
                "agent_digest": refs["agent"].digest,
                "runtime_instance_id": runtime_id,
                "kubernetes_agent_name": agent_name,
            },
        ),
    )
    assignments = {}
    for task_id, role in [
        ("root", "root"),
        *[(t["task_id"], "analyst") for t in semantics["tasks"]],
    ]:
        identity = stable_id("prepared-readonly-assignment", seed, task_id)
        instance = instances[role]
        authorize("ASSIGNMENT", "CREATE", "assignment:instance:" + instance_ids[role])
        assembly.create_assignment(
            scope,
            instance_ids[role],
            CreateDigitalEmployeeAssignment(
                assignmentId=identity,
                commandId=stable_id("prepared-readonly-assign", seed, task_id),
                assigneeId=actor,
                businessRole="prepared-readonly:" + task_id,
                effectiveFrom=instance["createdAt"],
                effectiveUntil=None,
            ),
        )
        assignments[task_id] = identity
    employee_ref = ExactReference(
        resource_id=definition["employeeDefinitionId"],
        revision_id=definition["employeeDefinitionRevisionId"],
        digest=definition["employeeDefinitionDigest"],
    )
    participants = []
    for task in semantics["tasks"]:
        selected = bindings[task["task_id"]]
        operation = selected["operation"]
        binding = ResourceBinding(
            kind="SKILL",
            reference=selected["reference"],
            owner_observation="published:" + selected["reference"].revision_id,
            input_schema_digest=canonical_digest(operation["inputSchema"]),
            output_schema_digest=canonical_digest(operation["outputSchema"]),
            operation=task["operation"],
        )
        participants.append(
            TaskParticipation(
                task_id=task["task_id"],
                assignment_id=assignments[task["task_id"]],
                instance_id=instance_ids["analyst"],
                definition=employee_ref,
                skill=binding,
                resources=(
                    ResourceBinding(
                        kind="KNOWLEDGE",
                        reference=refs["knowledge"],
                        owner_observation="published:" + refs["knowledge"].revision_id,
                        input_schema_digest=canonical_digest(
                            {"sourceSchema": expected_schema}
                        ),
                        output_schema_digest=canonical_digest(source_content),
                        operation="READ_RESOURCE",
                    ),
                ),
                executor_id=operation["executorId"],
                executor_revision=operation["executorRevision"],
                executor_digest=operation["executorConfigurationDigest"],
                agent_instance_id=agent_id,
                runtime_instance_id=runtime_id,
                runtime_generation=1,
                profile=refs["runtime"],
                max_attempts=1,
            ).model_dump(mode="json")
        )
    if case == "sales":
        from agent_console.readonly_resource_assembly import check_readonly_assembly
        from agent_console.sales_diagnostic_skill import OPERATIONS

        from .sales_gross_profit_integration import is_v2, require_source

        if any(
            is_v2(p["executor_id"], p["executor_revision"], p["executor_digest"])
            for p in participants
        ):
            require_source(source)
        from .resource_automation_validation import executor_registry

        check_readonly_assembly(
            tuple(TaskParticipation.model_validate(p) for p in participants),
            registry=executor_registry(sales_v2_candidate=sales_v2_candidate),
            allowed_references=tuple(
                ref.model_dump(mode="json")
                for ref in (
                    *[v for values in groups.values() for v in values],
                    employee_ref,
                )
            ),
            operations=OPERATIONS,
        )
    mapping = {
        "namespace": scope.namespace,
        "security_domain": scope.security_domain,
        "root_assignment_id": assignments["root"],
        "root_instance_id": instance_ids["root"],
        "participants": participants,
        "source_snapshot": refs["knowledge"].model_dump(mode="json"),
        "synthetic": True,
        "execution_boundary": "ISOLATED_SYNTHETIC_READ_ONLY",
    }
    return {
        "mapping": mapping,
        "mappingDigest": canonical_digest(mapping),
        "stepBindings": [
            {
                "taskId": task["task_id"],
                "operation": task["operation"],
                "inputs": task["inputs"],
                "outputs": task["outputs"],
                "dependsOn": task["depends_on"],
                "criterionRevisionIds": task["criterion_revision_ids"],
                "skill": bindings[task["task_id"]]["reference"].model_dump(mode="json"),
                "selectionBasis": bindings[task["task_id"]]["basis"],
                "source": refs["knowledge"].model_dump(mode="json"),
                "runtime": refs["runtime"].model_dump(mode="json"),
                "employeeUnchanged": True,
            }
            for task in semantics["tasks"]
        ],
        "employee": employee_ref.model_dump(mode="json"),
        "executionStarted": False,
    }
