"""Typed C1 over actual conversation/grant/budget owners, controlled model only."""

import copy
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from agent_console.context_call_admission import ContextCallAdmission
from agent_console.conversation_relation_context import (
    current_snapshot,
    sealed_snapshot,
)
from agent_console.conversation_typed_answer_policy import REVISION, SCHEMA_VERSION
from agent_console.draft_assistance import (
    DraftResultKind,
    ObservationState,
    PreparedProviderRequest,
    ProviderBudgetQuote,
    ProviderObservation,
)
from agent_console.draft_assistance_api import install_draft_assistance_routes
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.draft_provider_budget_postgres import (
    PostgresProviderCallBudget,
    _digest,
)
from agent_console.provider_profile_pricing import prepare_revision
from agent_console.understanding_adoption_admission import AdoptionExperience
from agent_console.workbench_bff import (
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from fastapi.testclient import TestClient
from test_local_accounts_postgres import login


@contextmanager
def typed_client(e, preparation, question, tmp_path, *, additional_installers=()):
    previous_service = e.adoption_client.app.state.understanding_adoption.routing
    previous = previous_service.authorization.context_admission
    service = copy.copy(previous_service)
    service.profile = replace(
        previous_service.profile,
        profile_revision_id="profile:typed-answer",
        profile_digest="7" * 64,
        maximum_output_tokens=previous.configuration["output_tokens"],
        adapter_revision=REVISION,
        output_schema_version=SCHEMA_VERSION,
    )
    config = {
        **previous.configuration,
        "profile_revision_id": service.profile.profile_revision_id,
        "profile_digest": service.profile.profile_digest,
        "configuration_digest": "8" * 64,
    }
    document = previous.experience.routing_document.model_dump(mode="json")
    document.update(
        configuration=config,
        predecessorRoutingPolicyDigest=previous.experience.understanding_policy_digest,
    )
    policy = tmp_path / "typed-admission.json"
    policy.write_text(json.dumps(document))
    policy.chmod(0o600)
    admission = ContextCallAdmission(e.admission.delegation, config)
    admission.experience = AdoptionExperience(e.admission, previous, policy, config)
    authorizer = e.draft.authorization.owner_authorization
    service.authorization = GrantAdministrationDraftAuthorization(
        e.admission.delegation.grants, authorizer
    )
    service.authorization.context_admission = admission
    e.admission.retained_conversation_relations = (
        previous,
        *e.admission.retained_conversation_relations,
    )
    e.admission.conversation_relation = admission
    with e.repo.connection_scope() as c:
        row = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE namespace=%s "
            "AND security_domain=%s AND ledger_id=%s",
            (preparation.namespace, preparation.security_domain, config["ledger_id"]),
        ).fetchone()
    assert row is not None
    original = row["record"]
    budget = PostgresProviderCallBudget(
        e.repo.pool.conninfo,
        migration_path=Path(__file__).parents[1]
        / "migrations/0024_draft_provider_budget.sql",
        profile=service.profile,
        ledger_id=config["ledger_id"],
        call_cap=original["callCap"],
        total_cost_cap_microusd=original["totalCostCapMicrousd"],
        input_price_microusd_per_million_tokens=original[
            "inputPriceMicrousdPerMillionTokens"
        ],
        output_price_microusd_per_million_tokens=original[
            "outputPriceMicrousdPerMillionTokens"
        ],
        profile_pricing_root_digest=_digest(original),
        allowance_id=e.admission.experience.document.allowanceId,
    )
    with budget._connection() as c:
        prepare_revision(c, budget)
    budget.migrate_and_configure()
    budget.context_admission = admission
    budget.delegation_configuration = config
    original_reserve = budget.reserve

    def reserve(*args, **kwargs):
        try:
            return original_reserve(*args, **kwargs)
        except Exception as exc:
            e.typed_budget_error = (type(exc).__name__, str(exc))
            raise

    budget.reserve = reserve
    service.budget = budget
    calls = []
    service.transport = copy.copy(previous_service.transport)

    original_prepare = service.transport.prepare

    def prepare(**kw):
        old = original_prepare(**kw)
        return PreparedProviderRequest(
            old.payload,
            ProviderBudgetQuote(10, service.profile.maximum_output_tokens, 0),
        )

    service.transport.prepare = prepare

    def dispatch(**kw):
        calls.append(kw["invocation_id"])
        snapshot = current_snapshot()
        return ProviderObservation(
            "typed:" + kw["invocation_id"],
            ObservationState.SUCCEEDED,
            correlation="controlled-typed",
            local_cleanup={"reaped": True},
            result_kind=DraftResultKind.CURRENT_QUESTION_ANSWER,
            input_tokens=10,
            output_tokens=20,
            conversation_route={
                "relation": "CURRENT_QUESTION",
                "contextDigest": snapshot["contextDigest"],
                "currentQuestionToken": snapshot["currentQuestionToken"],
                "questionAnswer": e.typed_meaning,
            },
        )

    service.transport.dispatch = dispatch
    app = create_workbench_bff(
        e.routing_sessions,
        authorizer,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(),
        conversation_database_url=e.repo.pool.conninfo,
        route_installers=(
            install_draft_assistance_routes(
                e.draft, service, retained_routing_services=(previous_service, e.route)
            ),
            *additional_installers,
        ),
    )
    records = app.state.conversation_actions.records

    def reader(context, conversation, message, *_):
        with records.connect() as c:
            records.owned(c, context, conversation)
            journal = c.execute(
                "SELECT version,state FROM private_conversation.journeys "
                "WHERE tenant_id=%s "
                "AND security_domain=%s AND conversation_id=%s",
                (*records.scope(context), conversation),
            ).fetchone()
        target = {
            "kind": "NATIVE",
            "invocationId": question["invocationId"],
            "questionKey": question["questionKey"],
            "questionDigest": question["questionDigest"],
            "executionDigest": preparation.digest,
            "runId": preparation.run_id,
            "expiresAt": question["expiresAt"],
            "journalVersion": journal["version"],
            "journeyKey": journal["state"]["key"],
            "problemId": preparation.semantics.target.problem.resource_id,
        }
        return sealed_snapshot(
            conversation,
            message,
            target,
            {
                "goal": "检查合成交接材料",
                "scope": "只读",
                "stage": "RUNNING",
                "currentQuestionType": "NATIVE",
                "currentQuestion": question["question"],
                "answerContract": question["answerContract"],
            },
        )

    app.state.conversation_relation_reader = reader
    secret = login(e.routing_sessions, "reviewer324")
    session, context = e.routing_sessions.authenticate_session(secret.value)
    headers = {
        "origin": "https://testserver",
        "x-csrf-token": e.routing_sessions.issue_csrf(session),
    }
    try:
        with TestClient(app, base_url="https://testserver") as client:
            client.cookies.set(SESSION_COOKIE, secret.value)
            yield client, headers, context, service, calls, authorizer
    finally:
        budget.close()
