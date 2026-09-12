"""Exact authorization and creator-continuation adapters for Model Governance."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

from agent_console.authority_configuration import validate_registered_grant
from agent_console.authority_contracts import (
    AuthorityScope,
    ContinuationClaim,
    ExactGrant,
    TrustedRequestContext,
    require_bounded_label,
)
from agent_console.model_binding_resolution import (
    AuthorizedModelUse,
    ExactModelBinding,
    ExactModelUse,
    ModelConsumptionScope,
    ModelUseAction,
    ModelUseSubject,
    ResolvedModelBinding,
)
from agent_console.model_governance import (
    ModelDefinition,
    ModelDefinitionRepository,
    ModelGovernanceNotFound,
    ModelProviderConfigurationRepository,
    ModelRevisionRepository,
    ModelScope,
)

MODEL_OWNER = "MODEL_GOVERNANCE"
CREATE_MODEL = "CREATE_MODEL"
READ_MODEL = "READ_MODEL"
MANAGE_MODEL_REVISION = "MANAGE_MODEL_REVISION"


class ModelManagementOperation(StrEnum):
    REVISE = "REVISE"
    PUBLISH = "PUBLISH"
    DISABLE = "DISABLE"
    ENABLE = "ENABLE"
    DEPRECATE = "DEPRECATE"
    REVOKE = "REVOKE"


def _part(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("INVALID_MODEL_GRANT_TARGET")
    return value


def create_model_grant() -> ExactGrant:
    return ExactGrant(MODEL_OWNER, CREATE_MODEL, "model:collection")


def model_catalog_grant() -> ExactGrant:
    return ExactGrant(MODEL_OWNER, READ_MODEL, "model:catalog")


def model_revision_grant(binding: ExactModelBinding) -> ExactGrant:
    return ExactGrant(
        MODEL_OWNER,
        READ_MODEL,
        f"model:revision:{_part(binding.resource_id)}:"
        f"{_part(binding.revision_id)}:{binding.digest}",
    )


def bind_model_use(
    *,
    consumer_kind: str,
    consumer_id: str,
    consumer_revision_id: str,
    binding: ExactModelBinding,
) -> ExactModelUse:
    resource = (
        f"model:binding:{_part(consumer_kind)}:{_part(consumer_id)}:"
        f"{_part(consumer_revision_id)}:{_part(binding.resource_id)}:"
        f"{_part(binding.revision_id)}:{binding.digest}"
    )
    return ExactModelUse(binding, ModelUseAction.BIND_MODEL, resource)


def invoke_model_use(
    *,
    attempt_id: str,
    binding_snapshot_id: str,
    binding: ExactModelBinding,
) -> ExactModelUse:
    resource = (
        f"model:invocation:{_part(attempt_id)}:{_part(binding_snapshot_id)}:"
        f"{_part(binding.resource_id)}:{_part(binding.revision_id)}:{binding.digest}"
    )
    return ExactModelUse(binding, ModelUseAction.INVOKE_MODEL, resource)


def model_management_grant(
    operation: ModelManagementOperation,
    model_id: str,
    target_revision_or_new: str,
) -> ExactGrant:
    if not isinstance(operation, ModelManagementOperation):
        raise ValueError("INVALID_MODEL_GRANT_TARGET")
    return ExactGrant(
        MODEL_OWNER,
        MANAGE_MODEL_REVISION,
        f"model:management:{operation.value}:{_part(model_id)}:"
        f"{_part(target_revision_or_new)}",
    )


def model_definition_reference(model_id: str) -> str:
    return f"model:definition:{_part(model_id)}"


def model_definition_owner_revision(definition: ModelDefinition) -> str:
    return f"definition:{definition.aggregate_version}"


def authority_scope(scope: ModelConsumptionScope) -> AuthorityScope:
    return AuthorityScope(scope.namespace, scope.security_domain)


def model_scope(scope: AuthorityScope) -> ModelScope:
    return ModelScope(scope.tenant_id, scope.security_domain)


@dataclass(frozen=True, slots=True)
class CurrentExactGrantDecision:
    """Current authority result supplied by the shared authority owner."""

    decision_id: str
    context: TrustedRequestContext
    grant: ExactGrant
    policy_generation: int
    policy_version: str
    issued_at: datetime
    expires_at: datetime


class CurrentExactGrantDecisionReader(Protocol):
    def authorize_current(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        now: datetime,
    ) -> CurrentExactGrantDecision | None: ...


class ModelUseAuthorizationAdapter:
    """Translate shared trusted authority into the Model consumer port."""

    def __init__(
        self,
        context: TrustedRequestContext,
        decisions: CurrentExactGrantDecisionReader,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.context = context
        self.decisions = decisions
        self.clock = clock

    def authorize_use(
        self,
        scope: ModelConsumptionScope,
        subject: ModelUseSubject,
        use: ExactModelUse,
    ) -> AuthorizedModelUse | None:
        if (
            authority_scope(scope) != self.context.scope
            or subject.principal_id != self.context.principal_id
        ):
            return None
        grant = ExactGrant(MODEL_OWNER, use.action.value, use.exact_resource)
        validate_registered_grant(grant, allow_meta=False)
        now = self.clock()
        decision = self.decisions.authorize_current(self.context, grant, now=now)
        if (
            decision is None
            or decision.context != self.context
            or decision.grant != grant
            or not decision.decision_id
            or decision.policy_version == ""
            or isinstance(decision.policy_generation, bool)
            or decision.policy_generation < 1
            or now.tzinfo is None
            or decision.issued_at.tzinfo is None
            or decision.expires_at.tzinfo is None
            or decision.issued_at > now
            or now >= decision.expires_at
        ):
            return None
        return AuthorizedModelUse(
            decision.decision_id,
            subject,
            scope,
            use,
            decision.policy_generation,
            decision.policy_version,
            decision.issued_at,
            decision.expires_at,
        )


class ModelGovernanceExactResolver:
    """Resolve the exact Model graph from the three owner ports."""

    def __init__(
        self,
        definitions: ModelDefinitionRepository,
        revisions: ModelRevisionRepository,
        configurations: ModelProviderConfigurationRepository,
    ) -> None:
        self.definitions = definitions
        self.revisions = revisions
        self.configurations = configurations

    def resolve_exact(
        self, scope: ModelConsumptionScope, binding: ExactModelBinding
    ) -> ResolvedModelBinding | None:
        owner_scope = ModelScope(scope.namespace, scope.security_domain)
        try:
            self.definitions.get(owner_scope, binding.resource_id)
            revision = self.revisions.get_revision(
                owner_scope, binding.resource_id, binding.revision_id
            )
        except ModelGovernanceNotFound:
            return None
        if revision.digest != binding.digest:
            return None
        # A zero-fact revision deliberately preserves MODEL_LIFECYCLE_NOT_FOUND.
        eligibility = self.revisions.read_lifecycle(
            owner_scope, binding.resource_id, binding.revision_id
        )
        try:
            configuration = self.configurations.resolve_exact(
                owner_scope,
                revision.provider,
                revision.endpoint,
                revision.connection_profile,
            )
        except ModelGovernanceNotFound:
            return None
        return ResolvedModelBinding(
            scope,
            binding,
            configuration.provider.identity,
            configuration.endpoint.identity,
            configuration.connection_profile.identity,
            eligibility,
        )


class CreatorContinuationPort(Protocol):
    def mint_owner_continuation(
        self,
        context: TrustedRequestContext,
        claim: ContinuationClaim,
        *,
        originating_command_key: str,
    ) -> str: ...


class ModelCreatorContinuationAdapter:
    """Mint the creator's request opportunity after the Definition commit."""

    def __init__(
        self,
        continuations: CreatorContinuationPort,
        *,
        policy_generation: int,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        identity_factory: Callable[[], str] = lambda: (
            f"model-creator-continuation-{secrets.token_hex(16)}"
        ),
    ) -> None:
        self.continuations = continuations
        self.policy_generation = policy_generation
        self.clock = clock
        self.identity_factory = identity_factory

    def mint_after_create(
        self,
        context: TrustedRequestContext,
        definition: ModelDefinition,
        *,
        request_purpose: str,
        originating_command_key: str,
        expires_at: datetime,
    ) -> str:
        issued_at = self.clock()
        require_bounded_label(
            request_purpose, reason_code="MODEL_CREATOR_CONTINUATION_INVALID"
        )
        if (
            model_scope(context.scope) != definition.scope
            or definition.created_by != context.principal_id
            or definition.aggregate_version != 1
            or definition.current_revision_id is not None
            or not originating_command_key
            or len(originating_command_key) > 200
            or originating_command_key.strip() != originating_command_key
            or isinstance(self.policy_generation, bool)
            or self.policy_generation < 1
            or issued_at.tzinfo is None
            or expires_at.tzinfo is None
            or expires_at <= issued_at
            or expires_at - issued_at > timedelta(minutes=10)
        ):
            raise ValueError("MODEL_CREATOR_CONTINUATION_INVALID")
        nonce = self.identity_factory()
        if not nonce:
            raise ValueError("MODEL_CREATOR_CONTINUATION_INVALID")
        claim = ContinuationClaim(
            nonce=nonce,
            subject_principal_id=context.principal_id,
            scope=context.scope,
            purpose=request_purpose,
            members=(
                model_management_grant(
                    ModelManagementOperation.REVISE,
                    definition.model_id,
                    "new",
                ),
            ),
            canonical_resource_reference=model_definition_reference(
                definition.model_id
            ),
            owner_revision=model_definition_owner_revision(definition),
            policy_generation=self.policy_generation,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return self.continuations.mint_owner_continuation(
            context,
            claim,
            originating_command_key=originating_command_key,
        )


class ModelGrantTargetLookup(Protocol):
    def is_known_exact_target(
        self,
        scope: ModelScope,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool: ...

    def is_current_creator_definition(
        self,
        scope: ModelScope,
        *,
        principal_id: str,
        canonical_resource_reference: str,
        owner_revision: str,
        connection: object | None = None,
    ) -> bool: ...


class ModelCreatorGrantTargetValidator:
    """Grant Administration owner adapter for Model creator continuations."""

    def __init__(self, lookup: ModelGrantTargetLookup) -> None:
        self.lookup = lookup

    def is_known_exact_target(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool:
        if grant.owner != MODEL_OWNER:
            return False
        try:
            validate_registered_grant(grant, allow_meta=False)
        except ValueError:
            return False
        return self.lookup.is_known_exact_target(
            model_scope(context.scope), grant, connection=connection
        )

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool:
        if (
            not claim.members
            or any(
                member.owner != MODEL_OWNER
                or member.action not in {READ_MODEL, MANAGE_MODEL_REVISION}
                for member in claim.members
            )
            or not self.lookup.is_current_creator_definition(
                model_scope(claim.scope),
                principal_id=claim.subject_principal_id,
                canonical_resource_reference=claim.canonical_resource_reference,
                owner_revision=claim.owner_revision,
                connection=connection,
            )
        ):
            return False
        return all(
            self.lookup.is_known_exact_target(
                model_scope(claim.scope), member, connection=connection
            )
            for member in claim.members
        )

    def validate_offer(
        self,
        scope: AuthorityScope,
        members: Sequence[ExactGrant],
        canonical_resource_reference: str,
        owner_revision: str,
    ) -> bool:
        # This bounded adapter is creator-facing; assignment remains with its owner.
        return False


class PostgresModelGrantTargetLookup:
    """Read Model owner facts on Grant Administration's caller transaction."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository

    @contextmanager
    def _connection(self, connection: object | None):
        if connection is not None:
            yield connection
        else:
            with self.repository.pool.connection() as owned:
                yield owned

    def is_known_exact_target(
        self,
        scope: ModelScope,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool:
        if grant == create_model_grant() or grant == model_catalog_grant():
            return True
        with self._connection(connection) as current:
            if grant.action == READ_MODEL:
                row = current.execute(
                    "SELECT EXISTS(SELECT 1 FROM model_governance.model_revisions "
                    "WHERE namespace=%s AND security_domain=%s AND "
                    "concat('model:revision:',model_id,':',revision_id,':',digest)=%s)"
                    " AS known",
                    (scope.namespace, scope.security_domain, grant.exact_resource),
                ).fetchone()
                return bool(row["known"])
            if grant.action == MANAGE_MODEL_REVISION:
                row = current.execute(
                    "SELECT EXISTS("
                    "SELECT 1 FROM model_governance.definitions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:REVISE:',"
                    "model_id,':new')=%s UNION ALL "
                    "SELECT 1 FROM model_governance.model_revisions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:PUBLISH:',"
                    "model_id,':',revision_id)=%s UNION ALL "
                    "SELECT 1 FROM model_governance.model_revisions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:DISABLE:',"
                    "model_id,':',revision_id)=%s UNION ALL "
                    "SELECT 1 FROM model_governance.model_revisions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:ENABLE:',"
                    "model_id,':',revision_id)=%s UNION ALL "
                    "SELECT 1 FROM model_governance.model_revisions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:DEPRECATE:',"
                    "model_id,':',revision_id)=%s UNION ALL "
                    "SELECT 1 FROM model_governance.model_revisions WHERE namespace=%s "
                    "AND security_domain=%s AND concat('model:management:REVOKE:',"
                    "model_id,':',revision_id)=%s) AS known",
                    (
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                        scope.namespace,
                        scope.security_domain,
                        grant.exact_resource,
                    ),
                ).fetchone()
                return bool(row["known"])
        return False

    def is_current_creator_definition(
        self,
        scope: ModelScope,
        *,
        principal_id: str,
        canonical_resource_reference: str,
        owner_revision: str,
        connection: object | None = None,
    ) -> bool:
        with self._connection(connection) as current:
            row = current.execute(
                "SELECT EXISTS(SELECT 1 FROM model_governance.definitions "
                "WHERE namespace=%s AND security_domain=%s AND created_by=%s "
                "AND concat('model:definition:',model_id)=%s "
                "AND concat('definition:',aggregate_version)=%s) AS known",
                (
                    scope.namespace,
                    scope.security_domain,
                    principal_id,
                    canonical_resource_reference,
                    owner_revision,
                ),
            ).fetchone()
            return bool(row["known"])
