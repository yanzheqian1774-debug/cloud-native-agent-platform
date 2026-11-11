"""Opt-in trusted business architecture/process draft operations."""

from __future__ import annotations

import json
from typing import Literal

from psycopg import Error as PostgresError
from pydantic import Field, model_validator

from .authority_contracts import AuthorityError, ExactGrant
from .business_process_authorization import require_process_grant
from .business_process_definition import (
    BusinessArchitecture,
    BusinessProcessContent,
    definition_issues,
)
from .business_process_postgres import BusinessProcessStorageError
from .execution_domain import ScopeIdentity, record_digest
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError

OWNER = "BUSINESS_PROCESS"
COLLECTION = "business-process:collection"
ARCHITECTURE = "business-process:architecture"
ROOT = PREFIX + "/business-processes"


class SaveBusinessProcess(StrictWorkbenchModel):
    kind: Literal["ARCHITECTURE", "PROCESS"]
    objectId: str = Field(min_length=1, max_length=200)
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)
    content: dict

    @model_validator(mode="after")
    def valid_content(self):
        model = (
            BusinessArchitecture
            if self.kind == "ARCHITECTURE"
            else BusinessProcessContent
        )
        model.model_validate(self.content)
        if self.kind == "ARCHITECTURE" and self.objectId != "architecture":
            raise ValueError("BUSINESS_ARCHITECTURE_ID_INVALID")
        if any(not value.strip() for value in (self.objectId, self.commandId)):
            raise ValueError("BUSINESS_COMMAND_ID_INVALID")
        return self


class ReadBusinessProcess(StrictWorkbenchModel):
    revision: str = Field(default="", max_length=200)


class BusinessProcessEditorAccess(StrictWorkbenchModel):
    kind: Literal["ARCHITECTURE", "PROCESS"]
    action: Literal["CREATE", "REVISE", "PUBLISH"]
    objectId: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def valid_target(self):
        if self.kind == "ARCHITECTURE":
            if self.action != "REVISE" or self.objectId != "architecture":
                raise ValueError("BUSINESS_ARCHITECTURE_TARGET_INVALID")
        elif self.action in {"REVISE", "PUBLISH"} and not self.objectId.strip():
            raise ValueError("BUSINESS_PROCESS_TARGET_REQUIRED")
        return self


def editor_grant(query):
    target = (
        ARCHITECTURE
        if query.kind == "ARCHITECTURE"
        else COLLECTION
        if query.action in {"CREATE", "PUBLISH"}
        else f"business-process:{query.objectId}:aggregate"
    )
    return ExactGrant(OWNER, query.action, target)


class ListBusinessProcesses(StrictWorkbenchModel):
    pageSize: int = Field(default=25, ge=1, le=50)
    cursor: str = Field(default="", max_length=2048)
    domainId: str = Field(default="", max_length=200)
    groupId: str = Field(default="", max_length=200)
    query: str = Field(default="", max_length=160)


def command_grant(command):
    if command.kind == "ARCHITECTURE":
        return ExactGrant(OWNER, "REVISE", ARCHITECTURE)
    if command.expectedVersion == 0:
        return ExactGrant(OWNER, "CREATE", COLLECTION)
    return ExactGrant(OWNER, "REVISE", f"business-process:{command.objectId}:aggregate")


class BusinessProcessTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if grant.owner != OWNER or connection is None:
            return False
        if grant.action in {
            "CREATE",
            "LIST",
            "READ_SCOPE",
            "MAINTAIN_SCOPE",
            "PUBLISH",
        }:
            return grant.exact_resource == COLLECTION
        if grant.action in {"READ", "REVISE"} and grant.exact_resource == ARCHITECTURE:
            return True
        if grant.action not in {"READ", "REVISE"}:
            return False
        table, expression = (
            ("definitions", "'business-process:' || object_id || ':aggregate'")
            if grant.action == "REVISE"
            else (
                "revisions",
                "'business-process:' || kind || ':' || object_id || ':' || revision_id",
            )
        )
        return (
            connection.execute(
                f"SELECT 1 FROM business_process.{table} WHERE namespace=%s "
                f"AND security_domain=%s AND {expression}=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    grant.exact_resource,
                ),
            ).fetchone()
            is not None
        )


def business_process_operations(repository, cursors, *, employees=None, services=None):
    from .workbench_business_process_references import BusinessProcessReferences
    from .workbench_business_process_relations import (
        business_process_relation_operations,
    )

    references = BusinessProcessReferences(employees, services)
    from .workbench_business_process_publication import (
        business_process_publication_operations,
        publication_state,
    )

    require = require_process_grant

    def read(call, kind, object_id, revision=""):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        if kind == "ARCHITECTURE" and not revision:
            require(call, ExactGrant(OWNER, "READ", ARCHITECTURE))
        else:
            if not revision:
                head = call.connection.execute(
                    "SELECT head_revision_id FROM business_process.definitions "
                    "WHERE namespace=%s AND security_domain=%s "
                    "AND kind=%s AND object_id=%s",
                    (scope.namespace, scope.security_domain, kind, object_id),
                ).fetchone()
                if not head:
                    raise WorkbenchOwnerError("BUSINESS_PROCESS_NOT_FOUND", 404)
                revision = head["head_revision_id"]
            require(
                call,
                ExactGrant(
                    OWNER, "READ", f"business-process:{kind}:{object_id}:{revision}"
                ),
            )
        return repository.read(
            call.connection, scope, kind, object_id, revision or None
        )

    def handle(call):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )
        try:
            if call.operation == "READ_BUSINESS_PROCESS_EDITOR_ACCESS":
                query = BusinessProcessEditorAccess.model_validate(call.query)
                require(call, editor_grant(query))
                return {
                    "allowed": True,
                    "kind": query.kind,
                    "action": query.action,
                    "objectId": query.objectId,
                    "executionAuthorized": False,
                }
            if call.operation == "SAVE_BUSINESS_PROCESS":
                command = SaveBusinessProcess.model_validate(call.payload)
                decision = require(call, command_grant(command))
                options = dict(
                    expected_version=command.expectedVersion,
                    command_id=command.commandId,
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
                if command.kind == "ARCHITECTURE":
                    return repository.save_architecture(
                        call.connection,
                        scope,
                        BusinessArchitecture.model_validate(command.content),
                        **options,
                    )
                require(call, ExactGrant(OWNER, "READ", ARCHITECTURE))
                content = BusinessProcessContent.model_validate(command.content)
                references.validate(call, content)
                return repository.save_process(
                    call.connection, scope, command.objectId, content, **options
                )
            if call.operation == "READ_BUSINESS_PROCESS_RECEIPT":
                row = call.connection.execute(
                    "SELECT kind,object_id,actor_id,result FROM "
                    "business_process.receipts "
                    "WHERE namespace=%s AND security_domain=%s AND command_id=%s",
                    (scope.namespace, scope.security_domain, call.path["command_id"]),
                ).fetchone()
                if not row or row["actor_id"] != call.context.principal_id:
                    raise WorkbenchOwnerError("BUSINESS_PROCESS_COMMAND_NOT_FOUND", 404)
                result = row["result"]
                # Initial LIST is insufficient; recheck the original write action.
                action = (
                    "REVISE"
                    if row["kind"] == "ARCHITECTURE" or result["aggregateVersion"] > 1
                    else "CREATE"
                )
                target = (
                    ARCHITECTURE
                    if row["kind"] == "ARCHITECTURE"
                    else COLLECTION
                    if action == "CREATE"
                    else f"business-process:{row['object_id']}:aggregate"
                )
                require(call, ExactGrant(OWNER, action, target))
                return result
            if call.operation == "READ_BUSINESS_ARCHITECTURE":
                try:
                    return read(
                        call,
                        "ARCHITECTURE",
                        "architecture",
                        call.query.get("revision", ""),
                    )
                except BusinessProcessStorageError as error:
                    if str(
                        error
                    ) == "BUSINESS_PROCESS_NOT_FOUND" and not call.query.get(
                        "revision"
                    ):
                        return {
                            "objectId": "architecture",
                            "aggregateVersion": 0,
                            "revisionId": None,
                            "record": {
                                "content": BusinessArchitecture().model_dump(
                                    mode="json"
                                )
                            },
                        }
                    raise
            if call.operation == "READ_BUSINESS_PROCESS":
                value = read(
                    call,
                    "PROCESS",
                    call.path["process_id"],
                    call.query.get("revision", ""),
                )
                reference = value["record"].get("architectureReference")
                if not reference:
                    raise WorkbenchOwnerError("BUSINESS_PROCESS_RECORD_CORRUPT", 503)
                architecture = read(
                    call, "ARCHITECTURE", "architecture", reference["revisionId"]
                )
                if architecture["digest"] != reference["digest"]:
                    raise WorkbenchOwnerError("BUSINESS_PROCESS_RECORD_CORRUPT", 503)
                issues = definition_issues(
                    BusinessProcessContent.model_validate(value["record"]["content"]),
                    BusinessArchitecture.model_validate(
                        architecture["record"]["content"]
                    ),
                )
                return {
                    **value,
                    "architecture": architecture,
                    "referenceDetails": references.describe(
                        call,
                        BusinessProcessContent.model_validate(
                            value["record"]["content"]
                        ),
                    ),
                    "publicationState": publication_state(
                        call, repository, value["objectId"], value["revisionId"]
                    ),
                    "definitionValidation": {
                        "status": "INCOMPLETE" if issues else "COMPLETE",
                        "issues": [issue.model_dump(mode="json") for issue in issues],
                        "executionAuthorized": False,
                    },
                }
            query = ListBusinessProcesses.model_validate(call.query)
            route = json.dumps(
                [
                    ROOT,
                    call.context.principal_id,
                    query.domainId,
                    query.groupId,
                    query.query,
                ],
                ensure_ascii=False,
            )
            last = (
                cursors.resolve(
                    query.cursor,
                    route=route,
                    context=call.context,
                    page_size=query.pageSize,
                    key_size=1,
                )[0]
                if query.cursor
                else ""
            )
            pattern = (
                "%"
                + query.query.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
                + "%"
            )
            rows = call.connection.execute(
                "SELECT "
                "d.object_id,d.head_revision_id,d.aggregate_version,"
                "r.digest,r.record,p.revision_id AS published_revision_id "
                "FROM business_process.definitions d "
                "JOIN business_process.revisions r ON "
                "(d.namespace,d.security_domain,d.kind,d.object_id,"
                "d.head_revision_id)="
                "(r.namespace,r.security_domain,r.kind,r.object_id,r.revision_id) "
                "LEFT JOIN LATERAL (SELECT revision_id "
                "FROM business_process.publications p "
                "WHERE p.namespace=d.namespace AND p.security_domain=d.security_domain "
                "AND p.object_id=d.object_id ORDER BY publication_version DESC "
                "LIMIT 1) p ON true "
                "WHERE d.namespace=%s AND d.security_domain=%s AND "
                "d.kind='PROCESS' AND d.object_id>%s "
                "AND (%s='' OR r.record->'content'->>'domain_id'=%s) "
                "AND (%s='' OR r.record->'content'->>'group_id'=%s) "
                "AND concat_ws(' "
                "',r.record->'content'->>'name',r.record->'content'->>'business_code',"
                "r.record->'content'->>'owner_description') ILIKE %s "
                "ORDER BY d.object_id LIMIT %s",
                (
                    scope.namespace,
                    scope.security_domain,
                    last,
                    query.domainId,
                    query.domainId,
                    query.groupId,
                    query.groupId,
                    pattern,
                    query.pageSize + 1,
                ),
            ).fetchall()
            items = []
            for row in rows[: query.pageSize]:
                try:
                    require(
                        call,
                        ExactGrant(
                            OWNER,
                            "READ",
                            f"business-process:PROCESS:{row['object_id']}:{row['head_revision_id']}",
                        ),
                    )
                except AuthorityError as error:
                    if str(error) != "AUTHORIZATION_NOT_FOUND":
                        raise
                    continue
                if record_digest(row["record"]) != row["digest"]:
                    raise WorkbenchOwnerError("BUSINESS_PROCESS_RECORD_CORRUPT", 503)
                content = row["record"]["content"]
                items.append(
                    {
                        "processId": row["object_id"],
                        "revisionId": row["head_revision_id"],
                        "name": content["name"],
                        "domainId": content["domain_id"],
                        "groupId": content["group_id"],
                        "ownerDescription": content["owner_description"],
                        "state": "PUBLISHED"
                        if row["published_revision_id"] == row["head_revision_id"]
                        else "DRAFT",
                        "hasPublishedVersion": row["published_revision_id"] is not None,
                        "aggregateVersion": row["aggregate_version"],
                    }
                )
            next_cursor = (
                cursors.mint(
                    route=route,
                    context=call.context,
                    page_size=query.pageSize,
                    last_key=(rows[query.pageSize - 1]["object_id"],),
                )
                if len(rows) > query.pageSize
                else None
            )
            return {"items": items, "nextCursor": next_cursor}
        except BusinessProcessStorageError as error:
            reason = str(error)
            status = (
                404
                if reason.endswith("NOT_FOUND")
                else 409
                if reason.endswith("CONFLICT")
                else 422
            )
            raise WorkbenchOwnerError(reason, status) from error
        except PostgresError as error:
            raise WorkbenchOwnerError("BUSINESS_PROCESS_UNAVAILABLE", 503) from error

    def constant(grant):
        return lambda context, path, payload, query: (grant,)

    def admission(grant):
        if grant.action == "READ" or (
            grant.action == "REVISE" and grant.exact_resource != ARCHITECTURE
        ):
            return ExactGrant(OWNER, "LIST", COLLECTION)
        return grant

    def save_grants(context, path, payload, query):
        return (admission(command_grant(SaveBusinessProcess.model_validate(payload))),)

    def editor_grants(context, path, payload, query):
        return (
            admission(editor_grant(BusinessProcessEditorAccess.model_validate(query))),
        )

    return (
        *business_process_relation_operations(repository, cursors),
        *business_process_publication_operations(repository, references),
        WorkbenchOperation(
            "READ_BUSINESS_PROCESS_EDITOR_ACCESS",
            "GET",
            ROOT + "/editor-access",
            None,
            BusinessProcessEditorAccess,
            editor_grants,
            handle,
        ),
        WorkbenchOperation(
            "SAVE_BUSINESS_PROCESS",
            "POST",
            ROOT + "/commands",
            SaveBusinessProcess,
            None,
            save_grants,
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_PROCESS_RECEIPT",
            "GET",
            ROOT + "/commands/{command_id}",
            None,
            None,
            constant(ExactGrant(OWNER, "LIST", COLLECTION)),
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_ARCHITECTURE",
            "GET",
            ROOT + "/architecture",
            None,
            ReadBusinessProcess,
            constant(ExactGrant(OWNER, "LIST", COLLECTION)),
            handle,
        ),
        WorkbenchOperation(
            "READ_BUSINESS_PROCESS",
            "GET",
            ROOT + "/{process_id}",
            None,
            ReadBusinessProcess,
            constant(ExactGrant(OWNER, "LIST", COLLECTION)),
            handle,
        ),
        WorkbenchOperation(
            "LIST_BUSINESS_PROCESSES",
            "GET",
            ROOT,
            None,
            ListBusinessProcesses,
            constant(ExactGrant(OWNER, "LIST", COLLECTION)),
            handle,
        ),
    )
