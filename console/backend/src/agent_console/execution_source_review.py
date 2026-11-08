# ruff: noqa: E501 -- Fixed scoped owner SQL and exact resource references.
"""Exact saved-execution review, pinned original-text search and MCP source checks.

Source checks are separate post-result maintenance observations, never Run effects.
"""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .digital_employee_definition import EmployeeDefinitionError
from .digital_employee_definition_postgres import PostgresEmployeeDefinitionRepository
from .execution_domain import ScopeIdentity
from .knowledge_quality import KnowledgeQualityService
from .knowledge_repository import KnowledgeNotFound
from .plan_suggestion_domain import ExactReference
from .resource_management import target
from .resource_use_domain import canonical_digest
from .skill_mcp_service import SkillMcpFailure
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_execution import PreparedExecutionOwner, grant
from .workbench_prepared_resources import bind_service, reference

SCHEMA = "execution-source-verification.v1"
LEDGER = "execution-source-check:"


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subject: str
    tenantId: str
    securityDomain: str
    executionDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: ExactReference
    sourceDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    csvDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    mcp: ExactReference
    selectionId: str
    toolName: Literal["verify_project_sales_source"]
    expiresAt: datetime


class ReviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["execution-source-review-policy.v1"]
    policyId: str
    bindings: tuple[Binding, ...]

    @classmethod
    def load(cls, path):
        return cls.model_validate_json(Path(path).read_text()) if path else None

    def binding(self, ctx, digest, source):
        found = [
            b
            for b in self.bindings
            if (b.subject, b.tenantId, b.securityDomain, b.executionDigest, b.source)
            == (
                ctx.principal_id,
                ctx.scope.tenant_id,
                ctx.scope.security_domain,
                digest,
                ExactReference.model_validate(source),
            )
            and b.expiresAt.tzinfo is not None
            and b.expiresAt > datetime.now(UTC)
        ]
        return found[0] if len(found) == 1 else None


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=2000)


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotencyKey: str = Field(min_length=8, max_length=120)
    source: ExactReference
    mcp: ExactReference
    expectedVersion: int = Field(ge=1)


class ExecutionSourceReview:
    def __init__(
        self, services, coordinator=None, policy=None, *, sales_v2_candidate=False
    ):
        self.services, self.policy = services, policy
        self.execution = PreparedExecutionOwner(
            coordinator, sales_v2_candidate=sales_v2_candidate
        )

    @staticmethod
    def principal(call):
        return OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )

    def saved(self, call):
        p = self.principal(call)
        call.authority.require(
            p, "EXECUTION", "READ", "governed-execution:prepared:" + call.path["digest"]
        )
        view = self.execution(
            replace(call, operation="READ_PREPARED_EXECUTION", payload={}, query={})
        )
        if view["digest"] != call.path["digest"]:
            raise WorkbenchOwnerError("REVIEW_EXECUTION_MISMATCH", 409)
        return view

    def source(self, call, view):
        ref = view["preparation"]["source_snapshot"]
        call.authority.require(
            self.principal(call),
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", ref["resource_id"], ref["revision_id"]),
        )
        service = bind_service(self.services["knowledge"], call.connection)
        scope = service.scope(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        record = service.repository.get(scope, ref["resource_id"])
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == ref["revision_id"]),
            None,
        )
        if (
            not revision
            or revision["digest"] != ref["digest"]
            or revision["state"] not in {"PUBLISHED", "DEPRECATED"}
        ):
            raise WorkbenchOwnerError("REVIEW_SOURCE_VERSION_MISMATCH", 409)
        pinned = deepcopy(record)
        pinned.update(
            publishedRevisionId=ref["revision_id"],
            currentDraftRevisionId=None,
            activeIndexSnapshotId=None,
        )
        pinned["revisions"] = [revision]
        return scope, pinned, revision

    def mcp(self, call, binding, *, operate=False):
        p = self.principal(call)
        call.authority.require(
            p,
            "SKILL",
            "READ_RESOURCE",
            reference("mcp", binding.mcp.resource_id, binding.mcp.revision_id),
        )
        if operate:
            for action in ("MANAGE_RESOURCE", "CONNECT_MCP"):
                call.authority.require(
                    p, "SKILL", action, target("mcp", binding.mcp.resource_id)
                )
            owned = call.connection.execute(
                "SELECT 1 FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND result->>'schemaVersion'='resource-management-receipt.v1' AND result->>'kind'='mcp' AND result->>'action'='create' AND result->>'identity'=%s",
                (
                    p.tenant_id,
                    p.security_domain,
                    p.principal_id,
                    binding.mcp.resource_id,
                ),
            ).fetchone()
            if not owned:
                raise WorkbenchOwnerError("SOURCE_CHECK_MCP_NOT_OWNED", 404)
        service = bind_service(
            self.services.get("mcp", self.services["skill"]), call.connection
        )
        scope = service.scope(p.tenant_id, p.security_domain)
        record = service.repository.get(scope, "mcp", binding.mcp.resource_id)
        revision = next(
            (
                r
                for r in record["revisions"]
                if r["revisionId"] == binding.mcp.revision_id
            ),
            None,
        )
        if (
            not revision
            or revision["digest"] != binding.mcp.digest
            or revision["state"] != "PUBLISHED"
            or record["publishedRevisionId"] != binding.mcp.revision_id
            or not record.get("enabled")
            or record.get("archived")
            or record.get("currentDraftRevisionId")
            or revision["content"].get("sideEffect") != "READ"
            or revision["content"].get("secretReference")
        ):
            raise WorkbenchOwnerError("SOURCE_CHECK_MCP_VERSION_UNAVAILABLE", 409)
        selection = next(
            (
                x
                for x in record["toolSelections"]
                if x["selectionId"] == binding.selectionId
            ),
            None,
        )
        snapshot = next(
            (
                x
                for x in record["discoverySnapshots"]
                if selection and x["snapshotId"] == selection["snapshotId"]
            ),
            None,
        )
        tool = (
            next(
                (
                    x
                    for x in snapshot["catalog"]["tools"]
                    if x.get("name") == binding.toolName
                ),
                None,
            )
            if snapshot
            else None
        )
        if (
            not selection
            or binding.toolName not in selection["toolNames"]
            or selection.get("revisionDigest") != binding.mcp.digest
            or not tool
            or record["discoverySnapshots"][-1]["snapshotId"] != selection["snapshotId"]
            or tool.get("annotations", {}).get("readOnlyHint") is not True
            or tool.get("annotations", {}).get("destructiveHint") is not False
        ):
            raise WorkbenchOwnerError("SOURCE_CHECK_READ_ONLY_TOOL_REQUIRED", 409)
        return service, scope, record, revision

    def binding(self, call, view):
        return (
            self.policy.binding(
                call.context, view["digest"], view["preparation"]["source_snapshot"]
            )
            if self.policy
            else None
        )

    def review(self, call, view):
        _, record, _ = self.source(call, view)
        p = self.principal(call)
        employees = {}
        scope = ScopeIdentity(p.tenant_id, p.security_domain)
        for task in view["preparation"]["semantics"]["tasks"]:
            actor = next(
                (
                    a
                    for a in view["preparation"]["participants"]
                    if a["task_id"] == task["task_id"]
                ),
                None,
            )
            if actor is None:
                raise WorkbenchOwnerError("REVIEW_TASK_BINDING_MISSING", 409)
            ref = actor["definition"]
            call.authority.require(
                p,
                "EMPLOYEE",
                "READ",
                f"employee:{ref['resource_id']}:{ref['revision_id']}",
            )
            value = PostgresEmployeeDefinitionRepository.read_revision_for_workbench(
                call.connection,
                scope,
                ref["resource_id"],
                ref["revision_id"],
                authorized=True,
            )
            if value["digest"] != ref["digest"]:
                raise WorkbenchOwnerError("REVIEW_EMPLOYEE_MISMATCH", 409)
            key = canonical_digest(ref)
            item = employees.setdefault(
                key, {"name": value["revision"]["role"], "reference": ref, "tasks": []}
            )
            state = next(
                (
                    x
                    for x in (view.get("progress") or {}).get("tasks", [])
                    if x["task_id"] == task["task_id"]
                ),
                {},
            )
            observation = (
                call.connection.execute(
                    "SELECT state,queued_at,effect_started_at,terminal_at,kubernetes_task_uid FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
                    (p.tenant_id, p.security_domain, state.get("attempt_id")),
                ).fetchone()
                if state.get("attempt_id")
                else None
            )
            if observation:
                observation = {
                    k: (v.isoformat() if isinstance(v, datetime) else v)
                    for k, v in observation.items()
                }
            item["tasks"].append(
                {
                    "title": task["title"],
                    "taskId": task["task_id"],
                    "state": state.get("state", "NOT_STARTED"),
                    "nativeObservation": observation,
                    "instanceId": actor["instance_id"],
                    "assignmentId": actor["assignment_id"],
                }
            )
        mcp = {"available": False}
        binding = self.binding(call, view)
        if binding:
            try:
                _, _, r, revision = self.mcp(call, binding, operate=True)
                mcp = {
                    "available": True,
                    "reference": binding.mcp.model_dump(mode="json"),
                    "name": r["name"],
                    "endpoint": revision["content"]["endpoint"],
                    "toolName": binding.toolName,
                    "expectedVersion": r["aggregateVersion"],
                    "phase": "POST_RESULT_SOURCE_VERIFICATION",
                }
            except (AuthorityError, WorkbenchOwnerError):
                mcp = {"available": False, "reason": "CURRENT_ACCESS_REQUIRED"}
        return {
            "schemaVersion": "execution-source-review.v1",
            "executionDigest": view["digest"],
            "subject": p.principal_id,
            "scope": {"tenantId": p.tenant_id, "securityDomain": p.security_domain},
            "runState": (view.get("progress") or {}).get("state", "NOT_STARTED"),
            "employees": list(employees.values()),
            "source": {
                "reference": view["preparation"]["source_snapshot"],
                "name": record["name"],
            },
            "mcp": mcp,
            "originalRunChanged": False,
            "runtimeHealth": "NOT_INFERRED_FROM_TASK_STATE",
        }

    def search(self, call, view):
        scope, record, revision = self.source(call, view)
        query = Query.model_validate(call.query).query.strip()
        if query:
            result = KnowledgeQualityService(
                SimpleNamespace(list=lambda _: [record])
            ).search(
                scope,
                query=query,
                mode="LEXICAL",
                top_k=5,
                knowledge_id=record["knowledgeId"],
                revision_id=revision["revisionId"],
            )
        else:
            result = {
                "classification": "ORIGINAL_TEXT",
                "results": [
                    {"rank": i + 1, "citation": c}
                    for i, c in enumerate(KnowledgeQualityService._chunks(record)[:5])
                ],
            }
        if len(json.dumps(result, ensure_ascii=False).encode()) > 262144:
            raise WorkbenchOwnerError("ORIGINAL_TEXT_RESULT_LIMIT", 409)
        return {
            "executionDigest": view["digest"],
            "source": view["preparation"]["source_snapshot"],
            "name": record["name"],
            "query": query,
            "retrieval": result,
            "indexCreated": False,
            "modelCalls": 0,
        }

    def check(self, call, view):
        binding = self.binding(call, view)
        if not binding or (view.get("progress") or {}).get("state") != "SUCCEEDED":
            raise WorkbenchOwnerError("SOURCE_CHECK_SCOPE_OR_TERMINAL_REQUIRED", 403)
        _, _, source_revision = self.source(call, view)
        service, scope, record, _ = self.mcp(call, binding, operate=True)
        reading = call.operation == "READ_EXECUTION_SOURCE_CHECK"
        spec = None if reading else Check.model_validate(call.payload)
        key = call.path["key"] if reading else spec.idempotencyKey
        storage_key = LEDGER + key
        if not reading:
            call.connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (
                    canonical_digest(
                        [
                            scope.namespace,
                            scope.security_domain,
                            call.context.principal_id,
                            storage_key,
                        ]
                    ),
                ),
            )
        prior = call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                scope.namespace,
                scope.security_domain,
                call.context.principal_id,
                storage_key,
            ),
        ).fetchone()
        digest = canonical_digest([view["digest"], call.payload]) if spec else None
        if prior:
            if (
                prior["result"]["executionDigest"] != view["digest"]
                or prior["result"]["source"] != binding.source.model_dump(mode="json")
                or prior["result"]["mcp"] != binding.mcp.model_dump(mode="json")
                or (spec and prior["digest"] != digest)
            ):
                raise WorkbenchOwnerError("SOURCE_CHECK_KEY_CONFLICT", 409)
            return prior["result"]
        if reading:
            raise WorkbenchOwnerError("SOURCE_CHECK_RECEIPT_NOT_FOUND", 404)
        if (
            spec.source != binding.source
            or spec.mcp != binding.mcp
            or spec.expectedVersion != record["aggregateVersion"]
        ):
            raise WorkbenchOwnerError("SOURCE_CHECK_BINDING_CHANGED", 409)
        docs = source_revision["content"]["documents"]
        if len(docs) != 1 or len(docs[0]["chunks"]) != 1:
            raise WorkbenchOwnerError("SOURCE_CHECK_SINGLE_DOCUMENT_REQUIRED", 409)
        source = json.loads(docs[0]["chunks"][0]["content"])
        if (
            source.get("synthetic") is not True
            or canonical_digest(source) != binding.sourceDigest
            or source["snapshot"]["sourceBytesSha256"] != binding.csvDigest
        ):
            raise WorkbenchOwnerError("SOURCE_CHECK_SOURCE_DIGEST_MISMATCH", 409)
        projected = service.invoke_mcp(
            scope,
            binding.mcp.resource_id,
            call.context.principal_id,
            spec.expectedVersion,
            binding.selectionId,
            binding.toolName,
            "ALLOW_BOUNDED_MCP_INVOCATION",
            {"sourceDigest": binding.sourceDigest},
            3,
        )
        invocation = projected["invocation"]
        matched = False
        actual = None
        if invocation["status"] == "SUCCEEDED":
            try:
                result = invocation["result"]
                actual = json.loads(result["content"][0]["text"])
                matched = (
                    result.get("isError", False) is False
                    and actual["synthetic"] is True
                    and actual["sourceSnapshot"]
                    == binding.source.model_dump(mode="json")
                    and actual["sourceDigest"] == binding.sourceDigest
                    and actual["csvDigest"] == binding.csvDigest
                    and actual["rows"] == source["snapshot"]["rows"]
                )
            except (KeyError, TypeError, ValueError):
                pass
        receipt = {
            "schemaVersion": SCHEMA,
            "requestKey": key,
            "executionDigest": view["digest"],
            "source": binding.source.model_dump(mode="json"),
            "mcp": binding.mcp.model_dump(mode="json"),
            "policyId": self.policy.policyId,
            "policyDigest": canonical_digest(self.policy.model_dump(mode="json")),
            "subject": call.context.principal_id,
            "phase": "POST_RESULT_SOURCE_VERIFICATION",
            "state": "MATCHED" if matched else "UNDETERMINED",
            "invocation": invocation,
            "actualSource": actual if matched else None,
            "originalRunChanged": False,
            "executionStarted": False,
            "modelCalls": 0,
            "createdAt": datetime.now(UTC).isoformat(),
        }
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                call.context.principal_id,
                storage_key,
                digest,
                Jsonb(receipt),
            ),
        )
        return receipt

    def __call__(self, call):
        try:
            view = self.saved(call)
            if call.operation == "READ_EXECUTION_SOURCE_REVIEW":
                return self.review(call, view)
            if call.operation == "SEARCH_EXECUTION_ORIGINAL_TEXT":
                return self.search(call, view)
            return self.check(call, view)
        except KnowledgeNotFound as exc:
            raise WorkbenchOwnerError("REVIEW_SOURCE_UNAVAILABLE", 404) from exc
        except EmployeeDefinitionError as exc:
            raise WorkbenchOwnerError("REVIEW_EMPLOYEE_UNAVAILABLE", 404) from exc
        except json.JSONDecodeError as exc:
            raise WorkbenchOwnerError("SOURCE_CHECK_DOCUMENT_INVALID", 409) from exc
        except SkillMcpFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc


def operations(services, coordinator=None, policy=None, *, sales_v2_candidate=False):
    handler = ExecutionSourceReview(
        services, coordinator, policy, sales_v2_candidate=sales_v2_candidate
    )
    path = PREFIX + "/prepared-executions/{digest}"
    return (
        WorkbenchOperation(
            "READ_EXECUTION_SOURCE_REVIEW",
            "GET",
            path + "/source-review",
            None,
            None,
            grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "SEARCH_EXECUTION_ORIGINAL_TEXT",
            "GET",
            path + "/original-text",
            None,
            Query,
            grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "VERIFY_EXECUTION_SOURCE",
            "POST",
            path + "/source-checks",
            Check,
            None,
            grant("READ"),
            handler,
        ),
        WorkbenchOperation(
            "READ_EXECUTION_SOURCE_CHECK",
            "GET",
            path + "/source-checks/by-key/{key}",
            None,
            None,
            grant("READ"),
            handler,
        ),
    )
