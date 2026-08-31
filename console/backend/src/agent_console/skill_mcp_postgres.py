# ruff: noqa: E501
"""PostgreSQL primary adapter for Skill/MCP product continuity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.skill_mcp_repository import (
    ResourceScope,
    SkillMcpConflict,
    SkillMcpNotFound,
    SkillMcpRepositoryError,
)

ADAPTER = "skill-mcp-resource-postgresql-v1"
SCHEMA_VERSION = 1
PROFESSIONAL_ADAPTER = "skill-mcp-professional-postgresql-v1"
PROFESSIONAL_SCHEMA_VERSION = 2


class PostgresSkillMcpRepository:
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
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE")
        self.migration_path = migration_path
        self.professional_migration_path = migration_path.with_name(
            "0004_skill_mcp_professional_experience.sql"
        )
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
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    @property
    def migration_checksum(self) -> str:
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    @property
    def professional_migration_checksum(self) -> str:
        return hashlib.sha256(self.professional_migration_path.read_bytes()).hexdigest()

    def migrate(self) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '5s'")
                connection.execute("SET LOCAL lock_timeout = '3s'")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM skill_mcp_resource.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO skill_mcp_resource.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (SCHEMA_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif (
                    row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise SkillMcpRepositoryError("SKILL_MCP_SCHEMA_INCOMPATIBLE")
                connection.execute(self.professional_migration_path.read_text())
                professional = connection.execute(
                    "SELECT checksum,adapter FROM skill_mcp_resource.schema_migrations WHERE version=%s",
                    (PROFESSIONAL_SCHEMA_VERSION,),
                ).fetchone()
                if professional is None:
                    connection.execute(
                        "INSERT INTO skill_mcp_resource.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (
                            PROFESSIONAL_SCHEMA_VERSION,
                            self.professional_migration_checksum,
                            PROFESSIONAL_ADAPTER,
                        ),
                    )
                elif (
                    professional["checksum"] != self.professional_migration_checksum
                    or professional["adapter"] != PROFESSIONAL_ADAPTER
                ):
                    raise SkillMcpRepositoryError("SKILL_MCP_SCHEMA_INCOMPATIBLE")
        except SkillMcpRepositoryError:
            raise
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    def compatibility(self) -> None:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT checksum,adapter FROM skill_mcp_resource.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if (
                    row is None
                    or row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise SkillMcpRepositoryError("SKILL_MCP_SCHEMA_INCOMPATIBLE")
                professional = connection.execute(
                    "SELECT checksum,adapter FROM skill_mcp_resource.schema_migrations WHERE version=%s",
                    (PROFESSIONAL_SCHEMA_VERSION,),
                ).fetchone()
                if (
                    professional is None
                    or professional["checksum"] != self.professional_migration_checksum
                    or professional["adapter"] != PROFESSIONAL_ADAPTER
                ):
                    raise SkillMcpRepositoryError("SKILL_MCP_SCHEMA_INCOMPATIBLE")
        except SkillMcpRepositoryError:
            raise
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    def get(self, scope: ResourceScope, kind: str, resource_id: str) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection:
                row = connection.execute(
                    "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s",
                    (scope.namespace, scope.security_domain, kind, resource_id),
                ).fetchone()
                if row is None:
                    raise SkillMcpNotFound("RESOURCE_NOT_FOUND")
                return row["record"]
        except SkillMcpNotFound:
            raise
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    def list(self, scope: ResourceScope, kind: str) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as connection:
                rows = connection.execute(
                    "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind=%s ORDER BY resource_id LIMIT 200",
                    (scope.namespace, scope.security_domain, kind),
                ).fetchall()
                return [row["record"] for row in rows]
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        key = (
            record["namespace"],
            record["securityDomain"],
            record["kind"],
            record["resourceId"],
        )
        try:
            with self.pool.connection() as connection, connection.transaction():
                if connection.execute(
                    "SELECT 1 FROM skill_mcp_resource.tombstones WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s",
                    key,
                ).fetchone():
                    raise SkillMcpConflict("RESOURCE_CONFLICT")
                connection.execute(
                    "INSERT INTO skill_mcp_resource.resources(namespace,security_domain,kind,resource_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                    (*key, record["aggregateVersion"], json.dumps(record)),
                )
                self._fact(connection, record, 1, record["facts"][0])
            return record
        except SkillMcpConflict:
            raise
        except PsycopgError as exc:
            raise SkillMcpConflict("RESOURCE_CONFLICT") from exc

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "UPDATE skill_mcp_resource.resources SET aggregate_version=%s,record=%s::jsonb,updated_at=now() WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s AND aggregate_version=%s RETURNING resource_id",
                    (
                        record["aggregateVersion"],
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["kind"],
                        record["resourceId"],
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise SkillMcpConflict("STALE_RESOURCE")
                self._fact(connection, record, len(record["facts"]) + 1, fact)
                if fact["event"] in {
                    "TEST_CASE_SAVED",
                    "TEST_RESULT_RECORDED",
                    "MCP_HEALTH_OBSERVED",
                    "MCP_DISCOVERY_SNAPSHOTTED",
                    "MCP_TOOL_SELECTION_GOVERNED",
                    "MCP_INVOCATION_RECORDED",
                    "MCP_DRIFT_RECORDED",
                }:
                    connection.execute(
                        "INSERT INTO skill_mcp_resource.professional_facts(namespace,security_domain,kind,resource_id,ordinal,fact_id,fact_type,safe_fact) VALUES (%s,%s,%s,%s,(SELECT coalesce(max(ordinal),0)+1 FROM skill_mcp_resource.professional_facts WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s),%s,%s,%s::jsonb)",
                        (
                            record["namespace"],
                            record["securityDomain"],
                            record["kind"],
                            record["resourceId"],
                            record["namespace"],
                            record["securityDomain"],
                            record["kind"],
                            record["resourceId"],
                            fact["factId"],
                            fact["event"],
                            json.dumps(fact),
                        ),
                    )
                record["facts"] = [*record["facts"], fact]
                connection.execute(
                    "UPDATE skill_mcp_resource.resources SET record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s",
                    (
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["kind"],
                        record["resourceId"],
                    ),
                )
            return record
        except SkillMcpConflict:
            raise
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc

    @staticmethod
    def _fact(
        connection: Any, record: dict[str, Any], ordinal: int, fact: dict[str, Any]
    ) -> None:
        connection.execute(
            "INSERT INTO skill_mcp_resource.lifecycle_facts(namespace,security_domain,kind,resource_id,ordinal,fact_id,fact) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)",
            (
                record["namespace"],
                record["securityDomain"],
                record["kind"],
                record["resourceId"],
                ordinal,
                fact["factId"],
                json.dumps(fact),
            ),
        )

    def delete_draft(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "DELETE FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s AND aggregate_version=%s AND record->>'publishedRevisionId' IS NULL RETURNING resource_id",
                    (
                        scope.namespace,
                        scope.security_domain,
                        kind,
                        resource_id,
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise SkillMcpConflict("PROTECTED_OR_STALE_RESOURCE")
                connection.execute(
                    "INSERT INTO skill_mcp_resource.tombstones(namespace,security_domain,kind,resource_id,tombstone) VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (
                        scope.namespace,
                        scope.security_domain,
                        kind,
                        resource_id,
                        json.dumps(tombstone),
                    ),
                )
        except SkillMcpConflict:
            raise
        except PsycopgError as exc:
            raise SkillMcpRepositoryError("SKILL_MCP_STORAGE_UNAVAILABLE") from exc
