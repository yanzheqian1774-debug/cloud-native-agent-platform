# ruff: noqa: E501 -- Exact owner/resource SQL and registered targets.
"""Narrow trusted Human review/publication bridge to existing resource owners.

No resource creation, discovery, execution or new resource lifecycle authority.
"""

import copy
import json
from contextlib import nullcontext

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import ExactGrant
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError

OWNERS = {
    "skill": "SKILL",
    "agent": "AGENT",
    "runtime": "RUNTIME_PROFILE",
    "knowledge": "KNOWLEDGE",
}
PREFIXES = {
    "skill": "skill-invocation:",
    "agent": "agent:",
    "runtime": "runtime-profile:",
    "knowledge": "knowledge:",
}
TABLES = {
    "skill": ("skill_mcp_resource.resources", "resource_id"),
    "agent": ("agent_definition.definitions", "definition_id"),
    "runtime": ("runtime_profile.profiles", "runtime_profile_id"),
    "knowledge": ("knowledge_operation.knowledge", "knowledge_id"),
}


def reference(kind, identity, revision):
    return PREFIXES[kind] + f"prepared-resource:{identity}:{revision}"


class ReviewPublication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(ge=1)
    digest: str = Field(pattern="^(sha256:)?[0-9a-f]{64}$")
    reason: str = Field(min_length=1, max_length=1000)
    idempotencyKey: str = Field(min_length=1, max_length=200)


def grants(action):
    def targets(context, path, payload, query):
        kind = path["kind"]
        if kind not in OWNERS:
            raise WorkbenchOwnerError("PREPARED_RESOURCE_NOT_FOUND", 404)
        return (
            ExactGrant(
                OWNERS[kind],
                action,
                reference(kind, path["identity"], path["revision"]),
            ),
        )

    return targets


def bind_service(service, connection):
    """Reuse original service and repository methods in the BFF's authorized UoW."""
    clone = copy.copy(service)
    clone.repository = copy.copy(service.repository)

    class Pool:
        def connection(self):
            return nullcontext(connection)

    clone.repository.pool = Pool()
    return clone


class PreparedResourceOwner:
    def __init__(self, services):
        self.services = services

    def __call__(self, call):
        kind, identity, revision = (
            call.path[k] for k in ("kind", "identity", "revision")
        )
        service = self.services.get(kind)
        if service is None:
            raise WorkbenchOwnerError("PREPARED_RESOURCE_OWNER_UNAVAILABLE", 503)
        service = bind_service(service, call.connection)
        scope = service.scope(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        principal = OwnerPrincipal(
            call.context.principal_id, scope.namespace, scope.security_domain
        )
        actor = principal.principal_id
        key = (scope.namespace, scope.security_domain)
        repo_args = (scope, "skill", identity) if kind == "skill" else (scope, identity)
        if call.operation == "READ_PREPARED_RESOURCE":
            record = service.repository.get(*repo_args)
            exact = next(
                (r for r in record["revisions"] if r["revisionId"] == revision), None
            )
            if exact is None:
                raise WorkbenchOwnerError("PREPARED_RESOURCE_NOT_FOUND", 404)
            return {
                "kind": kind,
                "identity": identity,
                "name": record["name"],
                "aggregateVersion": record["aggregateVersion"],
                "revision": exact,
                "publishedRevisionId": record.get("publishedRevisionId"),
            }
        if not actor.startswith("human:") or not call.payload["reason"].strip():
            raise WorkbenchOwnerError("HUMAN_RESOURCE_REVIEW_REQUIRED", 403)
        call.authority.require(
            principal,
            OWNERS[kind],
            "READ_RESOURCE",
            reference(kind, identity, revision),
        )
        digest = canonical_digest(
            {
                "kind": kind,
                "identity": identity,
                "revision": revision,
                "payload": dict(call.payload),
            }
        )
        command_key = call.payload["idempotencyKey"]
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (json.dumps(["prepared-resource", *key, actor, command_key]),),
        )
        prior = call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (*key, actor, command_key),
        ).fetchone()
        if prior:
            if prior["digest"] != digest:
                raise WorkbenchOwnerError("RESOURCE_REVIEW_REPLAY_CONFLICT", 409)
            return prior["result"]
        record = service.repository.get(*repo_args)
        if (
            record["aggregateVersion"] != call.payload["expectedVersion"]
            or record.get("currentDraftRevisionId") != revision
        ):
            raise WorkbenchOwnerError("RESOURCE_REVIEW_TARGET_STALE", 409)
        exact = next(r for r in record["revisions"] if r["revisionId"] == revision)
        if exact["digest"] != call.payload["digest"]:
            raise WorkbenchOwnerError("RESOURCE_REVIEW_TARGET_STALE", 409)
        args = (*repo_args, actor)
        if exact["state"] == "DRAFT":
            service.validate(*args, record["aggregateVersion"])
            record = service.repository.get(*repo_args)
        version = record["aggregateVersion"]
        if kind == "knowledge":
            service.review(*args, version, exact["digest"])
            service.publish(*args, version + 1, exact["digest"])
        else:
            service.review(
                *args, version, exact["digest"], "APPROVE", call.payload["reason"]
            )
            reviewed = service.repository.get(*repo_args)
            service.publish(
                *args, version + 1, exact["digest"], reviewed["reviews"][-1]["reviewId"]
            )
        record = service.repository.get(*repo_args)
        result = {
            "kind": kind,
            "identity": identity,
            "revisionId": revision,
            "digest": exact["digest"],
            "state": "PUBLISHED",
            "aggregateVersion": record["aggregateVersion"],
            "actor": actor,
            "reason": call.payload["reason"],
        }
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES (%s,%s,%s,%s,%s,%s)",
            (*key, actor, command_key, digest, Jsonb(result)),
        )
        return result


class PreparedResourceTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None or grant.action not in {
            "READ_RESOURCE",
            "REVIEW_PUBLISH_RESOURCE",
        }:
            return False
        for kind, owner in OWNERS.items():
            prefix = PREFIXES[kind] + "prepared-resource:"
            if grant.owner != owner or not grant.exact_resource.startswith(prefix):
                continue
            table, col = TABLES[kind]
            # IDs can contain colons: compare exact assembled references, never split IDs.
            return (
                connection.execute(
                    f"SELECT 1 FROM {table} t CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r WHERE namespace=%s AND security_domain=%s "
                    f"AND %s || {col} || ':' || (r->>'revisionId')=%s"
                    + (" AND kind='skill'" if kind == "skill" else ""),
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        prefix,
                        grant.exact_resource,
                    ),
                ).fetchone()
                is not None
            )
        return False


def prepared_resource_operations(services):
    path = PREFIX + "/prepared-resources/{kind}/{identity}/{revision}"
    handler = PreparedResourceOwner(services)
    return (
        WorkbenchOperation(
            "READ_PREPARED_RESOURCE",
            "GET",
            path,
            None,
            None,
            grants("READ_RESOURCE"),
            handler,
        ),
        WorkbenchOperation(
            "REVIEW_PREPARED_RESOURCE",
            "POST",
            path + "/review-publish",
            ReviewPublication,
            None,
            grants("REVIEW_PUBLISH_RESOURCE"),
            handler,
        ),
    )
