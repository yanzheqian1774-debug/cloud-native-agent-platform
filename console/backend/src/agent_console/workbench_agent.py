"""Trusted Workbench adapter for one exact Agent Definition revision."""

from __future__ import annotations

from typing import Any

from agent_console.agent_definition_repository import (
    AgentDefinitionNotFound,
    AgentDefinitionRepository,
    AgentDefinitionRepositoryError,
    DefinitionScope,
)
from agent_console.agent_definition_service import agent_revision_digest
from agent_console.authority_contracts import ExactGrant
from agent_console.workbench_bff import PREFIX, WorkbenchOperation
from agent_console.workbench_bff_schemas import (
    WorkbenchAgentPage,
    WorkbenchAgentRevision,
    WorkbenchAgentSummary,
    WorkbenchPageQuery,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from agent_console.workbench_pagination import WorkbenchCursorCodec


class AgentDefinitionOwnerAdapter:
    """Read and verify one Agent revision on the authorization transaction."""

    def __init__(self, repository: AgentDefinitionRepository) -> None:
        self.repository = repository

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        if call.operation != "READ_AGENT_REVISION":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        scope = DefinitionScope(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            value = self.repository.read_revision_for_workbench(
                call.connection,
                scope,
                call.path["definition_id"],
                call.path["revision_id"],
                authorized=True,
            )
            record, revision = value["record"], value["revision"]
            if revision.get("digest") != agent_revision_digest(record, revision):
                raise AgentDefinitionRepositoryError("AGENT_DEFINITION_RECORD_CORRUPT")
            content = revision["content"]
            result = WorkbenchAgentRevision(
                definitionId=record["definitionId"],
                revisionId=revision["revisionId"],
                digest=revision["digest"],
                name=record["name"],
                role={
                    "title": content["title"],
                    "duties": content["duties"],
                    "businessPurpose": content["businessPurpose"],
                    "capabilities": content["capabilities"],
                },
            )
        except AgentDefinitionNotFound as exc:
            raise WorkbenchOwnerError("AGENT_NOT_FOUND", 404) from exc
        except (AgentDefinitionRepositoryError, KeyError, TypeError, ValueError) as exc:
            raise WorkbenchOwnerError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE", 503
            ) from exc
        return result.model_dump(mode="json")


class AgentDefinitionListOwnerAdapter:
    """List only formal published-revision summaries on the caller transaction."""

    ROUTE = "AGENT_LIST"

    def __init__(
        self,
        repository: AgentDefinitionRepository,
        cursors: WorkbenchCursorCodec,
    ) -> None:
        self.repository = repository
        self.cursors = cursors

    @staticmethod
    def _summary(record: dict[str, Any]) -> WorkbenchAgentSummary:
        revision_id = record["publishedRevisionId"]
        revisions = [
            revision
            for revision in record["revisions"]
            if revision.get("revisionId") == revision_id
        ]
        if len(revisions) != 1:
            raise AgentDefinitionRepositoryError("AGENT_DEFINITION_RECORD_CORRUPT")
        revision = revisions[0]
        if revision.get("state") != "PUBLISHED" or revision.get(
            "digest"
        ) != agent_revision_digest(record, revision):
            raise AgentDefinitionRepositoryError("AGENT_DEFINITION_RECORD_CORRUPT")
        return WorkbenchAgentSummary(
            definitionId=record["definitionId"],
            name=record["name"],
            revisionId=revision["revisionId"],
            digest=revision["digest"],
            title=revision["content"]["title"],
            enabled=record["enabled"],
            archived=record["archived"],
        )

    def __call__(self, call: AuthorizedOwnerCall) -> dict[str, Any]:
        if call.operation != "LIST_AGENTS":
            raise WorkbenchOwnerError("WORKBENCH_OPERATION_INVALID", 500)
        page_size = call.query["pageSize"]
        after = None
        if cursor := call.query.get("cursor"):
            after = self.cursors.resolve(
                cursor,
                route=self.ROUTE,
                context=call.context,
                page_size=page_size,
                key_size=1,
            )[0]
        scope = DefinitionScope(
            call.context.scope.tenant_id,
            call.context.scope.security_domain,
        )
        try:
            records = self.repository.list_published_for_workbench(
                call.connection,
                scope,
                after_definition_id=after,
                limit=page_size + 1,
                authorized=True,
            )
            page_records = records[:page_size]
            items = tuple(self._summary(record) for record in page_records)
            keys = [item.definitionId for item in items]
            if keys != sorted(keys, key=lambda value: value.encode("utf-8")) or len(
                keys
            ) != len(set(keys)):
                raise AgentDefinitionRepositoryError("AGENT_DEFINITION_RECORD_CORRUPT")
        except (AgentDefinitionRepositoryError, KeyError, TypeError, ValueError) as exc:
            raise WorkbenchOwnerError(
                "AGENT_DEFINITION_STORAGE_UNAVAILABLE", 503
            ) from exc
        next_cursor = None
        if len(records) > page_size:
            next_cursor = self.cursors.mint(
                route=self.ROUTE,
                context=call.context,
                page_size=page_size,
                last_key=(items[-1].definitionId,),
            )
        return WorkbenchAgentPage(items=items, nextCursor=next_cursor).model_dump(
            mode="json", exclude_none=True
        )


def _agent_revision_read(context, path, payload, query):
    return (
        ExactGrant(
            "AGENT",
            "READ",
            f"agent:{path['definition_id']}:{path['revision_id']}",
        ),
    )


def _agent_list(context, path, payload, query):
    return (ExactGrant("AGENT", "LIST", "agent:collection"),)


def agent_operations(
    repository: AgentDefinitionRepository,
    cursors: WorkbenchCursorCodec,
) -> tuple[WorkbenchOperation, ...]:
    return (
        WorkbenchOperation(
            "LIST_AGENTS",
            "GET",
            f"{PREFIX}/agents",
            None,
            WorkbenchPageQuery,
            _agent_list,
            AgentDefinitionListOwnerAdapter(repository, cursors),
        ),
        WorkbenchOperation(
            "READ_AGENT_REVISION",
            "GET",
            f"{PREFIX}/agents/{{definition_id}}/revisions/{{revision_id}}",
            None,
            None,
            _agent_revision_read,
            AgentDefinitionOwnerAdapter(repository),
        ),
    )
