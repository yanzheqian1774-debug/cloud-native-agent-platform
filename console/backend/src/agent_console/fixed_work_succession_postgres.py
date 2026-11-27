"""Additive source succession storage; only an enclosing owner may write facts."""

import hashlib
from pathlib import Path

from .fixed_work_succession import require
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

MIGRATION = Path(__file__).parents[2] / "migrations/0079_fixed_work_successions.sql"
SCOPE = ("namespace", "security_domain")
WORK = (*SCOPE, "work_id", "revision_id")
STRUCTURE = (
    Table(
        "fixed_work_successions.schema_migrations",
        LEDGER_COLUMNS,
        (primary("version"),),
    ),
    Table(
        "fixed_work_successions.transitions",
        columns(
            *(
                (k, "text")
                for k in (
                    *SCOPE,
                    "logical_work_id",
                    "subject_id",
                    "conversation_id",
                    "predecessor_work_id",
                    "predecessor_revision_id",
                    "work_id",
                    "revision_id",
                    "command_id",
                    "payload_digest",
                    "digest",
                )
            ),
            ("ordinal", "bigint"),
            ("record", "jsonb"),
        ),
        (
            primary(*SCOPE, "logical_work_id", "ordinal"),
            unique(*SCOPE, "subject_id", "command_id"),
            unique(*SCOPE, "predecessor_work_id", "predecessor_revision_id"),
            unique(*WORK),
            unique(*SCOPE, "conversation_id", "ordinal"),
            foreign(
                (*SCOPE, "predecessor_work_id", "predecessor_revision_id"),
                "fixed_work_authoring.revisions",
                WORK,
            ),
            foreign(WORK, "fixed_work_authoring.revisions", WORK),
        ),
        ("immutable_fixed_work_successions",),
    ),
    Table(
        "fixed_work_successions.bindings",
        columns(
            *(
                (k, "text")
                for k in (
                    *WORK,
                    "subject_id",
                    "conversation_id",
                    "command_id",
                    "digest",
                )
            ),
            ("record", "jsonb"),
        ),
        (
            primary(*WORK),
            unique(*SCOPE, "subject_id", "command_id"),
            foreign(WORK, "fixed_work_successions.transitions", WORK),
        ),
        ("immutable_fixed_work_successor_bindings",),
    ),
)


def available(c):
    return (
        c.execute(
            "SELECT to_regclass('fixed_work_successions.schema_migrations') relation"
        ).fetchone()["relation"]
        is not None
    )


def compatible(c):
    rows = c.execute(
        "SELECT version,checksum,adapter FROM fixed_work_successions.schema_migrations"
    ).fetchall()
    require(
        rows
        == [
            {
                "version": 79,
                "checksum": hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
                "adapter": "fixed-work-succession-v1",
            }
        ]
        and schema_is_compatible(c, STRUCTURE),
        "SCHEMA_INCOMPATIBLE",
    )


def migrate(c):
    c.execute("SELECT pg_advisory_xact_lock(2760079)")
    if not available(c):
        c.execute(MIGRATION.read_text())
        c.execute(
            "INSERT INTO fixed_work_successions.schema_migrations VALUES(79,%s,%s)",
            (
                hashlib.sha256(MIGRATION.read_bytes()).hexdigest(),
                "fixed-work-succession-v1",
            ),
        )
    compatible(c)


def _rows(c, scope, *, work_id=None, conversation=None, team=None):
    """Retained facts are validated even when new transitions are disabled."""
    if not available(c):
        return []
    compatible(c)
    require(
        sum(v is not None for v in (work_id, conversation, team)) == 1,
        "CHAIN_SELECTOR_REQUIRED",
    )
    parameters = [*scope, *scope]
    if work_id is not None:
        selection = "(work_id=%s OR predecessor_work_id=%s)"
        parameters.extend((work_id, work_id))
    elif conversation is not None:
        selection = "conversation_id=%s"
        parameters.append(conversation)
    else:
        # Only chains attached to a team the caller already has exact READ for.
        selection = (
            "EXISTS (SELECT 1 FROM fixed_work_authoring.heads r "
            "WHERE r.namespace=t.namespace AND r.security_domain=t.security_domain "
            "AND r.team_id=%s AND r.team_revision_id=%s AND r.team_digest=%s "
            "AND (r.work_id=t.work_id "
            "OR r.work_id=t.predecessor_work_id)"
            ")"
        )
        parameters.extend(team)
    result = c.execute(
        "SELECT * FROM fixed_work_successions.transitions WHERE namespace=%s "
        "AND security_domain=%s AND logical_work_id IN "
        "(SELECT t.logical_work_id FROM fixed_work_successions.transitions t "
        "WHERE t.namespace=%s AND t.security_domain=%s AND " + selection + ") "
        "ORDER BY logical_work_id,ordinal",
        parameters,
    ).fetchall()
    from . import fixed_work_authoring_postgres as authoring
    from .digital_employee_definition import digest

    chains = {}
    for row in result:
        v = row["record"]
        require(isinstance(v, dict) and digest(v) == row["digest"], "RECORD_CHANGED")
        before, after = v["predecessor"], v["work"]
        require(
            v["schemaVersion"] == "fixed-work-succession.v1"
            and (row["namespace"], row["security_domain"]) == tuple(scope)
            and v["scope"] == list(scope)
            and row["logical_work_id"] == v["logicalWorkId"]
            and row["ordinal"] == v["ordinal"]
            and row["subject_id"] == v["subjectId"]
            and row["conversation_id"] == v["conversationId"]
            and row["command_id"] == v["commandId"]
            and row["payload_digest"] == v["payloadDigest"]
            and row["predecessor_work_id"] == before["resource_id"]
            and row["predecessor_revision_id"] == before["revision_id"]
            and row["work_id"] == after["resource_id"]
            and row["revision_id"] == after["revision_id"]
            and v["effectivePoint"] == "BEFORE_FIRST_TARGET_ONLY"
            and v["executionEnabled"] is False,
            "RECORD_CHANGED",
        )
        old = authoring.read(c, scope, before["resource_id"], before["revision_id"])
        new = authoring.read(c, scope, after["resource_id"], after["revision_id"])
        require(
            old["digest"] == before["digest"] and new["digest"] == after["digest"],
            "WORK_CHANGED",
        )
        previous = chains.get(row["logical_work_id"])
        if previous:
            require(
                row["ordinal"] == previous["ordinal"] + 1
                and before == previous["record"]["work"]
                and v["predecessorTransitionDigest"] == previous["digest"]
                and row["conversation_id"] == previous["conversation_id"]
                and row["subject_id"] == previous["subject_id"],
                "CHAIN_CHANGED",
            )
            h = previous["record"]["handoff"]
        else:
            require(
                row["ordinal"] == 1
                and row["logical_work_id"] == before["resource_id"]
                and v["predecessorTransitionDigest"] is None,
                "CHAIN_CHANGED",
            )
            original = c.execute(
                "SELECT * FROM fixed_work_sources.handoffs WHERE "
                "namespace=%s AND security_domain=%s "
                "AND work_id=%s AND revision_id=%s",
                (*scope, before["resource_id"], before["revision_id"]),
            ).fetchone()
            require(
                original is not None
                and digest(original["record"]) == original["digest"]
                and original["namespace"] == scope[0]
                and original["security_domain"] == scope[1]
                and original["record"]["schemaVersion"] == "fixed-work-conversation.v1"
                and original["subject_id"] == original["record"]["subjectId"]
                and original["conversation_id"] == original["record"]["conversationId"]
                and original["command_id"] == original["record"]["commandId"]
                and original["work_id"] == original["record"]["work"]["resource_id"]
                and original["revision_id"]
                == original["record"]["work"]["revision_id"],
                "ANCHOR_CHANGED",
            )
            h = original["record"]
        require(
            digest(h) == v["predecessorHandoffDigest"]
            and h["work"] == before
            and h["subjectId"] == v["subjectId"]
            and h["conversationId"] == v["conversationId"],
            "ANCHOR_CHANGED",
        )
        from .execution_domain import ScopeIdentity
        from .fixed_work_succession import SuccessionCommand, preview
        from .team_definition_postgres import PostgresTeamDefinitionRepository as Teams

        command = SuccessionCommand.model_validate(v["command"])
        require(
            digest(command.model_dump(mode="json")) == v["payloadDigest"]
            and command.commandId == v["commandId"]
            and command.predecessor.model_dump(mode="json") == before
            and command.predecessorHandoffDigest == digest(h),
            "COMMAND_CHANGED",
        )
        old_team = old["record"]["team"]
        new_team = new["record"]["team"]
        expected = preview(
            old,
            {"record": h, "digest": digest(h)},
            Teams.read(
                c, ScopeIdentity(*scope), old_team["teamId"], old_team["revisionId"]
            ),
            Teams.read(
                c, ScopeIdentity(*scope), new_team["teamId"], new_team["revisionId"]
            ),
            v["subjectId"],
            v["conversationId"],
        )
        from .fixed_work_succession_members import compositions

        expected["employeeCompositions"] = compositions(c, scope, expected)
        require(
            v["preview"] == expected
            and v["previewDigest"] == command.previewDigest == digest(expected)
            and command.team.model_dump(mode="json")
            == {
                "resource_id": new_team["teamId"],
                "revision_id": new_team["revisionId"],
                "digest": new_team["digest"],
            },
            "PREVIEW_CHANGED",
        )
        nh = v["handoff"]
        require(
            nh
            == {
                "schemaVersion": "fixed-work-conversation.v2",
                "work": after,
                "team": new["record"]["team"],
                "subjectId": v["subjectId"],
                "conversationId": v["conversationId"],
                "commandId": v["commandId"],
                "instructionDigest": digest(new["record"]["instruction"]),
                "mode": "TARGET_REVIEW_ONLY",
                "executionEnabled": False,
                "logicalWorkId": v["logicalWorkId"],
                "predecessorHandoffDigest": digest(h),
            },
            "HANDOFF_CHANGED",
        )
        require(
            all(
                old["record"][k] == new["record"][k]
                for k in ("title", "instruction", "trigger", "createdBy")
            ),
            "PRESERVED_CONFIGURATION_CHANGED",
        )
        chains[row["logical_work_id"]] = row
    return result


def transition(c, scope, work_id, revision_id):
    matches = [
        r
        for r in rows(c, scope, work_id=work_id)
        if (r["work_id"], r["revision_id"]) == (work_id, revision_id)
    ]
    require(len(matches) <= 1, "CHAIN_AMBIGUOUS")
    return matches[0] if matches else None


def require_current(c, scope, work_id, revision_id=None):
    # A physical predecessor is retired as a whole, including its older revisions.
    require(
        not any(
            r["predecessor_work_id"] == work_id for r in rows(c, scope, work_id=work_id)
        ),
        "SUPERSEDED",
    )


def _source(c, scope, table, work_id, revision_id):
    row = transition(c, scope, work_id, revision_id)
    if row is None:
        return None
    from .digital_employee_definition import digest

    if table == "handoffs":
        v = row["record"]["handoff"]
        return {
            **{
                k: row[k]
                for k in (
                    "namespace",
                    "security_domain",
                    "work_id",
                    "revision_id",
                    "subject_id",
                    "conversation_id",
                    "command_id",
                )
            },
            "record": v,
            "digest": digest(v),
        }
    require(table == "bindings", "TABLE_INVALID")
    result = c.execute(
        "SELECT * FROM fixed_work_successions.bindings WHERE namespace=%s "
        "AND security_domain=%s "
        "AND work_id=%s AND revision_id=%s",
        (*scope, work_id, revision_id),
    ).fetchone()
    if result:
        v = result["record"]
        require(
            digest(v) == result["digest"]
            and result["namespace"] == scope[0]
            and result["security_domain"] == scope[1]
            and result["work_id"] == work_id
            and result["revision_id"] == revision_id
            and v["schemaVersion"] == "fixed-work-confirmed-source.v2"
            and v["work"] == row["record"]["work"]
            and v["handoffDigest"] == digest(row["record"]["handoff"])
            and v["subjectId"] == result["subject_id"] == row["subject_id"]
            and v["conversationId"]
            == result["conversation_id"]
            == row["conversation_id"]
            and v["commandId"] == result["command_id"],
            "BINDING_CHANGED",
        )
    return result


def append_binding(c, scope, value):
    from psycopg.types.json import Jsonb

    from .digital_employee_definition import digest

    work = value["work"]
    require_current(c, scope, work["resource_id"], work["revision_id"])
    row = transition(c, scope, work["resource_id"], work["revision_id"])
    require(row is not None, "TRANSITION_REQUIRED")
    old = source(c, scope, "bindings", work["resource_id"], work["revision_id"])
    if old:
        require(old["record"] == value, "COMMAND_CONFLICT")
        return old
    require(
        value["schemaVersion"] == "fixed-work-confirmed-source.v2"
        and value["handoffDigest"] == digest(row["record"]["handoff"]),
        "BINDING_CHANGED",
    )
    c.execute(
        "INSERT INTO fixed_work_successions.bindings "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope,
            work["resource_id"],
            work["revision_id"],
            value["subjectId"],
            value["conversationId"],
            value["commandId"],
            digest(value),
            Jsonb(value),
        ),
    )
    return source(c, scope, "bindings", work["resource_id"], work["revision_id"])


def conversation_source(c, scope, conversation):
    matches = [
        r
        for r in rows(c, scope, conversation=conversation)
        if r["conversation_id"] == conversation
    ]
    if not matches:
        return None
    last = matches[-1]
    require(len({r["logical_work_id"] for r in matches}) == 1, "CHAIN_AMBIGUOUS")
    return source(c, scope, "handoffs", last["work_id"], last["revision_id"])


def rows(c, scope, **selector):
    from .workbench_owner_authorization import WorkbenchOwnerError

    try:
        return _rows(c, scope, **selector)
    except WorkbenchOwnerError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WorkbenchOwnerError("FIXED_WORK_SUCCESSION_RECORD_INVALID", 503) from exc


def lock_writes(c, scope):
    """Same-scope authoring writes serialize before work/command locks.

    Needed only with installed 0079, to compose an old-work lock and the original
    SAVE's new-work/command locks without reversing either writer's lock order.
    """
    if available(c):
        from .digital_employee_definition import digest

        c.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,79))",
            (digest(("authoring-succession", *scope)),),
        )


def source(c, scope, table, work_id, revision_id):
    from .workbench_owner_authorization import WorkbenchOwnerError

    try:
        return _source(c, scope, table, work_id, revision_id)
    except WorkbenchOwnerError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise WorkbenchOwnerError("FIXED_WORK_SUCCESSION_RECORD_INVALID", 503) from exc
