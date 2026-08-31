"""Typed persistence port for governed Skill and MCP resources."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class SkillMcpRepositoryError(RuntimeError):
    pass


class SkillMcpConflict(SkillMcpRepositoryError):
    pass


class SkillMcpNotFound(SkillMcpRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class ResourceScope:
    namespace: str
    security_domain: str


class SkillMcpRepository(Protocol):
    def compatibility(self) -> None: ...
    def get(
        self, scope: ResourceScope, kind: str, resource_id: str
    ) -> dict[str, Any]: ...
    def list(self, scope: ResourceScope, kind: str) -> list[dict[str, Any]]: ...
    def create(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]: ...
    def delete_draft(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None: ...


class InMemorySkillMcpRepository:
    """Conformance adapter; never a deployment fallback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._tombstones: set[tuple[str, str, str, str]] = set()
        self._lock = threading.RLock()

    def compatibility(self) -> None:
        return None

    @staticmethod
    def _key(
        scope: ResourceScope, kind: str, resource_id: str
    ) -> tuple[str, str, str, str]:
        return scope.namespace, scope.security_domain, kind, resource_id

    def get(self, scope: ResourceScope, kind: str, resource_id: str) -> dict[str, Any]:
        with self._lock:
            value = self._records.get(self._key(scope, kind, resource_id))
            if value is None:
                raise SkillMcpNotFound("RESOURCE_NOT_FOUND")
            return copy.deepcopy(value)

    def list(self, scope: ResourceScope, kind: str) -> list[dict[str, Any]]:
        with self._lock:
            return [
                copy.deepcopy(v)
                for k, v in sorted(self._records.items())
                if k[:3] == (scope.namespace, scope.security_domain, kind)
            ]

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        scope = ResourceScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["kind"], record["resourceId"])
        with self._lock:
            if key in self._records or key in self._tombstones:
                raise SkillMcpConflict("RESOURCE_CONFLICT")
            self._records[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]:
        scope = ResourceScope(record["namespace"], record["securityDomain"])
        key = self._key(scope, record["kind"], record["resourceId"])
        with self._lock:
            current = self._records.get(key)
            if current is None or current["aggregateVersion"] != expected_version:
                raise SkillMcpConflict("STALE_RESOURCE")
            value = copy.deepcopy(record)
            value["facts"].append(copy.deepcopy(fact))
            self._records[key] = value
            return copy.deepcopy(value)

    def delete_draft(
        self,
        scope: ResourceScope,
        kind: str,
        resource_id: str,
        *,
        expected_version: int,
        tombstone: dict[str, Any],
    ) -> None:
        key = self._key(scope, kind, resource_id)
        with self._lock:
            current = self._records.get(key)
            if (
                current is None
                or current["aggregateVersion"] != expected_version
                or current["publishedRevisionId"]
            ):
                raise SkillMcpConflict("PROTECTED_OR_STALE_RESOURCE")
            del self._records[key]
            self._tombstones.add(key)
