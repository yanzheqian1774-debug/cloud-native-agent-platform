# ruff: noqa: E501 -- Exact scoped owner SQL.
"""Immutable correction facts in existing authority storage; no lifecycle mutation."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .ontology_action_correction_policy import require
from .resource_use_domain import canonical_digest


def migrate(repository):
    path = Path(__file__).parents[2] / "migrations/0072_ontology_action_correction.sql"
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240072)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS authorization_admin.ontology_correction_migrations (version integer PRIMARY KEY,checksum text NOT NULL)"
        )
        rows = c.execute(
            "SELECT version,checksum FROM authorization_admin.ontology_correction_migrations ORDER BY version"
        ).fetchall()
        if rows:
            require(
                rows == [dict(version=72, checksum=checksum)], "SCHEMA_INCOMPATIBLE"
            )
            return
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO authorization_admin.ontology_correction_migrations VALUES(72,%s)",
            (checksum,),
        )


def read(c, admission):
    row = c.execute(
        "SELECT record,record_digest FROM authorization_admin.ontology_action_corrections WHERE admission_id=%s",
        (admission,),
    ).fetchone()
    if row:
        require(
            canonical_digest(row["record"]) == row["record_digest"], "RECEIPT_CORRUPT"
        )
    return row


def append(c, policy, key, record):
    old = read(c, policy.admissionId)
    if old:
        require(old["record"] == record, "CONFLICT")
        return old
    value = canonical_digest(record)
    c.execute(
        "INSERT INTO authorization_admin.ontology_action_corrections (admission_id,namespace,security_domain,subject_id,plan_id,plan_version,plan_digest,request_key,record_digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            policy.admissionId,
            policy.tenantId,
            policy.securityDomain,
            policy.subjectId,
            policy.plan.resource_id,
            int(policy.plan.revision_id),
            policy.plan.digest,
            key,
            value,
            Jsonb(record),
        ),
    )
    return dict(record=record, record_digest=value)


def require_no_effect(c, scope, plan, ready):
    """Under original Plan lock. Reject any preparation/partial receipt, not just Run."""
    from .resource_use_domain import stable_id
    from .task_member_binding import resource_groups

    groups = resource_groups(
        [
            dict(
                kind=r["kind"],
                identity=r["reference"]["resource_id"],
                revisionId=r["reference"]["revision_id"],
                digest=r["reference"]["digest"],
            )
            for r in ready["resources"]
        ]
    )
    from .readonly_instance_assembly import assembly_seed

    seed = assembly_seed(
        scope, plan.digest, ready["assembly"]["definition"]["digest"], groups
    )
    ids = [
        stable_id("prepared-readonly-instance", seed, role)
        for role in ("root", "analyst")
    ]
    for table, column, values in (
        ("digital_employee_instances", "digital_employee_instance_id", ids),
        (
            "runtime_instances",
            "runtime_instance_id",
            [stable_id("prepared-readonly-runtime", seed)],
        ),
        (
            "agent_instances",
            "agent_instance_id",
            [stable_id("prepared-readonly-agent", seed)],
        ),
    ):
        require(
            not c.execute(
                f"SELECT 1 FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND {column}=ANY(%s) LIMIT 1",
                (scope.namespace, scope.security_domain, values),
            ).fetchone(),
            "PARTIAL_ASSEMBLY",
        )
    require(
        not c.execute(
            "SELECT 1 FROM execution_authority.plans WHERE namespace=%s AND security_domain=%s AND (plan_id=%s OR plan_digest=%s) LIMIT 1",
            (scope.namespace, scope.security_domain, plan.plan_id, plan.digest),
        ).fetchone(),
        "EXISTING_EXECUTION_PLAN",
    )
    needles = [plan.plan_id, plan.digest, plan.semantics.target.problem.resource_id]
    # jsonpath compares complete string values, never an arbitrary substring or latest row.
    for table, column in (
        ("prepared_candidates", "record"),
        ("run_preparations", "record"),
        ("workflow_runs", "record"),
        ("native_dispatch_commands", "payload"),
        ("prepared_resource_commands", "result"),
    ):
        for needle in needles:
            require(
                not c.execute(
                    f"SELECT 1 FROM execution_authority.{table} WHERE namespace=%s AND security_domain=%s AND jsonb_path_exists({column}, '$.** ? (@ == $id)', jsonb_build_object('id',%s::text)) LIMIT 1",
                    (scope.namespace, scope.security_domain, needle),
                ).fetchone(),
                "EXISTING_EXECUTION_OR_PARTIAL",
            )
    require(
        not c.execute(
            "SELECT 1 FROM execution_authority.prepared_start_commands WHERE namespace=%s AND security_domain=%s AND command_key=%s",
            (
                scope.namespace,
                scope.security_domain,
                "readonly-continuation:" + plan.digest + ":start",
            ),
        ).fetchone(),
        "EXISTING_START",
    )
