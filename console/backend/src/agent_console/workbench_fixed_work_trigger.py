# ruff: noqa: E501 -- Exact scoped SQL owner keys.
"""One-use trigger adapter around the existing transactional START owner."""

import json
import re
from dataclasses import replace
from datetime import UTC, datetime

from . import fixed_work_authoring_postgres as authoring
from .authority_contracts import ExactGrant
from .digital_employee_definition import digest
from .fixed_work_trigger import TriggerPolicy
from .fixed_work_trigger_postgres import compatible
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_execution import PreparedExecutionOwner, StartPrepared


def grants(_context, path, _payload, _query, *, write=False):
    return (
        ExactGrant(
            "EXECUTION",
            "START" if write else "READ",
            "governed-execution:prepared:" + path["digest"],
        ),
    )


class FixedWorkTriggerOwner:
    def __init__(self, policy_reader, coordinator, *, clock=lambda: datetime.now(UTC)):
        self.policy_reader, self.clock = policy_reader, clock
        self.owner = PreparedExecutionOwner(coordinator)

    def __call__(self, call):
        write = call.operation == "TRIGGER_FIXED_WORK_ONCE"
        if call.operation not in {"TRIGGER_FIXED_WORK_ONCE", "READ_FIXED_WORK_TRIGGER"}:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_NOT_FOUND", 404)
        c, context, path = call.connection, call.context, call.path
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,199}", path["event_id"]):
            raise WorkbenchOwnerError("FIXED_WORK_EVENT_ID_INVALID", 422)
        scope = (context.scope.tenant_id, context.scope.security_domain)
        principal = OwnerPrincipal(context.principal_id, *scope)
        call.authority.require(
            principal,
            "EXECUTION",
            "START" if write else "READ",
            "governed-execution:prepared:" + path["digest"],
        )
        compatible(c)
        if write:
            from .fixed_work_succession_postgres import require_current

            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,67))",
                (digest(("work", *scope, path["work_id"])),),
            )
            require_current(c, scope, path["work_id"], path["revision_id"])
        # Stable lock serializes both event identity and preparation reuse.
        for key in sorted(
            (
                digest([*scope, context.principal_id, path["event_id"]]),
                digest([*scope, path["digest"]]),
                digest([*scope, "work", path["work_id"]]),
            )
        ):
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                ("fixed-work-trigger:" + key,),
            )
        identity = (*scope, context.principal_id, path["event_id"])
        row = c.execute(
            "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND event_id=%s",
            identity,
        ).fetchone()
        if row and (row["work_id"], row["revision_id"], row["preparation_digest"]) != (
            path["work_id"],
            path["revision_id"],
            path["digest"],
        ):
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_CONFLICT", 409)
        # READ uses current exact read authority, not a still-active historical policy.
        if not write:
            if row is None:
                raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_NOT_FOUND", 404)
            return self.receipt(row)
        policy = self.policy_reader()
        if not isinstance(policy, TriggerPolicy):
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_UNAVAILABLE", 503)
        binding = policy.require(context, path, self.clock())
        payload_digest = digest(
            {
                "binding": binding.model_dump(mode="json"),
                "command": dict(call.payload),
                "eventId": path["event_id"],
            }
        )
        if row:
            if row["payload_digest"] != payload_digest:
                raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_CONFLICT", 409)
            return self.receipt(row)
        other = c.execute(
            "SELECT 1 FROM fixed_work_triggers.receipts WHERE namespace=%s AND security_domain=%s AND preparation_digest=%s",
            (*scope, path["digest"]),
        ).fetchone()
        if other:
            raise WorkbenchOwnerError("FIXED_WORK_INSTANCE_ALREADY_BOUND", 409)
        unresolved = c.execute(
            "SELECT 1 FROM fixed_work_triggers.receipts r "
            "LEFT JOIN execution_authority.prepared_run_progress p "
            "ON p.namespace=r.namespace AND p.security_domain=r.security_domain "
            "AND p.workflow_run_id=r.workflow_run_id "
            "WHERE r.namespace=%s AND r.security_domain=%s AND r.work_id=%s "
            "AND (p.record->>'state' IS NULL OR p.record->>'state' NOT IN "
            "('SUCCEEDED','FAILED','CANCELLED')) LIMIT 1",
            (*scope, binding.workId),
        ).fetchone()
        if unresolved:
            raise WorkbenchOwnerError("FIXED_WORK_PREVIOUS_RUN_UNRESOLVED", 409)
        saved = authoring.read(c, scope, binding.workId, binding.revisionId)
        if saved["digest"] != binding.workDigest:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_BINDING_CHANGED", 409)
        team = saved["record"]["team"]
        call.authority.require(
            principal, "TEAM", "READ", f"team:{team['teamId']}:{team['revisionId']}"
        )
        candidate = c.execute(
            "SELECT prepared_by FROM execution_authority.prepared_candidates WHERE namespace=%s AND security_domain=%s AND digest=%s FOR SHARE",
            (*scope, path["digest"]),
        ).fetchone()
        if candidate is None or candidate["prepared_by"] != context.principal_id:
            raise WorkbenchOwnerError(
                "FIXED_WORK_TRIGGER_ORIGINAL_SUBJECT_REQUIRED", 403
            )
        command_key = "fixed-work-trigger:" + digest([*identity, payload_digest])
        # Pin the original owner's exact sorted locks BEFORE absence inspection.
        # Otherwise a concurrent ordinary START could be mistaken for our trigger.
        for key in sorted(
            (
                json.dumps((*scope, context.principal_id, command_key)),
                json.dumps((*scope, "workflow-run:" + path["digest"])),
            )
        ):
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (key,))
        # An existing owner run without our receipt is never absence/no-effect proof.
        run = c.execute(
            "SELECT 1 FROM execution_authority.run_preparations WHERE namespace=%s AND security_domain=%s AND digest=%s",
            (*scope, path["digest"]),
        ).fetchone()
        if run:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_STATE_REQUIRES_REVIEW", 409)
        result = self.owner(
            replace(
                call,
                operation="START_PREPARED_EXECUTION",
                path={"digest": path["digest"]},
                payload={"idempotencyKey": command_key},
            )
        )
        if result.get("runId") != "workflow-run:" + path["digest"]:
            raise WorkbenchOwnerError("FIXED_WORK_TRIGGER_OWNER_RESULT_INVALID", 409)
        row = c.execute(
            "INSERT INTO fixed_work_triggers.receipts VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                *identity,
                binding.workId,
                binding.revisionId,
                binding.workDigest,
                binding.preparationDigest,
                payload_digest,
                policy.digest,
                result["runId"],
                command_key,
                self.clock(),
            ),
        ).fetchone()
        return self.receipt(row)

    @staticmethod
    def receipt(row):
        return {
            "eventId": row["event_id"],
            "workId": row["work_id"],
            "revisionId": row["revision_id"],
            "workDigest": row["work_digest"],
            "preparationDigest": row["preparation_digest"],
            "runId": row["workflow_run_id"],
            "startCommandKey": row["start_command_key"],
            "recordedAt": row["recorded_at"].isoformat(),
            "status": "START_COMMITTED",
            "executionOutcome": "READ_EXISTING_EXECUTION_OWNER",
            "automaticTriggerEnabled": False,
        }


def fixed_work_trigger_operations(policy_reader, coordinator, *, enabled=False):
    # Composition must explicitly opt in. This package registers no bootstrap flag.
    if not enabled:
        return ()
    handler = FixedWorkTriggerOwner(policy_reader, coordinator)
    path = (
        PREFIX
        + "/fixed-work-drafts/{work_id}/revisions/{revision_id}/prepared/{digest}/triggers/{event_id}"
    )
    return (
        WorkbenchOperation(
            "TRIGGER_FIXED_WORK_ONCE",
            "POST",
            path,
            StartPrepared,
            None,
            lambda c, p, v, q: grants(c, p, v, q, write=True),
            handler,
        ),
        WorkbenchOperation(
            "READ_FIXED_WORK_TRIGGER", "GET", path, None, None, grants, handler
        ),
    )
