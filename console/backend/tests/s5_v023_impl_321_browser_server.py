"""Task-isolated HTTPS/PG acceptance, production owners and local provider only."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import uvicorn
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.authority_foundation import initialize_authority_generation
from agent_console.business_problem_bootstrap import build_business_problem_application
from agent_console.digital_employee_bootstrap import build_digital_employee_assembly
from agent_console.draft_assistance_bootstrap import build_draft_assistance_composition
from agent_console.workbench_bootstrap import build_workbench_composition
from agent_console.workflow_definition_postgres import (
    PostgresWorkflowDefinitionRepository,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from s5_v023_impl_310_real_browser_server import (
    apply_prerequisite_migrations,
    write_authority,
)
from s5_v023_impl_321_draft_fixture import build_fixture

MIGRATIONS = Path(__file__).parents[1] / "migrations"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    identity = json.loads((runtime / "identity.json").read_text())
    database = identity["databaseUrl"]
    if database != "postgresql://postgres@127.0.0.1:55441/s5_v023_impl_321_acceptance":
        raise ValueError("321_DATABASE_IDENTITY_MISMATCH")
    if not args.resume:
        with psycopg.connect(database) as connection:
            count = connection.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema')"
            ).fetchone()[0]
            if count:
                raise ValueError("321_ALREADY_INITIALIZED_USE_RESUME")
        apply_prerequisite_migrations(database, (1, 2, 3, 4, 5, 7))
    agent = PostgresAgentDefinitionRepository(
        database,
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
    )
    if not args.resume:
        agent.migrate()
    employees = build_digital_employee_assembly(
        database,
        AgentDefinitionService(agent),
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    workflows = PostgresWorkflowDefinitionRepository(
        database, migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql"
    )
    # The shared prerequisite SQL already exists. Record only its missing owner ledger.
    workflows.record_shared_migration()
    workflows.compatibility()
    workflows.pool.close()
    problems = build_business_problem_application(database, employees)
    if not (runtime / "runtime.json").exists():
        credentials = json.loads((runtime / "credentials.json").read_text())
        authority = write_authority(
            runtime,
            database,
            {
                name: hashlib.sha256(value.encode()).hexdigest()
                for name, value in credentials.items()
            },
            trusted_preparation=True,
            trusted_preparation_source="s5-v023-impl-321-isolated-acceptance",
            draft_assistance=True,
        )
        document = {
            "schemaVersion": "authority-foundation-runtime.v1",
            "databaseUrl": database,
            "migrationPath": str(authority.migration_path),
            "generationPath": str(authority.generation_path),
            "generationDigest": authority.generation_digest,
            "csrfSigningKeyPath": str(authority.csrf_signing_key_path),
            "continuationSigningKeyPath": str(authority.continuation_signing_key_path),
            "recoveryControlPath": str(authority.recovery_control_path),
            "databaseFingerprint": authority.database_fingerprint,
            "operatorId": authority.operator_id,
        }
        (runtime / "runtime.json").write_text(json.dumps(document))
        initialize_authority_generation(
            authority, control_epoch=1, recovery_epoch=1, now=datetime.now(UTC)
        )
    if not (runtime / "draft-assistance-runtime.json").exists():
        draft = build_fixture(
            database,
            runtime,
            responses_url="https://127.0.0.1:19323/v1/responses",
            ca_file=runtime / "cert.pem",
            credential_file=runtime / "provider-key",
        )
    else:
        draft = build_draft_assistance_composition(
            database_url=database,
            runtime_configuration_path=runtime / "draft-assistance-runtime.json",
            migrations_path=MIGRATIONS,
            allow_local_https_mock=True,
        )
    composition = build_workbench_composition(
        runtime_configuration_path=runtime / "runtime.json",
        allowed_host="127.0.0.1:19322",
        allowed_origin="https://127.0.0.1:19322",
        owner_database_url=database,
        agent_database_url=database,
        business_problems=problems,
        agent_definitions=agent,
        employee_definitions=employees.employee_definitions,
        digital_employees=employees.repository,
        draft_assistance=draft.service,
        managed_closeables=(draft,),
    )
    app = composition.application
    app.mount("/assets", StaticFiles(directory=args.dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        return FileResponse(args.dist / "index.html")

    (runtime / "initialized.json").write_text(
        json.dumps(
            {
                "session": "S5-V023-IMPL-321",
                "port": 19322,
                "modelQuality": "NOT_MEASURED",
            }
        )
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=19322,
        ssl_certfile=str(runtime / "cert.pem"),
        ssl_keyfile=str(runtime / "key.pem"),
        access_log=False,
    )


if __name__ == "__main__":
    main()
