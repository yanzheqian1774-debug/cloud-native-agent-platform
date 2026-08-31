"""Typed repository port for authoritative Knowledge operations."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class KnowledgeRepositoryError(RuntimeError):
    """Stable, non-disclosing storage failure."""


class KnowledgeConflict(KnowledgeRepositoryError):
    pass


class KnowledgeNotFound(KnowledgeRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class KnowledgeScope:
    namespace: str
    security_domain: str


class KnowledgeRepository(Protocol):
    def compatibility(self) -> None: ...
    def get(self, scope: KnowledgeScope, knowledge_id: str) -> dict[str, Any]: ...
    def list(self, scope: KnowledgeScope) -> list[dict[str, Any]]: ...
    def create(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]: ...
    def tombstone(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None: ...
    def put_quality_entity(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def list_quality_entities(
        self, scope: KnowledgeScope, entity_type: str | None = None
    ) -> list[dict[str, Any]]: ...


class InMemoryKnowledgeRepository:
    """Focused test adapter; never a deployment fallback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._tombstones: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._quality: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._lock = threading.RLock()

    def compatibility(self) -> None:
        return None

    @staticmethod
    def _key(scope: KnowledgeScope, knowledge_id: str) -> tuple[str, str, str]:
        return scope.namespace, scope.security_domain, knowledge_id

    def get(self, scope: KnowledgeScope, knowledge_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._records.get(self._key(scope, knowledge_id))
            if value is None:
                raise KnowledgeNotFound("KNOWLEDGE_NOT_FOUND")
            return copy.deepcopy(value)

    def list(self, scope: KnowledgeScope) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(value)
                for key, value in sorted(self._records.items())
                if key[:2] == (scope.namespace, scope.security_domain)
            ]

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        scope = KnowledgeScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["knowledgeId"])
        with self._lock:
            if key in self._records or key in self._tombstones:
                raise KnowledgeConflict("KNOWLEDGE_CONFLICT")
            self._records[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        scope = KnowledgeScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["knowledgeId"])
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise KnowledgeNotFound("KNOWLEDGE_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise KnowledgeConflict("STALE_KNOWLEDGE")
            stored = copy.deepcopy(record)
            stored["facts"] = [*current["facts"], copy.deepcopy(fact)]
            self._records[key] = stored
            return copy.deepcopy(stored)

    def tombstone(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        key = self._key(scope, knowledge_id)
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise KnowledgeNotFound("KNOWLEDGE_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise KnowledgeConflict("STALE_KNOWLEDGE")
            self._tombstones[key] = copy.deepcopy(tombstone)
            del self._records[key]

    def put_quality_entity(self, record: dict[str, Any]) -> dict[str, Any]:
        key = (
            record["namespace"],
            record["securityDomain"],
            record["entityType"],
            record["entityId"],
        )
        with self._lock:
            self._quality[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def list_quality_entities(
        self, scope: KnowledgeScope, entity_type: str | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(value)
                for key, value in sorted(self._quality.items())
                if key[:2] == (scope.namespace, scope.security_domain)
                and (entity_type is None or key[2] == entity_type)
            ]
