# ruff: noqa: E501 -- Parameterized owner SQL and exact reference strings.
"""P08 bounded discovery over existing owners, never an execution authority."""

from .authority_contracts import AuthorityError
from .digital_employee_definition import EmployeeRevision
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .plan_suggestion_domain import ExactReference, PlanningError, ResourceObservation
from .resource_use_domain import canonical_digest
from .workbench_prepared_resources import reference

# Fixed owner relations; request input never becomes a SQL identifier.
OWNERS = {
    "SKILL": ("skill_mcp_resource.resources", "resource_id", "SKILL", "skill"),
    "MCP": ("skill_mcp_resource.resources", "resource_id", "SKILL", "mcp"),
    "KNOWLEDGE": (
        "knowledge_operation.knowledge",
        "knowledge_id",
        "KNOWLEDGE",
        "knowledge",
    ),
    "RUNTIME": (
        "runtime_profile.profiles",
        "runtime_profile_id",
        "RUNTIME_PROFILE",
        "runtime",
    ),
    "AGENT": ("agent_definition.definitions", "definition_id", "AGENT", "agent"),
    "WORKFLOW": (
        "workflow_definition.definitions",
        "workflow_definition_id",
        "WORKFLOW",
        "workflow",
    ),
}


def require_read(authority, principal, kind, ref):
    if kind == "EMPLOYEE":
        owner, action, target = (
            "EMPLOYEE",
            "READ",
            f"employee:{ref.resource_id}:{ref.revision_id}",
        )
    elif kind in {"SKILL", "MCP", "KNOWLEDGE", "RUNTIME", "AGENT"}:
        owner, action, target = (
            OWNERS[kind][2],
            "READ_RESOURCE",
            reference(OWNERS[kind][3], ref.resource_id, ref.revision_id),
        )
    elif kind == "WORKFLOW":
        owner, action, target = (
            "WORKFLOW",
            "READ",
            f"workflow:{ref.resource_id}:{ref.revision_id}",
        )
    else:
        # These owners have no prepared-resource bridge. Do not reinterpret a
        # Skill grant as MCP/Workflow permission or invent registered grant kinds.
        raise AuthorityError("CANDIDATE_OWNER_READ_PORT_UNAVAILABLE")
    authority.require(principal, owner, action, target)


def read_published(c, scope, kind, ref, *, historical=False):
    if kind == "EMPLOYEE":
        value = PostgresEmployeeDefinitionRepository._read(
            c, scope, ref.resource_id, ref.revision_id
        )
        if not value["published"] or value["digest"] != ref.digest:
            raise PlanningError("CANDIDATE_VERSION_UNAVAILABLE")
        PostgresEmployeeDefinitionRepository.validate_members(
            c, EmployeeRevision.from_record(value["revision"])
        )
        return value["revision"], value["revision"].get("role", ref.resource_id)
    table, col, _, _ = OWNERS[kind]
    row = c.execute(
        f"SELECT record FROM {table} WHERE namespace=%s AND security_domain=%s AND {col}=%s"
        + (" AND kind=%s" if kind in {"SKILL", "MCP"} else ""),
        (
            scope.namespace,
            scope.security_domain,
            ref.resource_id,
            *([kind.lower()] if kind in {"SKILL", "MCP"} else []),
        ),
    ).fetchone()
    if not row:
        raise PlanningError("CANDIDATE_VERSION_UNAVAILABLE")
    record = row["record"]
    revision = next(
        (r for r in record.get("revisions", []) if r["revisionId"] == ref.revision_id),
        None,
    )
    if (
        (
            not historical
            and (
                record.get("archived")
                or record.get("enabled", True) is not True
                or record.get("publishedRevisionId") != ref.revision_id
            )
        )
        or not revision
        or revision.get("state")
        not in ({"PUBLISHED", "DEPRECATED"} if historical else {"PUBLISHED"})
        or str(revision.get("digest", "")).removeprefix("sha256:") != ref.digest
    ):
        raise PlanningError("CANDIDATE_VERSION_UNAVAILABLE")
    return revision["content"], record.get("name", ref.resource_id)


def identities(c, scope, kind, limit=200):
    if kind == "EMPLOYEE":
        return c.execute(
            "SELECT definition_id identity,revision_id revision,digest FROM digital_employee_definition.revisions WHERE namespace=%s AND security_domain=%s ORDER BY definition_id,revision_id LIMIT %s",
            (scope.namespace, scope.security_domain, limit),
        ).fetchall()
    if kind not in OWNERS:
        return []
    table, col, _, _ = OWNERS[kind]
    if not c.execute("SELECT to_regclass(%s) present", (table,)).fetchone()["present"]:
        raise PlanningError("CANDIDATE_OWNER_UNAVAILABLE")
    return c.execute(
        f"SELECT {col} identity,record->>'publishedRevisionId' revision,r->>'digest' digest FROM {table} t CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r WHERE namespace=%s AND security_domain=%s AND r->>'revisionId'=record->>'publishedRevisionId'"
        + (" AND kind=%s" if kind in {"SKILL", "MCP"} else "")
        + f" ORDER BY {col},r->>'revisionId' LIMIT %s",
        (
            scope.namespace,
            scope.security_domain,
            *([kind.lower()] if kind in {"SKILL", "MCP"} else []),
            limit,
        ),
    ).fetchall()


def declaration(c, scope, authority, principal, kind, content, operations):
    available = set()
    schemas = set()
    configuration = {}
    if kind == "EMPLOYEE":
        for m in content.get("members", []):
            if str(m.get("kind")) != "SKILL":
                continue
            ref = ExactReference(
                resource_id=m["resource_id"],
                revision_id=m["revision_id"],
                digest=m["digest"],
            )
            try:
                require_read(authority, principal, "SKILL", ref)
                skill, _ = read_published(c, scope, "SKILL", ref)
            except (AuthorityError, PlanningError):
                return {
                    "status": "MEMBER_CONFIGURATION_UNREADABLE",
                    "missingOperations": [],
                    "sourceSchemas": [],
                    "configuration": {},
                    "executionReady": False,
                }
            available.update(
                o["name"]
                for o in skill.get("operations", [])
                if o.get("sideEffectClass") == "READ_ONLY"
            )
            for o in skill.get("operations", []):
                schemas.update(
                    o.get("inputSchema", {})
                    .get("properties", {})
                    .get("schemaVersion", {})
                    .get("enum", [])
                )
        configuration = {
            "role": content.get("role"),
            "responsibilities": content.get("responsibilities", []),
            "members": len(content.get("members", [])),
        }
    elif kind in {"SKILL", "MCP"}:
        ops = content.get("operations", [])
        available = {o["name"] for o in ops if o.get("sideEffectClass") == "READ_ONLY"}
        for o in ops:
            schemas.update(
                o.get("inputSchema", {})
                .get("properties", {})
                .get("schemaVersion", {})
                .get("enum", [])
            )
        configuration = {
            "operations": [
                {
                    "name": o["name"],
                    "sideEffectClass": o.get("sideEffectClass"),
                    "inputSchemaDigest": canonical_digest(o.get("inputSchema", {})),
                    "outputSchemaDigest": canonical_digest(o.get("outputSchema", {})),
                    "executorId": o.get("executorId"),
                    "executorRevision": o.get("executorRevision"),
                    "ioLimits": o.get("ioLimits"),
                }
                for o in ops
            ]
        }
    elif kind == "KNOWLEDGE":
        # Expose only known source-family metadata after the caller's exact
        # owner READ; never send document text to the candidate chooser.
        import json

        for document in content.get("documents", []):
            for chunk in document.get("chunks", []):
                try:
                    source = json.loads(chunk.get("content", ""))
                except (ValueError, TypeError):
                    continue
                if isinstance(source, dict) and source.get("schemaVersion") in {
                    "sales-diagnostic-source.v1",
                    "synthetic-delivery-source.v1",
                }:
                    schemas.add(source["schemaVersion"])
        configuration = {
            "documents": [
                {
                    "contentDigest": d.get("contentDigest"),
                    "chunks": len(d.get("chunks", [])),
                }
                for d in content.get("documents", [])
            ]
        }
    elif kind == "RUNTIME":
        configuration = {
            "provider": content.get("provider"),
            "classification": "DECLARATION_NOT_LIVE_INSTANCE",
        }
    elif kind == "AGENT":
        configuration = {
            "businessPurpose": content.get("businessPurpose"),
            "model": {
                k: v
                for k, v in (content.get("bindings", {}).get("model") or {}).items()
                if k in {"resourceId", "revisionId", "digest"}
            },
        }
    missing = (
        sorted(set(operations) - available)
        if kind in {"EMPLOYEE", "SKILL", "MCP"}
        else []
    )
    return {
        "status": "DECLARED_CONTRACT_REQUIRED"
        if not operations and kind in {"EMPLOYEE", "SKILL", "MCP"}
        else "OPERATION_GAP"
        if missing
        else "DECLARED_OPERATIONS_MATCH"
        if kind in {"EMPLOYEE", "SKILL", "MCP"}
        else "SOURCE_OR_CONFIGURATION_REQUIRES_REVIEW",
        "missingOperations": missing,
        "declaredOperations": sorted(available),
        "sourceSchemas": sorted(schemas),
        "configuration": configuration,
        "executionReady": False,
    }


def discover(c, scope, authority, principal, proposal, requirement):
    kind = requirement.kind
    if kind not in {
        "EMPLOYEE",
        "SKILL",
        "MCP",
        "KNOWLEDGE",
        "RUNTIME",
        "AGENT",
        "WORKFLOW",
    }:
        return {
            "requirementId": requirement.requirement_id,
            "kind": kind,
            "state": "OWNER_READ_PORT_UNAVAILABLE",
            "candidates": [],
            "executionReady": False,
        }
    operations = sorted(
        {
            t.operation
            for t in proposal.semantics.tasks
            if hasattr(t, "operation")
            and (
                t.employee_requirement_id == requirement.requirement_id
                or requirement.requirement_id in t.requirement_ids
            )
        }
    )
    result = []
    from .digital_employee_definition import EmployeeDefinitionError

    for item in identities(c, scope, kind):
        ref = ExactReference(
            resource_id=item["identity"],
            revision_id=item["revision"],
            digest=item["digest"].removeprefix("sha256:"),
        )
        try:
            require_read(authority, principal, kind, ref)
            content, name = read_published(c, scope, kind, ref)
        except (AuthorityError, PlanningError, EmployeeDefinitionError):
            continue
        result.append(
            {
                "name": name,
                "reference": ref.model_dump(mode="json"),
                "selected": ref == requirement.selected,
                "publication": "PUBLISHED",
                "permission": "READABLE",
                "assessment": declaration(
                    c, scope, authority, principal, kind, content, operations
                ),
            }
        )
    return {
        "requirementId": requirement.requirement_id,
        "kind": kind,
        "state": "READABLE_PUBLISHED_CANDIDATES"
        if result
        else "NO_READABLE_PUBLISHED_CANDIDATE",
        "candidates": result,
        "scanLimit": 200,
        "executionReady": False,
    }


class ExactPlanningOwnerReader:
    def __init__(self, c, scope, authority, kind):
        self.c, self.scope, self.authority, self.kind = c, scope, authority, kind

    def observe(self, principal, requirement):
        ref = requirement.selected
        try:
            require_read(self.authority, principal, self.kind, ref)
            read_published(self.c, self.scope, self.kind, ref)
        except AuthorityError:
            return ResourceObservation(
                requirement_id=requirement.requirement_id,
                status="UNREADABLE",
                reason="RESOURCE_NOT_READABLE",
            )
        except PlanningError:
            return ResourceObservation(
                requirement_id=requirement.requirement_id,
                status="UNAVAILABLE",
                reason="EXACT_PUBLISHED_REFERENCE_UNAVAILABLE",
            )
        return ResourceObservation(
            requirement_id=requirement.requirement_id,
            status="MATCHED",
            reason="OWNER_EXACT_PUBLISHED_REFERENCE",
            exact_reference=ref,
            publication_checked=True,
            permission_checked=True,
        )
