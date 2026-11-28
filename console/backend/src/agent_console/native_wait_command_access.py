# ruff: noqa: E501 -- Exact scoped owner SQL.
"""Host process observation bridge; positive waiting is never new execution authority."""

from datetime import UTC, datetime

from agent_runtime.native_loop import digest

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    TrustedRequestContext,
)
from .native_host_provenance import lock_identity, validate
from .native_wait_owner import NativeWaitOwner
from .native_wait_store import NativeWaitStore
from .native_wait_types import StopObservation, WaitIdentity


class NativeWaitCommandAccess:
    def __init__(self, runtime, execution, work):
        self.runtime, self.execution, self.work = runtime, execution, work

    def _load(self, c, candidate):
        if self.runtime.durable_wait is None:
            return None
        rows = c.execute(
            "SELECT n.payload,h.state,h.checkpoint_digest,cp.record FROM "
            "execution_authority.native_dispatch_commands n "
            "JOIN skill_invocation.invocations i USING(namespace,security_domain,attempt_id) "
            "JOIN skill_invocation.native_wait_heads h USING(namespace,security_domain,skill_invocation_id) "
            "JOIN skill_invocation.native_wait_checkpoints cp USING(namespace,security_domain,skill_invocation_id,checkpoint_digest) "
            "WHERE n.namespace=%s AND n.security_domain=%s AND n.principal_id=%s "
            "AND n.authorization_resource=%s AND n.state='EFFECT_STARTED' "
            "AND n.terminal_record IS NULL AND h.state<>'COMPLETED'",
            (
                candidate["namespace"],
                candidate["securityDomain"],
                candidate["principalId"],
                "governed-execution:prepared:" + candidate["preparationDigest"],
            ),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise AuthorityError("NATIVE_WAIT_COMMAND_AMBIGUOUS")
        row = rows[0]
        command = self.execution._dispatch_command(row["payload"])
        identity = WaitIdentity.model_validate(row["record"]["identity"])
        cp = NativeWaitStore(c, identity).checkpoint(row["checkpoint_digest"])
        if (
            identity.command_id != str(command.command_id)
            or identity.workflow_run_id != candidate["runId"]
            or identity.preparation_digest != candidate["preparationDigest"]
            or identity.principal_id != command.principal_id
        ):
            raise AuthorityError("NATIVE_WAIT_HOST_BINDING_CHANGED")
        return cp, command, row["state"]

    def _authorize(self, c, cp, command):
        from .ontology_execution import parse_preparation
        from .prepared_execution_lineage import prepared_attempt

        if (
            self.runtime.authorize_current is None
            or not self.runtime.authorize_current(c, command)
            or datetime.now(UTC) >= self.runtime.expiry
        ):
            raise AuthorityError("NATIVE_WAIT_CURRENT_AUTHORITY_REQUIRED")
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(command.scope.namespace, command.scope.security_domain),
            command.credential_id,
            AuthenticationSource(command.authentication_source),
            self.runtime.generation.policy_version,
        )
        row = prepared_attempt(c, command.scope, command.attempt_id)
        if row is None:
            raise AuthorityError("NATIVE_WAIT_PREPARATION_REQUIRED")
        p = parse_preparation(row["preparation"])
        if command.principal_id.startswith("service:"):
            reader = getattr(self.runtime, "bound_service_execution", None)
            if reader is None:
                raise AuthorityError("NATIVE_WAIT_SERVICE_BINDING_REQUIRED")
            binding = reader.read(c, context, command, p)
            bound_source = binding.source
            if cp.identity.conversation_id != binding.conversation_id:
                raise AuthorityError("NATIVE_WAIT_SERVICE_BINDING_CHANGED")
        else:
            from .owned_resource_assembly import prepared_binding

            binding = prepared_binding(self.work.owned_business, c, context, command, p)
            bound_source = binding.scope.source
        config = self.runtime.durable_wait
        if (
            bound_source != p.source_snapshot
            or cp.identity.preparation_digest != p.digest
            or cp.source_digest != p.source_snapshot.digest
            or cp.identity.task_id != row["task_id"]
            or cp.model_profile_digest != self.runtime.config["modelRuntimeDigest"]
            or cp.maximum_decisions != self.runtime.config["maximumDecisions"]
            or cp.authority_expires_at > min(binding.expires_at, self.runtime.expiry)
            or (cp.executor_id, cp.executor_revision, cp.executor_configuration_digest)
            != (
                config.executorId,
                config.executorRevision,
                config.executorConfigurationDigest,
            )
        ):
            raise AuthorityError("NATIVE_WAIT_RUNTIME_BINDING_CHANGED")

    def inspect(self, c, candidate):
        value = self._load(c, candidate)
        if value is None:
            return None
        cp, command, state = value
        self._authorize(c, cp, command)
        store = NativeWaitStore(c, cp.identity)
        stopped = store.observation(cp.digest, "STOP_CONFIRMED")
        answer = store.observation(cp.digest, "ANSWER_SAVED")
        continuation = c.execute(
            "SELECT record FROM skill_invocation.native_wait_continuations WHERE "
            "namespace=%s AND security_domain=%s AND skill_invocation_id=%s AND checkpoint_digest=%s",
            (*cp.identity.skill_key, cp.digest),
        ).fetchone()
        active = continuation["record"] if continuation else None
        return {
            "state": state,
            "checkpointDigest": cp.digest,
            "questionKey": cp.question_key,
            "resumable": bool(
                state == "ANSWER_SAVED"
                and stopped
                and answer
                and datetime.now(UTC) < cp.authority_expires_at
            ),
            "activeWorkerId": active["worker_id"] if active else cp.worker_id,
            "startupRecordDigest": active["startup_record_digest"]
            if active
            else cp.startup_record_digest,
        }

    def stopped(
        self, c, candidate, process_record, startup_record, exit_receipt, verify_exit
    ):
        value = self._load(c, candidate)
        if value is None:
            return None
        cp, command, _state = value
        startup = validate(startup_record, cp.worker_id)
        expected = {
            "namespace": cp.identity.namespace,
            "securityDomain": cp.identity.security_domain,
            "principalId": cp.identity.principal_id,
            "preparationDigest": cp.identity.preparation_digest,
            "runId": cp.identity.workflow_run_id,
            "workerId": cp.worker_id,
        }
        if (
            any(process_record.get(k) != v for k, v in expected.items())
            or startup_record["digest"] != cp.startup_record_digest
            or process_record.get("startupDigest") != cp.startup_record_digest
            or process_record.get("pid") != startup.get("pid")
            or process_record.get("processBirth") != startup.get("processBirth")
            or process_record.get("released") is not True
            or exit_receipt.get("state") != "EXIT_CONFIRMED"
        ):
            raise AuthorityError("NATIVE_WAIT_STOP_BINDING_INVALID")
        observed = StopObservation(
            checkpoint_digest=cp.digest,
            command_id=cp.identity.command_id,
            worker_id=cp.worker_id,
            startup_record_digest=cp.startup_record_digest,
            process_identity_digest=digest(
                {
                    k: process_record.get(k)
                    for k in (
                        "pid",
                        "processBirth",
                        "boot",
                        "startupDigest",
                        "workerId",
                    )
                }
            ),
            exit_receipt_digest=digest(exit_receipt),
            stopped_at=datetime.fromisoformat(exit_receipt["stoppedAt"]),
        )

        def authorize(connection, supplied, operation):
            if supplied != cp or operation != "STOP_OBSERVATION":
                raise AuthorityError("NATIVE_WAIT_STOP_OPERATION_REQUIRED")
            lock_identity(connection, startup_record, cp.worker_id)
            self._authorize(connection, cp, command)

        NativeWaitOwner(authorize, None).confirm_stopped(c, cp, observed, verify_exit)
        return {"checkpointDigest": cp.digest, "stopRecorded": True}
