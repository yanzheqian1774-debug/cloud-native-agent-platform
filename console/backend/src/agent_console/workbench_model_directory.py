"""Current exact Model metadata reads on the authority caller's transaction."""

from dataclasses import asdict

from psycopg import Error as DatabaseError
from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .model_binding_resolution import ExactModelBinding
from .model_governance import ModelGovernanceError, ModelGovernanceNotFound
from .model_governance_authorization import (
    READ_MODEL,
    CallerOwnedPostgresModelGovernanceReader,
    PostgresModelGrantTargetLookup,
    model_catalog_grant,
    model_revision_grant,
    model_scope,
)
from .resource_use_domain import canonical_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


class ModelQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=200)
    pageSize: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=2048)


class ModelExactQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class ModelReadTargets:
    """Only the original read targets; no new Model maintenance admission."""

    def __init__(self, repository):
        self.lookup = PostgresModelGrantTargetLookup(repository)

    def is_known_exact_target(self, context, grant, *, connection=None):
        if (
            connection is None
            or grant.owner != "MODEL_GOVERNANCE"
            or grant.action != READ_MODEL
        ):
            return False
        try:
            return self.lookup.is_known_exact_target(
                model_scope(context.scope), grant, connection=connection
            )
        except DatabaseError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc


def _principal(context):
    return OwnerPrincipal(
        context.principal_id, context.scope.tenant_id, context.scope.security_domain
    )


def _exact(path, query):
    return ExactModelBinding(path["model_id"], path["revision_id"], query["digest"])


class ModelDirectory:
    def __init__(self, repository, cursors):
        self.repository, self.cursors = repository, cursors

    @staticmethod
    def envelope(call):
        return {
            "subject": call.context.principal_id,
            "scope": {
                "tenantId": call.context.scope.tenant_id,
                "securityDomain": call.context.scope.security_domain,
            },
            "basis": "CURRENT_EXACT_MODEL_READ",
            "executionAuthority": "NONE",
        }

    @staticmethod
    def projection(reader, scope, revision, definition):
        try:
            lifecycle = reader.read_lifecycle(
                scope, revision.model_id, revision.revision_id
            )
            state, high_water = lifecycle.state.value, asdict(lifecycle.high_water)
        except ModelGovernanceNotFound as exc:
            if str(exc) != "MODEL_LIFECYCLE_NOT_FOUND":
                raise
            state, high_water = "NOT_RECORDED", None
        # Deliberate allowlist. Configuration records/addresses/SecretReference
        # and unrelated revisions must never cross this read boundary.
        return {
            "modelId": revision.model_id,
            "revisionId": revision.revision_id,
            "digest": revision.digest,
            "revision": revision.revision,
            "name": revision.provider_native_model_id,
            "capabilities": list(revision.capabilities),
            "compatibility": list(revision.compatibility),
            "invocationLimits": [asdict(item) for item in revision.invocation_limits],
            "provider": asdict(revision.provider),
            "endpoint": asdict(revision.endpoint),
            "connectionProfile": asdict(revision.connection_profile),
            "createdAt": revision.created_at.isoformat(),
            "isCurrentRevision": definition.current_revision_id == revision.revision_id,
            "state": state,
            "lifecycleHighWater": high_water,
            "availability": "NOT_MEASURABLE",
            "price": "NOT_MEASURABLE",
        }

    def __call__(self, call):
        try:
            return self.read(call)
        except ModelGovernanceNotFound as exc:
            raise WorkbenchOwnerError("MODEL_DIRECTORY_NOT_FOUND", 404) from exc
        except (ModelGovernanceError, DatabaseError) as exc:
            raise WorkbenchOwnerError("MODEL_DIRECTORY_UNAVAILABLE", 503) from exc

    def read(self, call):
        scope = model_scope(call.context.scope)
        reader = CallerOwnedPostgresModelGovernanceReader(
            self.repository, call.connection
        )
        if call.operation == "READ_MODEL_DIRECTORY_REVISION":
            binding = _exact(call.path, call.query)
            revision = reader.get_revision(
                scope, binding.resource_id, binding.revision_id
            )
            if revision.digest != binding.digest:
                raise WorkbenchOwnerError("MODEL_DIRECTORY_NOT_FOUND", 404)
            definition = reader.get(scope, revision.model_id)
            return {
                **self.envelope(call),
                "item": self.projection(reader, scope, revision, definition),
            }
        args = ModelQuery.model_validate(call.query)
        route = "model-directory:" + canonical_digest(
            [call.context.principal_id, args.query]
        )
        lower = (
            self.cursors.resolve(
                args.cursor,
                route=route,
                context=call.context,
                page_size=args.pageSize,
                key_size=2,
            )
            if args.cursor
            else ("", "")
        )
        visible = []
        scanned = 0
        while len(visible) <= args.pageSize:
            rows = call.connection.execute(
                "SELECT model_id,revision_id,digest "
                "FROM model_governance.model_revisions "
                "WHERE namespace=%s AND security_domain=%s "
                "AND (model_id,revision_id)>(%s,%s) "
                "ORDER BY model_id,revision_id LIMIT 100",
                (scope.namespace, scope.security_domain, *lower),
            ).fetchall()
            for row in rows:
                scanned += 1
                if scanned > 10000:
                    raise WorkbenchOwnerError("MODEL_DIRECTORY_SCAN_LIMIT", 503)
                lower = (row["model_id"], row["revision_id"])
                # Digest is authoritative stored metadata, never a frontend alias.
                grant = model_revision_grant(ExactModelBinding(*lower, row["digest"]))
                try:
                    call.authority.require(
                        _principal(call.context),
                        grant.owner,
                        grant.action,
                        grant.exact_resource,
                    )
                except AuthorityError as exc:
                    if str(exc) != "AUTHORIZATION_NOT_FOUND":
                        raise
                    continue
                revision = reader.get_revision(scope, *lower)
                if (
                    args.query.casefold()
                    not in (
                        revision.provider_native_model_id + " " + revision.model_id
                    ).casefold()
                ):
                    continue
                visible.append((lower, revision))
                if len(visible) > args.pageSize:
                    break
            if len(rows) < 100 or len(visible) > args.pageSize:
                break
        shown = visible[: args.pageSize]
        return {
            **self.envelope(call),
            "items": [
                self.projection(
                    reader, scope, revision, reader.get(scope, revision.model_id)
                )
                for _, revision in shown
            ],
            "nextCursor": self.cursors.mint(
                route=route,
                context=call.context,
                page_size=args.pageSize,
                last_key=shown[-1][0],
            )
            if len(visible) > args.pageSize
            else None,
        }


def operations(repository, cursors):
    handler = ModelDirectory(repository, cursors)
    return (
        WorkbenchOperation(
            "LIST_MODEL_DIRECTORY",
            "GET",
            PREFIX + "/model-directory",
            None,
            ModelQuery,
            lambda *_: (model_catalog_grant(),),
            handler,
        ),
        WorkbenchOperation(
            "READ_MODEL_DIRECTORY_REVISION",
            "GET",
            PREFIX + "/model-directory/{model_id}/revisions/{revision_id}",
            None,
            ModelExactQuery,
            lambda _context, path, _payload, query: (
                model_revision_grant(_exact(path, query)),
            ),
            handler,
        ),
    )
