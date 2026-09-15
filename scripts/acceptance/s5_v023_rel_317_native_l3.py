"""Dedicated REL-317 Native L3 seed, worker, and readback command."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "console/backend/migrations"
BACKEND_TESTS = ROOT / "console/backend/tests"
NAMESPACE = "s5-v023-rel-317-native"
SECURITY_DOMAIN = "native"
PRINCIPAL = "human:rel-317-owner"
CREDENTIAL_ID = "rel-317-service-credential"
OPERATOR_ID = "operator:s5-v023-rel-317"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def generation(expires_at: datetime) -> dict[str, object]:
    return {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "policy-rel-317",
        "auditSource": "s5-v023-rel-317-native-l3",
        "credentials": [
            {
                "credentialId": CREDENTIAL_ID,
                "credentialSha256": "c" * 64,
                "principalId": PRINCIPAL,
                "tenantId": NAMESPACE,
                "securityDomain": SECURITY_DOMAIN,
                "expiresAt": expires_at.isoformat(),
                "authenticationSource": "SERVICE_ONLY",
                "grants": [],
            }
        ],
        "requestability": [],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
    }


def write_authority_files(
    artifact_dir: Path, cluster_database_url: str, generation_digest: str
) -> None:
    from agent_console.governed_execution_ownership import (
        execution_database_fingerprint,
    )

    authority_dir = artifact_dir / "authority"
    authority_dir.mkdir(parents=True, exist_ok=True)
    fingerprint = execution_database_fingerprint(cluster_database_url)
    runtime = {
        "schemaVersion": "authority-foundation-runtime.v1",
        "databaseUrl": cluster_database_url,
        "migrationPath": (
            "/app/console/backend/migrations/0018_browser_session_grant_authority.sql"
        ),
        "generationPath": "/authority/generation.json",
        "generationDigest": generation_digest,
        "csrfSigningKeyPath": "/authority/csrf.key",
        "continuationSigningKeyPath": "/authority/continuation.key",
        "recoveryControlPath": "/authority/control.json",
        "databaseFingerprint": fingerprint,
        "operatorId": OPERATOR_ID,
    }
    control = {
        "schemaVersion": "authority-host-control.v1",
        "control_epoch": 1,
        "recovery_epoch": 1,
        "state": "ACTIVE",
        "database_fingerprint": fingerprint,
        "generation": 1,
        "generation_digest": generation_digest,
        "operator_id": OPERATOR_ID,
    }
    (authority_dir / "runtime.json").write_bytes(canonical_json(runtime))
    (authority_dir / "control.json").write_bytes(canonical_json(control))
    (authority_dir / "csrf.key").write_bytes(b"c" * 32)
    (authority_dir / "continuation.key").write_bytes(b"o" * 32)
    for path in authority_dir.iterdir():
        path.chmod(0o600)


def seed(database_url: str, cluster_database_url: str, artifact_dir: Path) -> None:
    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityScope,
        ExactGrant,
        TrustedRequestContext,
    )
    from agent_console.authority_postgres import PostgresAuthorityRepository
    from agent_console.execution_domain import VersionedAggregate
    from agent_console.execution_postgres import (
        AgentInstanceId,
        Generation,
        PlacementDecision,
        PlacementDecisionKind,
        PlacementId,
        PlacementRequest,
        PlacementRequestId,
        PostgresExecutionAuthorityRepository,
        RuntimeInstanceId,
    )
    from agent_console.native_dispatch_application import (
        NativeDispatchApplication,
        QueueNativeDispatch,
    )

    sys.path.insert(0, str(BACKEND_TESTS))
    from employee_identity_support import start_chain
    from test_execution_application_postgres import approved_plan

    artifact_dir.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(database_url, autocommit=True) as connection:
        rows = connection.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' "
            "AND nspname <> 'information_schema'"
        ).fetchall()
        for (schema,) in rows:
            connection.execute(
                psycopg.sql.SQL("DROP SCHEMA {} CASCADE").format(
                    psycopg.sql.Identifier(schema)
                )
            )
        connection.execute("CREATE SCHEMA public")
    with psycopg.connect(database_url) as connection:
        for version in range(1, 8):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )

    repository = PostgresExecutionAuthorityRepository(
        database_url, migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql"
    )
    repository.migrate()
    repository.migrate_native_dispatch(
        MIGRATIONS / "0022_native_execution_dispatch.sql"
    )
    with repository.pool.connection() as connection, connection.transaction():
        connection.execute(
            "UPDATE execution_authority.evidence_cutover SET "
            "state='POSTGRES_ACTIVE',authoritative_writer='POSTGRES'"
        )

    suffix = f"rel317-{uuid.uuid4().hex[:12]}"
    workflow = replace(
        approved_plan(suffix), tenant_id=NAMESPACE, security_domain=SECURITY_DOMAIN
    )
    revision, _, _, start_command, started = start_chain(
        repository, database_url, workflow
    )
    identity = started.identity
    member = revision.members[0]
    runtime_id = RuntimeInstanceId(f"runtime-{suffix}")
    agent_id = AgentInstanceId(f"agent-{suffix}")
    repository.create_aggregate(
        "runtime_instance",
        VersionedAggregate(
            identity.scope, str(runtime_id), 1, {"current_generation": 1}
        ),
    )
    repository.create_aggregate(
        "agent_instance",
        VersionedAggregate(
            identity.scope,
            str(agent_id),
            1,
            {
                "agent_revision_id": member.revision_id,
                "agent_definition_id": member.resource_id,
                "agent_digest": member.digest,
                "runtime_instance_id": str(runtime_id),
            },
        ),
    )
    now = datetime.now(UTC)
    placement_request = PlacementRequest(
        PlacementRequestId(f"request-{suffix}"),
        identity.scope,
        identity.workflow_run.workflow_run_id,
        identity.task_run.task_run_id,
        identity.attempt.attempt_id,
        agent_id,
        member.revision_id,
        "runtime-profile",
        (),
        (),
        (),
        (),
        now,
    )
    placement = PlacementDecision.create(
        placement_id=PlacementId(f"placement-{suffix}"),
        request_id=placement_request.request_id,
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=runtime_id,
        policy_version="policy-rel-317",
        compatibility_facts=(),
        limitation_codes=("MOCK_PROVIDER_ONLY",),
        decided_at=now,
    )
    repository.decide(identity.scope, placement_request, placement)
    context = TrustedRequestContext(
        PRINCIPAL,
        AuthorityScope(NAMESPACE, SECURITY_DOMAIN),
        CREDENTIAL_ID,
        AuthenticationSource.SERVICE_CREDENTIAL,
        "policy-rel-317",
    )
    grant = ExactGrant(
        "EXECUTION", "START", f"governed-execution:{identity.attempt.attempt_id}"
    )
    queued = NativeDispatchApplication(repository).queue(
        QueueNativeDispatch(
            identity.scope,
            identity.attempt.attempt_id,
            placement.placement_id,
            start_command.approved_plan.plan_digest,
            Generation(1),
            agent_id,
            context,
            grant,
            Generation(1),
            Generation(1),
            "researcher-agent",
            "REL-317 bounded Native L3",
            30,
            f"queue-{suffix}",
            now,
        )
    )

    expires_at = now + timedelta(days=1)
    generation_raw = canonical_json(generation(expires_at))
    generation_digest = hashlib.sha256(generation_raw).hexdigest()
    authority_dir = artifact_dir / "authority"
    authority_dir.mkdir(parents=True, exist_ok=True)
    (authority_dir / "generation.json").write_bytes(generation_raw)
    (authority_dir / "generation.json").chmod(0o600)
    write_authority_files(artifact_dir, cluster_database_url, generation_digest)

    authority = PostgresAuthorityRepository(
        database_url,
        migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql",
    )
    authority.migrate()
    authority.activate_generation(
        1,
        generation_digest,
        1,
        operator_id=OPERATOR_ID,
        revoked_credentials=(),
        now=now,
    )
    with authority.pool.connection() as connection, connection.transaction():
        request_id = f"request-{suffix}"
        decision_id = f"decision-{suffix}"
        grant_id = f"grant-{suffix}"
        connection.execute(
            "INSERT INTO authorization_admin.grant_requests"
            "(request_id,subject_principal_id,tenant_id,security_domain,purpose,"
            "state,created_at,decided_at) VALUES"
            "(%s,%s,%s,%s,'NATIVE_DISPATCH','APPROVED',%s,%s)",
            (request_id, PRINCIPAL, NAMESPACE, SECURITY_DOMAIN, now, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grant_decisions VALUES"
            "(%s,%s,'human:rel-317-admin','meta-rel-317',true,'ASSIGNED_DUTY',"
            "'TASK',%s,'policy-rel-317','s5-v023-rel-317-native-l3',%s)",
            (decision_id, request_id, "d" * 64, now),
        )
        connection.execute(
            "INSERT INTO authorization_admin.grants VALUES("
            + ",".join(["%s"] * 19)
            + ")",
            (
                grant_id,
                decision_id,
                request_id,
                PRINCIPAL,
                NAMESPACE,
                SECURITY_DOMAIN,
                grant.owner,
                grant.action,
                grant.exact_resource,
                "TASK",
                "d" * 64,
                "human:rel-317-admin",
                "meta-rel-317",
                "policy-rel-317",
                "s5-v023-rel-317-native-l3",
                now,
                expires_at,
                now,
                1,
            ),
        )
        connection.execute(
            "INSERT INTO authorization_admin.effective_grants VALUES"
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                grant_id,
                PRINCIPAL,
                NAMESPACE,
                SECURITY_DOMAIN,
                grant.owner,
                grant.action,
                grant.exact_resource,
                now,
                expires_at,
                1,
            ),
        )
    seed_record = {
        "command_id": str(queued.command.command_id),
        "attempt_id": str(identity.attempt.attempt_id),
        "namespace": NAMESPACE,
        "security_domain": SECURITY_DOMAIN,
        "generation_digest": generation_digest,
    }
    (artifact_dir / "seed.json").write_text(json.dumps(seed_record, sort_keys=True))
    authority.close()
    repository.pool.close()
    print(json.dumps(seed_record, sort_keys=True))


def worker() -> None:
    from agent_operator.native_dispatch_reconciler import (
        build_native_dispatch_from_environment,
    )

    assembly = build_native_dispatch_from_environment()
    if assembly is None:
        raise RuntimeError("REL_317_NATIVE_DISPATCH_NOT_CONFIGURED")
    try:
        result = assembly.worker.run_once()
        print(json.dumps({"state": result.state, "command_id": result.command_id}))
        if result.state != "SUCCEEDED":
            raise RuntimeError(f"REL_317_NATIVE_L3_{result.state}")
    finally:
        assembly.close()


def readback(database_url: str, artifact_dir: Path) -> None:
    seed_record = json.loads((artifact_dir / "seed.json").read_text())
    with psycopg.connect(database_url, row_factory=psycopg.rows.dict_row) as connection:
        command = connection.execute(
            "SELECT command_id,state,kubernetes_task_name,kubernetes_task_uid,"
            "claim_generation,worker_id FROM "
            "execution_authority.native_dispatch_commands "
            "WHERE command_id=%s",
            (seed_record["command_id"],),
        ).fetchone()
        facts = connection.execute(
            "SELECT kind,ordinal FROM execution_authority.native_dispatch_facts "
            "WHERE command_id=%s ORDER BY ordinal",
            (seed_record["command_id"],),
        ).fetchall()
        attempt = connection.execute(
            "SELECT control_state FROM execution_authority.attempts "
            "WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
            (NAMESPACE, SECURITY_DOMAIN, seed_record["attempt_id"]),
        ).fetchone()
        evidence_count = connection.execute(
            "SELECT count(*) AS count FROM execution_authority.execution_evidence "
            "WHERE platform_execution_identity=%s",
            (seed_record["attempt_id"],),
        ).fetchone()["count"]
        outcome_count = connection.execute(
            "SELECT count(*) AS count FROM execution_authority.outcomes "
            "WHERE record->>'attempt_id'=%s "
            "AND record->>'technical'='true' "
            "AND record->>'business_problem_resolved'='false'",
            (seed_record["attempt_id"],),
        ).fetchone()["count"]
        ledgers = {
            "execution": connection.execute(
                "SELECT version,checksum,adapter FROM "
                "execution_authority.schema_migrations"
            ).fetchall(),
            "native": connection.execute(
                "SELECT version,checksum,adapter FROM "
                "native_execution_dispatch.schema_migrations"
            ).fetchall(),
            "authority": connection.execute(
                "SELECT version,checksum,adapter FROM "
                "authorization_admin.schema_migrations"
            ).fetchall(),
        }
    result = {
        "seed": seed_record,
        "command": command,
        "facts": facts,
        "attempt": attempt,
        "evidence_count": evidence_count,
        "outcome_count": outcome_count,
        "ledgers": ledgers,
    }
    (artifact_dir / "postgres-readback.json").write_text(
        json.dumps(result, default=str, indent=2, sort_keys=True)
    )
    print(json.dumps(result, default=str, sort_keys=True))
    if (
        command is None
        or command["state"] != "SUCCEEDED"
        or attempt != {"control_state": "SUCCEEDED"}
        or evidence_count != 1
        or outcome_count != 1
    ):
        raise RuntimeError("REL_317_NATIVE_L3_READBACK_FAILED")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "worker", "readback"))
    parser.add_argument(
        "--database-url", default=os.environ.get("REL_317_DATABASE_URL")
    )
    parser.add_argument("--cluster-database-url")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "worker":
        worker()
    elif not args.database_url:
        raise RuntimeError("REL_317_DATABASE_URL_REQUIRED")
    elif args.mode == "seed":
        if not args.cluster_database_url:
            raise RuntimeError("REL_317_CLUSTER_DATABASE_URL_REQUIRED")
        seed(args.database_url, args.cluster_database_url, args.artifact_dir)
    else:
        readback(args.database_url, args.artifact_dir)


if __name__ == "__main__":
    main()
