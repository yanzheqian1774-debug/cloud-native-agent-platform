"""Typed persistence port for the Agent Definition lifecycle."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class AgentDefinitionRepositoryError(RuntimeError):
    """Stable storage failure without persistence details."""


class AgentDefinitionConflict(AgentDefinitionRepositoryError):
    pass


class AgentDefinitionNotFound(AgentDefinitionRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class DefinitionScope:
    namespace: str
    security_domain: str


class AgentDefinitionRepository(Protocol):
    def compatibility(self) -> None: ...

    def get(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]: ...

    def list(self, scope: DefinitionScope) -> list[dict[str, Any]]: ...

    def create(self, record: dict[str, Any]) -> dict[str, Any]: ...

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]: ...

    def delete_draft(
        self,
        scope: DefinitionScope,
        definition_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None: ...


class InMemoryAgentDefinitionRepository:
    """Focused conformance/test adapter; never a deployment fallback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._tombstones: set[tuple[str, str, str]] = set()
        self._lock = threading.RLock()

    def compatibility(self) -> None:
        return None

    @staticmethod
    def _key(scope: DefinitionScope, definition_id: str) -> tuple[str, str, str]:
        return scope.namespace, scope.security_domain, definition_id

    def get(self, scope: DefinitionScope, definition_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._records.get(self._key(scope, definition_id))
            if item is None:
                raise AgentDefinitionNotFound("AGENT_DEFINITION_NOT_FOUND")
            return copy.deepcopy(item)

    def list(self, scope: DefinitionScope) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(item)
                for key, item in sorted(self._records.items())
                if key[:2] == (scope.namespace, scope.security_domain)
            ]

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        scope = DefinitionScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["definitionId"])
        with self._lock:
            if key in self._records or key in self._tombstones:
                raise AgentDefinitionConflict("AGENT_DEFINITION_CONFLICT")
            self._records[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        scope = DefinitionScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["definitionId"])
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise AgentDefinitionNotFound("AGENT_DEFINITION_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise AgentDefinitionConflict("STALE_AGENT_DEFINITION")
            stored = copy.deepcopy(record)
            stored["facts"] = [*current["facts"], copy.deepcopy(fact)]
            self._records[key] = stored
            return copy.deepcopy(stored)

    def delete_draft(
        self,
        scope: DefinitionScope,
        definition_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        key = self._key(scope, definition_id)
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise AgentDefinitionNotFound("AGENT_DEFINITION_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise AgentDefinitionConflict("STALE_AGENT_DEFINITION")
            self._tombstones.add(key)
            del self._records[key]
