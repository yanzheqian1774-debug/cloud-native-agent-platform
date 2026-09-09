"""Grant Administration Authority application service."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agent_console.authority_configuration import (
    StaticAuthorityGeneration,
    validate_registered_grant,
)
from agent_console.authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    BrowserSessionRepository,
    ContinuationClaim,
    ContinuationOwner,
    CredentialId,
    CurrentAuthorizationReader,
    DynamicAuthorizationState,
    ExactGrant,
    GrantAdministrationRepository,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
    GrantSource,
    GrantTargetValidator,
    TrustedRequestContext,
    require_bounded_label,
)


def canonical_digest(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class GrantRequestCommand:
    purpose: str
    requested_grants: tuple[ExactGrant, ...]
    idempotency_key: str
    continuation: str | None = None


@dataclass(frozen=True, slots=True)
class GrantDecisionCommand:
    request_id: str
    approve: bool
    reason_category: str
    basis_type: str
    basis_reference: str
    not_before: datetime | None
    expires_at: datetime | None
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ContinuationOfferCommand:
    subject_principal_id: str
    purpose: str
    requested_grants: tuple[ExactGrant, ...]
    canonical_resource_reference: str
    owner_revision: str
    expires_at: datetime
    mint_key: str


@dataclass(frozen=True, slots=True)
class GrantRevocationCommand:
    grant_id: GrantId
    reason_category: str
    idempotency_key: str
    surrender: bool = False


class GenerationAuthorizationReader(CurrentAuthorizationReader):
    """Pin static generation and query current PostgreSQL projection per call."""

    def __init__(
        self,
        generation: StaticAuthorityGeneration | Callable[[], StaticAuthorityGeneration],
        sessions: BrowserSessionRepository,
        dynamic: CurrentAuthorizationReader,
        *,
        recovery_epoch: int,
    ) -> None:
        self._generation_provider = (
            generation if callable(generation) else lambda: generation
        )
        self.sessions = sessions
        self.dynamic = dynamic
        self.recovery_epoch = recovery_epoch

    @property
    def generation(self) -> StaticAuthorityGeneration:
        return self._generation_provider()

    def has_dynamic_revocation(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        recovery_epoch: int,
    ) -> bool:
        return self.dynamic.has_dynamic_revocation(
            context,
            grant,
            now=now,
            recovery_epoch=recovery_epoch,
        )

    def read_dynamic_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> DynamicAuthorizationState:
        return self.dynamic.read_dynamic_authorization_state(
            context,
            grant,
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
        )

    def read_linearized_authorization_state(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> tuple[CredentialId | None, DynamicAuthorizationState]:
        return self.dynamic.read_linearized_authorization_state(
            context,
            grant,
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
        )

    def read_linearized_authorization_states(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
        connection: object | None = None,
    ) -> tuple[CredentialId | None, tuple[DynamicAuthorizationState, ...]]:
        reader = getattr(self.dynamic, "read_linearized_authorization_states", None)
        if reader is None:
            if connection is not None:
                raise AuthorityError("OWNER_TRANSACTION_UNAVAILABLE")
            rows = tuple(
                self.read_linearized_authorization_state(
                    context,
                    grant,
                    now=now,
                    generation=generation,
                    recovery_epoch=recovery_epoch,
                )
                for grant in grants
            )
            credentials = {credential for credential, _ in rows}
            if len(credentials) != 1:
                return None, tuple(state for _, state in rows)
            return rows[0][0], tuple(state for _, state in rows)
        return reader(
            context,
            grants,
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
            connection=connection,
        )

    def has_current_grants(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
        connection: object | None = None,
    ) -> tuple[bool, ...]:
        if (
            not grants
            or generation != self.generation.generation
            or recovery_epoch != self.recovery_epoch
        ):
            return tuple(False for _ in grants)
        credential_id, states = self.read_linearized_authorization_states(
            context,
            grants,
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
            connection=connection,
        )
        credential = (
            self.generation.credential_by_id(credential_id)
            if credential_id is not None
            else None
        )
        expected_source = (
            GrantSource.BROWSER_BOOTSTRAP
            if context.authentication_source is AuthenticationSource.BROWSER_SESSION
            else GrantSource.SERVICE_ONLY
        )
        credential_current = (
            credential is not None
            and credential.scope == context.scope
            and credential.authentication_source is expected_source
            and credential.credential_id
            not in self.generation.credential_revocation_tombstones
            and now < credential.expires_at
        )
        if not credential_current:
            return tuple(False for _ in grants)
        return tuple(
            state
            not in {
                DynamicAuthorizationState.REVOKED,
                DynamicAuthorizationState.UNAVAILABLE,
            }
            and (credential.credential_id, grant)
            not in self.generation.static_grant_revocation_tombstones
            and (
                any(
                    item.grant == grant
                    and (
                        item.source is expected_source
                        or item.source is GrantSource.STATIC_META
                    )
                    for item in credential.grants
                )
                or state is DynamicAuthorizationState.ALLOWED
            )
            for grant, state in zip(grants, states, strict=True)
        )

    def has_current_grant(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
        generation: int,
        recovery_epoch: int,
    ) -> bool:
        return self.has_current_grants(
            context,
            (grant,),
            now=now,
            generation=generation,
            recovery_epoch=recovery_epoch,
        )[0]


class GrantAdministrationService:
    def __init__(
        self,
        repository: GrantAdministrationRepository,
        authorization: CurrentAuthorizationReader,
        generation: StaticAuthorityGeneration | Callable[[], StaticAuthorityGeneration],
        *,
        continuation_owner: ContinuationOwner | None,
        target_validator: GrantTargetValidator | None = None,
        recovery_epoch: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        identity_factory: Callable[[str], str] = lambda prefix: (
            f"{prefix}-{secrets.token_hex(16)}"
        ),
    ) -> None:
        self.repository = repository
        self.authorization = authorization
        self._generation_provider = (
            generation if callable(generation) else lambda: generation
        )
        self.continuation_owner = continuation_owner
        self.target_validator = target_validator
        self.recovery_epoch = recovery_epoch
        self.clock = clock
        self.identity_factory = identity_factory

    @property
    def generation(self) -> StaticAuthorityGeneration:
        return self._generation_provider()

    def _require(self, context: TrustedRequestContext, grant: ExactGrant) -> None:
        if not self.authorization.has_current_grant(
            context,
            grant,
            now=self.clock(),
            generation=self.generation.generation,
            recovery_epoch=self.recovery_epoch,
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def _validate_requestable(
        self, purpose: str, members: Sequence[ExactGrant]
    ) -> None:
        require_bounded_label(purpose, reason_code="GRANT_REQUEST_INVALID")
        if not purpose or not members or len(set(members)) != len(members):
            raise AuthorityError("GRANT_REQUEST_INVALID")
        for member in members:
            validate_registered_grant(member, allow_meta=False)
            if not any(
                rule.purpose == purpose and rule.allows(member)
                for rule in self.generation.requestability
            ):
                raise AuthorityError("GRANT_REQUEST_NOT_FOUND")

    @staticmethod
    def _validate_idempotency_key(value: str) -> None:
        if not value or len(value) > 200 or value.strip() != value:
            raise AuthorityError("IDEMPOTENCY_KEY_INVALID")

    def inspect_request(
        self, context: TrustedRequestContext, request_id: str
    ) -> GrantRequest:
        admin_grant = ExactGrant(
            "GRANT_ADMIN",
            "INSPECT",
            f"grant-scope:{context.scope.tenant_id}:{context.scope.security_domain}",
        )
        administrator_authorized = self.authorization.has_current_grant(
            context,
            admin_grant,
            now=self.clock(),
            generation=self.generation.generation,
            recovery_epoch=self.recovery_epoch,
        )
        return self.repository.inspect_request_for(
            request_id,
            context,
            administrator_authorized=administrator_authorized,
        )

    def submit_request(
        self, context: TrustedRequestContext, command: GrantRequestCommand
    ) -> GrantRequest:
        now = self.clock()
        self._validate_idempotency_key(command.idempotency_key)
        members = command.requested_grants
        continuation_digest = None
        if command.continuation is not None:
            if self.continuation_owner is None:
                raise AuthorityError("CONTINUATION_INVALID")
            claim = self.continuation_owner.resolve_continuation(
                command.continuation, now=now
            )
            if (
                claim.subject_principal_id != context.principal_id
                or claim.scope != context.scope
                or claim.purpose != command.purpose
                or claim.policy_generation != self.generation.generation
                or now < claim.issued_at
                or now >= claim.expires_at
                or (members and tuple(members) != claim.members)
                or self.target_validator is None
            ):
                raise AuthorityError("CONTINUATION_INVALID")
            members = claim.members
            continuation_digest = hashlib.sha256(
                command.continuation.encode()
            ).hexdigest()

            def target_validation(connection: object) -> bool:
                return self.target_validator is not None and (
                    self.target_validator.validate_continuation(
                        claim, connection=connection
                    )
                )

        elif self.target_validator is None:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
        else:

            def target_validation(connection: object) -> bool:
                return all(
                    self.target_validator is not None
                    and self.target_validator.is_known_exact_target(
                        context, member, connection=connection
                    )
                    for member in members
                )

        self._validate_requestable(command.purpose, members)
        payload_digest = canonical_digest(
            {
                "subject": context.principal_id,
                "tenant": context.scope.tenant_id,
                "securityDomain": context.scope.security_domain,
                "purpose": command.purpose,
                "members": [
                    [item.owner, item.action, item.exact_resource] for item in members
                ],
                "continuationDigest": continuation_digest,
            }
        )
        request = GrantRequest(
            request_id=self.identity_factory("grant-request"),
            subject_principal_id=context.principal_id,
            scope=context.scope,
            members=tuple(members),
            purpose=command.purpose,
            status=GrantRequestStatus.PENDING,
            created_at=now,
        )
        return self.repository.submit_request(
            request,
            actor_id=context.principal_id,
            idempotency_key=command.idempotency_key,
            payload_digest=payload_digest,
            target_validation=target_validation,
            continuation_digest=continuation_digest,
            recovery_epoch=self.recovery_epoch,
        )

    def decide_request(
        self, context: TrustedRequestContext, command: GrantDecisionCommand
    ) -> GrantDecision:
        meta = ExactGrant(
            "GRANT_ADMIN",
            "DECIDE",
            f"grant-scope:{context.scope.tenant_id}:{context.scope.security_domain}",
        )
        self._require(context, meta)
        self._validate_idempotency_key(command.idempotency_key)
        require_bounded_label(
            command.reason_category, reason_code="INVALID_GRANT_DECISION"
        )
        require_bounded_label(command.basis_type, reason_code="INVALID_GRANT_DECISION")
        if not command.basis_reference or len(command.basis_reference) > 512:
            raise AuthorityError("INVALID_GRANT_DECISION")
        request = self.repository.inspect_request(command.request_id)
        if request.scope != context.scope:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
        if request.subject_principal_id == context.principal_id:
            raise AuthorityError("GRANT_SELF_APPROVAL_PROHIBITED")
        now = self.clock()
        if command.approve:
            if (
                command.not_before is None
                or command.expires_at is None
                or command.not_before < now
                or command.not_before >= command.expires_at
            ):
                raise AuthorityError("INVALID_GRANT_DECISION")
        elif command.not_before is not None or command.expires_at is not None:
            raise AuthorityError("INVALID_GRANT_DECISION")
        decision_id = self.identity_factory("grant-decision")
        basis_digest = canonical_digest(
            {"type": command.basis_type, "reference": command.basis_reference}
        )
        payload_digest = canonical_digest(
            {
                "requestId": command.request_id,
                "approve": command.approve,
                "reason": command.reason_category,
                "basisDigest": basis_digest,
                "notBefore": (
                    command.not_before.isoformat() if command.not_before else None
                ),
                "expiresAt": (
                    command.expires_at.isoformat() if command.expires_at else None
                ),
            }
        )
        decision = GrantDecision(
            decision_id=decision_id,
            request_id=request.request_id,
            issuer_principal_id=context.principal_id,
            issuer_meta_decision_id=(
                f"static-meta:{self.generation.generation}:{context.principal_id}"
            ),
            approved=command.approve,
            reason_category=command.reason_category,
            basis_type=command.basis_type,
            basis_reference_digest=basis_digest,
            policy_version=self.generation.policy_version,
            audit_source=self.generation.audit_source,
            created_at=now,
        )
        grant_rows = (
            tuple(
                (
                    GrantId(self.identity_factory("grant")),
                    member,
                    command.not_before,
                    command.expires_at,
                )
                for member in request.members
            )
            if command.approve
            else ()
        )
        return self.repository.decide_request(
            decision,
            grants=grant_rows,
            expected_status=GrantRequestStatus.PENDING,
            idempotency_key=command.idempotency_key,
            payload_digest=payload_digest,
            recovery_epoch=self.recovery_epoch,
        )

    def assign_offer(
        self,
        context: TrustedRequestContext,
        command: ContinuationOfferCommand,
    ) -> str:
        """Persist an offer after the typed domain owner validated its exact fact."""
        if self.continuation_owner is None:
            raise AuthorityError("CONTINUATION_INVALID")
        if command.subject_principal_id == context.principal_id:
            raise AuthorityError("CONTINUATION_SELF_ASSIGNMENT_PROHIBITED")
        meta = ExactGrant(
            "CONTINUATION_ASSIGNMENT",
            "ASSIGN",
            f"continuation-scope:{context.scope.tenant_id}:"
            f"{context.scope.security_domain}",
        )
        self._require(context, meta)
        self._validate_idempotency_key(command.mint_key)
        self._validate_requestable(command.purpose, command.requested_grants)
        now = self.clock()
        if (
            command.expires_at <= now
            or command.expires_at - now > timedelta(minutes=10)
            or not command.canonical_resource_reference
            or not command.owner_revision
            or not command.mint_key
            or self.target_validator is None
            or not self.target_validator.validate_offer(
                context.scope,
                command.requested_grants,
                command.canonical_resource_reference,
                command.owner_revision,
            )
        ):
            raise AuthorityError("CONTINUATION_INVALID")
        claim = ContinuationClaim(
            nonce=self.identity_factory("continuation-offer"),
            subject_principal_id=command.subject_principal_id,
            scope=context.scope,
            purpose=command.purpose,
            members=command.requested_grants,
            canonical_resource_reference=command.canonical_resource_reference,
            owner_revision=command.owner_revision,
            policy_generation=self.generation.generation,
            issued_at=now,
            expires_at=command.expires_at,
        )
        payload_digest = canonical_digest(
            {
                "subject": command.subject_principal_id,
                "scope": [context.scope.tenant_id, context.scope.security_domain],
                "purpose": command.purpose,
                "members": [
                    [item.owner, item.action, item.exact_resource]
                    for item in command.requested_grants
                ],
                "canonicalResourceReference": command.canonical_resource_reference,
                "ownerRevision": command.owner_revision,
                "generation": self.generation.generation,
                "expiresAt": command.expires_at.isoformat(),
            }
        )
        opaque = self.continuation_owner.mint(claim)
        persisted = self.repository.store_continuation_offer(
            claim,
            continuation_digest=hashlib.sha256(opaque.encode()).hexdigest(),
            issuer_actor_id=context.principal_id,
            mint_key=command.mint_key,
            mint_payload_digest=payload_digest,
            recovery_epoch=self.recovery_epoch,
        )
        return self.continuation_owner.mint(persisted)

    def mint_owner_continuation(
        self,
        context: TrustedRequestContext,
        claim: ContinuationClaim,
        *,
        originating_command_key: str,
    ) -> str:
        """Resume a creator-facing continuation after the owner fact committed."""
        if self.continuation_owner is None or self.target_validator is None:
            raise AuthorityError("CONTINUATION_INVALID")
        self._validate_idempotency_key(originating_command_key)
        now = self.clock()
        if (
            claim.subject_principal_id != context.principal_id
            or claim.scope != context.scope
            or claim.policy_generation != self.generation.generation
            or now < claim.issued_at
            or now >= claim.expires_at
            or claim.expires_at - claim.issued_at > timedelta(minutes=10)
            or not self.target_validator.validate_continuation(claim)
        ):
            raise AuthorityError("CONTINUATION_INVALID")
        self._validate_requestable(claim.purpose, claim.members)
        payload_digest = canonical_digest(
            {
                "subject": claim.subject_principal_id,
                "scope": [claim.scope.tenant_id, claim.scope.security_domain],
                "purpose": claim.purpose,
                "members": [
                    [item.owner, item.action, item.exact_resource]
                    for item in claim.members
                ],
                "canonicalResourceReference": claim.canonical_resource_reference,
                "ownerRevision": claim.owner_revision,
                "generation": claim.policy_generation,
                "expiresAt": claim.expires_at.isoformat(),
            }
        )
        opaque = self.continuation_owner.mint(claim)
        persisted = self.repository.store_continuation_offer(
            claim,
            continuation_digest=hashlib.sha256(opaque.encode()).hexdigest(),
            issuer_actor_id=context.principal_id,
            mint_key=originating_command_key,
            mint_payload_digest=payload_digest,
            recovery_epoch=self.recovery_epoch,
        )
        return self.continuation_owner.mint(persisted)

    def continuation_inbox(self, context: TrustedRequestContext) -> tuple[str, ...]:
        if self.continuation_owner is None:
            raise AuthorityError("CONTINUATION_INVALID")
        offers = self.repository.list_continuation_offers(
            context, now=self.clock(), recovery_epoch=self.recovery_epoch
        )
        return tuple(self.continuation_owner.mint(claim) for claim in offers)

    def revoke_grant(
        self, context: TrustedRequestContext, command: GrantRevocationCommand
    ) -> None:
        self._validate_idempotency_key(command.idempotency_key)
        require_bounded_label(
            command.reason_category, reason_code="INVALID_GRANT_REVOCATION"
        )
        if command.surrender:
            _, scope = self.repository.inspect_grant_for_subject(
                command.grant_id, context
            )
        else:
            meta = ExactGrant(
                "GRANT_ADMIN",
                "REVOKE",
                f"grant-scope:{context.scope.tenant_id}:"
                f"{context.scope.security_domain}",
            )
            self._require(context, meta)
            _, scope = self.repository.inspect_grant_subject(command.grant_id)
            if scope != context.scope:
                raise AuthorityError("GRANT_NOT_FOUND")
        payload_digest = canonical_digest(
            {
                "grantId": command.grant_id,
                "reason": command.reason_category,
                "surrender": command.surrender,
            }
        )
        self.repository.revoke_grant(
            command.grant_id,
            actor_id=context.principal_id,
            reason=command.reason_category,
            idempotency_key=command.idempotency_key,
            payload_digest=payload_digest,
            now=self.clock(),
        )
