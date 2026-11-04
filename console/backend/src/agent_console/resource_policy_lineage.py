"""Check exact planning provenance before generic resource policy mutations."""

from .plan_suggestion_domain import OntologyPlanOrigin
from .workbench_owner_authorization import WorkbenchOwnerError


def require_supported_lineage(app, cur, scope, plan):
    proposal = app.repository.proposal(
        cur, scope, plan.source_proposal_id, plan.source_proposal_revision
    )
    if proposal.digest != plan.source_proposal_digest:
        raise WorkbenchOwnerError("RESOURCE_POLICY_PROPOSAL_DIGEST_MISMATCH", 409)
    if isinstance(proposal.origin, OntologyPlanOrigin):
        # Source content equality does not preserve an ontology's exact source,
        # action references, query binding or criterion bindingDigest. Until the
        # policy adapter carries all of them, retain the normal ontology owner
        # path instead of producing a generic successor or partial publication.
        raise WorkbenchOwnerError("RESOURCE_POLICY_ONTOLOGY_BINDING_REQUIRED", 409)
