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
    ref = {"resource_id": "knowledge:adoption", "revision_id": "r1", "digest": "a" * 64}
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
            (scope.tenant_id, scope.security_domain, ref["resource_id"], Jsonb(record)),
        )
    members = (
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        ExactGrant(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference("knowledge", ref["resource_id"], "r1"),
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
    raw = source_reader(
        NS(
            bound_app=lambda call: NS(
                scope=lambda p: NS(
                    namespace=p.tenant_id, security_domain=p.security_domain
                )
            )
        ),
        e.draft.authorization.owner_authorization,
        app.state.conversation_actions.records,
        adoption=True,
    )
    app.state.conversation_adoption_source_input = raw

    def metadata(*args):
        attachment = raw(*args)
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
