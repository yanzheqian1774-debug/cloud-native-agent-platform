"""Same isolated document7 source, real C1/grant/budget/BFF owners.

Only model catalog resolution and provider response are controlled. No synthetic
C1 record, settlement or retained assistant fact is inserted by this helper.
"""

# ruff: noqa: E501,RUF001
import json
from contextlib import ExitStack
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_experience_admission import (
    LEDGER,
    ConversationExperienceAdmission,
)
from agent_console.conversation_relation_context import current_snapshot
from agent_console.conversation_typed_answer_policy import REVISION, SCHEMA_VERSION
from agent_console.draft_assistance import (
    DraftResultKind,
    DraftScope,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    DraftAssistanceGrantTargetValidator,
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_assistance_support import ExactProfileModelResolver
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.fixed_chat_api import install_fixed_chat
from agent_console.fixed_question_startup import configure as configure_question_startup
from agent_console.grant_administration_application import GrantDecisionCommand
from agent_console.model_binding_resolution import ModelConsumptionScope
from agent_console.model_governance import ModelScope
from agent_console.provider_profile_pricing import prepare_revision
from agent_console.task_delegation import TaskDelegationService, digest
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from fastapi.testclient import TestClient
from test_draft_assistance_postgres import _resolved, _service


def answer(a, live, native, work, presented):
    scope = DraftScope(a.e.scope.namespace, a.e.scope.security_domain)
    with ExitStack() as stack:
        with a.repository.pool.connection() as c:
            c.execute(
                (
                    Path(__file__).parents[1]
                    / "migrations/0047_conversation_action_facts.sql"
                ).read_text()
            )
        service, repository, uses, evidence, transport = _service(
            a.repository.pool.conninfo
        )
        for owner in (repository, uses, evidence):
            stack.callback(owner.close)
        service.clock = lambda: datetime.now(UTC)
        service.profile = replace(
            service.profile,
            scope=scope,
            profile_revision_id="document7-c1-typed",
            profile_digest="7" * 64,
            adapter_revision=REVISION,
            output_schema_version=SCHEMA_VERSION,
        )
        resolved = _resolved()
        service.model_resolver = ExactProfileModelResolver(
            replace(
                resolved,
                scope=ModelConsumptionScope(scope.namespace, scope.security_domain),
                eligibility=replace(
                    resolved.eligibility,
                    scope=ModelScope(scope.namespace, scope.security_domain),
                ),
            )
        )
        # Use the exact persisted planning ledger and its original total cap.
        with a.repository.pool.connection() as c:
            root = c.execute(
                "SELECT record FROM draft_provider_budget.policies WHERE namespace=%s AND security_domain=%s AND ledger_id=%s",
                (scope.namespace, scope.security_domain, LEDGER),
            ).fetchone()["record"]
        budget = PostgresProviderCallBudget(
            a.repository.pool.conninfo,
            migration_path=Path(__file__).parents[1]
            / "migrations/0024_draft_provider_budget.sql",
            profile=service.profile,
            ledger_id=root["ledgerId"],
            call_cap=root["callCap"],
            total_cost_cap_microusd=root["totalCostCapMicrousd"],
            input_price_microusd_per_million_tokens=root[
                "inputPriceMicrousdPerMillionTokens"
            ],
            output_price_microusd_per_million_tokens=root[
                "outputPriceMicrousdPerMillionTokens"
            ],
            profile_pricing_root_digest=_digest(root),
        )
        stack.callback(budget.close)
        with budget._connection() as c:
            prepare_revision(c, budget)
        budget.migrate_and_configure()
        service.budget = budget
        service.authorization = GrantAdministrationDraftAuthorization(
            a.automation.grants, a.adapter
        )
        configuration = dict(
            ledger_id=LEDGER,
            configuration_digest="8" * 64,
            profile_revision_id=service.profile.profile_revision_id,
            profile_digest=service.profile.profile_digest,
            model_target=service.profile.binding.resource_id,
            calls=20,
            input_tokens=100000,
            output_tokens=service.profile.maximum_output_tokens,
            cost_microusd=1_000_000,
        )
        delegation = TaskDelegationService(
            a.automation.grants, {"understanding": configuration}
        )
        delegation.migrate()
        admission = ContextCallAdmission(delegation, configuration)
        # The original BOUND provenance fixture applied the exact 0037 DDL
        # before creating its retained admission; do not apply it twice.
        with a.repository.pool.connection() as c:
            assert c.execute(
                "SELECT to_regclass('authorization_admin.context_call_requests') t"
            ).fetchone()["t"]
        document = dict(
            schemaVersion="f3-conversation-experience.v1",
            tenantId=scope.namespace,
            securityDomain=scope.security_domain,
            subjectId=presented.context.principal_id,
            accountId="local-account:reviewer324",
            authorizationDigest="a" * 64,
            configuration=configuration,
            conversations={
                presented.presentation.identity.conversationId: "SYNTHETIC_DOCUMENT_REVIEW"
            },
            externalWrites=False,
        )
        predecessor = digest(document)
        document.update(
            schemaVersion="f3-conversation-experience.v3",
            ownedConversationUnderstanding=True,
            predecessorSchemaVersion="f3-conversation-experience.v1",
            predecessorPolicyDigest=predecessor,
        )
        directory = Path(stack.enter_context(TemporaryDirectory()))
        policy_path = directory / "experience.json"
        policy_path.write_text(json.dumps(document))
        policy_path.chmod(0o600)
        admission.experience = ConversationExperienceAdmission(
            policy_path, configuration
        )
        service.authorization.context_admission = admission
        budget.context_admission = admission
        budget.delegation_configuration = configuration
        targets = a.automation.grants.target_validator
        targets.additional = (
            *targets.additional,
            DraftAssistanceGrantTargetValidator(repository),
        )
        calls = []
        prepare = transport.prepare

        def prepared(**kw):
            old = prepare(**kw)
            return PreparedProviderRequest(
                old.payload,
                ProviderBudgetQuote(10, service.profile.maximum_output_tokens, 0),
            )

        transport.prepare = prepared

        def dispatch(**kw):
            calls.append(kw["invocation_id"])
            snapshot = current_snapshot()
            contract = presented.presentation.question["answerContract"]
            return ProviderObservation(
                "typed:" + kw["invocation_id"],
                ObservationState.SUCCEEDED,
                correlation="controlled-document7-c1",
                local_cleanup={"reaped": True},
                result_kind=DraftResultKind.CURRENT_QUESTION_ANSWER,
                input_tokens=10,
                output_tokens=20,
                conversation_route=dict(
                    relation="CURRENT_QUESTION",
                    contextDigest=snapshot["contextDigest"],
                    currentQuestionToken=snapshot["currentQuestionToken"],
                    questionAnswer=dict(
                        decision="CONFIRM",
                        candidateId=contract["proposedCandidateId"],
                        questionContractDigest=contract["contractDigest"],
                    ),
                ),
            )

        transport.dispatch = dispatch
        policy = live.runtime.bound_service_execution.registry._policy()
        live.runtime.subject = policy.subjectId
        live.runtime.service_credential_id = policy.credentialId
        # Exercise the real opt-in startup selector with the already constructed
        # original service leaf. Only P1 factory construction is controlled here;
        # registry, typed7 runtime, settlement owner and composition are real.
        import hashlib
        from types import SimpleNamespace as NS

        def pinned(name, value):
            path = directory / name
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            return {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

        question_pin = pinned(
            "question-policy.json", presented.policy.model_dump(mode="json")
        )
        set_pin = pinned(
            "policy-set.json", {"controlledFactory": "existing-original-leaf"}
        )
        startup_pin = pinned(
            "question-startup.json",
            {
                "schemaVersion": "fixed-question-startup.v1",
                "enabled": True,
                "questionPolicy": question_pin,
                "policySetConfiguration": set_pin,
                "servicePolicyDigest": policy.digest,
            },
        )
        constructed, selected, closed = [], [], []

        def select(scope, *, credential_id, policy_digest):
            assert scope == (policy.tenantId, policy.securityDomain)
            assert (
                credential_id == policy.credentialId and policy_digest == policy.digest
            )
            selected.append(scope)
            return NS(runtime=live.runtime, work=work, execution_repository=native)

        def factory(path, _environment):
            assert path == set_pin["path"]
            constructed.append(path)
            return NS(service_leaf=select, close=lambda: closed.append(True))

        started = configure_question_startup(
            {
                "FIXED_QUESTION_DELEGATION_CONFIGURATION": startup_pin["path"],
                "FIXED_QUESTION_DELEGATION_CONFIGURATION_SHA256": startup_pin["sha256"],
            },
            (service,),
            factory=factory,
        )
        assert len(constructed) == len(selected) == 1
        stack.callback(started.close)
        composition = started.composition
        app = create_workbench_bff(
            presented.sessions,
            a.adapter,
            WorkbenchBffPolicy("testserver", "https://testserver"),
            operations=(),
            conversation_database_url=a.repository.pool.conninfo,
            route_installers=(
                install_draft_assistance_routes(service, service),
                install_fixed_chat(
                    presented.read_policy,
                    a.adapter,
                    a.automation,
                    presented.delivery.cursors,
                    question_composition=composition,
                ),
            ),
        )
        app.state.conversation_relation_reader = lambda ctx, chat, message, *_: (
            app.state.fixed_question_reader.read(
                ctx, chat, message_id=message, current=True
            )[1]
        )
        session, context = presented.sessions.authenticate_session(
            presented.secret.value
        )
        headers = {
            "origin": "https://testserver",
            "x-csrf-token": presented.sessions.issue_csrf(session),
        }
        client = stack.enter_context(TestClient(app, base_url="https://testserver"))
        client.cookies.set(SESSION_COOKIE, presented.secret.value)
        p = presented.presentation
        chat = p.identity.conversationId
        head = client.get(PREFIX + f"/conversations/{chat}/head").json()["result"][
            "conversation"
        ]
        text = "确认按该规范检查这份材料，不执行上线或回退。"
        saved = client.post(
            PREFIX + f"/conversations/{chat}/messages",
            headers=headers,
            json=dict(
                content=text,
                expectedVersion=head["version"],
                idempotencyKey="document7-answer",
                focusLinkId=p.focusLinkId,
            ),
        )
        assert saved.status_code == 200, saved.text
        message = saved.json()["result"]["identity"]
        payload = dict(
            content=text,
            idempotencyKey="document7-c1",
            conversationId=chat,
            conversationMessageId=message,
            conversationRouting=True,
        )
        approved = set()
        for _ in range(3):
            response = client.post(
                PREFIX + "/draft-assistance/invocations", headers=headers, json=payload
            )
            assert response.status_code in (200, 201), response.text
            result = response.json()["result"]
            if result["state"] == "SUCCEEDED":
                break
            invocation = repository.get(scope, result["invocationId"])
            auth = invocation.authorization
            issuer = a.automation.authenticate(context)
            for request_id in (
                auth.request_authorization_request_id,
                auth.model_authorization_request_id,
            ):
                if request_id and request_id not in approved:
                    a.automation.grants.decide_request(
                        issuer,
                        GrantDecisionCommand(
                            request_id,
                            True,
                            "ASSIGNED_BUSINESS_DUTY",
                            "TICKET",
                            "isolated-document7-answer",
                            None,
                            datetime.now(UTC) + timedelta(minutes=10),
                            "approve:" + request_id,
                            expected_version=1,
                        ),
                    )
                    approved.add(request_id)
        assert result["state"] == "SUCCEEDED", result
        assert result["conversationDelivery"]["state"] == "SAVED", result
        assert len(calls) == 1
        body = dict(
            presentationId=p.presentationId,
            presentationDigest=p.digest,
            messageId=message,
            requestKey="document7-c1",
            commandId="document7-answer-command",
        )
        path = PREFIX + f"/conversations/{chat}/fixed-work-activity/questions/answers"
        for invalid in (
            {**body, "presentationDigest": "0" * 64},
            {**body, "messageId": "missing-message"},
            {**body, "requestKey": "not-the-saved-c1"},
        ):
            denied = client.post(path, headers=headers, json=invalid)
            assert denied.status_code in (400, 403, 404, 409), denied.text
            with a.authority.connection_scope() as c:
                assert (
                    c.execute(
                        "SELECT count(*) n FROM fixed_question.answers"
                    ).fetchone()["n"]
                    == 0
                )
            assert len(calls) == 1
        response = client.post(path, headers=headers, json=body)
        assert response.status_code == 200, response.text
        first = response.json()["result"]
        again = client.post(path, headers=headers, json=body)
        assert again.status_code == 200, again.text
        assert again.json()["result"]["receiptDigest"] == first["receiptDigest"]
        recovered = client.get(
            path,
            params={"presentationId": p.presentationId, "commandId": body["commandId"]},
        )
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["result"]["receiptDigest"] == first["receiptDigest"]
        conflict = client.post(
            path, headers=headers, json={**body, "commandId": "cannot-answer-again"}
        )
        assert conflict.status_code == 404, conflict.text
        assert conflict.json()["reasonCode"] == "FIXED_QUESTION_FACT_BINDING_INVALID"
        with a.authority.connection_scope() as c:
            assert (
                c.execute("SELECT count(*) n FROM fixed_question.answers").fetchone()[
                    "n"
                ]
                == 1
            )
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE subject_principal_id=%s AND owner='EXECUTION' AND action='QUESTION_ANSWER'",
                (context.principal_id,),
            ).fetchone()
        from agent_console.grant_administration_application import (
            GrantRevocationCommand,
        )

        a.automation.grants.revoke_grant(
            context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "document7-withdraw-answer",
                surrender=True,
            ),
        )
        revoked = client.post(path, headers=headers, json=body)
        assert revoked.status_code in (403, 404, 409), revoked.text
        assert len(calls) == 1
        return first
