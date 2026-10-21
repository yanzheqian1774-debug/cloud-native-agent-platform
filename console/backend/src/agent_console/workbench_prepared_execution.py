# ruff: noqa: E501 -- Exact scoped SQL and grant identities.
"""Prepared execution operations on the existing authenticated owner transaction."""

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError, ExactGrant
from .execution_preparation import ExecutionPreparation, ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore
from .prepared_execution_application import PreparedExecutionApplication
from .prepared_execution_lineage import (
    validate_approved_preparation,
    validate_participant,
)
from .prepared_execution_resources import resource_read_grants, validate_resources
from .prepared_result_review import PreparedResultReview
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class StartPrepared(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=1, max_length=200)


class RetryPrepared(StartPrepared):
    taskId: str = Field(min_length=1, max_length=200)
    expectedAttemptOrdinal: int = Field(ge=1, le=3)


class ConfirmPreparedResult(StartPrepared):
    evaluationId: str = Field(min_length=1, max_length=200)
    evaluationDigest: str = Field(pattern="^[0-9a-f]{64}$")
    expectedVersion: int = Field(ge=1)
    decision: str = Field(
        pattern="^(ACKNOWLEDGE_UNDETERMINED|DISAGREE|CONFIRM_PROBLEM_SOLVED)$"
    )
    reason: str = Field(min_length=1, max_length=1000)


def result_grant(owner, action, prefix):
    return lambda context, path, payload, query: (
        ExactGrant(owner, action, prefix + path["digest"]),
    )


def grant(action):
    return lambda context, path, payload, query: (
        ExactGrant(
            "EXECUTION", action, "governed-execution:prepared:" + path["digest"]
        ),
    )


def candidate(connection, scope, digest):
    row = connection.execute(
        "SELECT record FROM execution_authority.prepared_candidates WHERE namespace=%s "
        "AND security_domain=%s AND digest=%s",
        (scope.namespace, scope.security_domain, digest),
    ).fetchone()
    if row is None:
        raise ExecutionPreparationError("PREPARED_EXECUTION_NOT_FOUND")
    p = ExecutionPreparation.model_validate(row["record"])
    if p.digest != digest:
        raise ExecutionPreparationError("PREPARED_EXECUTION_DIGEST_MISMATCH")
    return p


class PreparedExecutionOwner:
    def __init__(self, coordinator=None):
        self.coordinator = coordinator

    def __call__(self, call):
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        app = PreparedExecutionApplication(call.connection, principal, call.authority)
        try:
            if call.operation == "PREPARE_NATIVE_EXECUTION":
                p = ExecutionPreparation.model_validate(call.payload)
                if (p.namespace, p.security_domain, p.plan_id) != (
                    principal.tenant_id,
                    principal.security_domain,
                    call.path["plan_id"],
                ):
                    raise ExecutionPreparationError("PREPARED_EXECUTION_NOT_FOUND")
                call.authority.require(
                    principal, "PLAN", "READ", "plan:v2:" + p.plan_id
                )
                validate_approved_preparation(call.connection, p)
                app.validate_root(p)
                for t in p.participants:
                    call.authority.require(
                        principal,
                        "EMPLOYEE",
                        "READ",
                        f"employee:{t.definition.resource_id}:{t.definition.revision_id}",
                    )
                    validate_participant(call.connection, app.scope, t)
                    for resource_grant in resource_read_grants(p, t):
                        call.authority.require(
                            principal,
                            resource_grant.owner,
                            resource_grant.action,
                            resource_grant.exact_resource,
                        )
                    validate_resources(call.connection, app.scope, p, t)
                call.connection.execute(
                    "INSERT INTO execution_authority.prepared_candidates "
                    "(namespace,security_domain,digest,plan_id,plan_version,record,prepared_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (
                        p.namespace,
                        p.security_domain,
                        p.digest,
                        p.plan_id,
                        p.plan_version,
                        Jsonb(p.model_dump(mode="json")),
                        principal.principal_id,
                    ),
                )
                if candidate(call.connection, app.scope, p.digest) != p:
                    raise ExecutionPreparationError(
                        "PREPARED_EXECUTION_REPLAY_CONFLICT"
                    )
                return {
                    "digest": p.digest,
                    "mappingDigest": p.mapping_digest,
                    "resourceState": "BOUND",
                    "admissionRequired": True,
                    "executionStarted": False,
                }
            p = candidate(call.connection, app.scope, call.path["digest"])
            if call.operation == "START_PREPARED_EXECUTION":
                if self.coordinator is None:
                    raise WorkbenchOwnerError(
                        "PREPARED_NATIVE_COORDINATOR_UNAVAILABLE", 503
                    )
                state = app.start(p, call.payload["idempotencyKey"])
                self.coordinator(call, p)
                state = app.store.read(p.namespace, p.security_domain, p.run_id)[1]
                return {"runId": p.run_id, "progress": state.model_dump(mode="json")}
            if call.operation in {
                "CANCEL_PREPARED_EXECUTION",
                "RETRY_PREPARED_TASK",
                "DECLINE_PREPARED_RETRY",
            }:
                from .prepared_execution_cancellation import request_cancel
                from .prepared_execution_control import control_command

                action = (
                    "CANCEL"
                    if call.operation == "CANCEL_PREPARED_EXECUTION"
                    else "RETRY"
                )

                def execute():
                    if action == "CANCEL":
                        state = request_cancel(
                            call.connection,
                            principal,
                            call.authority,
                            p,
                            call.payload["idempotencyKey"],
                        )
                    else:
                        _, current = app.store.read(
                            p.namespace, p.security_domain, p.run_id, lock=True
                        )
                        task = next(
                            (
                                t
                                for t in current.tasks
                                if t.task_id == call.payload["taskId"]
                            ),
                            None,
                        )
                        if (
                            task is None
                            or task.attempt_ordinal
                            != call.payload["expectedAttemptOrdinal"]
                        ):
                            raise ExecutionPreparationError(
                                "RETRY_ATTEMPT_TARGET_STALE"
                            )
                        if call.operation == "DECLINE_PREPARED_RETRY":
                            from .execution_preparation import ProgressEvent
                            from .prepared_execution_observations import sync_projection
                            from .resource_use_domain import stable_id

                            state = app.store.apply(
                                p.namespace,
                                p.security_domain,
                                p.run_id,
                                ProgressEvent(
                                    action="FINALIZE_FAILURE",
                                    task_id=task.task_id,
                                    evidence_id=stable_id(
                                        "decline-retry",
                                        p.run_id,
                                        principal.principal_id,
                                        call.payload["idempotencyKey"],
                                    ),
                                ),
                                expected_version=current.version,
                            )
                            sync_projection(
                                call.connection,
                                (p.namespace, p.security_domain, p.run_id),
                                state,
                            )
                            return {
                                "runId": p.run_id,
                                "progress": state.model_dump(mode="json"),
                            }
                        if self.coordinator is None:
                            raise WorkbenchOwnerError(
                                "PREPARED_NATIVE_COORDINATOR_UNAVAILABLE", 503
                            )
                        self.coordinator(call, p, retry_task=call.payload["taskId"])
                        state = app.store.read(
                            p.namespace, p.security_domain, p.run_id
                        )[1]
                    return {
                        "runId": p.run_id,
                        "progress": state.model_dump(mode="json"),
                    }

                return control_command(
                    call.connection,
                    principal,
                    call.authority,
                    p,
                    action,
                    {**call.payload, "operation": call.operation},
                    execute,
                )
            review = PreparedResultReview(call.connection, principal, call.authority)
            if call.operation == "EVALUATE_PREPARED_EXECUTION":
                return review.evaluate(p, call.payload["idempotencyKey"])
            if call.operation == "CONFIRM_PREPARED_RESULT":
                body = call.payload
                return review.confirm(
                    p,
                    evaluation_id=body["evaluationId"],
                    evaluation_digest=body["evaluationDigest"],
                    expected_version=body["expectedVersion"],
                    decision=body["decision"],
                    reason=body["reason"],
                    command_key=body["idempotencyKey"],
                )
            return self.read(call, app, p)
        except ExecutionPreparationError as exc:
            raise WorkbenchOwnerError(str(exc), 409) from exc

    @staticmethod
    def read(call, app, p):
        key = (p.namespace, p.security_domain, p.run_id)
        exists = call.connection.execute(
            "SELECT 1 FROM execution_authority.run_preparations WHERE namespace=%s "
            "AND security_domain=%s AND workflow_run_id=%s",
            key,
        ).fetchone()
        progress = (
            PreparedExecutionStore(call.connection).read(*key)[1] if exists else None
        )
        artifacts = call.connection.execute(
            "SELECT artifact_id,task_id,attempt_id,digest,octet_length(content) AS bytes,"
            "created_at FROM execution_authority.run_artifacts WHERE namespace=%s "
            "AND security_domain=%s AND workflow_run_id=%s ORDER BY created_at,artifact_id",
            key,
        ).fetchall()
        for artifact in artifacts:
            artifact["contentAccess"] = "RESTRICTED"
            try:
                call.authority.require(
                    app.principal,
                    "EVIDENCE",
                    "READ_REFERENCE",
                    f"evidence-reference:prepared:{p.digest}:"
                    + artifact["artifact_id"],
                )
            except AuthorityError:
                continue
            artifact["contentAccess"] = "AUTHORIZED"
            artifact["content"] = call.connection.execute(
                "SELECT content FROM execution_authority.run_artifacts WHERE namespace=%s "
                "AND security_domain=%s AND workflow_run_id=%s AND artifact_id=%s",
                (*key, artifact["artifact_id"]),
            ).fetchone()["content"]
        admission = {"state": "NOT_ADMITTED", "reason": None}
        try:
            app.validate(p)
            for t in p.participants:
                call.authority.require(
                    app.principal,
                    "SKILL",
                    "INVOKE_SKILL",
                    f"skill-invocation:prepared:{p.digest}:{t.task_id}:1",
                )
        except (AuthorityError, ExecutionPreparationError) as exc:
            admission["reason"] = str(exc)
        else:
            admission["state"] = "ADMITTED"
        usage = []
        from .prepared_skill_invocation import planned_outputs

        for output in planned_outputs(p, progress) if progress else ():
            try:
                call.authority.require(
                    app.principal, "RESOURCE_USE", "READ", output["resourceGrant"]
                )
            except AuthorityError:
                usage.append(
                    {
                        "resourceUseId": output["resourceUseId"],
                        "state": "READ_RESTRICTED",
                    }
                )
                continue
            used = call.connection.execute(
                "SELECT record FROM resource_use.snapshots WHERE namespace=%s AND security_domain=%s AND resource_use_id=%s ORDER BY high_water DESC LIMIT 1",
                (p.namespace, p.security_domain, output["resourceUseId"]),
            ).fetchone()
            usage.append(
                {
                    "resourceUseId": output["resourceUseId"],
                    "snapshot": used["record"] if used else None,
                    "state": used["record"]["effective_state"]
                    if used
                    else "NOT_CALLED",
                }
            )
        outcome = None
        try:
            call.authority.require(
                app.principal, "EVALUATION", "READ", "evaluation:prepared:" + p.digest
            )
        except AuthorityError:
            pass
        else:
            # Snapshot assembly enforces each exact criterion/evidence/resource read.
            if progress and progress.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                PreparedResultReview(
                    call.connection, app.principal, call.authority
                ).snapshot(p)
                row = call.connection.execute(
                    "SELECT o.record FROM product_outcome.heads h JOIN product_outcome.outcomes o USING(namespace,security_domain,outcome_id) WHERE h.namespace=%s AND h.security_domain=%s AND h.workflow_run_id=%s",
                    key,
                ).fetchone()
                outcome = row["record"] if row else None
        events = call.connection.execute(
            "SELECT version,record,created_at FROM execution_authority.prepared_run_events WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY version",
            key,
        ).fetchall()
        from .planning_translation import prepared_task_translation

        return {
            "taskTranslation": prepared_task_translation(p),
            "preparation": p.model_dump(mode="json"),
            "digest": p.digest,
            "progress": progress.model_dump(mode="json") if progress else None,
            "artifacts": artifacts,
            "outcome": outcome,
            "admission": admission,
            "resourceUses": usage,
            "events": events,
            "executionStarted": exists is not None,
            "technicalSuccessNotBusinessSuccess": True,
        }


class PreparedExecutionGrantTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None:
            return False
        for owner, actions, prefix in (
            ("EVALUATION", {"EVALUATE", "READ"}, "evaluation:prepared:"),
            ("HUMAN_CONFIRMATION", {"CONFIRM", "READ"}, "human-confirmation:prepared:"),
        ):
            if (
                grant.owner == owner
                and grant.action in actions
                and grant.exact_resource.startswith(prefix)
            ):
                return (
                    connection.execute(
                        "SELECT 1 FROM execution_authority.prepared_candidates WHERE namespace=%s AND security_domain=%s AND digest=%s",
                        (
                            context.scope.tenant_id,
                            context.scope.security_domain,
                            grant.exact_resource[len(prefix) :],
                        ),
                    ).fetchone()
                    is not None
                )
        prefix = "governed-execution:prepared:"
        if (
            grant.owner == "EXECUTION"
            and grant.action in {"START", "READ", "CANCEL", "RETRY"}
            and grant.exact_resource.startswith(prefix)
        ):
            return (
                connection.execute(
                    "SELECT 1 FROM execution_authority.prepared_candidates WHERE namespace=%s "
                    "AND security_domain=%s AND digest=%s",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        grant.exact_resource[len(prefix) :],
                    ),
                ).fetchone()
                is not None
            )
        for owner, action, prefix in (
            ("EXECUTION", "START", "governed-execution:participant:"),
            ("SKILL", "INVOKE_SKILL", "skill-invocation:prepared:"),
        ):
            if (
                grant.owner != owner
                or grant.action != action
                or not grant.exact_resource.startswith(prefix)
            ):
                continue
            value = grant.exact_resource[len(prefix) :]
            digest, _, suffix = value.partition(":")
            from .execution_domain import ScopeIdentity

            try:
                p = candidate(
                    connection,
                    ScopeIdentity(
                        context.scope.tenant_id, context.scope.security_domain
                    ),
                    digest,
                )
            except ExecutionPreparationError:
                return False
            for t in p.participants:
                if owner == "EXECUTION" and suffix == t.task_id:
                    return True
                if owner == "SKILL" and suffix in {
                    f"{t.task_id}:{i}" for i in range(1, t.max_attempts + 1)
                }:
                    return True
        for owner, action, prefix, field in (
            (
                "EVIDENCE",
                "READ_REFERENCE",
                "evidence-reference:prepared:",
                "evidenceGrant",
            ),
            ("RESOURCE_USE", "READ", "resource-use:prepared:", "resourceGrant"),
        ):
            if (
                grant.owner != owner
                or grant.action != action
                or not grant.exact_resource.startswith(prefix)
            ):
                continue
            digest = grant.exact_resource[len(prefix) :].partition(":")[0]
            from .execution_domain import ScopeIdentity
            from .prepared_skill_invocation import planned_outputs

            try:
                p = candidate(
                    connection,
                    ScopeIdentity(
                        context.scope.tenant_id, context.scope.security_domain
                    ),
                    digest,
                )
            except ExecutionPreparationError:
                return False
            return any(
                item[field] == grant.exact_resource for item in planned_outputs(p)
            )
        return False


def prepared_execution_operations(coordinator=None):
    handler = PreparedExecutionOwner(coordinator)
    path = PREFIX + "/prepared-executions/{digest}"
    return (
        WorkbenchOperation(
            "PREPARE_NATIVE_EXECUTION",
            "POST",
            PREFIX + "/planning-v2/{plan_id}/prepared-executions",
            ExecutionPreparation,
            None,
            lambda ctx, path, payload, query: (
                ExactGrant("PLAN", "PREPARE", "plan:v2:" + path["plan_id"]),
            ),
            handler,
        ),
        WorkbenchOperation(
            "READ_PREPARED_EXECUTION", "GET", path, None, None, grant("READ"), handler
        ),
        WorkbenchOperation(
            "CANCEL_PREPARED_EXECUTION",
            "POST",
            path + "/cancel",
            StartPrepared,
            None,
            grant("CANCEL"),
            handler,
        ),
        WorkbenchOperation(
            "DECLINE_PREPARED_RETRY",
            "POST",
            path + "/decline-retry",
            RetryPrepared,
            None,
            grant("RETRY"),
            handler,
        ),
        WorkbenchOperation(
            "RETRY_PREPARED_TASK",
            "POST",
            path + "/retry",
            RetryPrepared,
            None,
            grant("RETRY"),
            handler,
        ),
        WorkbenchOperation(
            "EVALUATE_PREPARED_EXECUTION",
            "POST",
            path + "/evaluate",
            StartPrepared,
            None,
            result_grant("EVALUATION", "EVALUATE", "evaluation:prepared:"),
            handler,
        ),
        WorkbenchOperation(
            "CONFIRM_PREPARED_RESULT",
            "POST",
            path + "/human-decision",
            ConfirmPreparedResult,
            None,
            result_grant(
                "HUMAN_CONFIRMATION", "CONFIRM", "human-confirmation:prepared:"
            ),
            handler,
        ),
        WorkbenchOperation(
            "START_PREPARED_EXECUTION",
            "POST",
            path + "/start",
            StartPrepared,
            None,
            grant("START"),
            handler,
        ),
    )
