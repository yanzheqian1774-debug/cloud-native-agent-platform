"""Private authenticated import-preview and persistent tool draft operations."""

from __future__ import annotations

import base64
import json
from typing import Annotated, Literal

from psycopg import Error as PostgresError
from pydantic import Field, model_validator

from .authority_contracts import AuthorityError, ExactGrant
from .execution_domain import ScopeIdentity
from .tool_definition import ToolDraftContent
from .tool_definition_authorization import require_tool_grant
from .tool_definition_postgres import ToolStorageError, import_preview, logical_identity
from .tool_import import ToolImportError
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_owner_authorization import WorkbenchOwnerError

OWNER = "TOOL"
COLLECTION = "tool:collection"
ROOT = PREFIX + "/tool-definitions"


class ImportSource(StrictWorkbenchModel):
    kind: Literal["API", "PLUGIN", "PLUGIN_ZIP"]
    contentBase64: str = Field(min_length=1, max_length=133336)

    def source_bytes(self):
        try:
            payload = base64.b64decode(self.contentBase64, validate=True)
        except ValueError as exc:
            raise ToolImportError("IMPORT_ENCODING_INVALID") from exc
        if len(payload) > 100000:
            raise ToolImportError("IMPORT_SIZE_LIMIT")
        return payload

    @model_validator(mode="after")
    def valid_encoding(self):
        self.source_bytes()
        return self


class ImportTools(ImportSource):
    selected: list[str] = Field(min_length=1, max_length=20)
    expectedVersions: dict[str, Annotated[int, Field(strict=True, ge=0)]] = Field(
        default_factory=dict, max_length=20
    )
    effects: dict[
        str, Literal["UNCONFIRMED", "read-only", "creates-file", "external-write"]
    ] = Field(default_factory=dict, max_length=20)
    commandId: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_selection(self):
        if (
            len(set(self.selected)) != len(self.selected)
            or any(not n.strip() or len(n) > 200 for n in self.selected)
            or set(self.effects) - set(self.selected)
            or set(self.expectedVersions) - set(self.selected)
            or any(v < 0 for v in self.expectedVersions.values())
            or not self.commandId.strip()
        ):
            raise ValueError("TOOL_IMPORT_SELECTION_INVALID")
        return self


class ReviseTool(StrictWorkbenchModel):
    expectedVersion: int = Field(strict=True, ge=1)
    commandId: str = Field(min_length=1, max_length=200)
    content: ToolDraftContent


class ToolQuery(StrictWorkbenchModel):
    revision: str = Field(default="", max_length=200)


class ToolList(StrictWorkbenchModel):
    cursor: str = Field(default="", max_length=2048)
    pageSize: int = Field(default=25, ge=1, le=50)


class ToolDefinitionTargets:
    def is_known_exact_target(self, context, grant, *, connection=None):
        if grant.owner != OWNER or connection is None:
            return False
        if grant.action in {"IMPORT", "LIST", "READ_SCOPE", "MAINTAIN_SCOPE"}:
            return grant.exact_resource == COLLECTION
        if grant.action not in {"READ", "REVISE"}:
            return False
        table, expression = (
            ("definitions", "tool_id || ':aggregate'")
            if grant.action == "REVISE"
            else ("revisions", "tool_id || ':' || revision_id")
        )
        return (
            connection.execute(
                f"SELECT 1 FROM tool_definition.{table} WHERE namespace=%s AND "
                f"security_domain=%s AND {expression}=%s",
                (
                    context.scope.tenant_id,
                    context.scope.security_domain,
                    grant.exact_resource,
                ),
            ).fetchone()
            is not None
        )


def tool_definition_operations(repository, cursors):
    def require(call, action, target=COLLECTION):
        return require_tool_grant(call, ExactGrant(OWNER, action, target))

    def handle(call):
        scope = ScopeIdentity(
            call.context.scope.tenant_id, call.context.scope.security_domain
        )

        def read(tool_id, revision=""):
            head = repository.head(call.connection, scope, tool_id)
            if not head:
                raise ToolStorageError("TOOL_NOT_FOUND")
            revision = (
                revision or head["draft_revision_id"] or head["published_revision_id"]
            )
            require(call, "READ", tool_id + ":" + revision)
            return repository.read(call.connection, scope, tool_id, revision)

        try:
            if call.operation in {"PREVIEW_TOOL_IMPORT", "IMPORT_TOOL_DRAFTS"}:
                model = (
                    ImportTools
                    if call.operation == "IMPORT_TOOL_DRAFTS"
                    else ImportSource
                )
                command = model.model_validate(call.payload)
                payload = command.source_bytes()
                preview = import_preview(command.kind, payload)
                selected = (
                    set(command.selected)
                    if isinstance(command, ImportTools)
                    else {op["name"] for op in preview["operations"]}
                )
                existing = {}
                decisions = []
                for operation in preview["operations"]:
                    if operation["name"] not in selected:
                        continue
                    tool_id, _ = logical_identity(operation)
                    head = repository.head(call.connection, scope, tool_id)
                    if head:
                        revision = (
                            head["draft_revision_id"] or head["published_revision_id"]
                        )
                        require(call, "READ", tool_id + ":" + revision)
                        existing[operation["name"]] = {
                            "toolId": tool_id,
                            "revisionId": revision,
                            "aggregateVersion": head["aggregate_version"],
                        }
                        if (
                            isinstance(command, ImportTools)
                            and command.expectedVersions.get(operation["name"], 0) > 0
                        ):
                            decisions.append(
                                require(call, "REVISE", tool_id + ":aggregate")
                            )
                if call.operation == "PREVIEW_TOOL_IMPORT":
                    # Default preview excludes source payload and package code.
                    return {
                        "sourceDigest": preview["sourceDigest"],
                        "operations": [
                            {k: v for k, v in op.items() if k != "original"}
                            | {"existing": existing.get(op["name"])}
                            for op in preview["operations"]
                        ],
                        "files": preview.get("files", []),
                        "persisted": False,
                        "executionAuthorized": False,
                    }
                decision = require(call, "IMPORT")
                return repository.import_drafts(
                    call.connection,
                    scope,
                    command.kind,
                    payload,
                    command.selected,
                    command.expectedVersions,
                    effects=command.effects,
                    command_id=command.commandId,
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
            if call.operation == "READ_TOOL_IMPORT_ACCESS":
                require(call, "IMPORT")
                return {"allowed": True, "executionAuthorized": False}
            if call.operation == "REVISE_TOOL_DRAFT":
                command = ReviseTool.model_validate(call.payload)
                tool_id = call.path["tool_id"]
                read(tool_id)
                decision = require(call, "REVISE", tool_id + ":aggregate")
                return repository.revise_draft(
                    call.connection,
                    scope,
                    tool_id,
                    command.content,
                    expected_version=command.expectedVersion,
                    command_id=command.commandId,
                    actor_id=call.context.principal_id,
                    decision_id=decision.decision_id,
                )
            if call.operation == "READ_TOOL_DRAFT":
                return read(call.path["tool_id"], call.query.get("revision", ""))
            if call.operation == "READ_TOOL_IMPORT_RECEIPT":
                row = call.connection.execute(
                    "SELECT actor_id,result FROM tool_definition.receipts WHERE "
                    "namespace=%s AND security_domain=%s AND command_id=%s",
                    (scope.namespace, scope.security_domain, call.path["command_id"]),
                ).fetchone()
                if not row or row["actor_id"] != call.context.principal_id:
                    raise ToolStorageError("TOOL_COMMAND_NOT_FOUND")
                if row["result"].get("commandKind", "IMPORT") == "IMPORT":
                    require(call, "IMPORT")
                for item in row["result"]["items"]:
                    require(call, "READ", item["toolId"] + ":" + item["revisionId"])
                    if item.get("changed") and item["aggregateVersion"] > 1:
                        require(call, "REVISE", item["toolId"] + ":aggregate")
                return row["result"]
            query = ToolList.model_validate(call.query)
            route = json.dumps([ROOT, call.context.principal_id])
            after = (
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
            rows = call.connection.execute(
                "SELECT tool_id FROM tool_definition.definitions WHERE "
                "namespace=%s AND security_domain=%s AND tool_id>%s ORDER BY "
                "tool_id LIMIT %s",
                (
                    scope.namespace,
                    scope.security_domain,
                    after,
                    query.pageSize + 1,
                ),
            ).fetchall()
            items = []
            for row in rows[: query.pageSize]:
                try:
                    value = read(row["tool_id"])
                except AuthorityError as exc:
                    if str(exc) != "AUTHORIZATION_NOT_FOUND":
                        raise
                    continue
                items.append(
                    {
                        k: value[k]
                        for k in [
                            "toolId",
                            "revisionId",
                            "digest",
                            "aggregateVersion",
                            "draftRevisionId",
                            "publishedRevisionId",
                        ]
                    }
                    | {
                        "name": value["record"]["name"],
                        "purpose": value["record"]["purpose"],
                        "sourceKind": value["record"]["operation"]["source"]["kind"],
                    }
                )
            return {
                "items": items,
                "nextCursor": cursors.mint(
                    route=route,
                    context=call.context,
                    page_size=query.pageSize,
                    last_key=(rows[query.pageSize - 1]["tool_id"],),
                )
                if len(rows) > query.pageSize
                else None,
                "executionAuthorized": False,
            }
        except (ToolImportError, ToolStorageError) as exc:
            reason = str(exc)
            status = (
                404
                if reason.endswith("NOT_FOUND")
                else 409
                if reason.endswith("CONFLICT")
                else 422
            )
            raise WorkbenchOwnerError(reason, status) from exc
        except PostgresError as exc:
            raise WorkbenchOwnerError("TOOL_STORAGE_UNAVAILABLE", 503) from exc

    def admission(action):
        return lambda context, path, payload, query: (
            ExactGrant(OWNER, action, COLLECTION),
        )

    return (
        WorkbenchOperation(
            "READ_TOOL_IMPORT_ACCESS",
            "GET",
            ROOT + "/import-access",
            None,
            None,
            admission("IMPORT"),
            handle,
        ),
        WorkbenchOperation(
            "REVISE_TOOL_DRAFT",
            "POST",
            ROOT + "/{tool_id}/draft",
            ReviseTool,
            None,
            admission("LIST"),
            handle,
        ),
        WorkbenchOperation(
            "PREVIEW_TOOL_IMPORT",
            "POST",
            ROOT + "/import-preview",
            ImportSource,
            None,
            admission("IMPORT"),
            handle,
        ),
        WorkbenchOperation(
            "IMPORT_TOOL_DRAFTS",
            "POST",
            ROOT + "/imports",
            ImportTools,
            None,
            admission("IMPORT"),
            handle,
        ),
        WorkbenchOperation(
            "READ_TOOL_IMPORT_RECEIPT",
            "GET",
            ROOT + "/imports/{command_id}",
            None,
            None,
            admission("LIST"),
            handle,
        ),
        WorkbenchOperation(
            "LIST_TOOL_DRAFTS", "GET", ROOT, None, ToolList, admission("LIST"), handle
        ),
        WorkbenchOperation(
            "READ_TOOL_DRAFT",
            "GET",
            ROOT + "/{tool_id}",
            None,
            ToolQuery,
            admission("LIST"),
            handle,
        ),
    )
