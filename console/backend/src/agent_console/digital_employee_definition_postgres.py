# ruff: noqa: E501
"""Domain-owned employee revision persistence on the existing PostgreSQL pool."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .digital_employee_definition import (
    EmployeeDefinitionError,
    EmployeeRevision,
    MemberKind,
    digest,
    identifier,
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
                "INSERT INTO digital_employee_definition.schema_migrations VALUES (14,%s,'employee-definition-v1') ON CONFLICT DO NOTHING",
                (checksum,),
            )
            if (
                conn.execute(
                    "SELECT checksum FROM digital_employee_definition.schema_migrations WHERE version=14"
                ).fetchone()["checksum"]
                != checksum
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
            if exact is None or exact.get("digest") != member.digest:
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
