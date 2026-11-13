"""Bounded current-publication READ selection, never draft head or execution USE."""

import re
from dataclasses import dataclass

from .authority_contracts import AuthorityError
from .ontology_postgres import PostgresOntologyRepository
from .resource_use_domain import canonical_digest
from .test_resource_read_policy import TestReadTarget


@dataclass(frozen=True)
class PublishedSelection:
    digest: str
    targets: tuple[TestReadTarget, ...]
    unavailable: tuple[dict, ...]


def resolve(policy, context, connection):
    """Caller owns transaction; shared aggregate locks exclude publication races."""
    scope = (context.scope.tenant_id, context.scope.security_domain)
    targets, manifest, unavailable = [], [], []
    owner = PostgresOntologyRepository(connection)
    for identity in sorted(policy.publishedOntologyIds):
        head = connection.execute(
            "SELECT ontology_id FROM business_ontology.definitions WHERE namespace=%s "
            "AND security_domain=%s AND ontology_id=%s FOR SHARE",
            (*scope, identity),
        ).fetchone()
        publication = (
            None
            if not head
            else connection.execute(
                "SELECT ordinal,revision_id,digest FROM "
                "business_ontology.lifecycle_facts "
                "WHERE namespace=%s AND security_domain=%s AND ontology_id=%s "
                "AND action='PUBLISH' ORDER BY ordinal DESC LIMIT 1",
                (*scope, identity),
            ).fetchone()
        )
        if not publication:
            manifest.append([identity, "NOT_PUBLISHED"])
            unavailable.append(
                {"resource": "business-ontology:" + identity, "state": "NOT_PUBLISHED"}
            )
            continue
        value = owner.read(scope, identity, publication["revision_id"])
        if value["digest"] != publication["digest"]:
            raise AuthorityError("TEST_READ_POLICY_SNAPSHOT_CHANGED")
        manifest.append(
            [
                identity,
                publication["ordinal"],
                value["revision_id"],
                value["digest"],
                value["state"],
            ]
        )
        target = TestReadTarget(
            owner="BUSINESS_ONTOLOGY",
            action="READ",
            resource=f"business-ontology:{identity}:{value['revision_id']}",
            digest=value["digest"],
            purpose="F3_ONTOLOGY_TEST_READ",
        )
        if value["state"] != "PUBLISH":
            unavailable.append({"resource": target.resource, "state": "NOT_PUBLISHED"})
            continue
        targets.append(target)
    return PublishedSelection(
        canonical_digest([policy.digest, *scope, context.principal_id, manifest]),
        tuple(targets),
        tuple(unavailable),
    )


def validate_selection_key(key, expected, selected):
    """Digest is encoded in the immutable key itself, not a replaceable body field."""
    match = re.fullmatch(r"published:([a-f0-9]{64}):([A-Za-z0-9_-]{1,64})", key)
    if not match or match[1] != expected:
        raise AuthorityError("TEST_READ_SELECTION_KEY_MISMATCH")
    if expected != selected.digest:
        raise AuthorityError("TEST_READ_SELECTION_CHANGED")


def lineage_block(connection, context, resource):
    """An explicit denial/revocation cannot be escaped by publishing another UUID."""
    scope = (context.scope.tenant_id, context.scope.security_domain)
    identity = connection.execute(
        "SELECT ontology_id FROM business_ontology.revisions WHERE namespace=%s "
        "AND security_domain=%s AND 'business-ontology:' || ontology_id "
        "|| ':' || revision_id=%s",
        (*scope, resource),
    ).fetchone()
    if not identity:
        raise AuthorityError("TEST_READ_POLICY_TARGET_UNAVAILABLE")
    params = (*scope, context.principal_id, identity["ontology_id"])
    if connection.execute(
        "SELECT 1 FROM authorization_admin.grants g JOIN "
        "authorization_admin.grant_revocation_facts f USING(grant_id) "
        "JOIN business_ontology.revisions o ON o.namespace=g.tenant_id AND "
        "o.security_domain=g.security_domain "
        "AND g.exact_resource='business-ontology:' || o.ontology_id || ':' || "
        "o.revision_id "
        "WHERE g.tenant_id=%s AND g.security_domain=%s AND "
        "g.subject_principal_id=%s AND o.ontology_id=%s "
        "AND g.owner='BUSINESS_ONTOLOGY' AND g.action='READ' LIMIT 1",
        params,
    ).fetchone():
        return "REVOKED"
    if connection.execute(
        "SELECT 1 FROM authorization_admin.grant_requests r JOIN "
        "authorization_admin.grant_request_members m USING(request_id) "
        "JOIN business_ontology.revisions o ON o.namespace=r.tenant_id AND "
        "o.security_domain=r.security_domain "
        "AND m.exact_resource='business-ontology:' || o.ontology_id || ':' || "
        "o.revision_id "
        "WHERE r.tenant_id=%s AND r.security_domain=%s AND "
        "r.subject_principal_id=%s AND o.ontology_id=%s "
        "AND r.state='REJECTED' AND m.owner='BUSINESS_ONTOLOGY' "
        "AND m.action='READ' LIMIT 1",
        params,
    ).fetchone():
        return "DENIED"
    return None
