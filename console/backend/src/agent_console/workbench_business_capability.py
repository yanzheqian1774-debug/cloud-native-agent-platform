"""Trusted, draft-only capability owner; no model or resource mutation."""

from dataclasses import replace
from typing import Any

from psycopg import Error as PostgresError
from pydantic import Field

from .authority_contracts import AuthorityError, ExactGrant
from .business_capability import (
    BindingKind,
    BusinessCapabilityError,
    BusinessCapabilityRevision,
    OriginKind,
)
from .business_capability_publication import change_preview, verify_review
from .business_capability_publication_postgres import CapabilityPublicationRepository
from .capability_catalogue_preferences import operations as preference_operations
from .development_administrator import for_call
from .digital_employee_definition import EmployeeDefinitionError, digest
from .execution_domain import ScopeIdentity
from .execution_preparation import ExecutionPreparationError
from .knowledge_repository import KnowledgeRepositoryError
from .runtime_profile_repository import RuntimeProfileRepositoryError
from .skill_mcp_repository import SkillMcpRepositoryError
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel, WorkbenchPageQuery
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_execution import candidate
from .workbench_prepared_resources import TABLES, PreparedResourceOwner
from .workbench_resource_directory import target
from .workflow_definition_service import WorkflowDefinitionFailure

OWNER = "BUSINESS_CAPABILITY"
COLLECTION = "business-capability:collection"


class CapabilityListQuery(WorkbenchPageQuery):
    query: str = Field(default="", max_length=500)
    domain: str = Field(default="", max_length=80)
    favoritesOnly: bool = False


class PublishCapabilityInput(StrictWorkbenchModel):
    expectedVersion: int = Field(strict=True, ge=1)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    impactDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    commandId: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


class SaveCapabilityInput(StrictWorkbenchModel):
    revision: dict[str, Any]
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)


def save_grants(context, path, payload, query):
    try:
        revision = BusinessCapabilityRevision.from_record(payload["revision"])
    except BusinessCapabilityError as exc:
        raise WorkbenchOwnerError(str(exc), 422) from exc
    if (revision.scope.namespace, revision.scope.security_domain) != (
        context.scope.tenant_id,
        context.scope.security_domain,
    ):
        raise WorkbenchOwnerError("CAPABILITY_NOT_FOUND", 404)
    if revision.predecessor_revision_id is None:
        return (ExactGrant(OWNER, "CREATE", COLLECTION),)
    return (
        ExactGrant(
            OWNER, "REVISE", f"business-capability:{revision.capability_id}:aggregate"
        ),
    )


class CapabilityTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if grant.owner != OWNER or connection is None:
            return False
        if grant.action in {"CREATE", "LIST"}:
            return grant.exact_resource == COLLECTION
        if grant.action not in {"READ", "REVISE", "REVIEW_PUBLISH"}:
            return False
        table, expression = (
            (
                "revisions",
                "'business-capability:' || capability_id || ':' || revision_id",
            )
            if grant.action in {"READ", "REVIEW_PUBLISH"}
            else (
                "definitions",
                "'business-capability:' || capability_id || ':aggregate'",
            )
        )
        try:
            return (
                connection.execute(
                    f"SELECT 1 FROM business_capability.{table} WHERE namespace=%s "
                    f"AND security_domain=%s AND {expression}=%s FOR SHARE",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        grant.exact_resource,
                    ),
                ).fetchone()
                is not None
            )
        except PostgresError as exc:
            raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE") from exc


class CapabilityReferences:
    """Reuse each authoritative reader after exact permission checks."""

    def __init__(self, employees, services, workflows=None):
        self.employees = employees
        self.services = services
        self.resources = PreparedResourceOwner(services)
        self.workflows = workflows

    def validate(self, call, revision, *, require_published=False):
        principal = OwnerPrincipal(
            call.context.principal_id,
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        members = []
        for binding in revision.bindings:
            ref = binding.reference
            if binding.kind is BindingKind.EMPLOYEE:
                call.authority.require(
                    principal,
                    "EMPLOYEE",
                    "READ",
                    f"employee:{ref.resource_id}:{ref.revision_id}",
                )
                value = self.employees.read_revision_for_workbench(
                    call.connection,
                    revision.scope,
                    ref.resource_id,
                    ref.revision_id,
                    authorized=True,
                )
                name = value["revision"]["role"]
                actual_digest = value["digest"]
                if require_published and value["publicationState"] != "PUBLISHED":
                    raise BusinessCapabilityError("CAPABILITY_MEMBER_NOT_PUBLISHED")
            else:
                kind = {
                    BindingKind.SKILL: "skill",
                    BindingKind.MCP: "mcp",
                    BindingKind.KNOWLEDGE: "knowledge",
                    BindingKind.RUNTIME_PROFILE: "runtime",
                }.get(binding.kind)
                if kind is None or kind not in self.services:
                    raise BusinessCapabilityError(
                        "CAPABILITY_MEMBER_ADAPTER_UNAVAILABLE"
                    )
                grant = target(kind, ref.resource_id, ref.revision_id)
                call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
                if require_published:
                    table, column = TABLES[kind]
                    row = call.connection.execute(
                        f"SELECT record FROM {table} WHERE namespace=%s "
                        f"AND security_domain=%s AND {column}=%s FOR SHARE",
                        (
                            revision.scope.namespace,
                            revision.scope.security_domain,
                            ref.resource_id,
                        ),
                    ).fetchone()
                    if (
                        not row
                        or not row["record"].get("enabled", True)
                        or row["record"].get("archived", False)
                    ):
                        raise BusinessCapabilityError("CAPABILITY_MEMBER_UNAVAILABLE")
                value = self.resources(
                    replace(
                        call,
                        operation="READ_PREPARED_RESOURCE",
                        path={
                            "kind": kind,
                            "identity": ref.resource_id,
                            "revision": ref.revision_id,
                        },
                        payload={},
                        query={},
                    )
                )
                name = value["name"]
                actual_digest = value["revision"]["digest"]
                if binding.kind is BindingKind.RUNTIME_PROFILE:
                    actual_digest = actual_digest.removeprefix("sha256:")
                if require_published and value["revision"]["state"] != "PUBLISHED":
                    raise BusinessCapabilityError("CAPABILITY_MEMBER_NOT_PUBLISHED")
            if actual_digest != ref.digest:
                raise BusinessCapabilityError("CAPABILITY_MEMBER_VERSION_MISMATCH")
            members.append(
                {
                    "kind": binding.kind.value,
                    "resourceId": ref.resource_id,
                    "revisionId": ref.revision_id,
                    "digest": ref.digest,
                    "name": name,
                }
            )
        origin = revision.origin
        if origin.kind is OriginKind.WORKFLOW_REVISION:
            ref = origin.workflow
            if ref is None or self.workflows is None:
                raise BusinessCapabilityError("CAPABILITY_SOURCE_UNAVAILABLE")
            call.authority.require(
                principal,
                "WORKFLOW",
                "READ",
                f"workflow:{ref.resource_id}:{ref.revision_id}",
            )
            value = self.workflows.read_revision_for_workbench(
                call.connection,
                revision.scope,
                ref.resource_id,
                ref.revision_id,
                authorized=True,
            )
            if require_published and value["revision"]["state"] != "PUBLISHED":
                raise BusinessCapabilityError("CAPABILITY_SOURCE_NOT_PUBLISHED")
            if value["revision"]["digest"] != ref.digest:
                raise BusinessCapabilityError("CAPABILITY_SOURCE_VERSION_MISMATCH")
        elif origin.kind is OriginKind.SAVED_PREPARATION:
            call.authority.require(
                principal,
                "EXECUTION",
                "READ",
                "governed-execution:prepared:" + origin.preparation_digest,
            )
            candidate(call.connection, revision.scope, origin.preparation_digest)
        return members


class CapabilityOwner:
    def __init__(self, repository, references, cursors):
        self.repository, self.references, self.cursors = repository, references, cursors

    def __call__(self, call):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        principal = OwnerPrincipal(
            call.context.principal_id, scope.namespace, scope.security_domain
        )
        try:
            if call.operation in {
                "PREVIEW_CAPABILITY_PUBLICATION",
                "PUBLISH_CAPABILITY_REVISION",
            }:
                identity, version = call.path["capability_id"], call.path["revision_id"]
                call.authority.require(
                    principal,
                    OWNER,
                    "READ",
                    f"business-capability:{identity}:{version}",
                )
                revision = self.repository.read(
                    call.connection, scope, identity, version
                )
                self.references.validate(call, revision, require_published=True)
                if call.operation == "PREVIEW_CAPABILITY_PUBLICATION":
                    return self._preview(call, revision, principal)
                command = PublishCapabilityInput.model_validate(call.payload)
                if (
                    not principal.principal_id.startswith("human:")
                    or not command.reason.strip()
                ):
                    raise WorkbenchOwnerError("CAPABILITY_HUMAN_REVIEW_REQUIRED", 403)
                decision = call.authority.require(
                    principal,
                    OWNER,
                    "REVIEW_PUBLISH",
                    f"business-capability:{identity}:{version}",
                )
                replay = CapabilityPublicationRepository.begin(
                    call.connection, revision, command, principal.principal_id
                )
                if replay is not None:
                    return replay
                preview = self._preview(call, revision, principal)
                verify_review(command, preview)
                basis = (
                    "DEVELOPMENT_ADMINISTRATOR"
                    if for_call(call)
                    else "HUMAN_EXACT_REVIEW"
                )
                return CapabilityPublicationRepository.append(
                    call.connection,
                    revision,
                    command,
                    preview,
                    principal.principal_id,
                    decision.decision_id,
                    basis,
                )
            if call.operation == "SAVE_CAPABILITY_DRAFT":
                data = SaveCapabilityInput.model_validate(call.payload)
                revision = BusinessCapabilityRevision.from_record(data.revision)
                if revision.scope != scope:
                    raise WorkbenchOwnerError("CAPABILITY_NOT_FOUND", 404)
                grant = save_grants(call.context, call.path, call.payload, call.query)[
                    0
                ]
                decision = call.authority.require(
                    principal, grant.owner, grant.action, grant.exact_resource
                )
                # Recheck the original owners even on an idempotent retry.
                self.references.validate(call, revision)
                result = self.repository.save(
                    call.connection,
                    revision,
                    expected_version=data.expectedVersion,
                    command_id=data.commandId,
                    actor_id=principal.principal_id,
                    decision_id=decision.decision_id,
                )
                return {
                    **result,
                    "capabilityId": revision.capability_id,
                    "digest": revision.content_digest,
                    "state": "DRAFT",
                    "executionAuthorized": False,
                }
            if call.operation == "READ_CAPABILITY_REVISION":
                identity, version = call.path["capability_id"], call.path["revision_id"]
                call.authority.require(
                    principal,
                    OWNER,
                    "READ",
                    f"business-capability:{identity}:{version}",
                )
                revision = self.repository.read(
                    call.connection, scope, identity, version
                )
                members = self.references.validate(call, revision)
                head = call.connection.execute(
                    "SELECT head_revision_id,aggregate_version "
                    "FROM business_capability.definitions "
                    "WHERE namespace=%s AND security_domain=%s AND capability_id=%s",
                    (scope.namespace, scope.security_domain, identity),
                ).fetchone()
                latest = CapabilityPublicationRepository.latest(
                    call.connection, scope, identity
                )
                published = (
                    call.connection.execute(
                        "SELECT 1 FROM business_capability.publications "
                        "WHERE namespace=%s "
                        "AND security_domain=%s AND capability_id=%s "
                        "AND revision_id=%s",
                        (scope.namespace, scope.security_domain, identity, version),
                    ).fetchone()
                    is not None
                )
                return {
                    "members": members,
                    "revision": revision.canonical_record(),
                    "digest": revision.content_digest,
                    "aggregateVersion": head["aggregate_version"],
                    "headRevisionId": head["head_revision_id"],
                    "publishedRevisionId": latest["revision_id"] if latest else None,
                    "currentDraftRevisionId": head["head_revision_id"]
                    if not latest or latest["revision_id"] != head["head_revision_id"]
                    else None,
                    "state": "PUBLISHED" if published else "DRAFT",
                    "executionAuthorized": False,
                }
            if call.operation == "LIST_CAPABILITY_DOMAINS":
                call.authority.require(principal, OWNER, "LIST", COLLECTION)
                from .capability_catalogue_preferences import latest as preferences

                own = preferences(
                    call.connection,
                    (scope.namespace, scope.security_domain, principal.principal_id),
                )
                favorites = set(own["state"]["favorites"]) if own else set()
                values, favorite_count = set(), 0
                for item in self._scan(call, scope, principal):
                    values.add(item.get("businessDomain"))
                    favorite_count += item["capabilityId"] in favorites
                return {
                    "domains": sorted(value for value in values if value),
                    "hasUnassigned": None in values,
                    "readableFavoriteCount": favorite_count,
                }
            if call.operation == "LIST_CAPABILITIES":
                call.authority.require(principal, OWNER, "LIST", COLLECTION)
                return self._list(call, scope, principal)
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        except BusinessCapabilityError as exc:
            code = str(exc)
            status = (
                404
                if code == "CAPABILITY_NOT_FOUND"
                else 409
                if code.endswith(
                    (
                        "CONFLICT",
                        "MISMATCH",
                        "UNAVAILABLE",
                        "EXISTS",
                        "CHANGED",
                        "PUBLISHED",
                    )
                )
                else 422
            )
            raise WorkbenchOwnerError(code, status) from exc
        except (
            EmployeeDefinitionError,
            WorkflowDefinitionFailure,
            ExecutionPreparationError,
        ) as exc:
            raise WorkbenchOwnerError("CAPABILITY_REFERENCE_UNAVAILABLE", 409) from exc
        except (
            KnowledgeRepositoryError,
            RuntimeProfileRepositoryError,
            SkillMcpRepositoryError,
        ) as exc:
            raise WorkbenchOwnerError("CAPABILITY_REFERENCE_UNAVAILABLE", 409) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError("CAPABILITY_STORAGE_UNAVAILABLE", 503) from exc

    def _preview(self, call, revision, principal):
        head = call.connection.execute(
            "SELECT head_revision_id,aggregate_version "
            "FROM business_capability.definitions "
            "WHERE namespace=%s AND security_domain=%s AND capability_id=%s",
            (
                revision.scope.namespace,
                revision.scope.security_domain,
                revision.capability_id,
            ),
        ).fetchone()
        if not head or head["head_revision_id"] != revision.revision_id:
            raise BusinessCapabilityError("CAPABILITY_VERSION_CONFLICT")
        latest = CapabilityPublicationRepository.latest(
            call.connection, revision.scope, revision.capability_id
        )
        previous = None
        if latest:
            call.authority.require(
                principal,
                OWNER,
                "READ",
                f"business-capability:{revision.capability_id}:{latest['revision_id']}",
            )
            previous = self.repository.read(
                call.connection,
                revision.scope,
                revision.capability_id,
                latest["revision_id"],
            )
            if previous.content_digest != latest["revision_digest"]:
                raise BusinessCapabilityError("CAPABILITY_RECORD_CORRUPT")
        return change_preview(
            revision,
            previous,
            aggregate_version=head["aggregate_version"],
            generation=call.policy_generation,
        )

    def _item(self, call, scope, principal, row):
        latest = CapabilityPublicationRepository.latest(
            call.connection, scope, row["capability_id"]
        )
        candidates = [("currentPublished", latest["revision_id"])] if latest else []
        if not latest or latest["revision_id"] != row["head_revision_id"]:
            candidates.append(("currentDraft", row["head_revision_id"]))
        visible = {}
        for label, revision_id in candidates:
            try:
                call.authority.require(
                    principal,
                    OWNER,
                    "READ",
                    f"business-capability:{row['capability_id']}:{revision_id}",
                )
            except AuthorityError:
                continue
            revision = self.repository.read(
                call.connection, scope, row["capability_id"], revision_id
            )
            visible[label] = {
                "revisionId": revision.revision_id,
                "title": revision.title,
                "intent": revision.intent,
                "inputs": revision.inputs,
                "outputs": revision.outputs,
                "manualInvolvement": revision.manual_involvement,
                "businessDomain": revision.business_domain,
                "exclusions": revision.exclusions,
                "originKind": revision.origin.kind,
                "employeeResponsibilities": [
                    binding.purpose
                    for binding in revision.bindings
                    if binding.kind.value == "EMPLOYEE"
                ],
                "digest": revision.content_digest,
            }
        selected = visible.get("currentPublished") or visible.get("currentDraft")
        if selected is None:
            return None
        return {
            **selected,
            "capabilityId": row["capability_id"],
            "aggregateVersion": row["aggregate_version"],
            "state": "PUBLISHED" if "currentPublished" in visible else "DRAFT",
            "currentPublished": visible.get("currentPublished"),
            "currentDraft": visible.get("currentDraft"),
            "executionAuthorized": False,
        }

    def _scan(self, call, scope, principal, after=""):
        while True:
            rows = call.connection.execute(
                "SELECT capability_id,head_revision_id,aggregate_version "
                "FROM business_capability.definitions "
                "WHERE namespace=%s AND security_domain=%s "
                'AND capability_id COLLATE "C">%s '
                'ORDER BY capability_id COLLATE "C" LIMIT 100',
                (scope.namespace, scope.security_domain, after),
            ).fetchall()
            for row in rows:
                item = self._item(call, scope, principal, row)
                if item is not None:
                    yield item
            if len(rows) < 100:
                return
            after = rows[-1]["capability_id"]

    def _employee_names(self, call, scope, principal, item):
        revision = self.repository.read(
            call.connection, scope, item["capabilityId"], item["revisionId"]
        )
        names, unavailable = [], 0
        for binding in revision.bindings:
            if binding.kind is not BindingKind.EMPLOYEE:
                continue
            ref = binding.reference
            try:
                call.authority.require(
                    principal,
                    "EMPLOYEE",
                    "READ",
                    f"employee:{ref.resource_id}:{ref.revision_id}",
                )
                value = self.references.employees.read_revision_for_workbench(
                    call.connection,
                    scope,
                    ref.resource_id,
                    ref.revision_id,
                    authorized=True,
                )
                if value["digest"] != ref.digest:
                    unavailable += 1
                    continue
                names.append(value["revision"]["role"])
            except (AuthorityError, EmployeeDefinitionError):
                unavailable += 1
        return {**item, "employeeNames": names, "employeeNamesUnavailable": unavailable}

    def _list(self, call, scope, principal):
        from .capability_catalogue_preferences import latest as preferences

        size = call.query["pageSize"]
        query = call.query["query"].strip().casefold()
        domain = call.query["domain"]
        favorites = None
        if call.query["favoritesOnly"]:
            own = preferences(
                call.connection,
                (scope.namespace, scope.security_domain, principal.principal_id),
            )
            favorites = set(own["state"]["favorites"]) if own else set()
        route = "CAPABILITY_LIST:" + digest(
            {
                "principal": principal.principal_id,
                "query": query,
                "domain": domain,
                "favorites": sorted(favorites) if favorites is not None else None,
            }
        )
        after = (
            self.cursors.resolve(
                call.query["cursor"],
                route=route,
                context=call.context,
                page_size=size,
                key_size=1,
            )[0]
            if call.query.get("cursor")
            else ""
        )
        items = []
        for item in self._scan(call, scope, principal, after):
            if favorites is not None and item["capabilityId"] not in favorites:
                continue
            if domain and (item.get("businessDomain") or "__UNASSIGNED__") != domain:
                continue
            searchable = " ".join(
                [item["title"], item["intent"], *item["employeeResponsibilities"]]
            ).casefold()
            if query not in searchable:
                continue
            items.append(item)
            if len(items) > size:
                break
        return {
            "items": [
                self._employee_names(call, scope, principal, item)
                for item in items[:size]
            ],
            "nextCursor": self.cursors.mint(
                route=route,
                context=call.context,
                page_size=size,
                last_key=(items[size - 1]["capabilityId"],),
            )
            if len(items) > size
            else None,
        }


def capability_operations(repository, employees, services, cursors, workflows=None):
    handler = CapabilityOwner(
        repository, CapabilityReferences(employees, services, workflows), cursors
    )
    return (
        *preference_operations(),
        WorkbenchOperation(
            "LIST_CAPABILITY_DOMAINS",
            "GET",
            PREFIX + "/business-capabilities/domains",
            None,
            None,
            lambda *_: (ExactGrant(OWNER, "LIST", COLLECTION),),
            handler,
        ),
        WorkbenchOperation(
            "PREVIEW_CAPABILITY_PUBLICATION",
            "GET",
            PREFIX + "/business-capabilities/{capability_id}/revisions/"
            "{revision_id}/publication-preview",
            None,
            None,
            lambda _c, p, _v, _q: (
                ExactGrant(
                    OWNER,
                    "READ",
                    f"business-capability:{p['capability_id']}:{p['revision_id']}",
                ),
            ),
            handler,
        ),
        WorkbenchOperation(
            "PUBLISH_CAPABILITY_REVISION",
            "POST",
            PREFIX + "/business-capabilities/{capability_id}/revisions/"
            "{revision_id}/publication",
            PublishCapabilityInput,
            None,
            lambda _c, p, _v, _q: (
                ExactGrant(
                    OWNER,
                    "REVIEW_PUBLISH",
                    f"business-capability:{p['capability_id']}:{p['revision_id']}",
                ),
            ),
            handler,
            201,
        ),
        WorkbenchOperation(
            "LIST_CAPABILITIES",
            "GET",
            PREFIX + "/business-capabilities",
            None,
            CapabilityListQuery,
            lambda *_: (ExactGrant(OWNER, "LIST", COLLECTION),),
            handler,
        ),
        WorkbenchOperation(
            "SAVE_CAPABILITY_DRAFT",
            "POST",
            PREFIX + "/business-capabilities",
            SaveCapabilityInput,
            None,
            save_grants,
            handler,
            201,
        ),
        WorkbenchOperation(
            "READ_CAPABILITY_REVISION",
            "GET",
            PREFIX + "/business-capabilities/{capability_id}/revisions/{revision_id}",
            None,
            None,
            lambda _c, p, _v, _q: (
                ExactGrant(
                    OWNER,
                    "READ",
                    f"business-capability:{p['capability_id']}:{p['revision_id']}",
                ),
            ),
            handler,
        ),
    )
