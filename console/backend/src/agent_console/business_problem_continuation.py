"""Creator-only post-commit continuation coordination for Business Problems."""

from __future__ import annotations

import secrets
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from agent_console.authority_contracts import (
    AuthorityError,
    AuthorityScope,
    ContinuationClaim,
    ExactGrant,
    TrustedRequestContext,
)
from agent_console.business_problem_domain import (
    BusinessProblemCreatorReceipt,
    BusinessProblemError,
    problem_creator_mint_key,
)
from agent_console.business_problem_repository import BusinessProblemRepository
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import GrantAdministrationService
from agent_console.workbench_bff_schemas import (
    WorkbenchProblemCreatorContinuation,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


class BusinessProblemContinuationValidator:
    """Validate only receipt-minted creator continuations; direct targets stay shut."""

    def __init__(self, repository: BusinessProblemRepository) -> None:
        self.repository = repository

    def is_known_exact_target(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool:
        del context, grant, connection
        return False

    def validate_offer(
        self,
        scope: AuthorityScope,
        members: Sequence[ExactGrant],
        canonical_resource_reference: str,
        owner_revision: str,
    ) -> bool:
        del scope, members, canonical_resource_reference, owner_revision
        return False

    def validate_continuation(
        self, claim: ContinuationClaim, *, connection: object | None = None
    ) -> bool:
        prefix = "business-problem:"
        if (
            claim.purpose != "CONTINUE_PROBLEM_READ"
            or len(claim.members) != 1
            or not claim.canonical_resource_reference.startswith(prefix)
            or claim.members[0]
            != ExactGrant(
                "BUSINESS_PROBLEM",
                "READ",
                claim.canonical_resource_reference,
            )
        ):
            return False
        business_problem_id = claim.canonical_resource_reference.removeprefix(prefix)
        if not business_problem_id:
            return False
        try:
            receipt = self.repository.get_creator_receipt_for_problem(
                ScopeIdentity(
                    claim.scope.tenant_id,
                    claim.scope.security_domain,
                ),
                claim.subject_principal_id,
                business_problem_id,
                authorized=True,
                connection=connection,
            )
        except BusinessProblemError:
            return False
        return (
            receipt.creator_principal_id == claim.subject_principal_id
            and receipt.scope.namespace == claim.scope.tenant_id
            and receipt.scope.security_domain == claim.scope.security_domain
            and receipt.canonical_resource_reference
            == claim.canonical_resource_reference
            and receipt.committed_owner_revision == claim.owner_revision
            and receipt.policy_generation == claim.policy_generation
            and receipt.receipt_started_at == claim.issued_at
            and receipt.expires_at == claim.expires_at
        )


class BusinessProblemCreateCoordinator:
    """Run only after owner commit and recover one immutable creator offer."""

    def __init__(
        self,
        grants: GrantAdministrationService,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        identity_factory: Callable[[str], str] = lambda prefix: (
            f"{prefix}-{secrets.token_hex(16)}"
        ),
    ) -> None:
        self.grants = grants
        self.clock = clock
        self.identity_factory = identity_factory

    @staticmethod
    def _claim(receipt: BusinessProblemCreatorReceipt, nonce: str) -> ContinuationClaim:
        return ContinuationClaim(
            nonce=nonce,
            subject_principal_id=receipt.creator_principal_id,
            scope=AuthorityScope(
                receipt.scope.namespace,
                receipt.scope.security_domain,
            ),
            purpose="CONTINUE_PROBLEM_READ",
            members=(
                ExactGrant(
                    "BUSINESS_PROBLEM",
                    "READ",
                    receipt.canonical_resource_reference,
                ),
            ),
            canonical_resource_reference=receipt.canonical_resource_reference,
            owner_revision=receipt.committed_owner_revision,
            policy_generation=receipt.policy_generation,
            issued_at=receipt.receipt_started_at,
            expires_at=receipt.expires_at,
        )

    def __call__(
        self, context: TrustedRequestContext, owner_result: Any
    ) -> Mapping[str, Any]:
        if not isinstance(owner_result, dict) or set(owner_result) != {
            "revision",
            "_creatorReceipt",
        }:
            raise WorkbenchOwnerError("CREATOR_RECEIPT_REQUIRED", 409)
        receipt = owner_result["_creatorReceipt"]
        if not isinstance(receipt, BusinessProblemCreatorReceipt):
            raise WorkbenchOwnerError("CREATOR_RECEIPT_REQUIRED", 409)
        if receipt.recovery_epoch != self.grants.recovery_epoch:
            raise WorkbenchOwnerError("CREATOR_CONTINUATION_INVALIDATED", 409)
        claim = self._claim(
            receipt,
            self.identity_factory("continuation-offer"),
        )
        mint_key = problem_creator_mint_key(receipt)
        try:
            recovered = self.grants.recover_owner_continuation(
                context,
                claim,
                originating_command_key=mint_key,
            )
            if recovered is None and self.clock() < receipt.expires_at:
                self.grants.mint_owner_continuation(
                    context,
                    claim,
                    originating_command_key=mint_key,
                )
                recovered = self.grants.recover_owner_continuation(
                    context,
                    claim,
                    originating_command_key=mint_key,
                )
                if recovered is None:
                    raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")
        except AuthorityError as exc:
            if exc.reason_code in {
                "AUTHORITY_STORAGE_UNAVAILABLE",
                "AUTHORITY_RECOVERY_REQUIRED",
            }:
                raise WorkbenchOwnerError("CONTINUATION_MINT_UNAVAILABLE", 503) from exc
            raise WorkbenchOwnerError("CREATOR_CONTINUATION_INVALIDATED", 409) from exc

        now = self.clock()
        state = (
            "CONSUMED"
            if recovered is not None and recovered.request_id is not None
            else "EXPIRED"
            if now >= receipt.expires_at
            else "AVAILABLE"
        )
        continuation = WorkbenchProblemCreatorContinuation(
            state=state,
            expiresAt=receipt.expires_at,
            continuationId=(
                recovered.continuation_id if recovered is not None else None
            ),
            requestId=recovered.request_id if recovered is not None else None,
        )
        return {
            "revision": owner_result["revision"],
            "creatorContinuation": continuation.model_dump(
                mode="json", exclude_none=True
            ),
        }
