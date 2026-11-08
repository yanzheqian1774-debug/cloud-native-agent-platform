# ruff: noqa: E501 -- Parameterized receipt provenance SQL.
"""Read-only, same-actor handoff from the existing exact prepared Skill owner."""

from .resource_use_domain import canonical_digest
from .skill_mcp_service import SkillMcpService


def read_handoff(connection, context, identity, command_key):
    if not isinstance(command_key, str) or not 8 <= len(command_key) <= 120:
        return None
    scope = (context.scope.tenant_id, context.scope.security_domain)
    rows = connection.execute(
        "SELECT command_key,digest,result FROM execution_authority.prepared_resource_commands "
        "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
        "AND result->>'schemaVersion'='prepared-skill-successor-receipt.v1' "
        "AND result->'draft'->>'resource_id'=%s AND command_key=%s LIMIT 2",
        (
            *scope,
            context.principal_id,
            identity,
            "prepared-skill-successor:" + command_key,
        ),
    ).fetchall()
    if len(rows) != 1:
        return None
    row = connection.execute(
        "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s "
        "AND security_domain=%s AND kind='skill' AND resource_id=%s",
        (*scope, identity),
    ).fetchone()
    if not row:
        return None
    record = row["record"]
    if (
        record.get("kind") != "skill"
        or record.get("resourceId") != identity
        or record.get("namespace") != scope[0]
        or record.get("securityDomain") != scope[1]
    ):
        return None
    raw_revisions = record.get("revisions", [])
    if not isinstance(raw_revisions, list) or any(
        not isinstance(r, dict) or not isinstance(r.get("revisionId"), str)
        for r in raw_revisions
    ):
        return None
    revisions = {r["revisionId"]: r for r in raw_revisions}
    if len(revisions) != len(raw_revisions):
        return None
    for command in rows:
        try:
            receipt = command["result"]
            predecessor, draft = receipt["predecessor"], receipt["draft"]
            version = receipt["aggregateVersion"]
            if (
                receipt["actor"] != context.principal_id
                or command["command_key"]
                != "prepared-skill-successor:" + receipt["commandKey"]
                or receipt["state"] != "DRAFT"
                or receipt["published"] is not False
                or receipt["executionStarted"] is not False
                or predecessor["resource_id"] != identity
                or draft["resource_id"] != identity
                or not isinstance(version, int)
                or isinstance(version, bool)
                or version < 3
            ):
                continue
            old = revisions[predecessor["revision_id"]]
            saved = revisions[draft["revision_id"]]
            intermediate = revisions[saved["predecessorRevisionId"]]
            if (
                old["state"] != "PUBLISHED"
                or old["digest"] != predecessor["digest"]
                or saved["digest"] != draft["digest"]
                or intermediate["predecessorRevisionId"] != old["revisionId"]
                or intermediate["content"] != old["content"]
                or canonical_digest(saved["content"]) != receipt["contentDigest"]
                or any(
                    SkillMcpService._digest(record, revision) != revision["digest"]
                    for revision in (old, intermediate, saved)
                )
            ):
                continue
            # The original owner writes exactly successor + edit in one UoW.
            # Reconstruct its canonical request; a loose resource ID or grant
            # alone cannot become a management ownership record.
            payload = {
                "expectedVersion": version - 2,
                "expectedPublishedDigest": predecessor["digest"],
                "content": saved["content"],
                "reason": receipt["reason"],
                "commandKey": receipt["commandKey"],
            }
            path = {"identity": identity, "revision": old["revisionId"]}
            if command["digest"] != canonical_digest([path, payload]):
                continue
            facts = connection.execute(
                "SELECT fact FROM skill_mcp_resource.lifecycle_facts WHERE namespace=%s "
                "AND security_domain=%s AND kind='skill' AND resource_id=%s "
                "AND fact->>'actor'=%s AND fact->'subject'->>'revisionId'=ANY(%s)",
                (
                    *scope,
                    identity,
                    context.principal_id,
                    [intermediate["revisionId"], saved["revisionId"]],
                ),
            ).fetchall()
            if all(
                any(
                    fact["fact"].get("event") == event
                    and fact["fact"].get("subject", {}).get("revisionId")
                    == revision["revisionId"]
                    and fact["fact"].get("subject", {}).get("digest")
                    == revision["digest"]
                    for fact in facts
                )
                for event, revision in [
                    ("SUCCESSOR_CREATED", intermediate),
                    ("DRAFT_EDITED", saved),
                ]
            ):
                return receipt
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    return None
