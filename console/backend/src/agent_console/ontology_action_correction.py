# ruff: noqa: E501 -- Exact scoped owner SQL.
"""Explicit original-owner compatibility correction; never dispatch or replace work."""

import os
from dataclasses import replace
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from . import ontology_action_correction_postgres as store
from .authority_contracts import ExactGrant
from .execution_domain import ScopeIdentity
from .ontology_action_correction_policy import (
    CorrectionPolicy,
    require,
    verify_compatibility,
)
from .ontology_service import resource as ontology_resource
from .plan_suggestion_domain import ConfirmedPlanRevision
from .plan_suggestion_postgres import PostgresPlanningRepository
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal

ENV = "OWNED_BUSINESS_ONTOLOGY_CORRECTION_POLICY"


class CorrectBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=1, max_length=160)
    policyDigest: str = Field(pattern=r"^[a-f0-9]{64}$")


def current_policy(path, context, binding):
    p = CorrectionPolicy.load(path)
    require(
        (context.scope.tenant_id, context.scope.security_domain, context.principal_id)
        == (p.tenantId, p.securityDomain, p.subjectId),
        "SCOPE_DENIED",
    )
    require(
        not binding.history_only
        and (
            binding.admission_id,
            binding.record_digest,
            binding.policy_digest,
            binding.problem,
        )
        == (p.admissionId, p.admissionRecordDigest, p.originalPolicyDigest, p.problem),
        "ORIGINAL_WORK_CHANGED",
    )
    require(datetime.now(UTC) < min(p.expiresAt, binding.expires_at), "EXPIRED")
    return p


def resource_reads(reader, c, context, p):
    reader._reads(
        c,
        context,
        tuple(
            ExactGrant(
                "BUSINESS_ONTOLOGY",
                action,
                ontology_resource(ref.resource_id, ref.revision_id),
            )
            for ref in (p.oldBinding.ontology, p.newBinding.ontology)
            for action in ("READ", "USE")
        ),
        datetime.now(UTC),
    )


def project(reader, c, context, binding):
    environment = getattr(reader, "environment", None)
    environment = os.environ if environment is None else environment
    path = environment.get(ENV)
    if not path or binding.history_only:
        return binding
    p = CorrectionPolicy.load(path)
    if binding.admission_id != p.admissionId:
        return binding
    p = current_policy(path, context, binding)
    receipt = store.read(c, binding.admission_id)
    if receipt is None:
        return binding
    r = receipt["record"]
    require(
        r["policyDigest"] == p.digest and r["policy"] == p.model_dump(mode="json"),
        "CORRECTION_CHANGED",
    )
    resource_reads(reader, c, context, p)
    verify_compatibility(c, ScopeIdentity(p.tenantId, p.securityDomain), p, binding)
    return replace(
        binding,
        scope=binding.scope.model_copy(update={"documentRules": p.newBinding}),
        ontology_correction={
            "receiptDigest": receipt["record_digest"],
            "policyDigest": p.digest,
            "originalPlan": p.plan.model_dump(mode="json"),
            "bindingDigest": p.newBinding.digest,
        },
    )


class OntologyActionCorrection:
    def __init__(self, owner, path):
        self.owner, self.path = owner, path

    def __call__(self, call):
        p = CorrectionPolicy.load(self.path)
        require(p.plan.resource_id == call.path["plan_id"], "PLAN_CHANGED")
        data = CorrectBinding.model_validate(call.payload)
        require(data.policyDigest == p.digest, "POLICY_CHANGED")
        c, context = call.connection, call.context
        principal = OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )
        scope = ScopeIdentity(context.scope.tenant_id, context.scope.security_domain)
        # Original planning owner lock, same connection as the BFF mutation transaction.
        repo = PostgresPlanningRepository(None, connection=c)
        with repo.transaction(scope, p.plan.resource_id, authorized=True) as cur:
            value = repo.read_plan(
                cur, scope, p.plan.resource_id, int(p.plan.revision_id)
            )
            plan = ConfirmedPlanRevision.model_validate(value["plan"])
            require(
                value["digest"] == plan.digest == p.plan.digest
                and plan.semantics.target.problem == p.problem,
                "PLAN_CHANGED",
            )
            binding = self.owner.work_reader.work(
                c, context, p.problem, _apply_correction=False
            )
            p = current_policy(self.path, context, binding)
            for grant in grants(context, call.path, call.payload, {}):
                call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
            call.authority.require(
                principal,
                "BUSINESS_PROBLEM",
                "READ",
                "business-problem:" + p.problem.resource_id,
            )
            resource_reads(self.owner.work_reader, c, context, p)
            verify_compatibility(c, scope, p, binding)
            record = dict(
                schemaVersion="ontology-action-correction.v1",
                policyDigest=p.digest,
                policy=p.model_dump(mode="json"),
                requestKey=data.idempotencyKey,
                originalApproval=value["approval"],
                businessRulesUnchanged=True,
                executionStarted=False,
                modelCalls=0,
            )
            prior = store.read(c, p.admissionId)
            if prior:
                require(prior["record"] == record, "CONFLICT")
                return {"receipt": prior["record"], "digest": prior["record_digest"]}
            head = c.execute(
                "SELECT max(version) version FROM workflow_planning.plans WHERE namespace=%s AND security_domain=%s AND plan_id=%s",
                (scope.namespace, scope.security_domain, plan.plan_id),
            ).fetchone()
            require(head["version"] == plan.version, "PLAN_ADVANCED")
            require(value["approval"].get("decision") == "APPROVE", "PLAN_NOT_APPROVED")
            rows = c.execute(
                "SELECT record FROM execution_authority.resource_automation WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND plan_id=%s AND plan_version=%s AND record->>'state'='READY'",
                (
                    scope.namespace,
                    scope.security_domain,
                    context.principal_id,
                    plan.plan_id,
                    plan.version,
                ),
            ).fetchall()
            require(bool(rows), "RESOURCE_PREPARATION_REQUIRED")
            # Every saved READY must bind the same composition; no arbitrary latest choice.
            require(
                len({canonical_digest(r["record"]["resources"]) for r in rows}) == 1,
                "RESOURCE_PREPARATION_AMBIGUOUS",
            )
            from .owned_business_resource_adapter import (
                derive_work,
                require_plan,
                require_ready,
            )

            original_work = derive_work(self.owner, c, context, p.problem)
            require_plan(original_work, plan)
            for row in rows:
                require_ready(original_work, row["record"])
                require(
                    row["record"]["planDigest"] == plan.digest, "RESOURCE_PLAN_CHANGED"
                )
                store.require_no_effect(c, scope, plan, row["record"])
            require(CorrectionPolicy.load(self.path) == p, "POLICY_CHANGED")
            require(datetime.now(UTC) < min(p.expiresAt, binding.expires_at), "EXPIRED")
            result = store.append(c, p, data.idempotencyKey, record)
            return {"receipt": result["record"], "digest": result["record_digest"]}


def grants(context, path, payload, query):
    return tuple(
        ExactGrant("PLAN", a, "plan:v2:" + path["plan_id"])
        for a in ("READ", "PREPARE", "APPROVE")
    )


def operations(owner, path):
    return (
        WorkbenchOperation(
            "CORRECT_ORIGINAL_ONTOLOGY_ACTION_BINDING",
            "POST",
            PREFIX + "/planning-v2/{plan_id}/ontology-action-correction",
            CorrectBinding,
            None,
            grants,
            OntologyActionCorrection(owner, path),
            201,
        ),
    )
