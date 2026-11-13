"""Exact retained progress reads; execution still uses resource_read_grants."""

from .authority_contracts import ExactGrant
from .prepared_execution_resources import resource_read_grants


def projection_read_grants(preparation, participant):
    # Only the progress projection changes USE to exact version READ. The
    # execution/start/answer/runtime owners retain their separate USE checks.
    return tuple(
        ExactGrant(grant.owner, "READ", grant.exact_resource)
        if grant.owner == "BUSINESS_ONTOLOGY" and grant.action == "USE"
        else grant
        for grant in resource_read_grants(preparation, participant)
    )
