# ruff: noqa: F401,F811 -- Original isolated owner fixture registration.
"""Real same-DB ordinary owner chain; publication setup is isolated fixture only."""

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.digital_employee_definition import CompositionMember, MemberKind
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.owned_business_resource_adapter import (
    derive_work,
    evidence,
    require_reference,
)
from agent_console.owned_resource_assembly import MODE, selection_work
from agent_console.plan_suggestion_domain import ConfirmedPlanRevision, ExactReference
from agent_console.policy_plan_confirmation import PolicyPlanConfirmation
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from owned_business_consumer_support import configure_scope as original_scope
from owned_business_consumer_support import (
    prepare_current_resource_reads,
)
from owned_business_consumer_support import (
    prepare_source as original_source,
)
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark as pgmark
from test_conversation_relation_bff import routed
from test_owned_business_admission import owned_created, owned_ready
from test_owned_business_consumer_chain import cleanup_consumer_resources
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted


def prepare_source(e):
    # The initial synthetic fixture explicitly supplies its scope before any
    # source publication/admission. No saved user answer or old source is edited.
    # Ordinary scope clarification remains a separate existing product boundary.
    from copy import deepcopy
    from unittest.mock import patch

    from test_native_document_tools import SOURCE

    source = deepcopy(SOURCE)
    source["confirmedScope"] = "production"
    with patch("owned_business_consumer_support.SOURCE", source):
        result = original_source(e)
    e.assembly_case = "SUCCESS"
    return result


def unknown_source(e):
    result = prepare_source(e)
    e.assembly_case = "UNKNOWN"
    return result


def durable_source(e):
    from unittest.mock import patch

    from agent_console.native_document_resource_bundle import resource_content
    from agent_console.native_document_skill import NativeDurableDocumentSkillExecutor

    def content(source, **kwargs):
        return resource_content(source, **kwargs, durable_wait=True)

    with (
        patch("owned_business_consumer_support.resource_content", content),
        patch(
            "owned_business_consumer_support.NativeRuleDocumentSkillExecutor",
            NativeDurableDocumentSkillExecutor,
        ),
    ):
        result = original_source(e)
    e.assembly_case = "DURABLE"
    return result


def configure_scope(e, result, policy):
    from copy import deepcopy
    from unittest.mock import patch

    from agent_console.native_document_skill import (
        NativeDurableDocumentSkillExecutor,
        NativeRuleDocumentSkillExecutor,
    )
    from test_native_document_tools import SOURCE

    source = deepcopy(SOURCE)
    if e.assembly_case != "DURABLE":
        source["confirmedScope"] = "production"
    executor = (
        NativeDurableDocumentSkillExecutor
        if e.assembly_case == "DURABLE"
        else NativeRuleDocumentSkillExecutor
    )
    with (
        patch("owned_business_consumer_support.SOURCE", source),
        patch(
            "owned_business_consumer_support.NativeRuleDocumentSkillExecutor", executor
        ),
    ):
        original_scope(e, result, policy)
    policy["scopes"][0]["trustedAssemblyAdoption"] = MODE


pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(mode=None, prepare_source=source, configure_scope=configure_scope)
            for source in (prepare_source, unknown_source, durable_source)
        ],
        indirect=True,
    ),
]


def publish_new_role(e, c, *, suffix=""):
    """Normal original publication owners, no fake resource/contract/receipt rows."""
    from agent_console.digital_employee_definition import EmployeeRevision
    from agent_console.planning_candidates import read_published

    scope = ScopeIdentity(e.context.scope.tenant_id, e.context.scope.security_domain)
    old = e.consumer_refs["agent"]
    content, _ = read_published(c, scope, "AGENT", old)
    content = {**content, "title": "Same-business successor document reviewer"}
    service = e.consumer_services["agent"]
    value = service.create(
        service.scope(scope.namespace, scope.security_domain),
        "human:fixture-author",
        "Same-business role successor",
        content,
    )
    rev = value["revisions"][-1]
    new_agent = ExactReference(
        resource_id=value["definitionId"],
        revision_id=rev["revisionId"],
        digest=rev["digest"],
    )
    # Exactly the pre-existing fixture publication owner. This is setup only;
    # adoption below uses the ordinary real trusted context and dynamic grants.
    publication = NS(
        context=NS(
            principal_id="human:isolated-publication-reviewer", scope=e.context.scope
        ),
        connection=c,
        authority=NS(require=lambda *args: NS(decision_id="isolated-setup-only")),
        path={
            "kind": "agent",
            "identity": new_agent.resource_id,
            "revision": new_agent.revision_id,
        },
        payload={
            "expectedVersion": value["aggregateVersion"],
            "digest": new_agent.digest,
            "reason": "Isolated same-contract resource setup",
            "idempotencyKey": "new-agent-review" + suffix,
        },
    )
    owner = PreparedResourceOwner(e.consumer_services)
    owner(NS(**vars(publication), operation="REVIEW_PREPARED_RESOURCE"))
    repo = PostgresEmployeeDefinitionRepository(e.repo)
    old_employee = repo._read(
        c, scope, e.consumer_employee.resource_id, e.consumer_employee.revision_id
    )
    revision = EmployeeRevision.from_record(old_employee["revision"])
    revision = replace(
        revision,
        definition_id="employee-definition:trusted-new-role" + suffix,
        revision_id="employee-revision:trusted-new-role" + suffix,
        role="Same-business selected role",
        members=tuple(
            CompositionMember(
                m.kind, new_agent.resource_id, new_agent.revision_id, new_agent.digest
            )
            if m.kind == MemberKind.AGENT
            else m
            for m in revision.members
        ),
    )
    created = repo.create_for_workbench(
        c,
        revision,
        expected_version=0,
        decision_id="isolated-setup",
        command_id="trusted-role-create" + suffix,
        authorized=True,
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        created = repo.decide_for_workbench(
            c,
            scope,
            revision.definition_id,
            revision.revision_id,
            revision.digest,
            action,
            expected_version=created["aggregateVersion"],
            decision_id="isolated-setup",
            command_id="trusted-role-" + action + suffix,
            authorized=True,
        )
    return new_agent, ExactReference(
        resource_id=revision.definition_id,
        revision_id=revision.revision_id,
        digest=revision.digest,
    )


def test_ordinary_selected_new_role_reaches_prepared_native_host_without_policy_rewrite(
    owned_created, tmp_path, request, monkeypatch
):
    from agent_console.problem_resource_coverage import coverage
    from test_owned_business_consumer_chain import (
        test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
    )

    e = owned_created
    unknown = e.assembly_case == "UNKNOWN"
    durable = e.assembly_case == "DURABLE"
    policy_bytes = e.business_owner.path.read_bytes()
    original_confirm = PolicyPlanConfirmation.__call__
    observed = {}

    def confirm_and_explicitly_select(handler, call):
        original = original_confirm(handler, call)
        if "response" in observed:
            return observed["response"]
        automation = handler.automation
        plan = ConfirmedPlanRevision.model_validate(original["confirmation"]["plan"])
        c = call.connection
        old_ref = e.consumer_employee
        new_agent, new_employee = observed["new_agent"], observed["new_employee"]
        # Adoption must not manufacture USE. The original same-scope policy owner
        # separately prepares its already approved ontology, as Native normally does.
        from agent_console.authority_contracts import ExactGrant
        from agent_console.ontology_service import resource

        work = automation.work(
            call.context,
            plan.semantics.target.problem,
            automation.grants.clock(),
            connection=c,
            plan=plan,
        )
        with pytest.raises(AuthorityError, match="READ_DENIED"):
            selection_work(automation, call, work, plan, new_employee)
        ontology = work.businessScope.documentRules.ontology
        ontology_grants = [
            ExactGrant(
                "BUSINESS_ONTOLOGY",
                action,
                resource(ontology.resource_id, ontology.revision_id),
            )
            for action in ("READ", "USE")
        ]
        automation.decide(
            call,
            ontology_grants,
            "explicit-old-ontology-access",
            work,
            automation.authenticate(call.context),
        )
        automation.proof_grants(call, ontology_grants)
        directory = coverage(automation, call, plan)
        observed["coverage"] = directory
        selected = [
            x
            for x in directory["candidates"]
            if x["reference"] == new_employee.model_dump(mode="json")
        ]
        assert (
            len(selected) == 1 and selected[0]["state"] == "SELECTABLE_FOR_VERIFICATION"
        ), selected
        body = {
            "version": plan.version,
            "digest": plan.digest,
            "expectedProposalRevision": plan.source_proposal_revision,
            "employee": new_employee.model_dump(mode="json"),
            "idempotencyKey": "explicit-trusted-role-selection",
        }
        select_call = replace(
            call,
            operation="SELECT_POLICY_EMPLOYEE_RESOURCES",
            payload=body,
            path={"proposal_id": plan.plan_id},
        )
        result = automation.select_employee(select_call)
        assert automation.select_employee(select_call) == result
        from agent_console.resource_preparation_plan import read_selection

        recovered = read_selection(
            automation,
            replace(
                select_call,
                operation="READ_POLICY_EMPLOYEE_SELECTION",
                payload={},
                query={"version": plan.version, "key": body["idempotencyKey"]},
            ),
        )
        assert recovered == result
        successor = ConfirmedPlanRevision.model_validate(result["confirmation"]["plan"])
        assert successor.predecessor_digest == plan.digest
        assert successor.semantics.target == plan.semantics.target
        assert successor.semantics.tasks == plan.semantics.tasks
        assert result["assemblyAdoption"]["body"]["employee"] == body["employee"]
        old_work = derive_work(
            e.business_owner, c, e.context, plan.semantics.target.problem, plan=plan
        )
        assert old_work.assemblyAdoption is None
        require_reference(old_work, "employee", old_ref)
        with pytest.raises(AuthorityError, match="RESOURCE_NOT_AUTHORIZED"):
            require_reference(old_work, "employee", new_employee)
        observed.update(
            response={**original, "confirmation": result["confirmation"]},
            result=result,
            new_agent=new_agent,
            new_employee=new_employee,
            original_plan=plan,
            successor=successor,
        )
        return observed["response"]

    import owned_business_consumer_support as support

    original_automation = support.resource_automation

    def setup_new_resources(*args, **kwargs):
        automation, adapter = original_automation(*args, **kwargs)
        with e.repo.connection_scope() as c:
            new_agent, new_employee = publish_new_role(e, c)
        # Missing ordinary READ is rejected before any selection grant/receipt.
        from agent_console.owned_resource_assembly import read_assembly

        with e.repo.connection_scope() as c:
            before = c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            with pytest.raises(AuthorityError, match="READ_DENIED"):
                read_assembly(
                    e.business_owner.work_reader,
                    c,
                    e.context,
                    e.business_owner.policy.scopes[0],
                    new_employee,
                    selecting=True,
                )
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_decisions"
                ).fetchone()["n"]
                == before
            )
        refs, emp = e.consumer_refs, e.consumer_employee
        e.consumer_refs, e.consumer_employee = (
            {**refs, "agent": new_agent},
            new_employee,
        )
        prepare_current_resource_reads(e, automation)
        e.consumer_refs, e.consumer_employee = refs, emp
        observed.update(new_agent=new_agent, new_employee=new_employee)
        return automation, adapter

    monkeypatch.setattr(support, "resource_automation", setup_new_resources)
    monkeypatch.setattr(
        PolicyPlanConfirmation, "__call__", confirm_and_explicitly_select
    )

    def inspect(worker, native, receipt, ready):
        assert ready["assembly"]["definition"] == observed["new_employee"].model_dump(
            mode="json"
        )
        assert receipt["sourcePlanVersion"] == observed["successor"].version
        assert (
            receipt["ownedBusiness"]["assemblyAdoption"]["digest"]
            == observed["result"]["assemblyAdoption"]["digest"]
        )
        assert worker.dispatches()
        assert e.business_owner.path.read_bytes() == policy_bytes
        from copy import deepcopy

        from agent_console.owned_resource_assembly import project
        from agent_console.resource_use_domain import canonical_digest

        reader = e.business_owner.work_reader
        with native.pool.connection() as actual_c:
            base = reader.work(
                actual_c,
                e.context,
                prepared_problem := observed["successor"].semantics.target.problem,
            )
            actual_row = actual_c.execute(
                "SELECT request_key,record FROM "
                "execution_authority.resource_policy_plan_commands "
                "WHERE request_key=%s",
                ("explicit-trusted-role-selection",),
            ).fetchone()

            class FaultRead:
                def __init__(self, row):
                    self.row = row

                def execute(self, query, args=None):
                    if query.startswith(
                        "SELECT request_key,record FROM "
                        "execution_authority.resource_policy_plan_commands"
                    ):
                        return NS(fetchall=lambda: [self.row])
                    return actual_c.execute(query, args)

                def __getattr__(self, name):
                    return getattr(actual_c, name)

            for damage in (
                "checksum",
                "subject",
                "generation",
                "recovery",
                "source",
                "ontology",
                "member",
                "plan",
            ):
                fake = deepcopy(actual_row)
                proof = fake["record"]["assemblyAdoption"]
                body = proof["body"]
                if damage == "subject":
                    body["subject"] = "human:other"
                elif damage == "generation":
                    body["authorityGeneration"] += 1
                elif damage == "recovery":
                    body["recoveryEpoch"] += 1
                elif damage == "source":
                    body["scope"]["source"]["resource_id"] = "knowledge:other"
                elif damage == "ontology":
                    body["scope"]["documentRules"]["ontology"]["digest"] = "0" * 64
                elif damage == "member":
                    body["members"].pop()
                elif damage == "plan":
                    body["plan"]["digest"] = "0" * 64
                proof["digest"] = (
                    "0" * 64 if damage == "checksum" else canonical_digest(body)
                )
                with pytest.raises(AuthorityError, match="OWNED_ASSEMBLY_"):
                    project(
                        reader, FaultRead(fake), e.context, base, observed["successor"]
                    )

        from agent_console.native_document_skill import (
            NativeDurableDocumentSkillExecutor,
            NativeRuleDocumentSkillExecutor,
        )
        from agent_console.owned_resource_assembly import (
            ensure_no_pending_execution,
            plan_reference,
        )
        from agent_console.workbench_prepared_execution import candidate
        from agent_operator.errors import TaskExecutionError
        from native_wait_document_support import compose

        with native.pool.connection() as c:
            prepared = candidate(
                c,
                ScopeIdentity(
                    e.context.scope.tenant_id, e.context.scope.security_domain
                ),
                receipt["preparationDigest"],
            )

        def decide(library, ordinal):
            if durable and ordinal == 0:
                return {
                    "action": "CLARIFY",
                    "question": "Which policy scope should be used?",
                }
            if durable:
                ordinal -= 1
            submitted = next(
                d["id"] for d in library.documents.values() if d["role"] == "SUBMISSION"
            )
            policy = next(
                d["id"]
                for d in library.documents.values()
                if d["role"] == "POLICY" and d["scope"] == library.binding.scope
            )
            actions = [
                ("read_document", {"id": submitted}),
                ("read_document", {"id": policy}),
                ("review_document", {"documentId": submitted, "policyId": policy}),
                ("build_report", {}),
            ]
            if ordinal < len(actions):
                name, args = actions[ordinal]
                return {"action": "TOOL", "tool": name, "arguments": args}
            return {
                "action": "FINISH",
                "answer": library.invoke("build_report", {})["completionAnswer"],
            }

        import traceback

        from agent_runtime.native_loop import NativeLoop

        port_errors = []

        class RecordingLoop(NativeLoop):
            def __init__(self, tools, ports, journal, **kwargs):
                def wrap(fn):
                    def invoke(*args, **kw):
                        try:
                            return fn(*args, **kw)
                        except Exception:
                            port_errors.append(traceback.format_exc())
                            raise

                    return invoke

                for name in ("authorize", "decide", "invoke", "verify"):
                    setattr(ports, name, wrap(getattr(ports, name)))
                journal.claim = wrap(journal.claim)
                journal.finish = wrap(journal.finish)
                super().__init__(tools, ports, journal, **kwargs)

        monkeypatch.setattr("native_wait_document_support.NativeLoop", RecordingLoop)
        live = compose(
            e,
            worker,
            native,
            prepared,
            executor_type=(
                NativeDurableDocumentSkillExecutor
                if durable
                else NativeRuleDocumentSkillExecutor
            ),
            decision_factory=decide,
        )
        request.addfinalizer(live.skills.invocation_repository.pool.close)
        startup = live.startup(1)
        live.worker.startup_observation = NS(
            current=lambda: startup, observe_only_receipt=lambda _: None
        )
        if unknown:

            def lose_outcome(command):
                raise TaskExecutionError(
                    "ExecutionOutcomeUnknown", "Isolated response loss", retryable=False
                )

            live.worker.transport.invoke = lose_outcome
            assert live.worker.run_once().state == "UNKNOWN"
            with native.pool.connection() as c:
                before = c.execute(
                    "SELECT count(*) n FROM "
                    "execution_authority.native_dispatch_commands"
                ).fetchone()["n"]
                with pytest.raises(AuthorityError, match="PRIOR_EXECUTION_UNRESOLVED"):
                    ensure_no_pending_execution(
                        c, e.context, plan_reference(observed["successor"])
                    )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM "
                        "execution_authority.native_dispatch_commands "
                        "WHERE state='UNKNOWN'"
                    ).fetchone()["n"]
                    == 1
                )
            assert live.worker.run_once().state == "IDLE"
            assert not live.calls
            with native.pool.connection() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM "
                        "execution_authority.native_dispatch_commands"
                    ).fetchone()["n"]
                    == before
                )
        elif durable:
            from datetime import UTC, datetime

            from agent_console.native_wait_command_access import NativeWaitCommandAccess
            from agent_console.native_wait_store import NativeWaitStore
            from native_wait_answer_support import browser, link_created_problem

            for _ in prepared.participants:
                waited = live.worker.run_once()
                if waited.state == "DRAIN_FOR_INPUT":
                    break
                assert waited.state == "SUCCEEDED", (waited, live.runner_errors)
            assert waited.state == "DRAIN_FOR_INPUT"
            assert len(live.calls) == 1
            session = live.sessions[-1]
            with native.pool.connection() as c, c.transaction():
                wait = session.waiting
                cp = NativeWaitStore(c, wait.identity).checkpoint(
                    wait.checkpoint_digest
                )
                assert (
                    session.binding(c).assembly_adoption["digest"]
                    == observed["result"]["assemblyAdoption"]["digest"]
                )
                assert session.binding(c).scope.employees == (observed["new_employee"],)
                access = NativeWaitCommandAccess(live.runtime, native, worker)
                candidate_wait = dict(
                    namespace=prepared.namespace,
                    securityDomain=prepared.security_domain,
                    principalId=e.context.principal_id,
                    preparationDigest=prepared.digest,
                    runId=prepared.run_id,
                )
                assert access.inspect(c, candidate_wait)["state"] == "QUIESCING"
                process = dict(
                    **candidate_wait,
                    workerId=cp.worker_id,
                    startupDigest=startup["digest"],
                    released=True,
                    pid=startup["observation"]["pid"],
                    processBirth=startup["observation"]["processBirth"],
                )
                exited = dict(
                    state="EXIT_CONFIRMED", stoppedAt=datetime.now(UTC).isoformat()
                )
                assert access.stopped(
                    c, candidate_wait, process, startup, exited, lambda *_: None
                )["stopRecorded"]
                assert access.inspect(c, candidate_wait)["state"] == "WAITING_FOR_USER"
            body = dict(
                invocationId=cp.identity.skill_invocation_id,
                questionKey=cp.question_key,
                questionDigest=cp.question_digest,
                conversationId=cp.identity.conversation_id,
                answer="production",
            )
            with browser(e, worker, native, prepared, live.runtime, tmp_path) as (
                client,
                path,
            ):
                link_created_problem(client, e, cp.identity.conversation_id)
                before_calls = list(live.calls)
                denied = client.post(
                    path + "/native-answers",
                    headers=e.adoption_headers,
                    json={**body, "questionDigest": "0" * 64},
                )
                assert denied.status_code in {403, 404}
                answered = client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=body
                )
                assert answered.status_code == 200, answered.text
                assert answered.json()["result"] == {
                    "accepted": True,
                    "replayed": False,
                }
                replayed = client.post(
                    path + "/native-answers", headers=e.adoption_headers, json=body
                )
                assert (
                    replayed.status_code == 200
                    and replayed.json()["result"]["replayed"]
                )
                assert live.calls == before_calls
            startup = live.startup(2, (startup["digest"],))
            live.worker.startup_observation = NS(
                current=lambda: startup, observe_only_receipt=lambda _: None
            )
            for _ in range(len(prepared.participants) + 1):
                resumed = live.worker.run_once()
                if resumed.state == "IDLE":
                    break
                assert resumed.state == "SUCCEEDED", (
                    resumed,
                    live.runner_errors,
                    port_errors,
                )
            assert resumed.state == "IDLE"
            assert len(live.calls) == len(set(live.calls)) == 6
            with native.pool.connection() as c:
                rows = c.execute(
                    "SELECT result FROM execution_authority.prepared_resource_commands "
                    "WHERE result->>'preparationDigest'=%s",
                    (prepared.digest,),
                ).fetchall()
                assert len(rows) == 1 and rows[0]["result"]["runId"] == prepared.run_id
                assert rows[0]["result"]["ownedBusiness"] == receipt["ownedBusiness"]
                assert (
                    c.execute(
                        "SELECT count(*) n FROM "
                        "execution_authority.native_dispatch_commands "
                        "WHERE state='UNKNOWN'"
                    ).fetchone()["n"]
                    == 0
                )
        else:
            for _ in prepared.participants:
                result = live.worker.run_once()
                with native.pool.connection() as detail_c:
                    diagnostics = detail_c.execute(
                        "SELECT state,terminal_record FROM "
                        "execution_authority.native_dispatch_commands"
                    ).fetchall()
                    invocations = detail_c.execute(
                        "SELECT kind,record FROM skill_invocation.facts"
                    ).fetchall()
                if result.state != "SUCCEEDED":
                    import json
                    from pathlib import Path

                    (
                        Path(__file__).resolve().parents[4]
                        / "native-failure-diagnostic.json"
                    ).write_text(
                        json.dumps(
                            {
                                "result": {
                                    "state": result.state,
                                    "commandId": result.command_id,
                                },
                                "errors": live.runner_errors + port_errors,
                                "dispatches": diagnostics,
                                "invocations": invocations,
                            },
                            default=str,
                            indent=2,
                        )
                    )
                assert result.state == "SUCCEEDED", (
                    result,
                    live.runner_errors,
                    diagnostics,
                    invocations,
                )
            assert live.worker.run_once().state == "IDLE"
            assert live.calls
        after = getattr(e, "assembly_after_execution", None)
        if after is not None:
            after(observed, worker, native, prepared, receipt)

        from agent_console.authority_contracts import GrantId
        from agent_console.grant_administration_application import (
            GrantRevocationCommand,
        )
        from agent_console.workbench_prepared_resources import reference

        automation = e.consumer_preparation_context[0]
        new_agent = observed["new_agent"]
        with native.pool.connection() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants "
                "WHERE owner='AGENT' AND action='READ_RESOURCE' "
                "AND exact_resource=%s AND subject_principal_id=%s",
                (
                    reference("agent", new_agent.resource_id, new_agent.revision_id),
                    e.context.principal_id,
                ),
            ).fetchone()["grant_id"]
        automation.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                GrantId(grant), "USER_REQUESTED", "surrender-new-role-read", True
            ),
        )
        with native.pool.connection() as c:
            before = c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            with pytest.raises(AuthorityError, match="READ_DENIED"):
                derive_work(
                    e.business_owner,
                    c,
                    e.context,
                    prepared_problem,
                    plan=observed["successor"],
                )
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_decisions"
                ).fetchone()["n"]
                == before
            )
        observed["hostAccepted"] = True

    e.consumer_execution_observer = inspect
    exercise(e, tmp_path, request)
    assert observed["hostAccepted"] is True
    assert e.business_owner.path.read_bytes() == policy_bytes
