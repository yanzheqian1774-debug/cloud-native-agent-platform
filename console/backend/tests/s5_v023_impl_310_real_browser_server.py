"""Real HTTPS Workbench fixture for the IMPL-310 browser acceptance journey."""

from __future__ import annotations

import argparse
import hashlib
import json
import ssl
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from agent_console.agent_definition_postgres import PostgresAgentDefinitionRepository
from agent_console.agent_definition_service import AgentDefinitionService
from agent_console.authority_configuration import AuthorityRuntimeConfiguration
from agent_console.authority_contracts import ExactGrant, GrantId
from agent_console.authority_foundation import initialize_authority_generation
from agent_console.business_problem_bootstrap import build_business_problem_application
from agent_console.digital_employee_application import (
    AssignmentLifecycle,
    AssignmentRecord,
)
from agent_console.digital_employee_bootstrap import build_digital_employee_assembly
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeDefinitionError,
    EmployeeDefinitionService,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_schemas import CreateDigitalEmployeeInstance
from agent_console.execution_domain import VersionedAggregate
from agent_console.execution_postgres import (
    AgentInstanceId,
    AssignmentId,
    DigitalEmployeeInstanceId,
    PlacementDecision,
    PlacementDecisionKind,
    PlacementId,
    PlacementRequest,
    PlacementRequestId,
    RuntimeInstanceId,
    ScopeIdentity,
    canonical_bytes,
)
from agent_console.governed_execution_ownership import execution_database_fingerprint
from agent_console.workbench_bootstrap import build_workbench_composition
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from s5_v023_impl_310_startup_status import BoundedStartupStatus

MIGRATIONS = Path(__file__).parents[1] / "migrations"
SCOPE = ScopeIdentity("tenant-a", "quality")
PRIMARY_EMPLOYEE = "employee-definition:quality"
PRIMARY_EMPLOYEE_REVISION = "employee-revision:1"
INSTANCE_ID = "employee-instance:quality"
ASSIGNMENT_ID = "employee-assignment:quality"
PLACEMENT_ID = "placement:quality"
ATTEMPT_ID = "attempt:quality"
AGENT_INSTANCE_ID = "agent-instance:quality"
RUNTIME_INSTANCE_ID = "runtime-instance:quality"
PLACEMENT_GRANT_ID = GrantId("grant-alice-placement-read")


class Authorized:
    def require(self, scope, action, identity):
        if scope != SCOPE:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        return f"acceptance:{action}:{identity}"


def publish_agent(service: AgentDefinitionService, name: str) -> dict:
    scope = service.scope(SCOPE.namespace, SCOPE.security_domain)
    row = service.create(
        scope,
        "human:owner",
        name,
        {
            "title": f"{name} title",
            "duties": ["Review supplier quality"],
            "businessPurpose": "Produce an evidence-backed review",
            "capabilities": ["supplier-quality.review"],
        },
    )
    definition_id = row["definitionId"]
    row = service.validate(
        scope, definition_id, "human:owner", row["aggregateVersion"]
    )["definition"]
    revision = row["revisions"][0]
    row = service.review(
        scope,
        definition_id,
        "human:reviewer",
        row["aggregateVersion"],
        revision["digest"],
        "APPROVE",
        "Exact acceptance review",
    )["definition"]
    service.publish(
        scope,
        definition_id,
        "human:publisher",
        row["aggregateVersion"],
        revision["digest"],
        row["reviews"][0]["reviewId"],
    )
    return {
        "definitionId": definition_id,
        "revisionId": revision["revisionId"],
        "digest": revision["digest"],
    }


def publish_employee(
    store,
    members: tuple[CompositionMember, ...],
    definition_id: str,
    role: str,
) -> EmployeeRevision:
    revision = EmployeeRevision(
        SCOPE,
        definition_id,
        PRIMARY_EMPLOYEE_REVISION,
        role,
        ("Review supplier quality work",),
        members,
    )
    service = EmployeeDefinitionService(store, Authorized())
    current = service.create(
        revision, expected_version=0, command_id=f"create:{definition_id}"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        current = service.decide(
            SCOPE,
            revision.definition_id,
            revision.revision_id,
            revision.digest,
            action,
            expected_version=current["aggregateVersion"],
            command_id=f"{action}:{definition_id}",
        )
    return revision


def seed_execution_chain(assembly, agent: dict, now: datetime) -> None:
    instance_id = DigitalEmployeeInstanceId(INSTANCE_ID)
    assembly.create_instance(
        SCOPE,
        "human:owner",
        CreateDigitalEmployeeInstance(
            instanceId=INSTANCE_ID,
            employeeDefinitionId=PRIMARY_EMPLOYEE,
            employeeDefinitionRevisionId=PRIMARY_EMPLOYEE_REVISION,
            commandId="create:acceptance-instance",
        ),
    )
    assignment = AssignmentRecord(
        SCOPE,
        AssignmentId(ASSIGNMENT_ID),
        instance_id,
        "team:quality",
        "Quality reviewer",
        AssignmentLifecycle.ACTIVE,
        now - timedelta(hours=1),
        None,
        1,
        "assign:acceptance",
    )
    assembly.repository.create_assignment(assignment)
    authority = assembly.repository.authority
    runtime_id = RuntimeInstanceId(RUNTIME_INSTANCE_ID)
    agent_id = AgentInstanceId(AGENT_INSTANCE_ID)
    authority.create_aggregate(
        "runtime_instance",
        VersionedAggregate(SCOPE, str(runtime_id), 1, {"current_generation": 1}),
    )
    authority.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            SCOPE,
            str(agent_id),
            1,
            {
                "agent_definition_id": agent["definitionId"],
                "agent_revision_id": agent["revisionId"],
                "agent_digest": agent["digest"],
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    request = PlacementRequest(
        PlacementRequestId("placement-request:quality"),
        SCOPE,
        "workflow-run:quality",
        "task-run:quality",
        ATTEMPT_ID,
        agent_id,
        agent["revisionId"],
        "runtime-profile-revision:1",
        (),
        (),
        (),
        (),
        now,
    )
    decision = PlacementDecision.create(
        placement_id=PlacementId(PLACEMENT_ID),
        request_id=request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=runtime_id,
        policy_version="policy:1",
        compatibility_facts=("NATIVE_COMPATIBLE",),
        limitation_codes=(),
        decided_at=now,
    )
    with authority.pool.connection() as connection:
        connection.execute(
            "INSERT INTO execution_authority.workflow_runs VALUES "
            "(%s,%s,%s,%s,'plan-revision:1',NULL,NULL,'{}'::jsonb)",
            (
                SCOPE.namespace,
                SCOPE.security_domain,
                "workflow-run:quality",
                ASSIGNMENT_ID,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.task_runs VALUES "
            "(%s,%s,%s,%s,'{}'::jsonb)",
            (
                SCOPE.namespace,
                SCOPE.security_domain,
                "task-run:quality",
                "workflow-run:quality",
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.attempts VALUES "
            "(%s,%s,%s,%s,NULL,%s,'{}'::jsonb)",
            (
                SCOPE.namespace,
                SCOPE.security_domain,
                ATTEMPT_ID,
                "task-run:quality",
                "c" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.placement_requests VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                SCOPE.namespace,
                SCOPE.security_domain,
                str(request.request_id),
                request.digest,
                request.canonical_bytes,
                ATTEMPT_ID,
                AGENT_INSTANCE_ID,
                now,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.placement_decisions VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (
                SCOPE.namespace,
                SCOPE.security_domain,
                PLACEMENT_ID,
                str(request.request_id),
                decision.decision.value,
                RUNTIME_INSTANCE_ID,
                decision.digest,
                json.dumps(json.loads(canonical_bytes(decision))["payload"]),
                now,
            ),
        )


def credential(name: str, digest: str, tenant: str = "tenant-a") -> dict:
    if len(digest) != 64 or any(value not in "0123456789abcdef" for value in digest):
        raise ValueError("CREDENTIAL_DIGEST_INVALID")
    return {
        "credentialId": f"credential-{name}",
        "credentialSha256": digest,
        "principalId": f"human:{name}",
        "tenantId": tenant,
        "securityDomain": "quality",
        "expiresAt": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        "authenticationSource": "BROWSER_BOOTSTRAP",
        "grants": [
            {
                "owner": "EMPLOYEE",
                "action": "LIST",
                "resource": "employee:collection",
                "source": "BROWSER_BOOTSTRAP",
            }
        ],
    }


def write_authority(
    runtime_dir: Path, database_url: str, credential_digests: dict[str, str]
) -> AuthorityRuntimeConfiguration:
    document = {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "policy-310",
        "auditSource": "s5-v023-impl-310-real-browser",
        "credentials": [
            credential("alice", credential_digests["full"]),
            credential("lister", credential_digests["list"]),
            credential("wrongscope", credential_digests["wrong_scope"], "tenant-b"),
            credential("wronggrant", credential_digests["wrong_grant"]),
        ],
        "requestability": [],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
    }
    generation_path = runtime_dir / "generation.json"
    raw = json.dumps(document, sort_keys=True).encode()
    generation_path.write_bytes(raw)
    (runtime_dir / "csrf.key").write_bytes(b"c" * 32)
    (runtime_dir / "continuation.key").write_bytes(b"o" * 32)
    return AuthorityRuntimeConfiguration.from_mapping(
        {
            "schemaVersion": "authority-foundation-runtime.v1",
            "databaseUrl": database_url,
            "migrationPath": str(
                (MIGRATIONS / "0018_browser_session_grant_authority.sql").resolve()
            ),
            "generationPath": str(generation_path.resolve()),
            "generationDigest": hashlib.sha256(raw).hexdigest(),
            "csrfSigningKeyPath": str((runtime_dir / "csrf.key").resolve()),
            "continuationSigningKeyPath": str(
                (runtime_dir / "continuation.key").resolve()
            ),
            "recoveryControlPath": str((runtime_dir / "control.json").resolve()),
            "databaseFingerprint": execution_database_fingerprint(database_url),
            "operatorId": "operator:s5-310",
        }
    )


def seed_grant(
    repository,
    *,
    key: str,
    principal: str,
    tenant: str,
    grant: ExactGrant,
    now: datetime,
) -> GrantId:
    grant_id = GrantId(f"grant-{key}")
    with repository.connection_scope() as connection:
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests "
            "(request_id,subject_principal_id,tenant_id,security_domain,"
            "purpose,state,created_at,decided_at) "
            "VALUES (%s,%s,%s,'quality',%s,'APPROVED',%s,%s)",
            (f"request-{key}", principal, tenant, f"S5_310_{key}", now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions "
            "(decision_id,request_id,issuer_principal_id,issuer_meta_decision_id,"
            "approved,reason_category,basis_type,basis_reference_digest,"
            "policy_version,audit_source,created_at) "
            "VALUES (%s,%s,'human:grant-admin',%s,true,'ASSIGNED_DUTY','POLICY',%s,"
            "'policy-310','s5-310',%s)",
            (f"decision-{key}", f"request-{key}", f"meta-{key}", "f" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants "
            "(grant_id,decision_id,request_id,subject_principal_id,tenant_id,"
            "security_domain,owner,action,exact_resource,basis_type,"
            "basis_reference_digest,issuer_principal_id,issuer_meta_decision_id,"
            "policy_version,audit_source,not_before,expires_at,created_at,"
            "recovery_epoch) VALUES (%s,%s,%s,%s,%s,'quality',%s,%s,%s,"
            "'POLICY',%s,'human:grant-admin',%s,"
            "'policy-310','s5-310',%s,%s,%s,1)",
            (
                str(grant_id),
                f"decision-{key}",
                f"request-{key}",
                principal,
                tenant,
                grant.owner,
                grant.action,
                grant.exact_resource,
                "f" * 64,
                f"meta-{key}",
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
                now,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants "
            "(grant_id,subject_principal_id,tenant_id,security_domain,owner,"
            "action,exact_resource,not_before,expires_at,recovery_epoch) "
            "VALUES (%s,%s,%s,'quality',%s,%s,%s,%s,%s,1)",
            (
                str(grant_id),
                principal,
                tenant,
                grant.owner,
                grant.action,
                grant.exact_resource,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        )
    return grant_id


def seed_dynamic_grants(repository, agent: dict, now: datetime) -> None:
    for key, grant in (
        ("alice-agent-list", ExactGrant("AGENT", "LIST", "agent:collection")),
        (
            "alice-employee-read",
            ExactGrant(
                "EMPLOYEE",
                "READ",
                f"employee:{PRIMARY_EMPLOYEE}:{PRIMARY_EMPLOYEE_REVISION}",
            ),
        ),
        (
            "alice-agent-read",
            ExactGrant(
                "AGENT", "READ", f"agent:{agent['definitionId']}:{agent['revisionId']}"
            ),
        ),
        (
            "alice-instance-read",
            ExactGrant("INSTANCE", "READ", f"instance:{INSTANCE_ID}"),
        ),
        (
            "alice-assignment-read",
            ExactGrant("ASSIGNMENT", "READ", f"assignment:{ASSIGNMENT_ID}"),
        ),
        (
            "alice-placement-read",
            ExactGrant("PLACEMENT", "READ", f"placement:{PLACEMENT_ID}"),
        ),
        ("lister-agent-list", ExactGrant("AGENT", "LIST", "agent:collection")),
        (
            "wrongscope-employee-read",
            ExactGrant(
                "EMPLOYEE",
                "READ",
                f"employee:{PRIMARY_EMPLOYEE}:{PRIMARY_EMPLOYEE_REVISION}",
            ),
        ),
        (
            "wronggrant-employee-read",
            ExactGrant("EMPLOYEE", "READ", "employee:other:revision:other"),
        ),
    ):
        principal = "human:" + key.split("-", 1)[0]
        tenant = "tenant-b" if principal == "human:wrongscope" else "tenant-a"
        seed_grant(
            repository,
            key=key,
            principal=principal,
            tenant=tenant,
            grant=grant,
            now=now,
        )


def build_fixture(args, startup: BoundedStartupStatus):
    startup.begin("DATABASE_CONNECTION")
    now = datetime.now(UTC)
    agent_repository = PostgresAgentDefinitionRepository(
        args.database_url,
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
    )
    startup.complete("DATABASE_CONNECTION")
    startup.begin("DATABASE_MIGRATION")
    agent_repository.migrate()
    agents = AgentDefinitionService(agent_repository)
    assembly = build_digital_employee_assembly(
        args.database_url,
        agents,
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    startup.complete("DATABASE_MIGRATION")
    startup.begin("SAMPLE_PREPARATION")
    primary_agent = publish_agent(agents, "Quality analysis Agent")
    publish_agent(agents, "Second page Agent")
    primary_members = (
        CompositionMember(
            MemberKind.AGENT,
            primary_agent["definitionId"],
            primary_agent["revisionId"],
            primary_agent["digest"],
        ),
        CompositionMember(
            MemberKind.SKILL,
            "skill:quality-review",
            "skill-revision:1",
            f"sha256:{'1' * 64}",
        ),
        CompositionMember(
            MemberKind.MCP,
            "mcp:quality-evidence",
            "mcp-revision:1",
            f"sha256:{'2' * 64}",
        ),
        CompositionMember(
            MemberKind.KNOWLEDGE,
            "knowledge:quality-procedure",
            "knowledge-revision:1",
            f"sha256:{'3' * 64}",
        ),
        CompositionMember(
            MemberKind.WORKFLOW,
            "workflow:quality-review",
            "workflow-revision:1",
            f"sha256:{'4' * 64}",
        ),
        CompositionMember(
            MemberKind.RUNTIME_PROFILE,
            "runtime-profile:quality",
            "runtime-profile-revision:1",
            f"sha256:{'5' * 64}",
        ),
    )
    publish_employee(
        assembly.employee_definitions,
        primary_members,
        PRIMARY_EMPLOYEE,
        "Supplier quality owner",
    )
    publish_employee(
        assembly.employee_definitions,
        (primary_members[0],),
        "employee-definition:second",
        "Second page employee",
    )
    seed_execution_chain(assembly, primary_agent, now)
    startup.complete("SAMPLE_PREPARATION")
    startup.begin("AUTHORIZATION_PREPARATION")
    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    control_token = args.control_token_file.read_text().strip()
    if not control_token:
        raise ValueError("CONTROL_TOKEN_INVALID")
    runtime = write_authority(
        args.runtime_dir,
        args.database_url,
        {
            "full": args.full_credential_sha256,
            "list": args.list_credential_sha256,
            "wrong_scope": args.wrong_scope_credential_sha256,
            "wrong_grant": args.wrong_grant_credential_sha256,
        },
    )
    (args.runtime_dir / "runtime.json").write_text(
        json.dumps(
            {
                "schemaVersion": "authority-foundation-runtime.v1",
                "databaseUrl": runtime.database_url,
                "migrationPath": str(runtime.migration_path),
                "generationPath": str(runtime.generation_path),
                "generationDigest": runtime.generation_digest,
                "csrfSigningKeyPath": str(runtime.csrf_signing_key_path),
                "continuationSigningKeyPath": str(
                    runtime.continuation_signing_key_path
                ),
                "recoveryControlPath": str(runtime.recovery_control_path),
                "databaseFingerprint": runtime.database_fingerprint,
                "operatorId": runtime.operator_id,
            },
            sort_keys=True,
        )
    )
    initialize_authority_generation(runtime, control_epoch=1, recovery_epoch=1, now=now)
    problems = build_business_problem_application(args.database_url, assembly)
    composition = build_workbench_composition(
        runtime_configuration_path=args.runtime_dir / "runtime.json",
        allowed_host=f"127.0.0.1:{args.public_port}",
        allowed_origin=f"https://127.0.0.1:{args.public_port}",
        owner_database_url=args.database_url,
        agent_database_url=args.database_url,
        business_problems=problems,
        agent_definitions=agent_repository,
        employee_definitions=assembly.employee_definitions,
        digital_employees=assembly.repository,
    )
    seed_dynamic_grants(composition.foundation.repository, primary_agent, now)
    public = composition.application
    public.mount("/assets", StaticFiles(directory=args.dist / "assets"), name="assets")

    @public.get("/{path:path}")
    def frontend(path: str):
        return FileResponse(args.dist / "index.html")

    startup.complete("AUTHORIZATION_PREPARATION")
    return composition, public, control_token


def record_listener_readiness(
    startup: BoundedStartupStatus,
    public_server: uvicorn.Server,
    control_server: uvicorn.Server,
) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if public_server.started and control_server.started:
            startup.complete("LISTENER_READINESS")
            return
        time.sleep(0.025)
    startup.fail(TimeoutError())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--runtime-dir", required=True, type=Path)
    parser.add_argument("--dist", required=True, type=Path)
    parser.add_argument("--public-port", required=True, type=int)
    parser.add_argument("--control-port", required=True, type=int)
    parser.add_argument("--cert", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--control-token-file", required=True, type=Path)
    parser.add_argument("--startup-status", required=True, type=Path)
    parser.add_argument("--full-credential-sha256", required=True)
    parser.add_argument("--list-credential-sha256", required=True)
    parser.add_argument("--wrong-scope-credential-sha256", required=True)
    parser.add_argument("--wrong-grant-credential-sha256", required=True)
    args = parser.parse_args()
    startup = BoundedStartupStatus(args.startup_status)
    composition = None
    try:
        composition, public, control_token = build_fixture(args, startup)
        startup.begin("TLS_CONFIGURATION")
        tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_context.load_cert_chain(args.cert, args.key)
        startup.complete("TLS_CONFIGURATION")
        control = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @control.get("/ready", status_code=204)
        def control_ready() -> None:
            return None

        @control.post("/revoke-placement")
        def revoke_placement(x_control_token: str = Header(default="")):
            if x_control_token != control_token:
                raise HTTPException(status_code=404)
            composition.foundation.repository.revoke_grant(
                PLACEMENT_GRANT_ID,
                actor_id="human:grant-admin",
                reason="DUTY_ENDED",
                idempotency_key="s5-310-revoke-placement",
                payload_digest="e" * 64,
                now=datetime.now(UTC),
            )
            return {"status": "revoked"}

        control_server = uvicorn.Server(
            uvicorn.Config(
                control, host="127.0.0.1", port=args.control_port, log_level="warning"
            )
        )
        public_server = uvicorn.Server(
            uvicorn.Config(
                public,
                host="127.0.0.1",
                port=args.public_port,
                ssl_certfile=args.cert,
                ssl_keyfile=args.key,
                log_level="warning",
            )
        )
        startup.begin("LISTENER_READINESS")
        threading.Thread(target=control_server.run, daemon=True).start()
        threading.Thread(
            target=record_listener_readiness,
            args=(startup, public_server, control_server),
            daemon=True,
        ).start()
        public_server.run()
    except BaseException as error:
        startup.fail(error)
        raise
    finally:
        if composition is not None:
            composition.close()


if __name__ == "__main__":
    main()
