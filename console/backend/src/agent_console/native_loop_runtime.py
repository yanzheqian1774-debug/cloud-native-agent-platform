# ruff: noqa: RUF001 -- Business criteria in Chinese.
"""Explicit Native model composition; existing authority and budget owners reused."""

import json
import time
from contextlib import nullcontext
from contextvars import ContextVar
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from agent_runtime.native_loop import Limits, NativeLoop, digest

from .authority_contracts import (
    AuthenticationSource,
    AuthorityError,
    AuthorityScope,
    ExactGrant,
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
from .native_confirmed_scope import read_confirmed_scope
from .native_diagnostic_tools import NativeDiagnosticTools
from .native_document_skill import (
    NativeDefinitionQuerySkillExecutor,
    NativeDurableDocumentSkillExecutor,
    NativeEmployeeDocumentSkillExecutor,
    NativeRuleDocumentSkillExecutor,
    NativeUserScopeDocumentSkillExecutor,
)
from .native_employee_context import read_bound_employee_context
from .native_loop_journal import NativeLoopJournal
from .native_loop_provider import NativeDecisionJob
from .native_loop_subject import (
    configured_service_credential,
    configured_subject,
    require_original_subject,
)
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
        durable_wait_path=None,
        skill_repository=None,
        environment=None,
    ):
        self.authorize_current = authorize_current
        self.config = json.loads(Path(path).read_text())
        from .native_data_adapters import configured

        self.native_data_adapters = configured(self.config)
        self.subject = configured_subject(self.config)
        self.service_credential_id = configured_service_credential(self.config)
        if self.subject != PRINCIPAL and authorize_current is None:
            raise ValueError("NATIVE_LOOP_EXACT_AUTHORITY_REQUIRED")
        if (
            self.config.get("purpose") != "NATIVE_TASK_DECISION_V1"
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
        self.skill_repository, self.owned_business = skill_repository, None
        self.bound_service_execution = None
        self.durable_wait = None
        if durable_wait_path:
            from .native_wait_configuration import DurableWaitConfiguration

            if skill_repository is None:
                raise ValueError("NATIVE_WAIT_SKILL_OWNER_REQUIRED")
            self.durable_wait = DurableWaitConfiguration.load(
                durable_wait_path, self.policy_digest
            )
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
            **({"environment": environment} if environment is not None else {}),
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

        if self.durable_wait is not None:
            from .native_wait_store import NativeWaitStore

            with pool.connection() as c, c.transaction():
                NativeWaitStore.migrate(c)

    def close(self):
        self.model.close()

    def run(self, invocation_id, output, timeout_ms):
        command = COMMAND.get()
        if command is None:
            raise ValueError("NATIVE_LOOP_OWNER_COMMAND_REQUIRED")
        require_original_subject(
            self.subject,
            command,
            service_credential_id=getattr(self, "service_credential_id", None),
        )
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
                "SELECT attempt_id,executor_id,executor_revision,"
                "executor_configuration_digest FROM skill_invocation.invocations "
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
                    ("native-document-review", "2"),
                    ("native-document-review", "3"),
                    ("native-document-review", "4"),
                    ("native-document-review", "5"),
                    ("native-document-review", "6"),
                    ("native-document-review", "7"),
                }
                | {(adapter.adapter_id, "1") for adapter in self.native_data_adapters}
            ):
                raise ValueError("NATIVE_LOOP_INVOCATION_REQUIRED")
        employee_mode = (
            invocation["executor_id"],
            invocation["executor_revision"],
        ) in {
            ("native-document-review", "2"),
            ("native-document-review", "3"),
            ("native-document-review", "4"),
            ("native-document-review", "5"),
            ("native-document-review", "6"),
            ("native-document-review", "7"),
        }
        rule_mode = employee_mode and invocation["executor_revision"] in {
            "4",
            "5",
            "6",
            "7",
        }
        user_scope_mode = employee_mode and invocation["executor_revision"] in {
            "3",
            "4",
            "5",
            "6",
            "7",
        }
        typed_mode = employee_mode and invocation["executor_revision"] == "7"
        if typed_mode:
            from .native_typed_document_skill import (
                NativeTypedQuestionDocumentSkillExecutor,
            )
        document_revision = (
            NativeTypedQuestionDocumentSkillExecutor
            if typed_mode
            else NativeDurableDocumentSkillExecutor
            if invocation["executor_revision"] == "6"
            else NativeDefinitionQuerySkillExecutor
            if invocation["executor_revision"] == "5"
            else NativeRuleDocumentSkillExecutor
            if rule_mode
            else NativeUserScopeDocumentSkillExecutor
            if user_scope_mode
            else NativeEmployeeDocumentSkillExecutor
        ).revision
        if (
            employee_mode
            and invocation["executor_configuration_digest"]
            != document_revision.configuration_digest
        ):
            raise ValueError("NATIVE_EMPLOYEE_EXECUTOR_MISMATCH")

        def employee_snapshot(connection):
            def require(ref):
                grants = (
                    ExactGrant(
                        "EMPLOYEE",
                        "READ",
                        f"employee:{ref.resource_id}:{ref.revision_id}",
                    ),
                )
                if not all(
                    self.reader.has_current_grants(
                        context,
                        grants,
                        now=datetime.now(UTC),
                        generation=command.authority_generation.value,
                        recovery_epoch=command.recovery_epoch.value,
                        connection=connection,
                        configure_transaction=False,
                    )
                ):
                    raise AuthorityError("AUTHORIZATION_NOT_FOUND")

            return read_bound_employee_context(
                connection,
                p,
                row["task_id"],
                authorize=require,
                executor_revision=document_revision,
            )

        employee_context = None
        if employee_mode:
            with self.pool.connection() as c:
                employee_context = employee_snapshot(c)
        journal = NativeLoopJournal(self.pool, scope, invocation_id)
        document_mode = output["schemaVersion"] == "document-review-output.v1"
        from .native_data_skill import EXECUTOR_IDS
        from .native_document_tools import NativeDocumentTools

        data_mode = invocation["executor_id"] in EXECUTOR_IDS
        if data_mode:
            from .native_data_skill import exact_executor
            from .skill_invocation_domain import ExecutorRevision

            executor = exact_executor(
                ExecutorRevision(
                    invocation["executor_id"],
                    invocation["executor_revision"],
                    invocation["executor_configuration_digest"],
                )
            )
            if (
                executor.adapter not in self.native_data_adapters
                or output.get("schemaVersion") != "native-data-output.v1"
                or output.get("adapter") != executor.adapter.descriptor()
            ):
                raise ValueError("NATIVE_DATA_RUNTIME_BINDING_MISMATCH")
            library = executor.adapter.tools(output["source"], output["sourceSnapshot"])
        else:
            library = (NativeDocumentTools if document_mode else NativeDiagnosticTools)(
                output["source"], output["sourceSnapshot"]
            )

        def rule_snapshot(connection):
            from .ontology_execution import DocumentSemanticsBinding, published_content
            from .ontology_service import resource

            binding = getattr(p, "business_semantics", None)
            if not isinstance(binding, DocumentSemanticsBinding):
                raise ValueError("DOCUMENT_RULE_PREPARATION_V3_REQUIRED")
            grant = ExactGrant(
                "BUSINESS_ONTOLOGY",
                "USE",
                resource(binding.ontology.resource_id, binding.ontology.revision_id),
            )
            if not all(
                self.reader.has_current_grants(
                    context,
                    (grant,),
                    now=datetime.now(UTC),
                    generation=command.authority_generation.value,
                    recovery_epoch=command.recovery_epoch.value,
                    connection=connection,
                    configure_transaction=False,
                )
            ):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return published_content(connection, scope, binding).model_dump(mode="json")

        rule_content = None
        if rule_mode:
            from .native_document_rule_tools import NativeDocumentRuleTools

            with self.pool.connection() as c:
                rule_content = rule_snapshot(c)
            from .native_definition_query_tools import NativeDefinitionQueryTools

            library_type = (
                NativeDefinitionQueryTools
                if invocation["executor_revision"] == "5"
                else NativeDocumentRuleTools
            )
            library = library_type(
                output["source"],
                output["sourceSnapshot"],
                rule_content,
                p.business_semantics.model_dump(mode="json"),
            )

        def scope_snapshot(connection):
            return read_confirmed_scope(
                connection,
                p,
                command.principal_id,
                [
                    d["scope"]
                    for d in library.documents.values()
                    if d["role"] == "POLICY"
                ],
            )

        scope_evidence = None
        if user_scope_mode:
            if not document_mode:
                raise ValueError("NATIVE_DOCUMENT_SCOPE_DOMAIN_MISMATCH")
            with self.pool.connection() as c:
                scope_evidence = scope_snapshot(c)
            library.apply_confirmed_scope(scope_evidence)
        manager = self

        authority_timing = {"checks": 0, "seconds": 0.0}

        def current():
            before = time.monotonic()
            authority_timing["checks"] += 1
            try:
                return current_authority()
            finally:
                authority_timing["seconds"] += time.monotonic() - before

        def current_authority(connection=None):
            if (
                command.principal_id != manager.subject
                or datetime.now(UTC) >= manager.expiry
                or (scope.namespace, scope.security_domain) != SCOPE
            ):
                return False
            with (
                nullcontext(connection)
                if connection is not None
                else manager.pool.connection()
            ) as c:
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
                if employee_mode and employee_snapshot(c) != employee_context:
                    return False
                if rule_mode and rule_snapshot(c) != rule_content:
                    return False
                if user_scope_mode and scope_snapshot(c) != scope_evidence:
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
                    **(
                        {
                            "employeeContextDigest": digest(employee_context),
                            "employeeDefinition": employee_context["reference"],
                        }
                        if employee_mode
                        else {}
                    ),
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
                    **(
                        {
                            "domain": "NATIVE_READONLY_DATA",
                            "nativeDataAdapter": executor.adapter.descriptor(),
                            "answerSchema": library.answer_schema,
                        }
                        if data_mode
                        else {}
                    ),
                    **({"employeeContext": employee_context} if employee_mode else {}),
                    **(
                        {"confirmedScopeEvidence": scope_evidence}
                        if user_scope_mode
                        else {}
                    ),
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
        wait_session = None
        if invocation["executor_revision"] in {"6", "7"}:
            if self.durable_wait is None:
                raise ValueError("NATIVE_WAIT_NOT_ENABLED")
            if (
                self.durable_wait.executorId,
                self.durable_wait.executorRevision,
                self.durable_wait.executorConfigurationDigest,
            ) != (
                document_revision.executor_id,
                document_revision.executor_revision,
                document_revision.configuration_digest,
            ) or typed_mode != bool(
                getattr(self.durable_wait, "typedQuestions", False)
            ):
                raise ValueError("NATIVE_WAIT_EXECUTOR_BINDING_CHANGED")
            from .native_wait_runtime import NativeWaitRuntimeSession

            wait_session = NativeWaitRuntimeSession(
                runtime=self,
                command=command,
                context=context,
                preparation=p,
                task_id=row["task_id"],
                invocation_id=invocation_id,
                executor=document_revision,
                scope_evidence=scope_evidence,
                current_authority=current_authority,
            )
            ports.defer_input = wait_session.defer_input
            if typed_mode:
                from .native_question_contracts import resolve_contract, scope_contracts

                ports.validate_question_contract = lambda identity: resolve_contract(
                    library, identity
                )
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
                from .native_scope_answer import record_bound_answer

                record_bound_answer(library, question, reply)
                return reply

            ports.clarify = clarify
        if wait_session is not None and wait_session.continuation is not None:
            from .native_wait_runtime import ContinuationJournal

            journal = ContinuationJournal(wait_session)

            def enter_continuation(frame, root):
                won = wait_session.enter(frame, root)
                if won:
                    wait_session.restore_library(library, frame)
                return won

            ports.enter_continuation = enter_continuation
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
        arguments = (
            invocation_id,
            problem["title"] + "\n" + problem["description"],
            [
                "根据用户确认的范围选择文档规范，逐节核对完整性，引用准确原文；不"
                "代替上线批准。"
                if document_mode
                else (
                    "依据资料声明的口径调用只读工具核对原始证据，保留缺口和限制；"
                    "不推断因果、不代表业务接受。"
                )
                if data_mode
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
                **(
                    {
                        "domain": "NATIVE_READONLY_DATA",
                        "nativeDataAdapter": executor.adapter.descriptor(),
                        "answerSchema": library.answer_schema,
                    }
                    if data_mode
                    else {}
                ),
                **({"employeeContext": employee_context} if employee_mode else {}),
                **(
                    {"confirmedScopeEvidence": scope_evidence}
                    if user_scope_mode
                    else {}
                ),
                **(
                    {"questionContracts": scope_contracts(library)}
                    if typed_mode
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
        if wait_session is not None and wait_session.continuation is not None:
            root = {
                "identity": arguments[0],
                "goal": arguments[1],
                "criteria": arguments[2],
                "context": arguments[3],
                "tools": [t.descriptor() for t in loop.tools.values()],
                "limits": vars(loop.limits),
            }
            result = wait_session.terminal(root)
            if result is None:
                frame = wait_session.frame(root)
                if not wait_session.acquire():
                    from agent_runtime.native_loop_wait import (
                        LoopContinuationObservation,
                    )

                    return LoopContinuationObservation(
                        invocation_id, frame.checkpoint_digest
                    )
                result = loop.run_continuation(*arguments, continuation=frame)
        else:
            result = loop.run(*arguments)
        from agent_runtime.native_loop_wait import (
            LoopContinuationObservation,
            LoopWaiting,
        )

        if isinstance(result, LoopContinuationObservation):
            return result

        if isinstance(result, LoopWaiting):
            if wait_session is None or not hasattr(wait_session, "waiting"):
                raise ValueError("NATIVE_WAIT_OWNER_RECEIPT_REQUIRED")
            return wait_session.waiting
        return {
            **result,
            "performance": {
                "authority": authority_timing,
                "note": "Includes supervisor cancellation checks; nested, not additive",
            },
            **({"employeeContext": employee_context} if employee_mode else {}),
            **({"confirmedScopeEvidence": scope_evidence} if user_scope_mode else {}),
            "modelExecution": "REAL_PROVIDER",
            "model": asdict(profile.binding),
            "ledgerId": self.model.budget.ledger_id,
            "policyDigest": self.policy_digest,
            "invocationId": invocation_id,
        }
