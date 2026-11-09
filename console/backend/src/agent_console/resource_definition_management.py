# ruff: noqa: E501 -- Exact owner SQL, no interpolated user identifiers.
"""Current-session maintenance of creator-owned Agent and Knowledge definitions.

No indexing, retrieval, invocation, execution or implicit policy-kind expansion.
"""

from dataclasses import replace
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import ConfigDict, Field, ValidationError

from .agent_binding_validation import (
    BindingResolution,
    BindingValidationFailure,
    validate_bindings,
)
from .agent_definition_repository import AgentDefinitionRepositoryError
from .agent_definition_schemas import DefinitionContent
from .agent_definition_service import AgentDefinitionFailure
from .authority_contracts import AuthorityError, ExactGrant
from .knowledge_lifecycle_service import KnowledgeLifecycleFailure
from .knowledge_repository import KnowledgeRepositoryError
from .knowledge_schemas import KnowledgeSourceInput
from .resource_management import ManagementPolicy, ManagementScope, ResourceManagement
from .resource_use_domain import canonical_digest
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from .workbench_prepared_resources import (
    OWNERS,
    TABLES,
    PreparedResourceOwner,
    bind_service,
    reference,
)

SCHEMA = "definition-management-receipt.v1"
LEDGER = "definition-management:"
Kind = Literal["agent", "knowledge"]


def target(kind, identity):
    if kind not in {"agent", "knowledge"}:
        raise WorkbenchOwnerError("DEFINITION_KIND_INVALID", 422)
    return (
        ("agent:" if kind == "agent" else "knowledge:")
        + "resource-management:"
        + identity
    )


class DefinitionScope(ManagementScope):
    kinds: tuple[Kind, ...]


class DefinitionPolicy(ManagementPolicy):
    schemaVersion: Literal["resource-definition-management-policy.v1"] = (
        "resource-definition-management-policy.v1"
    )
    workScopes: tuple[DefinitionScope, ...]


class AgentContent(DefinitionContent):
    model_config = ConfigDict(extra="forbid")


class SourceInput(KnowledgeSourceInput):
    model_config = ConfigDict(extra="forbid")


from pydantic import BaseModel  # noqa: E402


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["create", "edit", "successor", "validate", "publish", "access"]
    commandKey: str = Field(min_length=8, max_length=120)
    identity: str | None = Field(default=None, min_length=1, max_length=240)
    expectedVersion: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)


class AgentCommand(Command):
    content: AgentContent | None = None


class KnowledgeCommand(Command):
    source: SourceInput | None = None
    successorContent: str | None = Field(default=None, min_length=1, max_length=200000)


class DefinitionTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if connection is None or grant.action not in {
            "CREATE_RESOURCE",
            "MANAGE_RESOURCE",
        }:
            return False
        for kind in ("agent", "knowledge"):
            if grant.owner != OWNERS[kind]:
                continue
            if grant.action == "CREATE_RESOURCE":
                return grant.exact_resource == target(kind, "collection")
            table, col = TABLES[kind]
            return (
                connection.execute(
                    f"SELECT 1 FROM {table} WHERE namespace=%s AND security_domain=%s AND %s || {col}=%s",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        target(kind, ""),
                        grant.exact_resource,
                    ),
                ).fetchone()
                is not None
            )
        return False


class BindingResolver:
    """Existing binding port, exact caller rights and the caller's transaction."""

    def __init__(self, manager, call, bindings):
        self.manager, self.call, self.bindings = manager, call, bindings

    def resolve(self, scope, kind, identity):
        field = {
            "skill": "skills",
            "mcp": "mcpTools",
            "knowledge": "knowledge",
            "runtime-profile": "runtimeProfile",
        }.get(kind)
        declarations = self.bindings.get(field, []) if field else []
        if isinstance(declarations, dict):
            declarations = [declarations]
        refs = [r for r in declarations or [] if r.get("resourceId") == identity]
        if not refs or any(
            (r.get("revisionId"), r.get("digest"))
            != (refs[0].get("revisionId"), refs[0].get("digest"))
            for r in refs
        ):
            return None
        ref = refs[0]
        actual_kind = "runtime" if kind == "runtime-profile" else kind
        if actual_kind not in self.manager.services or not ref.get("revisionId"):
            return None
        p = self.manager.principal(self.call)
        self.call.authority.require(
            p,
            OWNERS[actual_kind],
            "READ_RESOURCE",
            reference(actual_kind, identity, ref["revisionId"]),
        )
        service = bind_service(self.manager.services[actual_kind], self.call.connection)
        owner_scope = service.scope(scope.namespace, scope.security_domain)
        record = service.repository.get(
            *(
                (owner_scope, actual_kind, identity)
                if actual_kind in {"skill", "mcp"}
                else (owner_scope, identity)
            )
        )
        revision = next(
            (
                r
                for r in record["revisions"]
                if r["revisionId"] == record.get("publishedRevisionId")
            ),
            None,
        )
        if not revision:
            return None
        selections = [
            s
            for s in record.get("toolSelections", [])
            if s.get("revisionId") == revision["revisionId"]
            and s.get("revisionDigest") == revision["digest"]
        ]
        return BindingResolution(
            identity,
            revision["revisionId"],
            revision["digest"].removeprefix("sha256:"),
            revision["state"] == "PUBLISHED",
            record.get("enabled", True) and not record.get("archived", False),
            record.get("lifecycleState") == "DEPRECATED",
            tools=tuple(selections[-1]["toolNames"]) if selections else (),
            snapshots=tuple(s["snapshotId"] for s in selections)
            + tuple(
                s["snapshotId"]
                for s in record.get("indexSnapshots", [])
                if actual_kind == "knowledge"
                and s.get("snapshotId") == record.get("activeIndexSnapshotId")
                and s.get("revisionId") == revision["revisionId"]
                and s.get("revisionDigest") == revision["digest"]
                and s.get("status") == "ACTIVE"
                and s.get("freshness") == "FRESH"
            ),
        )


class DefinitionManagement(ResourceManagement):
    @staticmethod
    def principal(call):
        return OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )

    def owned(self, call, kind, identity):
        from .development_administrator import for_call

        if for_call(call):
            return True
        return (
            call.connection.execute(
                "SELECT 1 FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND result->>'schemaVersion'=%s AND result->>'kind'=%s AND result->>'identity'=%s AND result->>'action'='create'",
                (
                    call.context.scope.tenant_id,
                    call.context.scope.security_domain,
                    call.context.principal_id,
                    SCHEMA,
                    kind,
                    identity,
                ),
            ).fetchone()
            is not None
        )

    def require_manage(self, call, kind, identity):
        call.authority.require(
            self.principal(call),
            OWNERS[kind],
            "MANAGE_RESOURCE",
            target(kind, identity),
        )
        if not self.owned(call, kind, identity):
            raise WorkbenchOwnerError("DEFINITION_MANAGEMENT_NOT_FOUND", 404)

    def receipt(self, call, kind, key):
        row = call.connection.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                call.context.principal_id,
                LEDGER + key,
            ),
        ).fetchone()
        if (
            not row
            or row["result"].get("schemaVersion") != SCHEMA
            or row["result"].get("kind") != kind
        ):
            raise WorkbenchOwnerError("RESOURCE_COMMAND_NOT_FOUND", 404)
        self.require_manage(call, kind, row["result"]["identity"])
        return row["result"]

    def directory(self, call):
        kind = call.path["kind"]
        rows = call.connection.execute(
            "SELECT DISTINCT result->>'identity' identity FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND result->>'schemaVersion'=%s AND result->>'kind'=%s AND result->>'action'='create' ORDER BY identity LIMIT 200",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                call.context.principal_id,
                SCHEMA,
                kind,
            ),
        ).fetchall()
        from .development_administrator import for_call

        if for_call(call):
            table, column = TABLES[kind]
            rows = call.connection.execute(
                f"SELECT {column} identity FROM {table} WHERE namespace=%s AND security_domain=%s ORDER BY {column}",
                (call.context.scope.tenant_id, call.context.scope.security_domain),
            ).fetchall()
        service = bind_service(self.services[kind], call.connection)
        p = self.principal(call)
        items = []
        for row in rows:
            try:
                self.require_manage(call, kind, row["identity"])
            except AuthorityError:
                continue
            items.append(
                service.repository.get(
                    service.scope(p.tenant_id, p.security_domain), row["identity"]
                )
            )
        return {
            "kind": kind,
            "items": items,
            "subject": p.principal_id,
            "scope": {"tenantId": p.tenant_id, "securityDomain": p.security_domain},
            "executionStarted": False,
            "indexingStarted": False,
            "modelCalls": 0,
            "truncated": len(rows) == 200,
        }

    def handle(self, call):
        kind = call.path["kind"]
        issuer, work = self.scope(call.context, kind)
        try:
            cmd = (
                AgentCommand if kind == "agent" else KnowledgeCommand
            ).model_validate(call.payload)
        except ValidationError as exc:
            raise WorkbenchOwnerError("DEFINITION_COMMAND_INVALID", 422) from exc
        if (
            (
                cmd.action == "create"
                and (
                    not cmd.name or not (cmd.content if kind == "agent" else cmd.source)
                )
            )
            or (cmd.action == "edit" and (kind != "agent" or not cmd.content))
            or (
                cmd.action == "successor"
                and kind == "knowledge"
                and not cmd.successorContent
            )
        ):
            raise WorkbenchOwnerError("DEFINITION_CONTENT_REQUIRED", 422)
        self.safe_content("agent", cmd.model_dump(mode="json", exclude_none=True))
        p = self.principal(call)
        key, digest = LEDGER + cmd.commandKey, canonical_digest([kind, call.payload])
        call.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (canonical_digest([p.tenant_id, p.security_domain, p.principal_id, key]),),
        )
        old = call.connection.execute(
            "SELECT digest,result FROM execution_authority.prepared_resource_commands WHERE namespace=%s AND security_domain=%s AND actor_id=%s AND command_key=%s",
            (p.tenant_id, p.security_domain, p.principal_id, key),
        ).fetchone()
        if old:
            if old["digest"] != digest:
                raise WorkbenchOwnerError("RESOURCE_COMMAND_CONFLICT", 409)
            return self.receipt(call, kind, cmd.commandKey)
        identity = cmd.identity
        if cmd.action != "create" and (
            not identity or not self.owned(call, kind, identity)
        ):
            raise WorkbenchOwnerError("DEFINITION_MANAGEMENT_NOT_FOUND", 404)
        grant = ExactGrant(
            OWNERS[kind],
            "CREATE_RESOURCE" if cmd.action == "create" else "MANAGE_RESOURCE",
            target(kind, "collection" if cmd.action == "create" else identity),
        )
        proof = self.authorize(call, [grant], key + ":authorize", work, issuer)
        call.authority.require(p, grant.owner, grant.action, grant.exact_resource)
        service = bind_service(self.services[kind], call.connection)
        scope = service.scope(p.tenant_id, p.security_domain)
        try:
            if cmd.action == "create":
                value = service.create(
                    scope,
                    p.principal_id,
                    cmd.name,
                    cmd.content.model_dump()
                    if kind == "agent"
                    else cmd.source.model_dump(),
                )
                record = value if kind == "agent" else value["knowledge"]
                identity = record["definitionId" if kind == "agent" else "knowledgeId"]
            else:
                record = service.repository.get(scope, identity)
                if cmd.expectedVersion != record["aggregateVersion"] and (
                    cmd.action != "access" or cmd.expectedVersion is not None
                ):
                    raise WorkbenchOwnerError("RESOURCE_VERSION_STALE", 409)
                args = (scope, identity, p.principal_id, cmd.expectedVersion)
                if kind == "agent":
                    revision = next(
                        r
                        for r in record["revisions"]
                        if r["revisionId"]
                        == (
                            record["currentDraftRevisionId"]
                            or record["publishedRevisionId"]
                        )
                    )
                    service.binding_resolver = BindingResolver(
                        self, call, revision["content"].get("bindings", {})
                    )
                if cmd.action == "edit":
                    service.edit(*args, cmd.content.model_dump())
                elif cmd.action == "successor":
                    service.successor(
                        *args, *([cmd.successorContent] if kind == "knowledge" else [])
                    )
                elif cmd.action == "validate":
                    service.validate(*args)
                elif cmd.action == "publish":
                    revision = next(
                        (
                            r
                            for r in record["revisions"]
                            if r["revisionId"] == record["currentDraftRevisionId"]
                        ),
                        None,
                    )
                    if not revision:
                        raise WorkbenchOwnerError("RESOURCE_DRAFT_REQUIRED", 409)
                    if kind == "agent":
                        validate_bindings(
                            scope,
                            revision["content"].get("bindings", {}),
                            service.binding_resolver,
                        )
                    # Existing publication owner binds the repository again, retaining
                    # this exact transaction resolver on its shallow service copy.
                    members = [
                        ExactGrant(
                            OWNERS[kind],
                            a,
                            reference(kind, identity, revision["revisionId"]),
                        )
                        for a in ("READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE")
                    ]
                    review = self.authorize(
                        call, members, key + ":publish", work, issuer
                    )
                    PreparedResourceOwner(
                        {**self.services, kind: service}
                    ).publish_policy(
                        replace(
                            call,
                            path={
                                "kind": kind,
                                "identity": identity,
                                "revision": revision["revisionId"],
                            },
                            payload={
                                "expectedVersion": cmd.expectedVersion,
                                "digest": revision["digest"],
                                "reason": "按已授权资源策略核验并发布",
                                "idempotencyKey": key,
                            },
                        ),
                        review,
                    )
                record = service.repository.get(scope, identity)
        except (WorkbenchOwnerError, AuthorityError):
            raise
        except AgentDefinitionFailure as exc:
            raise WorkbenchOwnerError(exc.reason, exc.status) from exc
        except BindingValidationFailure as exc:
            raise WorkbenchOwnerError(exc.reason, 409) from exc
        except KnowledgeLifecycleFailure as exc:
            raise WorkbenchOwnerError(str(exc), 409) from exc
        except ValueError as exc:
            # Original ingestion/pack validation uses stable ValueError codes.
            # Return a definite rejected command, not an unknown server failure.
            reason = str(exc)
            if (
                not reason
                or len(reason) > 100
                or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_" for c in reason)
            ):
                reason = "DEFINITION_CONTENT_INVALID"
            raise WorkbenchOwnerError(reason, 422) from exc
        except (AgentDefinitionRepositoryError, KnowledgeRepositoryError) as exc:
            raise WorkbenchOwnerError("DEFINITION_STORAGE_UNAVAILABLE", 503) from exc
        self.authorize(
            call,
            [
                ExactGrant(OWNERS[kind], "MANAGE_RESOURCE", target(kind, identity)),
                *(
                    ExactGrant(
                        OWNERS[kind],
                        "READ_RESOURCE",
                        reference(kind, identity, r["revisionId"]),
                    )
                    for r in record["revisions"]
                ),
            ],
            key + ":result-access",
            work,
            issuer,
        )
        result = {
            "schemaVersion": SCHEMA,
            "kind": kind,
            "identity": identity,
            "action": cmd.action,
            "commandKey": cmd.commandKey,
            "aggregateVersion": record["aggregateVersion"],
            "policyIssuer": issuer.principal_id,
            "policyDecisionId": proof.decision_id,
            "resource": record,
            "executionStarted": False,
            "indexingStarted": False,
            "modelCalls": 0,
            "credentialMaterial": "NOT_INCLUDED",
        }
        call.connection.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                p.tenant_id,
                p.security_domain,
                p.principal_id,
                key,
                digest,
                Jsonb(result),
            ),
        )
        return result


def install_definitions(manager, authorizer):
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
                call = AuthorizedOwnerCall(
                    "DEFINITION_MANAGEMENT",
                    context,
                    connection,
                    {},
                    {"kind": kind},
                    {},
                    (),
                    AuthorizedOwnerAuthority(
                        authorizer, context, connection, generation.generation, ()
                    ),
                    generation.generation,
                    authorizer.controller.readiness.recovery_epoch,
                )
                return {"result": operation(call)}

        root = PREFIX + "/definition-management/{kind}"

        @app.get(root)
        def directory(request: Request, kind: Kind):
            return run(request, kind, manager.directory)

        @app.post(root + "/commands")
        def command(request: Request, kind: Kind, body: dict):
            return run(
                request, kind, lambda call: manager.handle(replace(call, payload=body))
            )

        @app.get(root + "/commands/{key}")
        def receipt(request: Request, kind: Kind, key: str):
            return run(request, kind, lambda call: manager.receipt(call, kind, key))

    return install
