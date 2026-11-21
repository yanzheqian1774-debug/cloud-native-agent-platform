# ruff: noqa: E501 -- Scoped SQL is kept together for audit.
"""Explicitly curated published descendants. Never catalog-wide authority."""

from types import SimpleNamespace

from .authority_contracts import AuthorityError
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .skill_mcp_service import SkillMcpService
from .test_resource_read_policy import TestReadTarget
from .workbench_prepared_resources import reference


def require(value):
    if not value:
        raise AuthorityError("TEST_READ_POLICY_SNAPSHOT_CHANGED")


def descendant(revisions, current, anchor, anchor_digest, predecessor):
    """Canonical revision identity/digests are checked by the caller first."""
    require(anchor in revisions and revisions[anchor]["digest"] == anchor_digest)
    seen = set()
    while current:
        require(current in revisions and current not in seen)
        seen.add(current)
        if current == anchor:
            return
        current = revisions[current].get(predecessor)
    require(False)


def select(connection, context, spec):
    scope = (context.scope.tenant_id, context.scope.security_domain)
    if spec.kind in {"skill", "mcp"}:
        row = connection.execute(
            "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s "
            "AND security_domain=%s AND kind=%s AND resource_id=%s FOR SHARE",
            (*scope, spec.kind, spec.logicalId),
        ).fetchone()
        if not row:
            return None
        record = row["record"]
        require((record["namespace"], record["securityDomain"]) == scope)
        require(record["resourceId"] == spec.logicalId and record["kind"] == spec.kind)
        facts = connection.execute(
            "SELECT fact FROM skill_mcp_resource.lifecycle_facts WHERE namespace=%s "
            "AND security_domain=%s AND kind=%s AND resource_id=%s ORDER BY ordinal",
            (*scope, spec.kind, spec.logicalId),
        ).fetchall()
        require([r["fact"] for r in facts] == record["facts"])
        require(bool(facts) and facts[0]["fact"]["event"] == "DRAFT_CREATED")
        revisions = {r["revisionId"]: r for r in record["revisions"]}
        require(len(revisions) == len(record["revisions"]))
        for revision in revisions.values():
            require(SkillMcpService._digest(record, revision) == revision["digest"])
        published = {
            f["subject"]["revisionId"]: f["subject"]["digest"]
            for f in record["facts"]
            if f["event"] == "REVISION_PUBLISHED"
        }
        require(published.get(spec.anchorRevision) == spec.anchorDigest)
        current = record.get("publishedRevisionId")
        if (
            not current
            or record.get("archived")
            or not record.get("enabled")
            or record.get("lifecycleState") in {"DEPRECATED", "ARCHIVED"}
        ):
            return None
        require(current in revisions)
        revision = revisions[current]
        if revision["state"] != "PUBLISHED":
            return None
        require(published.get(current) == revision["digest"])
        descendant(
            revisions,
            current,
            spec.anchorRevision,
            spec.anchorDigest,
            "predecessorRevisionId",
        )
        return TestReadTarget(
            owner="SKILL",
            action="READ_RESOURCE",
            resource=reference(spec.kind, spec.logicalId, current),
            digest=revision["digest"],
            purpose=spec.purpose,
        )
    row = connection.execute(
        "SELECT definition_id FROM digital_employee_definition.definitions "
        "WHERE namespace=%s AND security_domain=%s AND definition_id=%s FOR SHARE",
        (*scope, spec.logicalId),
    ).fetchone()
    if not row:
        return None
    rows = connection.execute(
        "SELECT revision_id,predecessor_revision_id,digest FROM digital_employee_definition.revisions "
        "WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
        (*scope, spec.logicalId),
    ).fetchall()
    revisions = {r["revision_id"]: r for r in rows}
    publication = connection.execute(
        "SELECT revision_id,revision_digest FROM digital_employee_definition.facts "
        "WHERE namespace=%s AND security_domain=%s AND definition_id=%s "
        "AND action='PUBLISH' ORDER BY ordinal DESC LIMIT 1",
        (*scope, spec.logicalId),
    ).fetchone()
    anchor = connection.execute(
        "SELECT 1 FROM digital_employee_definition.facts WHERE namespace=%s "
        "AND security_domain=%s AND definition_id=%s AND revision_id=%s "
        "AND revision_digest=%s AND action='PUBLISH'",
        (*scope, spec.logicalId, spec.anchorRevision, spec.anchorDigest),
    ).fetchone()
    require(anchor)
    if not publication:
        return None
    current = publication["revision_id"]
    descendant(
        revisions,
        current,
        spec.anchorRevision,
        spec.anchorDigest,
        "predecessor_revision_id",
    )
    # Original owner verifies canonical records and lifecycle; not merely SQL flags.
    for revision_id in revisions:
        value = PostgresEmployeeDefinitionRepository._read(
            connection,
            SimpleNamespace(namespace=scope[0], security_domain=scope[1]),
            spec.logicalId,
            revision_id,
        )
        require(value["digest"] == revisions[revision_id]["digest"])
        record = value["revision"]
        require((record["namespace"], record["securityDomain"]) == scope)
        require(
            record["definitionId"] == spec.logicalId
            and record["revisionId"] == revision_id
        )
        require(
            record.get("predecessorRevisionId")
            == revisions[revision_id]["predecessor_revision_id"]
        )
        if revision_id == current:
            selected = value
    require(selected["digest"] == publication["revision_digest"])
    if not selected["published"]:
        return None
    return TestReadTarget(
        owner="EMPLOYEE",
        action="READ",
        resource=f"employee:{spec.logicalId}:{current}",
        digest=selected["digest"],
        purpose=spec.purpose,
    )


def lineage_block(connection, context, resource, policy, generation):
    scope = (context.scope.tenant_id, context.scope.security_domain)
    for spec in getattr(policy, "publishedResources", ()):
        prefix = (
            reference(spec.kind, spec.logicalId, "")
            if spec.kind in {"skill", "mcp"}
            else "employee:" + spec.logicalId + ":"
        )
        if not resource.startswith(prefix):
            continue
        if spec.kind in {"skill", "mcp"}:
            rows = connection.execute(
                "SELECT r->>'revisionId' revision FROM skill_mcp_resource.resources t, "
                "LATERAL jsonb_array_elements(t.record->'revisions') r "
                "WHERE namespace=%s AND security_domain=%s AND kind=%s AND resource_id=%s",
                (*scope, spec.kind, spec.logicalId),
            ).fetchall()
            owner, action = "SKILL", "READ_RESOURCE"
        else:
            rows = connection.execute(
                "SELECT revision_id revision FROM digital_employee_definition.revisions "
                "WHERE namespace=%s AND security_domain=%s AND definition_id=%s",
                (*scope, spec.logicalId),
            ).fetchall()
            owner, action = "EMPLOYEE", "READ"
        refs = [prefix + r["revision"] for r in rows]
        same_subject = set()
        known = set()
        for identity in (*generation.credentials, *generation.local_accounts):
            ids = {
                identity.credential_id,
                getattr(identity, "grant_source_id", identity.credential_id),
            }
            known.update(ids)
            if (
                identity.principal_id == context.principal_id
                and identity.scope == context.scope
            ):
                same_subject.update(ids)
        relevant = {
            credential
            for credential, grant in generation.static_grant_revocation_tombstones
            if grant.owner == owner
            and grant.action == action
            and grant.exact_resource in refs
        }
        if relevant - known:
            # Removal is legal while tombstones survive. Without an immutable
            # subject/scope mapping we cannot infer whose revocation this was.
            # Abort the entire preparation before issuing any other target.
            raise AuthorityError("TEST_READ_LINEAGE_IDENTITY_UNVERIFIED")
        if relevant & same_subject:
            return "REVOKED"
        params = (*scope, context.principal_id, owner, action, refs)
        if connection.execute(
            "SELECT 1 FROM authorization_admin.grants g JOIN authorization_admin.grant_revocation_facts f USING(grant_id) "
            "WHERE g.tenant_id=%s AND g.security_domain=%s AND g.subject_principal_id=%s "
            "AND g.owner=%s AND g.action=%s AND g.exact_resource=ANY(%s) LIMIT 1",
            params,
        ).fetchone():
            return "REVOKED"
        if connection.execute(
            "SELECT 1 FROM authorization_admin.grant_requests r JOIN authorization_admin.grant_request_members m USING(request_id) "
            "WHERE r.tenant_id=%s AND r.security_domain=%s AND r.subject_principal_id=%s "
            "AND m.owner=%s AND m.action=%s AND m.exact_resource=ANY(%s) AND r.state='REJECTED' LIMIT 1",
            params,
        ).fetchone():
            return "DENIED"
        return None
    raise AuthorityError("TEST_READ_POLICY_TARGET_UNAVAILABLE")
