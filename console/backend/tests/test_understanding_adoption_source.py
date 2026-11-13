"""Real source READ grants/PG version validation; published content is a fixture."""

# ruff: noqa: F401,F811 -- Shared isolated database/session fixtures.
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.conversation_source_access import ConversationSourceAccess
from agent_console.conversation_source_input import source_reader
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
)
from agent_console.resource_automation_policy import source_digest
from agent_console.workbench_bff import PREFIX
from agent_console.workbench_prepared_resources import reference
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_local_accounts_postgres import login
from test_native_document_tools import SOURCE
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup
from test_understanding_adoption_bff import adopted, answer


def select(e):
    scope = e.context.scope
    published = getattr(e, "published_source", None)
    if published is None:
        ref = {
            "resource_id": "knowledge:adoption",
            "revision_id": "r1",
            "digest": "a" * 64,
        }
        raw = json.dumps(SOURCE)
        content = {
            "documents": [
                {
                    "contentDigest": sha256(raw.encode()).hexdigest(),
                    "chunks": [{"content": raw}],
                }
            ]
        }
        record = {
            "namespace": scope.tenant_id,
            "securityDomain": scope.security_domain,
            "knowledgeId": ref["resource_id"],
            "aggregateVersion": 1,
            "name": "Exact handover",
            "publishedRevisionId": "r1",
            "archived": False,
            "revisions": [
                {
                    "revisionId": "r1",
                    "digest": ref["digest"],
                    "state": "PUBLISHED",
                    "content": content,
                }
            ],
        }
        with e.repo.connection_scope() as c:
            c.execute(
                "INSERT INTO knowledge_operation.knowledge(namespace,security_domain,"
                "knowledge_id,aggregate_version,record) VALUES(%s,%s,%s,1,%s)",
                (
                    scope.tenant_id,
                    scope.security_domain,
                    ref["resource_id"],
                    Jsonb(record),
                ),
            )
    else:
        # Prepared by real lifecycle owners before any source message/result.
        ref, content = published["reference"], published["content"]
    members = (
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", ref["resource_id"], ref["revision_id"]),
        ),
    )
    grants = e.admission.delegation.grants
    generation = grants.generation
    grants._generation_provider = lambda: replace(
        generation,
        requestability=(
            *generation.requestability,
            *(
                RequestabilityRule(
                    g.owner, g.action, g.exact_resource, "RESOURCE_PREPARATION"
                )
                for g in members
            ),
        ),
    )
    previous = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda ctx, g, **kw: (
            g in members or previous.is_known_exact_target(ctx, g, **kw)
        )
    )
    pending = grants.submit_request(
        e.context, GrantRequestCommand("RESOURCE_PREPARATION", members, "source-read")
    )
    _, admin = e.routing_sessions.authenticate_session(
        login(e.routing_sessions, "devadmin").value
    )
    grants.decide_request(
        admin,
        GrantDecisionCommand(
            pending.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "source-fixture",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "source-decision",
        ),
    )
    app = e.adoption_client.app
    automation = NS(
        bound_app=lambda call: NS(
            scope=lambda p: NS(namespace=p.tenant_id, security_domain=p.security_domain)
        )
    )
    authorizer = e.draft.authorization.owner_authorization
    records = app.state.conversation_actions.records
    raw = source_reader(
        automation,
        authorizer,
        records,
        adoption=True,
        owned_access=ConversationSourceAccess(automation, authorizer, records, e.draft),
    )
    app.state.conversation_adoption_source_input = raw

    def metadata(*args, **kwargs):
        attachment = raw(*args, **kwargs)
        if attachment is None:
            return None
        value = json.loads(attachment)
        return {
            k: value[k]
            for k in ("source", "sourceContentDigest", "sourceSchema", "name")
        }

    app.state.understanding_adoption.source_reader = metadata
    journal = e.adoption_client.get(PREFIX + f"/conversations/{e.conv}/journey").json()[
        "result"
    ]
    journal["state"]["source"] = {
        "source": ref,
        "sourceContentDigest": source_digest(content),
    }
    result = e.adoption_client.post(
        PREFIX + f"/conversations/{e.conv}/journey",
        headers=e.adoption_headers,
        json={"expectedVersion": journal["version"], "state": journal["state"]},
    )
    assert result.status_code == 200, result.text
    return ref


@pytest.mark.parametrize("adopted", ["NEEDS_DATA", "READY_SOURCE"], indirect=True)
def test_explicit_authorized_source_supplement_is_exact_and_readback_only(adopted):
    e = adopted
    selected = select(e)
    path, value = answer(e)
    assert value["inputSource"]["source"] == selected
    from agent_console.draft_assistance import DraftScope

    recorded = e.draft.repository.get(
        DraftScope.from_context(e.context), value["invocationId"]
    )
    assert recorded.conversation_context["sourceInputBranch"] == {
        "currentQuestionType": "UNDERSTANDING",
        "hasCurrentQuestion": True,
    }
    assert "currentQuestion" not in recorded.conversation_context["sourceInputBranch"]
    result = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert result.status_code == 200, result.text
    assert (
        result.json()["result"]["adoption"]["sourceTransition"]
        == "EXPLICIT_AUTHORIZED_SUPPLEMENT"
    )
    refreshed = e.adoption_client.get(PREFIX + path, params={"requestKey": "answer"})
    assert refreshed.status_code == 200, refreshed.text
    assert len(e.calls) == 1


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
def test_source_changed_after_model_result_cannot_be_adopted(adopted):
    e = adopted
    selected = select(e)
    path, _ = answer(e)
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE knowledge_operation.knowledge SET "
            "record=jsonb_set(record,'{archived}','true') WHERE knowledge_id=%s",
            (selected["resource_id"],),
        )
    result = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert result.status_code == 409, result.text
    assert result.json()["reasonCode"] == "CONVERSATION_SOURCE_STALE_OR_UNREADABLE"
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_assistance.result_adoptions"
            ).fetchone()["n"]
            == 0
        )
    assert len(e.calls) == 1


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize("revoked", [False, True])
def test_actual_owned_source_adoption_reuses_transaction_and_keeps_read_gate(
    adopted, monkeypatch, revoked
):
    from contextlib import contextmanager

    from agent_console.grant_administration_application import GrantRevocationCommand

    e = adopted
    selected = select(
        e
    )  # Actual published owner record, current exact READ and access.
    from agent_console.draft_assistance import DraftResultKind

    e.kind = DraftResultKind.DRAFT_READY
    path, result = answer(e)
    assert result["state"] == "SUCCEEDED"
    app = e.adoption_client.app
    application = app.state.understanding_adoption
    metadata = application.source_reader
    connections = []
    held = []
    protected = e.draft.authorization.owner_authorization.controller.protected_request

    @contextmanager
    def generation_guard():
        with protected():
            held.append(True)
            try:
                yield
            finally:
                held.pop()

    application.source_transaction = generation_guard

    def observed(ctx, conversation, message, *, connection=None):
        assert (
            connection is not None
        )  # The actual adoption owner UoW, not another pool.
        connections.append(connection.info.backend_pid)
        return metadata(ctx, conversation, message, connection=connection)

    monkeypatch.setattr(application, "source_reader", observed)
    # Old nested-lock implementations fail boundedly instead of hanging the suite.
    repository = e.draft.authorization.owner_authorization.repository
    original_connection = repository.connection_scope

    @contextmanager
    def bounded(connection=None):
        with original_connection(connection) as c:
            c.execute("SET LOCAL statement_timeout='1500ms'")
            yield c

    monkeypatch.setattr(repository, "connection_scope", bounded)
    if revoked:
        grants = e.admission.delegation.grants
        with e.repo.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s AND owner='KNOWLEDGE' "
                "AND action='READ_RESOURCE' AND exact_resource=%s",
                (
                    e.context.principal_id,
                    reference(
                        "knowledge", selected["resource_id"], selected["revision_id"]
                    ),
                ),
            ).fetchone()
        grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                "source-adoption-withdrawal",
                surrender=True,
            ),
        )
    response = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert response.status_code == (403 if revoked else 200), response.text
    assert connections
    with e.repo.connection_scope() as c:
        count = c.execute(
            "SELECT count(*) n FROM draft_assistance.result_adoptions"
        ).fetchone()["n"]
        assert count == (0 if revoked else 1)
    if not revoked:
        replay = e.adoption_client.post(
            PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
        )
        assert replay.status_code == 200, replay.text
    assert len(e.calls) == len(e.initial_calls) == 1


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
def test_adoption_nested_source_read_completes_with_generation_writer_waiting(
    adopted, monkeypatch
):
    from contextlib import contextmanager
    from threading import Event, Thread, current_thread

    from agent_console.authority_foundation import ActivationBarrier

    e = adopted
    controller = e.draft.authorization.owner_authorization.controller
    original_protected = controller.protected_request
    barrier = ActivationBarrier(e.admission.delegation.grants.generation)
    waiting, entered = Event(), Event()
    original_wait = barrier._condition.wait

    def observe_wait(*args, **kwargs):
        if current_thread().name == "adoption-generation-writer":
            waiting.set()
        return original_wait(*args, **kwargs)

    monkeypatch.setattr(barrier._condition, "wait", observe_wait)

    @contextmanager
    def protected():
        with barrier.read() as generation, original_protected():
            yield generation

    monkeypatch.setattr(controller, "protected_request", protected)
    original_execute = ConversationSourceAccess.execute
    writers = []

    def write_generation():
        with barrier.write():
            entered.set()

    def execute(reader, context, conversation, handler, *, connection=None):
        if connection is not None and not writers:
            writer = Thread(
                target=write_generation, name="adoption-generation-writer", daemon=True
            )
            writers.append(writer)
            writer.start()
            assert waiting.wait(2), (
                "writer did not wait for outer owner generation read"
            )
            assert not entered.is_set()
            value = original_execute(
                reader, context, conversation, handler, connection=connection
            )
            assert not entered.is_set(), (
                "writer entered before owner transaction finished"
            )
            return value
        return original_execute(
            reader, context, conversation, handler, connection=connection
        )

    monkeypatch.setattr(ConversationSourceAccess, "execute", execute)
    test_actual_owned_source_adoption_reuses_transaction_and_keeps_read_gate(
        e, monkeypatch, False
    )
    assert len(writers) == 1
    writers[0].join(2)
    assert not writers[0].is_alive() and entered.is_set()


@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize("legacy", [True, False])
def test_branch_metadata_legacy_adoption_and_changed_branch_rejection(
    adopted, monkeypatch, legacy
):
    from agent_console import conversation_relation_context as relation

    e = adopted
    select(e)
    if legacy:
        monkeypatch.setattr(
            relation,
            "current_metadata",
            lambda: relation.metadata_for_snapshot(
                relation.current_snapshot(), include_source_branch=False
            ),
        )
    path, _ = answer(e)
    application = e.adoption_client.app.state.understanding_adoption
    if not legacy:
        reader = application.reader

        def changed(*args, **kwargs):
            snapshot = reader(*args, **kwargs)
            return {**snapshot, "input": {**snapshot["input"], "currentQuestion": ""}}

        monkeypatch.setattr(application, "reader", changed)
    result = e.adoption_client.post(
        PREFIX + path, headers=e.adoption_headers, json={"requestKey": "answer"}
    )
    assert result.status_code == (200 if legacy else 409), result.text
    if not legacy:
        assert result.json()["reasonCode"] == "UNDERSTANDING_ADOPTION_QUESTION_CHANGED"
    assert len(e.calls) == 1
