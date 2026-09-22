"""Prepare exact technical instances and Assignments after real resource publication.

Only existing owner application methods write. No Plan confirmation, grant,
Attempt, Run, Kubernetes effect or Human decision is performed here.
"""

import argparse
import json
from pathlib import Path

from agent_console.digital_employee_bootstrap import DigitalEmployeeProductAssembly
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.digital_employee_schemas import (
    CreateDigitalEmployeeAssignment,
    CreateDigitalEmployeeInstance,
)
from agent_console.execution_domain import ScopeIdentity, VersionedAggregate
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.execution_preparation import ResourceBinding, TaskParticipation
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.prepared_execution_resources import published
from agent_console.resource_use_domain import canonical_digest, stable_id

ACTOR = "agent:s5-324-resource-preparer"
ROOT = Path(__file__).resolve().parents[2]


def ensure_aggregate(authority, kind, value):
    existing = authority.get_aggregate(kind, value.scope, value.aggregate_id)
    if existing is None:
        authority.create_aggregate(kind, value)
    elif existing != value:
        raise ValueError("EXACT_RUNTIME_BINDING_CONFLICT")


def assemble(authority, bundle, employee, semantics):
    case = bundle.get("case", "cost")
    if case not in ("cost", "delivery"):
        raise ValueError("RESOURCE_CASE_UNSUPPORTED")
    scope = ScopeIdentity(bundle["namespace"], bundle["securityDomain"])
    assembly = DigitalEmployeeProductAssembly(
        None, PostgresDigitalEmployeeRepository(authority)
    )
    definition = assembly.get_definition(
        scope,
        ACTOR,
        employee["employeeDefinitionId"],
        employee["employeeDefinitionRevisionId"],
    )
    if (
        not definition["published"]
        or definition["employeeDefinitionDigest"]
        != employee["employeeDefinitionDigest"]
    ):
        raise ValueError("PUBLISHED_EXACT_EMPLOYEE_REQUIRED")
    refs = {
        r["kind"]: ExactReference(
            resource_id=r["identity"],
            revision_id=r["revisionId"],
            digest=r["digest"].removeprefix("sha256:"),
        )
        for r in bundle["resources"]
    }
    with authority.pool.connection() as c:
        skill = published(c, scope, "SKILL", refs["skill"])
        published(c, scope, "KNOWLEDGE", refs["knowledge"])
        profile = published(c, scope, "RUNTIME", refs["runtime"])
        if profile["provider"] != "NATIVE_KUBERNETES":
            raise ValueError("NATIVE_PROFILE_REQUIRED")
    seed = canonical_digest(
        {
            "scope": [scope.namespace, scope.security_domain],
            "employee": definition["employeeDefinitionDigest"],
            "resources": {k: v.model_dump(mode="json") for k, v in refs.items()},
        }
    )
    instance_ids = {
        role: stable_id("s5-324-instance", seed, role) for role in ("root", "analyst")
    }
    instances = {}
    for role, identity in instance_ids.items():
        assembly.create_instance(
            scope,
            ACTOR,
            CreateDigitalEmployeeInstance(
                instanceId=identity,
                employeeDefinitionId=definition["employeeDefinitionId"],
                employeeDefinitionRevisionId=definition["employeeDefinitionRevisionId"],
                commandId=stable_id("s5-324-instantiate", seed, role),
                workspaceReference=f"isolated-synthetic-{case}-324",
                policyReferences=["ISOLATED_SYNTHETIC_READ_ONLY"],
            ),
        )
        instances[role] = assembly.get_instance(scope, identity)
    runtime_id = stable_id("s5-324-runtime", seed)
    agent_id = stable_id("s5-324-agent", seed)
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
                "kubernetes_agent_name": f"s5-324-synthetic-{case}",
            },
        ),
    )
    assignments = {}
    for task_id, role in [
        ("root", "root"),
        *[(t["task_id"], "analyst") for t in semantics["tasks"]],
    ]:
        identity = stable_id("s5-324-assignment", seed, task_id)
        instance = instances[role]
        assembly.create_assignment(
            scope,
            instance_ids[role],
            CreateDigitalEmployeeAssignment(
                assignmentId=identity,
                commandId=stable_id("s5-324-assign", seed, task_id),
                assigneeId=ACTOR,
                businessRole="s5-324:" + task_id,
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
        operation = next(
            o for o in skill["operations"] if o["name"] == task["operation"]
        )
        binding = ResourceBinding(
            kind="SKILL",
            reference=refs["skill"],
            owner_observation="published:" + refs["skill"].revision_id,
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
                executor_id=operation["executorId"],
                executor_revision=operation["executorRevision"],
                executor_digest=operation["executorConfigurationDigest"],
                agent_instance_id=agent_id,
                runtime_instance_id=runtime_id,
                runtime_generation=1,
                profile=refs["runtime"],
            ).model_dump(mode="json")
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
        "employee": employee_ref.model_dump(mode="json"),
        "executionStarted": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("runtime", "resources", "employee", "output"):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    runtime = json.loads(args.runtime.read_text())
    authority = PostgresExecutionAuthorityRepository(
        runtime["databaseUrl"],
        migration_path=ROOT
        / "console/backend/migrations/0008_execution_runtime_authority.sql",
    )
    try:
        authority.compatibility()
        bundle = json.loads(args.resources.read_text())
        with authority.pool.connection() as c:
            row = c.execute(
                "SELECT record,digest FROM workflow_planning.plans "
                "WHERE namespace=%s AND security_domain=%s "
                "AND plan_id=%s AND version=2",
                (
                    bundle["namespace"],
                    bundle["securityDomain"],
                    "5ad74afd-a6bf-4b04-b395-34d18d01c3b6",
                ),
            ).fetchone()
            if (
                row is None
                or row["digest"]
                != "a789015b006cecc053dc5297529edf80fa430411253aa13e869c210292623492"
            ):
                raise ValueError("ORIGINAL_PLAN_V2_MISMATCH")
        result = assemble(
            authority,
            bundle,
            json.loads(args.employee.read_text()),
            row["record"]["semantics"],
        )
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {"mappingDigest": result["mappingDigest"], "executionStarted": False}
            )
        )
    finally:
        authority.pool.close()


if __name__ == "__main__":
    main()
