# ruff: noqa: E501, RUF001 -- Explicit immutable provenance and bound owner SQL.
"""Policy-only resource selection; business target/standards/task graph unchanged."""

from dataclasses import replace

from psycopg.types.json import Jsonb

from . import owned_business_resource_adapter as owned_resources
from .authority_contracts import AuthorityError, ExactGrant
from .capability_execution_constraints import verify_plan, verify_resources
from .capability_plan_confirmation import validate_source
from .cost_execution_revision import (
    DELIVERY_SYNTHETIC_ONLY,
    DOCUMENT_SYNTHETIC_ONLY,
    EXECUTION_ONLY,
    PLANNING_ONLY,
    READ_ONLY_PLANNING,
    SALES_SYNTHETIC_ONLY,
    SYNTHETIC_ONLY,
    TABULAR_SYNTHETIC_ONLY,
)
from .plan_suggestion_domain import (
    ConfirmedPlanRevision,
    ExactReference,
    FlexiblePlanSemantics,
    PolicyResourcePreparationOrigin,
    ProposalRevision,
)
from .planning_contracts import validation_report
from .planning_source_change import SourceChangeRequest, approved_source
from .planning_source_reference import is_source_boundary
from .resource_automation import ReadEmployeeSelection, SelectEmployeeResources
from .resource_policy_lineage import require_supported_lineage
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import reference


def select_employee(automation, call, *, automatic_coverage=None):
    request = SelectEmployeeResources.model_validate(call.payload)
    app = automation.bound_app(call)
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    scope = app.scope(principal)
    identity = call.path["proposal_id"]
    issuer = automation.authenticate(call.context)
    with app.repository.transaction(scope, identity, authorized=True) as cur:
        c = cur.connection
        baseline = app.repository.read_plan(cur, scope, identity, request.version)
        old = ConfirmedPlanRevision.model_validate(baseline["plan"])
        require_supported_lineage(app, cur, scope, old)
        if baseline["digest"] != request.digest:
            raise WorkbenchOwnerError("RESOURCE_SELECTION_PLAN_DIGEST_MISMATCH", 409)
        work = automation.work(
            call.context,
            old.semantics.target.problem,
            automation.grants.clock(),
            connection=c,
        )
        owned_resources.require_reference(work, "employee", request.employee)
        target = old.semantics.target
        target_reads = [
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
            *[
                ExactGrant(
                    "SUCCESS_CRITERION",
                    "READ",
                    "success-criterion:revision:" + revision,
                )
                for revision in target.criterion_revision_ids
            ],
        ]
        automation.decide(
            call,
            target_reads,
            "selection-target:" + request.idempotencyKey,
            work,
            issuer,
        )
        automation.proof_grants(call, target_reads)
        current = app.current_input(
            principal, old.semantics.target.problem.resource_id, c
        )
        capability = validate_source(automation, call, request, old, current)
        owned_resources.require_capability(automation, call, work, capability)
        if capability:
            employees = [
                b["reference"]
                for b in capability["contract"]["bindings"]
                if b["kind"] == "EMPLOYEE"
            ]
            if employees != [request.employee.model_dump(mode="json")]:
                raise WorkbenchOwnerError("CAPABILITY_PREPARED_EMPLOYEE_MISMATCH", 409)
        payload = request.model_dump(mode="json")
        if request.capabilityConversationId is None:
            for field in (
                "capabilityConversationId",
                "capabilityMessageId",
                "capabilityContractDigest",
            ):
                payload.pop(field)
        payload_digest = canonical_digest(
            owned_resources.digest_basis([payload, automation.policy.digest], work)
        )
        replay = c.execute(
            "SELECT record,payload_digest FROM execution_authority.resource_policy_plan_commands WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND request_key=%s",
            (
                scope.namespace,
                scope.security_domain,
                principal.principal_id,
                request.idempotencyKey,
            ),
        ).fetchone()
        if replay:
            if replay["payload_digest"] != payload_digest:
                raise WorkbenchOwnerError("RESOURCE_SELECTION_KEY_CONFLICT", 409)
            automation.recheck(call, replay["record"]["preflight"])
            return replay["record"]
        head = c.execute(
            "SELECT max(revision) revision FROM workflow_planning.proposals WHERE namespace=%s AND security_domain=%s AND proposal_id=%s",
            (scope.namespace, scope.security_domain, identity),
        ).fetchone()["revision"]
        if (
            head != request.expectedProposalRevision
            or old.source_proposal_revision != head
        ):
            raise WorkbenchOwnerError("RESOURCE_SELECTION_PLAN_STALE", 409)
        probe = old.semantics.model_dump(mode="json")
        for r in probe["requirements"]:
            if r["kind"] == "EMPLOYEE":
                r["selected"] = request.employee.model_dump(mode="json")
        from .pending_member_requirements import read_and_resolve

        prospective_semantics = FlexiblePlanSemantics.model_validate(probe)
        referenced = {
            identity
            for task in prospective_semantics.tasks
            for identity in task.requirement_ids
        }
        if any(
            r.kind != "EMPLOYEE"
            and (r.required or r.requirement_id in referenced)
            and r.selected is None
            for r in prospective_semantics.requirements
        ):
            resolved, _ = read_and_resolve(
                call, prospective_semantics, request.employee
            )
            probe = resolved.model_dump(mode="json")
        prospective = old.model_copy(
            update={"semantics": FlexiblePlanSemantics.model_validate(probe)}
        )
        refs, employee = automation.derive(
            call, prospective, "selection:" + request.idempotencyKey, work, issuer
        )
        if not employee:
            raise AuthorityError("RESOURCE_EMPLOYEE_COMMITMENT_REQUIRED")
        if capability:
            verify_resources(
                capability,
                {
                    "assembly": {"definition": employee[0].model_dump(mode="json")},
                    "resources": [
                        {"kind": kind, "reference": ref.model_dump(mode="json")}
                        for kind, ref in refs
                    ],
                },
            )
        # One source remains explicit. Same-content alias change uses D10's
        # immutable source owner record and truthful POLICY_SOURCE_CHANGE first.
        selected_sources = [
            r
            for k, r in refs
            if k == "knowledge"
            and r
            in [
                ExactReference(
                    resource_id=m["resource_id"],
                    revision_id=m["revision_id"],
                    digest=m["digest"],
                )
                for m in employee[1]["revision"]["members"]
                if m["kind"] == "KNOWLEDGE"
            ]
        ]
        current_source = approved_source(old.semantics)
        source_change = None
        if len(selected_sources) == 1 and selected_sources[0] != current_source:
            change = SourceChangeRequest(
                plan_version=old.version,
                plan_digest=baseline["digest"],
                expected_proposal_revision=head,
                old_source=current_source,
                new_source=selected_sources[0],
                reason="Same-business resource assembly selects an authorized same-content source; retain all previous versions",
                idempotency_key="resource-source:" + request.idempotencyKey,
            )
            source_call = replace(call, payload=change.model_dump(mode="json"))
            source_change = automation.source_change(source_call)
            baseline = source_change["policyConfirmation"]
            old = ConfirmedPlanRevision.model_validate(baseline["plan"])
            head = old.source_proposal_revision
            probe["boundaries"] = [
                s for s in probe["boundaries"] if not is_source_boundary(s)
            ] + [s for s in old.semantics.boundaries if is_source_boundary(s)]
            for r in probe["requirements"]:
                if r["kind"] == "KNOWLEDGE" and r.get(
                    "selected"
                ) == current_source.model_dump(mode="json"):
                    r["selected"] = selected_sources[0].model_dump(mode="json")
        elif len(selected_sources) != 1:
            raise AuthorityError("RESOURCE_PRIMARY_SOURCE_COMMITMENT_REQUIRED")
        source_reads = [
            ExactGrant(
                "KNOWLEDGE",
                "READ_RESOURCE",
                reference("knowledge", r.resource_id, r.revision_id),
            )
            for r in selected_sources
        ]
        actions = [
            ExactGrant("PLAN", a, "plan:v2:" + identity)
            for a in ("READ", "PREPARE", "APPROVE")
        ]
        t = old.semantics.target
        actions += source_reads
        actions += [
            ExactGrant(
                "BUSINESS_PROBLEM", "READ", "business-problem:" + t.problem.resource_id
            ),
            ExactGrant(
                "SUCCESS_CRITERIA_SET",
                "READ",
                "success-criteria-set:" + t.problem.resource_id,
            ),
        ]
        actions += [
            ExactGrant("SUCCESS_CRITERION", "READ", "success-criterion:revision:" + r)
            for r in t.criterion_revision_ids
        ]
        proof = automation.decide(
            call, actions, "selection:" + request.idempotencyKey, work, issuer
        )
        automation.proof_grants(call, actions)
        app.validate_target(principal, t, c)
        semantics = probe
        semantics["business_rules"] = [
            PLANNING_ONLY if s == EXECUTION_ONLY else s
            for s in semantics["business_rules"]
        ]
        if PLANNING_ONLY not in semantics["business_rules"]:
            semantics["business_rules"].append(PLANNING_ONLY)
        semantics["boundaries"] = [
            s
            for s in semantics["boundaries"]
            if not s.startswith("执行准备映射SHA256：")
            and s
            not in {
                DELIVERY_SYNTHETIC_ONLY,
                SALES_SYNTHETIC_ONLY,
                SYNTHETIC_ONLY,
                TABULAR_SYNTHETIC_ONLY,
                DOCUMENT_SYNTHETIC_ONLY,
                READ_ONLY_PLANNING,
            }
        ] + [READ_ONLY_PLANNING]
        for r in semantics["requirements"]:
            if r["kind"] == "EMPLOYEE":
                r["selected"] = request.employee.model_dump(mode="json")
        successor = ProposalRevision(
            proposal_id=identity,
            revision=head + 1,
            predecessor_digest=app.repository.proposal(
                cur, scope, identity, head
            ).digest,
            invocation_id=None,
            semantics=FlexiblePlanSemantics.model_validate(semantics),
            origin=PolicyResourcePreparationOrigin(
                namespace=scope.namespace,
                security_domain=scope.security_domain,
                root=t.problem,
                source_snapshot=approved_source(old.semantics),
                predecessor_plan=ExactReference(
                    resource_id=old.plan_id,
                    revision_id=str(old.version),
                    digest=baseline["digest"],
                ),
                prepared_by=issuer.principal_id,
                policy_basis=proof.record(issuer.principal_id),
            ),
        )
        validation_report(successor.semantics)
        if capability:
            verify_plan(capability, successor, current)
        app.repository.add_proposal(cur, scope, successor)
        confirmed = app.repository.confirmation(
            cur,
            scope,
            successor,
            actor=issuer.principal_id,
            key="policy-selection-confirm:" + request.idempotencyKey,
            expected_plan_version=old.version,
            authority_basis="POLICY:" + proof.decision_id + ":" + proof.policy_digest,
            approval_kind="RESOURCE_POLICY_APPROVAL",
        )
        # Exact source scope is rechecked before replay; no readable data content
        # or sensitive non-approved metadata is copied into this command receipt.
        preflight = {
            "resources": [
                {
                    "kind": "knowledge",
                    "state": "READY",
                    "reference": r.model_dump(mode="json"),
                }
                for r in selected_sources
            ],
            "employeeReference": request.employee.model_dump(mode="json"),
        }
        result = {
            "proposal": successor.model_dump(mode="json"),
            "digest": successor.digest,
            "confirmation": confirmed,
            "sourceChangeRequestId": source_change["requestId"]
            if source_change
            else None,
            "policyBasis": proof.record(issuer.principal_id),
            "preflight": preflight,
            "modelCalls": 0,
            "newRuns": 0,
            "executionStarted": False,
        }
        if owned_resources.evidence(work):
            result["ownedBusiness"] = owned_resources.evidence(work)
        if capability:
            result["capabilitySource"] = {
                "conversationId": request.capabilityConversationId,
                "sourceMessageId": request.capabilityMessageId,
                "contractDigest": request.capabilityContractDigest,
            }
        if automatic_coverage is not None:
            result["automaticCoverage"] = automatic_coverage
        c.execute(
            "INSERT INTO execution_authority.resource_policy_plan_commands VALUES(%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                principal.principal_id,
                request.idempotencyKey,
                payload_digest,
                Jsonb(result),
            ),
        )
        return result


def read_selection(automation, call):
    """Read a committed fixed selection without reselecting or writing."""
    request = ReadEmployeeSelection.model_validate(call.query)
    app = automation.bound_app(call)
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    scope = app.scope(principal)
    identity = call.path["proposal_id"]
    automation.authenticate(call.context)
    with app.repository.transaction(scope, identity, authorized=True) as cur:
        baseline = app.repository.read_plan(cur, scope, identity, request.version)
        plan = ConfirmedPlanRevision.model_validate(baseline["plan"])
        if baseline["digest"] != plan.digest:
            raise WorkbenchOwnerError("RESOURCE_SELECTION_PLAN_DIGEST_MISMATCH", 409)
        require_supported_lineage(app, cur, scope, plan)
        work = automation.work(
            call.context,
            plan.semantics.target.problem,
            automation.grants.clock(),
            connection=cur.connection,
            history=True,
        )
        owned_resources.require_plan(work, plan)
        owned_resources.require_capability(automation, call, work)
        current = app.current_input(
            principal, plan.semantics.target.problem.resource_id, cur.connection
        )
        capability = validate_source(automation, call, request, plan, current)
        row = cur.connection.execute(
            "SELECT record FROM execution_authority.resource_policy_plan_commands "
            "WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND request_key=%s",
            (
                scope.namespace,
                scope.security_domain,
                principal.principal_id,
                request.key,
            ),
        ).fetchone()
        if row is None:
            raise WorkbenchOwnerError("RESOURCE_SELECTION_NOT_FOUND", 404)
        result = row["record"]
        if owned_resources.evidence(work) and result.get(
            "ownedBusiness"
        ) != owned_resources.evidence(work):
            raise AuthorityError("OWNED_BUSINESS_PREPARATION_CHANGED")
        successor = ProposalRevision.model_validate(result["proposal"])
        expected = ExactReference(
            resource_id=identity, revision_id=str(request.version), digest=plan.digest
        )
        if (
            not isinstance(successor.origin, PolicyResourcePreparationOrigin)
            or successor.origin.predecessor_plan != expected
        ):
            raise WorkbenchOwnerError("RESOURCE_SELECTION_KEY_CONFLICT", 409)
        if result["policyBasis"]["policy_digest"] != automation.policy.digest:
            raise WorkbenchOwnerError("RESOURCE_SELECTION_POLICY_CHANGED", 409)
        if capability:
            source = {
                "conversationId": request.capabilityConversationId,
                "sourceMessageId": request.capabilityMessageId,
                "contractDigest": request.capabilityContractDigest,
            }
            if result.get("capabilitySource") != source:
                raise WorkbenchOwnerError("CAPABILITY_SELECTION_SOURCE_MISMATCH", 409)
            verify_plan(capability, successor, current)
            employees = [
                b["reference"]
                for b in capability["contract"]["bindings"]
                if b["kind"] == "EMPLOYEE"
            ]
            if employees != [result["preflight"].get("employeeReference")]:
                raise WorkbenchOwnerError("CAPABILITY_PREPARED_EMPLOYEE_MISMATCH", 409)
        elif result.get("capabilitySource"):
            raise WorkbenchOwnerError("CAPABILITY_CONFIRMATION_SOURCE_REQUIRED", 409)
        automation.recheck(call, result["preflight"])
        return result
