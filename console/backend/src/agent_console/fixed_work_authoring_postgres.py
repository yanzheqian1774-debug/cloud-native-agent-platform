"""Caller-owned transaction; additive configuration records, no execution writes."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .digital_employee_definition import digest
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)
from .workbench_owner_authorization import WorkbenchOwnerError

MIGRATION = Path(__file__).parents[2] / "migrations/0067_fixed_work_authoring.sql"
KEY = ("namespace", "security_domain", "work_id")
REV = (*KEY, "revision_id")
STRUCTURE = (
    Table(
        "fixed_work_authoring.schema_migrations", LEDGER_COLUMNS, (primary("version"),)
    ),
    Table(
        "fixed_work_authoring.heads",
        columns(
            *(
                (k, "text")
                for k in (
                    *KEY,
                    "team_id",
                    "team_revision_id",
                    "team_digest",
                    "head_revision_id",
                )
            ),
            ("aggregate_version", "bigint"),
        ),
        (primary(*KEY),),
    ),
    Table(
        "fixed_work_authoring.revisions",
        columns(*((k, "text") for k in (*REV, "digest")), ("record", "jsonb")),
        (
            primary(*REV),
            unique(*KEY, "predecessor_revision_id"),
            foreign(KEY, "fixed_work_authoring.heads", KEY),
            foreign(
                (*KEY, "predecessor_revision_id"), "fixed_work_authoring.revisions", REV
            ),
        ),
        ("immutable_revisions",),
    ),
    Table(
        "fixed_work_authoring.receipts",
        columns(
            *(
                (k, "text")
                for k in (
                    *REV,
                    "actor_id",
                    "command_id",
                    "payload_digest",
                    "decision_id",
                    "policy_digest",
                )
            ),
            ("aggregate_version", "bigint"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (
            primary("namespace", "security_domain", "actor_id", "command_id"),
            unique(*KEY, "aggregate_version"),
            foreign(REV, "fixed_work_authoring.revisions", REV),
        ),
        ("immutable_receipts",),
    ),
)


def compatibility(c):
    row = c.execute(
        "SELECT checksum,adapter FROM fixed_work_authoring.schema_migrations "
        "WHERE version=67"
    ).fetchone()
    if (
        not row
        or row["checksum"] != hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
        or row["adapter"] != "fixed-work-authoring-v1"
        or not schema_is_compatible(c, STRUCTURE)
    ):
        raise WorkbenchOwnerError("FIXED_WORK_AUTHORING_SCHEMA_INCOMPATIBLE", 503)


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(2760067)")
    c.execute(MIGRATION.read_text())
    c.execute(
        "INSERT INTO fixed_work_authoring.schema_migrations VALUES (67,%s,%s) ON "
        "CONFLICT DO NOTHING",
        (hashlib.sha256(MIGRATION.read_bytes()).hexdigest(), "fixed-work-authoring-v1"),
    )
    compatibility(c)


def read(c, scope, work_id, revision_id):
    row = c.execute(
        "SELECT r.record,r.digest,h.team_id,h.team_revision_id,h.team_digest "
        "FROM fixed_work_authoring.revisions r "
        "JOIN fixed_work_authoring.heads h USING(namespace,security_domain,work_id) "
        "WHERE r.namespace=%s AND r.security_domain=%s AND r.work_id=%s AND "
        "r.revision_id=%s",
        (*scope, work_id, revision_id),
    ).fetchone()
    if not row:
        raise WorkbenchOwnerError("FIXED_WORK_DRAFT_NOT_FOUND", 404)
    record = row["record"]
    if (
        digest(record) != row["digest"]
        or record.get("workId") != work_id
        or record.get("revisionId") != revision_id
        or record.get("state") != "DRAFT_ONLY"
        or record.get("team")
        != {
            "teamId": row["team_id"],
            "revisionId": row["team_revision_id"],
            "digest": row["team_digest"],
        }
    ):
        raise WorkbenchOwnerError("FIXED_WORK_RECORD_INCONSISTENT", 503)
    return row


def save(c, scope, actor, data, team, policy_digest, decision_id, now):
    from .fixed_work_succession_postgres import lock_writes

    lock_writes(c, scope)
    payload = digest(
        {"data": data.model_dump(mode="json"), "team": team, "actor": actor}
    )
    for key in sorted(
        (
            digest(("command", *scope, actor, data.commandId)),
            digest(("work", *scope, data.workId)),
        )
    ):
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,67))", (key,))
    from .fixed_work_succession_postgres import require_current

    require_current(c, scope, data.workId)
    prior = c.execute(
        "SELECT * FROM fixed_work_authoring.receipts WHERE namespace=%s AND "
        "security_domain=%s AND actor_id=%s AND command_id=%s",
        (*scope, actor, data.commandId),
    ).fetchone()
    if prior:
        if prior["payload_digest"] != payload:
            raise WorkbenchOwnerError("FIXED_WORK_COMMAND_CONFLICT", 409)
        return read(c, scope, prior["work_id"], prior["revision_id"]), prior[
            "aggregate_version"
        ]
    from .fixed_work_succession_postgres import rows as succession_rows

    if any(
        row["work_id"] == data.workId
        for row in succession_rows(c, scope, work_id=data.workId)
    ):
        raise WorkbenchOwnerError("FIXED_WORK_SUCCESSION_CONFIGURATION_FIXED", 409)
    head = c.execute(
        "SELECT * FROM fixed_work_authoring.heads WHERE namespace=%s AND "
        "security_domain=%s AND work_id=%s FOR UPDATE",
        (*scope, data.workId),
    ).fetchone()
    if head:
        if (head["team_id"], head["team_revision_id"], head["team_digest"]) != (
            team["teamId"],
            team["revisionId"],
            team["digest"],
        ):
            raise WorkbenchOwnerError("FIXED_WORK_TEAM_BINDING_CONFLICT", 409)
        if (
            head["aggregate_version"] != data.expectedVersion
            or head["head_revision_id"] != data.predecessorRevisionId
        ):
            raise WorkbenchOwnerError("FIXED_WORK_VERSION_CONFLICT", 409)
    elif data.expectedVersion != 0:
        raise WorkbenchOwnerError("FIXED_WORK_VERSION_CONFLICT", 409)
    version = data.expectedVersion + 1
    record = {
        "schemaVersion": "fixed-work-draft.v1",
        "state": "DRAFT_ONLY",
        "team": team,
        "workId": data.workId,
        "revisionId": data.revisionId,
        "predecessorRevisionId": data.predecessorRevisionId,
        "aggregateVersion": version,
        "title": data.title,
        "instruction": data.instruction,
        "trigger": data.trigger.model_dump(mode="json"),
        "createdBy": actor,
        "createdAt": now.isoformat(),
    }
    content_digest = digest(record)
    c.execute(
        "INSERT INTO fixed_work_authoring.heads VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(namespace,security_domain,work_id) DO UPDATE SET "
        "head_revision_id=EXCLUDED.head_revision_id,"
        "aggregate_version=EXCLUDED.aggregate_version",
        (
            *scope,
            data.workId,
            team["teamId"],
            team["revisionId"],
            team["digest"],
            data.revisionId,
            version,
        ),
    )
    c.execute(
        "INSERT INTO fixed_work_authoring.revisions VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope,
            data.workId,
            data.revisionId,
            data.predecessorRevisionId,
            content_digest,
            Jsonb(record),
        ),
    )
    c.execute(
        "INSERT INTO fixed_work_authoring.receipts VALUES "
        "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope,
            actor,
            data.commandId,
            payload,
            data.workId,
            data.revisionId,
            version,
            decision_id,
            policy_digest,
            now,
        ),
    )
    return read(c, scope, data.workId, data.revisionId), version
