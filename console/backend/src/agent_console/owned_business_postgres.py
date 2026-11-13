"""Opt-in immutable authorization facts; no dispatch, budget or business writes."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .resource_use_domain import canonical_digest


def context_binding(row):
    """Freeze validated owner provenance, never a new context or an active lease."""
    record = row["record"]
    return {
        "contextId": row["context_id"],
        "configuration": dict(record["configuration"]),
        "understandingPolicyDigest": record.get("owned_understanding_policy_digest"),
        "questionOnly": record.get("question_only") is True,
    }


def migrate(repository):
    path = Path(__file__).parents[2] / "migrations/0066_owned_business_admission.sql"
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    with repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240066)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS "
            "authorization_admin.owned_business_schema_migrations "
            "(version integer PRIMARY KEY,checksum text NOT NULL)"
        )
        rows = c.execute(
            "SELECT version,checksum FROM "
            "authorization_admin.owned_business_schema_migrations ORDER BY version"
        ).fetchall()
        if rows:
            if rows != [{"version": 66, "checksum": checksum}]:
                raise AuthorityError("OWNED_BUSINESS_SCHEMA_INCOMPATIBLE")
            return
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO authorization_admin.owned_business_schema_migrations "
            "VALUES(66,%s)",
            (checksum,),
        )


def saved(c, context, invocation_id):
    row = c.execute(
        "SELECT admission_id,record_digest,record FROM "
        "authorization_admin.owned_business_admissions WHERE tenant_id=%s "
        "AND security_domain=%s AND subject_id=%s AND invocation_id=%s",
        (
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            invocation_id,
        ),
    ).fetchone()
    if row and canonical_digest(row["record"]) != row["record_digest"]:
        raise AuthorityError("OWNED_BUSINESS_RECORD_CORRUPT")
    return row


def append(c, context, record):
    invocation = record["invocationId"]
    identity = "owned-business:" + canonical_digest(
        [
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            invocation,
        ]
    )
    # The caller already owns account/conversation/context locks. This final exact
    # admission lock serializes different client keys without creating a new scope.
    c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,3240066))", (identity,))
    previous = saved(c, context, invocation)
    if previous:
        if previous["record"] != record:
            raise AuthorityError("OWNED_BUSINESS_ADMISSION_CHANGED")
        return previous
    c.execute(
        "INSERT INTO authorization_admin.owned_business_admissions "
        "(admission_id,tenant_id,security_domain,subject_id,conversation_id,"
        "invocation_id,context_id,policy_digest,record_digest,record) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            identity,
            context.scope.tenant_id,
            context.scope.security_domain,
            context.principal_id,
            record["conversationId"],
            invocation,
            record["contextId"],
            record["policyDigest"],
            canonical_digest(record),
            Jsonb(record),
        ),
    )
    return {
        "admission_id": identity,
        "record_digest": canonical_digest(record),
        "record": record,
    }


def require_not_revoked(c, admission_id):
    # Shared with the append-only revocation writer. Effect-owner callers retain
    # this transaction lock through dispatch checks; no expired lease is renewed.
    c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,3240066))", (admission_id,)
    )
    if c.execute(
        "SELECT 1 FROM authorization_admin.owned_business_revocations "
        "WHERE admission_id=%s",
        (admission_id,),
    ).fetchone():
        raise AuthorityError("OWNED_BUSINESS_ADMISSION_REVOKED")
