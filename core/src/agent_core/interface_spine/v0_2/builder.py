"""Dependency-injected orchestration of A2 envelope construction."""

from collections.abc import Callable

from agent_core.representation.v0_2 import (
    NativeCorrelationId,
    PlatformExecutionIdentity,
    mint_platform_execution_identity,
)

from .envelope import InternalExecutionEnvelope, SourceTaskRef
from .errors import NativeIdentitySubstitutionError
from .projection import DefinitionFacingRequest, project_definition
from .selection import InstanceSelectionRequest, InstanceSelector

ExecutionIdentityMinter = Callable[[], PlatformExecutionIdentity]


class ExecutionEnvelopeBuilder:
    def __init__(
        self,
        *,
        selector: InstanceSelector,
        identity_minter: ExecutionIdentityMinter = mint_platform_execution_identity,
    ) -> None:
        self._selector = selector
        self._identity_minter = identity_minter

    def build(self, request: DefinitionFacingRequest) -> InternalExecutionEnvelope:
        projection = project_definition(request)
        selected = self._selector.select(
            InstanceSelectionRequest(
                definition_ref=projection.definition_ref,
                desired_runtime_binding=projection.desired_runtime_binding,
            )
        )
        execution_identity = self._identity_minter()
        if isinstance(execution_identity, NativeCorrelationId):
            raise NativeIdentitySubstitutionError(
                "identity minter returned a native correlation ID"
            )
        source_task_ref = None
        if request.source_task_name is not None:
            source_task_ref = SourceTaskRef(request.namespace, request.source_task_name)
        return InternalExecutionEnvelope(
            definition_ref=projection.definition_ref,
            selected_instance_id=selected.instance_id,
            execution_identity=execution_identity,
            desired_runtime_binding=selected.desired_runtime_binding,
            effective_runtime_binding=selected.effective_runtime_binding,
            selection_evidence=selected.evidence,
            source_task_ref=source_task_ref,
        )
