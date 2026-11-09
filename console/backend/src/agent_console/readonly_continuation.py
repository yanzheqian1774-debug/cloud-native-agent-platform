# ruff: noqa: E501 -- Exact owner SQL, authorization references and Chinese contracts.
"""Atomic, explicitly authorized resource-to-one-Run continuation on existing owners.

Native alone performs effects after commit. GET never dispatches or evaluates.
"""

from dataclasses import replace
from datetime import UTC, datetime

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError, ExactGrant
from .cost_execution_revision import (
    PLANNING_ONLY,
    READ_ONLY_PLANNING,
    CostExecutionRevisionRequest,
    execution_successor,
)
from .execution_preparation import ExecutionPreparation
from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    PolicyResourcePreparationOrigin,
)
from .planning_contracts import validation_report
from .planning_source_change import approved_source
from .prepared_skill_invocation import planned_outputs
from .readonly_instance_assembly import assemble
from .resource_automation_policy import source_digest
from .resource_policy_lineage import require_supported_lineage
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_execution import PreparedExecutionOwner
from .workbench_prepared_resources import bind_service


class ContinueReadonly(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


def command_key(plan):
    # Caller/session keys and policy renewals cannot mint another Run for this Plan.
    return "readonly-continuation:" + plan.digest


def resource_policy_digest(automation, call, development):
    if development:
        from .resource_policy_contract import DevelopmentAdministratorReview

        # Match the current role/generation used by resource preparation.
        return DevelopmentAdministratorReview(
            call.context.principal_id, call.policy_generation, "0" * 64
        ).policy_digest
    return automation.policy.digest


class ReadonlyContinuation:
    def __init__(self, automation, policy, coordinator):
        self.automation, self.policy, self.coordinator = automation, policy, coordinator
        self.execution = coordinator.repository
        self.owner = PreparedExecutionOwner(
            coordinator, sales_v2_candidate=automation.sales_v2_candidate
        )

    def capability(self, context, root):
        from .development_administrator import for_service

        if self.policy.enabled and for_service(self.automation.grants, context):
            return True
        return self.policy.enabled and any(
            (w.namespace, w.securityDomain, w.subject, w.problem)
            == (
                context.scope.tenant_id,
                context.scope.security_domain,
                context.principal_id,
                root,
            )
            and w.expiresAt.tzinfo is not None
            and w.expiresAt > self.automation.grants.clock()
            for w in self.policy.works
        )

    def __call__(self, call):
        try:
            return self.continue_work(call)
        except (AuthorityError, WorkbenchOwnerError):
            raise
        except ValueError as exc:
            import re

            reason = str(exc)
            if not re.fullmatch(r"[A-Z0-9_]{1,120}", reason):
                reason = "READONLY_CONTINUATION_VALIDATION_FAILED"
            raise WorkbenchOwnerError(reason, 409) from exc

    def continue_work(self, call):
        args = (
            call.query
            if call.operation == "READ_READONLY_CONTINUATION"
            else call.payload
        )
        version = args["version"]
        app = self.automation.bound_app(call)
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        scope = app.scope(principal)
        identity = call.path["proposal_id"]
        issuer = self.automation.authenticate(call.context)
        with app.repository.transaction(scope, identity, authorized=True) as cur:
            c = cur.connection
            original = app.repository.read_plan(cur, scope, identity, version)
            plan = ConfirmedPlanRevision.model_validate(original["plan"])
            if original["digest"] != plan.digest:
                raise WorkbenchOwnerError("READONLY_SOURCE_PLAN_DIGEST_MISMATCH", 409)
            key = command_key(plan)
            # Same transaction's Plan lock serializes first POST and GET recovery.
            prior = c.execute(
                "SELECT digest,result FROM execution_authority.prepared_resource_commands "
                "WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
                (scope.namespace, scope.security_domain, principal.principal_id, key),
            ).fetchone()
            source = approved_source(plan.semantics)
            call.authority.require(
                principal,
                "KNOWLEDGE",
                "READ_RESOURCE",
                "knowledge:prepared-resource:"
                + source.resource_id
                + ":"
                + source.revision_id,
            )
            source_service = bind_service(self.automation.services["knowledge"], c)
            content = source_service.repository.get(
                source_service.scope(scope.namespace, scope.security_domain),
                source.resource_id,
            )
            revision = next(
                (
                    r
                    for r in content["revisions"]
                    if r["revisionId"] == source.revision_id
                ),
                None,
            )
            if revision is None or revision["digest"] != source.digest:
                raise WorkbenchOwnerError("READONLY_WORK_SOURCE_MISMATCH", 409)
            digest = source_digest(revision["content"])
            now = self.automation.grants.clock()
            from .development_administrator import for_call

            development = for_call(call)
            if development:
                import json

                from .readonly_continuation_policy import ReadonlyWork

                schema = json.loads(
                    revision["content"]["documents"][0]["chunks"][0]["content"]
                )["schemaVersion"]
                case = {
                    "document-review-source.v1": "document",
                    "tabular-diagnostic-source.v1": "tabular",
                    "sales-diagnostic-source.v1": "sales",
                    "synthetic-delivery-source.v1": "delivery",
                }.get(schema)
                candidates = {
                    w.nativeAgentName
                    for w in self.policy.works
                    if w.case == case
                    and w.namespace == scope.namespace
                    and w.securityDomain == scope.security_domain
                }
                if case in {"tabular", "document"}:
                    candidates = (
                        {self.policy.developmentTabularAgentName}
                        if self.policy.developmentTabularAgentName
                        else set()
                    )
                if not self.policy.enabled or len(candidates) != 1:
                    raise WorkbenchOwnerError(
                        "CONVERSATION_EXECUTOR_NOT_CONFIGURED", 409
                    )
                resource_work = self.automation.work(
                    call.context, plan.semantics.target.problem, now
                )
                approved_work = ReadonlyWork(
                    namespace=scope.namespace,
                    securityDomain=scope.security_domain,
                    subject=principal.principal_id,
                    problem=plan.semantics.target.problem,
                    sourceContentDigests=(digest,),
                    case=case,
                    nativeAgentName=next(iter(candidates)),
                    expiresAt=resource_work.expiresAt,
                )
            else:
                approved_work = self.policy.work(
                    call.context, plan.semantics.target.problem, digest, now
                )
                resource_work = self.automation.policy.work(
                    call.context, plan.semantics.target.problem, now
                )
            work = resource_work.model_copy(
                update={
                    "expiresAt": min(resource_work.expiresAt, approved_work.expiresAt)
                }
            )
            payload_digest = canonical_digest(
                [plan.digest, self.policy.digest, self.automation.policy.digest]
            )
            if prior:
                if prior["digest"] != payload_digest:
                    raise WorkbenchOwnerError("READONLY_WORK_POLICY_CHANGED", 409)
                return self.read(call, prior["result"])
            if call.operation == "READ_READONLY_CONTINUATION":
                raise WorkbenchOwnerError("READONLY_CONTINUATION_NOT_FOUND", 404)
            require_supported_lineage(app, cur, scope, plan)
            head = c.execute(
                "SELECT max(version) version FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s",
                (scope.namespace, scope.security_domain, identity),
            ).fetchone()["version"]
            if head != version:
                raise WorkbenchOwnerError(
                    "READONLY_CONTINUATION_SOURCE_PLAN_STALE", 409
                )
            if (
                plan.semantics.business_rules.count(PLANNING_ONLY) != 1
                or plan.semantics.boundaries.count(READ_ONLY_PLANNING) != 1
            ):
                raise WorkbenchOwnerError(
                    "READONLY_EXISTING_EXECUTION_PLAN_NOT_RESTARTED", 409
                )
            app.validate_target(principal, plan.semantics.target, c)
            ready = c.execute(
                "SELECT record FROM execution_authority.resource_automation WHERE namespace=%s AND security_domain=%s "
                "AND subject_id=%s AND plan_id=%s AND plan_version=%s AND record->>'state'='READY' "
                "AND record->'policy'->>'digest'=%s ORDER BY created_at DESC LIMIT 1",
                (
                    scope.namespace,
                    scope.security_domain,
                    principal.principal_id,
                    identity,
                    version,
                    resource_policy_digest(self.automation, call, development),
                ),
            ).fetchone()
            if ready is None:
                raise WorkbenchOwnerError("READONLY_RESOURCE_PREPARATION_REQUIRED", 409)
            ready = ready["record"]
            if ready["planDigest"] != plan.digest:
                raise WorkbenchOwnerError(
                    "READONLY_PREPARATION_PLAN_DIGEST_MISMATCH", 409
                )
            self.automation.recheck(call, ready)
            if self.automation.runtime_probe(scope.namespace)["status"] != "PASSED":
                raise WorkbenchOwnerError("READONLY_RUNTIME_NOT_READY", 409)
            if not 4 <= len(
                ready["resources"]
            ) <= self.automation.policy.maxResources or any(
                r["state"] != "READY" for r in ready["resources"]
            ):
                raise WorkbenchOwnerError(
                    "READONLY_EXACT_RESOURCE_COMPOSITION_REQUIRED", 409
                )
            proof_ids = []

            def authorize(owner, action, reference):
                members = [ExactGrant(owner, action, reference)]
                proof = self.automation.decide(
                    call,
                    members,
                    key
                    + ":execution:"
                    + self.policy.digest
                    + ":"
                    + canonical_digest([owner, action, reference]),
                    work,
                    issuer,
                    purpose="READONLY_WORK_EXECUTION",
                )
                self.automation.proof_grants(call, members)
                proof_ids.append(proof.decision_id)
                return proof

            employee = ready["assembly"]["definition"]
            binding = assemble(
                self.execution,
                c,
                {
                    "case": approved_work.case,
                    "namespace": scope.namespace,
                    "securityDomain": scope.security_domain,
                    "resources": [
                        {
                            "kind": r["kind"],
                            "identity": r["reference"]["resource_id"],
                            "revisionId": r["reference"]["revision_id"],
                            "digest": r["reference"]["digest"],
                        }
                        for r in ready["resources"]
                    ],
                },
                {
                    "employeeDefinitionId": employee["resource_id"],
                    "employeeDefinitionRevisionId": employee["revision_id"],
                    "employeeDefinitionDigest": employee["digest"],
                },
                plan.semantics.model_dump(mode="json"),
                principal=principal,
                authorize=authorize,
                plan_digest=plan.digest,
                agent_name=approved_work.nativeAgentName,
                sales_v2_candidate=self.automation.sales_v2_candidate,
            )
            for action in ("READ", "PREPARE", "APPROVE"):
                execution_proof = authorize("PLAN", action, "plan:v2:" + identity)
            source_proposal = app.repository.proposal(
                cur, scope, plan.source_proposal_id, plan.source_proposal_revision
            )
            request = CostExecutionRevisionRequest(
                case=approved_work.case,
                plan_version=version,
                plan_digest=plan.digest,
                source_snapshot=source,
                mapping_digest=binding["mappingDigest"],
                selections={
                    r.requirement_id: r.selected
                    for r in plan.semantics.requirements
                    if r.selected is not None
                },
            )
            successor, _ = execution_successor(plan, source_proposal, request)
            # This is a real policy preparation successor, never a fabricated
            # model invocation. Exact predecessor retains original model/source
            # change provenance even when the historical source uses legacy None.
            successor = successor.model_copy(
                update={
                    "invocation_id": None,
                    "origin": PolicyResourcePreparationOrigin(
                        namespace=scope.namespace,
                        security_domain=scope.security_domain,
                        root=plan.semantics.target.problem,
                        source_snapshot=source,
                        predecessor_plan=ExactReference(
                            resource_id=identity,
                            revision_id=str(plan.version),
                            digest=plan.digest,
                        ),
                        prepared_by=issuer.principal_id,
                        policy_basis=execution_proof.record(issuer.principal_id),
                    ),
                }
            )
            validation_report(successor.semantics)
            app.repository.add_proposal(cur, scope, successor)
            confirmation = app.repository.confirmation(
                cur,
                scope,
                successor,
                actor=issuer.principal_id,
                key=key + ":execution-plan",
                expected_plan_version=version,
                authority_basis="POLICY_READONLY_EXECUTION:"
                + self.policy.digest
                + ":"
                + proof_ids[-1],
                approval_kind="POLICY_READONLY_EXECUTION_APPROVAL",
            )
            execution_plan = ConfirmedPlanRevision.model_validate(confirmation["plan"])
            p = ExecutionPreparation(
                **binding["mapping"],
                plan_id=identity,
                plan_version=execution_plan.version,
                plan_digest=execution_plan.digest,
                approval_id=confirmation["approval"]["approval_decision_id"],
                semantics=execution_plan.semantics,
            )
            prepared = self.owner(
                replace(
                    call,
                    operation="PREPARE_NATIVE_EXECUTION",
                    path={"plan_id": identity},
                    payload=p.model_dump(mode="json"),
                )
            )
            if prepared["digest"] != p.digest:
                raise WorkbenchOwnerError("READONLY_PREPARATION_BINDING_CONFLICT", 409)
            # Independent exact Run, each participant, each invocation and evaluation.
            for owner, action, reference in execution_grants(p):
                authorize(owner, action, reference)
            started = self.owner(
                replace(
                    call,
                    operation="START_PREPARED_EXECUTION",
                    path={"digest": p.digest},
                    payload={"idempotencyKey": key + ":start"},
                )
            )
            record = {
                "schemaVersion": "readonly-continuation.v1",
                "developmentJourney": development,
                "sourcePlanId": identity,
                "sourcePlanVersion": version,
                "sourcePlanDigest": plan.digest,
                "executionPlan": confirmation,
                "preparationDigest": p.digest,
                "runId": started["runId"],
                "resourcePreparationKey": ready["requestKey"],
                "instancesCreated": 2,
                "instanceBinding": binding,
                "executionAuthorizationDigest": self.policy.digest,
                "sourceContentDigest": digest,
                "case": approved_work.case,
                "nativeAgentName": approved_work.nativeAgentName,
                "authorizationExpiresAt": work.expiresAt.isoformat(),
                "executionPolicyId": self.policy.policyId,
                "executionPolicyVersion": self.policy.policyVersion,
                "policyIssuer": issuer.principal_id,
                "subject": principal.principal_id,
                "policyDecisionIds": sorted(set(proof_ids)),
                "createdAt": datetime.now(UTC).isoformat(),
                "modelCalls": 0,
                "humanResourceApprovalClicks": 0,
                "executionStarted": True,
            }
            c.execute(
                "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    principal.principal_id,
                    key,
                    payload_digest,
                    Jsonb(record),
                ),
            )
            return self.read(call, record)

    def read(self, call, record):
        from .workbench_prepared_execution import candidate

        scope = self.execution_scope(call)
        p = candidate(call.connection, scope, record["preparationDigest"])
        principal = OwnerPrincipal(
            call.context.principal_id, scope.namespace, scope.security_domain
        )
        call.authority.require(
            principal, "EXECUTION", "READ", "governed-execution:prepared:" + p.digest
        )
        view = self.owner(
            replace(
                call,
                operation="READ_PREPARED_EXECUTION",
                path={"digest": p.digest},
                payload={},
            )
        )
        return {"receipt": record, "execution": view}

    @staticmethod
    def execution_scope(call):
        from .execution_domain import ScopeIdentity

        return ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )


def execution_grants(p):
    items = [
        ("EXECUTION", a, "governed-execution:prepared:" + p.digest)
        for a in ("START", "READ")
    ]
    items += [
        ("EVALUATION", a, "evaluation:prepared:" + p.digest)
        for a in ("EVALUATE", "READ")
    ]
    items += [("HUMAN_CONFIRMATION", "READ", "human-confirmation:prepared:" + p.digest)]
    for task in p.participants:
        items.append(
            (
                "EXECUTION",
                "START",
                f"governed-execution:participant:{p.digest}:{task.task_id}",
            )
        )
        items.append(
            (
                "SKILL",
                "INVOKE_SKILL",
                f"skill-invocation:prepared:{p.digest}:{task.task_id}:1",
            )
        )
    for item in planned_outputs(p):
        items.extend(
            [
                ("EVIDENCE", "READ_REFERENCE", item["evidenceGrant"]),
                ("RESOURCE_USE", "READ", item["resourceGrant"]),
            ]
        )
    return items


def operations(handler):
    from .resource_automation import target_grants

    path = PREFIX + "/planning-v2/{proposal_id}/readonly-continuation"
    return (
        WorkbenchOperation(
            "CONTINUE_READONLY_WORK",
            "POST",
            path,
            ContinueReadonly,
            None,
            target_grants("APPROVE"),
            handler,
        ),
        WorkbenchOperation(
            "READ_READONLY_CONTINUATION",
            "GET",
            path,
            None,
            ContinueReadonly,
            target_grants("READ"),
            handler,
        ),
    )
