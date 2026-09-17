"""Human-approved single synthetic creation; no provider or initializer."""

from dataclasses import replace

from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.business_problem_domain import BusinessProblemError
from agent_console.execution_domain import ScopeIdentity
from agent_console.workbench_owner_authorization import WorkbenchOwnerError

CREATE_KEY = "s5-319-human-confirmed-problem-v2"
TITLE = "将供应商来料缺陷率降至低于1%"
DESCRIPTION = (
    "供应商来料质量存在问题。目标是在季度末前将来料缺陷率\n"
    "降至低于1%\uff0c并由质量负责人确认结果。具体季度、\n"
    "供应商范围、当前缺陷率基线及测量口径尚待明确。"
)
PAYLOAD = {
    "title": TITLE,
    "description": DESCRIPTION,
    "ownerId": "human:alice",
    "idempotencyKey": CREATE_KEY,
}


def require_identity(context, principal="human:alice"):
    if (
        context.principal_id != principal
        or context.scope.tenant_id != "tenant-a"
        or context.scope.security_domain != "quality"
    ):
        raise AuthorityError("AUTHORIZATION_NOT_FOUND")


def restricted_operation(operation):
    def handler(call):
        require_identity(call.context)
        if dict(call.payload) != PAYLOAD:
            raise WorkbenchOwnerError("ACCEPTANCE_CREATE_MISMATCH", 403)
        return operation.handler(call)

    return replace(operation, handler=handler)


class RestrictedReadGrants:
    """Delegate legitimate grants only for the durable fixed-key owner receipt."""

    def __init__(self, grants, problems):
        self.grants = grants
        self.problems = problems

    def target(self):
        try:
            receipt = self.problems.get_creator_receipt(
                ScopeIdentity("tenant-a", "quality"),
                "human:alice",
                CREATE_KEY,
                authorized=True,
            )
        except BusinessProblemError as exc:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND") from exc
        return ExactGrant(
            "BUSINESS_PROBLEM", "READ", receipt.canonical_resource_reference
        )

    def check_request(self, request):
        if (
            request.subject_principal_id != "human:alice"
            or request.scope.tenant_id != "tenant-a"
            or request.scope.security_domain != "quality"
            or tuple(request.members) != (self.target(),)
            or request.purpose != "CONTINUE_PROBLEM_READ"
        ):
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")

    def submit_request(self, context, command):
        require_identity(context)
        prefix = self.grants._CONTINUATION_REFERENCE_PREFIX
        if (
            command.requested_grants
            or not command.continuation
            or not command.continuation.startswith(prefix)
        ):
            raise AuthorityError("INVALID_GRANT_TARGET")
        claim = self.grants.repository.resolve_continuation_offer(
            command.continuation.removeprefix(prefix),
            context,
            now=self.grants.clock(),
            recovery_epoch=self.grants.recovery_epoch,
        )
        if claim.purpose != "CONTINUE_PROBLEM_READ" or tuple(claim.members) != (
            self.target(),
        ):
            raise AuthorityError("INVALID_GRANT_TARGET")
        return self.grants.submit_request(context, command)

    def inspect_request(self, context, request_id):
        require_identity(context, context.principal_id)
        if context.principal_id not in {"human:alice", "human:admin"}:
            raise AuthorityError("GRANT_REQUEST_NOT_FOUND")
        request = self.grants.inspect_request(context, request_id)
        self.check_request(request)
        return request

    def decide_request(self, context, command):
        require_identity(context, "human:admin")
        self.inspect_request(context, command.request_id)
        return self.grants.decide_request(context, command)

    def continuation_inbox_details(self, context):
        require_identity(context)
        # This acceptance page obtains the exact continuation from CREATE.
        return ()
