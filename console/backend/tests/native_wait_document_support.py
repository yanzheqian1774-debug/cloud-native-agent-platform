"""Controlled decision ports over real document/Skill/Native owners, disposable DB."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.execution_application import (
    ExecutionCompletionService,
    ExecutionEvidenceRecord,
    PostgresExecutionCompletionWriter,
    RecordNativeCompletionCommand,
)
from agent_console.native_document_rule_tools import NativeDocumentRuleTools
from agent_console.native_document_skill import NativeDurableDocumentSkillExecutor
from agent_console.native_loop_journal import NativeLoopJournal
from agent_console.native_loop_runtime import COMMAND
from agent_console.native_wait_runtime import (
    ContinuationJournal,
    NativeWaitRuntimeSession,
)
from agent_console.native_wait_store import NativeWaitStore
from agent_console.ontology_execution import published_content
from agent_console.prepared_execution_application import PreparedExecutionApplication
from agent_console.prepared_execution_lineage import prepared_attempt
from agent_console.prepared_native_composition import POLICY
from agent_console.prepared_native_coordinator import PreparedNativeCoordinator
from agent_console.prepared_native_skill import PreparedNativeSkillCaller
from agent_console.skill_executor import SkillExecutorRegistry
from agent_console.skill_invocation_application import FixedReadOnlyPolicyAuthority
from agent_console.skill_invocation_composition import compose_governed_skill_invocation
from agent_console.workbench_business_problem import OwnerPrincipal
from agent_operator.native_dispatch_reconciler import (
    ManagedSkillNativeTransport,
    NativeDispatchWorker,
)
from agent_runtime.native_loop import Limits, NativeLoop, digest
from agent_runtime.native_loop_wait import LoopWaiting
from test_prepared_native_pipeline import FixtureKubernetes


def compose(
    e,
    work,
    native,
    p,
    *,
    executor_type=NativeDurableDocumentSkillExecutor,
    typed_questions=False,
    decision_factory=None,
    worker_id="durable-controlled-host",
    bound_service_execution=None,
):
    calls, sessions, runner_errors = [], [], []
    now = datetime.now(UTC)
    expiry = getattr(e, "wait_runtime_expiry", now + timedelta(hours=1))
    runtime = NS(
        pool=native.pool,
        owned_business=e.business_owner,
        bound_service_execution=bound_service_execution,
        config={
            "maximumDecisions": 8,
            "modelRuntimeDigest": "a" * 64,
            "expiresAt": expiry.isoformat(),
        },
        expiry=expiry,
        durable_wait=NS(
            maximumHumanWaitSeconds=1200,
            typedQuestions=typed_questions,
            executorId=executor_type.revision.executor_id,
            executorRevision=executor_type.revision.executor_revision,
            executorConfigurationDigest=executor_type.revision.configuration_digest,
        ),
        model=NS(budget=NS(allowance_id=None)),
        generation=NS(
            credential_by_id=lambda _: None,
            policy_version=e.context.authentication_policy_version,
        ),
    )

    def authority(c, command):
        context, adapter = work.authority_factory(c, command)
        app = PreparedExecutionApplication(
            c,
            OwnerPrincipal(context.principal_id, p.namespace, p.security_domain),
            adapter,
        )
        app.validate(p)
        if bound_service_execution is not None:
            bound_service_execution.read(c, context, command, p)
        else:
            from agent_console.authority_contracts import AuthorityError
            from agent_console.owned_business_resource_adapter import authorize_dispatch

            if not authorize_dispatch(e.business_owner, c, command, context):
                raise AuthorityError("NATIVE_WAIT_CURRENT_DISPATCH_DENIED")
        return context, adapter

    runtime.authorize_current = lambda c, command: bool(authority(c, command))

    def authorize(c, command):
        context, adapter = authority(c, command)
        row = prepared_attempt(c, command.scope, command.attempt_id)
        return adapter.require(
            OwnerPrincipal(context.principal_id, p.namespace, p.security_domain),
            "SKILL",
            "INVOKE_SKILL",
            f"skill-invocation:prepared:{p.digest}:{row['task_id']}:{row['attempt_ordinal']}",
        ).decision_id

    def runner(invocation_id, output, timeout):
        command = COMMAND.get()
        with native.pool.connection() as c:
            row = prepared_attempt(c, command.scope, command.attempt_id)
            rules = published_content(c, command.scope, p.business_semantics)
        library = NativeDocumentRuleTools(
            output["source"],
            output["sourceSnapshot"],
            rules.model_dump(mode="json"),
            p.business_semantics.model_dump(mode="json"),
        )

        def current(c):
            authority(c, command)
            return True

        session = NativeWaitRuntimeSession(
            runtime=runtime,
            command=command,
            context=e.context,
            preparation=p,
            task_id=row["task_id"],
            invocation_id=invocation_id,
            executor=executor_type.revision,
            scope_evidence=None,
            current_authority=current,
        )
        sessions.append(session)
        base = NativeLoopJournal(native.pool, command.scope, invocation_id)
        journal = ContinuationJournal(session) if session.continuation else base

        class Ports:
            def defer_input(self, *args, **kwargs):
                try:
                    return session.defer_input(*args, **kwargs)
                except Exception:
                    import traceback

                    runner_errors.append("defer_input: " + traceback.format_exc())
                    raise

            def authorize(self, *_):
                with native.pool.connection() as c:
                    return current(c)

            def decide(self, assembled, **kwargs):
                calls.append(kwargs["key"])
                ordinal = 8 - assembled["remainingDecisions"]
                if decision_factory is not None:
                    return decision_factory(library, ordinal)
                if ordinal < 2:
                    return {
                        "action": "CLARIFY",
                        "question": f"Confirm business choice {ordinal}?",
                    }
                document = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "SUBMISSION"
                )
                policy = next(
                    d["id"]
                    for d in library.documents.values()
                    if d["role"] == "POLICY" and d["scope"] == library.binding.scope
                )
                if ordinal in (2, 3):
                    return {
                        "action": "TOOL",
                        "tool": "read_document",
                        "arguments": {"id": document if ordinal == 2 else policy},
                    }
                if ordinal == 4:
                    return {
                        "action": "TOOL",
                        "tool": "review_document",
                        "arguments": {"documentId": document, "policyId": policy},
                    }
                if ordinal == 5:
                    return {"action": "TOOL", "tool": "build_report", "arguments": {}}
                return {
                    "action": "FINISH",
                    "answer": library.invoke("build_report", {})["completionAnswer"],
                }

            def invoke(self, tool, arguments, **kwargs):
                return library.invoke(tool.name, arguments)

            def verify(self, assembled, answer):
                return library.verify(assembled, answer)

            def enter_continuation(self, frame, root):
                result = session.enter(frame, root)
                if result:
                    session.restore_library(library, frame)
                return result

        ports = Ports()
        context = {}
        if typed_questions:
            from agent_console.native_question_contracts import (
                resolve_contract,
                scope_contracts,
            )

            ports.validate_question_contract = lambda identity: resolve_contract(
                library, identity
            )
            context["questionContracts"] = scope_contracts(library)
        loop = NativeLoop(
            library.tools,
            ports,
            journal,
            limits=Limits(maximum_decisions=8, total_seconds=300),
        )
        args = (
            invocation_id,
            "controlled document review",
            ["exact evidence"],
            context,
        )
        if session.continuation:
            root = {
                "identity": args[0],
                "goal": args[1],
                "criteria": args[2],
                "context": args[3],
                "tools": [t.descriptor() for t in library.tools],
                "limits": vars(loop.limits),
            }
            result = session.terminal(root)
            if result is None:
                frame = session.frame(root)
                assert session.acquire()
                result = loop.run_continuation(*args, continuation=frame)
        else:
            result = loop.run(*args)
        if isinstance(result, LoopWaiting):
            return session.waiting
        return result

    def observed_runner(*args):
        try:
            return runner(*args)
        except Exception:
            import traceback

            runner_errors.append(traceback.format_exc())
            raise

    skills = compose_governed_skill_invocation(
        native.pool.conninfo,
        Path(__file__).parents[1] / "migrations",
        None,
        FixedReadOnlyPolicyAuthority(POLICY),
        SkillExecutorRegistry((executor_type(observed_runner),)),
    )
    runtime.skill_repository = skills.invocation_repository
    with native.pool.connection() as c, c.transaction():
        c.execute(
            (Path(__file__).parents[1] / "migrations/0050_native_loop.sql").read_text()
        )
        NativeWaitStore.migrate(c)
    caller = PreparedNativeSkillCaller(native.pool, skills, authorize)
    caller.runtime = runtime
    coordinator = PreparedNativeCoordinator(native)

    def queue():
        with native.pool.connection() as c, c.transaction():
            _, auth = work.authority_factory(c, NS(principal_id=e.context.principal_id))
            coordinator(
                NS(
                    connection=c,
                    context=e.context,
                    authority=auth,
                    policy_generation=auth.generation,
                    recovery_epoch=1,
                ),
                p,
            )

    completion = ExecutionCompletionService(
        native, PostgresExecutionCompletionWriter(native)
    )

    def complete(claim, observation):
        command = claim.command
        identity = native.get_attempt(command.scope, command.attempt_id)
        evidence_id, outcome_id = (
            "test-evidence:" + str(command.attempt_id),
            "test-outcome:" + str(command.attempt_id),
        )
        evidence = ExecutionEvidenceRecord.from_allowlisted(
            dict(
                evidence_record_id=evidence_id,
                namespace=p.namespace,
                security_domain=p.security_domain,
                platform_execution_identity=str(command.attempt_id),
                workflow_identity=p.run_id,
                task_identity=str(identity.task_run.task_run_id),
                attempt_ordinal=1,
                event_ordinal=1,
                event_type="EXECUTION_OUTCOME",
                occurred_at=observation.observed_at.isoformat(),
                runtime_classification="NATIVE",
                selected_instance_identity="native",
                capability_identity=None,
                authorization_decision="ALLOW",
                reason_code="NATIVE_EXECUTION_SUCCEEDED",
                provider_correlation_id=observation.kubernetes_task_uid,
                provider_call_count=1,
                outcome_classification=observation.kind.value,
                outcome_reference=outcome_id,
                references=[],
                limitation_code="CONTROLLED_MODEL_KUBERNETES_NOT_ACCEPTANCE",
                supersedes_record_id=None,
                schema_version=1,
            )
        )
        outcome = dict(
            outcome_id=outcome_id,
            workflow_run_id=p.run_id,
            task_run_id=str(identity.task_run.task_run_id),
            attempt_id=str(command.attempt_id),
            approved_plan_revision_id=command.approved_plan_revision_id,
            evidence_ids=[evidence_id],
            classification=observation.kind.value,
            technical=True,
            business_problem_resolved=False,
        )
        completion.record_native(
            RecordNativeCompletionCommand(
                claim, observation, (evidence,), outcome_id, outcome
            )
        )

    kube = FixtureKubernetes()
    worker = NativeDispatchWorker(
        native,
        kube,
        ManagedSkillNativeTransport(caller),
        lambda c, command: bool(authority(c, command)),
        complete,
        worker_id=worker_id,
        prepare_ready=queue,
    )

    def startup(number, predecessors=()):
        observation = dict(
            schema="native-host-startup.v1",
            workerId=worker_id,
            startupId=f"controlled-startup-{number}",
            namespace=p.namespace,
            securityDomain=p.security_domain,
            principalId=e.context.principal_id,
            authorizationResources=["governed-execution:prepared:" + p.digest],
            predecessorDigests=list(predecessors),
            pid=20000 + number,
            processBirth=f"controlled-process-{number}",
        )
        return dict(observation=observation, digest=digest(observation))

    return NS(
        worker=worker,
        skills=skills,
        runtime=runtime,
        startup=startup,
        calls=calls,
        sessions=sessions,
        runner_errors=runner_errors,
        caller=caller,
        kube=kube,
    )
