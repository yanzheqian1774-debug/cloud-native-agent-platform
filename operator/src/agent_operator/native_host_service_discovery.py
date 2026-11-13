"""Read-only bounded discovery through the existing owned continuation owner."""

from datetime import UTC, datetime


class Discovery:
    def __init__(self, assembly, scope, fingerprint):
        self.work = assembly.worker.repository.work
        if self.work.owned_business is None or not self.work.policy.enabled:
            raise ValueError("HOST_SERVICE_OWNED_CONTINUATION_REQUIRED")
        self.repository = assembly.execution_repository
        self.scope = scope
        self.fingerprint = fingerprint
        self.cursor = ""

    def page(self, limit=32):
        ns, domain, principal = self.scope
        with self.repository.pool.connection() as c:
            rows = c.execute(
                "SELECT namespace,security_domain,command_key,result FROM "
                "execution_authority.prepared_resource_commands WHERE namespace=%s "
                "AND security_domain=%s AND actor_id=%s AND command_key>%s "
                "AND result->>'schemaVersion'='readonly-continuation.v1' "
                "AND result ? 'ownedBusiness' ORDER BY command_key LIMIT %s",
                (ns, domain, principal, self.cursor, limit),
            ).fetchall()
        self.cursor = rows[-1]["command_key"] if len(rows) == limit else ""
        return [item for row in rows if (item := self.inspect(row)) is not None]

    def inspect(self, row):
        receipt = row["result"]
        if receipt.get("executionAuthorizationDigest") != self.work.policy.digest:
            return None
        if receipt.get("subject") != self.scope[2] or not self.work._owned_receipt(
            row, datetime.now(UTC)
        ):
            return None
        resource = "governed-execution:prepared:" + receipt["preparationDigest"]
        ns, domain, principal = self.scope
        with self.repository.pool.connection() as c:
            progress = c.execute(
                "SELECT record FROM execution_authority.prepared_run_progress WHERE "
                "namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (ns, domain, receipt["runId"]),
            ).fetchone()
            commands = c.execute(
                "SELECT state,worker_id FROM "
                "execution_authority.native_dispatch_commands "
                "WHERE namespace=%s AND security_domain=%s AND principal_id=%s "
                "AND authorization_resource=%s ORDER BY queued_at,command_id",
                (ns, domain, principal, resource),
            ).fetchall()
        if progress is None or not commands:
            return None
        phase = progress["record"].get("state")
        if phase not in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}:
            return None
        if phase in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            # Existing after_tick still owes the original outcome projection.
            # This cannot requeue: work.dispatches excludes terminal progress.
            with self.repository.pool.connection() as c:
                outcome = c.execute(
                    "SELECT 1 FROM product_outcome.heads WHERE namespace=%s "
                    "AND security_domain=%s AND workflow_run_id=%s",
                    (ns, domain, receipt["runId"]),
                ).fetchone()
            if outcome is not None:
                return None
        if any(
            command["state"] in {"UNKNOWN", "RECOVERY_REQUIRED"} for command in commands
        ):
            return None
        return {
            "namespace": ns,
            "securityDomain": domain,
            "principalId": principal,
            "preparationDigest": receipt["preparationDigest"],
            "runId": receipt["runId"],
            "commandKey": row["command_key"],
            "resource": resource,
            "existingWorkers": sorted(
                {r["worker_id"] for r in commands if r["worker_id"]}
            ),
        }

    def current(self, candidate):
        ns, domain, principal = self.scope
        with self.repository.pool.connection() as c:
            row = c.execute(
                "SELECT namespace,security_domain,command_key,result FROM "
                "execution_authority.prepared_resource_commands WHERE namespace=%s "
                "AND security_domain=%s AND actor_id=%s AND command_key=%s",
                (ns, domain, principal, candidate["commandKey"]),
            ).fetchone()
        return None if row is None else self.inspect(row)
