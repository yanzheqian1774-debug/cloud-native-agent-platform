# ruff: noqa: F401,F811,E501 -- Isolated real authority/session BFF; candidate row is a fixture.
"""Actual BFF/PG grants distinguish historical ontology READ from expired USE."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS

from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import ExactGrant
from agent_console.grant_administration_application import (
    GrantDecisionCommand,
    GrantRequestCommand,
    GrantRevocationCommand,
)
from agent_console.native_progress_projection import projection_read_grants
from agent_console.ontology_execution import (
    DocumentRuleExecutionPreparation,
    DocumentSemanticsBinding,
)
from agent_console.prepared_execution_resources import resource_read_grants
from agent_console.workbench_bff import (
    PREFIX,
    SESSION_COOKIE,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_prepared_execution import prepared_execution_operations
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from test_context_call_admission import env
from test_conversation_experience_admission import pytestmark
from test_conversation_relation_bff import routed
from test_conversation_work_history import snapshot
from test_execution_preparation import preparation
from test_local_accounts_postgres import login
from test_owned_conversation_bff import ordinary
from test_recovery_bound_understanding import setup


def test_directory_ordinary_exact_reads_revocation_and_cross_domain(
    routed, monkeypatch
):
    from agent_console import workbench_current_work as directory
    from agent_console.execution_preparation import initial_progress
    from agent_console.workbench_current_work import operations
    from agent_console.workbench_pagination import WorkbenchCursorCodec
    from test_current_work_projection import setup as projection_fixture

    e = routed
    old = preparation()
    p = DocumentRuleExecutionPreparation.model_validate(
        {
            **old.model_dump(mode="json"),
            "namespace": e.reviewer.scope.tenant_id,
            "security_domain": e.reviewer.scope.security_domain,
            "schema_version": "execution-preparation.v3",
            "business_semantics": DocumentSemanticsBinding(
                ontology=old.source_snapshot,
                source=old.source_snapshot,
                mapping_code="interview",
                scope="interview",
            ).model_dump(mode="json"),
        }
    )
    # Canonical typed persisted candidate fixture; no claim that this test approved a plan.
    with e.repo.connection_scope() as c:
        c.execute(
            "CREATE TABLE execution_authority.prepared_candidates(namespace text,security_domain text,digest text,record jsonb,prepared_by text,PRIMARY KEY(namespace,security_domain,digest))"
        )
        c.execute(
            "INSERT INTO execution_authority.prepared_candidates VALUES(%s,%s,%s,%s,%s)",
            (
                p.namespace,
                p.security_domain,
                p.digest,
                Jsonb(p.model_dump(mode="json")),
                e.reviewer.principal_id,
            ),
        )
    _, row = projection_fixture(monkeypatch, state="SUCCEEDED")
    # Restore the real batch authorization function replaced by the row helper.
    from agent_console import workbench_current_work_projection as projection
    from agent_console.workbench_current_work_authorization import readable_grants

    monkeypatch.setattr(projection, "readable_grants", readable_grants)
    progress = initial_progress(p).model_copy(update={"state": "SUCCEEDED"})
    row.update(
        preparation=p.model_dump(mode="json"),
        digest=p.digest,
        workflow_run_id=p.run_id,
        progress=progress.model_dump(mode="json"),
        progress_version=progress.version,
        origins=[],
    )
    row["questions"][0].update(answered=True, answerDigest="a" * 64)
    monkeypatch.setattr(directory, "read_current_work_snapshot", lambda *a, **kw: [row])
    exact = {
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        ExactGrant(
            "BUSINESS_PROBLEM",
            "READ",
            "business-problem:" + p.semantics.target.problem.resource_id,
        ),
        *(
            ExactGrant("EXECUTION", action, "governed-execution:prepared:" + p.digest)
            for action in ("READ", "START")
        ),
    }
    for member in p.participants:
        exact.update(resource_read_grants(p, member))
        exact.update(projection_read_grants(p, member))
    ontology_read = next(
        g for g in exact if g.owner == "BUSINESS_ONTOLOGY" and g.action == "READ"
    )
    wrong_version = ExactGrant(
        ontology_read.owner,
        ontology_read.action,
        ontology_read.exact_resource + ":other",
    )
    exact.add(wrong_version)
    grants = e.admission.delegation.grants
    old_generation = grants.generation
    grants._generation_provider = lambda: replace(
        old_generation,
        requestability=(
            *old_generation.requestability,
            *(
                RequestabilityRule(
                    g.owner, g.action, g.exact_resource, "PROJECTION_TEST"
                )
                for g in exact
            ),
        ),
    )
    previous = grants.target_validator
    grants.target_validator = NS(
        is_known_exact_target=lambda ctx, g, **kwargs: (
            g in exact or previous.is_known_exact_target(ctx, g, **kwargs)
        )
    )
    requested = grants.submit_request(
        e.reviewer,
        GrantRequestCommand(
            "PROJECTION_TEST",
            tuple(sorted(exact, key=lambda g: (g.owner, g.action, g.exact_resource))),
            "projection-grants",
        ),
    )
    secret = login(e.routing_sessions, "devadmin")
    _, admin = e.routing_sessions.authenticate_session(secret.value)
    grants.decide_request(
        admin,
        GrantDecisionCommand(
            requested.request_id,
            True,
            "ISOLATED_READ",
            "TICKET",
            "controlled-candidate",
            None,
            datetime.now(UTC) + timedelta(hours=1),
            "projection-decision",
        ),
    )
    with e.repo.connection_scope() as c:
        c.execute(
            "UPDATE authorization_admin.grants SET not_before=now()-interval '9 hours',expires_at=now()-interval '1 hour' WHERE owner='BUSINESS_ONTOLOGY' AND action='USE'"
        )
    before = snapshot(e)
    app = create_workbench_bff(
        e.routing_sessions,
        e.draft.authorization.owner_authorization,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(
            *prepared_execution_operations(),
            *operations(WorkbenchCursorCodec(b"d" * 32)),
        ),
    )
    secret = login(e.routing_sessions, "reviewer324")
    session, _ = e.routing_sessions.authenticate_session(secret.value)
    with TestClient(app, base_url="https://testserver") as client:
        client.cookies.set(SESSION_COOKIE, secret.value)
        path = PREFIX + "/prepared-executions/" + p.digest
        directory_path = PREFIX + "/current-work?scopeFilter=visible"
        response = client.get(directory_path)
        assert response.status_code == 200, response.text
        value = response.json()["result"]
        assert value["answerHistoryComplete"] is True
        assert value["items"][0]["answeredQuestionCount"] == 1
        assert value["items"][0]["pendingQuestionCount"] == 0
        assert value["items"][0]["questionsDigest"]
        assert (
            client.get(directory_path + "&state=answered").json()["result"]["total"]
            == 1
        )
        response = client.get(path + "/native-progress")
        assert response.status_code == 200, response.text
        assert response.json()["result"]["runId"] == p.run_id
        response = client.post(
            path + "/native-answers",
            headers={
                "origin": "https://testserver",
                "x-csrf-token": e.routing_sessions.issue_csrf(session),
            },
            json={
                "invocationId": "original",
                "questionKey": "question",
                "questionDigest": "a" * 64,
                "conversationId": e.conv,
                "answer": "production",
            },
        )
        assert response.status_code in (403, 404), response.text
        assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
        assert snapshot(e) == before
        with e.repo.connection_scope() as c:
            grant_id = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE owner='BUSINESS_ONTOLOGY' AND action='READ' AND exact_resource=%s",
                (ontology_read.exact_resource,),
            ).fetchone()["grant_id"]
        grants.revoke_grant(
            e.reviewer,
            GrantRevocationCommand(
                grant_id, "USER_SURRENDER", "revoke-exact-read", surrender=True
            ),
        )
        response = client.get(path + "/native-progress")
        assert response.status_code in (403, 404), response.text
        assert response.json()["reasonCode"] == "AUTHORIZATION_NOT_FOUND"
        value = client.get(directory_path).json()["result"]
        assert value["total"] == 1  # Collection/run visibility stays independent.
        assert value["answerHistoryComplete"] is False
        assert value["items"][0]["answeredQuestionCount"] is None
        assert value["items"][0]["questionsDigest"] is None
        assert (
            client.get(directory_path + "&state=answered").json()["result"]["total"]
            == 0
        )
        # A foreign-scope stored session cannot inherit the original grants.
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE browser_identity.sessions SET security_domain='foreign' WHERE session_id=%s",
                (session.session_id,),
            )
        foreign = client.get(directory_path)
        assert foreign.status_code in (401, 403, 404), foreign.text
        # Active READ for another version cannot substitute for the original reference.
        assert snapshot(e) == before
    assert e.route_calls == [] and e.dispatches == []
