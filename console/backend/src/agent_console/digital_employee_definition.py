"""Independent employee composition values and authorization-first application port."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Protocol

from .execution_domain import ScopeIdentity


class EmployeeDefinitionError(ValueError):
    """Bounded error; unauthorized and absent identities share NOT_FOUND."""


class MemberKind(StrEnum):
    AGENT = "AGENT"
    WORKFLOW = "WORKFLOW"
    SKILL = "SKILL"
    MCP = "MCP"
    KNOWLEDGE = "KNOWLEDGE"
    RUNTIME_PROFILE = "RUNTIME_PROFILE"


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}", value
    ):
        raise EmployeeDefinitionError("INVALID_IDENTITY")
    return value


def digest_bytes(value: object) -> bytes:
    def normalize(item):
        if isinstance(item, str):
            return unicodedata.normalize("NFC", item)
        if isinstance(item, dict):
            return {key: normalize(val) for key, val in item.items()}
        if isinstance(item, (tuple, list)):
            return [normalize(val) for val in item]
        if item is None or type(item) in (bool, int):
            return item
        raise EmployeeDefinitionError("INVALID_CANONICAL_VALUE")

    return json.dumps(
        normalize(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def digest(value: object) -> str:
    return hashlib.sha256(digest_bytes(value)).hexdigest()


@dataclass(frozen=True)
class CompositionMember:
    kind: MemberKind
    resource_id: str
    revision_id: str
    digest: str

    def __post_init__(self):
        if not isinstance(self.kind, MemberKind):
            raise EmployeeDefinitionError("UNSUPPORTED_DIRECT_MEMBER")
        identifier(self.resource_id)
        identifier(self.revision_id)
        if not re.fullmatch(r"(?:sha256:)?[a-f0-9]{64}", self.digest):
            raise EmployeeDefinitionError("INVALID_MEMBER_DIGEST")


@dataclass(frozen=True)
class EmployeeRevision:
    scope: ScopeIdentity
    definition_id: str
    revision_id: str
    role: str
    responsibilities: tuple[str, ...]
    members: tuple[CompositionMember, ...]
    predecessor_revision_id: str | None = None

    def __post_init__(self):
        identifier(self.definition_id)
        identifier(self.revision_id)
        if self.predecessor_revision_id is not None:
            identifier(self.predecessor_revision_id)
            if self.predecessor_revision_id == self.revision_id:
                raise EmployeeDefinitionError("INVALID_PREDECESSOR")
        if not isinstance(self.scope, ScopeIdentity):
            raise EmployeeDefinitionError("INVALID_SCOPE")
        if (
            not self.role.strip()
            or len(self.role) > 200
            or not 1 <= len(self.responsibilities) <= 32
        ):
            raise EmployeeDefinitionError("INVALID_ROLE")
        if any(
            not value.strip() or len(value) > 500 for value in self.responsibilities
        ):
            raise EmployeeDefinitionError("INVALID_RESPONSIBILITY")
        if not 1 <= len(self.members) <= 128 or any(
            not isinstance(m, CompositionMember) for m in self.members
        ):
            raise EmployeeDefinitionError("INVALID_COMPOSITION")
        if sum(m.kind is MemberKind.AGENT for m in self.members) != 1:
            raise EmployeeDefinitionError("PRIMARY_AGENT_CARDINALITY")
        if sum(m.kind is MemberKind.RUNTIME_PROFILE for m in self.members) > 1:
            raise EmployeeDefinitionError("DEFAULT_RUNTIME_CARDINALITY")
        keys = [(m.kind, m.resource_id) for m in self.members]
        if len(keys) != len(set(keys)):
            raise EmployeeDefinitionError("DUPLICATE_COMPOSITION_MEMBER")

    @property
    def record(self):
        return {
            "schemaVersion": "digital-employee-composition.v1",
            "namespace": self.scope.namespace,
            "securityDomain": self.scope.security_domain,
            "definitionId": self.definition_id,
            "revisionId": self.revision_id,
            "role": self.role,
            "responsibilities": self.responsibilities,
            "members": [
                asdict(m)
                for m in sorted(self.members, key=lambda m: (m.kind, m.resource_id))
            ],
            "predecessorRevisionId": self.predecessor_revision_id,
        }

    @property
    def digest(self):
        return digest(self.record)

    @classmethod
    def from_record(cls, record):
        return cls(
            ScopeIdentity(record["namespace"], record["securityDomain"]),
            record["definitionId"],
            record["revisionId"],
            record["role"],
            tuple(record["responsibilities"]),
            tuple(
                CompositionMember(
                    MemberKind(m["kind"]),
                    m["resource_id"],
                    m["revision_id"],
                    m["digest"],
                )
                for m in record["members"]
            ),
            record["predecessorRevisionId"],
        )


class EmployeeAuthorization(Protocol):
    def require(self, scope: ScopeIdentity, action: str, identity: str) -> str:
        """Return trusted decision identity or raise nondisclosing NOT_FOUND."""
        ...


@dataclass(frozen=True)
class ScopedEmployeeAuthorization:
    """Already-authenticated application permission context, never a wire DTO."""

    scope: ScopeIdentity
    actor_id: str
    permissions: frozenset[str]
    decision_id: str

    def require(self, scope, action, identity):
        if scope != self.scope or action not in self.permissions or not self.actor_id:
            raise EmployeeDefinitionError("EMPLOYEE_NOT_FOUND")
        return identifier(self.decision_id)


class PublishedEmployeeDefinitionAuthority:
    def __init__(self, repository, authorization):
        self.repository = repository
        self.authorization = authorization

    def resolve(self, scope, definition_id, revision_id):
        from .digital_employee_application import DefinitionReference

        self.authorization.require(scope, "INSTANTIATE", definition_id)
        row = self.repository.read(scope, definition_id, revision_id)
        revision = EmployeeRevision.from_record(row["revision"])
        for member in revision.members:
            self.authorization.require(scope, "READ_MEMBER", member.resource_id)
        agent = next(m for m in revision.members if m.kind is MemberKind.AGENT)
        return DefinitionReference(
            definition_id,
            revision_id,
            row["digest"],
            row["published"],
            row["published"],
            "DIGITAL_EMPLOYEE_DEFINITION_V1",
            agent.resource_id,
            agent.revision_id,
            agent.digest,
        )


class EmployeeDefinitionRepository(Protocol):
    def create(
        self,
        revision: EmployeeRevision,
        *,
        expected_version: int,
        decision_id: str,
        command_id: str,
    ): ...
    def list(self, scope: ScopeIdentity): ...
    def read(self, scope: ScopeIdentity, definition_id: str, revision_id: str): ...
    def decide(
        self,
        scope: ScopeIdentity,
        definition_id: str,
        revision_id: str,
        revision_digest: str,
        action: str,
        *,
        expected_version: int,
        decision_id: str,
        command_id: str,
    ): ...


class EmployeeDefinitionService:
    def __init__(
        self,
        repository: EmployeeDefinitionRepository,
        authorization: EmployeeAuthorization,
    ):
        self.repository = repository
        self.authorization = authorization

    def create(
        self, revision: EmployeeRevision, *, expected_version: int, command_id: str
    ):
        decision = self.authorization.require(
            revision.scope, "CREATE", revision.definition_id
        )
        return self.repository.create(
            revision,
            expected_version=expected_version,
            decision_id=decision,
            command_id=command_id,
        )

    def read(self, scope, definition_id, revision_id):
        self.authorization.require(scope, "READ", definition_id)
        return self.repository.read(scope, definition_id, revision_id)

    def list(self, scope):
        self.authorization.require(scope, "LIST", "employee-definitions")
        return self.repository.list(scope)

    def decide(
        self,
        scope,
        definition_id,
        revision_id,
        revision_digest,
        action,
        *,
        expected_version,
        command_id,
    ):
        decision = self.authorization.require(scope, action, definition_id)
        if action in {"VALIDATE", "APPROVE", "PUBLISH", "GRANT_MATCH"}:
            current = self.repository.read(scope, definition_id, revision_id)
            for member in current["revision"]["members"]:
                self.authorization.require(scope, "READ_MEMBER", member["resource_id"])
        return self.repository.decide(
            scope,
            definition_id,
            revision_id,
            revision_digest,
            action,
            expected_version=expected_version,
            decision_id=decision,
            command_id=command_id,
        )
