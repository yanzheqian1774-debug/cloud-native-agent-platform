"""Bounded D324-7 synthetic provenance, distinct from real AI planning."""

from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from .cost_execution_revision import DELIVERY_SYNTHETIC_ONLY
from .plan_suggestion_domain import (
    Digest,
    ExactReference,
    FlexiblePlanSemantics,
    Immutable,
    PlanningError,
    ProposalRevision,
    SyntheticValidationOrigin,
)


class SyntheticValidationRequest(Immutable):
    idempotency_key: str = Field(min_length=1, max_length=200)
    semantics: FlexiblePlanSemantics
    source_snapshot: ExactReference
    mapping_digest: Digest


def make_proposal(principal, request):
    if (principal.tenant_id, principal.security_domain) != (
        "s5-324-native-capability",
        "isolated-native-validation",
    ):
        raise PlanningError("SYNTHETIC_PLAN_SCOPE_DENIED")
    if DELIVERY_SYNTHETIC_ONLY not in request.semantics.boundaries:
        raise PlanningError("SYNTHETIC_PLAN_BOUNDARY_REQUIRED")
    from .planning_contracts import validation_report

    validation_report(request.semantics)
    identity = str(
        uuid5(
            NAMESPACE_URL,
            "/".join(
                (
                    principal.tenant_id,
                    principal.security_domain,
                    principal.principal_id,
                    request.idempotency_key,
                )
            ),
        )
    )
    return ProposalRevision(
        proposal_id=identity,
        revision=1,
        predecessor_digest=None,
        invocation_id=None,
        semantics=request.semantics,
        origin=SyntheticValidationOrigin(
            namespace=principal.tenant_id,
            security_domain=principal.security_domain,
            root=request.semantics.target.problem,
            source_snapshot=request.source_snapshot,
            mapping_digest=request.mapping_digest,
            prepared_by=principal.principal_id,
        ),
    )
