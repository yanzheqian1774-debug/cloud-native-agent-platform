# ruff: noqa: RUF001 -- Business criteria in Chinese.
"""Explicit Native model composition; existing authority and budget owners reused."""

import json
import time
from contextvars import ContextVar
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from agent_runtime.native_loop import Limits, NativeLoop, digest

from .authority_contracts import (
    AuthenticationSource,
    AuthorityScope,
    TrustedRequestContext,
)
from .development_administrator import PRINCIPAL, SCOPE, authorized
from .model_binding_resolution import (
    AuthorizedModelUse,
    ModelConsumptionScope,
    ModelUseSubject,
    resolve_authorized_model_binding,
)
from .model_governance_authorization import invoke_model_use
from .native_diagnostic_tools import NativeDiagnosticTools
from .native_loop_journal import NativeLoopJournal
from .native_loop_provider import NativeDecisionJob
from .ontology_execution import parse_preparation
from .plan_suggestion_runtime import build_planning_runtime
from .planning_measurement import settle
from .prepared_execution_lineage import prepared_attempt
from .responses_deadline import supervise

COMMAND = ContextVar("native_loop_command", default=None)


class NativeLoopRuntime:
    def __init__(
        self,
        path,
        pool,
        database_url,
        migrations,
        reader,
        generation,
        authorize,
        *,
        authorize_current=None,
    ):
        self.authorize_current = authorize_current
        self.config = json.loads(Path(path).read_text())
        if (
            self.config.get("purpose") != "NATIVE_TASK_DECISION_V1"
            or self.config.get("subject") != PRINCIPAL
            or self.config.get("maximumDecisions") != 8
        ):
            raise ValueError("NATIVE_LOOP_CONFIGURATION_INVALID")
        self.expiry = datetime.fromisoformat(self.config["expiresAt"])
        if self.expiry.tzinfo is None or self.expiry <= datetime.now(UTC):
            raise ValueError("NATIVE_LOOP_CONFIGURATION_EXPIRED")
        runtime_path = Path(self.config["modelRuntimeFile"])
        if (
            not runtime_path.is_absolute()
            or sha256(runtime_path.read_bytes()).hexdigest()
            != self.config["modelRuntimeDigest"]
        ):
            raise ValueError("NATIVE_LOOP_MODEL_CONFIGURATION_MISMATCH")
        self.policy_digest = digest(self.config)
        self.pool, self.reader, self.generation, self.authorize_skill = (
            pool,
            reader,
            generation,
            authorize,
        )
        self.model = build_planning_runtime(
            database_url=database_url,
            runtime_configuration_path=self.config["modelRuntimeFile"],
            migrations_path=migrations,
        )
        # This reuses transport/binding/budget construction, NOT the planning
        # invocation service. All invocations below are NATIVE_TASK_DECISION.
        self.dependencies = self.model.dependencies
        if not self.dependencies.profile.real_calls_enabled:
            raise ValueError("NATIVE_LOOP_REAL_CALLS_DISABLED")
        if (
            self.model.budget.call_cap > 24
            or self.model.budget.total_cost_cap_microusd > 2_000_000
            or self.model.budget.ledger_id != self.config["ledgerId"]
        ):
            raise ValueError("NATIVE_LOOP_LEDGER_MISMATCH")
        migration = migrations / "0050_native_loop.sql"
        checksum = sha256(migration.read_bytes()).hexdigest()
        with pool.connection() as c, c.transaction():
            c.execute("SELECT pg_advisory_xact_lock(3240050)")
            prior = c.execute(
                "SELECT checksum,adapter FROM skill_invocation.schema_migrations "
                "WHERE version=50"
            ).fetchone()
            expected = {"checksum": checksum, "adapter": "native-loop-owner-v1"}
            if prior is not None and prior != expected:
                raise ValueError("NATIVE_LOOP_STORAGE_INCOMPATIBLE")
            c.execute(migration.read_text())
            if prior is None:
                c.execute(
                    "INSERT INTO skill_invocation.schema_migrations "
                    "(version,checksum,adapter) "
                    "VALUES(50,%s,%s)",
                    (checksum, expected["adapter"]),
                )

    def close(self):
        self.model.close()

    def run(self, invocation_id, output, timeout_ms):
        command = COMMAND.get()
        if command is None:
            raise ValueError("NATIVE_LOOP_OWNER_COMMAND_REQUIRED")
        scope = command.scope
        context = TrustedRequestContext(
            command.principal_id,
            AuthorityScope(scope.namespace, scope.security_domain),
            command.credential_id,
            AuthenticationSource(command.authentication_source),
            self.generation.policy_version,
        )
        profile = self.dependencies.provider.transport_profile
        model_scope = ModelConsumptionScope(scope.namespace, scope.security_domain)
        subject = ModelUseSubject(command.principal_id)
        with self.pool.connection() as c:
            row = prepared_attempt(c, scope, command.attempt_id)
            p = parse_preparation(row["preparation"])
            problem = c.execute(
                "SELECT title,description,digest FROM "
                "business_problem_authority.problem_revisions WHERE namespace=%s AND "
                "security_domain=%s AND revision_id=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    p.semantics.target.problem.revision_id,
                ),
            ).fetchone()
            if not problem or problem["digest"] != p.semantics.target.problem.digest:
                raise ValueError("NATIVE_LOOP_GOAL_LINEAGE_MISMATCH")
            invocation = c.execute(
                "SELECT attempt_id,executor_id,executor_revision FROM sk"
                "ill_invocation.invocations "
                "WHERE namespace=%s AND security_domain=%s AND skill_invocation_id=%s",
                (scope.namespace, scope.security_domain, invocation_id),
            ).fetchone()
            if (
                not invocation
                or invocation["attempt_id"] != str(command.attempt_id)
                or (invocation["executor_id"], invocation["executor_revision"])
                not in {
                    ("tabular-diagnostic-readonly", "2"),
                    ("tabular-diagnostic-readonly", "3"),
                    ("native-document-review", "1"),
                }
            ):
                raise ValueError("NATIVE_LOOP_INVOCATION_REQUIRED")
        journal = NativeLoopJournal(self.pool, scope, invocation_id)
        document_mode = output["schemaVersion"] == "document-review-output.v1"
        from .native_document_tools import NativeDocumentTools

        library = (NativeDocumentTools if document_mode else NativeDiagnosticTools)(
            output["source"], output["sourceSnapshot"]
        )
        manager = self

        authority_timing = {"checks": 0, "seconds": 0.0}

        def current():
            before = time.monotonic()
            authority_timing["checks"] += 1
            try:
                return current_authority()
            finally:
                authority_timing["seconds"] += time.monotonic() - before

        def current_authority():
            if (
                datetime.now(UTC) >= manager.expiry
                or (scope.namespace, scope.security_domain) != SCOPE
            ):
                return False
            with manager.pool.connection() as c:
                if manager.authorize_current is not None:
                    if not manager.authorize_current(c, command):
                        return False
                else:
                    manager.authorize_skill(c, command)
                    if not authorized(
                        manager.reader,
                        context,
                        generation=command.authority_generation.value,
                        recovery_epoch=command.recovery_epoch.value,
                        connection=c,
                    ):
                        return False
                progress = c.execute(
                    "SELECT record FROM execution_authority.prepared_run_progress "
                    "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                    (scope.namespace, scope.security_domain, p.run_id),
                ).fetchone()
                return bool(
                    progress and not progress["record"].get("cancellation_request_id")
                )

        class Cancellation:
            def is_set(self):
                try:
                    return not current()
                except Exception:
                    return True

        class Ports:
            def authorize(self, kind, request):
                return current()

            def authorize_use(self, requested_scope, requested_subject, use):
                if (
                    requested_scope != model_scope
                    or requested_subject != subject
                    or not current()
                ):
                    return None
                now = datetime.now(UTC)
                return AuthorizedModelUse(
                    "native-model-admission:"
                    + digest(
                        [manager.policy_digest, invocation_id, use.exact_resource]
                    ),
                    subject,
                    model_scope,
                    use,
                    command.authority_generation.value,
                    "D15:" + manager.policy_digest,
                    now,
                    min(manager.expiry, now + timedelta(minutes=5)),
                )

            def decide(self, assembled, *, key, remaining_seconds):
                dependency = manager.dependencies
                use = invoke_model_use(
                    attempt_id=str(command.attempt_id),
                    binding_snapshot_id=digest([p.digest, manager.policy_digest, key]),
                    binding=profile.binding,
                )
                resolve_authorized_model_binding(
                    scope=model_scope,
                    subject=subject,
                    use=use,
                    authorizer=self,
                    resolver=dependency.model_resolver,
                    evaluation_time=lambda: datetime.now(UTC),
                )
                identity = SimpleNamespace(
                    scope=scope,
                    invocation_id=key,
                    profile_revision_id=profile.profile_revision_id,
                )
                config = dependency.provider.configuration
                if remaining_seconds < config.total_timeout_seconds + 2:
                    raise ValueError("NATIVE_LOOP_DECISION_DEADLINE")
                reservation = dependency.budget.reserve(
                    key + ":budget", identity, dependency.quote
                )
                receipt_key = key + ":receipt"
                input_digest = digest(assembled)
                if journal.claim(receipt_key, input_digest) is not None:
                    raise ValueError("NATIVE_LOOP_MODEL_ALREADY_CLAIMED")
                if not current():
                    raise ValueError("NATIVE_LOOP_AUTHORITY_REVOKED")
                with dependency.budget.dispatch_guard(identity, dependency.quote):
                    result, deadline = supervise(
                        NativeDecisionJob(config, profile, key, assembled),
                        config,
                        cancel=Cancellation(),
                    )
                receipt = {
                    "contextKind": "NATIVE_TASK_DECISION",
                    "taskId": row["task_id"],
                    "attemptId": str(command.attempt_id),
                    "workflowRunId": p.run_id,
                    "principal": command.principal_id,
                    "model": asdict(profile.binding),
                    "authorizationResource": use.exact_resource,
                    "authorizationDecisionId": "native-model-admission:"
                    + digest(
                        [manager.policy_digest, invocation_id, use.exact_resource]
                    ),
                    "authorityGeneration": command.authority_generation.value,
                    "recoveryEpoch": command.recovery_epoch.value,
                    "sourceSnapshot": output["sourceSnapshot"],
                    "policyDigest": manager.policy_digest,
                    "inputDigest": input_digest,
                    "measurement": result.get("measurement", {}),
                    "deadline": deadline,
                    "reservation_id": reservation,
                    "ledgerId": manager.model.budget.ledger_id,
                    "pricing": dependency.budget.pricing(),
                }
                # Persist provider receipt before accounting; a crash retains the
                # reservation and never invokes the provider to recover metering.
                journal.finish(receipt_key, input_digest, receipt)
                settlement = settle(dependency.budget, key, receipt)
                settlement_key = key + ":settlement"
                journal.claim(settlement_key, input_digest)
                journal.finish(settlement_key, input_digest, settlement)
                if result.get("failure") or not receipt["measurement"].get(
                    "settleable"
                ):
                    raise ValueError("NATIVE_LOOP_MODEL_OR_METERING_UNCONFIRMED")
                return result["decision"]

            def invoke(self, tool, arguments, **kwargs):
                if not current():
                    raise ValueError("NATIVE_LOOP_AUTHORITY_REVOKED")
                return library.invoke(tool.name, arguments)

            def verify(self, assembled, answer):
                return library.verify(assembled, answer)

        ports = Ports()
        if document_mode:
            from .native_interaction import await_answer

            def clarify(question, *, key, remaining_seconds):
                reply = await_answer(
                    journal,
                    question,
                    key=key,
                    remaining_seconds=remaining_seconds,
                    current=current,
                    principal=command.principal_id,
                    run_id=p.run_id,
                    policy_expiry=self.expiry,
                )
                library.record_answer(reply["answer"])
                return reply

            ports.clarify = clarify
        loop = NativeLoop(
            library.tools,
            ports,
            journal,
            limits=Limits(
                maximum_decisions=8,
                total_seconds=min(timeout_ms / 1000, command.timeout_seconds, 600),
            ),
            cancelled=Cancellation().is_set,
        )
        result = loop.run(
            invocation_id,
            problem["title"] + "\n" + problem["description"],
            [
                "根据用户确认的范围选择文档规范，逐节核对完整性，引用准确原文；不"
                "代替上线批准。"
                if document_mode
                else (
                    "核对声明上限，检查异常和缺失的原始行，返回可独立复算的报告；不证"
                    "明因果或业务改善。"
                )
            ],
            {
                **(
                    {
                        "domain": "DOCUMENT_REVIEW",
                        "answerSchema": library.answer_schema,
                        "documentInventory": library.inventory(),
                    }
                    if document_mode
                    else {}
                ),
                "sourceSnapshot": output["sourceSnapshot"],
                "model": asdict(profile.binding),
                "policyDigest": self.policy_digest,
                "taskId": row["task_id"],
                "attemptId": str(command.attempt_id),
                "workflowRunId": p.run_id,
            },
        )
        return {
            **result,
            "performance": {
                "authority": authority_timing,
                "note": "Includes supervisor cancellation checks; nested, not additive",
            },
            "modelExecution": "REAL_PROVIDER",
            "model": asdict(profile.binding),
            "ledgerId": self.model.budget.ledger_id,
            "policyDigest": self.policy_digest,
            "invocationId": invocation_id,
        }
