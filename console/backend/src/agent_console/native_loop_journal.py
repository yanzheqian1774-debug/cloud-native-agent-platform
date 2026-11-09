# ruff: noqa: E501 -- Exact owner SQL.
"""Atomic claim/receipt storage under the existing Skill invocation owner."""

from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError


class NativeLoopJournal:
    def __init__(self, pool, scope, invocation_id):
        self.pool = pool
        self.identity = (scope.namespace, scope.security_domain, invocation_id)

    def claim(self, key, request_digest):
        with self.pool.connection() as c, c.transaction():
            inserted = c.execute(
                "INSERT INTO skill_invocation.native_loop_records "
                "(namespace,security_domain,skill_invocation_id,record_key,request_digest) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING record_key",
                (*self.identity, key, request_digest),
            ).fetchone()
            if inserted:
                return None
            row = c.execute(
                'SELECT request_digest AS "requestDigest",result FROM '
                "skill_invocation.native_loop_records WHERE namespace=%s AND "
                "security_domain=%s AND skill_invocation_id=%s AND record_key=%s",
                (*self.identity, key),
            ).fetchone()
            if row is None or row["requestDigest"] != request_digest:
                raise AuthorityError("NATIVE_LOOP_JOURNAL_CONFLICT")
            return row

    def finish(self, key, request_digest, result):
        with self.pool.connection() as c, c.transaction():
            row = c.execute(
                "UPDATE skill_invocation.native_loop_records SET result=%s,completed_at=now() "
                "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
                "AND record_key=%s AND request_digest=%s AND result IS NULL "
                "RETURNING record_key",
                (Jsonb(result), *self.identity, key, request_digest),
            ).fetchone()
            if row is None:
                existing = c.execute(
                    "SELECT result,request_digest FROM skill_invocation.native_loop_records "
                    "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s "
                    "AND record_key=%s",
                    (*self.identity, key),
                ).fetchone()
                if not existing or existing != {
                    "result": result,
                    "request_digest": request_digest,
                }:
                    raise AuthorityError("NATIVE_LOOP_JOURNAL_CONFLICT")
