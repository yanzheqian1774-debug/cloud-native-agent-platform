"""Opt-in bounded fixed-work polling, reusing local host lifecycle primitives.

No subprocess, credential issuance, implicit startup or database migration.
A real composition must provide the existing cycle owner and current identity.
"""

import os
from threading import Event

from psycopg.rows import dict_row

from .native_host_service_state import lock, machine_lock_directory
from .native_host_startup import digest


class FixedWorkCycleService:
    def __init__(
        self,
        host,
        current_context,
        database_fingerprint,
        *,
        enabled=False,
        poll_seconds=30,
    ):
        if type(poll_seconds) is not int or not 5 <= poll_seconds <= 300:
            raise ValueError("FIXED_WORK_POLL_INTERVAL_INVALID")
        if not isinstance(database_fingerprint, str) or not database_fingerprint:
            raise ValueError("FIXED_WORK_DATABASE_IDENTITY_REQUIRED")
        self.host, self.current_context = host, current_context
        self.database_fingerprint = database_fingerprint
        self.enabled, self.poll_seconds = enabled, poll_seconds

    def step(self):
        if not self.enabled:
            raise ValueError("FIXED_WORK_CYCLE_SERVICE_DISABLED")
        context = self.current_context()
        registry = self.host.runtime.registry
        policy = registry._policy()
        with registry.repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            now = registry._check(c, context, policy)
            rows = c.execute(
                "SELECT event_id FROM fixed_work_service.planning_preparations "
                "WHERE namespace=%s AND security_domain=%s AND work_id=%s "
                "AND subject_id=%s AND policy_digest=%s",
                (
                    policy.tenantId,
                    policy.securityDomain,
                    policy.work.resource_id,
                    context.principal_id,
                    policy.digest,
                ),
            ).fetchall()
        saved = {row["event_id"] for row in rows}
        # A saved event remains observable after its dispatch window; an unsaved
        # missed slot is never backfilled. Owner expiry/revoke still blocks writes.
        eligible = [
            event
            for event in policy.allowedEventIds
            if event in saved
            or policy.eventWindows[event][0] <= now < policy.eventWindows[event][1]
        ]
        results = []
        for event in sorted(eligible, key=lambda e: (policy.eventWindows[e][0], e)):
            try:
                result = self.host.step(context, event)
            except Exception as exc:
                from agent_console.authority_contracts import AuthorityError

                if not isinstance(exc, AuthorityError) or exc.reason_code not in {
                    "FIXED_WORK_SERVICE_PREVIOUS_RUN_UNRESOLVED",
                    "FIXED_WORK_SERVICE_PREVIOUS_OUTCOME_UNRESOLVED",
                    "FIXED_WORK_SERVICE_PREVIOUS_BUDGET_UNRESOLVED",
                    "FIXED_WORK_SERVICE_PREVIOUS_CYCLE_AWAITS_CONTINUATION",
                }:
                    raise
                # These exact preparation guards run before model claim/reserve.
                # Polling their observations cannot repeat a previous effect.
                results.append({"eventId": event, "stage": "WAITING_PREVIOUS_WORK"})
                break
            results.append({"eventId": event, **result})
            # A definitive failed planning result is never called again here.
            # The next event still enters the original registry, which refuses
            # an unsettled budget or unresolved prior effect before dispatch.
            if (
                result["stage"] == "PLANNING_OBSERVATION"
                and result.get("result", {}).get("technical_status") == "FAILED"
            ):
                continue
            if result["stage"] != "START_COMMITTED":
                break  # do not skip a pending/unknown earlier business cycle
        return tuple(results)

    def run(self, stop: Event, observe):
        """Explicit caller-run loop; observer is presentation, never authority.

        Any owner/network failure stops this process rather than retrying writes.
        A supervisor may restart it; persisted original owner keys fence replay.
        """
        if not self.enabled:
            raise ValueError("FIXED_WORK_CYCLE_SERVICE_DISABLED")
        policy = self.host.runtime.registry._policy()
        identity = digest(
            [
                self.database_fingerprint,
                policy.tenantId,
                policy.securityDomain,
                policy.work.resource_id,
            ]
        )
        fd = lock(machine_lock_directory() / ("fixed-cycle-" + identity + ".lock"))
        try:
            while not stop.is_set():
                # Configuration replacement requires a fresh process/lock identity.
                current = self.host.runtime.registry._policy()
                if current.digest != policy.digest:
                    raise ValueError("FIXED_WORK_CYCLE_CONFIGURATION_CHANGED")
                observe(self.step())
                stop.wait(self.poll_seconds)
        finally:
            os.close(fd)
