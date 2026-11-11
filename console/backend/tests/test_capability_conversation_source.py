"""Capability preparation requires the actual exact published owner reference."""

import pytest
import test_workbench_business_capability_postgres as capability_fixture
from agent_console.private_conversation_api import SourceReference
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_business_capability_publication_postgres import (
    access,
    command,
    path_for,
    publish_employee,
)
from test_workbench_business_capability_postgres import (
    PREFIX,
    member_grant,
    setup,
)
from test_workbench_team_postgres import allow

app = capability_fixture.app


def test_capability_source_is_strictly_typed():
    source = {
        "kind": "CAPABILITY",
        "target": {
            "capabilityId": "cap",
            "revisionId": "rev",
            "digest": "a" * 64,
            "objective": "Check handover",
            "inputNotes": "Confirmed source document",
        },
    }
    assert (
        SourceReference.model_validate(source).model_dump(exclude_none=True) == source
    )
    for field in ("capabilityId", "revisionId", "digest", "objective", "inputNotes"):
        with pytest.raises(ValidationError):
            SourceReference.model_validate(
                {
                    "kind": "CAPABILITY",
                    "target": {
                        key: value
                        for key, value in source["target"].items()
                        if key != field
                    },
                }
            )
    with pytest.raises(ValidationError):
        SourceReference.model_validate({**source, "invocationId": "not-an-invocation"})


def test_published_capability_source_persists_once_and_rechecks_access(app):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        member_grant(app, employee)
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "create-cap",
        )
        assert client.post(PREFIX, json=body, headers=headers).status_code == 201
        access(app, body)
        capability = client.get(path_for(body)).json()["result"]
        assert capability["members"][0]["name"] == "Quality owner"
        created = client.post(
            "/api/workbench/v1/conversations",
            json={
                "idempotencyKey": "cap-source-conversation",
                "title": "Document review",
            },
            headers=headers,
        )
        assert created.status_code == 200, created.text
        conversation = created.json()["result"]["conversation_id"]
        route = "/api/workbench/v1/conversations/" + conversation
        source = {
            "idempotencyKey": "cap-source",
            "expectedVersion": 0,
            "source": {
                "kind": "CAPABILITY",
                "target": {
                    "capabilityId": body["revision"]["capability_id"],
                    "revisionId": body["revision"]["revision_id"],
                    "digest": capability["digest"],
                    "objective": "Check original handover",
                    "inputNotes": "Use confirmed documents only",
                },
            },
        }
        assert (
            client.post(route + "/sources", json=source, headers=headers).status_code
            == 409
        )
        publish_employee(app, client, employee, headers)
        preview = client.get(path_for(body) + "/publication-preview").json()["result"]
        access(app, body, "REVIEW_PUBLISH", "publish-cap")
        assert (
            client.post(
                path_for(body) + "/publication",
                json=command(preview, "publish-for-source"),
                headers=headers,
            ).status_code
            == 201
        )
        assert client.post(route + "/sources", json=source).status_code == 403
        first = client.post(route + "/sources", json=source, headers=headers)
        assert first.status_code == 200, first.text
        again = client.post(route + "/sources", json=source, headers=headers)
        assert again.status_code == 200 and again.json()["result"]["replayed"]
        stored = client.get(route).json()["result"]
        assert len(stored["messages"]) == 1
        facts = stored["messages"][0]["facts"]
        assert facts["source"] == source["source"]
        assert facts["observation"]["state"] == "PREPARED_NOT_EXECUTED"
        assert facts["observation"]["receiptState"] == "NOT_STARTED"
        assert facts["observation"]["executionAuthorized"] is False
        assert (
            facts["observation"]["capability"]["bindings"]
            == body["revision"]["bindings"]
        )
        message_id = first.json()["result"]["identity"]
        contract_route = route + "/sources/" + message_id + "/execution-contract"
        resolved = client.get(contract_route)
        assert resolved.status_code == 200, resolved.text
        result = resolved.json()["result"]
        assert result["admissionState"] == "NOT_ADMITTED"
        assert result["executionAuthorized"] is False
        assert result["executionStarted"] is False
        contract = result["contract"]
        assert contract["conversationId"] == conversation
        assert contract["sourceMessageId"] == message_id
        assert contract["capability"]["digest"] == capability["digest"]
        assert contract["objective"] == source["source"]["target"]["objective"]
        assert contract["acceptanceCriteria"] == body["revision"]["acceptance_criteria"]
        assert contract["bindings"] == body["revision"]["bindings"]
        from agent_console.business_problem_domain import (
            CriterionType,
            validate_measurement,
        )
        from agent_console.business_problem_schemas import (
            CreateBusinessProblem,
            CreateCriterionRevision,
        )

        prepared = result["workInput"]
        CreateBusinessProblem.model_validate(
            {**prepared["problem"], "ownerId": "owner", "idempotencyKey": "work"}
        )
        criterion = CreateCriterionRevision.model_validate(
            {**prepared["criterion"], "idempotencyKey": "criterion"}
        )
        validate_measurement(CriterionType.HUMAN_EVALUATED, criterion.measurement)
        assert criterion.applicability["capabilityConstraints"] == contract
        from agent_console.private_conversation import digest

        assert result["contractDigest"] == digest(contract)
        assert client.get(contract_route).json()["result"] == result
        journal_route = route + "/sources/" + message_id + "/journey"
        assert client.get(journal_route).json()["result"]["version"] == 0
        legacy = {"expectedVersion": 0, "state": {"phase": "DONE", "key": "original"}}
        assert (
            client.post(route + "/journey", json=legacy, headers=headers).status_code
            == 200
        )
        journal_body = {
            "expectedVersion": 0,
            "idempotencyKey": "capability-journal",
            "contractDigest": result["contractDigest"],
            "state": {"phase": "PREPARE_PLAN"},
        }
        assert client.post(journal_route, json=journal_body).status_code == 403
        stored_journal = client.post(journal_route, json=journal_body, headers=headers)
        assert stored_journal.status_code == 200, stored_journal.text
        assert stored_journal.json()["result"]["version"] == 1
        assert client.post(journal_route, json=journal_body, headers=headers).json()[
            "result"
        ]["replayed"]
        for changed in (
            {**journal_body, "state": {"phase": "EXECUTE"}},
            {**journal_body, "idempotencyKey": "stale-journal"},
            {**journal_body, "contractDigest": "0" * 64},
        ):
            assert (
                client.post(journal_route, json=changed, headers=headers).status_code
                == 409
            )
        assert (
            client.get(journal_route).json()["result"]["state"] == journal_body["state"]
        )
        assert (
            client.get(route + "/journey").json()["result"]["state"] == legacy["state"]
        )
        from agent_console.authority_contracts import ExactGrant
        from agent_console.workbench_bff import SESSION_COOKIE

        _, context = app.application.state.test_sessions.authenticate_session(
            client.cookies.get(SESSION_COOKIE)
        )

        def inside_owner(call):
            call.connection.execute("SET LOCAL lock_timeout='2s'")
            return app.application.state.capability_execution_contract_reader(
                call, conversation, message_id
            )

        assert (
            app.application.state.test_authorizer.execute(
                context,
                (
                    ExactGrant(
                        "BUSINESS_CAPABILITY",
                        "READ",
                        "business-capability:"
                        + contract["capability"]["resource_id"]
                        + ":"
                        + contract["capability"]["revision_id"],
                    ),
                ),
                operation="VERIFY_FIXED_CAPABILITY_IN_EXISTING_OWNER",
                payload={},
                path={},
                query={},
                handler=inside_owner,
            )
            == result
        )
        other = client.post(
            "/api/workbench/v1/conversations",
            json={"idempotencyKey": "other-cap-source", "title": "Other conversation"},
            headers=headers,
        ).json()["result"]["conversation_id"]
        assert (
            client.get(
                "/api/workbench/v1/conversations/"
                + other
                + "/sources/"
                + message_id
                + "/execution-contract"
            ).status_code
            == 404
        )
        assert len(client.get(route).json()["result"]["messages"]) == 1
        with app.authority.connection_scope() as connection:
            assert (
                connection.execute(
                    "SELECT count(*) n FROM private_conversation.action_intents"
                ).fetchone()["n"]
                == 0
            )
        intent_body = {
            "idempotencyKey": "create-from-saved-capability",
            "expectedVersion": 1,
            "messageId": message_id,
            "action": "CREATE_PROBLEM",
            "payload": {
                **prepared["problem"],
                "ownerId": context.principal_id,
                "idempotencyKey": "capability-problem",
            },
            "source": source["source"],
            "expectedOwnerVersion": 0,
            "confirmed": True,
        }
        from copy import deepcopy

        for mode in ("input", "message", "conversation", "source"):
            invalid = deepcopy(intent_body)
            target_route = route
            if mode == "input":
                invalid["payload"]["description"] = "Substituted target"
            elif mode == "message":
                invalid["messageId"] = "missing"
            elif mode == "conversation":
                target_route = "/api/workbench/v1/conversations/" + other
                invalid["expectedVersion"] = 0
            else:
                invalid["source"]["target"]["inputNotes"] = "Unsaved notes"
            assert client.post(
                target_route + "/intents", json=invalid, headers=headers
            ).status_code in {404, 409}
        saved_intent = client.post(
            route + "/intents", json=intent_body, headers=headers
        )
        assert saved_intent.status_code == 200, saved_intent.text
        replay = client.post(route + "/intents", json=intent_body, headers=headers)
        assert (
            replay.status_code == 200
            and replay.json()["result"]["intentId"]
            == saved_intent.json()["result"]["intentId"]
        )
        other_journal = journal_route.replace(conversation, other)
        assert client.get(other_journal).status_code == 404
        assert (
            client.post(other_journal, json=journal_body, headers=headers).status_code
            == 404
        )
        second_source = {
            **source,
            "idempotencyKey": "second-cap-source",
            "expectedVersion": client.get(route).json()["result"]["conversation"][
                "version"
            ],
        }
        second = client.post(route + "/sources", json=second_source, headers=headers)
        assert second.status_code == 200, second.text
        second_message = second.json()["result"]["identity"]
        second_route = route + "/sources/" + second_message
        second_contract = client.get(second_route + "/execution-contract").json()[
            "result"
        ]
        second_body = {
            **journal_body,
            "contractDigest": second_contract["contractDigest"],
            "state": {"phase": "PREPARE_PLAN", "work": "second"},
        }
        response = client.post(
            second_route + "/journey", json=second_body, headers=headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["version"] == 1
        next_body = {
            **journal_body,
            "expectedVersion": 1,
            "idempotencyKey": "next-journal",
            "state": {"phase": "PREPARE_PLAN", "work": "first-updated"},
        }
        updated = client.post(journal_route, json=next_body, headers=headers)
        assert updated.status_code == 200, updated.text
        assert updated.json()["result"]["version"] == 2
        assert (
            client.get(second_route + "/journey").json()["result"]["state"]
            == second_body["state"]
        )
        assert client.get(journal_route).json()["result"]["state"] == next_body["state"]
        assert (
            client.get(route + "/journey").json()["result"]["state"] == legacy["state"]
        )
        from psycopg.errors import RaiseException

        with app.authority.connection_scope() as connection:
            rows = connection.execute(
                "SELECT version,state "
                "FROM private_conversation.capability_work_journal "
                "WHERE source_message_id=%s ORDER BY version",
                (message_id,),
            ).fetchall()
            assert [row["version"] for row in rows] == [1, 2]
            assert rows[0]["state"] == journal_body["state"]
            with (
                pytest.raises(RaiseException, match="CAPABILITY_JOURNAL_IMMUTABLE"),
                connection.transaction(),
            ):
                connection.execute(
                    "DELETE FROM private_conversation.capability_work_journal"
                )
        with app.authority.connection_scope() as connection:
            intent_row = connection.execute(
                "SELECT * FROM private_conversation.action_intents"
            ).fetchone()
            assert intent_row["message_id"] == message_id
            assert intent_row["source"] == source["source"]
            assert intent_row["owner_ref"] is None
            assert intent_row["claimed_at"] is None
            connection.execute(
                "DELETE FROM authorization_admin.effective_grants "
                "WHERE owner='EMPLOYEE'"
            )
        assert (
            client.post(route + "/sources", json=source, headers=headers).status_code
            == 404
        )
        assert client.get(contract_route).status_code == 404
        assert client.get(journal_route).status_code == 404
        assert (
            client.post(journal_route, json=journal_body, headers=headers).status_code
            == 404
        )
        from agent_console.authority_contracts import AuthorityError
        from agent_console.workbench_owner_authorization import WorkbenchOwnerError

        with pytest.raises((AuthorityError, WorkbenchOwnerError)):
            app.application.state.conversation_actions.claim(
                context,
                conversation,
                saved_intent.json()["result"]["intentId"],
                "CREATE_PROBLEM",
                intent_body["payload"],
            )
        with app.authority.connection_scope() as connection:
            row = connection.execute(
                "SELECT claimed_at,owner_ref FROM private_conversation.action_intents"
            ).fetchone()
            assert row["claimed_at"] is None and row["owner_ref"] is None
        withdrawn = client.get(route).json()["result"]["messages"][0]
        assert withdrawn["facts"] == {"readable": False}
        assert "Check original handover" not in str(withdrawn)
