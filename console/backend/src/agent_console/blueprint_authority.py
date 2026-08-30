"""Bounded in-memory authority for immutable Solution Blueprint versions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from agent_console.solution_blueprint import (
    SolutionBlueprint,
    canonical_sha256,
    identifier,
    utc,
)


class BlueprintAuthorityError(ValueError):
    """Stable internal authority failure."""


def _fail(code: str) -> BlueprintAuthorityError:
    return BlueprintAuthorityError(code)


class ReviewAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class PublicationAction(StrEnum):
    PUBLISH = "PUBLISH"
    UNPUBLISH = "UNPUBLISH"
    REVOKE = "REVOKE"
    SUPERSEDE = "SUPERSEDE"


class MatchAction(StrEnum):
    GRANT = "GRANT"
    DENY = "DENY"
    REVOKE = "REVOKE"


@dataclass(frozen=True, slots=True)
class AuthorityDecision:
    decision_id: str
    replay_identity: str
    blueprint_id: str
    version_id: str
    blueprint_digest: str
    tenant_id: str
    security_domain: str
    facet: str
    action: str
    scope: str
    purpose: str
    authority: str
    reason_code: str
    decided_at: datetime
    effective_at: datetime
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AvailabilityResult:
    available: bool
    reason_code: str
    blueprint: SolutionBlueprint | None
    match_authorized: bool
    execution_authorized: bool = False


UNAVAILABLE = AvailabilityResult(False, "UNAVAILABLE", None, False, False)


def create_decision(
    *,
    blueprint: SolutionBlueprint,
    decision_id: object,
    replay_identity: object,
    facet: object,
    action: StrEnum,
    scope: object,
    purpose: object,
    authority: object,
    reason_code: object,
    decided_at: object,
    effective_at: object,
    expires_at: object = None,
) -> AuthorityDecision:
    blueprint.validate()
    if not isinstance(action, StrEnum):
        raise _fail("MALFORMED_AUTHORITY_DECISION")
    decided = utc(decided_at, "INVALID_DECISION_TIMESTAMP")
    effective = utc(effective_at, "INVALID_EFFECTIVE_TIMESTAMP")
    expiry = None if expires_at is None else utc(expires_at, "INVALID_EXPIRY")
    if expiry is not None and expiry <= effective:
        raise _fail("INVALID_EXPIRY")
    return AuthorityDecision(
        identifier(decision_id, "INVALID_DECISION_ID"),
        identifier(replay_identity, "INVALID_REPLAY_IDENTITY"),
        blueprint.blueprint_id,
        blueprint.version_id,
        blueprint.canonical_digest,
        blueprint.tenant_id,
        blueprint.security_domain,
        identifier(facet, "INVALID_FACET"),
        action.value,
        identifier(scope, "INVALID_SCOPE"),
        identifier(purpose, "INVALID_PURPOSE"),
        identifier(authority, "INVALID_AUTHORITY"),
        identifier(reason_code, "INVALID_REASON_CODE").upper(),
        decided,
        effective,
        expiry,
    )


class InMemoryBlueprintAuthority:
    """Append-only proposal, review, registration, publication and match authority."""

    def __init__(self) -> None:
        self._proposals: dict[tuple[str, str, str, str], SolutionBlueprint] = {}
        self._registered: dict[tuple[str, str, str, str], SolutionBlueprint] = {}
        self._decisions: list[AuthorityDecision] = []
        self._decision_ids: dict[str, AuthorityDecision] = {}
        self._replays: dict[str, AuthorityDecision] = {}

    @property
    def decision_history(self) -> tuple[AuthorityDecision, ...]:
        return tuple(self._decisions)

    @property
    def registered_versions(self) -> tuple[SolutionBlueprint, ...]:
        return tuple(self._registered[key] for key in sorted(self._registered))

    def propose(self, blueprint: SolutionBlueprint) -> SolutionBlueprint:
        if not isinstance(blueprint, SolutionBlueprint):
            raise _fail("MALFORMED_BLUEPRINT")
        blueprint.validate()
        existing = self._proposals.get(blueprint.identity_key)
        if existing is not None:
            if existing.semantic_bytes == blueprint.semantic_bytes:
                return existing
            raise _fail("CONFLICTING_BLUEPRINT_VERSION")
        self._validate_successor(blueprint)
        self._proposals[blueprint.identity_key] = blueprint
        return blueprint

    def append_decision(self, decision: AuthorityDecision) -> AuthorityDecision:
        self._validate_decision(decision)
        for existing in (
            self._decision_ids.get(decision.decision_id),
            self._replays.get(decision.replay_identity),
        ):
            if existing is not None:
                if existing == decision:
                    return existing
                raise _fail("CONFLICTING_AUTHORITY_DECISION")
        self._decision_ids[decision.decision_id] = decision
        self._replays[decision.replay_identity] = decision
        self._decisions.append(decision)
        return decision

    def register(self, blueprint: SolutionBlueprint) -> SolutionBlueprint:
        blueprint.validate()
        proposed = self._proposals.get(blueprint.identity_key)
        if proposed is None or proposed.semantic_bytes != blueprint.semantic_bytes:
            raise _fail("BLUEPRINT_PROPOSAL_MISSING")
        reviews = self._current(
            blueprint,
            facet="REVIEW",
            scope="registration",
            purpose="registration",
            at=None,
        )
        if not reviews or reviews[-1].action != ReviewAction.APPROVE.value:
            code = (
                "BLUEPRINT_REJECTED"
                if reviews and reviews[-1].action == ReviewAction.REJECT.value
                else "BLUEPRINT_APPROVAL_MISSING"
            )
            raise _fail(code)
        existing = self._registered.get(blueprint.identity_key)
        if existing is not None:
            if existing.semantic_bytes == blueprint.semantic_bytes:
                return existing
            raise _fail("CONFLICTING_BLUEPRINT_VERSION")
        self._registered[blueprint.identity_key] = blueprint
        return blueprint

    def evaluate(
        self,
        *,
        tenant_id: object,
        security_domain: object,
        blueprint_id: object,
        version_id: object,
        scope: object,
        purpose: object,
        at: object,
    ) -> AvailabilityResult:
        try:
            tenant = identifier(tenant_id, "INVALID_TENANT_ID")
            domain = identifier(security_domain, "INVALID_SECURITY_DOMAIN")
            key = (
                tenant,
                domain,
                identifier(blueprint_id, "INVALID_BLUEPRINT_ID"),
                identifier(version_id, "INVALID_VERSION_ID"),
            )
            evaluation_time = utc(at, "INVALID_EVALUATION_TIME")
            exact_scope = identifier(scope, "INVALID_SCOPE")
            exact_purpose = identifier(purpose, "INVALID_PURPOSE")
        except ValueError:
            return UNAVAILABLE
        blueprint = self._registered.get(key)
        if blueprint is None:
            return UNAVAILABLE
        publication = self._effective(
            blueprint, "PUBLICATION", exact_scope, exact_purpose, evaluation_time
        )
        if publication is None or publication.action != PublicationAction.PUBLISH.value:
            return UNAVAILABLE
        authorization = self._effective(
            blueprint, "MATCH", exact_scope, exact_purpose, evaluation_time
        )
        if authorization is None or authorization.action != MatchAction.GRANT.value:
            return UNAVAILABLE
        return AvailabilityResult(True, "AVAILABLE", blueprint, True, False)

    def _validate_successor(self, blueprint: SolutionBlueprint) -> None:
        predecessor = blueprint.predecessor_version
        if predecessor is None:
            return
        key = (
            blueprint.tenant_id,
            blueprint.security_domain,
            predecessor.asset_id,
            predecessor.version_id,
        )
        existing = self._proposals.get(key)
        if (
            existing is None
            or existing.canonical_digest != predecessor.canonical_digest
        ):
            raise _fail("INVALID_PREDECESSOR_BINDING")
        if (
            predecessor.asset_id != blueprint.blueprint_id
            or predecessor.version_id == blueprint.version_id
        ):
            raise _fail("INVALID_PREDECESSOR_BINDING")

    def _validate_decision(self, decision: AuthorityDecision) -> None:
        if not isinstance(decision, AuthorityDecision):
            raise _fail("MALFORMED_AUTHORITY_DECISION")
        key = (
            decision.tenant_id,
            decision.security_domain,
            decision.blueprint_id,
            decision.version_id,
        )
        blueprint = self._proposals.get(key)
        if blueprint is None or blueprint.canonical_digest != decision.blueprint_digest:
            raise _fail("MALFORMED_AUTHORITY_DECISION")
        expected_actions = {
            "REVIEW": ReviewAction,
            "PUBLICATION": PublicationAction,
            "MATCH": MatchAction,
        }
        enum = expected_actions.get(decision.facet)
        if enum is None or decision.action not in {item.value for item in enum}:
            raise _fail("MALFORMED_AUTHORITY_DECISION")
        if decision.facet != "REVIEW" and key not in self._registered:
            raise _fail("BLUEPRINT_NOT_REGISTERED")
        if decision.facet == "REVIEW" and (
            decision.scope != "registration" or decision.purpose != "registration"
        ):
            raise _fail("MALFORMED_AUTHORITY_DECISION")
        if (
            decision.expires_at is not None
            and decision.expires_at <= decision.effective_at
        ):
            raise _fail("INVALID_EXPIRY")

    def _current(
        self,
        blueprint: SolutionBlueprint,
        *,
        facet: str,
        scope: str,
        purpose: str,
        at: datetime | None,
    ) -> list[AuthorityDecision]:
        result = [
            item
            for item in self._decisions
            if item.blueprint_digest == blueprint.canonical_digest
            and item.tenant_id == blueprint.tenant_id
            and item.security_domain == blueprint.security_domain
            and item.facet == facet
            and item.scope == scope
            and item.purpose == purpose
            and (
                at is None
                or (
                    item.effective_at <= at
                    and (item.expires_at is None or at < item.expires_at)
                )
            )
        ]
        return sorted(
            result,
            key=lambda item: (item.effective_at, item.decided_at, item.decision_id),
        )

    def _effective(
        self,
        blueprint: SolutionBlueprint,
        facet: str,
        scope: str,
        purpose: str,
        at: datetime,
    ) -> AuthorityDecision | None:
        decisions = self._current(
            blueprint, facet=facet, scope=scope, purpose=purpose, at=at
        )
        if not decisions:
            return None
        latest_time = decisions[-1].effective_at
        latest = [item for item in decisions if item.effective_at == latest_time]
        if len({item.action for item in latest}) != 1:
            return None
        return latest[-1]

    def history_digest(self) -> str:
        return canonical_sha256(
            tuple(self._decisions),
            domain="agent-console:blueprint-authority-history.v1",
        )
