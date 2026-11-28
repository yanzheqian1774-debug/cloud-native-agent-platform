# ruff: noqa: E501 -- Exact scoped owner queries and Chinese product labels.
"""D11 same-transaction policy decisions, resource publication and assembly.

No provider invocation, job dispatch, execution admission, or Human outcome write.
The browser provides a Plan version/key, never grants, an actor, or resource IDs.
"""

import copy
import hashlib
from contextlib import nullcontext
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_serializer

from . import owned_business_resource_adapter as owned_resources
from .authority_contracts import AuthorityError, ExactGrant
from .capability_plan_confirmation import CapabilityPlanSource
from .digital_employee_definition import CompositionMember, EmployeeRevision, MemberKind
from .execution_domain import ScopeIdentity
from .grant_administration_application import GrantDecisionCommand, GrantRequestCommand
from .plan_suggestion_domain import ConfirmedPlanRevision, ExactReference
from .plan_suggestion_postgres import PostgresPlanningRepository
from .planning_source_change import approved_source
from .resource_automation_validation import validate
from .resource_policy_contract import PolicyReview
from .resource_policy_lineage import require_supported_lineage
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import (
    OWNERS,
    TABLES,
    PreparedResourceOwner,
    reference,
)


class PrepareResources(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    idempotencyKey: str = Field(min_length=1, max_length=160)


class SelectEmployeeResources(CapabilityPlanSource):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    expectedProposalRevision: int = Field(ge=1)
    employee: ExactReference
    ontologySuccessor: ExactReference | None = None
    idempotencyKey: str = Field(min_length=1, max_length=120)

    @model_serializer(mode="wrap")
    def compatible_selection(self, handler):
        result = handler(self)
        if self.ontologySuccessor is None:
            result.pop("ontologySuccessor", None)
        return result


class ReadEmployeeSelection(CapabilityPlanSource):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    key: str = Field(min_length=1, max_length=120)


class ReadPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    key: str = Field(min_length=1, max_length=160)


def migrate(c):
    path = Path(__file__).parents[2] / "migrations/0044_resource_automation.sql"
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    c.execute("SELECT pg_advisory_xact_lock(3240044)")
    c.execute(
        "CREATE TABLE IF NOT EXISTS "
        "execution_authority.resource_policy_migrations (version integer PRIMARY "
        "KEY,checksum text NOT NULL)"
    )
    previous = c.execute(
        "SELECT checksum FROM execution_authority.resource_policy_migrations "
        "WHERE version=44"
    ).fetchone()
    if previous and previous["checksum"] != checksum:
        raise AuthorityError("RESOURCE_POLICY_SCHEMA_INCOMPATIBLE")
    versions = c.execute(
        "SELECT version,checksum FROM "
        "execution_authority.resource_policy_migrations ORDER BY version"
    ).fetchall()
    if versions and versions != [{"version": 44, "checksum": checksum}]:
        raise AuthorityError("RESOURCE_POLICY_SCHEMA_INCOMPATIBLE")
    c.execute(path.read_text())
    c.execute(
        "INSERT INTO execution_authority.resource_policy_migrations "
        "VALUES(44,%s) ON CONFLICT DO NOTHING",
        (checksum,),
    )


def bound_grants(service, c):
    # All normal owner request/decision/current-target checks, one owner UoW.
    clone = copy.copy(service)
    clone.repository = copy.copy(service.repository)
    clone.repository.connection_scope = lambda connection=None: nullcontext(c)
    return clone


def target_grants(action):
    def build(context, path, payload, query):
        resource = "plan:v2:" + path["proposal_id"]
        return tuple(ExactGrant("PLAN", a, resource) for a in sorted({"READ", action}))

    return build


class ResourceAutomation:
    def __init__(
        self,
        policy,
        grants,
        planning,
        services,
        employees,
        *,
        runtime_probe=None,
        sales_v2_candidate=False,
    ):
        self.policy, self.grants, self.planning = policy, grants, planning
        self.resources = PreparedResourceOwner(services)
        self.services, self.employees = services, employees
        self.runtime_probe = runtime_probe or policy.probe_runtime
        self.sales_v2_candidate = sales_v2_candidate
        self.owned_business = None

    def authenticate(self, context):
        from .development_administrator import for_service

        if for_service(self.grants, context):
            return context
        return self.policy.authenticate(self.grants, context)

    def work(
        self,
        context,
        root,
        now,
        *,
        connection=None,
        source_digest=None,
        history=False,
        plan=None,
    ):
        from .development_administrator import for_service
        from .resource_automation_policy import AdministratorWorkScope

        if for_service(self.grants, context):
            return AdministratorWorkScope(
                namespace=context.scope.tenant_id,
                securityDomain=context.scope.security_domain,
                subject=context.principal_id,
                problem=root,
                expiresAt=now + timedelta(hours=1),
            )
        try:
            return self.policy.work(context, root, now)
        except AuthorityError as exc:
            if (
                str(exc) != "RESOURCE_POLICY_WORK_SCOPE_DENIED"
                or self.owned_business is None
            ):
                raise
        if not self.policy.enabled:
            raise AuthorityError("RESOURCE_POLICY_DISABLED")
        with self.grants.repository.connection_scope(connection) as current:
            return owned_resources.derive_work(
                self.owned_business,
                current,
                context,
                root,
                source_digest=source_digest,
                history=history,
                plan=plan,
            )

    def selection_work(self, call, plan, *, key=None):
        try:
            return self.work(
                call.context,
                plan.semantics.target.problem,
                self.grants.clock(),
                connection=call.connection,
                plan=plan,
            )
        except AuthorityError as exc:
            if (
                str(exc) != "OWNED_BUSINESS_POLICY_BINDING_CHANGED"
                or self.owned_business is None
            ):
                raise
        from .owned_business_admission_successor import fresh

        owner = self.owned_business
        stored = fresh(owner, call.connection, call.context, plan, key=key)
        binding = owner.work_reader.work(
            call.connection,
            call.context,
            plan.semantics.target.problem,
            plan=plan,
            _selection_record=stored,
        )
        work = owned_resources.from_binding(
            binding, call.context, plan.semantics.target.problem
        )
        return work.model_copy(
            update={
                "selectionAdmission": {
                    "identity": stored["admission_id"],
                    "preview": key is None,
                    "predecessor": plan.model_dump(mode="json"),
                }
            }
        )

    def decide(
        self,
        call,
        members,
        key,
        work,
        issuer,
        *,
        purpose="RESOURCE_PREPARATION",
        request_key=None,
    ):
        if isinstance(work, owned_resources.OwnedResourceWork):
            if work.historyRead:
                raise AuthorityError("OWNED_BUSINESS_HISTORY_NOT_EXECUTABLE")
            if work.selectionAdmission is not None:
                from .owned_business_admission_successor import read_exact

                selected = work.selectionAdmission
                if selected["preview"]:
                    raise AuthorityError("OWNED_BUSINESS_SUCCESSOR_PREVIEW_ONLY")
                stored = read_exact(
                    call.connection,
                    selected["identity"],
                    work.namespace,
                    work.securityDomain,
                    work.subject,
                    expected_digest=work.admissionRecordDigest,
                )
                predecessor = ConfirmedPlanRevision.model_validate(
                    selected["predecessor"]
                )
                from .owned_resource_assembly import plan_reference

                if stored["successor"]["identityBasis"][
                    "predecessorPlan"
                ] != plan_reference(predecessor).model_dump(mode="json"):
                    raise AuthorityError("OWNED_BUSINESS_SUCCESSOR_PLAN_CHANGED")
                binding = self.owned_business.work_reader.work(
                    call.connection,
                    call.context,
                    work.problem,
                    plan=predecessor,
                    _selection_record=stored,
                )
                current = owned_resources.from_binding(
                    binding, call.context, work.problem
                )
            else:
                current = owned_resources.derive_work(
                    self.owned_business,
                    call.connection,
                    call.context,
                    work.problem,
                    source_digest=work.businessScope.sourceContentDigest,
                    plan=(
                        ExactReference.model_validate(work.assemblyAdoption["plan"])
                        if work.assemblyAdoption is not None
                        else None
                    ),
                )
            if owned_resources.evidence(current) != owned_resources.evidence(work):
                raise AuthorityError("OWNED_BUSINESS_ADMISSION_CHANGED")
        members = tuple(
            sorted(set(members), key=lambda g: (g.owner, g.action, g.exact_resource))
        )
        from .development_administrator import for_call
        from .resource_policy_contract import DevelopmentAdministratorReview

        if for_call(call):
            return DevelopmentAdministratorReview(
                call.context.principal_id,
                call.policy_generation,
                canonical_digest([key, [vars_grant(g) for g in members]]),
            )
        for g in members:
            if self.grants.authorization.has_dynamic_revocation(
                call.context,
                g,
                now=self.grants.clock(),
                recovery_epoch=self.grants.recovery_epoch,
            ):
                raise AuthorityError("RESOURCE_PERMISSION_REVOKED")
        grants = bound_grants(self.grants, call.connection)
        request = grants.submit_request(
            call.context,
            GrantRequestCommand(
                purpose,
                members,
                request_key
                or "d11-request:"
                + canonical_digest([key, [vars_grant(g) for g in members]]),
            ),
        )
        # Exact same expiry for owner idempotency replay, anchored to request time.
        expiry = min(
            work.expiresAt,
            request.created_at + timedelta(seconds=self.policy.grantTTLSeconds),
        )
        if expiry <= grants.clock():
            raise AuthorityError("RESOURCE_POLICY_DECISION_EXPIRED")
        decision = grants.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_BUSINESS_DUTY",
                "POLICY",
                "resource-preparation:"
                + self.policy.policyId
                + ":"
                + self.policy.policyVersion
                + ":"
                + self.policy.digest,
                None,
                expiry,
                "d11-decision:" + canonical_digest([key, request.request_id]),
                expected_version=1,
            ),
        )
        return PolicyReview(
            self.policy.policyId,
            self.policy.policyVersion,
            self.policy.digest,
            decision.decision_id,
            issuer.principal_id,
            call.context.principal_id,
            canonical_digest(work.model_dump(mode="json")),
        )

    def proof_grants(self, call, grants):
        p = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        for g in grants:
            call.authority.require(p, g.owner, g.action, g.exact_resource)

    def bound_app(self, call):
        app = copy.copy(self.planning)
        app.repository = PostgresPlanningRepository(
            self.planning.repository.pool, call.connection
        )
        app.authority = call.authority
        return app

    def capability(self, context, root=None):
        try:
            self.authenticate(context)
            if root is not None:
                self.work(context, root, self.grants.clock())
        except (AuthorityError, OSError, ValueError):
            return {"enabled": False}
        return {
            **(
                {
                    "readonlyContinuationEnabled": self.continuation.capability(
                        context, root
                    )
                }
                if getattr(self, "continuation", None) is not None and root is not None
                else {}
            ),
            "enabled": True,
            "policyVersion": self.policy.policyVersion,
            "policyStamp": canonical_digest(
                [
                    self.policy.digest,
                    self.grants.generation.generation,
                    self.grants.recovery_epoch,
                ]
            ),
        }

    def source_change(self, call):
        from .plan_suggestion_domain import ProposalRevision
        from .planning_contracts import validation_report
        from .planning_source_change import (
            SourceChangeRequest,
            prepare,
            validate_confirmation,
        )

        request = SourceChangeRequest.model_validate(call.payload)
        app = self.bound_app(call)
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        scope = app.scope(principal)
        issuer = self.authenticate(call.context)
        identity = call.path["proposal_id"]
        with app.repository.transaction(scope, identity, authorized=True) as cur:
            plan = ConfirmedPlanRevision.model_validate(
                app.repository.read_plan(cur, scope, identity, request.plan_version)[
                    "plan"
                ]
            )
            require_supported_lineage(app, cur, scope, plan)
            work = self.work(
                call.context,
                plan.semantics.target.problem,
                self.grants.clock(),
                connection=cur.connection,
                plan=plan,
            )
            owned_resources.require_plan(work, plan)
            owned_resources.require_capability(self, call, work)
            # Existing publication and data-scope checks precede any new privilege.
            for ref in (request.old_source, request.new_source):
                self.prepare_one(
                    call,
                    "knowledge",
                    ref,
                    "source:" + request.idempotency_key,
                    work,
                    issuer,
                )
            members = [
                ExactGrant("PLAN", a, "plan:v2:" + identity)
                for a in ("READ", "PREPARE", "APPROVE")
            ]
            target = plan.semantics.target
            members.extend(
                [
                    ExactGrant(
                        "BUSINESS_PROBLEM",
                        "READ",
                        "business-problem:" + target.problem.resource_id,
                    ),
                    ExactGrant(
                        "SUCCESS_CRITERIA_SET",
                        "READ",
                        "success-criteria-set:" + target.problem.resource_id,
                    ),
                ]
            )
            members.extend(
                ExactGrant(
                    "SUCCESS_CRITERION", "READ", "success-criterion:revision:" + r
                )
                for r in target.criterion_revision_ids
            )
            proof = self.decide(
                call, members, "source:" + request.idempotency_key, work, issuer
            )
            self.proof_grants(call, members)
            value = prepare(app, principal, identity, request, policy_basis=proof)
            if not value["proposal"]:
                raise WorkbenchOwnerError(
                    "POLICY_SOURCE_CHANGE_BUSINESS_DECISION_REQUIRED", 409
                )
            proposal = ProposalRevision.model_validate(value["proposal"])
            validate_confirmation(app, principal, cur.connection, proposal)
            validation_report(proposal.semantics)
            app.validate_target(principal, proposal.semantics.target, cur.connection)
            confirmation = app.repository.confirmation(
                cur,
                scope,
                proposal,
                actor=issuer.principal_id,
                key="policy-source-confirm:" + request.idempotency_key,
                expected_plan_version=request.plan_version,
                authority_basis="POLICY:"
                + proof.decision_id
                + ":"
                + proof.policy_digest,
                approval_kind="RESOURCE_POLICY_APPROVAL",
            )
            return {
                **value,
                "policyConfirmation": confirmation,
                "confirmationRequired": False,
                "executionStarted": False,
            }

    def select_employee(self, call, *, automatic_coverage=None):
        from .resource_preparation_plan import select_employee

        return select_employee(self, call, automatic_coverage=automatic_coverage)

    def __call__(self, call):
        app = self.bound_app(call)
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        scope = app.scope(principal)
        identity = call.path["proposal_id"]
        args = (
            call.query if call.operation == "READ_RESOURCE_AUTOMATION" else call.payload
        )
        version = args["version"]
        key = args.get("key", args.get("idempotencyKey"))
        issuer = self.authenticate(call.context)
        with app.repository.transaction(scope, identity, authorized=True) as cur:
            c = cur.connection
            confirmed = app.repository.read_plan(cur, scope, identity, version)
            plan = ConfirmedPlanRevision.model_validate(confirmed["plan"])
            require_supported_lineage(app, cur, scope, plan)
            work = self.work(
                call.context,
                plan.semantics.target.problem,
                self.grants.clock(),
                connection=cur.connection,
                history=call.operation == "READ_RESOURCE_AUTOMATION",
                plan=plan,
            )
            owned_resources.require_plan(work, plan)
            owned_resources.require_capability(self, call, work)
            digest = canonical_digest(
                owned_resources.digest_basis(
                    [identity, version, confirmed["digest"], self.policy.digest], work
                )
            )
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (
                    canonical_digest(
                        [
                            "d11",
                            scope.namespace,
                            scope.security_domain,
                            principal.principal_id,
                            key,
                        ]
                    ),
                ),
            )
            prior = c.execute(
                "SELECT payload_digest,record FROM "
                "execution_authority.resource_automation WHERE namespace=%s AND "
                "security_domain=%s AND subject_id=%s AND request_key=%s",
                (scope.namespace, scope.security_domain, principal.principal_id, key),
            ).fetchone()
            if prior:
                if owned_resources.evidence(work) and prior["record"].get(
                    "ownedBusiness"
                ) != owned_resources.evidence(work):
                    raise AuthorityError("OWNED_BUSINESS_PREPARATION_CHANGED")
                if prior["payload_digest"] != digest:
                    raise WorkbenchOwnerError("RESOURCE_PREPARATION_KEY_CONFLICT", 409)
                self.recheck(call, prior["record"])
                return prior["record"]
            if call.operation == "READ_RESOURCE_AUTOMATION":
                raise WorkbenchOwnerError("RESOURCE_PREPARATION_NOT_FOUND", 404)
            head = c.execute(
                "SELECT max(version) version FROM workflow_planning.plans WHERE "
                "namespace=%s AND security_domain=%s AND plan_id=%s",
                (scope.namespace, scope.security_domain, identity),
            ).fetchone()
            if head["version"] != version:
                raise WorkbenchOwnerError("RESOURCE_PREPARATION_PLAN_STALE", 409)
            target = plan.semantics.target
            base = [
                ExactGrant(
                    "BUSINESS_PROBLEM",
                    "READ",
                    "business-problem:" + target.problem.resource_id,
                ),
                ExactGrant(
                    "SUCCESS_CRITERIA_SET",
                    "READ",
                    "success-criteria-set:" + target.problem.resource_id,
                ),
            ]
            base.extend(
                ExactGrant(
                    "SUCCESS_CRITERION", "READ", "success-criterion:revision:" + r
                )
                for r in target.criterion_revision_ids
            )
            base_proof = self.decide(call, base, key + ":business", work, issuer)
            self.proof_grants(call, base)
            app.validate_target(principal, target, c)
            refs, employee = self.derive(call, plan, key, work, issuer)
            if len(refs) > self.policy.maxResources:
                raise WorkbenchOwnerError("RESOURCE_PREPARATION_BATCH_LIMIT", 422)
            try:
                runtime = self.runtime_probe(scope.namespace)
            except Exception as exc:
                # Never include credential/client exception text in product evidence.
                runtime = {
                    "check": "NATIVE_NAMESPACE_CREDENTIAL_READ",
                    "status": "FAILED",
                    "reason": "NATIVE_RUNTIME_OR_CREDENTIAL_UNAVAILABLE",
                }
                if isinstance(exc, KeyboardInterrupt):
                    raise
            source_ref = approved_source(plan.semantics)
            source_failure = None
            try:
                source_read = [
                    ExactGrant(
                        "KNOWLEDGE",
                        "READ_RESOURCE",
                        reference(
                            "knowledge", source_ref.resource_id, source_ref.revision_id
                        ),
                    )
                ]
                self.decide(call, source_read, key + ":test-source-read", work, issuer)
                self.proof_grants(call, source_read)
                source_row = c.execute(
                    "SELECT record FROM knowledge_operation.knowledge WHERE "
                    "namespace=%s AND security_domain=%s AND knowledge_id=%s",
                    (scope.namespace, scope.security_domain, source_ref.resource_id),
                ).fetchone()
                if not source_row:
                    raise AuthorityError("RESOURCE_SOURCE_EXACT_VERSION_REQUIRED")
                source_revision = next(
                    (
                        r
                        for r in source_row["record"]["revisions"]
                        if r["revisionId"] == source_ref.revision_id
                    ),
                    None,
                )
                if (
                    not source_revision
                    or source_revision["digest"] != source_ref.digest
                ):
                    raise AuthorityError("RESOURCE_SOURCE_EXACT_VERSION_REQUIRED")
                source_check = validate("knowledge", source_revision["content"], work)
                expected_source_schema = source_check["sourceSchema"]
            except AuthorityError as exc:
                source_failure = str(exc)
                source_revision = None
                expected_source_schema = None
            results = []
            for item in refs:
                kind, ref = item
                try:
                    with c.transaction():
                        if source_failure and kind in {"skill", "knowledge"}:
                            raise AuthorityError(source_failure)
                        if runtime["status"] != "PASSED":
                            raise AuthorityError(runtime["reason"])
                        proof = self.authenticate(call.context)
                        result = self.prepare_one(
                            call,
                            kind,
                            ref,
                            key,
                            work,
                            proof,
                            expected_source_schema,
                            source_ref,
                            source_revision,
                            employee_binding=employee[0]
                            if employee and employee[1]["published"]
                            else None,
                        )
                        results.append(result)
                except Exception as exc:
                    reason = getattr(exc, "reason_code", getattr(exc, "reason", None))
                    if reason is None and isinstance(exc, AuthorityError):
                        reason = str(exc)
                    results.append(
                        {
                            "kind": kind,
                            "reference": ref.model_dump(mode="json"),
                            "state": "BLOCKED",
                            "reason": reason or "RESOURCE_VALIDATION_FAILED",
                        }
                    )
            assembly = {"state": "BLOCKED", "reason": "RESOURCE_GAPS_REMAIN"}
            available = {
                op
                for r in results
                if r["state"] == "READY"
                for check in r["checks"]
                for op in check.get("operations", [])
            }
            required = {t.operation for t in plan.semantics.tasks}
            if required - available:
                assembly = {
                    "state": "BLOCKED",
                    "reason": "RESOURCE_TASK_OPERATION_GAPS",
                    "missingOperations": sorted(required - available),
                }
            if (
                results
                and all(r["state"] == "READY" for r in results)
                and not required - available
            ):
                try:
                    with c.transaction():
                        assembly = self.assemble(
                            call, plan, refs, employee, key, work, issuer
                        )
                except Exception as exc:
                    reason = getattr(
                        exc,
                        "reason_code",
                        str(exc)
                        if isinstance(exc, AuthorityError)
                        else "RESOURCE_ASSEMBLY_VALIDATION_FAILED",
                    )
                    assembly = {"state": "BLOCKED", "reason": reason}
            state = (
                "READY"
                if assembly["state"] == "ASSEMBLED"
                else "PARTIALLY_READY"
                if any(r["state"] == "READY" for r in results)
                else "BLOCKED"
            )
            from .plan_suggestion_resources import (
                EmployeePlanningReader,
                PlanningResourceResolver,
            )
            from .planning_candidates import ExactPlanningOwnerReader

            readers = {
                "EMPLOYEE": EmployeePlanningReader(
                    self.employees, call.authority, app.scope, c
                )
            }
            for kind in ("SKILL", "MCP", "KNOWLEDGE", "WORKFLOW"):
                readers[kind] = ExactPlanningOwnerReader(
                    c,
                    scope,
                    call.authority,
                    kind,
                    (
                        r.selected
                        for r in plan.semantics.requirements
                        if r.kind == "EMPLOYEE" and r.selected is not None
                    ),
                )
            proposal = app.repository.proposal(
                cur, scope, identity, plan.source_proposal_revision
            )
            snapshot = PlanningResourceResolver(readers).resolve(principal, proposal)
            app.repository.save_resources(cur, scope, proposal, snapshot)
            record = {
                "resourceSnapshot": snapshot.model_dump(mode="json"),
                "schemaVersion": "resource-preparation.v1",
                "requestKey": key,
                "planId": identity,
                "planVersion": version,
                "planDigest": confirmed["digest"],
                "state": state,
                "policy": {
                    "id": base_proof.policy_id,
                    "version": base_proof.policy_version,
                    "digest": base_proof.policy_digest,
                    "actor": issuer.principal_id,
                },
                "businessScopeDecision": base_proof.decision_id,
                "subject": principal.principal_id,
                "runtimeCheck": runtime,
                "resources": results,
                "assembly": assembly,
                "createdAt": datetime.now(UTC).isoformat(),
                "humanApprovalClicks": 0,
                "modelCalls": 0,
                "newRuns": 0,
                "executionStarted": False,
                "notifications": [
                    {
                        "kind": "IN_APP_POLICY_PREPARATION",
                        "status": "RECORDED_NONBLOCKING",
                        "recipient": principal.principal_id,
                    }
                ],
                "nextStep": "EXISTING_EXECUTION_ADMISSION"
                if state == "READY"
                else "RESOLVE_REPORTED_GAPS",
            }
            if owned_resources.evidence(work):
                record["ownedBusiness"] = owned_resources.evidence(work)
            c.execute(
                "INSERT INTO "
                "execution_authority.resource_automation(namespace,security_domai"
                "n,subject_id,request_key,plan_id,plan_version,payload_digest,rec"
                "ord) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    scope.namespace,
                    scope.security_domain,
                    principal.principal_id,
                    key,
                    identity,
                    version,
                    digest,
                    Jsonb(record),
                ),
            )
            return record

    def derive(self, call, plan, key, work, issuer, *, selection_predecessor=None):
        owned_resources.require_plan(
            work, plan, selection_predecessor=selection_predecessor
        )
        selections = {
            r.selected
            for r in plan.semantics.requirements
            if r.kind == "EMPLOYEE" and r.selected is not None
        }
        if len(selections) > 1:
            raise WorkbenchOwnerError("SINGLE_EXACT_EMPLOYEE_REQUIRED", 409)
        refs = {}
        employee = None
        for r in plan.semantics.requirements:
            if r.selected is None:
                if r.required:
                    raise WorkbenchOwnerError("RESOURCE_EXACT_COMMITMENT_REQUIRED", 409)
                continue
            if r.kind == "EMPLOYEE":
                from .digital_employee_definition_postgres import (
                    PostgresEmployeeDefinitionRepository,
                )

                g = ExactGrant(
                    "EMPLOYEE",
                    "READ",
                    f"employee:{r.selected.resource_id}:{r.selected.revision_id}",
                )
                scope = ScopeIdentity(
                    call.context.scope.tenant_id, call.context.scope.security_domain
                )
                value = PostgresEmployeeDefinitionRepository._read(
                    call.connection,
                    scope,
                    r.selected.resource_id,
                    r.selected.revision_id,
                )
                if value["published"]:
                    PostgresEmployeeDefinitionRepository.validate_members(
                        call.connection,
                        EmployeeRevision.from_record(value["revision"]),
                        published_binding=True,
                    )
                if value["digest"] != r.selected.digest:
                    raise WorkbenchOwnerError("RESOURCE_EMPLOYEE_DIGEST_MISMATCH", 409)
                if isinstance(work, owned_resources.OwnedResourceWork):
                    if not value["published"]:
                        raise AuthorityError(
                            "OWNED_BUSINESS_PUBLISHED_EMPLOYEE_REQUIRED"
                        )
                    for member in value["revision"]["members"]:
                        owned_resources.require_reference(
                            work,
                            {"RUNTIME_PROFILE": "runtime"}.get(
                                member["kind"], member["kind"].lower()
                            ),
                            ExactReference(
                                resource_id=member["resource_id"],
                                revision_id=member["revision_id"],
                                digest=member["digest"].removeprefix("sha256:"),
                            ),
                        )
                for member in value["revision"]["members"]:
                    if member["kind"] == "KNOWLEDGE":
                        data = call.connection.execute(
                            "SELECT record FROM knowledge_operation.knowledge "
                            "WHERE namespace=%s AND security_domain=%s AND "
                            "knowledge_id=%s",
                            (
                                scope.namespace,
                                scope.security_domain,
                                member["resource_id"],
                            ),
                        ).fetchone()
                        exact = (
                            next(
                                (
                                    x
                                    for x in data["record"]["revisions"]
                                    if x["revisionId"] == member["revision_id"]
                                ),
                                None,
                            )
                            if data
                            else None
                        )
                        if not exact or exact["digest"] != member["digest"]:
                            raise AuthorityError(
                                "RESOURCE_SOURCE_EXACT_VERSION_REQUIRED"
                            )
                        validate("knowledge", exact["content"], work)
                self.decide(call, [g], key + ":employee-read", work, issuer)
                self.proof_grants(call, [g])
                employee = (r.selected, value)
                for m in value["revision"]["members"]:
                    kind = {"RUNTIME_PROFILE": "runtime"}.get(
                        m["kind"], m["kind"].lower()
                    )
                    ref = ExactReference(
                        resource_id=m["resource_id"],
                        revision_id=m["revision_id"],
                        digest=m["digest"].removeprefix("sha256:"),
                    )
                    refs[(kind, ref.resource_id, ref.revision_id)] = (kind, ref)
            else:
                kind = {"RUNTIME": "runtime"}.get(r.kind, r.kind.lower())
                if kind not in TABLES:
                    raise WorkbenchOwnerError(
                        "RESOURCE_AUTOMATION_OWNER_UNSUPPORTED", 409
                    )
                refs[(kind, r.selected.resource_id, r.selected.revision_id)] = (
                    kind,
                    r.selected,
                )
        owned_resources.require_employee(work, employee, list(refs.values()))
        return sorted(
            refs.values(), key=lambda v: (v[0], v[1].resource_id, v[1].revision_id)
        ), employee

    def prepare_one(
        self,
        call,
        kind,
        ref,
        key,
        work,
        issuer,
        expected_source_schema=None,
        source_ref=None,
        source_revision=None,
        employee_binding=None,
    ):
        owned_resources.require_reference(work, kind, ref)
        c = call.connection
        table, col = TABLES[kind]
        row = c.execute(
            f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s AND {col}=%s"
            + (" AND kind=%s" if kind in {"skill", "mcp"} else ""),
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                ref.resource_id,
                *([kind] if kind in {"skill", "mcp"} else []),
            ),
        ).fetchone()
        if not row:
            raise AuthorityError("RESOURCE_EXACT_VERSION_UNAVAILABLE")
        record = row["record"]
        frozen = False
        if employee_binding is not None:
            from .planning_candidates import read_employee_member

            read_employee_member(
                c,
                ScopeIdentity(
                    call.context.scope.tenant_id, call.context.scope.security_domain
                ),
                employee_binding,
                "RUNTIME" if kind == "runtime" else kind.upper(),
                ref,
            )
            frozen = True
        rev = next(
            (r for r in record["revisions"] if r["revisionId"] == ref.revision_id), None
        )
        if (
            not rev
            or rev["digest"].removeprefix("sha256:") != ref.digest
            or record.get("archived")
            or record.get("enabled", True) is not True
            or (
                not frozen
                and ref.revision_id
                not in {
                    record.get("publishedRevisionId"),
                    record.get("currentDraftRevisionId"),
                }
            )
        ):
            raise AuthorityError("RESOURCE_EXACT_VERSION_UNAVAILABLE")
        if isinstance(work, owned_resources.OwnedResourceWork) and kind == "skill":
            operations = {
                operation["name"] for operation in rev["content"].get("operations", [])
            }
            if not operations or not operations.issubset(work.businessScope.operations):
                raise AuthorityError("OWNED_BUSINESS_TEST_OPERATION_NOT_AUTHORIZED")
        check = validate(
            kind,
            rev["content"],
            work,
            expected_source_schema=expected_source_schema,
            sales_v2_candidate=self.sales_v2_candidate,
        )
        existing = rev["state"] == "PUBLISHED" and (
            frozen or record.get("publishedRevisionId") == ref.revision_id
        )
        if isinstance(work, owned_resources.OwnedResourceWork) and not existing:
            raise AuthorityError("OWNED_BUSINESS_PUBLISHED_RESOURCE_REQUIRED")
        reads = [
            ExactGrant(
                OWNERS[kind],
                "READ_RESOURCE",
                reference(kind, ref.resource_id, ref.revision_id),
            )
        ]
        actions = (
            reads
            if existing
            else [
                *reads,
                ExactGrant(
                    OWNERS[kind],
                    "REVIEW_PUBLISH_RESOURCE",
                    reference(kind, ref.resource_id, ref.revision_id),
                ),
            ]
        )
        proof = self.decide(
            call, actions, key + ":" + kind + ":" + ref.resource_id, work, issuer
        )
        self.proof_grants(call, actions)
        actual_check = None
        if kind == "skill":
            from .automatic_document_inputs import resolve as document_inputs
            from .automatic_skill_testing import verify_skill

            if source_ref is None or source_revision is None:
                raise AuthorityError("RESOURCE_EXACT_TEST_SOURCE_REQUIRED")
            actual_check = verify_skill(
                call,
                self.services[kind],
                ref,
                source_ref,
                source_revision,
                proof,
                document_inputs=lambda: document_inputs(
                    self, call, work, issuer, key, source_ref, source_revision
                ),
                persist=not existing,
                sales_v2_candidate=self.sales_v2_candidate,
            )
            if not actual_check["passed"]:
                # A normal blocked return preserves genuine failed owner test facts.
                return {
                    "kind": kind,
                    "reference": ref.model_dump(mode="json"),
                    "name": record["name"],
                    "state": "BLOCKED",
                    "reason": "RESOURCE_ACTUAL_TEST_FAILED",
                    "checks": [check, actual_check],
                    "executionReady": False,
                    "publication": None,
                }
            record = c.execute(
                f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s AND {col}=%s AND kind=%s",
                (
                    call.context.scope.tenant_id,
                    call.context.scope.security_domain,
                    ref.resource_id,
                    kind,
                ),
            ).fetchone()["record"]
        publication = None
        if not existing:
            publication = self.resources.publish_policy(
                replace(
                    call,
                    operation="POLICY_REVIEW_PREPARED_RESOURCE",
                    path={
                        "kind": kind,
                        "identity": ref.resource_id,
                        "revision": ref.revision_id,
                    },
                    payload={
                        "expectedVersion": record["aggregateVersion"],
                        "digest": rev["digest"],
                        "reason": "D11 authorized read-only work scope; automatic technical validation and policy publication",
                        "idempotencyKey": "d11-publish:"
                        + canonical_digest([key, kind, ref.model_dump(mode="json")]),
                    },
                ),
                proof,
            )
        return {
            "kind": kind,
            "reference": ref.model_dump(mode="json"),
            "name": record["name"],
            "state": "READY",
            "case": "EXISTING"
            if existing
            else "EXPANDED"
            if rev.get("predecessorRevisionId")
            else "NEW",
            "checks": [check, *([actual_check] if actual_check else [])],
            "decisionId": proof.decision_id,
            "publication": publication,
            "executionReady": False,
        }

    def assemble(self, call, plan, refs, employee, key, work, issuer):
        owned_resources.require_employee(work, employee, refs)
        c = call.connection
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        members = tuple(
            CompositionMember(
                MemberKind("RUNTIME_PROFILE" if kind == "runtime" else kind.upper()),
                ref.resource_id,
                ref.revision_id,
                "sha256:" + ref.digest if kind == "runtime" else ref.digest,
            )
            for kind, ref in refs
        )
        member_reads = [
            ExactGrant("AGENT", "READ", f"agent:{m.resource_id}:{m.revision_id}")
            for m in members
            if m.kind == MemberKind.AGENT
        ]
        self.decide(call, member_reads, key + ":canonical-member-read", work, issuer)
        self.proof_grants(call, member_reads)
        if employee and {
            (m.kind, m.resource_id, m.revision_id, m.digest.removeprefix("sha256:"))
            for m in members
        } == {
            (m.kind, m.resource_id, m.revision_id, m.digest.removeprefix("sha256:"))
            for m in EmployeeRevision.from_record(employee[1]["revision"]).members
        }:
            from .digital_employee_definition_postgres import (
                PostgresEmployeeDefinitionRepository,
            )

            revision = EmployeeRevision.from_record(employee[1]["revision"])
            PostgresEmployeeDefinitionRepository.validate_members(
                c, revision, published_binding=employee[1]["published"]
            )
            if employee[1]["published"]:
                return {
                    "state": "ASSEMBLED",
                    "definition": employee[0].model_dump(mode="json"),
                    "reused": True,
                    "instancesCreated": 0,
                    "executionAdmitted": False,
                }
            aggregate = f"employee:{revision.definition_id}:aggregate"
            actions = [
                ExactGrant("EMPLOYEE", a, aggregate)
                for a in ("VALIDATE", "APPROVE", "PUBLISH")
            ]
            proof = self.decide(
                call, actions, key + ":selected-employee-publish", work, issuer
            )
            self.proof_grants(call, actions)
            current = employee[1]
            for state, action in (
                ("DRAFT", "VALIDATE"),
                ("VALIDATED", "APPROVE"),
                ("APPROVED", "PUBLISH"),
            ):
                if current["lifecycleState"] == state:
                    current = self.employees.decide_for_workbench(
                        c,
                        scope,
                        revision.definition_id,
                        revision.revision_id,
                        revision.digest,
                        action,
                        expected_version=current["aggregateVersion"],
                        decision_id=proof.decision_id,
                        command_id="policy-"
                        + action.lower()
                        + ":"
                        + canonical_digest([key, revision.digest]),
                        authorized=True,
                    )
            if not current["published"]:
                raise AuthorityError("RESOURCE_EMPLOYEE_PUBLICATION_INCOMPLETE")
            return {
                "state": "ASSEMBLED",
                "definition": employee[0].model_dump(mode="json"),
                "reused": False,
                "decisionId": proof.decision_id,
                "instancesCreated": 0,
                "executionAdmitted": False,
            }
        if employee:
            # A new definition must first be selected in an explicit successor
            # Plan. Do not report readiness for a different role than the one
            # committed by the current Plan.
            raise AuthorityError("RESOURCE_EMPLOYEE_SUCCESSOR_SELECTION_REQUIRED")
        if not {
            MemberKind.AGENT,
            MemberKind.RUNTIME_PROFILE,
            MemberKind.SKILL,
        }.issubset({m.kind for m in members}):
            raise AuthorityError("RESOURCE_ASSEMBLY_MEMBERS_REQUIRED")
        fingerprint = canonical_digest(
            [
                self.policy.digest,
                plan.plan_id,
                plan.version,
                [
                    m.record()
                    if hasattr(m, "record")
                    else {
                        "kind": m.kind,
                        "resource_id": m.resource_id,
                        "revision_id": m.revision_id,
                        "digest": m.digest,
                    }
                    for m in members
                ],
            ]
        )
        definition_id = "employee-definition:policy:" + fingerprint[:40]
        revision_id = "employee-revision:policy:" + fingerprint[:40]
        revision = EmployeeRevision(
            scope,
            definition_id,
            revision_id,
            plan.semantics.title,
            tuple(t.responsibility for t in plan.semantics.tasks),
            members,
            None,
        )
        member_reads = [
            ExactGrant("AGENT", "READ", f"agent:{m.resource_id}:{m.revision_id}")
            for m in members
            if m.kind == MemberKind.AGENT
        ]
        self.decide(call, member_reads, key + ":canonical-member-read", work, issuer)
        self.proof_grants(call, member_reads)
        create = [ExactGrant("EMPLOYEE", "CREATE", "employee:collection")]
        proof = self.decide(call, create, key + ":assemble-create", work, issuer)
        self.proof_grants(call, create)
        current = self.employees.create_for_workbench(
            c,
            revision,
            expected_version=0,
            decision_id=proof.decision_id,
            command_id="policy-create:" + fingerprint,
            authorized=True,
        )
        resource = f"employee:{definition_id}:aggregate"
        actions = [
            ExactGrant("EMPLOYEE", a, resource)
            for a in ("VALIDATE", "APPROVE", "PUBLISH")
        ]
        actions.append(
            ExactGrant("EMPLOYEE", "READ", f"employee:{definition_id}:{revision_id}")
        )
        proof = self.decide(call, actions, key + ":assemble-publish", work, issuer)
        self.proof_grants(call, actions)
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            current = self.employees.decide_for_workbench(
                c,
                scope,
                definition_id,
                revision_id,
                revision.digest,
                action,
                expected_version=current["aggregateVersion"],
                decision_id=proof.decision_id,
                command_id="policy-" + action.lower() + ":" + fingerprint,
                authorized=True,
            )
        return {
            "state": "ASSEMBLED",
            "definition": {
                "resource_id": definition_id,
                "revision_id": revision_id,
                "digest": revision.digest,
            },
            "reused": False,
            "decisionId": proof.decision_id,
            "instancesCreated": 0,
            "executionAdmitted": False,
        }

    def recheck(self, call, record):
        self.authenticate(call.context)
        if record.get("employeeReference"):
            ref = record["employeeReference"]
            self.proof_grants(
                call,
                [
                    ExactGrant(
                        "EMPLOYEE",
                        "READ",
                        f"employee:{ref['resource_id']}:{ref['revision_id']}",
                    )
                ],
            )
        for r in record["resources"]:
            if r["state"] == "READY":
                ref = r["reference"]
                self.proof_grants(
                    call,
                    [
                        ExactGrant(
                            OWNERS[r["kind"]],
                            "READ_RESOURCE",
                            reference(
                                r["kind"], ref["resource_id"], ref["revision_id"]
                            ),
                        )
                    ],
                )
        from .planning_candidates import read_published

        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        assembled = record.get("assembly", {}).get("definition")
        for item in record["resources"]:
            if item["state"] == "READY":
                try:
                    from .planning_candidates import read_employee_member

                    reader = read_published
                    args = ()
                    if assembled is not None:
                        reader = read_employee_member
                        args = (ExactReference.model_validate(assembled),)
                    reader(
                        call.connection,
                        scope,
                        *args,
                        item["kind"].upper()
                        if item["kind"] != "runtime"
                        else "RUNTIME",
                        ExactReference.model_validate(item["reference"]),
                    )
                except Exception as exc:
                    raise WorkbenchOwnerError(
                        "RESOURCE_PREPARATION_REVALIDATION_REQUIRED", 409
                    ) from exc


def vars_grant(grant):
    return [grant.owner, grant.action, grant.exact_resource]


def operations(automation):
    path = PREFIX + "/planning-v2/{proposal_id}/resource-preparation"
    from .capability_planning_input import (
        CapabilityPlanningInput,
        CapabilityPlanningRequest,
    )
    from .conversation_sources import ConversationSources
    from .planning_source_change import SourceChangeRequest
    from .policy_plan_confirmation import (
        ConfirmPolicyPlan,
        PolicyPlanConfirmation,
        entry_grants,
    )
    from .problem_resource_coverage import (
        CoverageQuery,
        CoverageRecovery,
        CoverageRequest,
        ProblemResourceCoverage,
    )
    from .question_activity_input import (
        QuestionActivityInput,
        QuestionActivityRequest,
    )
    from .question_activity_input import (
        entry_grants as question_entry_grants,
    )
    from .resource_preparation_plan import read_selection

    coverage = ProblemResourceCoverage(automation)
    return (
        WorkbenchOperation(
            "PREPARE_CAPABILITY_PLANNING_INPUT",
            "POST",
            PREFIX + "/capability-planning-input",
            CapabilityPlanningRequest,
            None,
            lambda *args: (
                ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
            ),
            CapabilityPlanningInput(automation),
        ),
        WorkbenchOperation(
            "READ_CONVERSATION_SOURCES",
            "GET",
            PREFIX + "/conversation-sources",
            None,
            None,
            lambda *args: (
                ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
            ),
            ConversationSources(automation),
        ),
        WorkbenchOperation(
            "CONFIRM_POLICY_PLAN",
            "POST",
            PREFIX + "/planning-v2/{proposal_id}/confirmation/automatic",
            ConfirmPolicyPlan,
            None,
            entry_grants,
            PolicyPlanConfirmation(automation),
        ),
        WorkbenchOperation(
            "PREPARE_QUESTION_ACTIVITY_INPUT",
            "POST",
            PREFIX + "/question-activity-input",
            QuestionActivityRequest,
            None,
            question_entry_grants,
            QuestionActivityInput(automation),
        ),
        WorkbenchOperation(
            "READ_PROBLEM_RESOURCE_COVERAGE",
            "GET",
            PREFIX + "/planning-v2/{proposal_id}/resource-coverage",
            None,
            CoverageQuery,
            target_grants("READ"),
            coverage,
        ),
        WorkbenchOperation(
            "SELECT_PROBLEM_RESOURCES",
            "POST",
            PREFIX + "/planning-v2/{proposal_id}/resource-selection/automatic",
            CoverageRequest,
            None,
            target_grants("APPROVE"),
            coverage,
        ),
        WorkbenchOperation(
            "READ_PROBLEM_RESOURCE_SELECTION",
            "GET",
            PREFIX + "/planning-v2/{proposal_id}/resource-selection/automatic",
            None,
            CoverageRecovery,
            target_grants("READ"),
            coverage,
        ),
        WorkbenchOperation(
            "READ_POLICY_EMPLOYEE_SELECTION",
            "GET",
            PREFIX + "/planning-v2/{proposal_id}/resource-selection",
            None,
            ReadEmployeeSelection,
            target_grants("READ"),
            lambda call: read_selection(automation, call),
        ),
        WorkbenchOperation(
            "SELECT_POLICY_EMPLOYEE_RESOURCES",
            "POST",
            PREFIX + "/planning-v2/{proposal_id}/resource-selection",
            SelectEmployeeResources,
            None,
            target_grants("APPROVE"),
            automation.select_employee,
        ),
        WorkbenchOperation(
            "AUTOMATE_SOURCE_CHANGE",
            "POST",
            PREFIX + "/planning-v2/{proposal_id}/source-changes/automatic",
            SourceChangeRequest,
            None,
            target_grants("APPROVE"),
            automation.source_change,
        ),
        WorkbenchOperation(
            "PREPARE_RESOURCE_AUTOMATION",
            "POST",
            path,
            PrepareResources,
            None,
            target_grants("APPROVE"),
            automation,
        ),
        WorkbenchOperation(
            "READ_RESOURCE_AUTOMATION",
            "GET",
            path,
            None,
            ReadPreparation,
            target_grants("READ"),
            automation,
        ),
    )
