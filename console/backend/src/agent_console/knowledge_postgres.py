# ruff: noqa: E501
"""PostgreSQL primary adapter for authoritative Knowledge continuity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.knowledge_repository import (
    KnowledgeConflict,
    KnowledgeNotFound,
    KnowledgeRepositoryError,
    KnowledgeScope,
)

ADAPTER = "knowledge-postgresql-v1"
SCHEMA_VERSION = 1


class PostgresKnowledgeRepository:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
    ) -> None:
        if not database_url:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        try:
            self.pool = ConnectionPool(
                database_url,
                min_size=min_pool_size,
                max_size=max_pool_size,
                timeout=timeout,
                kwargs={"row_factory": dict_row, "autocommit": False},
                open=True,
            )
            self.pool.wait(timeout=timeout)
        except Exception as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '5s'")
                connection.execute("SET LOCAL lock_timeout = '3s'")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM knowledge_operation.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO knowledge_operation.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (SCHEMA_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif (
                    row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise KnowledgeRepositoryError("KNOWLEDGE_SCHEMA_INCOMPATIBLE")
        except KnowledgeRepositoryError:
            raise
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT checksum,adapter FROM knowledge_operation.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if (
                    row is None
                    or row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise KnowledgeRepositoryError("KNOWLEDGE_SCHEMA_INCOMPATIBLE")
        except KnowledgeRepositoryError:
            raise
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    def get(self, scope: KnowledgeScope, knowledge_id: str) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    (scope.namespace, scope.security_domain, knowledge_id),
                ).fetchone()
                if row is None:
                    raise KnowledgeNotFound("KNOWLEDGE_NOT_FOUND")
                return row["record"]
        except KnowledgeNotFound:
            raise
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    def list(self, scope: KnowledgeScope) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as connection:
                rows = connection.execute(
                    "SELECT record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s ORDER BY knowledge_id LIMIT 200",
                    (scope.namespace, scope.security_domain),
                ).fetchall()
                return [row["record"] for row in rows]
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        params = (record["namespace"], record["securityDomain"], record["knowledgeId"])
        try:
            with self.pool.connection() as connection, connection.transaction():
                if connection.execute(
                    "SELECT 1 FROM knowledge_operation.purge_tombstones WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    params,
                ).fetchone():
                    raise KnowledgeConflict("KNOWLEDGE_CONFLICT")
                connection.execute(
                    "INSERT INTO knowledge_operation.knowledge(namespace,security_domain,knowledge_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (*params, record["aggregateVersion"], json.dumps(record)),
                )
                self._insert_fact(connection, record, 1, record["facts"][0])
            return record
        except KnowledgeConflict:
            raise
        except PsycopgError as exc:
            raise KnowledgeConflict("KNOWLEDGE_CONFLICT") from exc

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "UPDATE knowledge_operation.knowledge SET aggregate_version=%s,record=%s::jsonb,updated_at=now() WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s AND aggregate_version=%s RETURNING knowledge_id",
                    (
                        record["aggregateVersion"],
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["knowledgeId"],
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise KnowledgeConflict("STALE_KNOWLEDGE")
                self._insert_fact(connection, record, len(record["facts"]) + 1, fact)
                record["facts"] = [*record["facts"], fact]
                connection.execute(
                    "UPDATE knowledge_operation.knowledge SET record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    (
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["knowledgeId"],
                    ),
                )
            return record
        except KnowledgeConflict:
            raise
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _insert_fact(
        connection: Any, record: dict[str, Any], ordinal: int, fact: dict[str, Any]
    ) -> None:
        connection.execute(
            "INSERT INTO knowledge_operation.lifecycle_facts(namespace,security_domain,knowledge_id,ordinal,fact_id,fact) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                record["namespace"],
                record["securityDomain"],
                record["knowledgeId"],
                ordinal,
                fact["factId"],
                json.dumps(fact),
            ),
        )

    def tombstone(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "SELECT knowledge_id FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s AND aggregate_version=%s FOR UPDATE",
                    (
                        scope.namespace,
                        scope.security_domain,
                        knowledge_id,
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise KnowledgeConflict("STALE_KNOWLEDGE")
                connection.execute(
                    "DELETE FROM knowledge_operation.lifecycle_facts WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    (scope.namespace, scope.security_domain, knowledge_id),
                )
                connection.execute(
                    "DELETE FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    (scope.namespace, scope.security_domain, knowledge_id),
                )
                connection.execute(
                    "INSERT INTO knowledge_operation.purge_tombstones(namespace,security_domain,knowledge_id,tombstone) VALUES (%s,%s,%s,%s::jsonb)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        knowledge_id,
                        json.dumps(tombstone),
                    ),
                )
        except KnowledgeConflict:
            raise
        except PsycopgError as exc:
            raise KnowledgeRepositoryError("KNOWLEDGE_STORAGE_UNAVAILABLE") from exc
