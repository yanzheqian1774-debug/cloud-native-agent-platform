"""Internal v0.2 Definition publication and matchability authority.

This module is deliberately in-memory and has no public/API persistence surface.
Authoring approval, publication, match authorization, and matching remain separate
authorities.  MATCHABLE is derived for one exact scope and UTC instant.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

DIGEST_ALGORITHM = "SHA-256"
DIGEST_CONTRACT_VERSION = "definition-match-v1"
DEFINITION_SCHEMA_VERSION = "definition-version.v1"
SNAPSHOT_CONTRACT_VERSION = "effective-definition-catalog.v1"
IDENTIFIER_LIMIT = 200
SEMANTIC_TEXT_LIMIT = 500
MAX_AUTHORIZED_CANDIDATES = 64

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class DefinitionAuthorityError(ValueError):
    """Stable disclosure-safe authority failure."""


class PublicationAction(StrEnum):
    PUBLISH = "PUBLISH"
    UNPUBLISH = "UNPUBLISH"
    REVOKE_PUBLICATION = "REVOKE_PUBLICATION"


class MatchAuthorizationAction(StrEnum):
    GRANT = "GRANT"
    DENY = "DENY"
    REVOKE = "REVOKE"


class ReplacementEffect(StrEnum):
    NONE = "NONE"
    EXCLUDE_PREDECESSOR_FOR_MATCH = "EXCLUDE_PREDECESSOR_FOR_MATCH"


def _fail(code: str) -> DefinitionAuthorityError:
    return DefinitionAuthorityError(code)


def _identifier(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = unicodedata.normalize("NFC", value)
    if not normalized or len(normalized) > IDENTIFIER_LIMIT:
        raise _fail(code if not normalized else "IDENTIFIER_LIMIT_EXCEEDED")
    if _IDENTIFIER.fullmatch(normalized) is None:
        raise _fail(code)
    return normalized


def _text(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise _fail(code)
    normalized = " ".join(unicodedata.normalize("NFC", value).split())
    if not normalized or len(normalized) > SEMANTIC_TEXT_LIMIT:
        raise _fail(code if not normalized else "SEMANTIC_TEXT_LIMIT_EXCEEDED")
    return normalized


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise _fail(code)
    if value.utcoffset() is None or value.utcoffset().total_seconds() != 0:
        raise _fail(code)
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _utc(value, "INVALID_UTC_TIMESTAMP").isoformat().replace("+00:00", "Z")


def _set_items(value: object, code: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _fail(code)
    items = tuple(_text(item, code) for item in value)
    if len(set(items)) != len(items):
        raise _fail("AMBIGUOUS_SET_LIKE_CONTENT")
    return tuple(sorted(items))


def _canonical(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return _utc_text(value)
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        normalized_items = [
            (unicodedata.normalize("NFC", key), item) for key, item in value.items()
        ]
        if len({key for key, _ in normalized_items}) != len(normalized_items):
            raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")
        return {key: _canonical(item) for key, item in sorted(normalized_items)}
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if value is None or isinstance(value, (bool, int)):
        return value
    raise _fail("AMBIGUOUS_CANONICAL_SERIALIZATION")


def canonical_json(value: object) -> str:
    return json.dumps(
        _canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def canonical_digest(value: object, *, domain: str) -> str:
    payload = f"{domain}\n{canonical_json(value)}".encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class RoleDescriptor:
    title: str
    duties: tuple[str, ...]
    data: tuple[str, ...] = ()
    knowledge: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()

    @classmethod
    def create(
        cls,
        *,
        title: object,
        duties: object,
        data: object = (),
        knowledge: object = (),
        skills: object = (),
        capabilities: object = (),
        runtimes: object = (),
    ) -> RoleDescriptor:
        return cls(
            title=_text(title, "INVALID_ROLE_TITLE"),
            duties=_set_items(duties, "INVALID_ROLE_DUTY"),
            data=_set_items(data, "INVALID_DATA_COVERAGE"),
            knowledge=_set_items(knowledge, "INVALID_KNOWLEDGE_COVERAGE"),
            skills=_set_items(skills, "INVALID_SKILL_COVERAGE"),
            capabilities=_set_items(capabilities, "INVALID_CAPABILITY_COVERAGE"),
            runtimes=_set_items(runtimes, "INVALID_RUNTIME_COVERAGE"),
        )


@dataclass(frozen=True, slots=True)
class DefinitionVersion:
    definition_id: str
    version_id: str
    definition_digest: str
    role: RoleDescriptor
    source_authoring_revision_id: str
    source_authority_kind: str
    source_authority_revision: str
    source_authoring_state: str
    tenant_id: str
    security_domain: str
    provenance: str
    created_at: datetime
    schema_version: str = DEFINITION_SCHEMA_VERSION
    digest_algorithm: str = DIGEST_ALGORITHM
    digest_contract_version: str = DIGEST_CONTRACT_VERSION

    @property
    def semantic_payload(self) -> dict[str, object]:
        return {
            "definitionId": self.definition_id,
            "versionId": self.version_id,
            "role": asdict(self.role),
            "sourceAuthoringRevisionId": self.source_authoring_revision_id,
            "sourceAuthorityKind": self.source_authority_kind,
            "sourceAuthorityRevision": self.source_authority_revision,
            "sourceAuthoringState": self.source_authoring_state,
            "tenantId": self.tenant_id,
            "securityDomain": self.security_domain,
            "provenance": self.provenance,
            "createdAt": self.created_at,
            "schemaVersion": self.schema_version,
            "digestAlgorithm": self.digest_algorithm,
            "digestContractVersion": self.digest_contract_version,
        }

    def validate(self) -> None:
        if (
            self.schema_version != DEFINITION_SCHEMA_VERSION
            or self.digest_algorithm != DIGEST_ALGORITHM
            or (self.digest_contract_version != DIGEST_CONTRACT_VERSION)
        ):
            raise _fail("INVALID_DEFINITION_DIGEST")
        if (
            _identifier(self.definition_id, "INVALID_DEFINITION_ID")
            != self.definition_id
        ):
            raise _fail("INVALID_DEFINITION_ID")
        if _identifier(self.version_id, "INVALID_VERSION_ID") != self.version_id:
            raise _fail("INVALID_VERSION_ID")
        if not isinstance(
            self.role, RoleDescriptor
        ) or self.role != RoleDescriptor.create(
            title=self.role.title,
            duties=self.role.duties,
            data=self.role.data,
            knowledge=self.role.knowledge,
            skills=self.role.skills,
            capabilities=self.role.capabilities,
            runtimes=self.role.runtimes,
        ):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        for value, code in (
            (self.source_authoring_revision_id, "INVALID_AUTHORING_REVISION"),
            (self.source_authority_kind, "INVALID_SOURCE_AUTHORITY"),
            (self.source_authority_revision, "INVALID_SOURCE_REVISION"),
            (self.source_authoring_state, "INVALID_AUTHORING_STATE"),
            (self.tenant_id, "TENANT_SCOPE_MISMATCH"),
            (self.security_domain, "SECURITY_DOMAIN_SCOPE_MISMATCH"),
            (self.provenance, "INVALID_PROVENANCE"),
        ):
            if _identifier(value, code) != value:
                raise _fail(code)
        if _utc(self.created_at, "INVALID_CREATED_AT") != self.created_at:
            raise _fail("INVALID_CREATED_AT")
        if self.source_authoring_state != "APPROVED":
            raise _fail("AUTHORING_APPROVAL_REQUIRED")
        expected = canonical_digest(
            self.semantic_payload, domain=DIGEST_CONTRACT_VERSION
        )
        if self.definition_digest != expected:
            raise _fail("INVALID_DEFINITION_DIGEST")


def create_definition_version(
    *,
    definition_id: object,
    version_id: object,
    role: RoleDescriptor,
    source_authoring_revision_id: object,
    source_authority_kind: object,
    source_authority_revision: object,
    source_authoring_state: object,
    tenant_id: object,
    security_domain: object,
    provenance: object,
    created_at: object,
) -> DefinitionVersion:
    if not isinstance(role, RoleDescriptor):
        raise _fail("MALFORMED_AUTHORITY_RECORD")
    values = {
        "definition_id": _identifier(definition_id, "INVALID_DEFINITION_ID"),
        "version_id": _identifier(version_id, "INVALID_VERSION_ID"),
        "role": role,
        "source_authoring_revision_id": _identifier(
            source_authoring_revision_id, "INVALID_AUTHORING_REVISION"
        ),
        "source_authority_kind": _identifier(
            source_authority_kind, "INVALID_SOURCE_AUTHORITY"
        ),
        "source_authority_revision": _identifier(
            source_authority_revision, "INVALID_SOURCE_REVISION"
        ),
        "source_authoring_state": _identifier(
            source_authoring_state, "INVALID_AUTHORING_STATE"
        ).upper(),
        "tenant_id": _identifier(tenant_id, "TENANT_SCOPE_MISMATCH"),
        "security_domain": _identifier(
            security_domain, "SECURITY_DOMAIN_SCOPE_MISMATCH"
        ),
        "provenance": _identifier(provenance, "INVALID_PROVENANCE"),
        "created_at": _utc(created_at, "INVALID_CREATED_AT"),
    }
    provisional = DefinitionVersion(definition_digest="", **values)
    digest = canonical_digest(
        provisional.semantic_payload, domain=DIGEST_CONTRACT_VERSION
    )
    result = DefinitionVersion(definition_digest=digest, **values)
    result.validate()
    return result


@dataclass(frozen=True, slots=True)
class PublicationDecision:
    decision_id: str
    replay_identity: str
    definition_id: str
    version_id: str
    definition_digest: str
    source_authority_revision: str
    tenant_id: str
    security_domain: str
    action: PublicationAction
    actor: str
    reason_code: str
    policy_ref: str
    decided_at: datetime
    effective_at: datetime
    expires_at: datetime | None
    provenance: str
    predecessor_definition_id: str | None = None
    predecessor_version_id: str | None = None
    predecessor_digest: str | None = None
    replacement_effect: ReplacementEffect = ReplacementEffect.NONE


@dataclass(frozen=True, slots=True)
class MatchAuthorizationDecision:
    decision_id: str
    replay_identity: str
    definition_id: str
    version_id: str
    definition_digest: str
    source_authority_revision: str
    tenant_id: str
    security_domain: str
    purpose: str
    action: MatchAuthorizationAction
    authority: str
    reason_code: str
    policy_ref: str
    decided_at: datetime
    effective_at: datetime
    expires_at: datetime | None
    provenance: str


def _validate_decision_time(
    decided_at: object, effective_at: object, expires_at: object
) -> tuple[datetime, datetime, datetime | None]:
    decided = _utc(decided_at, "INVALID_DECISION_TIMESTAMP")
    effective = _utc(effective_at, "INVALID_EFFECTIVE_TIMESTAMP")
    expiry = None if expires_at is None else _utc(expires_at, "INVALID_EXPIRY")
    if expiry is not None and expiry <= effective:
        raise _fail("INVALID_EXPIRY")
    return decided, effective, expiry


def create_publication_decision(
    *,
    version: DefinitionVersion,
    decision_id: object,
    replay_identity: object,
    action: PublicationAction,
    actor: object,
    reason_code: object,
    policy_ref: object,
    decided_at: object,
    effective_at: object,
    expires_at: object = None,
    provenance: object,
    predecessor: DefinitionVersion | None = None,
    replacement_effect: ReplacementEffect = ReplacementEffect.NONE,
) -> PublicationDecision:
    version.validate()
    if not isinstance(action, PublicationAction) or not isinstance(
        replacement_effect, ReplacementEffect
    ):
        raise _fail("MALFORMED_AUTHORITY_RECORD")
    decided, effective, expiry = _validate_decision_time(
        decided_at, effective_at, expires_at
    )
    if replacement_effect is ReplacementEffect.EXCLUDE_PREDECESSOR_FOR_MATCH:
        if predecessor is None or action is not PublicationAction.PUBLISH:
            raise _fail("INVALID_PREDECESSOR_EXCLUSION")
        predecessor.validate()
        if (
            predecessor.tenant_id != version.tenant_id
            or predecessor.security_domain != version.security_domain
            or predecessor.definition_id != version.definition_id
        ):
            raise _fail("INVALID_PREDECESSOR_EXCLUSION")
    return PublicationDecision(
        decision_id=_identifier(decision_id, "INVALID_DECISION_ID"),
        replay_identity=_identifier(replay_identity, "INVALID_REPLAY_IDENTITY"),
        definition_id=version.definition_id,
        version_id=version.version_id,
        definition_digest=version.definition_digest,
        source_authority_revision=version.source_authority_revision,
        tenant_id=version.tenant_id,
        security_domain=version.security_domain,
        action=action,
        actor=_identifier(actor, "INVALID_ACTOR"),
        reason_code=_identifier(reason_code, "INVALID_REASON_CODE").upper(),
        policy_ref=_identifier(policy_ref, "INVALID_POLICY_REFERENCE"),
        decided_at=decided,
        effective_at=effective,
        expires_at=expiry,
        provenance=_identifier(provenance, "INVALID_PROVENANCE"),
        predecessor_definition_id=(
            None if predecessor is None else predecessor.definition_id
        ),
        predecessor_version_id=(
            None if predecessor is None else predecessor.version_id
        ),
        predecessor_digest=(
            None if predecessor is None else predecessor.definition_digest
        ),
        replacement_effect=replacement_effect,
    )


def create_match_authorization_decision(
    *,
    version: DefinitionVersion,
    decision_id: object,
    replay_identity: object,
    purpose: object,
    action: MatchAuthorizationAction,
    authority: object,
    reason_code: object,
    policy_ref: object,
    decided_at: object,
    effective_at: object,
    expires_at: object = None,
    provenance: object,
) -> MatchAuthorizationDecision:
    version.validate()
    if not isinstance(action, MatchAuthorizationAction):
        raise _fail("MALFORMED_AUTHORITY_RECORD")
    decided, effective, expiry = _validate_decision_time(
        decided_at, effective_at, expires_at
    )
    return MatchAuthorizationDecision(
        decision_id=_identifier(decision_id, "INVALID_DECISION_ID"),
        replay_identity=_identifier(replay_identity, "INVALID_REPLAY_IDENTITY"),
        definition_id=version.definition_id,
        version_id=version.version_id,
        definition_digest=version.definition_digest,
        source_authority_revision=version.source_authority_revision,
        tenant_id=version.tenant_id,
        security_domain=version.security_domain,
        purpose=_identifier(purpose, "INVALID_MATCH_PURPOSE"),
        action=action,
        authority=_identifier(authority, "INVALID_AUTHORITY"),
        reason_code=_identifier(reason_code, "INVALID_REASON_CODE").upper(),
        policy_ref=_identifier(policy_ref, "INVALID_POLICY_REFERENCE"),
        decided_at=decided,
        effective_at=effective,
        expires_at=expiry,
        provenance=_identifier(provenance, "INVALID_PROVENANCE"),
    )


@dataclass(frozen=True, slots=True)
class DefinitionAuthorityEvidence:
    evidence_id: str
    event: str
    subject_digest: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class EffectiveDefinition:
    version: DefinitionVersion
    publication_decision_id: str
    match_authorization_decision_id: str


@dataclass(frozen=True, slots=True)
class EffectiveDefinitionCatalogSnapshot:
    snapshot_id: str
    snapshot_contract_version: str
    tenant_id: str
    security_domain: str
    purpose: str
    evaluation_time: datetime
    workflow_revision_id: str
    workflow_digest: str
    source_authority_revision: str
    definitions: tuple[EffectiveDefinition, ...]
    decision_references: tuple[str, ...]
    complete: bool = True
    limitations: tuple[str, ...] = ("ADVISORY_MATCHING_ONLY", "NON_EXECUTABLE")


class EffectiveDefinitionCatalogProvider(Protocol):
    def snapshot(
        self,
        *,
        tenant_id: str,
        security_domain: str,
        purpose: str,
        evaluation_time: datetime,
        workflow_revision_id: str,
        workflow_digest: str,
    ) -> EffectiveDefinitionCatalogSnapshot: ...


def effective_snapshot_identity(
    *,
    tenant_id: str,
    security_domain: str,
    purpose: str,
    evaluation_time: datetime,
    workflow_revision_id: str,
    workflow_digest: str,
    source_authority_revision: str,
    definitions: tuple[EffectiveDefinition, ...],
) -> str:
    """Compute the governed identity of a complete catalog snapshot."""
    payload = {
        "contract": SNAPSHOT_CONTRACT_VERSION,
        "tenant": tenant_id,
        "securityDomain": security_domain,
        "purpose": purpose,
        "evaluationTime": evaluation_time,
        "workflowRevisionId": workflow_revision_id,
        "workflowDigest": workflow_digest,
        "sourceAuthorityRevision": source_authority_revision,
        "definitions": tuple(
            {
                "definitionId": item.version.definition_id,
                "versionId": item.version.version_id,
                "digest": item.version.definition_digest,
                "publication": item.publication_decision_id,
                "authorization": item.match_authorization_decision_id,
            }
            for item in definitions
        ),
    }
    return canonical_digest(payload, domain=SNAPSHOT_CONTRACT_VERSION)


def _active(
    decision: PublicationDecision | MatchAuthorizationDecision, at: datetime
) -> bool:
    return decision.effective_at <= at and (
        decision.expires_at is None or at < decision.expires_at
    )


class InMemoryDefinitionAuthority(EffectiveDefinitionCatalogProvider):
    """Trusted catalog owner plus separate append-only decision authorities."""

    def __init__(self, *, source_authority_revision: object) -> None:
        self.source_authority_revision = _identifier(
            source_authority_revision, "INVALID_SOURCE_REVISION"
        )
        self._versions: dict[tuple[str, str], DefinitionVersion] = {}
        self._publication: dict[str, PublicationDecision] = {}
        self._publication_replays: dict[str, PublicationDecision] = {}
        self._authorization: dict[str, MatchAuthorizationDecision] = {}
        self._authorization_replays: dict[str, MatchAuthorizationDecision] = {}
        self._evidence: list[DefinitionAuthorityEvidence] = []

    @property
    def evidence(self) -> tuple[DefinitionAuthorityEvidence, ...]:
        return tuple(self._evidence)

    def register(self, version: DefinitionVersion) -> DefinitionVersion:
        if not isinstance(version, DefinitionVersion):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        version.validate()
        key = (version.definition_id, version.version_id)
        existing = self._versions.get(key)
        if existing is not None:
            if existing == version:
                return existing
            raise _fail("CONFLICTING_DEFINITION_VERSION")
        self._versions[key] = version
        self._record("VERSION_REGISTERED", version.definition_digest, "REGISTERED")
        return version

    def append_publication(self, decision: PublicationDecision) -> PublicationDecision:
        if not isinstance(decision, PublicationDecision):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        self._validate_publication_decision(decision)
        self._assert_binding(decision)
        return self._append_decision(
            decision,
            identities=self._publication,
            replays=self._publication_replays,
            conflict="CONFLICTING_PUBLICATION_DECISION",
            event="PUBLICATION_DECISION_RECORDED",
        )

    def append_match_authorization(
        self, decision: MatchAuthorizationDecision
    ) -> MatchAuthorizationDecision:
        if not isinstance(decision, MatchAuthorizationDecision):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        self._validate_match_authorization_decision(decision)
        self._assert_binding(decision)
        return self._append_decision(
            decision,
            identities=self._authorization,
            replays=self._authorization_replays,
            conflict="CONFLICTING_MATCH_AUTHORIZATION",
            event="MATCH_AUTHORIZATION_RECORDED",
        )

    def _append_decision(self, decision, *, identities, replays, conflict, event):
        by_id = identities.get(decision.decision_id)
        by_replay = replays.get(decision.replay_identity)
        for existing in (by_id, by_replay):
            if existing is not None:
                if existing == decision:
                    return existing
                raise _fail(conflict)
        identities[decision.decision_id] = decision
        replays[decision.replay_identity] = decision
        self._record(event, decision.definition_digest, decision.reason_code)
        return decision

    def _assert_binding(self, decision) -> None:
        version = self._versions.get((decision.definition_id, decision.version_id))
        if version is None or version.definition_digest != decision.definition_digest:
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        if (
            version.tenant_id != decision.tenant_id
            or version.security_domain != decision.security_domain
            or version.source_authority_revision != decision.source_authority_revision
        ):
            raise _fail("MALFORMED_AUTHORITY_RECORD")

    @staticmethod
    def _validate_common_decision(decision) -> None:
        for value, code in (
            (decision.decision_id, "INVALID_DECISION_ID"),
            (decision.replay_identity, "INVALID_REPLAY_IDENTITY"),
            (decision.definition_id, "INVALID_DEFINITION_ID"),
            (decision.version_id, "INVALID_VERSION_ID"),
            (decision.source_authority_revision, "INVALID_SOURCE_REVISION"),
            (decision.tenant_id, "TENANT_SCOPE_MISMATCH"),
            (decision.security_domain, "SECURITY_DOMAIN_SCOPE_MISMATCH"),
            (decision.reason_code, "INVALID_REASON_CODE"),
            (decision.policy_ref, "INVALID_POLICY_REFERENCE"),
            (decision.provenance, "INVALID_PROVENANCE"),
        ):
            if _identifier(value, code) != value:
                raise _fail(code)
        if not re.fullmatch(r"[0-9a-f]{64}", decision.definition_digest):
            raise _fail("INVALID_DEFINITION_DIGEST")
        decided, effective, expiry = _validate_decision_time(
            decision.decided_at, decision.effective_at, decision.expires_at
        )
        if (decided, effective, expiry) != (
            decision.decided_at,
            decision.effective_at,
            decision.expires_at,
        ):
            raise _fail("MALFORMED_AUTHORITY_RECORD")

    @classmethod
    def _validate_publication_decision(cls, decision: PublicationDecision) -> None:
        cls._validate_common_decision(decision)
        if not isinstance(decision.action, PublicationAction) or not isinstance(
            decision.replacement_effect, ReplacementEffect
        ):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        if _identifier(decision.actor, "INVALID_ACTOR") != decision.actor:
            raise _fail("INVALID_ACTOR")
        predecessor = (
            decision.predecessor_definition_id,
            decision.predecessor_version_id,
            decision.predecessor_digest,
        )
        if decision.replacement_effect is ReplacementEffect.NONE:
            if any(value is not None for value in predecessor):
                raise _fail("INVALID_PREDECESSOR_EXCLUSION")
        else:
            if decision.action is not PublicationAction.PUBLISH or any(
                value is None for value in predecessor
            ):
                raise _fail("INVALID_PREDECESSOR_EXCLUSION")
            _identifier(predecessor[0], "INVALID_PREDECESSOR_EXCLUSION")
            _identifier(predecessor[1], "INVALID_PREDECESSOR_EXCLUSION")
            if not isinstance(predecessor[2], str) or not re.fullmatch(
                r"[0-9a-f]{64}", predecessor[2]
            ):
                raise _fail("INVALID_PREDECESSOR_EXCLUSION")

    @classmethod
    def _validate_match_authorization_decision(
        cls, decision: MatchAuthorizationDecision
    ) -> None:
        cls._validate_common_decision(decision)
        if not isinstance(decision.action, MatchAuthorizationAction):
            raise _fail("MALFORMED_AUTHORITY_RECORD")
        for value, code in (
            (decision.purpose, "INVALID_MATCH_PURPOSE"),
            (decision.authority, "INVALID_AUTHORITY"),
        ):
            if _identifier(value, code) != value:
                raise _fail(code)

    def _record(self, event: str, digest: str, reason: str) -> None:
        ordinal = len(self._evidence) + 1
        evidence_id = canonical_digest(
            {"ordinal": ordinal, "event": event, "digest": digest, "reason": reason},
            domain="definition-authority-evidence-v1",
        )
        self._evidence.append(
            DefinitionAuthorityEvidence(evidence_id, event, digest, reason)
        )

    def snapshot(
        self,
        *,
        tenant_id: str,
        security_domain: str,
        purpose: str,
        evaluation_time: datetime,
        workflow_revision_id: str,
        workflow_digest: str,
    ) -> EffectiveDefinitionCatalogSnapshot:
        tenant = _identifier(tenant_id, "TENANT_SCOPE_MISMATCH")
        domain = _identifier(security_domain, "SECURITY_DOMAIN_SCOPE_MISMATCH")
        match_purpose = _identifier(purpose, "INVALID_MATCH_PURPOSE")
        at = _utc(evaluation_time, "INVALID_EVALUATION_TIME")
        workflow_id = _identifier(workflow_revision_id, "INVALID_WORKFLOW_REVISION")
        workflow_hash = _identifier(workflow_digest, "INVALID_WORKFLOW_DIGEST")
        scoped_versions = sorted(
            (
                item
                for item in self._versions.values()
                if item.tenant_id == tenant and item.security_domain == domain
            ),
            key=lambda item: (
                item.definition_id,
                item.version_id,
                item.definition_digest,
            ),
        )
        effective: list[EffectiveDefinition] = []
        failure_codes: set[str] = set()
        for version in scoped_versions:
            try:
                projection = self._project(version, match_purpose, at)
            except DefinitionAuthorityError as exc:
                failure_codes.add(str(exc))
                continue
            if projection is not None:
                effective.append(projection)
        if len(effective) > MAX_AUTHORIZED_CANDIDATES:
            raise _fail("CANDIDATE_LIMIT_EXCEEDED")
        if not effective and scoped_versions and failure_codes:
            priority = (
                "CONFLICTING_AUTHORITY_RECORDS",
                "PUBLICATION_NOT_EFFECTIVE",
                "DEFINITION_UNPUBLISHED",
                "MATCH_AUTHORIZATION_REVOKED",
                "MATCH_AUTHORIZATION_EXPIRED",
                "MATCH_AUTHORIZATION_DENIED",
                "MATCH_AUTHORIZATION_MISSING",
            )
            raise _fail(
                next(
                    (code for code in priority if code in failure_codes),
                    "DEFINITION_CATALOG_UNAVAILABLE",
                )
            )
        ordered = tuple(effective)
        decision_refs = tuple(
            sorted(
                ref
                for item in ordered
                for ref in (
                    item.publication_decision_id,
                    item.match_authorization_decision_id,
                )
            )
        )
        snapshot_id = effective_snapshot_identity(
            tenant_id=tenant,
            security_domain=domain,
            purpose=match_purpose,
            evaluation_time=at,
            workflow_revision_id=workflow_id,
            workflow_digest=workflow_hash,
            source_authority_revision=self.source_authority_revision,
            definitions=ordered,
        )
        self._record("SNAPSHOT_ASSEMBLED", snapshot_id, "COMPLETE")
        return EffectiveDefinitionCatalogSnapshot(
            snapshot_id=snapshot_id,
            snapshot_contract_version=SNAPSHOT_CONTRACT_VERSION,
            tenant_id=tenant,
            security_domain=domain,
            purpose=match_purpose,
            evaluation_time=at,
            workflow_revision_id=workflow_id,
            workflow_digest=workflow_hash,
            source_authority_revision=self.source_authority_revision,
            definitions=ordered,
            decision_references=decision_refs,
        )

    def _project(
        self, version: DefinitionVersion, purpose: str, at: datetime
    ) -> EffectiveDefinition | None:
        publications = [
            item
            for item in self._publication.values()
            if (item.definition_id, item.version_id, item.definition_digest)
            == (version.definition_id, version.version_id, version.definition_digest)
            and _active(item, at)
        ]
        if not publications:
            raise _fail("DEFINITION_UNPUBLISHED")
        self._reject_simultaneous_conflict(publications)
        publications.sort(
            key=lambda item: (item.effective_at, item.decided_at, item.decision_id)
        )
        publication = publications[-1]
        if publication.action is not PublicationAction.PUBLISH:
            raise _fail("PUBLICATION_NOT_EFFECTIVE")
        if self._excluded_by_successor(version, at):
            raise _fail("PUBLICATION_NOT_EFFECTIVE")
        authorizations = [
            item
            for item in self._authorization.values()
            if (
                item.definition_id,
                item.version_id,
                item.definition_digest,
                item.purpose,
            )
            == (
                version.definition_id,
                version.version_id,
                version.definition_digest,
                purpose,
            )
            and item.effective_at <= at
        ]
        if not authorizations:
            raise _fail("MATCH_AUTHORIZATION_MISSING")
        self._reject_simultaneous_conflict(authorizations)
        authorizations.sort(
            key=lambda item: (item.effective_at, item.decided_at, item.decision_id)
        )
        authorization = authorizations[-1]
        if authorization.expires_at is not None and at >= authorization.expires_at:
            raise _fail("MATCH_AUTHORIZATION_EXPIRED")
        if authorization.action is MatchAuthorizationAction.DENY:
            raise _fail("MATCH_AUTHORIZATION_DENIED")
        if authorization.action is MatchAuthorizationAction.REVOKE:
            raise _fail("MATCH_AUTHORIZATION_REVOKED")
        if authorization.action is not MatchAuthorizationAction.GRANT:
            raise _fail("MATCH_AUTHORIZATION_MISSING")
        return EffectiveDefinition(
            version, publication.decision_id, authorization.decision_id
        )

    @staticmethod
    def _reject_simultaneous_conflict(decisions: list[object]) -> None:
        seen: dict[tuple[datetime, datetime], object] = {}
        for item in decisions:
            key = (item.effective_at, item.decided_at)
            action = item.action
            previous = seen.get(key)
            if previous is not None and previous != action:
                raise _fail("CONFLICTING_AUTHORITY_RECORDS")
            seen[key] = action

    def _excluded_by_successor(self, version: DefinitionVersion, at: datetime) -> bool:
        for item in self._publication.values():
            if (
                item.action is PublicationAction.PUBLISH
                and item.replacement_effect
                is ReplacementEffect.EXCLUDE_PREDECESSOR_FOR_MATCH
                and item.predecessor_definition_id == version.definition_id
                and item.predecessor_version_id == version.version_id
                and item.predecessor_digest == version.definition_digest
                and item.tenant_id == version.tenant_id
                and item.security_domain == version.security_domain
                and _active(item, at)
            ):
                return True
        return False
