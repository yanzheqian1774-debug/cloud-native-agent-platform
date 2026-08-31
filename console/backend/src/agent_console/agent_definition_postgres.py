# ruff: noqa: E501
"""PostgreSQL primary adapter for Agent Definition continuity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.agent_definition_repository import (
    AgentDefinitionConflict,
    AgentDefinitionNotFound,
    AgentDefinitionRepositoryError,
    DefinitionScope,
)

ADAPTER = "agent-definition-postgresql-v1"
SCHEMA_VERSION = 1


class PostgresAgentDefinitionRepository:
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
            raise AgentDefinitionRepositoryError("AGENT_DEFINITION_STORAGE_UNAVAILABLE")
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
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        sql = self.migration_path.read_text()
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '5s'")
                connection.execute("SET LOCAL lock_timeout = '3s'")
                connection.execute(sql)
                row = connection.execute(
                    "SELECT checksum, adapter FROM agent_definition.schema_migrations WHERE version = %s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO agent_definition.schema_migrations(version, checksum, adapter) VALUES (%s, %s, %s)",
                        (SCHEMA_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif (
                    row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise AgentDefinitionRepositoryError(
                        "AGENT_DEFINITION_SCHEMA_INCOMPATIBLE"
                    )
        except AgentDefinitionRepositoryError:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT checksum, adapter FROM agent_definition.schema_migrations WHERE version = %s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if (
                    row is None
                    or row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise AgentDefinitionRepositoryError(
                        "AGENT_DEFINITION_SCHEMA_INCOMPATIBLE"
                    )
        except AgentDefinitionRepositoryError:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    def get(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT record FROM agent_definition.definitions WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                    (scope.namespace, scope.security_domain, definition_id),
                ).fetchone()
                if row is None:
                    raise AgentDefinitionNotFound("AGENT_DEFINITION_NOT_FOUND")
                return row["record"]
        except AgentDefinitionNotFound:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    def list(self, scope: DefinitionScope) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as connection:
                rows = connection.execute(
                    "SELECT record FROM agent_definition.definitions WHERE namespace=%s AND security_domain=%s ORDER BY definition_id LIMIT 200",
                    (scope.namespace, scope.security_domain),
                ).fetchall()
                return [row["record"] for row in rows]
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        params = (record["namespace"], record["securityDomain"], record["definitionId"])
        try:
            with self.pool.connection() as connection, connection.transaction():
                conflict = connection.execute(
                    "SELECT 1 FROM agent_definition.tombstones WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                    params,
                ).fetchone()
                if conflict:
                    raise AgentDefinitionConflict("AGENT_DEFINITION_CONFLICT")
                connection.execute(
                    "INSERT INTO agent_definition.definitions(namespace,security_domain,definition_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (*params, record["aggregateVersion"], json.dumps(record)),
                )
                self._insert_fact(connection, record, 1, record["facts"][0])
            return record
        except AgentDefinitionConflict:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionConflict("AGENT_DEFINITION_CONFLICT") from exc

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "UPDATE agent_definition.definitions SET aggregate_version=%s,record=%s::jsonb,updated_at=now() WHERE namespace=%s AND security_domain=%s AND definition_id=%s AND aggregate_version=%s RETURNING definition_id",
                    (
                        record["aggregateVersion"],
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["definitionId"],
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise AgentDefinitionConflict("STALE_AGENT_DEFINITION")
                self._insert_fact(connection, record, len(record["facts"]) + 1, fact)
                record["facts"] = [*record["facts"], fact]
                connection.execute(
                    "UPDATE agent_definition.definitions SET record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                    (
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["definitionId"],
                    ),
                )
            return record
        except AgentDefinitionConflict:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    @staticmethod
    def _insert_fact(
        connection: Connection[Any],
        record: dict[str, Any],
        ordinal: int,
        fact: dict[str, Any],
    ) -> None:
        connection.execute(
            "INSERT INTO agent_definition.lifecycle_facts(namespace,security_domain,definition_id,ordinal,fact_id,fact) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                record["namespace"],
                record["securityDomain"],
                record["definitionId"],
                ordinal,
                fact["factId"],
                json.dumps(fact),
            ),
        )

    def delete_draft(
        self,
        scope: DefinitionScope,
        definition_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "DELETE FROM agent_definition.definitions WHERE namespace=%s AND security_domain=%s AND definition_id=%s AND aggregate_version=%s AND record->>'publishedRevisionId' IS NULL RETURNING definition_id",
                    (
                        scope.namespace,
                        scope.security_domain,
                        definition_id,
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise AgentDefinitionConflict("PROTECTED_OR_STALE_AGENT_DEFINITION")
                connection.execute(
                    "INSERT INTO agent_definition.tombstones(namespace,security_domain,definition_id,tombstone) VALUES (%s,%s,%s,%s::jsonb)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        definition_id,
                        json.dumps(tombstone),
                    ),
                )
        except AgentDefinitionConflict:
            raise
        except PsycopgError as exc:
            raise AgentDefinitionRepositoryError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc
