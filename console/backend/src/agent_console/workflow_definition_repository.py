"""Typed scoped persistence port for Workflow Definitions."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class WorkflowDefinitionRepositoryError(RuntimeError):
    pass


class WorkflowDefinitionConflict(WorkflowDefinitionRepositoryError):
    pass


class WorkflowDefinitionNotFound(WorkflowDefinitionRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowScope:
    namespace: str
    security_domain: str


class WorkflowDefinitionRepository(Protocol):
    def compatibility(self) -> None: ...
    def get(self, scope: WorkflowScope, resource_id: str) -> dict[str, Any]: ...
    def list(self, scope: WorkflowScope) -> list[dict[str, Any]]: ...
    def create(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]: ...


class InMemoryWorkflowDefinitionRepository:
    """Focused test adapter; never a deployment fallback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = threading.RLock()

    def compatibility(self) -> None:
        return None

    @staticmethod
    def _key(scope: WorkflowScope, resource_id: str):
        return scope.namespace, scope.security_domain, resource_id

    def get(self, scope: WorkflowScope, resource_id: str):
        with self._lock:
            value = self._records.get(self._key(scope, resource_id))
            if value is None:
                raise WorkflowDefinitionNotFound("WORKFLOW_DEFINITION_NOT_FOUND")
            return copy.deepcopy(value)

    def list(self, scope: WorkflowScope):
        with self._lock:
            return [
                copy.deepcopy(v)
                for k, v in sorted(self._records.items())
                if k[:2] == (scope.namespace, scope.security_domain)
            ]

    def create(self, record):
        key = (
            record["namespace"],
            record["securityDomain"],
            record["workflowDefinitionId"],
        )
        with self._lock:
            if key in self._records:
                raise WorkflowDefinitionConflict("WORKFLOW_DEFINITION_CONFLICT")
            self._records[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def replace(self, record, *, expected_version, fact):
        key = (
            record["namespace"],
            record["securityDomain"],
            record["workflowDefinitionId"],
        )
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise WorkflowDefinitionNotFound("WORKFLOW_DEFINITION_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise WorkflowDefinitionConflict("STALE_WORKFLOW_DEFINITION")
            stored = copy.deepcopy(record)
            stored["facts"] = [*current["facts"], copy.deepcopy(fact)]
            self._records[key] = stored
            return copy.deepcopy(stored)
