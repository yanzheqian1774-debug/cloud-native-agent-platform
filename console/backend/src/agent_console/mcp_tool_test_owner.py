# ruff: noqa: E501 -- Exact scoped SQL and bounded policy predicates.
"""One-use published tool testing; durable claim precedes any transport attempt."""

import json
import secrets
from datetime import timedelta

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from . import mcp_tool_test_postgres as store
from .authority_contracts import AuthenticationSource, AuthorityError, ExactGrant
from .definition_authority import canonical_digest as resource_digest
from .execution_preparation import ExecutionPreparationError
from .grant_administration_application import GrantDecisionCommand, GrantRequestCommand
from .knowledge_pack import canonical_digest as knowledge_digest
from .mcp_tool_test_policy import ToolBinding, ToolTestPolicy, require
from .prepared_execution_resources import published
from .resource_automation import bound_grants
from .resource_use_domain import canonical_digest
from .skill_mcp_service import SkillMcpService
from .skill_mcp_transport import (
    McpTransportFailure,
    StreamableHttpMcpClient,
    redact,
    request_selected_tool,
)
from .skill_resource_testing import schema_check
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_resources import bind_service, reference


class TestCommand(BaseModel):
    __test__ = False
    model_config = ConfigDict(extra="forbid")
    commandKey: str = Field(min_length=8, max_length=120, pattern=r"^[A-Za-z0-9:_-]+$")
    bindingDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    input: dict


def read_grant(binding):
    return ExactGrant(
        "SKILL",
        "READ_RESOURCE",
        reference("mcp", binding.mcp.resource_id, binding.mcp.revision_id),
    )


class ToolTestOwner:
    def __init__(self, path, manager, authorizer):
        self.path, self.manager, self.authorizer = path, manager, authorizer
        self.grants = manager.grants

    def policy(self):
        return ToolTestPolicy.load(self.path)

    def binding(self, context, digest):
        require(
            context.authentication_source == AuthenticationSource.BROWSER_SESSION,
            "BROWSER_REQUIRED",
        )
        return self.policy().binding(context, digest, self.grants.clock())

    @staticmethod
    def principal(context):
        return OwnerPrincipal(
            context.principal_id, context.scope.tenant_id, context.scope.security_domain
        )

    def exact(self, call, b):
        """Current rights plus resource share lock fence lifecycle changes during send."""
        p = self.principal(call.context)
        call.authority.require(p, *tuple_grant(read_grant(b)))
        call.authority.require(
            p,
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", b.source.resource_id, b.source.revision_id),
        )
        require(self.manager.owned(call, "mcp", b.mcp.resource_id), "NOT_OWNED")
        row = call.connection.execute(
            "SELECT record FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind='mcp' AND resource_id=%s FOR SHARE",
            (b.namespace, b.securityDomain, b.mcp.resource_id),
        ).fetchone()
        require(row is not None, "RESOURCE_NOT_FOUND")
        record = row["record"]
        require(
            record["enabled"]
            and not record["archived"]
            and record["publishedRevisionId"] == b.mcp.revision_id,
            "PUBLISHED_HEAD_CHANGED",
        )
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == b.mcp.revision_id),
            None,
        )
        require(
            revision
            and revision["state"] == "PUBLISHED"
            and revision["digest"] == b.mcp.digest
            and SkillMcpService._digest(record, revision) == b.mcp.digest,
            "PUBLISHED_REFERENCE_CHANGED",
        )
        content = revision["content"]
        require(
            content.get("endpoint") == b.endpoint
            and content.get("sideEffect") == "READ"
            and not content.get("secretReference"),
            "ENDPOINT_OR_EFFECT_CHANGED",
        )
        selection = next(
            (s for s in record["toolSelections"] if s["selectionId"] == b.selectionId),
            None,
        )
        snapshot = next(
            (
                s
                for s in record["discoverySnapshots"]
                if s["snapshotId"] == b.snapshotId
            ),
            None,
        )
        require(
            selection
            and snapshot
            and selection["snapshotId"] == b.snapshotId
            and b.toolName in selection["toolNames"],
            "SELECTION_CHANGED",
        )
        for item in (selection, snapshot):
            require(
                item.get("revisionId") == b.mcp.revision_id
                and item.get("revisionDigest") == b.mcp.digest,
                "SELECTION_SOURCE_CHANGED",
            )
        require(
            snapshot["digest"] == b.snapshotDigest
            and resource_digest(snapshot["catalog"], domain="mcp-discovery-snapshot-v1")
            == b.snapshotDigest,
            "CATALOG_CHANGED",
        )
        tools = [t for t in snapshot["catalog"]["tools"] if t.get("name") == b.toolName]
        require(
            len(tools) == 1 and tools[0].get("inputSchema") == b.inputSchema,
            "SCHEMA_CHANGED",
        )
        schema_check(b.arguments, b.inputSchema, "MCP_TOOL_TEST_INPUT_INVALID")
        # Explicit approved arguments, not annotations, bound to actual published source.
        require(
            b.arguments == {"sourceDigest": b.sourceContentDigest},
            "SOURCE_ARGUMENT_REQUIRED",
        )
        service = bind_service(self.manager.services["knowledge"], call.connection)
        scope = service.scope(b.namespace, b.securityDomain)
        # Same transaction and row lock as the transport; original lifecycle
        # UPDATE/purge cannot change availability between this check and send.
        try:
            published(call.connection, scope, "KNOWLEDGE", b.source)
        except ExecutionPreparationError as exc:
            raise AuthorityError("MCP_TOOL_TEST_SOURCE_CHANGED") from exc
        row = call.connection.execute(
            "SELECT namespace,security_domain,knowledge_id,aggregate_version,record FROM knowledge_operation.knowledge WHERE namespace=%s AND security_domain=%s AND knowledge_id=%s FOR SHARE",
            (b.namespace, b.securityDomain, b.source.resource_id),
        ).fetchone()
        require(row, "SOURCE_CHANGED")
        source = row["record"]
        require(
            source.get("namespace") == row["namespace"] == b.namespace
            and source.get("securityDomain")
            == row["security_domain"]
            == b.securityDomain
            and source.get("knowledgeId") == row["knowledge_id"] == b.source.resource_id
            and source.get("aggregateVersion") == row["aggregate_version"]
            and source.get("enabled", True) is True
            and not source.get("archived")
            and not source.get("purge"),
            "SOURCE_CHANGED",
        )
        revisions = [
            r for r in source["revisions"] if r["revisionId"] == b.source.revision_id
        ]
        require(len(revisions) == 1, "SOURCE_CHANGED")
        rev = revisions[0]
        semantic = {
            "scope": {"namespace": b.namespace, "securityDomain": b.securityDomain},
            "content": rev["content"],
        }
        if rev.get("predecessorRevisionId") is not None:
            semantic["predecessorRevisionId"] = rev["predecessorRevisionId"]
        require(
            knowledge_digest(semantic, domain="knowledge-revision.v1")
            == b.source.digest,
            "SOURCE_CHANGED",
        )
        docs = rev["content"].get("documents", [])
        require(
            len(docs) == 1 and len(docs[0].get("chunks", [])) == 1,
            "SOURCE_CONTENT_INVALID",
        )
        try:
            value = json.loads(docs[0]["chunks"][0]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise AuthorityError("MCP_TOOL_TEST_SOURCE_CONTENT_INVALID") from exc
        require(
            value.get("synthetic") is True
            and canonical_digest(value) == b.sourceContentDigest,
            "SOURCE_DIGEST_CHANGED",
        )
        self.manager.safe_content("mcp", {"endpoint": b.endpoint, "input": b.arguments})
        return record

    def prepare(self, call):
        spec = TestCommand.model_validate(call.payload)
        b = self.binding(call.context, spec.bindingDigest)
        require(
            call.path["identity"] == b.mcp.resource_id and spec.input == b.arguments,
            "INPUT_OR_RESOURCE_CHANGED",
        )
        self.exact(call, b)
        store.lock(call.connection, call.context, b.digest)
        old = store.read(call.connection, call.context, spec.commandKey)
        request = {
            "scope": list(store.scope(call.context)),
            "commandKey": spec.commandKey,
            "bindingDigest": b.digest,
            "binding": b.model_dump(mode="json"),
            "input": spec.input,
            "policyDigest": self.policy().digest,
        }
        if old:
            require(old["request"] == request, "KEY_CONFLICT")
            return self.projection(old)
        existing = call.connection.execute(
            "SELECT command_key FROM authorization_admin.mcp_tool_test_requests WHERE namespace=%s AND security_domain=%s AND subject_id=%s AND binding_digest=%s",
            (*store.scope(call.context), b.digest),
        ).fetchall()
        for item in existing:
            previous = store.read(call.connection, call.context, item["command_key"])
            require(
                self.projection(previous)["state"] in {"SUCCEEDED", "TOOL_FAILED"},
                "UNRESOLVED_TEST_EXISTS",
            )
        call.connection.execute(
            "INSERT INTO authorization_admin.mcp_tool_test_requests(namespace,security_domain,subject_id,command_key,binding_digest,request_digest,request) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                *store.scope(call.context),
                spec.commandKey,
                b.digest,
                canonical_digest(request),
                Jsonb(request),
            ),
        )
        return self.projection(
            store.read(call.connection, call.context, spec.commandKey)
        )

    def claim(self, call):
        row = store.read(call.connection, call.context, call.payload["commandKey"])
        require(row is not None, "REQUEST_NOT_FOUND")
        b = self.binding(call.context, row["binding_digest"])
        require(call.path["identity"] == b.mcp.resource_id, "RESOURCE_CHANGED")
        self.exact(call, b)
        store.lock(call.connection, call.context, b.digest)
        row = store.read(call.connection, call.context, row["command_key"])
        if row["facts"]:
            return {"receipt": self.projection(row), "ticket": None}
        policy = self.policy()
        require(row["request"]["policyDigest"] == policy.digest, "POLICY_CHANGED")
        issuer = policy.authenticate(self.grants, call.context)
        require(
            issuer.principal_id != call.context.principal_id,
            "INDEPENDENT_ISSUER_REQUIRED",
        )
        if self.grants.authorization.has_dynamic_revocation(
            call.context,
            b.grant,
            now=self.grants.clock(),
            recovery_epoch=self.grants.recovery_epoch,
        ):
            raise AuthorityError("MCP_TOOL_TEST_PERMISSION_REVOKED")
        grants = bound_grants(self.grants, call.connection)
        request = grants.submit_request(
            call.context,
            GrantRequestCommand(
                "MCP_TOOL_TEST",
                (b.grant,),
                "mcp-test-request:"
                + canonical_digest(
                    [*store.scope(call.context), row["command_key"], b.digest]
                ),
            ),
        )
        expiry = min(
            b.expiresAt, request.created_at + timedelta(seconds=policy.grantTTLSeconds)
        )
        require(expiry > grants.clock(), "AUTHORIZATION_EXPIRED")
        decision = grants.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                True,
                "ASSIGNED_BUSINESS_DUTY",
                "POLICY",
                "mcp-tool-test:"
                + policy.policyId
                + ":"
                + policy.policyVersion
                + ":"
                + policy.digest,
                None,
                expiry,
                "mcp-test-decision:" + request.request_id,
                expected_version=1,
            ),
        )
        call.authority.require(self.principal(call.context), *tuple_grant(b.grant))
        ticket = secrets.token_hex(32)
        store.append(
            call.connection,
            call.context,
            row["command_key"],
            "DISPATCH_CLAIM",
            {
                "ticketDigest": canonical_digest(ticket),
                "decisionId": decision.decision_id,
                "policyDigest": policy.digest,
            },
        )
        return {
            "receipt": self.projection(
                store.read(call.connection, call.context, row["command_key"])
            ),
            "ticket": ticket,
        }

    def transport(self, call, ticket):
        key = call.payload["commandKey"]
        row = store.read(call.connection, call.context, key)
        require(row is not None, "REQUEST_NOT_FOUND")
        b = self.binding(call.context, row["binding_digest"])
        self.exact(call, b)
        store.lock(call.connection, call.context, b.digest)
        row = store.read(call.connection, call.context, key)
        require(
            len(row["facts"]) == 1
            and row["facts"][0]["kind"] == "DISPATCH_CLAIM"
            and row["facts"][0]["fact"]["ticketDigest"] == canonical_digest(ticket),
            "DISPATCH_TICKET_INVALID",
        )
        require(
            self.policy().digest == row["request"]["policyDigest"], "POLICY_CHANGED"
        )
        call.authority.require(self.principal(call.context), *tuple_grant(b.grant))
        try:
            result = call_mcp_tool(
                b.endpoint, b.toolName, b.arguments, self.policy().timeoutSeconds
            )
        except McpTransportFailure:
            return {"state": "UNKNOWN", "reasonCode": "MCP_RESPONSE_NOT_CONFIRMED"}
        if (
            "isError" in result and not isinstance(result["isError"], bool)
        ) or not isinstance(result.get("content"), list):
            return {"state": "UNKNOWN", "reasonCode": "MCP_RESPONSE_NOT_CONFIRMED"}
        return {
            "state": "TOOL_FAILED" if result.get("isError") is True else "SUCCEEDED",
            "result": redact(result),
        }

    def finalize(self, context, key, ticket, result):
        # Internal ticket only. Logout after response must not discard transport facts.
        with self.authorizer.repository.connection_scope() as c:
            row = store.read(c, context, key)
            require(row is not None, "REQUEST_NOT_FOUND")
            store.lock(c, context, row["binding_digest"])
            row = store.read(c, context, key)
            require(
                row["facts"]
                and row["facts"][0]["fact"]["ticketDigest"] == canonical_digest(ticket),
                "DISPATCH_TICKET_INVALID",
            )
            if len(row["facts"]) == 1:
                store.append(c, context, key, "RESULT", result)
            else:
                require(
                    store.payload(row["facts"][1]["fact"]) == result, "RESULT_CONFLICT"
                )
            return self.projection(store.read(c, context, key))

    def read(self, call):
        row = store.read(call.connection, call.context, call.path["key"])
        if not row:
            raise WorkbenchOwnerError("MCP_TOOL_TEST_NOT_FOUND", 404)
        b = ToolBinding.model_validate(row["request"]["binding"])
        require(call.path["identity"] == b.mcp.resource_id, "RESOURCE_CHANGED")
        call.authority.require(
            self.principal(call.context), *tuple_grant(read_grant(b))
        )
        return self.projection(row)

    @staticmethod
    def projection(row):
        result = next((f["fact"] for f in row["facts"] if f["kind"] == "RESULT"), None)
        return {
            "commandKey": row["command_key"],
            "bindingDigest": row["binding_digest"],
            "publishedReference": row["request"]["binding"]["mcp"],
            "state": result["state"]
            if result
            else ("UNKNOWN" if row["facts"] else "PREPARED"),
            "result": store.payload(result) if result else None,
            "retryPermitted": False,
            "modelCalls": 0,
        }


def tuple_grant(grant):
    return grant.owner, grant.action, grant.exact_resource


def call_mcp_tool(endpoint, tool, inputs, timeout):
    client = StreamableHttpMcpClient(endpoint, timeout=timeout)
    initialized = client.initialize()
    return request_selected_tool(
        client, tool, inputs, session_id=initialized.session_id
    )
