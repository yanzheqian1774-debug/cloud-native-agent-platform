# ruff: noqa: E501 -- Parameterized owner SQL.
"""Trusted authoring adapter; existing Skill/MCP owner, current exact policy grants."""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .authority_contracts import AuthorityError, ExactGrant
from .resource_automation import ResourceAutomation
from .resource_automation_policy import AutomationPolicy
from .resource_use_domain import canonical_digest
from .skill_mcp_repository import SkillMcpNotFound
from .skill_mcp_schemas import ResourceContent
from .skill_mcp_service import SkillMcpFailure
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from .workbench_prepared_resources import bind_service, reference


def target(kind, identity):
    if kind not in {"skill", "mcp"}:
        raise WorkbenchOwnerError("RESOURCE_KIND_INVALID", 422)
    return "skill-invocation:resource-management:" + kind + ":" + identity


class ManagementScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    namespace: str
    securityDomain: str
    subject: str
    kinds: tuple[Literal["skill", "mcp"], ...]
    expiresAt: datetime


class ManagementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["resource-management-policy.v1"] = (
        "resource-management-policy.v1"
    )
    enabled: bool = False
    policyId: str
    policyVersion: str
    issuer: str
    credentialPath: Path
    workScopes: tuple[ManagementScope, ...]
    grantTTLSeconds: int = Field(default=3600, ge=60, le=3600)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    def authenticate(self, grants, subject):
        return AutomationPolicy.authenticate(self, grants, subject)

    def work(self, subject, kind, now):
        matches = [
            w
            for w in self.workScopes
            if w.namespace == subject.scope.tenant_id
            and w.securityDomain == subject.scope.security_domain
            and w.subject == subject.principal_id
            and kind in w.kinds
            and w.expiresAt.tzinfo
            and w.expiresAt > now
        ]
        if len(matches) != 1:
            raise AuthorityError("RESOURCE_MANAGEMENT_SCOPE_DENIED")
        return matches[0]


class ManagementCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal[
        "batch-import",
        "adopt-prepared",
        "test",
        "publish-tested",
        "create",
        "import",
        "edit",
        "successor",
        "validate",
        "publish",
        "health",
        "discover",
        "select-tools",
        "disable",
        "enable",
        "deprecate",
        "access",
    ]
    commandKey: str = Field(min_length=8, max_length=120)
    identity: str | None = None
    expectedVersion: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    content: ResourceContent | None = None
    manifest: dict | None = None
    manifests: list[dict] | None = Field(default=None, min_length=1, max_length=100)
    previewDigest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    preparedCommandKey: str | None = Field(default=None, min_length=8, max_length=120)
    operation: str | None = Field(default=None, max_length=200)
    testName: str | None = Field(default=None, min_length=1, max_length=120)
    testInput: dict | None = None
    expectedOutput: dict | None = None
    comparison: Literal["exact", "subset"] = "exact"
    snapshotId: str | None = None
    toolNames: list[str] = Field(default_factory=list, max_length=128)


class ManagementTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if (
            connection is None
            or grant.owner != "SKILL"
            or grant.action not in {"CREATE_RESOURCE", "MANAGE_RESOURCE", "CONNECT_MCP"}
        ):
            return False
        for kind in ["skill", "mcp"]:
            if grant.action == "CREATE_RESOURCE":
                if grant.exact_resource == target(kind, "collection"):
                    return True
                continue
            if grant.action == "CONNECT_MCP" and kind != "mcp":
                continue
            if connection.execute(
                "SELECT 1 FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind=%s AND %s || resource_id=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    kind,
                    target(kind, ""),
                    grant.exact_resource,
                ),
            ).fetchone():
                return True
        return False


class ResourceManagement:
    def __init__(
        self,
        services,
        policy,
        grants,
        *,
        sales_v2_candidate=False,
        prepared_handoff_enabled=False,
    ):
        self.services, self.policy, self.grants = services, policy, grants
        self.sales_v2_candidate = sales_v2_candidate
        self.prepared_handoff_enabled = prepared_handoff_enabled
        self.automation = SimpleNamespace(policy=policy, grants=grants)

    def authorize(self, call, members, key, work, issuer):
        from .development_administrator import for_call

        if for_call(call):
            from .resource_policy_contract import DevelopmentAdministratorReview

            return DevelopmentAdministratorReview(
                call.context.principal_id,
                call.policy_generation,
                canonical_digest(
                    [key, [(g.owner, g.action, g.exact_resource) for g in members]]
                ),
            )
        return ResourceAutomation.decide(
            self.automation,
            call,
            members,
            key,
            work,
            issuer,
            purpose="RESOURCE_MANAGEMENT",
        )

    def scope(self, context, kind):
        from .development_administrator import for_service

        if for_service(self.grants, context):
            return context, None
        issuer = self.policy.authenticate(self.grants, context)
        work = self.policy.work(context, kind, self.grants.clock())
        return issuer, work

    def owned(self, call, kind, identity):
        from .development_administrator import for_call

        if for_call(call):
            return True
        rows = call.connection.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND result->>'schemaVersion'='resource-management-receipt.v1' AND result->>'kind'=%s AND result->>'identity'=%s AND result->>'action' IN ('create','import','adopt-prepared') LIMIT 201",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                call.context.principal_id,
                kind,
                identity,
            ),
        ).fetchall()
        if len(rows) > 200:
            return False
        for row in rows:
            result = row["result"]
            if result["action"] in {"create", "import"}:
                return True
            if kind == "skill":
                from .prepared_skill_handoff import read_handoff

                handoff = read_handoff(
                    call.connection,
                    call.context,
                    identity,
                    result.get("preparedCommandKey"),
                )
                if (
                    handoff is not None
                    and result.get("preparedSuccessor") == handoff["draft"]
                    and result.get("executionStarted") is False
                    and result.get("modelCalls") == 0
                    and result.get("credentialMaterial") == "NOT_INCLUDED"
                ):
                    decision = call.connection.execute(
                        "SELECT 1 FROM authorization_admin.grant_decisions d WHERE d.decision_id=%s AND d.approved AND d.basis_type='POLICY' AND d.issuer_principal_id=%s AND EXISTS(SELECT 1 FROM authorization_admin.grants g WHERE g.decision_id=d.decision_id AND g.subject_principal_id=%s AND g.tenant_id=%s AND g.security_domain=%s AND g.owner='SKILL' AND g.action='MANAGE_RESOURCE' AND g.exact_resource=%s)",
                        (
                            result.get("policyDecisionId"),
                            result.get("policyIssuer"),
                            call.context.principal_id,
                            call.context.scope.tenant_id,
                            call.context.scope.security_domain,
                            target(kind, identity),
                        ),
                    ).fetchone()
                    if decision is not None:
                        return True
        return False

    def handle(self, call):
        kind = call.path["kind"]
        issuer, work = self.scope(call.context, kind)
        command = ManagementCommand.model_validate(call.payload)
        key = "resource-management:" + command.commandKey
        digest = canonical_digest([kind, call.payload])
        ns, domain = call.context.scope.tenant_id, call.context.scope.security_domain
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (canonical_digest([ns, domain, call.context.principal_id, key]),),
        )
        old = call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (ns, domain, call.context.principal_id, key),
        ).fetchone()
        if old:
            if old["digest"] != digest:
                raise WorkbenchOwnerError("RESOURCE_COMMAND_CONFLICT", 409)
            for identity in old["result"].get(
                "identities", [old["result"].get("identity")]
            ):
                call.authority.require(
                    OwnerPrincipal(call.context.principal_id, ns, domain),
                    "SKILL",
                    "MANAGE_RESOURCE",
                    target(kind, identity),
                )
            return old["result"]
        if command.action == "batch-import":
            return self.import_batch(call, command, key, digest, issuer, work)
        service = bind_service(self.services[kind], call.connection)
        scope = service.scope(ns, domain)
        actor = call.context.principal_id
        identity = command.identity
        action = (
            "CREATE_RESOURCE"
            if command.action in {"create", "import"}
            else "CONNECT_MCP"
            if command.action in {"health", "discover", "select-tools"}
            else "MANAGE_RESOURCE"
        )
        handoff = None
        if command.action == "adopt-prepared":
            if not self.prepared_handoff_enabled:
                raise WorkbenchOwnerError("PREPARED_SKILL_HANDOFF_DISABLED", 403)
            from .prepared_skill_handoff import read_handoff

            if kind != "skill" or not identity:
                raise WorkbenchOwnerError("PREPARED_SKILL_HANDOFF_REQUIRED", 422)
            handoff = read_handoff(
                call.connection, call.context, identity, command.preparedCommandKey
            )
            if handoff is None:
                raise WorkbenchOwnerError("PREPARED_SKILL_HANDOFF_NOT_FOUND", 404)
            # A prepared receipt alone never self-authorizes adoption. Require
            # the original current exact management and predecessor-read grants.
            original = OwnerPrincipal(actor, ns, domain)
            call.authority.require(
                original, "SKILL", "MANAGE_RESOURCE", target(kind, identity)
            )
            call.authority.require(
                original,
                "SKILL",
                "READ_RESOURCE",
                reference(kind, identity, handoff["predecessor"]["revision_id"]),
            )
        elif command.preparedCommandKey is not None:
            raise WorkbenchOwnerError("PREPARED_SKILL_HANDOFF_ACTION_REQUIRED", 422)
        elif action != "CREATE_RESOURCE" and (
            not identity or not self.owned(call, kind, identity)
        ):
            raise WorkbenchOwnerError("RESOURCE_MANAGEMENT_NOT_FOUND", 404)
        if action == "CONNECT_MCP" and kind != "mcp":
            raise WorkbenchOwnerError("MCP_ONLY", 422)
        g = ExactGrant(
            "SKILL",
            action,
            target(kind, "collection" if action == "CREATE_RESOURCE" else identity),
        )
        proof = self.authorize(call, [g], key + ":authorize", work, issuer)
        principal = OwnerPrincipal(actor, ns, domain)
        call.authority.require(principal, g.owner, g.action, g.exact_resource)
        content = None
        if command.content is not None:
            content = command.content.model_dump(exclude_unset=True)
        if command.action == "import":
            m = command.manifest
            if (
                not m
                or set(m)
                - {
                    "manifestVersion",
                    "kind",
                    "name",
                    "content",
                    "sourceRevisionId",
                    "sourceDigest",
                    "credentialMaterial",
                }
                or m.get("manifestVersion") != "skill-mcp-workbench/v1"
                or m.get("kind") != kind
                or m.get("credentialMaterial", "NOT_INCLUDED") != "NOT_INCLUDED"
            ):
                raise WorkbenchOwnerError("MANIFEST_BOUNDARY_INVALID", 422)
            try:
                content = ResourceContent.model_validate(m.get("content")).model_dump(
                    exclude_unset=True
                )
            except ValidationError as exc:
                raise WorkbenchOwnerError("MANIFEST_CONTENT_INVALID", 422) from exc
            name = command.name or m.get("name")
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise WorkbenchOwnerError("MANIFEST_NAME_INVALID", 422)
        else:
            name = command.name
        if content is not None:
            self.safe_content(kind, content)
        try:
            if command.action in {"create", "import"}:
                if not name or not content:
                    raise WorkbenchOwnerError("RESOURCE_CONTENT_REQUIRED", 422)
                record = service.create(scope, kind, actor, name, content)
                identity = record["resourceId"]
            else:
                record = service.repository.get(scope, kind, identity)
                # Access does not mutate the resource. A caller whose exact
                # management grant expired cannot read its aggregate version;
                # ownership and the current policy were checked above. Explicit
                # versions and every mutating action keep optimistic locking.
                if command.expectedVersion != record["aggregateVersion"] and (
                    command.action != "access" or command.expectedVersion is not None
                ):
                    raise WorkbenchOwnerError("RESOURCE_VERSION_STALE", 409)
                if handoff is not None and (
                    record["aggregateVersion"] != handoff["aggregateVersion"]
                    or record["currentDraftRevisionId"]
                    != handoff["draft"]["revision_id"]
                    or record["publishedRevisionId"]
                    != handoff["predecessor"]["revision_id"]
                ):
                    raise WorkbenchOwnerError(
                        "PREPARED_SKILL_HANDOFF_TARGET_STALE", 409
                    )
                args = (scope, kind, identity, actor, command.expectedVersion)
                if command.action == "edit":
                    service.edit(*args, content or {})
                elif command.action == "successor":
                    service.successor(*args)
                elif command.action == "validate":
                    service.validate(*args)
                elif command.action == "test":
                    if (
                        kind != "skill"
                        or not command.operation
                        or not command.testName
                        or command.testInput is None
                        or command.expectedOutput is None
                    ):
                        raise WorkbenchOwnerError("TEST_CASE_REQUIRED", 422)
                    from .resource_automation_validation import executor_registry
                    from .skill_resource_testing import run as run_test

                    self.safe_content(
                        "skill",
                        {
                            "input": command.testInput,
                            "expected": command.expectedOutput,
                        },
                    )
                    run_test(
                        service,
                        scope,
                        identity,
                        actor,
                        command.expectedVersion,
                        operation=command.operation,
                        name=command.testName,
                        inputs=command.testInput,
                        expected_output=command.expectedOutput,
                        comparison=command.comparison,
                        executor_registry=executor_registry(
                            sales_v2_candidate=self.sales_v2_candidate
                        ),
                    )
                elif command.action in {"publish", "publish-tested"}:
                    if command.action == "publish-tested":
                        from .skill_resource_testing import coverage

                        if kind != "skill":
                            raise WorkbenchOwnerError("SKILL_ONLY", 422)
                        candidate = next(
                            (
                                r
                                for r in record["revisions"]
                                if r["revisionId"] == record["currentDraftRevisionId"]
                            ),
                            None,
                        )
                        if (
                            candidate is None
                            or not coverage(record, candidate)["ready"]
                        ):
                            raise WorkbenchOwnerError(
                                "CURRENT_OPERATION_TESTS_REQUIRED", 409
                            )
                    if not record["currentDraftRevisionId"]:
                        raise WorkbenchOwnerError("RESOURCE_DRAFT_REQUIRED", 409)
                    from dataclasses import replace

                    from .workbench_prepared_resources import PreparedResourceOwner

                    revision = next(
                        r
                        for r in record["revisions"]
                        if r["revisionId"] == record["currentDraftRevisionId"]
                    )
                    members = [
                        ExactGrant(
                            "SKILL",
                            a,
                            reference(kind, identity, revision["revisionId"]),
                        )
                        for a in ["READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE"]
                    ]
                    review = self.authorize(
                        call, members, key + ":publish", work, issuer
                    )
                    PreparedResourceOwner(self.services).publish_policy(
                        replace(
                            call,
                            path={
                                "kind": kind,
                                "identity": identity,
                                "revision": revision["revisionId"],
                            },
                            payload={
                                "expectedVersion": command.expectedVersion,
                                "digest": revision["digest"],
                                "reason": "按已授权资源策略核验并发布",
                                "idempotencyKey": key,
                            },
                        ),
                        review,
                    )
                elif command.action in {"health", "discover"}:
                    revision = next(
                        r
                        for r in record["revisions"]
                        if r["revisionId"]
                        == (
                            record["currentDraftRevisionId"]
                            or record["publishedRevisionId"]
                        )
                    )
                    if revision["content"].get("secretReference"):
                        raise WorkbenchOwnerError(
                            "MCP_CREDENTIAL_RESOLVER_UNAVAILABLE", 422
                        )
                    getattr(service, command.action)(
                        scope, identity, actor, command.expectedVersion, 2
                    )
                elif command.action == "select-tools":
                    if (
                        not command.toolNames
                        or not record["discoverySnapshots"]
                        or command.snapshotId
                        != record["discoverySnapshots"][-1]["snapshotId"]
                    ):
                        raise WorkbenchOwnerError("LATEST_DISCOVERY_REQUIRED", 409)
                    current_revision = next(
                        r
                        for r in record["revisions"]
                        if r["revisionId"]
                        == (
                            record["currentDraftRevisionId"]
                            or record["publishedRevisionId"]
                        )
                    )
                    latest_snapshot = record["discoverySnapshots"][-1]
                    if (
                        latest_snapshot.get("revisionId")
                        != current_revision["revisionId"]
                        or latest_snapshot.get("revisionDigest")
                        != current_revision["digest"]
                    ):
                        raise WorkbenchOwnerError(
                            "CURRENT_REVISION_DISCOVERY_REQUIRED", 409
                        )
                    service.select_tools(
                        scope,
                        identity,
                        actor,
                        command.expectedVersion,
                        command.snapshotId,
                        command.toolNames,
                        "配置人员明确选择已发现工具",
                    )
                elif command.action in {"disable", "enable", "deprecate"}:
                    service.lifecycle(*args, command.action.upper(), "资源配置操作")
                elif command.action not in {"access", "adopt-prepared"}:
                    raise WorkbenchOwnerError("RESOURCE_ACTION_UNSUPPORTED", 422)
                record = service.repository.get(scope, kind, identity)
        except SkillMcpFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        members = [ExactGrant("SKILL", "MANAGE_RESOURCE", target(kind, identity))]
        members += [
            ExactGrant(
                "SKILL", "READ_RESOURCE", reference(kind, identity, r["revisionId"])
            )
            for r in record["revisions"]
        ]
        self.authorize(call, members, key + ":result-access", work, issuer)
        result = {
            "schemaVersion": "resource-management-receipt.v1",
            "kind": kind,
            "identity": identity,
            "action": command.action,
            "commandKey": command.commandKey,
            "aggregateVersion": record["aggregateVersion"],
            "policyIssuer": issuer.principal_id,
            "policyDecisionId": proof.decision_id,
            "resource": record,
            "executionStarted": False,
            "modelCalls": 0,
            "credentialMaterial": "NOT_INCLUDED",
        }
        if command.action == "adopt-prepared":
            result["preparedCommandKey"] = command.preparedCommandKey
            result["preparedSuccessor"] = handoff["draft"]
        if command.action == "publish-tested":
            from .skill_resource_testing import coverage

            published = next(
                r
                for r in record["revisions"]
                if r["revisionId"] == record["publishedRevisionId"]
            )
            result["publicationVerification"] = coverage(record, published)
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (ns, domain, actor, key, digest, Jsonb(result)),
        )
        return result

    def import_preview(self, call, manifests):
        from .resource_import import preview_manifests

        kind = call.path["kind"]
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        names = []
        for record in bind_service(
            self.services[kind], call.connection
        ).repository.list(
            self.services[kind].scope(principal.tenant_id, principal.security_domain),
            kind,
        ):
            # Older seeded records may omit authoring metadata. They cannot
            # contribute an authorized duplicate-name warning.
            if not record.get("resourceId") or not record.get("name"):
                continue
            try:
                call.authority.require(
                    principal,
                    "SKILL",
                    "MANAGE_RESOURCE",
                    target(kind, record["resourceId"]),
                )
            except AuthorityError:
                continue
            names.append(record["name"])
        return preview_manifests(manifests, kind, names)

    def import_batch(self, call, command, key, digest, issuer, work):
        from dataclasses import replace

        from .resource_import import preview_manifests

        kind = call.path["kind"]
        preview = preview_manifests(command.manifests, kind)
        if not preview["ready"] or preview["previewDigest"] != command.previewDigest:
            raise WorkbenchOwnerError("IMPORT_PREVIEW_INVALID_OR_CHANGED", 409)
        receipts = []
        for ordinal, manifest in enumerate(preview["manifests"]):
            receipts.append(
                self.handle(
                    replace(
                        call,
                        payload={
                            "action": "import",
                            "commandKey": "batch-item:"
                            + canonical_digest([key, ordinal]),
                            "manifest": manifest,
                        },
                    )
                )
            )
        result = {
            "schemaVersion": "resource-management-batch-receipt.v1",
            "action": "batch-import",
            "kind": kind,
            "commandKey": command.commandKey,
            "previewDigest": preview["previewDigest"],
            "identities": [r["identity"] for r in receipts],
            "resources": [r["resource"] for r in receipts],
            "importedRows": len(receipts),
            "policyIssuer": issuer.principal_id,
            "executionStarted": False,
            "modelCalls": 0,
            "credentialMaterial": "NOT_INCLUDED",
        }
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                call.context.principal_id,
                key,
                digest,
                Jsonb(result),
            ),
        )
        return result

    @staticmethod
    def safe_content(kind, content):
        import json
        from urllib.parse import urlsplit

        if kind == "mcp":
            endpoint = content.get("endpoint", "")
            p = urlsplit(endpoint)
            if p.username or p.password or p.query or p.fragment:
                raise WorkbenchOwnerError("MCP_ENDPOINT_CREDENTIALS_DENIED", 422)
            from .skill_mcp_transport import (
                McpTransportFailure,
                StreamableHttpMcpClient,
            )

            try:
                StreamableHttpMcpClient(endpoint)
            except McpTransportFailure as exc:
                raise WorkbenchOwnerError(str(exc), 422) from exc

        def visit(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if k.lower() in {
                        "authorization",
                        "password",
                        "token",
                        "api_key",
                        "apikey",
                        "cookie",
                        "secret",
                    }:
                        raise WorkbenchOwnerError("RESOURCE_INLINE_SECRET_DENIED", 422)
                    visit(v)
            elif isinstance(value, list):
                for v in value:
                    visit(v)

        visit(content)
        if len(json.dumps(content)) > 200000:
            raise WorkbenchOwnerError("RESOURCE_CONTENT_TOO_LARGE", 422)


def install_management(manager, authorizer):
    from fastapi import Request

    from .workbench_bff import PREFIX, WorkbenchBoundaryError

    def install(app, authenticate, require_csrf, policy):
        def run(request, kind, operation):
            if request.query_params:
                raise WorkbenchBoundaryError("REQUEST_INVALID", 422)
            with (
                authorizer.controller.protected_request() as generation,
                authorizer.repository.connection_scope() as connection,
            ):
                session, context = authenticate(request)
                if request.method != "GET":
                    require_csrf(request, session)
                manager.scope(context, kind)
                connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
                authority = AuthorizedOwnerAuthority(
                    authorizer, context, connection, generation.generation, ()
                )
                call = AuthorizedOwnerCall(
                    "RESOURCE_MANAGEMENT",
                    context,
                    connection,
                    {},
                    {"kind": kind},
                    {},
                    (),
                    authority,
                    generation.generation,
                    authorizer.controller.readiness.recovery_epoch,
                )
                try:
                    return {"result": operation(call)}
                except SkillMcpFailure as exc:
                    raise WorkbenchOwnerError(exc.reason, exc.status) from exc
                except SkillMcpNotFound as exc:
                    raise WorkbenchOwnerError("RESOURCE_NOT_FOUND", 404) from exc

        root = PREFIX + "/resource-management/{kind}"

        @app.get(root)
        def directory(request: Request, kind: Literal["skill", "mcp"]):
            def read(call):
                rows = call.connection.execute(
                    "SELECT DISTINCT result->>'identity' identity FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND result->>'schemaVersion'='resource-management-receipt.v1' AND result->>'kind'=%s AND result->>'action' IN ('create','import','adopt-prepared') ORDER BY identity LIMIT 200",
                    (
                        call.context.scope.tenant_id,
                        call.context.scope.security_domain,
                        call.context.principal_id,
                        kind,
                    ),
                ).fetchall()
                from .development_administrator import for_call

                if for_call(call):
                    rows = call.connection.execute(
                        "SELECT resource_id identity FROM skill_mcp_resource.resources WHERE namespace=%s AND security_domain=%s AND kind=%s ORDER BY resource_id",
                        (
                            call.context.scope.tenant_id,
                            call.context.scope.security_domain,
                            kind,
                        ),
                    ).fetchall()
                service = bind_service(manager.services[kind], call.connection)
                scope = service.scope(
                    call.context.scope.tenant_id, call.context.scope.security_domain
                )
                principal = OwnerPrincipal(
                    call.context.principal_id, scope.namespace, scope.security_domain
                )
                items = []
                for row in rows:
                    if not row["identity"] or not manager.owned(
                        call, kind, row["identity"]
                    ):
                        continue
                    try:
                        call.authority.require(
                            principal,
                            "SKILL",
                            "MANAGE_RESOURCE",
                            target(kind, row["identity"]),
                        )
                    except AuthorityError:
                        continue
                    items.append(service.repository.get(scope, kind, row["identity"]))
                return {
                    "kind": kind,
                    "items": items,
                    "subject": call.context.principal_id,
                    "scope": {
                        "tenantId": scope.namespace,
                        "securityDomain": scope.security_domain,
                    },
                    "enabled": True,
                    "credentialSupport": "REFERENCE_ONLY_NO_RESOLVER",
                    "connectionBoundary": "LOOPBACK_NO_AUTH",
                    "executionStarted": False,
                }

            return run(request, kind, read)

        @app.get(root + "/{identity}/impact")
        def impact(request: Request, kind: Literal["skill", "mcp"], identity: str):
            def read(call):
                from .skill_resource_testing import version_impact

                principal = OwnerPrincipal(
                    call.context.principal_id,
                    call.context.scope.tenant_id,
                    call.context.scope.security_domain,
                )
                call.authority.require(
                    principal, "SKILL", "MANAGE_RESOURCE", target(kind, identity)
                )
                if not manager.owned(call, kind, identity):
                    raise WorkbenchOwnerError("RESOURCE_MANAGEMENT_NOT_FOUND", 404)
                service = bind_service(manager.services[kind], call.connection)
                record = service.repository.get(
                    service.scope(principal.tenant_id, principal.security_domain),
                    kind,
                    identity,
                )
                for revision in record["revisions"]:
                    call.authority.require(
                        principal,
                        "SKILL",
                        "READ_RESOURCE",
                        reference(kind, identity, revision["revisionId"]),
                    )
                from .resource_dependency_impact import project

                summary = {
                    **version_impact(record),
                    "dependencies": project(call, kind, record),
                }
                uses = []
                rows = call.connection.execute(
                    "SELECT u.resource_use_id,u.resource_revision_id,u.resource_digest,p.digest preparation_digest,u.workflow_run_id,g.record->>'state' run_state FROM resource_use.uses u JOIN execution_authority.run_preparations p USING(namespace,security_domain,workflow_run_id) LEFT JOIN execution_authority.prepared_run_progress g USING(namespace,security_domain,workflow_run_id) WHERE u.namespace=%s AND u.security_domain=%s AND u.resource_id=%s AND u.resource_kind=%s ORDER BY u.resource_use_id LIMIT 201",
                    (
                        principal.tenant_id,
                        principal.security_domain,
                        identity,
                        "SKILL" if kind == "skill" else "MCP",
                    ),
                ).fetchall()
                for row in rows[:200]:
                    try:
                        call.authority.require(
                            principal,
                            "RESOURCE_USE",
                            "READ",
                            "resource-use:prepared:"
                            + row["preparation_digest"]
                            + ":"
                            + row["resource_use_id"],
                        )
                    except AuthorityError:
                        continue
                    use = dict(row)
                    try:
                        call.authority.require(
                            principal,
                            "EXECUTION",
                            "READ",
                            "governed-execution:prepared:" + row["preparation_digest"],
                        )
                    except AuthorityError:
                        use["run_state"] = None
                    uses.append(use)
                return {**summary, "authorizedUses": uses, "truncated": len(rows) > 200}

            return run(request, kind, read)

        @app.post(root + "/import-preview")
        async def preview(request: Request, kind: Literal["skill", "mcp"]):
            from urllib.parse import unquote

            from .resource_import import MAX_FILE, decode_file

            session, context = authenticate(request)
            require_csrf(request, session)
            manager.scope(context, kind)
            if (
                request.headers.get("content-type", "").split(";")[0]
                != "application/octet-stream"
            ):
                raise WorkbenchBoundaryError("IMPORT_CONTENT_TYPE_INVALID", 422)
            filename = unquote(request.headers.get("x-import-filename", ""))
            if (
                not filename
                or len(filename) > 200
                or "/" in filename
                or "\\" in filename
            ):
                raise WorkbenchBoundaryError("IMPORT_FILENAME_INVALID", 422)
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > MAX_FILE:
                    raise WorkbenchBoundaryError("IMPORT_FILE_SIZE_INVALID", 413)
            manifests = decode_file(filename, bytes(raw), kind)
            return run(
                request, kind, lambda call: manager.import_preview(call, manifests)
            )

        @app.post(root + "/commands")
        def command(
            request: Request, kind: Literal["skill", "mcp"], body: ManagementCommand
        ):
            from dataclasses import replace

            return run(
                request,
                kind,
                lambda call: manager.handle(
                    replace(
                        call,
                        payload=body.model_dump(
                            mode="json", exclude_none=True, exclude_unset=True
                        ),
                    )
                ),
            )

        @app.get(root + "/commands/{key}")
        def receipt(request: Request, kind: Literal["skill", "mcp"], key: str):
            def read(call):
                row = call.connection.execute(
                    "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
                    (
                        call.context.scope.tenant_id,
                        call.context.scope.security_domain,
                        call.context.principal_id,
                        "resource-management:" + key,
                    ),
                ).fetchone()
                if (
                    not row
                    or row["result"].get("schemaVersion")
                    not in {
                        "resource-management-receipt.v1",
                        "resource-management-batch-receipt.v1",
                    }
                    or row["result"]["kind"] != kind
                ):
                    raise WorkbenchOwnerError("RESOURCE_COMMAND_NOT_FOUND", 404)
                for identity in row["result"].get(
                    "identities", [row["result"].get("identity")]
                ):
                    call.authority.require(
                        OwnerPrincipal(
                            call.context.principal_id,
                            call.context.scope.tenant_id,
                            call.context.scope.security_domain,
                        ),
                        "SKILL",
                        "MANAGE_RESOURCE",
                        target(kind, identity),
                    )
                return row["result"]

            return run(request, kind, read)

    return install
