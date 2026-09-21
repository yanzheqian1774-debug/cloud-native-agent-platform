"""Create only the bounded engineering Employee draft through the normal owner.

No validation approval, publication, instance, Assignment, Plan or Run is created.
Actual generated identities are read back and reused after an interrupted receipt.
"""

import argparse
import json
from pathlib import Path
from uuid import uuid4

from agent_console.digital_employee_bootstrap import DigitalEmployeeProductAssembly
from agent_console.digital_employee_postgres import PostgresDigitalEmployeeRepository
from agent_console.digital_employee_schemas import CreateEmployeeDefinition
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
ROLE = "S5-324 隔离合成成本核验员"
ACTOR = "agent:s5-324-resource-preparer"


def prepare(authority, resources):
    scope = ScopeIdentity(resources["namespace"], resources["securityDomain"])
    members = [
        {
            "kind": {
                "agent": "AGENT",
                "skill": "SKILL",
                "runtime": "RUNTIME_PROFILE",
                "knowledge": "KNOWLEDGE",
            }[r["kind"]],
            "resourceId": r["identity"],
            "revisionId": r["revisionId"],
            "digest": r["digest"],
        }
        for r in resources["resources"]
    ]
    assembly = DigitalEmployeeProductAssembly(
        None, PostgresDigitalEmployeeRepository(authority)
    )
    with authority.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        c.execute("SELECT pg_advisory_xact_lock(3240014)")
        rows = c.execute(
            "SELECT definition_id,revision_id,record "
            "FROM digital_employee_definition.revisions WHERE namespace=%s "
            "AND security_domain=%s AND record->>'role'=%s",
            (scope.namespace, scope.security_domain, ROLE),
        ).fetchall()
        if len({r["definition_id"] for r in rows}) > 1:
            raise ValueError("EMPLOYEE_DRAFT_AMBIGUOUS")
        predecessors = {r["record"].get("predecessorRevisionId") for r in rows}
        leaves = [r for r in rows if r["revision_id"] not in predecessors]
        if rows and len(leaves) != 1:
            raise ValueError("EMPLOYEE_DRAFT_AMBIGUOUS")
        if leaves:
            row = leaves[0]
            current = assembly.get_definition(
                scope, ACTOR, row["definition_id"], row["revision_id"]
            )
        else:
            current = assembly.create_definition(
                scope,
                ACTOR,
                CreateEmployeeDefinition(
                    employeeDefinitionId="employee-definition:" + str(uuid4()),
                    employeeDefinitionRevisionId="employee-revision:" + str(uuid4()),
                    role=ROLE,
                    responsibilities=[
                        "按批准的六任务依赖处理固定合成资料",
                        "只读分析并保留来源、产物、限制及人工决定",
                    ],
                    members=members,
                    expectedVersion=0,
                    commandId="s5-324-engineering-employee-draft-v1",
                ),
            )
        actual = {
            (m["kind"], m["resourceId"], m["revisionId"], m["digest"])
            for m in current["members"]
        }
        expected = {
            (m["kind"], m["resourceId"], m["revisionId"], m["digest"]) for m in members
        }
        if actual != expected:
            raise ValueError("EMPLOYEE_DRAFT_CONTENT_CONFLICT")
        return current


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runtime", type=Path, required=True)
    p.add_argument("--resources", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    runtime = json.loads(args.runtime.read_text())
    repo = PostgresExecutionAuthorityRepository(
        runtime["databaseUrl"],
        migration_path=ROOT
        / "console/backend/migrations/0008_execution_runtime_authority.sql",
    )
    try:
        repo.compatibility()
        result = prepare(repo, json.loads(args.resources.read_text()))
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "state": ("PUBLISHED" if result["published"] else "DRAFT"),
                    "output": str(args.output),
                }
            )
        )
    finally:
        repo.pool.close()


if __name__ == "__main__":
    main()
