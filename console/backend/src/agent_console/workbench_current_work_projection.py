"""Apply existing Native, evaluation and private-conversation read boundaries."""

from datetime import datetime

from .authority_contracts import ExactGrant
from .business_problem_authorization import (
    criteria_resource,
    criterion_revision_resource,
)
from .execution_preparation import RunProgress
from .ontology_execution import parse_preparation
from .prepared_execution_resources import resource_read_grants
from .prepared_result_review import PreparedResultReview
from .prepared_skill_invocation import planned_outputs
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal
from .workbench_current_work_authorization import readable_grants
from .workbench_current_work_page import CurrentWorkItem
from .workbench_owner_authorization import WorkbenchOwnerError

TERMINAL = {
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "CANCELED",
    "RECOVERY_REQUIRED",
    "UNKNOWN",
    "OUTCOME_UNKNOWN",
}


def evaluation_grants(preparation, progress):
    target = preparation.semantics.target
    result = [
        ExactGrant("EVALUATION", "READ", "evaluation:prepared:" + preparation.digest),
        ExactGrant(
            "SUCCESS_CRITERIA_SET",
            "READ",
            criteria_resource(target.problem.resource_id),
        ),
    ]
    result.extend(
        ExactGrant("SUCCESS_CRITERION", "READ", criterion_revision_resource(identity))
        for identity in target.criterion_revision_ids
    )
    for output in planned_outputs(preparation, progress):
        result.extend(
            (
                ExactGrant("EVIDENCE", "READ_REFERENCE", output["evidenceGrant"]),
                ExactGrant("RESOURCE_USE", "READ", output["resourceGrant"]),
            )
        )
    return tuple(result)


def project_runs(call, rows, *, verified_administrator, include_outcomes=True):
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    preparations = [parse_preparation(row["preparation"]) for row in rows]
    progress = [RunProgress.model_validate(row["progress"]) for row in rows]
    requirements = []
    for row, p, state in zip(rows, preparations, progress, strict=True):
        if (
            p.namespace != call.context.scope.tenant_id
            or p.security_domain != call.context.scope.security_domain
            or p.digest != row["digest"]
            or p.run_id != row["workflow_run_id"]
            or state.version != row["progress_version"]
        ):
            raise WorkbenchOwnerError("CURRENT_WORK_IDENTITY_MISMATCH", 503)
        question = (
            tuple(g for t in p.participants for g in resource_read_grants(p, t))
            if verified_administrator
            else ()
        )
        evaluation = (
            evaluation_grants(p, state)
            if include_outcomes
            and row["outcome_version"] is not None
            and state.state in {"SUCCEEDED", "FAILED", "CANCELLED"}
            else ()
        )
        requirements.append((question, evaluation))
    grants = tuple(g for groups in requirements for group in groups for g in group)
    allowed = dict(zip(grants, readable_grants(call, grants), strict=True))
    result = []
    for row, p, state, (question_grants, outcome_grants) in zip(
        rows, preparations, progress, requirements, strict=True
    ):
        # Native progress currently requires the development role and all bound
        # resource reads. Unknown access is null, not a false zero.
        question_readable = verified_administrator and all(
            allowed[g] for g in question_grants
        )
        pending, answered, question_digest = None, None, None
        if question_readable:
            if any(
                q["answered"] and q["answerDigest"] != q["questionDigest"]
                for q in row["questions"]
            ):
                raise WorkbenchOwnerError(
                    "CURRENT_WORK_QUESTION_IDENTITY_MISMATCH", 503
                )
            question_digest = canonical_digest(row["questions"])
            answered = sum(q["answered"] for q in row["questions"])
            pending = (
                0
                if state.state != "RUNNING" or state.cancellation_request_id
                else sum(
                    not q["answered"]
                    and datetime.fromisoformat(q["expiresAt"]) > row["read_at"]
                    for q in row["questions"]
                )
            )
        resolution, outcome_version = None, None
        if outcome_grants and all(allowed[g] for g in outcome_grants):
            # Reuse the current evidence/criteria integrity checks. No evaluation
            # command is run and no outcome is created by this read.
            snapshot = PreparedResultReview(
                call.connection, principal, call.authority
            ).snapshot(p)
            if snapshot["runVersion"] != row["progress_version"]:
                raise WorkbenchOwnerError("CURRENT_WORK_SNAPSHOT_CHANGED", 503)
            resolution, outcome_version = (
                row["business_resolution"],
                row["outcome_version"],
            )
        origins = [
            o
            for o in row["origins"]
            if o["schemaVersion"] == 1
            and (verified_administrator or o["ownerId"] == call.context.principal_id)
        ]
        # Prefer a matching persisted journey; an ordinary exact link does not
        # claim to be the original conversation. Never infer by title.
        origin = next(
            (o for o in origins if o["journeyMatches"]), origins[0] if origins else None
        )
        display = (
            "completed"
            if state.state == "SUCCEEDED"
            else "cancelled"
            if state.state in {"CANCELLED", "CANCELED"}
            else "failed"
            if state.state == "FAILED"
            else "unknown"
            if state.state in TERMINAL
            or state.state == "CANCEL_REQUESTED"
            or state.cancellation_request_id
            or (state.state == "RUNNING" and pending is None)
            else "waiting"
            if pending
            else "running"
        )
        result.append(
            CurrentWorkItem(
                workflowRunId=p.run_id,
                preparationDigest=p.digest,
                title=row["title"],
                createdAt=row["created_at"],
                initiatorId=row["initiators"][0]
                if len(row["initiators"]) == 1
                else None,
                executionState=state.state,
                displayState=display,
                progressVersion=state.version,
                problemId=row["business_problem_id"],
                problemRevisionId=row["problem_revision_id"],
                problemDigest=row["problem_digest"],
                pendingQuestionCount=pending,
                answeredQuestionCount=answered,
                questionsDigest=question_digest,
                artifactCount=row["artifact_count"],
                planVersion=p.plan_version,
                participantCount=len({t.instance_id for t in p.participants}),
                completedTaskCount=sum(t.state == "SUCCEEDED" for t in state.tasks),
                taskCount=len(p.semantics.tasks),
                updatedAt=row.get("progress_updated_at"),
                businessResolution=resolution,
                outcomeVersion=outcome_version,
                originConversationId=origin["conversationId"] if origin else None,
                originVerified=bool(origin and origin["journeyMatches"]),
            )
        )
    return result
