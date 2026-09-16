"""Bounded, load-existing acceptance server; no initializer or provider is loaded."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path

import psycopg
from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg import sql

from agent_console.authority_configuration import AuthorityRuntimeConfiguration
from agent_console.authority_contracts import AuthorityError
from agent_console.authority_foundation import build_authority_foundation
from agent_console.browser_session_application import BrowserSessionPolicy
from agent_console.business_plan_postgres import PostgresProblemPlanUnitOfWork
from agent_console.business_problem_application import BusinessProblemApplication
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.draft_assistance import (
    DraftAssistanceError,
    read_authorized_invocation,
)
from agent_console.draft_assistance_api import _payload, _status
from agent_console.draft_assistance_authorization import (
    DraftAssistanceGrantTargetValidator,
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_assistance_postgres import PostgresDraftAssistanceRepository
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_console.workbench_bff import PREFIX, WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization


class RecoveryError(Exception):
    """Only the bounded error category may be printed; never raw driver errors."""


def file_identity(path: Path) -> dict:
    """Reject links and foreign ownership before hashing a preserved asset."""
    try:
        if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
            raise RecoveryError("ASSET_OWNERSHIP_MISMATCH")
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
                raise RecoveryError("ASSET_OWNERSHIP_MISMATCH")
            return {
                "sha256": hashlib.sha256(stream.read()).hexdigest(),
                "mode": stat.S_IMODE(info.st_mode),
                "uid": info.st_uid,
            }
    except OSError as exc:
        raise RecoveryError("ASSET_UNAVAILABLE") from exc


def verify_files(expected: dict) -> None:
    if not expected:
        raise RecoveryError("ASSET_MANIFEST_EMPTY")
    for name, identity in expected.items():
        if file_identity(Path(name)) != identity:
            raise RecoveryError("ASSET_MISMATCH")


def database_snapshot(connection) -> dict:
    """Read-only consistency fingerprint, not an authorized business projection."""
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        identity = connection.execute(
            "SELECT current_database(), system_identifier::text "
            "FROM pg_control_system()"
        ).fetchone()
        tables = connection.execute(
            "SELECT schemaname,tablename FROM pg_tables "
            "WHERE schemaname NOT IN ('pg_catalog','information_schema') "
            "ORDER BY schemaname,tablename"
        ).fetchall()
        facts = {}
        for schema, table in tables:
            rows = connection.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY 1").format(
                    sql.Identifier(schema, table)
                )
            ).fetchall()
            facts[f"{schema}.{table}"] = {
                "count": len(rows),
                "digest": hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            }
        columns = connection.execute(
            "SELECT table_schema,table_name,column_name,data_type,is_nullable,"
            "column_default FROM information_schema.columns "
            "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
            "ORDER BY table_schema,table_name,ordinal_position"
        ).fetchall()
        return {
            "database": identity[0],
            "systemIdentifier": identity[1],
            "columnsDigest": hashlib.sha256(json.dumps(columns).encode()).hexdigest(),
            "tables": facts,
        }


def verify_database(expected: dict, actual: dict) -> None:
    if actual != expected:
        raise RecoveryError("DATABASE_SNAPSHOT_MISMATCH")


def verify_owner_schemas(connection, migrations: Path) -> None:
    checks = (
        (
            "business_problem_authority",
            13,
            "0013_business_problem_authority.sql",
            "business-problem-postgresql-v1",
        ),
        (
            "business_problem_authority",
            20,
            "0020_business_problem_creator_receipt.sql",
            "business-problem-creator-receipt-postgresql-v20",
        ),
        (
            "draft_assistance",
            23,
            "0023_draft_assistance.sql",
            "draft-assistance-postgresql-v23",
        ),
    )
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        for schema, version, filename, adapter in checks:
            row = connection.execute(
                sql.SQL("SELECT checksum,adapter FROM {} WHERE version=%s").format(
                    sql.Identifier(schema, "schema_migrations")
                ),
                (version,),
            ).fetchone()
            if row != (
                hashlib.sha256((migrations / filename).read_bytes()).hexdigest(),
                adapter,
            ):
                raise RecoveryError("OWNER_SCHEMA_MISMATCH")
        for schema, maximum in (
            ("business_problem_authority", 20),
            ("draft_assistance", 23),
        ):
            row = connection.execute(
                sql.SQL("SELECT max(version) FROM {}").format(
                    sql.Identifier(schema, "schema_migrations")
                )
            ).fetchone()
            if row != (maximum,):
                raise RecoveryError("OWNER_SCHEMA_MISMATCH")


def acquire_writer(connection, database: str) -> None:
    locked = connection.execute(
        "SELECT pg_try_advisory_lock(hashtextextended(%s,0))",
        (f"acceptance-recovery:{database}",),
    ).fetchone()[0]
    if not locked:
        raise RecoveryError("COMPETING_RECOVERY_WRITER")
    others = connection.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
        "AND pid<>pg_backend_pid() AND backend_type='client backend'"
    ).fetchone()[0]
    if others:
        raise RecoveryError("COMPETING_DATABASE_CLIENT")


def mutation_allowed(method: str, path: str) -> bool:
    return method in {"GET", "HEAD"} or (
        path == f"{PREFIX}/session" and method in {"POST", "DELETE"}
    )


def install_recovery_boundary(app, check_serving_assets):
    @app.middleware("http")
    async def recovery_boundary(request, call_next):
        if not mutation_allowed(request.method, request.url.path):
            return JSONResponse(
                status_code=403,
                content={"reasonCode": "ACCEPTANCE_RECOVERY_READ_ONLY"},
            )
        try:
            check_serving_assets()
        except (RecoveryError, AuthorityError):
            return JSONResponse(
                status_code=503,
                content={"reasonCode": "RECOVERY_REQUIRED"},
            )
        return await call_next(request)


def build_application(runtime, migrations: Path, stack: ExitStack):
    problems = PostgresBusinessProblemRepository(
        runtime.database_url,
        migration_path=migrations / "0013_business_problem_authority.sql",
        creator_receipt_migration_path=migrations
        / "0020_business_problem_creator_receipt.sql",
    )
    stack.callback(problems.pool.close)
    drafts = PostgresDraftAssistanceRepository(
        runtime.database_url,
        migration_path=migrations / "0023_draft_assistance.sql",
    )
    stack.callback(drafts.close)
    targets = WorkbenchGrantTargetValidator(
        problems,
        additional=(DraftAssistanceGrantTargetValidator(drafts),),
    )
    foundation = build_authority_foundation(
        runtime,
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(minutes=30),
            absolute_lifetime=timedelta(hours=8),
            csrf_lifetime=timedelta(minutes=10),
        ),
        target_validator=targets,
        existing_only=True,
    )
    stack.callback(foundation.close)
    authorizer = WorkbenchOwnerAuthorization(
        foundation.generation_controller,
        foundation.repository,
        foundation.grants.authorization,
    )
    draft_authorization = GrantAdministrationDraftAuthorization(
        foundation.grants, authorizer
    )

    def install_reads(app, authenticate, require_csrf, policy):
        @app.get(f"{PREFIX}/draft-assistance/invocations/{{invocation_id}}")
        def read(invocation_id: str, request: Request):
            _, context = authenticate(request)
            try:
                return _payload(
                    read_authorized_invocation(
                        drafts,
                        draft_authorization,
                        context,
                        invocation_id,
                        synthetic=False,
                    )
                )
            except DraftAssistanceError as exc:
                return JSONResponse(
                    status_code=_status(exc.reason_code),
                    content={"reasonCode": exc.reason_code},
                )

    business = BusinessProblemApplication(
        PostgresProblemPlanUnitOfWork(problems, None),
        None,
        None,
        None,
        None,
    )
    app = create_workbench_bff(
        foundation.sessions,
        authorizer,
        WorkbenchBffPolicy("127.0.0.1:19643", "https://127.0.0.1:19643"),
        operations=tuple(
            operation
            for operation in business_problem_operations(business)
            if operation.name in {"LIST_PROBLEMS", "READ_PROBLEM"}
        ),
        route_installers=(install_reads,),
    )
    return app, foundation


def serve(manifest_path: Path, expected_manifest_digest: str) -> None:
    """Manifest creation is a separate, reviewed read-only preservation step."""
    import uvicorn

    identity = file_identity(manifest_path)
    if identity["mode"] != 0o600:
        raise RecoveryError("MANIFEST_NOT_PRIVATE")
    if identity["sha256"] != expected_manifest_digest:
        raise RecoveryError("MANIFEST_MISMATCH")
    manifest = json.loads(manifest_path.read_text())
    if manifest["schemaVersion"] != "kimi-acceptance-recovery.v1":
        raise RecoveryError("MANIFEST_INVALID")
    verify_files(manifest["files"])
    runtime = AuthorityRuntimeConfiguration.from_mapping(
        json.loads(Path(manifest["runtime"]).read_text())
    )
    if runtime.database_fingerprint != execution_database_fingerprint(
        runtime.database_url
    ):
        raise RecoveryError("DATABASE_CONFIGURATION_MISMATCH")
    migrations = Path(manifest["migrations"])
    with ExitStack() as stack:
        owner = stack.enter_context(
            psycopg.connect(runtime.database_url, autocommit=True)
        )
        acquire_writer(owner, manifest["database"]["database"])
        verify_database(manifest["database"], database_snapshot(owner))
        verify_owner_schemas(owner, migrations)
        app, foundation = build_application(runtime, migrations, stack)
        verify_database(manifest["database"], database_snapshot(owner))
        verify_files(manifest["files"])
        control = foundation.generation_controller.control.read()
        if control.operator_id != runtime.operator_id:
            raise RecoveryError("CONTROL_OWNER_MISMATCH")
        with foundation.generation_controller.protected_request():
            pass

        def check_serving_assets():
            verify_files(manifest["files"])
            with foundation.generation_controller.protected_request():
                pass

        install_recovery_boundary(app, check_serving_assets)

        dist = Path(manifest["dist"])
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}")
        def frontend(path: str):
            if path.startswith("api/"):
                return JSONResponse(
                    status_code=404, content={"reasonCode": "WORKBENCH_ROUTE_NOT_FOUND"}
                )
            return FileResponse(dist / "index.html")

        # Reserve both original ports before starting. The mutation control listener
        # is intentionally not exposed in this read-only recovery composition.
        sockets = []
        for port in (19643, 19644):
            sock = stack.enter_context(socket.socket())
            sock.bind(("127.0.0.1", port))
            sockets.append(sock)
        verify_files(manifest["files"])
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=19643,
            ssl_certfile=manifest["cert"],
            ssl_keyfile=manifest["key"],
            access_log=False,
            log_level="warning",
        )
        print(
            "RECOVERY_ASSETS_VERIFIED; MODEL_DISPATCH_DISABLED; FORMAL_WRITES_DISABLED",
            flush=True,
        )
        uvicorn.Server(config).run(sockets=[sockets[0]])
