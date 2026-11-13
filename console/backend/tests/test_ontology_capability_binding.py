# ruff: noqa: F401,F811 -- Reuse existing isolated browser/database fixture.
from copy import deepcopy
from types import SimpleNamespace

import psycopg
import pytest
from agent_console.ontology_capability_binding import (
    document_binding,
    require_work_binding,
)
from agent_console.ontology_domain import OntologyCommand
from agent_console.ontology_execution import DocumentSemanticsBinding
from agent_console.ontology_postgres import PostgresOntologyRepository, migrate
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from fastapi.testclient import TestClient
from test_capability_execution_constraints import fixture
from test_document_rule_owner import rules
from test_workbench_business_capability_postgres import PREFIX, app, member_grant, setup
from test_workbench_team_postgres import allow


def seed(app, scope):
    with psycopg.connect(app.database_url) as c:
        migrate(c)
        repo = PostgresOntologyRepository(c)
        value = repo.command(
            scope,
            "human:author",
            "rules",
            "CREATE",
            OntologyCommand(
                request_key="create",
                expected_version=0,
                revision_id="r1",
                content=rules(),
                reason="isolated fixture",
            ),
        )
        for action in ("VALIDATE", "TEST", "REVIEW", "PUBLISH"):
            value = repo.command(
                scope,
                "human:reviewer" if action == "REVIEW" else "human:author",
                "rules",
                action,
                OntologyCommand(
                    request_key=action,
                    expected_version=value["version"],
                    revision_id="r1",
                    digest=value["digest"],
                    reason="isolated fixture",
                ),
            )
        return value


def test_capability_owner_reads_exact_published_ontology_without_adding_employee_member(
    app,
):
    with TestClient(app.application, base_url="https://console.example") as client:
        headers, employee, body = setup(client, app)
        scope = body["revision"]["scope"]
        value = seed(app, (scope["namespace"], scope["security_domain"]))
        ref = {"resource_id": "rules", "revision_id": "r1", "digest": value["digest"]}
        body["revision"]["bindings"].append(
            {"kind": "ONTOLOGY", "reference": ref, "purpose": "核对固定规则"}
        )
        allow(
            app,
            "BUSINESS_CAPABILITY",
            "CREATE",
            "business-capability:collection",
            "create-cap",
        )
        member_grant(app, employee)
        assert client.post(PREFIX, json=body, headers=headers).status_code == 404
        allow(
            app, "BUSINESS_ONTOLOGY", "READ", "business-ontology:rules:r1", "read-rule"
        )
        bad = deepcopy(body)
        bad["revision"]["bindings"][-1]["reference"]["digest"] = "f" * 64
        assert client.post(PREFIX, json=bad, headers=headers).status_code == 409
        saved = client.post(PREFIX, json=body, headers=headers)
        assert saved.status_code == 201, saved.text
        assert saved.json()["result"]["executionAuthorized"] is False
        with psycopg.connect(app.database_url) as c:
            repo = PostgresOntologyRepository(c)
            repo.command(
                (scope["namespace"], scope["security_domain"]),
                "human:author",
                "rules",
                "DEPRECATE",
                OntologyCommand(
                    request_key="deprecated",
                    expected_version=value["version"],
                    revision_id="r1",
                    digest=value["digest"],
                    reason="isolated fixture",
                ),
            )
        # Save/replay rechecks publication; old stored capability remains immutable.
        assert client.post(PREFIX, json=body, headers=headers).status_code == 409


def test_execution_constraint_requires_independent_verified_semantic_binding():
    from agent_console.capability_execution_constraints import verify_resources

    resolved, _, _, ready = fixture()
    ontology = {"resource_id": "rules", "revision_id": "r1", "digest": "b" * 64}
    source = {"resource_id": "source", "revision_id": "r1", "digest": "a" * 64}
    resolved["contract"]["bindings"].append({"kind": "ONTOLOGY", "reference": ontology})
    selected = DocumentSemanticsBinding(
        ontology=ontology, source=source, mapping_code="interview", scope="interview"
    )
    with pytest.raises(WorkbenchOwnerError, match="BINDING_MISMATCH"):
        verify_resources(resolved, ready)
    verify_resources(resolved, ready, ontology_binding=selected)
    require_work_binding(selected, selected)
    with pytest.raises(WorkbenchOwnerError, match="BINDING_MISMATCH"):
        require_work_binding(selected, None)
    with pytest.raises(WorkbenchOwnerError, match="BINDING_MISMATCH"):
        require_work_binding(selected, selected.model_copy(update={"scope": "other"}))


def test_binding_resolves_only_unique_declared_source(monkeypatch):
    import agent_console.ontology_capability_binding as module

    value = rules().model_dump(mode="json")
    monkeypatch.setattr(module, "read_reference", lambda *a, **k: {"content": value})
    ref = {"resource_id": "rules", "revision_id": "r1", "digest": "b" * 64}
    bindings = [
        {"kind": "ONTOLOGY", "reference": ref},
        {"kind": "KNOWLEDGE", "reference": value["mappings"][0]["source"]},
    ]
    assert (
        document_binding(None, {"contract": {"bindings": bindings}}).scope
        == "interview"
    )
    for changed in (
        [bindings[0]],
        [*bindings, bindings[0]],
        [
            bindings[0],
            {
                "kind": "KNOWLEDGE",
                "reference": {**bindings[1]["reference"], "revision_id": "other"},
            },
        ],
    ):
        with pytest.raises(WorkbenchOwnerError):
            document_binding(None, {"contract": {"bindings": changed}})
    assert document_binding(None, {"contract": {"bindings": []}}) is None
