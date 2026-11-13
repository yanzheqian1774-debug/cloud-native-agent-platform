"""Observe-first Operator worker for PostgreSQL-owned Native dispatch commands."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

from .errors import TaskExecutionError
from .runtime_identity_translation import (
    AppendDisposition,
    NativeDispatchClaim,
    NativeDispatchCommand,
    NativeTerminalKind,
    NativeTerminalObservation,
)
from .task_controller import invoke_compatible_agent


class NativeDispatchWorkerError(RuntimeError):
    pass


class DispatchRepository(Protocol):
    def claim_next(self, worker_id: str, **kwargs) -> NativeDispatchClaim | None: ...

    def resume_effect_started(self, worker_id: str) -> NativeDispatchClaim | None: ...

    def permit_effect(
        self, claim, task_name, authorization_check, **kwargs
    ) -> AppendDisposition: ...

    def record_kubernetes_correlation(
        self, claim, task_name, task_uid
    ) -> AppendDisposition: ...

    def record_uncertain(self, claim, observation) -> AppendDisposition: ...


class KubernetesTaskPort(Protocol):
    def create(self, claim: NativeDispatchClaim, task_name: str) -> dict: ...

    def read(self, claim: NativeDispatchClaim, task_name: str) -> dict | None: ...

    def patch_status(
        self, command: NativeDispatchCommand, task_name: str, status: dict
    ) -> None: ...


class NativeTransport(Protocol):
    def invoke(self, command: NativeDispatchCommand) -> str: ...


@dataclass(frozen=True, slots=True)
class DispatchRunResult:
    state: str
    command_id: str | None


@dataclass(slots=True)
class NativeDispatchAssembly:
    worker: NativeDispatchWorker
    execution_repository: object
    authority_repository: object
    prepared_skill_composition: object | None = None
    after_tick: Callable[[], object] | None = None

    def close(self) -> None:
        self.execution_repository.pool.close()
        self.authority_repository.close()
        if self.prepared_skill_composition is not None:
            self.prepared_skill_composition.close()


class KubernetesNativeTaskPort:
    """Real Kubernetes Task actual-state adapter; no public schema extension."""

    def __init__(self, api=None) -> None:
        if api is None:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config()
            api = client.CustomObjectsApi()
        self.api = api

    @staticmethod
    def _labels(command: NativeDispatchCommand) -> dict[str, str]:
        return {
            "agentos.io/native-dispatch-managed": "true",
            "agentos.io/native-dispatch-command": hashlib.sha256(
                str(command.command_id).encode()
            ).hexdigest()[:40],
        }

    @staticmethod
    def _annotations(claim: NativeDispatchClaim) -> dict[str, str]:
        command = claim.command
        return {
            "agentos.io/attempt-id": str(command.attempt_id),
            "agentos.io/placement-id": str(command.placement_id),
            "agentos.io/runtime-instance-id": str(command.runtime_instance_id),
            "agentos.io/runtime-generation": str(command.runtime_generation.value),
            "agentos.io/claim-generation": str(claim.claim_generation.value),
            "agentos.io/fencing-token-digest": hashlib.sha256(
                claim.fencing_token.encode()
            ).hexdigest(),
        }

    @classmethod
    def _matches(cls, claim: NativeDispatchClaim, body: dict) -> bool:
        metadata = body.get("metadata", {})
        labels = metadata.get("labels", {})
        annotations = metadata.get("annotations", {})
        return all(
            labels.get(key) == value
            for key, value in cls._labels(claim.command).items()
        ) and all(
            annotations.get(key) == value
            for key, value in cls._annotations(claim).items()
        )

    def create(self, claim: NativeDispatchClaim, task_name: str) -> dict:
        command = claim.command
        body = {
            "apiVersion": "agentos.io/v1alpha1",
            "kind": "Task",
            "metadata": {
                "name": task_name,
                "namespace": command.scope.namespace,
                "labels": self._labels(command),
                "annotations": self._annotations(claim),
            },
            "spec": {
                "agentRef": {"name": command.agent_name},
                "input": {"prompt": command.input_text},
                "timeoutSeconds": command.timeout_seconds,
            },
        }
        try:
            return self.api.create_namespaced_custom_object(
                group="agentos.io",
                version="v1alpha1",
                namespace=command.scope.namespace,
                plural="tasks",
                body=body,
            )
        except ApiException as exc:
            if exc.status != 409:
                raise
            existing = self.read(claim, task_name)
            if existing is None:
                raise NativeDispatchWorkerError(
                    "KUBERNETES_TASK_CORRELATION_CONFLICT"
                ) from exc
            return existing

    def read(self, claim: NativeDispatchClaim, task_name: str) -> dict | None:
        command = claim.command
        try:
            body = self.api.get_namespaced_custom_object(
                group="agentos.io",
                version="v1alpha1",
                namespace=command.scope.namespace,
                plural="tasks",
                name=task_name,
            )
        except ApiException as exc:
            if exc.status == 404:
                return None
            raise
        if not self._matches(claim, body):
            raise NativeDispatchWorkerError("KUBERNETES_TASK_CORRELATION_CONFLICT")
        return body

    def patch_status(
        self, command: NativeDispatchCommand, task_name: str, status: dict
    ) -> None:
        self.api.patch_namespaced_custom_object_status(
            group="agentos.io",
            version="v1alpha1",
            namespace=command.scope.namespace,
            plural="tasks",
            name=task_name,
            body={"status": status},
        )


class HttpNativeTransport:
    """Existing `/v1/invoke` seam with the canonical Attempt identity header."""

    def invoke(self, command: NativeDispatchCommand) -> str:
        context = SimpleNamespace(
            definition_ref=SimpleNamespace(
                name=command.agent_name, namespace=command.scope.namespace
            ),
            execution_identity=command.attempt_id,
        )
        return invoke_compatible_agent(
            context=context,
            prompt=command.input_text,
            timeout_seconds=float(command.timeout_seconds),
        )


class ManagedSkillNativeTransport:
    supports_prepared_execution = True

    def __init__(self, caller):
        self.caller = caller
        self.legacy = HttpNativeTransport()

    def resume_wait(self, command):
        return self.caller.resume_wait(command)

    def invoke(self, command):
        if not command.authorization_resource.startswith(
            "governed-execution:prepared:"
        ):
            return self.legacy.invoke(command)
        try:
            from agent_console.native_wait_types import SkillJobWaiting

            result = self.caller.invoke(command)
            if isinstance(result, SkillJobWaiting):
                return result
            state, output = result
        except Exception as exc:
            from agent_console.execution_preparation import ExecutionPreparationError

            if (
                isinstance(exc, ExecutionPreparationError)
                and str(exc) == "PREPARED_CANCEL_REQUESTED_BEFORE_SKILL"
            ):
                raise TaskExecutionError(
                    "PreparedCancellationStopped",
                    "取消请求已核验; 尚未调用 Skill",
                    False,
                ) from exc
            # No inferred stop after an incomplete owner transaction/readback.
            raise TaskExecutionError(
                "ExecutionOutcomeUnknown", "受管执行结果待核验", False
            ) from exc
        if state == "SUCCEEDED":
            return output
        if state == "FAILED":
            raise TaskExecutionError("ManagedSkillFailed", "受管 Skill 执行失败", False)
        raise TaskExecutionError("ExecutionOutcomeUnknown", "受管执行结果待核验", False)


class NativeDispatchWorker:
    def __init__(
        self,
        repository: DispatchRepository,
        kubernetes: KubernetesTaskPort,
        transport: NativeTransport,
        authorization_check: Callable[[object, NativeDispatchCommand], bool],
        completion: Callable[[NativeDispatchClaim, NativeTerminalObservation], None],
        *,
        worker_id: str,
        task_prefix: str = "native-dispatch",
        checkpoint: Callable[[str], None] = lambda _name: None,
        prepare_ready: Callable[[], None] | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-z0-9](?:[-a-z0-9]{0,28}[a-z0-9])?", task_prefix):
            raise NativeDispatchWorkerError("NATIVE_DISPATCH_TASK_PREFIX_INVALID")
        self.repository = repository
        self.kubernetes = kubernetes
        self.transport = transport
        self.authorization_check = authorization_check
        self.completion = completion
        self.worker_id = worker_id
        self.task_prefix = task_prefix
        self.checkpoint = checkpoint
        self.prepare_ready = prepare_ready
        self.startup_observation = None

    def task_name(self, command: NativeDispatchCommand) -> str:
        suffix = hashlib.sha256(str(command.command_id).encode()).hexdigest()[:32]
        return f"{self.task_prefix}-{suffix}"

    def run_once(self) -> DispatchRunResult:
        claim = self.repository.resume_effect_started(self.worker_id)
        if claim is None:
            if self.prepare_ready is not None:
                self.prepare_ready()
            options = (
                {}
                if self.startup_observation is None
                else {"startup_observation": self.startup_observation.current()}
            )
            claim = self.repository.claim_next(self.worker_id, **options)
        if claim is None:
            return DispatchRunResult("IDLE", None)
        self.checkpoint("claimed")
        return self.run_claim(claim)

    def run_claim(self, claim: NativeDispatchClaim) -> DispatchRunResult:
        command = claim.command
        if command.authorization_resource.startswith(
            "governed-execution:prepared:"
        ) and not getattr(self.transport, "supports_prepared_execution", False):
            raise NativeDispatchWorkerError("PREPARED_MANAGED_SKILL_TRANSPORT_REQUIRED")
        stop = getattr(self.repository, "stop_prepared_before_effect", None)
        if stop is not None and stop(claim):
            return DispatchRunResult("CANCELLED", str(command.command_id))
        task_name = self.task_name(command)
        options = (
            {}
            if self.startup_observation is None
            else {"startup_observation": self.startup_observation.current()}
        )
        permission = self.repository.permit_effect(
            claim, task_name, self.authorization_check, **options
        )
        self.checkpoint("effect_started")
        if permission is AppendDisposition.REPLAYED:
            if self.startup_observation is not None:
                self.startup_observation.observe_only_receipt(claim)
            observed = self.kubernetes.read(claim, task_name)
            if observed and observed.get("status", {}).get("phase") == "Running":
                resume = getattr(self.transport, "resume_wait", None)
                if resume is not None:
                    from agent_console.native_wait_runtime import HOST_CLAIM

                    token = HOST_CLAIM.set((claim, options.get("startup_observation")))
                    try:
                        continued = resume(command)
                    except Exception:
                        # A positive-wait read/current admission failure is not
                        # proof of execution failure and never invokes legacy retry.
                        return DispatchRunResult(
                            "WAIT_OBSERVATION_UNAVAILABLE", str(command.command_id)
                        )
                    finally:
                        HOST_CLAIM.reset(token)
                    if continued is not None:
                        from agent_console.native_wait_types import SkillJobWaiting

                        if isinstance(continued, SkillJobWaiting):
                            return DispatchRunResult(
                                "DRAIN_FOR_INPUT", str(command.command_id)
                            )
                        state, output = continued
                        if state not in {"SUCCEEDED", "FAILED"}:
                            return DispatchRunResult(
                                "WAIT_OBSERVATION_UNAVAILABLE", str(command.command_id)
                            )
                        status = {
                            "phase": "Succeeded" if state == "SUCCEEDED" else "Failed",
                            "attempts": 1,
                            "completedAt": datetime.now(UTC).isoformat(),
                        }
                        if state == "SUCCEEDED":
                            status["result"] = output
                        else:
                            # Only the existing Skill owner's persisted FAILED
                            # result is terminal. UNKNOWN/read errors stay above.
                            status.update(
                                reason="InternalError",
                                message=(
                                    "[ManagedSkillFailed] "
                                    "Original Skill continuation failed"
                                ),
                                retryable=False,
                            )
                        self.kubernetes.patch_status(command, task_name, status)
                        observed = self.kubernetes.read(claim, task_name)
            observation = self._terminal_observation(command, task_name, observed)
            return self._finish(claim, observation)
        task = self.kubernetes.create(claim, task_name)
        uid = task.get("metadata", {}).get("uid")
        if not isinstance(uid, str) or not uid:
            return self._uncertain(
                claim,
                task_name,
                None,
                NativeTerminalKind.RECOVERY_REQUIRED,
                "KUBERNETES_TASK_UID_MISSING",
            )
        self.repository.record_kubernetes_correlation(claim, task_name, uid)
        self.kubernetes.patch_status(
            command,
            task_name,
            {
                "phase": "Running",
                "startedAt": datetime.now(UTC).isoformat(),
                "attempts": 1,
            },
        )
        try:
            from agent_console.native_wait_runtime import HOST_CLAIM

            token = HOST_CLAIM.set((claim, options.get("startup_observation")))
            try:
                output = self.transport.invoke(command)
            finally:
                HOST_CLAIM.reset(token)
        except TaskExecutionError as exc:
            if exc.reason in {"ExecutionOutcomeUnknown", "ExecutionTimeout"}:
                return self._uncertain(
                    claim,
                    task_name,
                    uid,
                    NativeTerminalKind.UNKNOWN,
                    exc.reason,
                )
            # The frozen Task CRD accepts a bounded reason enum. Preserve the
            # managed owner classification in diagnostics, not an invalid enum
            # value that would leave the Task stuck Running after a failed PATCH.
            managed_failure = exc.reason in {
                "ManagedSkillFailed",
                "PreparedCancellationStopped",
            }
            status = {
                "phase": "Failed",
                "reason": "InternalError" if managed_failure else exc.reason,
                "message": f"[{exc.reason}] {exc.message}"
                if managed_failure
                else exc.message,
                "retryable": False,
                "attempts": 1,
                "completedAt": datetime.now(UTC).isoformat(),
            }
            self.kubernetes.patch_status(command, task_name, status)
        else:
            from agent_console.native_wait_types import SkillJobWaiting

            if isinstance(output, SkillJobWaiting):
                if (
                    output.identity.command_id != str(command.command_id)
                    or output.identity.attempt_id != str(command.attempt_id)
                    or output.identity.principal_id != command.principal_id
                    or output.identity.namespace != command.scope.namespace
                    or output.identity.security_domain != command.scope.security_domain
                ):
                    raise NativeDispatchWorkerError(
                        "NATIVE_WAIT_COMMAND_BINDING_INVALID"
                    )
                return DispatchRunResult("DRAIN_FOR_INPUT", str(command.command_id))
            status = {
                "phase": "Succeeded",
                "result": output,
                "attempts": 1,
                "completedAt": datetime.now(UTC).isoformat(),
            }
            self.kubernetes.patch_status(command, task_name, status)
        observed = self.kubernetes.read(claim, task_name)
        observation = self._terminal_observation(command, task_name, observed)
        return self._finish(claim, observation)

    def _finish(self, claim, observation):
        self.checkpoint("terminal_observed")
        if observation.kind in {
            NativeTerminalKind.UNKNOWN,
            NativeTerminalKind.RECOVERY_REQUIRED,
        }:
            self.repository.record_uncertain(claim, observation)
        else:
            self.completion(claim, observation)
        return DispatchRunResult(observation.kind.value, str(claim.command.command_id))

    def _uncertain(self, claim, task_name, uid, kind, reason):
        observation = NativeTerminalObservation(
            claim.command.command_id,
            kind,
            task_name,
            uid,
            None,
            reason,
            datetime.now(UTC),
        )
        self.repository.record_uncertain(claim, observation)
        return DispatchRunResult(kind.value, str(claim.command.command_id))

    @staticmethod
    def _terminal_observation(command, task_name, body):
        if body is None:
            return NativeTerminalObservation(
                command.command_id,
                NativeTerminalKind.RECOVERY_REQUIRED,
                task_name,
                None,
                None,
                "KUBERNETES_TASK_MISSING",
                datetime.now(UTC),
            )
        metadata = body.get("metadata", {})
        status = body.get("status", {})
        uid = metadata.get("uid")
        phase = status.get("phase")
        if phase == "Succeeded" and isinstance(status.get("result"), str):
            return NativeTerminalObservation(
                command.command_id,
                NativeTerminalKind.SUCCEEDED,
                task_name,
                uid,
                status["result"],
                None,
                datetime.now(UTC),
            )
        if phase in {"Failed", "TimedOut"}:
            return NativeTerminalObservation(
                command.command_id,
                NativeTerminalKind.FAILED,
                task_name,
                uid,
                None,
                status.get("reason") or "RUNTIME_FAILED",
                datetime.now(UTC),
            )
        return NativeTerminalObservation(
            command.command_id,
            NativeTerminalKind.UNKNOWN,
            task_name,
            uid,
            None,
            "TERMINAL_OBSERVATION_UNAVAILABLE",
            datetime.now(UTC),
        )


def build_native_dispatch_from_environment() -> NativeDispatchAssembly | None:
    """Compose the worker only from explicit, externally supplied authority state."""
    database_url = os.environ.get("NATIVE_DISPATCH_DATABASE_URL", "")
    if not database_url:
        return None
    authority_configuration_path = os.environ.get(
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION", ""
    )
    execution_migration = os.environ.get("NATIVE_DISPATCH_EXECUTION_MIGRATION", "")
    dispatch_migration = os.environ.get("NATIVE_DISPATCH_SCHEMA_MIGRATION", "")
    worker_id = os.environ.get("NATIVE_DISPATCH_WORKER_ID", "")
    task_prefix = os.environ.get("NATIVE_DISPATCH_TASK_PREFIX", "native-dispatch")
    if not all(
        (
            authority_configuration_path,
            execution_migration,
            dispatch_migration,
            worker_id,
        )
    ):
        raise NativeDispatchWorkerError("NATIVE_DISPATCH_CONFIGURATION_INCOMPLETE")

    from agent_console.authority_configuration import (
        AuthorityRuntimeConfiguration,
        StaticAuthorityLoader,
    )
    from agent_console.authority_contracts import (
        AuthenticationSource,
        AuthorityScope,
        TrustedRequestContext,
    )
    from agent_console.authority_postgres import PostgresAuthorityRepository
    from agent_console.authority_recovery import HostRecoveryControl
    from agent_console.execution_application import (
        ExecutionCompletionService,
        ExecutionEvidenceRecord,
        PostgresExecutionCompletionWriter,
        RecordNativeCompletionCommand,
    )
    from agent_console.execution_postgres import (
        PostgresExecutionAuthorityRepository,
    )
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )

    try:
        configuration = AuthorityRuntimeConfiguration.from_mapping(
            json.loads(Path(authority_configuration_path).read_text())
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise NativeDispatchWorkerError(
            "NATIVE_DISPATCH_CONFIGURATION_INVALID"
        ) from exc
    if configuration.database_url != database_url:
        raise NativeDispatchWorkerError("NATIVE_DISPATCH_DATABASE_IDENTITY_MISMATCH")
    generation = StaticAuthorityLoader.load(
        configuration.generation_path,
        expected_digest=configuration.generation_digest,
    )
    authority = PostgresAuthorityRepository(
        database_url, migration_path=configuration.migration_path
    )
    execution = PostgresExecutionAuthorityRepository(
        database_url, migration_path=Path(execution_migration)
    )
    prepared_composition = None
    try:
        authority.migrate()
        active = authority.active_generation()
        if active is None or active[:2] != (generation.generation, generation.digest):
            raise NativeDispatchWorkerError("NATIVE_DISPATCH_AUTHORITY_NOT_ACTIVE")
        recovery_epoch = active[2]
        control = HostRecoveryControl(configuration.recovery_control_path)
        control.require_ready(
            database_fingerprint=configuration.database_fingerprint,
            generation=generation.generation,
            generation_digest=generation.digest,
            recovery_epoch=recovery_epoch,
        )
        reader = GenerationAuthorizationReader(
            generation, authority, authority, recovery_epoch=recovery_epoch
        )
        execution.compatibility()
        execution.native_dispatch_compatibility(Path(dispatch_migration))

        continuation_work = None

        def authorization_check(connection, command):
            return authorization_bundle_check(connection, command, ())

        def authorization_bundle_check(connection, command, additional_grants):
            control.require_ready(
                database_fingerprint=configuration.database_fingerprint,
                generation=generation.generation,
                generation_digest=generation.digest,
                recovery_epoch=recovery_epoch,
            )
            context = TrustedRequestContext(
                command.principal_id,
                AuthorityScope(command.scope.namespace, command.scope.security_domain),
                command.credential_id,
                AuthenticationSource(command.authentication_source),
                generation.policy_version,
            )
            from agent_console.owned_business_resource_adapter import authorize_dispatch

            if not authorize_dispatch(
                continuation_work.owned_business if continuation_work else None,
                connection,
                command,
                context,
            ):
                return False
            from agent_console.prepared_execution_lineage import dispatch_grants

            grants = tuple(
                dict.fromkeys(
                    (*dispatch_grants(connection, command), *additional_grants)
                )
            )
            return all(
                reader.has_current_grants(
                    context,
                    grants,
                    now=datetime.now(UTC),
                    generation=command.authority_generation.value,
                    recovery_epoch=command.recovery_epoch.value,
                    connection=connection,
                    configure_transaction=False,
                )
            )

        completion_service = ExecutionCompletionService(
            execution, PostgresExecutionCompletionWriter(execution)
        )

        def complete(claim, observation):
            command = claim.command
            identity = execution.get_attempt(command.scope, command.attempt_id)
            if identity is None:
                raise NativeDispatchWorkerError("NATIVE_DISPATCH_ATTEMPT_NOT_FOUND")
            with execution.pool.connection() as connection:
                attempt_row = connection.execute(
                    "SELECT attempt_ordinal FROM execution_authority.attempts "
                    "WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
                    (
                        command.scope.namespace,
                        command.scope.security_domain,
                        str(command.attempt_id),
                    ),
                ).fetchone()
            if attempt_row is None:
                raise NativeDispatchWorkerError("NATIVE_DISPATCH_ATTEMPT_NOT_FOUND")
            suffix = hashlib.sha256(
                f"{command.command_id}\0{observation.digest}".encode()
            ).hexdigest()
            evidence_id = f"native-evidence-{suffix}"
            outcome_id = f"native-outcome-{suffix}"
            evidence = ExecutionEvidenceRecord.from_allowlisted(
                {
                    "evidence_record_id": evidence_id,
                    "namespace": command.scope.namespace,
                    "security_domain": command.scope.security_domain,
                    "platform_execution_identity": str(command.attempt_id),
                    "workflow_identity": str(identity.workflow_run.workflow_run_id),
                    "task_identity": str(identity.task_run.task_run_id),
                    "attempt_ordinal": attempt_row["attempt_ordinal"],
                    "event_ordinal": 1,
                    "event_type": "EXECUTION_OUTCOME",
                    "occurred_at": observation.observed_at.isoformat(),
                    "runtime_classification": "NATIVE",
                    "selected_instance_identity": str(command.runtime_instance_id),
                    "capability_identity": None,
                    "authorization_decision": "ALLOW",
                    "reason_code": f"NATIVE_EXECUTION_{observation.kind.value}",
                    "provider_correlation_id": observation.kubernetes_task_uid,
                    "provider_call_count": 1,
                    "outcome_classification": observation.kind.value,
                    "outcome_reference": outcome_id,
                    "references": [],
                    "limitation_code": "MODEL_INVOCATION_NOT_PROVEN",
                    "supersedes_record_id": None,
                    "schema_version": 1,
                }
            )
            outcome = {
                "outcome_id": outcome_id,
                "workflow_run_id": str(identity.workflow_run.workflow_run_id),
                "task_run_id": str(identity.task_run.task_run_id),
                "attempt_id": str(command.attempt_id),
                "approved_plan_revision_id": command.approved_plan_revision_id,
                "evidence_ids": [evidence_id],
                "classification": observation.kind.value,
                "technical": True,
                "business_problem_resolved": False,
            }
            completion_service.record_native(
                RecordNativeCompletionCommand(
                    claim, observation, (evidence,), outcome_id, outcome
                )
            )

        transport = HttpNativeTransport()
        ready_driver = None
        prepared_mode = os.environ.get("NATIVE_DISPATCH_PREPARED_SKILL", "")
        if prepared_mode:
            if prepared_mode not in {
                "synthetic-cost-v1",
                "synthetic-delivery-v1",
                "sales-diagnostic-v1",
                "sales-gross-profit-v2-candidate",
                "registered-readonly-v1",
            }:
                raise NativeDispatchWorkerError("PREPARED_SKILL_CONFIGURATION_INVALID")
            from agent_console.prepared_native_composition import compose

            caller, prepared_composition = compose(
                execution.pool,
                database_url,
                Path(execution_migration).parent,
                reader,
                generation,
                authorization_check,
                mode=prepared_mode,
                native_loop_path=os.getenv("NATIVE_LOOP_RUNTIME_FILE"),
                durable_wait_path=os.getenv("NATIVE_DURABLE_WAIT_CONFIGURATION"),
                authorization_bundle_check=authorization_bundle_check,
            )
            transport = ManagedSkillNativeTransport(caller)
            from agent_console.prepared_native_composition import (
                owner_authority_factory,
            )
            from agent_console.prepared_native_coordinator import PreparedReadyDriver

            ready_driver = PreparedReadyDriver(
                execution,
                owner_authority_factory(reader, generation, authorization_check),
            )
        after_tick = None
        dispatch_repository = execution
        continuation_path = os.environ.get("NATIVE_DISPATCH_CONTINUATION_POLICY")
        if continuation_path:
            if ready_driver is None:
                raise NativeDispatchWorkerError("CONTINUATION_MANAGED_SKILL_REQUIRED")
            from agent_console.readonly_continuation_worker import (
                ContinuationDispatchRepository,
                ContinuationWork,
            )

            owned_business = None
            business_policy_path = os.environ.get("OWNED_BUSINESS_ADMISSION_POLICY")
            if business_policy_path:
                from agent_console.owned_business_retained_history import (
                    configured_paths,
                )
                from agent_console.owned_business_work_reader import (
                    OwnedBusinessWorkReader,
                )

                candidate = OwnedBusinessWorkReader(
                    business_policy_path,
                    reader,
                    generation.generation,
                    recovery_epoch,
                    retained_history_paths=configured_paths(
                        os.environ.get("OWNED_BUSINESS_RETAINED_HISTORY_POLICIES")
                    ),
                )
                if candidate.policy.enabled:
                    owned_business = candidate
            work = ContinuationWork.load(
                execution,
                continuation_path,
                owner_authority_factory(reader, generation, authorization_check),
                sales_v2_candidate=prepared_mode == "sales-gross-profit-v2-candidate",
                **({"owned_business": owned_business} if owned_business else {}),
            )
            continuation_work = work
            if prepared_composition is not None:
                for runtime in prepared_composition.closeables:
                    if getattr(runtime, "durable_wait", None) is not None:
                        if owned_business is None:
                            raise NativeDispatchWorkerError(
                                "NATIVE_WAIT_OWNED_BUSINESS_REQUIRED"
                            )
                        runtime.owned_business = owned_business
                        from agent_console.native_wait_command_access import (
                            NativeWaitCommandAccess,
                        )

                        caller.wait_access = NativeWaitCommandAccess(
                            runtime, execution, work
                        )
            dispatch_repository = ContinuationDispatchRepository(execution, work)
            ready_driver.eligible_dispatches = work.dispatches
            after_tick = work.evaluate_terminal
        worker = NativeDispatchWorker(
            dispatch_repository,
            KubernetesNativeTaskPort(),
            transport,
            authorization_check,
            complete,
            worker_id=worker_id,
            task_prefix=task_prefix,
            prepare_ready=ready_driver.tick if ready_driver else None,
        )
        return NativeDispatchAssembly(
            worker, execution, authority, prepared_composition, after_tick
        )
    except Exception:
        execution.pool.close()
        authority.close()
        if prepared_composition is not None:
            prepared_composition.close()
        raise
