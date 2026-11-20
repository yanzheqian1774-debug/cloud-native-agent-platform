"""Explicit current-viewer READ preparation through the existing independent issuer.

No timer, execution, model, answer delegation or service impersonation.  The
command selects at most the newest receipt for the exact immutable work version.
"""

from dataclasses import replace

from pydantic import Field

from .authority_contracts import AuthenticationSource, ExactGrant
from .digital_employee_definition import digest
from .execution_preparation_postgres import PreparedExecutionStore
from .resource_automation_policy import AdministratorWorkScope
from .resource_automation_validation import validate
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_fixed_work import grants
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import reference


class PrepareFixedWorkRead(StrictWorkbenchModel):
    workDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    commandId: str = Field(min_length=1, max_length=160)


def require(condition, reason="FIXED_WORK_READ_BINDING_CHANGED"):
    if not condition:
        raise WorkbenchOwnerError(reason, 409)


class FixedWorkActivityReadOwner:
    def __init__(self, authoring, automation):
        self.authoring, self.automation = authoring, automation

    def __call__(self, call):
        context, c = call.context, call.connection
        if (
            context.authentication_source != AuthenticationSource.BROWSER_SESSION
            or not context.principal_id.startswith("human:")
        ):
            raise WorkbenchOwnerError("FIXED_WORK_READ_VIEWER_REQUIRED", 403)
        command = PrepareFixedWorkRead.model_validate(call.payload)
        saved = self.authoring(
            replace(call, operation="READ_FIXED_WORK_DRAFT", payload={}, query={})
        )
        require(saved["digest"] == command.workDigest)
        scope = context.scope.tenant_id, context.scope.security_domain
        row = c.execute(
            "SELECT * FROM fixed_work_triggers.receipts WHERE namespace=%s "
            "AND security_domain=%s AND work_id=%s AND revision_id=%s "
            "AND work_digest=%s ORDER BY recorded_at DESC,event_id DESC LIMIT 1",
            (
                *scope,
                saved["draft"]["workId"],
                saved["draft"]["revisionId"],
                saved["digest"],
            ),
        ).fetchone()
        if row is None:
            return {"state": "NO_RECORD", "workDigest": saved["digest"]}
        p, _progress = PreparedExecutionStore(c).read(*scope, row["workflow_run_id"])
        require(p.digest == row["preparation_digest"])
        principal = OwnerPrincipal(context.principal_id, *scope)
        problem = p.semantics.target.problem
        call.authority.require(
            principal,
            "BUSINESS_PROBLEM",
            "READ",
            "business-problem:" + problem.resource_id,
        )
        source = p.source_snapshot
        call.authority.require(
            principal,
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", source.resource_id, source.revision_id),
        )
        source_record = self.automation.resources(
            replace(
                call,
                operation="READ_PREPARED_RESOURCE",
                payload={},
                query={},
                path={
                    "kind": "knowledge",
                    "identity": source.resource_id,
                    "revision": source.revision_id,
                },
            )
        )
        revision = source_record["revision"]
        require(str(revision["digest"]).removeprefix("sha256:") == source.digest)
        work = self.automation.work(
            context, problem, self.automation.grants.clock(), connection=c
        )
        validate("knowledge", revision["content"], work)
        # Original artifact owner has already verified task/attempt lineage and
        # content digest before committing these immutable identities. Include
        # retained failure evidence too; never relabel it as successful output.
        rows = c.execute(
            "SELECT artifact_id FROM execution_authority.run_artifacts "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
            "ORDER BY artifact_id LIMIT 65",
            (*scope, row["workflow_run_id"]),
        ).fetchall()
        artifact_ids = [r["artifact_id"] for r in rows]
        require(len(artifact_ids) <= 64, "FIXED_WORK_READ_BOUND_EXCEEDED")
        members = (
            ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + p.digest),
            *(
                ExactGrant(
                    "EVIDENCE",
                    "READ_REFERENCE",
                    "evidence-reference:prepared:" + p.digest + ":" + identity,
                )
                for identity in artifact_ids
            ),
        )
        key = "fixed-work-read:" + digest(
            [
                *scope,
                context.principal_id,
                saved["digest"],
                command.commandId,
            ]
        )
        # The request key deliberately excludes the selected Run/artifact set.
        # A changed set on ambiguous replay hits the original owner payload conflict.
        if isinstance(work, AdministratorWorkScope):
            # Preserve the existing administrator authorizer, without introducing
            # a new bypass or issuing any policy grant for an unbounded scope.
            require(
                call.authority.current_action_grants(members) == (True,) * len(members),
                "FIXED_WORK_READ_EXACT_POLICY_REQUIRED",
            )
        else:
            issuer = self.automation.authenticate(context)
            require(issuer.principal_id != context.principal_id)
            self.automation.decide(
                call,
                members,
                key,
                work,
                issuer,
                request_key=key,
            )
        self.automation.proof_grants(call, members)
        return {
            "state": "READ_READY",
            "workDigest": saved["digest"],
            "runId": row["workflow_run_id"],
            "preparationDigest": p.digest,
        }


def fixed_work_activity_read_operations(authoring, automation, *, enabled=False):
    if not enabled:
        return ()
    if automation is None:
        raise ValueError("FIXED_WORK_READ_AUTOMATION_REQUIRED")
    return (
        WorkbenchOperation(
            "PREPARE_FIXED_WORK_ACTIVITY_READ",
            "POST",
            PREFIX + "/teams/{team_id}/revisions/{team_revision_id}/fixed-work-drafts/"
            "{work_id}/revisions/{revision_id}/activity-read",
            PrepareFixedWorkRead,
            None,
            grants,
            FixedWorkActivityReadOwner(authoring, automation),
        ),
    )
