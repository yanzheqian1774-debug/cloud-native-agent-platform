"""Explicit exact-authority successor port of the existing prepared Skill owner."""

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import ExactGrant
from .resource_management import ResourceManagement, target
from .resource_use_domain import canonical_digest
from .skill_mcp_schemas import ResourceContent
from .skill_mcp_service import SkillMcpFailure
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service, reference


class PreparedSkillSuccessor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedVersion: int = Field(ge=1)
    expectedPublishedDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: ResourceContent
    reason: str = Field(min_length=1, max_length=1000)
    commandKey: str = Field(min_length=8, max_length=120)


def grants(context, path, payload, query):
    return (
        ExactGrant("SKILL", "MANAGE_RESOURCE", target("skill", path["identity"])),
        ExactGrant(
            "SKILL",
            "READ_RESOURCE",
            reference("skill", path["identity"], path["revision"]),
        ),
    )


class PreparedSkillSuccessorOwner:
    def __init__(self, service):
        self.service = service

    def __call__(self, call):
        context, c = call.context, call.connection
        if not context.principal_id.startswith("human:"):
            raise WorkbenchOwnerError("EXPLICIT_SKILL_SUCCESSOR_REQUIRED", 403)
        principal = OwnerPrincipal(
            context.principal_id,
            context.scope.tenant_id,
            context.scope.security_domain,
        )
        for g in grants(context, call.path, call.payload, call.query):
            call.authority.require(principal, g.owner, g.action, g.exact_resource)
        writing = call.operation == "PREPARE_PREPARED_SKILL_SUCCESSOR"
        if not writing and call.operation != "READ_PREPARED_SKILL_SUCCESSOR":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        spec = PreparedSkillSuccessor.model_validate(call.payload) if writing else None
        if spec is not None and not spec.reason.strip():
            raise WorkbenchOwnerError("SKILL_SUCCESSOR_REASON_REQUIRED", 422)
        key = spec.commandKey if spec else call.path["command_key"]
        storage_key = "prepared-skill-successor:" + key
        scope = (context.scope.tenant_id, context.scope.security_domain)
        if writing:
            c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (canonical_digest([*scope, context.principal_id, storage_key]),),
            )
        prior = c.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands "
            "WHERE namespace=%s AND security_domain=%s AND actor_id=%s "
            "AND command_key=%s",
            (*scope, context.principal_id, storage_key),
        ).fetchone()
        payload_digest = (
            canonical_digest([call.path, call.payload]) if writing else None
        )
        if prior:
            result = prior["result"]
            if (
                result.get("predecessor", {}).get("resource_id")
                != call.path["identity"]
                or result["predecessor"]["revision_id"] != call.path["revision"]
            ):
                raise WorkbenchOwnerError("SKILL_SUCCESSOR_RECEIPT_NOT_FOUND", 404)
            if writing and prior["digest"] != payload_digest:
                raise WorkbenchOwnerError("SKILL_SUCCESSOR_KEY_CONFLICT", 409)
            return result
        if not writing:
            raise WorkbenchOwnerError("SKILL_SUCCESSOR_RECEIPT_NOT_FOUND", 404)
        content = spec.content.model_dump(exclude_unset=True)
        ResourceManagement.safe_content("skill", content)
        service = bind_service(self.service, c)
        rs = service.scope(*scope)
        try:
            old = service.repository.get(rs, "skill", call.path["identity"])
            exact = next(
                (
                    r
                    for r in old["revisions"]
                    if r["revisionId"] == call.path["revision"]
                ),
                None,
            )
            if (
                old["aggregateVersion"] != spec.expectedVersion
                or old.get("publishedRevisionId") != call.path["revision"]
                or old.get("currentDraftRevisionId")
                or old.get("archived")
                or old.get("enabled", True) is not True
                or not exact
                or exact["state"] != "PUBLISHED"
                or exact["digest"] != spec.expectedPublishedDigest
            ):
                raise WorkbenchOwnerError("SKILL_SUCCESSOR_PREDECESSOR_STALE", 409)
            successor = service.successor(
                rs,
                "skill",
                call.path["identity"],
                context.principal_id,
                spec.expectedVersion,
            )["resource"]
            saved = service.edit(
                rs,
                "skill",
                call.path["identity"],
                context.principal_id,
                successor["aggregateVersion"],
                content,
            )["resource"]
        except SkillMcpFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        draft = next(
            r
            for r in saved["revisions"]
            if r["revisionId"] == saved["currentDraftRevisionId"]
        )
        result = {
            "schemaVersion": "prepared-skill-successor-receipt.v1",
            "actor": context.principal_id,
            "predecessor": {
                "resource_id": call.path["identity"],
                "revision_id": call.path["revision"],
                "digest": spec.expectedPublishedDigest,
            },
            "draft": {
                "resource_id": call.path["identity"],
                "revision_id": draft["revisionId"],
                "digest": draft["digest"],
            },
            "aggregateVersion": saved["aggregateVersion"],
            "commandKey": key,
            "reason": spec.reason,
            "contentDigest": canonical_digest(content),
            "state": "DRAFT",
            "published": False,
            "executionStarted": False,
        }
        c.execute(
            "INSERT INTO execution_authority.prepared_resource_commands"
            "(namespace,security_domain,actor_id,command_key,digest,result) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (*scope, context.principal_id, storage_key, payload_digest, Jsonb(result)),
        )
        return result


def operations(service):
    path = (
        f"{PREFIX}/prepared-resources/skill/{{identity}}"
        "/revisions/{revision}/successors"
    )
    handler = PreparedSkillSuccessorOwner(service)
    return (
        WorkbenchOperation(
            "PREPARE_PREPARED_SKILL_SUCCESSOR",
            "POST",
            path,
            PreparedSkillSuccessor,
            None,
            grants,
            handler,
        ),
        WorkbenchOperation(
            "READ_PREPARED_SKILL_SUCCESSOR",
            "GET",
            path + "/by-key/{command_key}",
            None,
            None,
            grants,
            handler,
        ),
    )
