"""Controlled decision ports over real document/Skill/Native owners, disposable DB."""

from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.execution_application import (
    ExecutionCompletionService,
    ExecutionEvidenceRecord,
    PostgresExecutionCompletionWriter,
    RecordNativeCompletionCommand,
)
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
from agent_runtime.native_loop import NativeLoop
from test_prepared_native_pipeline import FixtureKubernetes


def compose(e, work, native, p, *, tmp_path, monkeypatch):
    from agent_console.native_data_adapters import ADAPTERS
    from agent_console.native_data_skill import NativeDataSkillExecutor
    from test_native_delivery_tools import Decisions

    adapter = next(
        a for a in ADAPTERS if a.source_schema == "synthetic-delivery-source.v1"
    )
    calls = []
    decisions = []
    runtime_results = []
    worker_id = "controlled-native-data-host"

    def authority(c, command):
        context, adapter = work.authority_factory(c, command)
        app = PreparedExecutionApplication(
            c,
            OwnerPrincipal(context.principal_id, p.namespace, p.security_domain),
            adapter,
        )
        app.validate(p)
        if getattr(e, "service_bridge", None) is not None:
            e.service_bridge.authorize(c, context, command)
        else:
            e.business_owner.work(c, context, p.semantics.target.problem)
        return context, adapter

    def authorize(c, command):
        context, adapter = authority(c, command)
        row = prepared_attempt(c, command.scope, command.attempt_id)
        return adapter.require(
            OwnerPrincipal(context.principal_id, p.namespace, p.security_domain),
            "SKILL",
            "INVOKE_SKILL",
            f"skill-invocation:prepared:{p.digest}:{row['task_id']}:{row['attempt_ordinal']}",
        ).decision_id

    runtime_box = []

    def runner(invocation_id, output, timeout):
        try:
            result = runtime_box[0].run(invocation_id, output, timeout)
            runtime_results.append(
                {
                    "status": result.get("status"),
                    "performance": result.get("performance"),
                }
            )
            if result.get("status") != "SUCCEEDED":
                print("CONTROLLED_RUNTIME_RESULT", result)
            return result
        except Exception:
            import traceback

            traceback.print_exc()
            raise

    skills = compose_governed_skill_invocation(
        native.pool.conninfo,
        Path(__file__).parents[1] / "migrations",
        None,
        FixedReadOnlyPolicyAuthority(POLICY),
        SkillExecutorRegistry((NativeDataSkillExecutor(adapter, runner),)),
    )
    with native.pool.connection() as c, c.transaction():
        c.execute(
            (Path(__file__).parents[1] / "migrations/0050_native_loop.sql").read_text()
        )
    import json
    from dataclasses import dataclass
    from datetime import UTC, datetime, timedelta
    from hashlib import sha256

    from agent_console import native_loop_runtime as runtime_module

    @dataclass
    class ControlledBinding:
        marker: str = "CONTROLLED_MODEL_BINDING_NOT_LIVE_PROVIDER"

    model_file = tmp_path / "controlled-model.json"
    model_file.write_text("{}")
    config_file = tmp_path / "controlled-native.json"
    config_file.write_text(
        json.dumps(
            dict(
                purpose="NATIVE_TASK_DECISION_V1",
                maximumDecisions=8,
                expiresAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                modelRuntimeFile=str(model_file),
                modelRuntimeDigest=sha256(model_file.read_bytes()).hexdigest(),
                ledgerId="controlled-original-ledger",
                authorizationMode="EXACT_SERVICE_SUBJECT"
                if getattr(e, "service_bridge", None)
                else "EXACT_ORIGINAL_SUBJECT",
                **(
                    {
                        "serviceCredentialId": (
                            e.context.session_id_or_service_credential_id
                        )
                    }
                    if getattr(e, "service_bridge", None)
                    else {}
                ),
                subject=e.context.principal_id,
                nativeDataAdapters=[adapter.descriptor()],
            )
        )
    )
    model = NS(
        dependencies=NS(
            profile=NS(real_calls_enabled=True),
            provider=NS(transport_profile=NS(binding=ControlledBinding())),
        ),
        budget=NS(
            call_cap=20,
            total_cost_cap_microusd=1000000,
            ledger_id="controlled-original-ledger",
        ),
    )
    monkeypatch.setattr(runtime_module, "build_planning_runtime", lambda **_: model)

    # Only model decision port is replaced. Actual runtime context construction,
    # source tuple, current owner authorization, tools, journal and verify run.
    def loop_factory(tools, ports, journal, **kwargs):
        decide = Decisions.__new__(Decisions)

        def controlled(assembled, **kw):
            assert assembled["context"]["domain"] == "NATIVE_READONLY_DATA"
            assert assembled["context"]["nativeDataAdapter"] == adapter.descriptor()
            assert assembled["context"]["answerSchema"]
            action = decide.decide(assembled, **kw)
            decisions.append(action["action"])
            if action["action"] == "TOOL":
                calls.append(action["tool"])
            return action

        ports.decide = controlled
        return NativeLoop(tools, ports, journal, **kwargs)

    monkeypatch.setattr(runtime_module, "NativeLoop", loop_factory)
    runtime_box.append(
        runtime_module.NativeLoopRuntime(
            config_file,
            native.pool,
            native.pool.conninfo,
            Path(__file__).parents[1] / "migrations",
            None,
            NS(policy_version=e.context.authentication_policy_version),
            authorize,
            authorize_current=lambda c, cmd: bool(authority(c, cmd)),
        )
    )
    caller = PreparedNativeSkillCaller(native.pool, skills, authorize)
    coordinator = PreparedNativeCoordinator(native)

    def queue():
        with native.pool.connection() as c, c.transaction():
            _, auth = work.authority_factory(
                c,
                getattr(e, "factory_command", NS(principal_id=e.context.principal_id)),
            )
            coordinator(
                NS(
                    connection=c,
                    context=e.context,
                    authority=auth,
                    policy_generation=(
                        e.factory_command.authority_generation.value
                        if hasattr(e, "factory_command")
                        else auth.generation
                    ),
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

    return NS(
        worker=worker,
        skills=skills,
        calls=calls,
        caller=caller,
        decisions=decisions,
        runtime_results=runtime_results,
    )
