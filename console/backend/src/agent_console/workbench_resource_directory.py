# ruff: noqa: E501 -- Parameterized exact owner SQL.
"""Authenticated directory of exact readable versions; no legacy default tenant."""

from dataclasses import replace
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError, ExactGrant
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import (
    OWNERS,
    TABLES,
    PreparedResourceOwner,
    reference,
)

KINDS = ("agent", "knowledge", "mcp", "runtime", "skill", "workflow")


class DirectoryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["", "agent", "knowledge", "mcp", "runtime", "skill", "workflow"] = ""
    query: str = Field(default="", max_length=200)
    status: str = Field(default="", max_length=32)
    pageSize: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2048)


def target(kind, identity, revision):
    if kind == "workflow":
        return ExactGrant("WORKFLOW", "READ", f"workflow:{identity}:{revision}")
    if kind not in OWNERS:
        raise WorkbenchOwnerError("RESOURCE_DIRECTORY_NOT_FOUND", 404)
    return ExactGrant(
        OWNERS[kind], "READ_RESOURCE", reference(kind, identity, revision)
    )


class ResourceDirectory:
    def __init__(self, services, cursors, workflows=None):
        self.services, self.cursors = services, cursors
        self.resources = PreparedResourceOwner(services)
        self.workflows = workflows

    def __call__(self, call):
        if call.operation == "READ_DIRECTORY_RESOURCE":
            if call.path["kind"] == "workflow":
                if self.workflows is None:
                    raise WorkbenchOwnerError("RESOURCE_DIRECTORY_NOT_FOUND", 404)
                from .workbench_workflow import WorkflowOwnerAdapter

                return WorkflowOwnerAdapter(self.workflows)(
                    replace(
                        call,
                        operation="READ_WORKFLOW_REVISION",
                        path={
                            "workflow_definition_id": call.path["identity"],
                            "revision_id": call.path["revision"],
                        },
                    )
                )
            value = self.resources(replace(call, operation="READ_PREPARED_RESOURCE"))
            return {
                **value,
                "usage": self.usage(call),
                "subject": call.context.principal_id,
                "scope": {
                    "tenantId": call.context.scope.tenant_id,
                    "securityDomain": call.context.scope.security_domain,
                },
            }
        args = DirectoryQuery.model_validate(call.query)
        p = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        route = "resource-directory:" + canonical_digest(
            [p.principal_id, args.kind, args.query, args.status]
        )
        after = (
            self.cursors.resolve(
                args.cursor,
                route=route,
                context=call.context,
                page_size=args.pageSize,
                key_size=3,
            )
            if args.cursor
            else None
        )
        result, scanned = [], 0
        for kind in KINDS:
            if (args.kind and args.kind != kind) or (after and kind < after[0]):
                continue
            table, column = (
                TABLES[kind]
                if kind != "workflow"
                else ("workflow_definition.definitions", "workflow_definition_id")
            )
            if not call.connection.execute(
                "SELECT to_regclass(%s) t", (table,)
            ).fetchone()["t"]:
                continue
            lower = after[1:] if after and kind == after[0] else ("", "")
            while len(result) <= args.pageSize:
                rows = call.connection.execute(
                    f"SELECT {column} identity,t.record,r FROM {table} t "
                    "CROSS JOIN LATERAL jsonb_array_elements(t.record->'revisions') r "
                    f"WHERE namespace=%s AND security_domain=%s AND ({column},r->>'revisionId')>(%s,%s) "
                    + ("AND kind=%s " if kind in {"skill", "mcp"} else "")
                    + f"ORDER BY {column},r->>'revisionId' LIMIT 100",
                    (
                        p.tenant_id,
                        p.security_domain,
                        *lower,
                        *([kind] if kind in {"skill", "mcp"} else []),
                    ),
                ).fetchall()
                for row in rows:
                    scanned += 1
                    if scanned > 10000:
                        raise WorkbenchOwnerError("RESOURCE_DIRECTORY_SCAN_LIMIT", 503)
                    r, record, identity = row["r"], row["record"], row["identity"]
                    lower = (identity, r["revisionId"])
                    grant = target(kind, identity, r["revisionId"])
                    try:
                        call.authority.require(
                            p, grant.owner, grant.action, grant.exact_resource
                        )
                    except AuthorityError:
                        continue
                    if args.query.casefold() not in record["name"].casefold():
                        continue
                    if args.status and r["state"] != args.status:
                        continue
                    result.append(
                        {
                            "kind": kind,
                            "identity": identity,
                            "revisionId": r["revisionId"],
                            "digest": r["digest"],
                            "name": record["name"],
                            "state": r["state"],
                            "enabled": record.get("enabled", True)
                            and not record.get("archived", False),
                            "isCurrentPublished": record.get("publishedRevisionId")
                            == r["revisionId"],
                            "isCurrentDraft": record.get("currentDraftRevisionId")
                            == r["revisionId"],
                            "createdAt": r.get("createdAt"),
                            "executionReady": False,
                            "policyReviewed": any(
                                f.get("policyBasis")
                                and f.get("revisionId") == r["revisionId"]
                                for f in record.get("facts", [])
                            ),
                        }
                    )
                    if len(result) > args.pageSize:
                        break
                if len(rows) < 100:
                    break
            if len(result) > args.pageSize:
                break
        more = len(result) > args.pageSize
        visible = result[: args.pageSize]
        cursor = (
            self.cursors.mint(
                route=route,
                context=call.context,
                page_size=args.pageSize,
                last_key=(
                    visible[-1]["kind"],
                    visible[-1]["identity"],
                    visible[-1]["revisionId"],
                ),
            )
            if more
            else None
        )
        return {
            "items": visible,
            "subject": p.principal_id,
            "nextCursor": cursor,
            "scope": {"tenantId": p.tenant_id, "securityDomain": p.security_domain},
            "basis": "EXACT_CURRENT_READ_GRANTS",
            "executionAuthority": "NONE",
        }

    @staticmethod
    def usage(call):
        from .ontology_execution import parse_preparation

        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        path = call.path
        rows = call.connection.execute(
            "SELECT p.record,s.record progress FROM execution_authority.run_preparations p "
            "JOIN execution_authority.prepared_run_progress s USING(namespace,security_domain,workflow_run_id) "
            "WHERE p.namespace=%s AND p.security_domain=%s ORDER BY p.workflow_run_id LIMIT 200",
            (principal.tenant_id, principal.security_domain),
        ).fetchall()
        visible = []
        for row in rows:
            p = parse_preparation(row["record"])
            try:
                call.authority.require(
                    principal,
                    "EXECUTION",
                    "READ",
                    "governed-execution:prepared:" + p.digest,
                )
                call.authority.require(
                    principal,
                    "BUSINESS_PROBLEM",
                    "READ",
                    "business-problem:" + p.semantics.target.problem.resource_id,
                )
            except AuthorityError:
                continue
            refs = (
                [p.source_snapshot]
                if path["kind"] == "knowledge"
                else [t.skill.reference for t in p.participants]
                if path["kind"] == "skill"
                else [t.profile for t in p.participants]
                if path["kind"] == "runtime"
                else []
            )
            matched = any(
                ref.resource_id == path["identity"]
                and ref.revision_id == path["revision"]
                for ref in refs
            )
            if path["kind"] == "agent":
                matched = any(
                    call.connection.execute(
                        "SELECT 1 FROM execution_authority.agent_instances WHERE namespace=%s AND security_domain=%s "
                        "AND agent_instance_id=%s AND record->>'agent_definition_id'=%s AND agent_revision_id=%s",
                        (
                            p.namespace,
                            p.security_domain,
                            t.agent_instance_id,
                            path["identity"],
                            path["revision"],
                        ),
                    ).fetchone()
                    for t in p.participants
                )
            if matched:
                visible.append(
                    {
                        "digest": p.digest,
                        "title": p.semantics.title,
                        "planVersion": p.plan_version,
                        "state": row["progress"]["state"],
                        "problemId": p.semantics.target.problem.resource_id,
                    }
                )
        return visible


def operations(services, cursors, workflows=None):
    handler = ResourceDirectory(services, cursors, workflows)
    return (
        WorkbenchOperation(
            "READ_RESOURCE_DIRECTORY",
            "GET",
            PREFIX + "/resource-directory",
            None,
            DirectoryQuery,
            lambda *args: (),
            handler,
        ),
        WorkbenchOperation(
            "READ_DIRECTORY_RESOURCE",
            "GET",
            PREFIX + "/resource-directory/{kind}/{identity}/{revision}",
            None,
            None,
            lambda ctx, path, payload, query: (
                target(path["kind"], path["identity"], path["revision"]),
            ),
            handler,
        ),
    )
