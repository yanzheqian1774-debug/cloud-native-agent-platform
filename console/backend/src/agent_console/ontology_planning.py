# ruff: noqa: RUF001 -- Exact existing Chinese approval commitment syntax.
"""Explicit non-model draft preparation, followed by ordinary plan confirmation."""

from pydantic import Field

from .cost_execution_revision import EXECUTION_ONLY, SALES_SYNTHETIC_ONLY
from .execution_preparation import ExecutionPreparationError
from .ontology_domain import OntologyError, Value
from .ontology_execution import (
    DocumentRuleExecutionPreparation,
    OntologyExecutionPreparation,
    published_content,
)
from .ontology_service import resource
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_domain import (
    OntologyPlanOrigin,
    PlanningConflict,
    PlanningError,
    ProposalRevision,
)
from .plan_suggestion_postgres import PostgresPlanningRepository
from .planning_contracts import validation_report
from .prepared_execution_application import PreparedExecutionApplication
from .prepared_execution_lineage import validate_participant
from .prepared_execution_resources import resource_read_grants, validate_resources
from .workbench_business_problem import OwnerPrincipal


class OntologyDraftCommand(Value):
    request_key: str = Field(min_length=1, max_length=128)
    draft: OntologyExecutionPreparation | DocumentRuleExecutionPreparation


def prepare(call, planning):
    command = OntologyDraftCommand.model_validate(call.payload)
    p = command.draft
    context = call.context
    principal = OwnerPrincipal(
        context.principal_id, context.scope.tenant_id, context.scope.security_domain
    )
    if (p.namespace, p.security_domain) != (
        principal.tenant_id,
        principal.security_domain,
    ) or p.business_semantics.ontology.resource_id != call.path["identity"]:
        raise OntologyError("ONTOLOGY_PLAN_SCOPE_MISMATCH")
    if p.plan_digest != "0" * 64 or p.approval_id != "PENDING":
        raise OntologyError("ONTOLOGY_UNAPPROVED_DRAFT_REQUIRED")
    call.authority.require(principal, "PLAN", "PREPARE", "plan:v2:" + p.plan_id)
    call.authority.require(principal, "PLAN", "READ", "plan:v2:" + p.plan_id)
    call.authority.require(
        principal,
        "BUSINESS_ONTOLOGY",
        "USE",
        resource(
            p.business_semantics.ontology.resource_id,
            p.business_semantics.ontology.revision_id,
        ),
    )
    app = PreparedExecutionApplication(call.connection, principal, call.authority)
    published_content(call.connection, app.scope, p.business_semantics)
    app.validate_root(p)
    for participant in p.participants:
        call.authority.require(
            principal,
            "EMPLOYEE",
            "READ",
            f"employee:{participant.definition.resource_id}:{participant.definition.revision_id}",
        )
        validate_participant(call.connection, app.scope, participant)
        for grant in resource_read_grants(p, participant):
            call.authority.require(
                principal, grant.owner, grant.action, grant.exact_resource
            )
        validate_resources(call.connection, app.scope, p, participant)
    if (
        EXECUTION_ONLY not in p.semantics.business_rules
        or SALES_SYNTHETIC_ONLY not in p.semantics.boundaries
    ):
        raise ExecutionPreparationError("ONTOLOGY_SYNTHETIC_BOUNDARY_REQUIRED")
    semantics = p.semantics.model_copy(
        update={
            "boundaries": (
                *(
                    b
                    for b in p.semantics.boundaries
                    if not b.startswith("执行准备映射SHA256：")
                ),
                f"执行准备映射SHA256：{p.mapping_digest}；本体版本与口径已固定，仍需独立执行准入。",
            )
        }
    )
    validation_report(semantics)
    repo = PostgresPlanningRepository(planning.repository.pool, call.connection)
    application = PlanningApplication(repo, planning.problems, call.authority)
    application.validate_target(principal, semantics.target, call.connection)
    proposal = ProposalRevision(
        proposal_id=p.plan_id,
        revision=1,
        predecessor_digest=None,
        invocation_id=None,
        semantics=semantics,
        origin=OntologyPlanOrigin(
            namespace=p.namespace,
            security_domain=p.security_domain,
            root=semantics.target.problem,
            source_snapshot=p.source_snapshot,
            ontology=p.business_semantics.ontology,
            mapping_digest=p.mapping_digest,
            prepared_by=principal.principal_id,
            request_key=command.request_key,
        ),
    )
    with repo.transaction(app.scope, p.plan_id, authorized=True) as cursor:
        try:
            existing = repo.proposal(cursor, app.scope, p.plan_id, 1)
        except PlanningError as exc:
            if str(exc) != "PLANNING_NOT_FOUND":
                raise
            repo.add_proposal(cursor, app.scope, proposal)
        else:
            if (
                not isinstance(existing.origin, OntologyPlanOrigin)
                or existing.origin.prepared_by != principal.principal_id
                or existing.origin.mapping_digest != p.mapping_digest
                or existing.semantics != semantics
            ):
                raise PlanningConflict("ONTOLOGY_DRAFT_REPLAY_CONFLICT")
            proposal = existing
    return {
        "proposal": proposal.model_dump(mode="json"),
        "digest": proposal.digest,
        "draft": p.model_copy(update={"semantics": semantics}).model_dump(mode="json"),
        "execution_status": "NOT_STARTED",
        "confirmation_required": True,
    }
