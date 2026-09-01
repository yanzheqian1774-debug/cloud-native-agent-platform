# ruff: noqa: E501
"""PostgreSQL primary adapter for Runtime Profile continuity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from psycopg.errors import Error as PsycopgError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from agent_console.runtime_profile_repository import (
    RuntimeProfileConflict,
    RuntimeProfileNotFound,
    RuntimeProfileRepositoryError,
    RuntimeProfileScope,
)

ADAPTER = "runtime-profile-postgresql-v1"
SCHEMA_VERSION = 1


class PostgresRuntimeProfileRepository:
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
            raise RuntimeProfileRepositoryError("RUNTIME_PROFILE_STORAGE_UNAVAILABLE")
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
            raise RuntimeProfileRepositoryError(
                "RUNTIME_PROFILE_STORAGE_UNAVAILABLE"
            ) from exc

    @property
    def migration_checksum(self):
        return hashlib.sha256(self.migration_path.read_bytes()).hexdigest()

    def migrate(self):
        try:
            with self.pool.connection() as c, c.transaction():
                c.execute("SET LOCAL statement_timeout='5s'")
                c.execute("SET LOCAL lock_timeout='3s'")
                c.execute(self.migration_path.read_text())
                row = c.execute(
                    "SELECT checksum,adapter FROM runtime_profile.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if row is None:
                    c.execute(
                        "INSERT INTO runtime_profile.schema_migrations(version,checksum,adapter) VALUES (%s,%s,%s)",
                        (SCHEMA_VERSION, self.migration_checksum, ADAPTER),
                    )
                elif (
                    row["checksum"] != self.migration_checksum
                    or row["adapter"] != ADAPTER
                ):
                    raise RuntimeProfileRepositoryError(
                        "RUNTIME_PROFILE_SCHEMA_INCOMPATIBLE"
                    )
        except RuntimeProfileRepositoryError:
            raise
        except PsycopgError as exc:
            raise RuntimeProfileRepositoryError(
                "RUNTIME_PROFILE_STORAGE_UNAVAILABLE"
            ) from exc

    def compatibility(self):
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT checksum,adapter FROM runtime_profile.schema_migrations WHERE version=%s",
                (SCHEMA_VERSION,),
            ).fetchone()
            if (
                row is None
                or row["checksum"] != self.migration_checksum
                or row["adapter"] != ADAPTER
            ):
                raise RuntimeProfileRepositoryError(
                    "RUNTIME_PROFILE_SCHEMA_INCOMPATIBLE"
                )

    def get(self, scope: RuntimeProfileScope, resource_id: str):
        with self.pool.connection() as c:
            row = c.execute(
                "SELECT record FROM runtime_profile.profiles WHERE namespace=%s AND security_domain=%s AND runtime_profile_id=%s",
                (scope.namespace, scope.security_domain, resource_id),
            ).fetchone()
            if row is None:
                raise RuntimeProfileNotFound("RUNTIME_PROFILE_NOT_FOUND")
            return row["record"]

    def list(self, scope):
        with self.pool.connection() as c:
            return [
                x["record"]
                for x in c.execute(
                    "SELECT record FROM runtime_profile.profiles WHERE namespace=%s AND security_domain=%s ORDER BY runtime_profile_id LIMIT 200",
                    (scope.namespace, scope.security_domain),
                ).fetchall()
            ]

    def create(self, record):
        try:
            with self.pool.connection() as c, c.transaction():
                c.execute(
                    "INSERT INTO runtime_profile.profiles(namespace,security_domain,runtime_profile_id,aggregate_version,record) VALUES (%s,%s,%s,%s,%s::jsonb)",
                    (
                        record["namespace"],
                        record["securityDomain"],
                        record["runtimeProfileId"],
                        record["aggregateVersion"],
                        json.dumps(record),
                    ),
                )
                self._fact(c, record, 1, record["facts"][0])
            return record
        except PsycopgError as exc:
            raise RuntimeProfileConflict("RUNTIME_PROFILE_CONFLICT") from exc

    def replace(self, record, *, expected_version, fact):
        try:
            with self.pool.connection() as c, c.transaction():
                row = c.execute(
                    "UPDATE runtime_profile.profiles SET aggregate_version=%s,record=%s::jsonb,updated_at=now() WHERE namespace=%s AND security_domain=%s AND runtime_profile_id=%s AND aggregate_version=%s RETURNING runtime_profile_id",
                    (
                        record["aggregateVersion"],
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["runtimeProfileId"],
                        expected_version,
                    ),
                ).fetchone()
                if row is None:
                    raise RuntimeProfileConflict("STALE_RUNTIME_PROFILE")
                self._fact(c, record, len(record["facts"]) + 1, fact)
                record["facts"] = [*record["facts"], fact]
                c.execute(
                    "UPDATE runtime_profile.profiles SET record=%s::jsonb WHERE namespace=%s AND security_domain=%s AND runtime_profile_id=%s",
                    (
                        json.dumps(record),
                        record["namespace"],
                        record["securityDomain"],
                        record["runtimeProfileId"],
                    ),
                )
            return record
        except RuntimeProfileConflict:
            raise
        except PsycopgError as exc:
            raise RuntimeProfileRepositoryError(
                "RUNTIME_PROFILE_STORAGE_UNAVAILABLE"
            ) from exc

    @staticmethod
    def _fact(c, record, ordinal, fact):
        c.execute(
            "INSERT INTO runtime_profile.lifecycle_facts(namespace,security_domain,runtime_profile_id,ordinal,fact_id,fact) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                record["namespace"],
                record["securityDomain"],
                record["runtimeProfileId"],
                ordinal,
                fact["factId"],
                json.dumps(fact),
            ),
        )
