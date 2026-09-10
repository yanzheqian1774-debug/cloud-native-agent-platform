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
from agent_console.workbench_bff_schemas import WorkbenchAgentRevision
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)


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


def _agent_revision_read(context, path, payload, query):
    return (
        ExactGrant(
            "AGENT",
            "READ",
            f"agent:{path['definition_id']}:{path['revision_id']}",
        ),
    )


def agent_operations(
    repository: AgentDefinitionRepository,
) -> tuple[WorkbenchOperation, ...]:
    return (
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
