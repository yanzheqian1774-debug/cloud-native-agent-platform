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


@dataclass(frozen=True, slots=True)
class WorkbenchAuthorizationDecision:
    decision_id: str
    principal_id: str
    owner: str
    action: str
    exact_resource: str


@dataclass(frozen=True, slots=True)
class AuthorizedOwnerCall:
    """Only input accepted by a browser-enabled owner adapter."""

    operation: str
    context: TrustedRequestContext
    connection: Any
    payload: Mapping[str, Any]
    path: Mapping[str, str]
    decisions: tuple[WorkbenchAuthorizationDecision, ...]


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
            allowed = self.authorization.has_current_grants(
                context,
                grants,
                now=self.clock(),
                generation=generation.generation,
                recovery_epoch=self.controller.readiness.recovery_epoch,
                connection=connection,
            )
            if not all(allowed):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            decisions = tuple(
                self._decision(context, grant, generation.generation)
                for grant in grants
            )
            return handler(
                AuthorizedOwnerCall(
                    operation=operation,
                    context=context,
                    connection=connection,
                    payload=payload,
                    path=path,
                    decisions=decisions,
                )
            )
