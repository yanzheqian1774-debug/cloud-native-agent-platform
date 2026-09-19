"""Formal exact-grant adapter for Draft Assistance bootstrap and admission."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from agent_console.authority_contracts import (
    AuthorityError,
    ExactGrant,
    GrantRequestStatus,
    TrustedRequestContext,
)
from agent_console.draft_assistance import (
    AuthorizationState,
    DispatchAdmission,
    DraftAssistanceError,
    DraftAssistanceRepository,
    DraftAuthorization,
    DraftBindingSnapshot,
    DraftInvocation,
    DraftScope,
)
from agent_console.grant_administration_application import (
    GrantAdministrationService,
    GrantRequestCommand,
)
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization

DRAFT_OWNER = "DRAFT_ASSISTANCE"
REQUEST = "REQUEST_DRAFT_ASSISTANCE"
READ = "READ_DRAFT_ASSISTANCE_INVOCATION"
CANCEL = "CANCEL_DRAFT_ASSISTANCE_INVOCATION"


def request_grant(invocation: DraftInvocation) -> ExactGrant:
    return ExactGrant(DRAFT_OWNER, REQUEST, invocation.request_target)


def model_grant(invocation: DraftInvocation) -> ExactGrant:
    return ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", invocation.model_target)


def read_grant(invocation: DraftInvocation) -> ExactGrant:
    return ExactGrant(
        DRAFT_OWNER,
        READ,
        f"draft-assistance:invocation:{invocation.invocation_id}",
    )


def cancel_grant(invocation: DraftInvocation) -> ExactGrant:
    return ExactGrant(
        DRAFT_OWNER,
        CANCEL,
        f"draft-assistance:invocation:{invocation.invocation_id}",
    )


class GrantAdministrationDraftAuthorization:
    """Recover the two formal requests and linearize current dispatch grants."""

    def __init__(
        self,
        grants: GrantAdministrationService,
        owner_authorization: WorkbenchOwnerAuthorization,
        *,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self.grants = grants
        self.owner_authorization = owner_authorization
        self.clock = clock

    def _current(self, context: TrustedRequestContext, grant: ExactGrant):
        return self.grants.authorization.authorize_current(
            context, grant, now=self.clock()
        )

    def require_usage(self, context, owner, action, resource):
        if self._current(context, ExactGrant(owner, action, resource)) is None:
            raise DraftAssistanceError("PROVIDER_USAGE_NOT_FOUND")

    def _submit(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        *,
        purpose: str,
        grants: Sequence[ExactGrant],
        suffix: str,
    ):
        return self.grants.submit_request(
            context,
            GrantRequestCommand(
                purpose=purpose,
                requested_grants=tuple(grants),
                idempotency_key=f"draft-authorization:{invocation.invocation_id}:{suffix}",
            ),
        )

    def resolve(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> DraftAuthorization:
        current = invocation.authorization
        request = request_grant(invocation)
        model = model_grant(invocation)
        try:
            if current is None:
                submitted = self._submit(
                    context,
                    invocation,
                    purpose="PROBLEM_DRAFT_ASSISTANCE",
                    grants=(request, read_grant(invocation), cancel_grant(invocation)),
                    suffix="request",
                )
                return DraftAuthorization(
                    AuthorizationState.PENDING,
                    submitted.request_id,
                    None,
                    "",
                    None,
                    submitted.aggregate_version,
                    0,
                )
            request_status = self.grants.inspect_request(
                context, current.request_authorization_request_id
            )
            if request_status.status is GrantRequestStatus.REJECTED:
                return DraftAuthorization(
                    AuthorizationState.DENIED,
                    request_status.request_id,
                    current.model_authorization_request_id,
                    "",
                    None,
                    request_status.aggregate_version,
                    current.model_version,
                )
            request_decision = self._current(context, request)
            if request_status.status is not GrantRequestStatus.APPROVED:
                return current
            if request_decision is None:
                return DraftAuthorization(
                    AuthorizationState.DENIED,
                    request_status.request_id,
                    current.model_authorization_request_id,
                    "",
                    None,
                    request_status.aggregate_version,
                    current.model_version,
                )
            model_request_id = current.model_authorization_request_id
            if model_request_id is None:
                submitted = self._submit(
                    context,
                    invocation,
                    purpose="PROBLEM_DRAFT_MODEL_INVOKE",
                    grants=(model,),
                    suffix="model",
                )
                return DraftAuthorization(
                    AuthorizationState.PENDING,
                    request_status.request_id,
                    submitted.request_id,
                    request_decision.decision_id,
                    None,
                    request_status.aggregate_version,
                    submitted.aggregate_version,
                )
            model_status = self.grants.inspect_request(context, model_request_id)
            if model_status.status is GrantRequestStatus.REJECTED:
                state = AuthorizationState.DENIED
                model_decision_id = None
            elif model_status.status is GrantRequestStatus.APPROVED:
                model_decision = self._current(context, model)
                state = (
                    AuthorizationState.ALLOWED
                    if model_decision is not None
                    else AuthorizationState.DENIED
                )
                model_decision_id = (
                    model_decision.decision_id if model_decision is not None else None
                )
            else:
                return current
            return DraftAuthorization(
                state,
                request_status.request_id,
                model_status.request_id,
                request_decision.decision_id,
                model_decision_id,
                request_status.aggregate_version,
                model_status.aggregate_version,
            )
        except AuthorityError as exc:
            raise DraftAssistanceError("DRAFT_AUTHORIZATION_UNAVAILABLE") from exc

    def _check(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        grant: ExactGrant,
    ) -> bool:
        try:
            return bool(
                self.owner_authorization.execute(
                    context,
                    (grant,),
                    operation="DRAFT_ASSISTANCE_CURRENT_GRANT",
                    payload={},
                    path={},
                    query={},
                    handler=lambda call: call.decisions,
                )
            )
        except AuthorityError:
            return False

    def can_read(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool:
        return self._check(context, invocation, read_grant(invocation))

    def can_cancel(
        self, context: TrustedRequestContext, invocation: DraftInvocation
    ) -> bool:
        return self._check(context, invocation, cancel_grant(invocation))

    def validate_current_and_admit(
        self,
        context: TrustedRequestContext,
        invocation: DraftInvocation,
        snapshot: DraftBindingSnapshot,
    ) -> DispatchAdmission | None:
        try:
            result = self.owner_authorization.execute(
                context,
                (request_grant(invocation), model_grant(invocation)),
                operation="DRAFT_ASSISTANCE_DISPATCH_ADMISSION",
                payload={},
                path={},
                query={},
                handler=lambda call: (
                    call.policy_generation,
                    call.recovery_epoch,
                    tuple(item.decision_id for item in call.decisions),
                ),
            )
        except AuthorityError:
            return None
        semantic = (
            f"{invocation.invocation_id}\0{snapshot.snapshot_digest}\0"
            f"{result[0]}\0{result[1]}\0{'|'.join(result[2])}"
        ).encode()
        return DispatchAdmission(
            f"dispatch-admission:{hashlib.sha256(semantic).hexdigest()}",
            int(result[0] or 0),
            self.clock() + timedelta(seconds=30),
        )


class DraftAssistanceGrantTargetValidator:
    """Validate exact targets from already-durable Draft Assistance identities."""

    def __init__(
        self,
        repository: DraftAssistanceRepository,
        *,
        model_target_validator=None,
    ) -> None:
        self.repository = repository
        self.model_target_validator = model_target_validator

    def is_known_exact_target(
        self,
        context: TrustedRequestContext,
        grant: ExactGrant,
        *,
        connection: object | None = None,
    ) -> bool:
        scope = DraftScope.from_context(context)
        if grant.owner == DRAFT_OWNER and grant.action == REQUEST:
            prefix = "draft-assistance:context:"
            if not grant.exact_resource.startswith(prefix):
                return False
            value = self.repository.find_by_target(
                scope, context.principal_id, grant.exact_resource
            )
            return value is not None and value.request_target == grant.exact_resource
        if grant.owner == DRAFT_OWNER and grant.action in {READ, CANCEL}:
            prefix = "draft-assistance:invocation:"
            if not grant.exact_resource.startswith(prefix):
                return False
            value = self.repository.find_by_target(
                scope, context.principal_id, grant.exact_resource
            )
            return (
                value is not None
                and value.initiating_principal_id == context.principal_id
            )
        if grant.owner == "MODEL_GOVERNANCE" and grant.action == "INVOKE_MODEL":
            value = self.repository.find_by_target(
                scope, context.principal_id, grant.exact_resource
            )
            matched = value is not None and value.model_target == grant.exact_resource
            return matched and (
                self.model_target_validator is None
                or self.model_target_validator.is_known_exact_target(
                    context, grant, connection=connection
                )
            )
        return False

    def validate_continuation(self, claim, *, connection=None) -> bool:
        del claim, connection
        return False

    def validate_offer(
        self, scope, members, canonical_resource_reference, owner_revision
    ):
        del scope, members, canonical_resource_reference, owner_revision
        return False
