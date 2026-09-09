"""Current exact-grant adapter for caller-owned owner transactions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar

from agent_console.authority_configuration import validate_registered_grant
from agent_console.authority_contracts import (
    AuthorityError,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.authority_foundation import AuthorityGenerationController
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.grant_administration_application import GenerationAuthorizationReader

T = TypeVar("T")


class WorkbenchOwnerError(ValueError):
    def __init__(self, reason_code: str, status_code: int) -> None:
        self.reason_code = reason_code
        self.status_code = status_code
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class WorkbenchAuthorizationDecision:
    decision_id: str
    principal_id: str
    owner: str
    action: str
    exact_resource: str


class AuthorizedOwnerAuthority:
    """Owner-facing current-grant port pinned to the caller transaction."""

    def __init__(
        self,
        adapter: WorkbenchOwnerAuthorization,
        context: TrustedRequestContext,
        connection: Any,
        generation: int,
        initial: Sequence[WorkbenchAuthorizationDecision],
    ) -> None:
        self.adapter = adapter
        self.context = context
        self.connection = connection
        self.generation = generation
        self.decisions = {
            (item.owner, item.action, item.exact_resource): item for item in initial
        }

    def require(self, principal, owner: str, action: str, resource: str):
        if (
            principal.principal_id != self.context.principal_id
            or principal.tenant_id != self.context.scope.tenant_id
            or principal.security_domain != self.context.scope.security_domain
        ):
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        grant = ExactGrant(owner, action, resource)
        validate_registered_grant(grant, allow_meta=False)
        key = (owner, action, resource)
        decision = self.decisions.get(key)
        if decision is not None:
            return decision
        allowed = self.adapter.authorization.has_current_grants(
            self.context,
            (grant,),
            now=self.adapter.clock(),
            generation=self.generation,
            recovery_epoch=self.adapter.controller.readiness.recovery_epoch,
            connection=self.connection,
            configure_transaction=False,
        )[0]
        if not allowed:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        decision = self.adapter._decision(self.context, grant, self.generation)
        self.decisions[key] = decision
        return decision


@dataclass(frozen=True, slots=True)
class AuthorizedOwnerCall:
    """Only input accepted by a browser-enabled owner adapter."""

    operation: str
    context: TrustedRequestContext
    connection: Any
    payload: Mapping[str, Any]
    path: Mapping[str, str]
    query: Mapping[str, Any]
    decisions: tuple[WorkbenchAuthorizationDecision, ...]
    authority: AuthorizedOwnerAuthority


class TransactionalOwnerHandler(Protocol[T]):
    def __call__(self, call: AuthorizedOwnerCall) -> T: ...


class WorkbenchOwnerAuthorization:
    """Pin I1 generation and current grants through the owner commit boundary."""

    def __init__(
        self,
        controller: AuthorityGenerationController,
        repository: PostgresAuthorityRepository,
        authorization: GenerationAuthorizationReader,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.controller = controller
        self.repository = repository
        self.authorization = authorization
        self.clock = clock

    @staticmethod
    def _decision(
        context: TrustedRequestContext, grant: ExactGrant, generation: int
    ) -> WorkbenchAuthorizationDecision:
        semantic = json.dumps(
            {
                "principal": context.principal_id,
                "session": context.session_id_or_service_credential_id,
                "generation": generation,
                "owner": grant.owner,
                "action": grant.action,
                "resource": grant.exact_resource,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return WorkbenchAuthorizationDecision(
            decision_id=f"workbench-authorization:{hashlib.sha256(semantic).hexdigest()}",
            principal_id=context.principal_id,
            owner=grant.owner,
            action=grant.action,
            exact_resource=grant.exact_resource,
        )

    def execute(
        self,
        context: TrustedRequestContext,
        grants: Sequence[ExactGrant],
        *,
        operation: str,
        payload: Mapping[str, Any],
        path: Mapping[str, str],
        query: Mapping[str, Any],
        handler: TransactionalOwnerHandler[T],
    ) -> T:
        if not grants:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        for grant in grants:
            validate_registered_grant(grant, allow_meta=False)
        with (
            self.controller.protected_request() as generation,
            self.repository.connection_scope() as connection,
        ):
            # Owner idempotency claims intentionally serialize after this
            # authorization read. READ COMMITTED lets a waiter observe the
            # winner's completed claim while the session/grant share locks and
            # generation barrier still hold revocation behind this transaction.
            connection.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            allowed = self.authorization.has_current_grants(
                context,
                grants,
                now=self.clock(),
                generation=generation.generation,
                recovery_epoch=self.controller.readiness.recovery_epoch,
                connection=connection,
                configure_transaction=False,
            )
            if not all(allowed):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            decisions = tuple(
                self._decision(context, grant, generation.generation)
                for grant in grants
            )
            owner_authority = AuthorizedOwnerAuthority(
                self, context, connection, generation.generation, decisions
            )
            return handler(
                AuthorizedOwnerCall(
                    operation=operation,
                    context=context,
                    connection=connection,
                    payload=payload,
                    path=path,
                    query=query,
                    decisions=decisions,
                    authority=owner_authority,
                )
            )
