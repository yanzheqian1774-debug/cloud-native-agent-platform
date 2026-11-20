"""Bounded fixed-work receipts; no trigger or authority mutations."""

from dataclasses import replace

from .authority_contracts import ExactGrant
from .execution_preparation_postgres import PreparedExecutionStore
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_fixed_work import FixedWorkAuthoringOwner, grants
from .workbench_owner_authorization import WorkbenchOwnerError


class FixedWorkActivityOwner:
    def __init__(self, authoring):
        if not isinstance(authoring, FixedWorkAuthoringOwner):
            raise ValueError("FIXED_WORK_AUTHORING_OWNER_REQUIRED")
        self.authoring = authoring

    def __call__(self, call):
        # Same exact team/work/revision/policy reader; no service identity assumed.
        saved = self.authoring(
            replace(call, operation="READ_FIXED_WORK_DRAFT", query={}, payload={})
        )
        context, c = call.context, call.connection
        scope = context.scope.tenant_id, context.scope.security_domain
        draft = saved["draft"]
        if (
            c.execute(
                "SELECT to_regclass('fixed_work_triggers.receipts') AS name"
            ).fetchone()["name"]
            is None
        ):
            raise WorkbenchOwnerError("FIXED_WORK_ACTIVITY_UNAVAILABLE", 503)
        rows = c.execute(
            "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s "
            "AND security_domain=%s AND work_id=%s AND revision_id=%s "
            "AND work_digest=%s ORDER BY recorded_at DESC,event_id DESC LIMIT 50",
            (*scope, draft["workId"], draft["revisionId"], saved["digest"]),
        ).fetchall()
        principal = OwnerPrincipal(context.principal_id, *scope)
        visible = []
        for row in rows:
            target = "governed-execution:prepared:" + row["preparation_digest"]
            if call.authority.current_action_grants(
                (ExactGrant("EXECUTION", "READ", target),)
            ) != (True,):
                continue
            call.authority.require(principal, "EXECUTION", "READ", target)
            preparation, progress = PreparedExecutionStore(c).read(
                *scope, row["workflow_run_id"]
            )
            if preparation.digest != row["preparation_digest"]:
                raise WorkbenchOwnerError("FIXED_WORK_ACTIVITY_BINDING_CHANGED", 409)
            visible.append(
                {
                    "eventId": row["event_id"],
                    "preparationDigest": preparation.digest,
                    "runId": row["workflow_run_id"],
                    "recordedAt": row["recorded_at"].isoformat(),
                    "state": progress.state,
                    "aggregateVersion": progress.version,
                }
            )
        return {
            "workId": draft["workId"],
            "revisionId": draft["revisionId"],
            "workDigest": saved["digest"],
            "items": visible,
            "windowLimit": 50,
            # A saved receipt proves a past START, not a currently enabled timer.
            "automaticTriggerStatus": "NOT_OBSERVED",
        }


def fixed_work_activity_operations(authoring, *, enabled=False):
    if not enabled:
        return ()
    return (
        WorkbenchOperation(
            "READ_FIXED_WORK_ACTIVITY",
            "GET",
            PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts/"
            "{work_id}/revisions/{revision_id}/activity",
            None,
            None,
            grants,
            FixedWorkActivityOwner(authoring),
        ),
    )
