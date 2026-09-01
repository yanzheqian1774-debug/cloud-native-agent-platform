"""Typed scoped persistence port for Runtime Profiles."""

from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Protocol


class RuntimeProfileRepositoryError(RuntimeError):
    pass


class RuntimeProfileConflict(RuntimeProfileRepositoryError):
    pass


class RuntimeProfileNotFound(RuntimeProfileRepositoryError):
    pass


@dataclass(frozen=True, slots=True)
class RuntimeProfileScope:
    namespace: str
    security_domain: str


class RuntimeProfileRepository(Protocol):
    def compatibility(self) -> None: ...
    def get(self, scope: RuntimeProfileScope, resource_id: str) -> dict[str, Any]: ...
    def list(self, scope: RuntimeProfileScope) -> list[dict[str, Any]]: ...
    def create(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def replace(
        self, record: dict[str, Any], *, expected_version: int, fact: dict[str, Any]
    ) -> dict[str, Any]: ...


class InMemoryRuntimeProfileRepository:
    """Focused test adapter; never a deployment fallback."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._lock = threading.RLock()

    def compatibility(self) -> None:
        return None

    @staticmethod
    def _key(scope: RuntimeProfileScope, resource_id: str):
        return scope.namespace, scope.security_domain, resource_id

    def get(self, scope, resource_id):
        with self._lock:
            value = self._records.get(self._key(scope, resource_id))
            if value is None:
                raise RuntimeProfileNotFound("RUNTIME_PROFILE_NOT_FOUND")
            return copy.deepcopy(value)

    def list(self, scope):
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
            record["runtimeProfileId"],
        )
        with self._lock:
            if key in self._records:
                raise RuntimeProfileConflict("RUNTIME_PROFILE_CONFLICT")
            self._records[key] = copy.deepcopy(record)
            return copy.deepcopy(record)

    def replace(self, record, *, expected_version, fact):
        key = (
            record["namespace"],
            record["securityDomain"],
            record["runtimeProfileId"],
        )
        with self._lock:
            current = self._records.get(key)
            if current is None:
                raise RuntimeProfileNotFound("RUNTIME_PROFILE_NOT_FOUND")
            if current["aggregateVersion"] != expected_version:
                raise RuntimeProfileConflict("STALE_RUNTIME_PROFILE")
            stored = copy.deepcopy(record)
            stored["facts"] = [*current["facts"], copy.deepcopy(fact)]
            self._records[key] = stored
            return copy.deepcopy(stored)
