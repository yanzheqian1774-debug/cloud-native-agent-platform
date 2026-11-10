"""Team-local duties over exact employee references; no execution authority."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .digital_employee_definition import digest, identifier
from .execution_domain import ScopeIdentity


class TeamDefinitionError(ValueError):
    """Bounded team-content validation failure."""


def _text(value: str, limit: int, code: str, *, optional: bool = False) -> None:
    if not isinstance(value, str) or len(value) > limit:
        raise TeamDefinitionError(code)
    if not optional and not value.strip():
        raise TeamDefinitionError(code)
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise TeamDefinitionError(code)


def _identity(value: str) -> None:
    try:
        identifier(value)
    except ValueError as exc:
        raise TeamDefinitionError("TEAM_IDENTITY_INVALID") from exc


@dataclass(frozen=True)
class TeamMember:
    employee_definition_id: str
    employee_revision_id: str
    employee_digest: str
    responsibility: str
    handoff: str = ""

    def __post_init__(self) -> None:
        _identity(self.employee_definition_id)
        _identity(self.employee_revision_id)
        value = self.employee_digest
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise TeamDefinitionError("TEAM_MEMBER_DIGEST_INVALID")
        _text(self.responsibility, 1000, "TEAM_RESPONSIBILITY_INVALID")
        _text(self.handoff, 1000, "TEAM_HANDOFF_INVALID", optional=True)


@dataclass(frozen=True)
class TeamRevision:
    scope: ScopeIdentity
    team_id: str
    revision_id: str
    title: str
    goal: str
    owner_id: str
    members: tuple[TeamMember, ...]
    predecessor_revision_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.scope, ScopeIdentity):
            raise TeamDefinitionError("TEAM_SCOPE_REQUIRED")
        for value in (self.team_id, self.revision_id, self.owner_id):
            _identity(value)
        if self.predecessor_revision_id is not None:
            _identity(self.predecessor_revision_id)
            if self.predecessor_revision_id == self.revision_id:
                raise TeamDefinitionError("TEAM_PREDECESSOR_INVALID")
        _text(self.title, 120, "TEAM_TITLE_INVALID")
        _text(self.goal, 2000, "TEAM_GOAL_INVALID")
        if (
            not isinstance(self.members, tuple)
            or not 1 <= len(self.members) <= 32
            or any(not isinstance(member, TeamMember) for member in self.members)
        ):
            raise TeamDefinitionError("TEAM_MEMBERS_INVALID")
        if len({m.employee_definition_id for m in self.members}) != len(self.members):
            raise TeamDefinitionError("TEAM_MEMBER_DUPLICATE")

    def canonical_record(self) -> dict:
        return {"schemaVersion": "team-definition.v1", **asdict(self)}

    @classmethod
    def from_record(cls, record: dict) -> TeamRevision:
        """Reject malformed stored content instead of silently dropping fields."""
        try:
            value = dict(record)
            if value.pop("schemaVersion") != "team-definition.v1":
                raise ValueError("schema")
            value["scope"] = ScopeIdentity(**value["scope"])
            value["members"] = tuple(TeamMember(**m) for m in value["members"])
            return cls(**value)
        except (KeyError, TypeError, ValueError) as exc:
            raise TeamDefinitionError("TEAM_RECORD_CORRUPT") from exc

    @property
    def content_digest(self) -> str:
        return digest(self.canonical_record())
