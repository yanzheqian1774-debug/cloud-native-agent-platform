# ruff: noqa: E501 -- Exact scoped SQL and bounded policy predicates.
"""Append-only test intents/claims/results, separate from resource lifecycle."""

import hashlib
from pathlib import Path

from psycopg.types.json import Jsonb

from .mcp_tool_test_policy import ToolBinding, require
from .resource_use_domain import canonical_digest

PATH = Path(__file__).parents[2] / "migrations/0076_mcp_tool_tests.sql"


def compatible(c):
    rows = c.execute(
        "SELECT version,checksum FROM authorization_admin.mcp_tool_test_migrations ORDER BY version"
    ).fetchall()
    require(
        rows
        == [{"version": 76, "checksum": hashlib.sha256(PATH.read_bytes()).hexdigest()}],
        "SCHEMA_INCOMPATIBLE",
    )


def migrate(repository):
    with repository.connection_scope() as c:
        c.execute("SELECT pg_advisory_xact_lock(3240076)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS authorization_admin.mcp_tool_test_migrations(version integer PRIMARY KEY,checksum text NOT NULL)"
        )
        if c.execute(
            "SELECT 1 FROM authorization_admin.mcp_tool_test_migrations"
        ).fetchone():
            compatible(c)
            return
        c.execute(PATH.read_text())
        c.execute(
            "INSERT INTO authorization_admin.mcp_tool_test_migrations VALUES(76,%s)",
            (hashlib.sha256(PATH.read_bytes()).hexdigest(),),
        )


def scope(context):
    return (
        context.scope.tenant_id,
        context.scope.security_domain,
        context.principal_id,
    )


def lock(c, context, binding):
    c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (canonical_digest([*scope(context), binding]),),
    )


def read(c, context, key):
    row = c.execute(
        "SELECT * FROM authorization_admin.mcp_tool_test_requests WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s",
        (*scope(context), key),
    ).fetchone()
    if row:
        request = row["request"]
        try:
            binding = ToolBinding.model_validate(request["binding"])
        except (ValueError, KeyError, TypeError):
            require(False, "RECEIPT_CORRUPT")
        require(
            canonical_digest(request) == row["request_digest"]
            and (row["namespace"], row["security_domain"], row["subject_id"])
            == scope(context)
            and request.get("scope") == list(scope(context))
            and (binding.namespace, binding.securityDomain, binding.subject)
            == scope(context)
            and request.get("commandKey") == row["command_key"] == key
            and request.get("bindingDigest") == row["binding_digest"] == binding.digest
            and request.get("input") == binding.arguments,
            "RECEIPT_CORRUPT",
        )
        row["facts"] = c.execute(
            "SELECT ordinal,kind,fact,fact_digest FROM authorization_admin.mcp_tool_test_facts WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND command_key=%s ORDER BY ordinal",
            (*scope(context), key),
        ).fetchall()
        sequence = [(f["ordinal"], f["kind"]) for f in row["facts"]]
        require(
            sequence
            in ([], [(1, "DISPATCH_CLAIM")], [(1, "DISPATCH_CLAIM"), (2, "RESULT")]),
            "RECEIPT_CORRUPT",
        )
        for index, fact in enumerate(row["facts"]):
            expected = seal(row, fact["kind"])
            if index:
                expected["claimDigest"] = row["facts"][0]["fact_digest"]
            value = fact["fact"]
            require(
                canonical_digest(value) == fact["fact_digest"]
                and value.get("_seal") == expected,
                "RECEIPT_CORRUPT",
            )
            if index == 0:
                require(
                    set(value)
                    == {"_seal", "ticketDigest", "decisionId", "policyDigest"}
                    and isinstance(value["ticketDigest"], str)
                    and len(value["ticketDigest"]) == 64
                    and bool(value["decisionId"])
                    and value["policyDigest"] == request["policyDigest"],
                    "RECEIPT_CORRUPT",
                )
            else:
                require(
                    value.get("state") in {"SUCCEEDED", "TOOL_FAILED", "UNKNOWN"},
                    "RECEIPT_CORRUPT",
                )
                require(
                    (
                        value["state"] == "UNKNOWN"
                        and set(value) == {"_seal", "state", "reasonCode"}
                    )
                    or (
                        value["state"] != "UNKNOWN"
                        and set(value) == {"_seal", "state", "result"}
                        and isinstance(value["result"], dict)
                    ),
                    "RECEIPT_CORRUPT",
                )
    return row


def seal(row, kind):
    return {
        "scope": [row["namespace"], row["security_domain"], row["subject_id"]],
        "commandKey": row["command_key"],
        "bindingDigest": row["binding_digest"],
        "requestDigest": row["request_digest"],
        "kind": kind,
    }


def payload(fact):
    return {k: v for k, v in fact.items() if k != "_seal"}


def append(c, context, key, kind, fact):
    row = read(c, context, key)
    require(row is not None and "_seal" not in fact, "RECEIPT_CORRUPT")
    require(
        (kind == "DISPATCH_CLAIM" and not row["facts"])
        or (kind == "RESULT" and len(row["facts"]) == 1),
        "RECEIPT_CORRUPT",
    )
    binding = seal(row, kind)
    if kind == "RESULT":
        binding["claimDigest"] = row["facts"][0]["fact_digest"]
    fact = {**fact, "_seal": binding}
    c.execute(
        "INSERT INTO authorization_admin.mcp_tool_test_facts(namespace,security_domain,subject_id,command_key,ordinal,kind,fact,fact_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope(context),
            key,
            1 if kind == "DISPATCH_CLAIM" else 2,
            kind,
            Jsonb(fact),
            canonical_digest(fact),
        ),
    )
    read(c, context, key)


class ToolTestTargets:
    """Committed PREPARE enables exact grant discovery, never the tool call itself."""

    def is_known_exact_target(self, context, grant, *, connection=None):
        if (
            connection is None
            or grant.owner != "SKILL"
            or grant.action != "INVOKE_MCP_TOOL"
        ):
            return False
        rows = connection.execute(
            "SELECT command_key FROM authorization_admin.mcp_tool_test_requests WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND %s || binding_digest=%s",
            (*scope(context), "skill-invocation:mcp-tool-test:", grant.exact_resource),
        ).fetchall()
        return any(
            read(connection, context, r["command_key"]) is not None for r in rows
        )
