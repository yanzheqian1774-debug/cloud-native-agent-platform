"""Internal immutable ``solution-blueprint.v1`` logical contract."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum

SCHEMA_VERSION = "solution-blueprint.v1"
DIGEST_DOMAIN = "agent-console:solution-blueprint.v1"
IDENTIFIER_LIMIT = 200
TEXT_LIMIT = 2_000
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


class BlueprintContractError(ValueError):
    """Stable contract validation failure."""


def _fail(code: str) -> BlueprintContractError:
    return BlueprintContractError(code)


def identifier(value: object, code: str = "INVALID_IDENTIFIER") -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or len(normalized) > IDENTIFIER_LIMIT:
        raise _fail(code if not normalized else "IDENTIFIER_LIMIT_EXCEEDED")
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise _fail(code)
    return normalized


def digest(value: object, code: str = "INVALID_DIGEST") -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise _fail(code)
    return value


def utc(value: object, code: str = "INVALID_UTC_TIMESTAMP") -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _fail(code)
    offset = value.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise _fail(code)
    return value.astimezone(UTC)


def text(value: object, code: str = "INVALID_SEMANTIC_TEXT") -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized or len(normalized) > TEXT_LIMIT:
        raise _fail(code if not normalized else "SEMANTIC_TEXT_LIMIT_EXCEEDED")
    return normalized


def semantic_set(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _fail(code)
    items = tuple(text(item, code) for item in value)
    if len(set(items)) != len(items):
        raise _fail("AMBIGUOUS_SEMANTIC_SET")
    return tuple(sorted(items))


def _canonical(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return utc(value).isoformat().replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        pairs = [
            (unicodedata.normalize("NFC", key), item) for key, item in value.items()
        ]
        if len({key for key, _ in pairs}) != len(pairs):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        return {key: _canonical(item) for key, item in sorted(pairs)}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")


def canonical_json(value: object) -> str:
    return json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_bytes(value: object, *, domain: str = DIGEST_DOMAIN) -> bytes:
    prefix = identifier(domain, "INVALID_DIGEST_DOMAIN")
    return f"{prefix}\n{canonical_json(value)}".encode()


def canonical_sha256(value: object, *, domain: str = DIGEST_DOMAIN) -> str:
    return hashlib.sha256(canonical_bytes(value, domain=domain)).hexdigest()


@dataclass(frozen=True, slots=True, order=True)
class AssetReference:
    asset_id: str
    version_id: str
    canonical_digest: str

    @classmethod
    def create(
        cls, *, asset_id: object, version_id: object, canonical_digest: object
    ) -> AssetReference:
        return cls(
            identifier(asset_id), identifier(version_id), digest(canonical_digest)
        )


@dataclass(frozen=True, slots=True)
class SolutionBlueprint:
    blueprint_id: str
    version_id: str
    canonical_digest: str
    tenant_id: str
    security_domain: str
    created_at: datetime
    source_authority_revisions: tuple[AssetReference, ...]
    provenance_classification: str
    lifecycle_decision_references: tuple[str, ...]
    problem_intent: str
    business_scope: tuple[str, ...]
    applicability_constraints: tuple[str, ...]
    exclusion_constraints: tuple[str, ...]
    canonical_workflow_revision: AssetReference
    role_definition_references: tuple[AssetReference, ...]
    skill_references: tuple[AssetReference, ...]
    mcp_capability_references: tuple[AssetReference, ...]
    knowledge_references: tuple[AssetReference, ...]
    runtime_requirement_references: tuple[AssetReference, ...]
    placement_requirement_references: tuple[AssetReference, ...]
    permission_prerequisite_references: tuple[AssetReference, ...]
    authorization_prerequisite_references: tuple[AssetReference, ...]
    expected_outcomes: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    evidence_references: tuple[AssetReference, ...]
    provenance_references: tuple[AssetReference, ...]
    known_limitations: tuple[str, ...]
    configuration_generation_eligible: bool
    predecessor_version: AssetReference | None = None
    successor_version_references: tuple[AssetReference, ...] = ()
    schema_version: str = SCHEMA_VERSION

    @property
    def identity_key(self) -> tuple[str, str, str, str]:
        return (
            self.tenant_id,
            self.security_domain,
            self.blueprint_id,
            self.version_id,
        )

    @property
    def semantic_payload(self) -> dict[str, object]:
        payload = asdict(self)
        payload.pop("canonical_digest")
        return payload

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_bytes(self.semantic_payload)

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise _fail("INVALID_SCHEMA_VERSION")
        for value, code in (
            (self.blueprint_id, "INVALID_BLUEPRINT_ID"),
            (self.version_id, "INVALID_VERSION_ID"),
            (self.tenant_id, "INVALID_TENANT_ID"),
            (self.security_domain, "INVALID_SECURITY_DOMAIN"),
            (self.provenance_classification, "INVALID_PROVENANCE_CLASSIFICATION"),
        ):
            if identifier(value, code) != value:
                raise _fail(code)
        if utc(self.created_at, "INVALID_CREATED_AT") != self.created_at:
            raise _fail("INVALID_CREATED_AT")
        if not isinstance(self.configuration_generation_eligible, bool):
            raise _fail("INVALID_GENERATION_ELIGIBILITY")
        if self.configuration_generation_eligible:
            raise _fail("GENERATION_NOT_AUTHORIZED")
        expected = canonical_sha256(self.semantic_payload)
        if self.canonical_digest != expected:
            raise _fail("INVALID_CANONICAL_DIGEST")


_REFERENCE_FIELDS = (
    "source_authority_revisions",
    "role_definition_references",
    "skill_references",
    "mcp_capability_references",
    "knowledge_references",
    "runtime_requirement_references",
    "placement_requirement_references",
    "permission_prerequisite_references",
    "authorization_prerequisite_references",
    "evidence_references",
    "provenance_references",
    "successor_version_references",
)
_TEXT_SET_FIELDS = (
    "lifecycle_decision_references",
    "business_scope",
    "applicability_constraints",
    "exclusion_constraints",
    "expected_outcomes",
    "acceptance_criteria",
    "known_limitations",
)


def _references(value: object, code: str) -> tuple[AssetReference, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _fail(code)
    if any(not isinstance(item, AssetReference) for item in value):
        raise _fail(code)
    items = tuple(value)
    if len(set(items)) != len(items):
        raise _fail("AMBIGUOUS_SEMANTIC_SET")
    return tuple(sorted(items))


def create_solution_blueprint(**values: object) -> SolutionBlueprint:
    normalized = dict(values)
    for field in _REFERENCE_FIELDS:
        normalized[field] = _references(
            normalized.get(field, ()), f"INVALID_{field.upper()}"
        )
    for field in _TEXT_SET_FIELDS:
        normalized[field] = semantic_set(
            normalized.get(field, ()), f"INVALID_{field.upper()}"
        )
    normalized["blueprint_id"] = identifier(
        normalized.get("blueprint_id"), "INVALID_BLUEPRINT_ID"
    )
    normalized["version_id"] = identifier(
        normalized.get("version_id"), "INVALID_VERSION_ID"
    )
    normalized["tenant_id"] = identifier(
        normalized.get("tenant_id"), "INVALID_TENANT_ID"
    )
    normalized["security_domain"] = identifier(
        normalized.get("security_domain"), "INVALID_SECURITY_DOMAIN"
    )
    normalized["created_at"] = utc(normalized.get("created_at"), "INVALID_CREATED_AT")
    normalized["provenance_classification"] = identifier(
        normalized.get("provenance_classification"), "INVALID_PROVENANCE_CLASSIFICATION"
    )
    normalized["problem_intent"] = text(
        normalized.get("problem_intent"), "INVALID_PROBLEM_INTENT"
    )
    workflow = normalized.get("canonical_workflow_revision")
    if not isinstance(workflow, AssetReference):
        raise _fail("INVALID_CANONICAL_WORKFLOW_REVISION")
    predecessor = normalized.get("predecessor_version")
    if predecessor is not None and not isinstance(predecessor, AssetReference):
        raise _fail("INVALID_PREDECESSOR_VERSION")
    normalized["schema_version"] = SCHEMA_VERSION
    normalized["configuration_generation_eligible"] = normalized.get(
        "configuration_generation_eligible", False
    )
    provisional = SolutionBlueprint(canonical_digest="", **normalized)
    result = SolutionBlueprint(
        canonical_digest=canonical_sha256(provisional.semantic_payload), **normalized
    )
    result.validate()
    return result
