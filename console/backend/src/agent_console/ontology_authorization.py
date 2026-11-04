"""Exact ontology targets for the existing grant administration owner."""


class OntologyTargets:
    def __init__(self, creation_targets=()):
        self.creation_targets = frozenset(creation_targets)

    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None or grant.owner != "BUSINESS_ONTOLOGY":
            return False
        if grant.exact_resource == "business-ontology:collection":
            return grant.action == "LIST"
        if grant.exact_resource in self.creation_targets:
            return True
        if grant.action in {"CREATE", "REVISE"}:
            return False
        return (
            connection.execute(
                "SELECT 1 FROM business_ontology.revisions WHERE namespace=%s"
                " AND security_domain=%s "
                "AND 'business-ontology:' || ontology_id || ':' || revision_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    grant.exact_resource,
                ),
            ).fetchone()
            is not None
        )


class OntologyPlanTargets:
    """Operator-declared future plan identities, still requiring exact grants."""

    def __init__(self, targets=()):
        self.targets = frozenset(targets)

    def is_known_exact_target(self, context, grant, *, connection=None):
        return (
            connection is not None
            and grant.owner == "PLAN"
            and grant.action in {"PREPARE", "READ", "APPROVE"}
            and grant.exact_resource in self.targets
        )
