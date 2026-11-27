"""Read-only bounded discovery through the existing owned continuation owner."""

from datetime import UTC, datetime


class Discovery:
    def __init__(self, assembly, scope, fingerprint):
        self.work = assembly.worker.repository.work
        self.service = getattr(self.work, "bound_service_execution", None)
        if self.service is not None:
            from agent_console.bound_service_execution import (
                BoundServiceExecutionBridge,
            )

            if not isinstance(self.service, BoundServiceExecutionBridge):
                raise ValueError("HOST_SERVICE_BOUND_SERVICE_REQUIRED")
            self.service.require_scope(scope)
        if (
            self.work.owned_business is None and self.service is None
        ) or not self.work.policy.enabled:
            raise ValueError("HOST_SERVICE_OWNED_CONTINUATION_REQUIRED")
        caller = getattr(getattr(assembly.worker, "transport", None), "caller", None)
        self.wait_access = getattr(caller, "wait_access", None)
        self.repository = assembly.execution_repository
        self.scope = scope
        self.fingerprint = fingerprint
        self.cursor = ""
        self.observe_stopped = None

    def page(self, limit=32):
        ns, domain, principal = self.scope
        with self.repository.pool.connection() as c:
            rows = c.execute(
                "SELECT namespace,security_domain,command_key,result FROM "
                "execution_authority.prepared_resource_commands WHERE namespace=%s "
                "AND security_domain=%s AND actor_id=%s AND command_key>%s "
                "AND result->>'schemaVersion'='readonly-continuation.v1' "
                + ("AND result ? 'ownedBusiness' " if self.service is None else "")
                + "ORDER BY command_key LIMIT %s",
                (ns, domain, principal, self.cursor, limit),
            ).fetchall()
        self.cursor = rows[-1]["command_key"] if len(rows) == limit else ""
        return [
            item
            for row in rows
            if (item := self.inspect(row, observe_stopped=True)) is not None
        ]

    def inspect(self, row, active_process=None, *, observe_stopped=False):
        receipt = row["result"]
        if receipt.get("executionAuthorizationDigest") != self.work.policy.digest:
            return None
        check = (
            self.work._owned_receipt
            if self.service is None
            else self.work._service_receipt
        )
        if receipt.get("subject") != self.scope[2] or not check(row, datetime.now(UTC)):
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
        candidate = {
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
        if self.wait_access is not None:
            with self.repository.pool.connection() as c:
                waiting = self.wait_access.inspect(c, candidate)
            if (
                waiting is not None
                and observe_stopped
                and self.observe_stopped is not None
            ):
                if self.observe_stopped(candidate) is False:
                    return None
                with self.repository.pool.connection() as c:
                    waiting = self.wait_access.inspect(c, candidate)
            if waiting is not None:
                if active_process is not None and waiting["state"] in {
                    "CONTINUATION_CLAIMED",
                    "ADVANCING",
                }:
                    if (
                        waiting["activeWorkerId"] != active_process.get("workerId")
                        or waiting["startupRecordDigest"]
                        != active_process.get("startupDigest")
                        or active_process.get("released") is not True
                    ):
                        return None
                elif (
                    waiting["state"] != "ANSWER_SAVED"
                    or waiting["resumable"] is not True
                ):
                    return None
        return candidate

    def current(self, candidate):
        return self._current(candidate)

    def maintain(self, candidate, process_record):
        return self._current(candidate, active_process=process_record)

    def stopped(
        self, candidate, process_record, startup_record, exit_receipt, verify_exit
    ):
        if self.wait_access is None:
            return None
        with self.repository.pool.connection() as c, c.transaction():
            return self.wait_access.stopped(
                c, candidate, process_record, startup_record, exit_receipt, verify_exit
            )

    def _current(self, candidate, active_process=None):
        ns, domain, principal = self.scope
        with self.repository.pool.connection() as c:
            row = c.execute(
                "SELECT namespace,security_domain,command_key,result FROM "
                "execution_authority.prepared_resource_commands WHERE namespace=%s "
                "AND security_domain=%s AND actor_id=%s AND command_key=%s",
                (ns, domain, principal, candidate["commandKey"]),
            ).fetchone()
        return None if row is None else self.inspect(row, active_process=active_process)
