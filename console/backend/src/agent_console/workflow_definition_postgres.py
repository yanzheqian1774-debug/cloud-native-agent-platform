# ruff: noqa: E501
"""PostgreSQL primary adapter for Workflow Definition continuity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.workflow_definition_repository import (
    WorkflowDefinitionConflict,
    WorkflowDefinitionNotFound,
    WorkflowDefinitionRepositoryError,
    WorkflowScope,
)

ADAPTER = "workflow-definition-postgresql-v1"
SCHEMA_VERSION = 1


class PostgresWorkflowDefinitionRepository:
    def __init__(
        self,
        database_url: str,
        *,
        migration_path: Path,
        min_pool_size: int = 1,
        max_pool_size: int = 4,
        timeout: float = 5.0,
    ):
        if not database_url:
            raise WorkflowDefinitionRepositoryError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"
            )
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
            raise WorkflowDefinitionRepositoryError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    @property
    def migration_checksum(self):
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self):
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("SET LOCAL statement_timeout = '5s'")
                connection.execute("SET LOCAL lock_timeout = '3s'")
                connection.execute(self.migration_path.read_text())
                row = connection.execute(
                    "SELECT checksum,adapter FROM workflow_definition.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if row is None:
                    connection.execute(
                        "INSERT INTO workflow_definition.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (SCHEMA_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif (
                    row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise WorkflowDefinitionRepositoryError(
                        "WORKFLOW_DEFINITION_SCHEMA_INCOMPATIBLE"
                    )
        except WorkflowDefinitionRepositoryError:
            raise
        except PsycopgError as exc:
            raise WorkflowDefinitionRepositoryError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    def compatibility(self):
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT checksum,adapter FROM workflow_definition.schema_migrations WHERE version=%s",
                (SCHEMA_VERSION,),
            ).fetchone()
            if (
                row is None
                or row["checksum"] != self.migration_checksum
                or row["adapter"] != ADAPTER
            ):
                raise WorkflowDefinitionRepositoryError(
                    "WORKFLOW_DEFINITION_SCHEMA_INCOMPATIBLE"
                )

    def get(self, scope: WorkflowScope, resource_id: str):
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT record FROM workflow_definition.definitions WHERE namespace=%s AND security_domain=%s AND workflow_definition_id=%s",
                (scope.namespace, scope.security_domain, resource_id),
            ).fetchone()
            if row is None:
                raise WorkflowDefinitionNotFound("WORKFLOW_DEFINITION_NOT_FOUND")
            return row["record"]

    def list(self, scope):
        with self.pool.connection() as connection:
            return [
                x["record"]
                for x in connection.execute(
                    "SELECT record FROM workflow_definition.definitions WHERE namespace=%s AND security_domain=%s ORDER BY workflow_definition_id LIMIT 200",
                    (scope.namespace, scope.security_domain),
                ).fetchall()
            ]

    def create(self, record):
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute(
                    "INSERT INTO workflow_definition.definitions(namespace,security_domain,workflow_definition_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (
                        record["namespace"],
                        record["securityDomain"],
                        record["workflowDefinitionId"],
                        record["aggregateVersion"],
                        json.dumps(record),
                    ),
                )
                self._fact(connection, record, 1, record["facts"][0])
            return record
        except PsycopgError as exc:
            raise WorkflowDefinitionConflict("WORKFLOW_DEFINITION_CONFLICT") from exc

    def replace(self, record, *, expected_version, fact):
        try:
            with self.pool.connection() as connection, connection.transaction():
                row = connection.execute(
                    "UPDATE workflow_definition.definitions SET aggregate_version=%s,record=%s::jsonb,updated_at=now() WHERE namespace=%s AND security_domain=%s AND workflow_definition_id=%s AND aggregate_version=%s RETURNING workflow_definition_id",
                    (
                        record["aggregateVersion"],
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["workflowDefinitionId"],
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise WorkflowDefinitionConflict("STALE_WORKFLOW_DEFINITION")
                self._fact(connection, record, len(record["facts"]) + 1, fact)
                record["facts"] = [*record["facts"], fact]
                connection.execute(
                    "UPDATE workflow_definition.definitions SET record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND workflow_definition_id=%s",
                    (
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["workflowDefinitionId"],
                    ),
                )
            return record
        except WorkflowDefinitionConflict:
            raise
        except PsycopgError as exc:
            raise WorkflowDefinitionRepositoryError(
                "WORKFLOW_DEFINITION_STORAGE_UNAVAILABLE"
            ) from exc

    @staticmethod
    def _fact(connection, record, ordinal, fact):
        connection.execute(
            "INSERT INTO workflow_definition.lifecycle_facts(namespace,security_domain,workflow_definition_id,ordinal,fact_id,fact) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                record["namespace"],
                record["securityDomain"],
                record["workflowDefinitionId"],
                ordinal,
                fact["factId"],
                json.dumps(fact),
            ),
        )
