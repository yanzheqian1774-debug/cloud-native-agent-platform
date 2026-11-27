"""Read current service execution authority through original Native owners."""

from .authority_contracts import AuthenticationSource, AuthorityError
from .bound_service_execution import BoundServiceExecutionBridge
from .native_wait_command_access import NativeWaitCommandAccess
from .native_wait_owner import NativeWaitOwner


class FixedQuestionExecutionAuthority:
    def __init__(self, runtime, execution, work):
        if (
            runtime.durable_wait is None
            or not isinstance(
                runtime.bound_service_execution, BoundServiceExecutionBridge
            )
            or runtime.authorize_current is None
        ):
            raise TypeError("FIXED_QUESTION_SERVICE_RUNTIME_REQUIRED")
        self.access = NativeWaitCommandAccess(runtime, execution, work)

    def __call__(self, c, cp):
        i = cp.identity
        row = c.execute(
            "SELECT payload FROM execution_authority.native_dispatch_commands "
            "WHERE namespace=%s AND security_domain=%s AND command_id=%s",
            (i.namespace, i.security_domain, i.command_id),
        ).fetchone()
        if row is None:
            raise AuthorityError("FIXED_QUESTION_COMMAND_REQUIRED")
        command = self.access.execution._dispatch_command(row["payload"])
        if (
            str(command.command_id) != i.command_id
            or str(command.attempt_id) != i.attempt_id
            or command.principal_id != i.principal_id
            or not command.principal_id.startswith("service:")
            or AuthenticationSource(command.authentication_source)
            is not AuthenticationSource.SERVICE_CREDENTIAL
        ):
            raise AuthorityError("FIXED_QUESTION_COMMAND_BINDING_INVALID")

        def authorize(connection, checkpoint, operation):
            if (
                connection is not c
                or checkpoint != cp
                or operation != "DELEGATION_VALIDATE"
            ):
                raise AuthorityError("FIXED_QUESTION_COMMAND_OPERATION_INVALID")
            self.access._authorize(connection, checkpoint, command)

        # Original command -> Skill -> progress -> root checks, on caller's
        # already chat-locked connection. This does not claim or advance anything.
        NativeWaitOwner(authorize, None)._lock(c, cp, "DELEGATION_VALIDATE")
