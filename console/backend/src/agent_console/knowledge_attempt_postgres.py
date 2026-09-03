# ruff: noqa: E501
"""PostgreSQL adapter for immutable Attempt/Knowledge bindings and Evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.knowledge_attempt_retrieval import (
    AttemptContext,
    AttemptKnowledgeFailure,
)
from agent_console.knowledge_repository import KnowledgeScope


class PostgresAttemptKnowledgeEvidenceRepository:
    def __init__(
        self, database_url: str, *, migration_path: Path, timeout: float = 5
    ) -> None:
        self.migration_path = migration_path
        self.pool = ConnectionPool(
            database_url,
            min_size=1,
            max_size=4,
            timeout=timeout,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        self.pool.wait(timeout=timeout)

    def migrate(self) -> None:
        checksum = hashlib.sha256(self.migration_path.read_bytes()).hexdigest()
        with self.pool.connection() as connection, connection.transaction():
            connection.execute(self.migration_path.read_text())
            row = connection.execute(
                "SELECT checksum FROM knowledge_attempt.schema_migrations WHERE version=12"
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO knowledge_attempt.schema_migrations(version,checksum,adapter) VALUES (12,%s,'knowledge-attempt-postgresql-v1')",
                    (checksum,),
                )
            elif row["checksum"] != checksum:
                raise AttemptKnowledgeFailure("KNOWLEDGE_ATTEMPT_SCHEMA_INCOMPATIBLE")

    def get_attempt(
        self, scope: KnowledgeScope, attempt_id: str
    ) -> AttemptContext | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT a.record,ai.agent_instance_id FROM execution_authority.attempts a LEFT JOIN execution_authority.placement_requests pr USING(namespace,security_domain,attempt_id) LEFT JOIN execution_authority.agent_instances ai ON ai.namespace=pr.namespace AND ai.security_domain=pr.security_domain AND ai.agent_instance_id=pr.agent_instance_id WHERE a.namespace=%s AND a.security_domain=%s AND a.attempt_id=%s LIMIT 1",
                (scope.namespace, scope.security_domain, attempt_id),
            ).fetchone()
        if row is None:
            return None
        return AttemptContext(
            attempt_id,
            row["record"]["assignment"]["digital_employee_instance_id"],
            row["agent_instance_id"],
            scope.namespace,
            scope.security_domain,
        )

    def _append(
        self, table: str, id_column: str, record: dict[str, Any]
    ) -> dict[str, Any]:
        identity = record[id_column]
        if table == "bindings":
            columns = "binding_id,attempt_id,knowledge_id,digest,record"
            values = (
                identity,
                record["attemptId"],
                record["knowledgeId"],
                record["digest"],
                json.dumps(record),
            )
        else:
            columns = "evidence_id,attempt_id,binding_id,digest,record"
            values = (
                identity,
                record["attemptId"],
                record["bindingId"],
                record["evidenceDigest"],
                json.dumps(record),
            )
        with self.pool.connection() as connection, connection.transaction():
            connection.execute(
                f"INSERT INTO knowledge_attempt.{table}(namespace,security_domain,{columns}) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT DO NOTHING",
                (
                    record["namespace"],
                    record["securityDomain"],
                    *values,
                ),
            )
            row = connection.execute(
                f"SELECT record FROM knowledge_attempt.{table} WHERE namespace=%s AND security_domain=%s AND {self._snake(id_column)}=%s",
                (record["namespace"], record["securityDomain"], identity),
            ).fetchone()
            if row is None or row["record"] != record:
                raise AttemptKnowledgeFailure("KNOWLEDGE_REPLAY_CONFLICT")
        return record

    @staticmethod
    def _snake(value: str) -> str:
        return "binding_id" if value == "bindingId" else "evidence_id"

    def append_binding(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._append("bindings", "bindingId", record)

    def append_evidence(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._append("retrieval_evidence", "evidenceId", record)

    def get_evidence(
        self, scope: KnowledgeScope, evidence_id: str
    ) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM knowledge_attempt.retrieval_evidence WHERE namespace=%s AND security_domain=%s AND evidence_id=%s",
                (scope.namespace, scope.security_domain, evidence_id),
            ).fetchone()
        return None if row is None else row["record"]
