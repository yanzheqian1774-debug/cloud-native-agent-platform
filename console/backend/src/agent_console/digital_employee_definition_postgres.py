# ruff: noqa: E501
"""Domain-owned employee revision persistence on the existing PostgreSQL pool."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path

from .digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeRevision,
    MemberKind,
    digest,
    identifier,
)
from .postgres_schema_compatibility import (
    LEDGER_COLUMNS,
    Table,
    columns,
    foreign,
    primary,
    schema_is_compatible,
    unique,
)

_SHA256_DIGEST = re.compile(r"(?:(?P<algorithm>sha256):)?(?P<value>[a-f0-9]{64})")
_ADAPTER = "employee-definition-v1"
_DEFINITION_KEY = ("namespace", "security_domain", "definition_id")
_REVISION_KEY = (*_DEFINITION_KEY, "revision_id")
_EMPLOYEE_FACT_ACTIONS = frozenset(
    {
        "CREATE",
        "VALIDATE",
        "APPROVE",
        "REJECT",
        "PUBLISH",
        "UNPUBLISH",
        "REVOKE_PUBLICATION",
        "DEPRECATE",
        "GRANT_MATCH",
        "DENY_MATCH",
        "REVOKE_MATCH",
    }
)
_PUBLICATION_ACTIONS = frozenset(
    {"PUBLISH", "UNPUBLISH", "REVOKE_PUBLICATION", "DEPRECATE"}
)
EMPLOYEE_DEFINITION_STRUCTURE = (
    Table(
        "digital_employee_definition.schema_migrations",
        LEDGER_COLUMNS,
        (primary("version"),),
    ),
    Table(
        "digital_employee_definition.definitions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("definition_id", "text"),
            ("aggregate_version", "bigint"),
        ),
        (primary(*_DEFINITION_KEY),),
    ),
    Table(
        "digital_employee_definition.revisions",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("definition_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
            ("record", "jsonb"),
        ),
        (
            primary(*_REVISION_KEY),
            unique(*_DEFINITION_KEY, "predecessor_revision_id"),
            foreign(
                _DEFINITION_KEY,
                "digital_employee_definition.definitions",
                _DEFINITION_KEY,
            ),
            foreign(
                (*_DEFINITION_KEY, "predecessor_revision_id"),
                "digital_employee_definition.revisions",
                _REVISION_KEY,
            ),
        ),
        ("immutable_revisions",),
    ),
    Table(
        "digital_employee_definition.facts",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("definition_id", "text"),
            ("ordinal", "bigint"),
            ("revision_id", "text"),
            ("action", "text"),
            ("revision_digest", "text"),
            ("decision_id", "text"),
            ("command_id", "text"),
            ("payload_digest", "text"),
        ),
        (
            primary(*_DEFINITION_KEY, "ordinal"),
            unique("namespace", "security_domain", "command_id"),
            foreign(
                _REVISION_KEY,
                "digital_employee_definition.revisions",
                _REVISION_KEY,
            ),
        ),
        ("immutable_facts",),
    ),
    Table(
        "digital_employee_definition.instance_bindings",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("digital_employee_instance_id", "text"),
            ("definition_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
        ),
        (
            primary("namespace", "security_domain", "digital_employee_instance_id"),
            foreign(
                _REVISION_KEY,
                "digital_employee_definition.revisions",
                _REVISION_KEY,
            ),
            foreign(
                ("namespace", "security_domain", "digital_employee_instance_id"),
                "execution_authority.digital_employee_instances",
                ("namespace", "security_domain", "digital_employee_instance_id"),
            ),
        ),
        ("immutable_instance_bindings",),
    ),
    Table(
        "digital_employee_definition.execution_bindings",
        columns(
            ("namespace", "text"),
            ("security_domain", "text"),
            ("attempt_id", "text"),
            ("digital_employee_instance_id", "text"),
            ("definition_id", "text"),
            ("revision_id", "text"),
            ("digest", "text"),
            ("plan_digest", "text"),
            ("approval_id", "text"),
            ("authorization_decision_id", "text"),
        ),
        (
            primary("namespace", "security_domain", "attempt_id"),
            foreign(
                _REVISION_KEY,
                "digital_employee_definition.revisions",
                _REVISION_KEY,
            ),
            foreign(
                ("namespace", "security_domain", "attempt_id"),
                "execution_authority.attempts",
                ("namespace", "security_domain", "attempt_id"),
            ),
            foreign(
                ("namespace", "security_domain", "digital_employee_instance_id"),
                "digital_employee_definition.instance_bindings",
                ("namespace", "security_domain", "digital_employee_instance_id"),
            ),
        ),
        ("immutable_execution_bindings",),
    ),
)


def _same_sha256_digest(left: object, right: object) -> bool:
    """Compare the two accepted SHA-256 encodings without rewriting either value."""

    def parse(value: object) -> bytes | None:
        if not isinstance(value, str):
            return None
        matched = _SHA256_DIGEST.fullmatch(value)
        if matched is None:
            return None
        # An absent algorithm is the existing compact SHA-256 representation;
        # an explicit algorithm is accepted only when it is exactly ``sha256``.
        return bytes.fromhex(matched.group("value"))

    left_value, right_value = parse(left), parse(right)
    return (
        left_value is not None
        and right_value is not None
        and hmac.compare_digest(left_value, right_value)
    )


class PostgresEmployeeDefinitionRepository:
    def __init__(self, authority):
        self.authority = authority
        self.pool = authority.pool

    def migrate(self, path: Path):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(2760014)")
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO digital_employee_definition.schema_migrations VALUES (14,%s,%s) ON CONFLICT DO NOTHING",
                (checksum, _ADAPTER),
            )
            row = conn.execute(
                "SELECT checksum,adapter FROM digital_employee_definition.schema_migrations WHERE version=14"
            ).fetchone()
            if row["checksum"] != checksum or row["adapter"] != _ADAPTER:
                raise EmployeeDefinitionError("EMPLOYEE_SCHEMA_INCOMPATIBLE")

    def compatibility(self, path: Path) -> None:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.pool.connection() as conn:
            row = conn.execute(
                "SELECT checksum,adapter FROM digital_employee_definition.schema_migrations WHERE version=14"
            ).fetchone()
            compatible = schema_is_compatible(conn, EMPLOYEE_DEFINITION_STRUCTURE)
        if (
            row is None
            or row["checksum"] != checksum
            or row["adapter"] != _ADAPTER
            or not compatible
        ):
            raise EmployeeDefinitionError("EMPLOYEE_SCHEMA_INCOMPATIBLE")

    @staticmethod
    def _key(scope, definition_id):
        return scope.namespace, scope.security_domain, identifier(definition_id)

    @staticmethod
    def _read(conn, scope, definition_id, revision_id):
        key = (scope.namespace, scope.security_domain, definition_id, revision_id)
        row = conn.execute(
            "SELECT r.record,r.digest,d.aggregate_version FROM digital_employee_definition.revisions r JOIN digital_employee_definition.definitions d USING(namespace,security_domain,definition_id) WHERE r.namespace=%s AND r.security_domain=%s AND r.definition_id=%s AND r.revision_id=%s FOR SHARE OF d",
            key,
        ).fetchone()
        if row is None:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        revision = EmployeeRevision.from_record(row["record"])
        if revision.digest != row["digest"]:
            raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT")
        facts = conn.execute(
            "SELECT action,decision_id,ordinal FROM digital_employee_definition.facts WHERE namespace=%s AND security_domain=%s AND definition_id=%s AND revision_id=%s ORDER BY ordinal",
            key,
        ).fetchall()
        actions = [f["action"] for f in facts]
        publication = next(
            (
                a
                for a in reversed(actions)
                if a in {"PUBLISH", "UNPUBLISH", "REVOKE_PUBLICATION", "DEPRECATE"}
            ),
            None,
        )
        match = next(
            (
                a
                for a in reversed(actions)
                if a in {"GRANT_MATCH", "DENY_MATCH", "REVOKE_MATCH"}
            ),
            None,
        )
        return {
            "revision": row["record"],
            "digest": row["digest"],
            "aggregateVersion": row["aggregate_version"],
            "facts": facts,
            "published": publication == "PUBLISH",
            "matchable": publication == "PUBLISH" and match == "GRANT_MATCH",
        }

    def read(self, scope, definition_id, revision_id):
        with self.pool.connection() as conn:
            return self._read(
                conn, scope, identifier(definition_id), identifier(revision_id)
            )

    @staticmethod
    def read_revision_for_workbench(
        connection,
        scope,
        definition_id,
        revision_id,
        *,
        authorized,
    ):
        """Read one authorized immutable revision on the caller transaction."""
        if not authorized:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        key = (
            scope.namespace,
            scope.security_domain,
            identifier(definition_id),
            identifier(revision_id),
        )
        row = connection.execute(
            "SELECT r.record,r.digest FROM digital_employee_definition.revisions r "
            "JOIN digital_employee_definition.definitions d "
            "USING(namespace,security_domain,definition_id) "
            "WHERE r.namespace=%s AND r.security_domain=%s "
            "AND r.definition_id=%s AND r.revision_id=%s FOR SHARE OF d",
            key,
        ).fetchone()
        if row is None:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        try:
            revision = EmployeeRevision.from_record(row["record"])
        except (EmployeeDefinitionError, KeyError, TypeError) as exc:
            raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT") from exc
        if revision.digest != row["digest"]:
            raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT")
        facts = connection.execute(
            "SELECT action,revision_digest,ordinal FROM "
            "digital_employee_definition.facts WHERE namespace=%s "
            "AND security_domain=%s AND definition_id=%s AND revision_id=%s "
            "ORDER BY ordinal",
            key,
        ).fetchall()
        if not facts:
            raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT")
        for fact in facts:
            if fact["action"] not in _EMPLOYEE_FACT_ACTIONS or not _same_sha256_digest(
                fact["revision_digest"], row["digest"]
            ):
                raise EmployeeDefinitionError("EMPLOYEE_RECORD_CORRUPT")
        publication = next(
            (
                fact["action"]
                for fact in reversed(facts)
                if fact["action"] in _PUBLICATION_ACTIONS
            ),
            None,
        )
        return {
            "revision": row["record"],
            "digest": row["digest"],
            "publicationState": (
                "PUBLISHED" if publication == "PUBLISH" else "NOT_PUBLISHED"
            ),
        }

    def list_revisions_for_workbench(
        self,
        connection,
        scope,
        *,
        after,
        limit,
        authorized,
    ):
        """Read one bounded keyset page on the caller transaction."""
        if not authorized:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        if not isinstance(limit, int) or not 1 <= limit <= 201:
            raise EmployeeDefinitionError("INVALID_PAGE_SIZE")
        parameters = [scope.namespace, scope.security_domain]
        after_clause = ""
        if after is not None:
            if not isinstance(after, tuple) or len(after) != 2:
                raise EmployeeDefinitionError("INVALID_CURSOR")
            after_clause = (
                'AND (definition_id COLLATE "C", revision_id COLLATE "C") > (%s, %s) '
            )
            parameters.extend((identifier(after[0]), identifier(after[1])))
        parameters.append(limit)
        rows = connection.execute(
            "SELECT definition_id,revision_id FROM "
            "digital_employee_definition.revisions WHERE namespace=%s "
            "AND security_domain=%s "
            + after_clause
            + 'ORDER BY definition_id COLLATE "C", revision_id COLLATE "C" '
            "LIMIT %s",
            tuple(parameters),
        ).fetchall()
        return [
            self.read_revision_for_workbench(
                connection,
                scope,
                row["definition_id"],
                row["revision_id"],
                authorized=True,
            )
            for row in rows
        ]

    def list(self, scope):
        with self.pool.connection() as conn:
            rows = conn.execute(
                "SELECT definition_id,revision_id FROM "
                "digital_employee_definition.revisions WHERE namespace=%s "
                "AND security_domain=%s ORDER BY definition_id,revision_id",
                (scope.namespace, scope.security_domain),
            ).fetchall()
            return [
                self._read(conn, scope, row["definition_id"], row["revision_id"])
                for row in rows
            ]

    @staticmethod
    def validate_members(conn, revision):
        tables = {
            MemberKind.AGENT: ("agent_definition.definitions", "definition_id"),
            MemberKind.KNOWLEDGE: ("knowledge_operation.knowledge", "knowledge_id"),
            MemberKind.WORKFLOW: (
                "workflow_definition.definitions",
                "workflow_definition_id",
            ),
            MemberKind.RUNTIME_PROFILE: (
                "runtime_profile.profiles",
                "runtime_profile_id",
            ),
            MemberKind.SKILL: ("skill_mcp_resource.resources", "resource_id"),
            MemberKind.MCP: ("skill_mcp_resource.resources", "resource_id"),
        }
        for member in revision.members:
            table, column = tables[member.kind]
            clause = (
                " AND kind=%s"
                if member.kind in {MemberKind.SKILL, MemberKind.MCP}
                else ""
            )
            key = (
                revision.scope.namespace,
                revision.scope.security_domain,
                member.resource_id,
            )
            if clause:
                key += (member.kind.lower(),)
            row = conn.execute(
                f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s AND {column}=%s{clause} FOR SHARE",
                key,
            ).fetchone()
            if row is None:
                raise EmployeeDefinitionError("BOUND_RESOURCE_NOT_FOUND")
            record = row["record"]
            exact = next(
                (
                    r
                    for r in record.get("revisions", [])
                    if r["revisionId"] == member.revision_id
                ),
                None,
            )
            if exact is None or not _same_sha256_digest(
                exact.get("digest"), member.digest
            ):
                raise EmployeeDefinitionError("BOUND_RESOURCE_MISMATCH")
            if (
                record.get("publishedRevisionId") != member.revision_id
                or exact.get("state") != "PUBLISHED"
                or (
                    member.kind in {MemberKind.AGENT, MemberKind.SKILL, MemberKind.MCP}
                    and record.get("enabled") is not True
                )
                or record.get("archived") is True
                or record.get("lifecycleState") in {"DEPRECATED", "ARCHIVED"}
            ):
                raise EmployeeDefinitionError("BOUND_RESOURCE_INELIGIBLE")

    @staticmethod
    def _replay(conn, scope, command_id, payload_digest):
        row = conn.execute(
            "SELECT definition_id,revision_id,payload_digest FROM digital_employee_definition.facts WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (scope.namespace, scope.security_domain, identifier(command_id)),
        ).fetchone()
        if row is not None and row["payload_digest"] != payload_digest:
            raise EmployeeDefinitionError("IDEMPOTENCY_PAYLOAD_MISMATCH")
        return row

    @staticmethod
    def _fact(
        conn,
        key,
        revision_id,
        action,
        version,
        revision_digest,
        decision_id,
        command_id,
        payload_digest,
    ):
        conn.execute(
            "INSERT INTO digital_employee_definition.facts(namespace,security_domain,definition_id,revision_id,action,ordinal,revision_digest,decision_id,command_id,payload_digest) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                revision_id,
                action,
                version,
                revision_digest,
                identifier(decision_id),
                identifier(command_id),
                payload_digest,
            ),
        )

    def create(self, revision, *, expected_version, decision_id, command_id):
        key = self._key(revision.scope, revision.definition_id)
        payload = digest([revision.record, expected_version, decision_id, "CREATE"])
        with self.pool.connection() as conn, conn.transaction():
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (json.dumps(key),),
            )
            replay = self._replay(conn, revision.scope, command_id, payload)
            if replay:
                return self._read(
                    conn, revision.scope, revision.definition_id, revision.revision_id
                )
            head = conn.execute(
                "SELECT aggregate_version FROM digital_employee_definition.definitions WHERE namespace=%s AND security_domain=%s AND definition_id=%s FOR UPDATE",
                key,
            ).fetchone()
            if (0 if head is None else head["aggregate_version"]) != expected_version:
                raise EmployeeDefinitionError("STALE_AGGREGATE_VERSION")
            if (head is None) != (revision.predecessor_revision_id is None):
                raise EmployeeDefinitionError("EXACT_PREDECESSOR_REQUIRED")
            if head is None:
                conn.execute(
                    "INSERT INTO digital_employee_definition.definitions VALUES (%s,%s,%s,1)",
                    key,
                )
            else:
                self._read(
                    conn,
                    revision.scope,
                    revision.definition_id,
                    revision.predecessor_revision_id,
                )
                conn.execute(
                    "UPDATE digital_employee_definition.definitions SET aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                    key,
                )
            conn.execute(
                "INSERT INTO digital_employee_definition.revisions VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    *key,
                    revision.revision_id,
                    revision.predecessor_revision_id,
                    revision.digest,
                    json.dumps(revision.record),
                ),
            )
            self._fact(
                conn,
                key,
                revision.revision_id,
                "CREATE",
                expected_version + 1,
                revision.digest,
                decision_id,
                command_id,
                payload,
            )
            return self._read(
                conn, revision.scope, revision.definition_id, revision.revision_id
            )

    def decide(
        self,
        scope,
        definition_id,
        revision_id,
        revision_digest,
        action,
        *,
        expected_version,
        decision_id,
        command_id,
    ):
        key = self._key(scope, definition_id)
        payload = digest(
            [
                definition_id,
                revision_id,
                revision_digest,
                action,
                expected_version,
                decision_id,
            ]
        )
        with self.pool.connection() as conn, conn.transaction():
            conn.execute(
                "SELECT aggregate_version FROM digital_employee_definition.definitions WHERE namespace=%s AND security_domain=%s AND definition_id=%s FOR UPDATE",
                key,
            )
            replay = self._replay(conn, scope, command_id, payload)
            current = self._read(conn, scope, definition_id, revision_id)
            if replay:
                return current
            if current["digest"] != revision_digest:
                raise EmployeeDefinitionError("EMPLOYEE_REVISION_MISMATCH")
            if current["aggregateVersion"] != expected_version:
                raise EmployeeDefinitionError("STALE_AGGREGATE_VERSION")
            actions = [f["action"] for f in current["facts"]]
            allowed = {
                "VALIDATE": actions == ["CREATE"],
                "APPROVE": actions[-1] == "VALIDATE",
                "REJECT": actions[-1] == "VALIDATE",
                "PUBLISH": actions[-1] == "APPROVE",
                "UNPUBLISH": current["published"],
                "REVOKE_PUBLICATION": current["published"],
                "DEPRECATE": current["published"],
                "GRANT_MATCH": current["published"],
                "DENY_MATCH": current["published"],
                "REVOKE_MATCH": current["published"],
            }
            if not allowed.get(action, False):
                raise EmployeeDefinitionError("INVALID_EMPLOYEE_TRANSITION")
            if action in {"VALIDATE", "APPROVE", "PUBLISH", "GRANT_MATCH"}:
                self.validate_members(
                    conn, EmployeeRevision.from_record(current["revision"])
                )
            conn.execute(
                "UPDATE digital_employee_definition.definitions SET aggregate_version=aggregate_version+1 WHERE namespace=%s AND security_domain=%s AND definition_id=%s AND aggregate_version=%s",
                (*key, expected_version),
            )
            self._fact(
                conn,
                key,
                revision_id,
                action,
                expected_version + 1,
                revision_digest,
                decision_id,
                command_id,
                payload,
            )
            return self._read(conn, scope, definition_id, revision_id)

    def read_for_plan(
        self,
        connection,
        scope,
        definition_id,
        revision_id,
        expected_digest,
        *,
        authorized,
    ):
        if not authorized:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        value = self._read(
            connection, scope, identifier(definition_id), identifier(revision_id)
        )
        if not value["published"] or value["digest"] != expected_digest:
            raise EmployeeDefinitionError("EMPLOYEE_PLAN_REFERENCE_INVALID")
        return value
