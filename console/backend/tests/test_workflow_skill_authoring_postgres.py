"""Real production HTTP authoring; execution Plan uses existing domain preparation."""

import copy

import httpx
import pytest
from test_governed_execution_api_postgres import (
    DATABASE_URL,
    _free_port,
    _headers,
    _prepare,
    _start_supervisor,
    _stop_process,
    _write_authority,
    protocol_service,
)

pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL 15 required"
)
WORKFLOWS = "/api/internal/v0.2.2/workflow-definitions"
SKILLS = "/api/internal/v0.2.2/resources/skill"


def request(client, method, path, headers, payload=None, status=200):
    response = client.request(method, path, headers=headers, json=payload)
    assert response.status_code == status, response.text
    return response.json()


def publish(client, kind, scope, content):
    headers = {
        "X-Tenant-ID": scope.namespace,
        "X-Security-Domain": scope.security_domain,
        "X-Principal-ID": "human:293-author",
    }
    content = copy.deepcopy(content)
    if kind == "skill" and "operations" in content:
        alternate = copy.deepcopy(content["operations"][0])
        alternate["name"] += ".alternate"
        if not any(item["name"] == alternate["name"] for item in content["operations"]):
            content["operations"].append(alternate)
    path, wrapper, key = (
        (SKILLS, "resource", "resourceId")
        if kind == "skill"
        else (WORKFLOWS, "definition", "workflowDefinitionId")
    )
    row = request(
        client,
        "POST",
        path,
        headers,
        {"name": "293 real API authoring", "content": content},
        201,
    )[wrapper]
    resource_id = row[key]
    path = f"{path}/{resource_id}"
    if kind == "skill":
        saved = request(client, "GET", path, headers)[wrapper]
        prior = copy.deepcopy(saved["revisions"])
        editing = copy.deepcopy(saved["revisions"][-1]["content"])
        editing["description"] = "Edit unrelated Skill description"
        for clear in ("omitted", None, []):
            bad = copy.deepcopy(editing)
            if clear == "omitted":
                bad.pop("operations", None)
                if "operations" not in content:
                    continue
            else:
                bad["operations"] = clear
            request(
                client,
                "PUT",
                f"{path}/draft",
                headers,
                {"expectedVersion": row["aggregateVersion"], "content": bad},
                422,
            )
        row = request(
            client,
            "PUT",
            f"{path}/draft",
            headers,
            {"expectedVersion": row["aggregateVersion"], "content": editing},
        )[wrapper]
        assert row["revisions"][: len(prior)] == prior
        assert row["revisions"][-1]["content"].get("operations") == content.get(
            "operations"
        )
        for bad in (
            {**editing, "unknownInput": True},
            {**editing, "operations": [{"name": "incomplete"}]},
        ):
            request(
                client,
                "PUT",
                f"{path}/draft",
                headers,
                {"expectedVersion": row["aggregateVersion"], "content": bad},
                422,
            )
    row = request(
        client,
        "POST",
        f"{path}/validation",
        headers,
        {"expectedVersion": row["aggregateVersion"]},
    )[wrapper]
    revision = row["revisions"][-1]
    if kind == "skill":
        assert revision["content"].get("operations") == content.get("operations")
        if "operations" not in content:
            assert "operations" not in revision["content"]
    row = request(
        client,
        "POST",
        f"{path}/reviews",
        headers,
        {
            "expectedVersion": row["aggregateVersion"],
            "digest": revision["digest"],
            "decision": "APPROVE",
            "reason": "Human review of exact 293 revision",
        },
    )[wrapper]
    row = request(
        client,
        "POST",
        f"{path}/publications",
        headers,
        {
            "expectedVersion": row["aggregateVersion"],
            "digest": revision["digest"],
            "reviewId": row["reviews"][-1]["reviewId"],
        },
    )[wrapper]
    read = request(client, "GET", path, headers)[wrapper]
    assert read["publishedRevisionId"] == revision["revisionId"]
    assert read["revisions"] == row["revisions"]
    if kind == "skill":
        # Published content cannot be edited in place, even with exact operations.
        request(
            client,
            "PUT",
            f"{path}/draft",
            headers,
            {
                "expectedVersion": row["aggregateVersion"],
                "content": revision["content"],
            },
            409,
        )
    return resource_id, revision["revisionId"], revision["digest"]


def reject_unusable_references(client, scope, headers, content, skill_id):
    skill = request(client, "GET", f"{SKILLS}/{skill_id}", headers)["resource"]
    skill_content = copy.deepcopy(skill["revisions"][-1]["content"])
    unpublished = request(
        client,
        "POST",
        SKILLS,
        headers,
        {"name": "Unpublished", "content": skill_content},
        201,
    )["resource"]
    unpublished_revision = unpublished["revisions"][-1]
    legacy_content = copy.deepcopy(skill_content)
    del legacy_content["operations"]
    legacy = publish(client, "skill", scope, legacy_content)
    other_scope = type(scope)(scope.namespace + "-other", scope.security_domain)
    foreign = publish(client, "skill", other_scope, skill_content)
    invalid_identities = [
        (
            unpublished["resourceId"],
            unpublished_revision["revisionId"],
            unpublished_revision["digest"],
        ),
        legacy,
        foreign,
        (skill_id, "nonexistent-revision", skill["revisions"][-1]["digest"]),
    ]
    for resource_id, revision_id, digest in invalid_identities:
        bad = copy.deepcopy(content)
        bad["tasks"][0]["references"] = [
            {
                "kind": "SKILL",
                "resourceId": resource_id,
                "revisionId": revision_id,
                "digest": digest,
            }
        ]
        bad["tasks"][0]["skillOperationBindings"] = [
            {
                "skillId": resource_id,
                "skillRevisionId": revision_id,
                "skillDigest": digest,
                "operation": "supplier-quality.summary",
            }
        ]
        row = request(
            client,
            "POST",
            WORKFLOWS,
            headers,
            {"name": "Ineligible Skill", "content": bad},
            201,
        )["definition"]
        request(
            client,
            "POST",
            f"{WORKFLOWS}/{row['workflowDefinitionId']}/validation",
            headers,
            {"expectedVersion": row["aggregateVersion"]},
            409,
        )
    # A valid binding cannot conceal a contradictory reference digest.
    bad = copy.deepcopy(content)
    bad["tasks"][0]["references"][0]["digest"] = "0" * 64
    row = request(
        client,
        "POST",
        WORKFLOWS,
        headers,
        {"name": "Contradictory digest", "content": bad},
        201,
    )["definition"]
    request(
        client,
        "POST",
        f"{WORKFLOWS}/{row['workflowDefinitionId']}/validation",
        headers,
        {"expectedVersion": row["aggregateVersion"]},
        409,
    )
    # Historical Workflow reads/publications never invent bindings.
    historical = copy.deepcopy(content)
    historical["tasks"][0].pop("skillOperationBindings")
    history_id = publish(client, "workflow", scope, historical)[0]
    history = request(client, "GET", f"{WORKFLOWS}/{history_id}", headers)["definition"]
    assert (
        "skillOperationBindings" not in history["revisions"][-1]["content"]["tasks"][0]
    )
    return legacy


def test_real_workflow_authoring_and_supervised_consumption(monkeypatch, tmp_path):
    monkeypatch.setenv("WORKFLOW_RUNTIME_DATABASE_URL", DATABASE_URL or "")
    authority_file = tmp_path / "293-authority.json"

    def start(endpoint):
        # Many real HTTP requests must not fill an unread subprocess log pipe.
        with (tmp_path / "293-supervisor.log").open("a") as output:
            return _start_supervisor(
                _free_port(), endpoint, authority_file, output=output
            )

    with protocol_service() as (endpoint, calls):
        process, _, base = start(endpoint)
        try:
            with httpx.Client(base_url=base, timeout=15) as client:
                scope, command, identities = _prepare(
                    endpoint,
                    author_resources=lambda kind, scope, content: publish(
                        client, kind, scope, content
                    ),
                )
                headers = {
                    "X-Tenant-ID": scope.namespace,
                    "X-Security-Domain": scope.security_domain,
                }
                path = f"{WORKFLOWS}/{identities['workflowDefinitionId']}"
                original = request(client, "GET", path, headers)["definition"]
                history = copy.deepcopy(original["revisions"])
                row = request(
                    client,
                    "POST",
                    f"{path}/successors",
                    headers,
                    {"expectedVersion": original["aggregateVersion"]},
                )["definition"]
                content = copy.deepcopy(row["revisions"][-1]["content"])
                binding = copy.deepcopy(content["tasks"][0]["skillOperationBindings"])
                content["description"] = "Unrelated edit through GET / draft"
                row = request(
                    client,
                    "PUT",
                    f"{path}/draft",
                    headers,
                    {"expectedVersion": row["aggregateVersion"], "content": content},
                )["definition"]
                assert (
                    row["revisions"][-1]["content"]["tasks"][0][
                        "skillOperationBindings"
                    ]
                    == binding
                )
                for null in (False, True):
                    bad = copy.deepcopy(content)
                    if null:
                        bad["tasks"][0]["skillOperationBindings"] = None
                    else:
                        del bad["tasks"][0]["skillOperationBindings"]
                    response = client.put(
                        f"{path}/draft",
                        headers=headers,
                        json={
                            "expectedVersion": row["aggregateVersion"],
                            "content": bad,
                        },
                    )
                    assert response.status_code == 409, response.text
                for field, value in (
                    ("skillRevisionId", "missing"),
                    ("skillDigest", "0" * 64),
                    ("operation", "missing"),
                ):
                    bad = copy.deepcopy(content)
                    bad["tasks"][0]["skillOperationBindings"][0][field] = value
                    created = client.post(
                        WORKFLOWS,
                        headers=headers,
                        json={"name": "Rejected exact identity", "content": bad},
                    )
                    if field == "skillRevisionId":
                        assert created.status_code == 422, created.text
                    else:
                        assert created.status_code == 201, created.text
                        record = created.json()["definition"]
                        request(
                            client,
                            "POST",
                            f"{WORKFLOWS}/{record['workflowDefinitionId']}/validation",
                            headers,
                            {"expectedVersion": record["aggregateVersion"]},
                            409,
                        )
                legacy = reject_unusable_references(
                    client, scope, headers, content, command["skillId"]
                )
                changed = copy.deepcopy(content)
                changed["tasks"][0]["skillOperationBindings"][0]["operation"] += (
                    ".alternate"
                )
                row = request(
                    client,
                    "PUT",
                    f"{path}/draft",
                    headers,
                    {"expectedVersion": row["aggregateVersion"], "content": changed},
                )["definition"]
                request(
                    client,
                    "POST",
                    f"{path}/validation",
                    headers,
                    {"expectedVersion": row["aggregateVersion"]},
                )
                final = request(client, "GET", path, headers)["definition"]
                assert final["revisions"][: len(history)] == history
                assert calls == []
        finally:
            _stop_process(process)
        invalid = [
            {
                **command,
                "operation": "unknown",
                "idempotencyKey": "293-unknown-operation",
            },
            {
                **command,
                "skillId": legacy[0],
                "skillRevisionId": legacy[1],
                "skillDigest": legacy[2],
                "idempotencyKey": "293-historical-no-operation",
            },
            {**command, "skillDigest": "0" * 64, "idempotencyKey": "293-wrong-digest"},
        ]
        _write_authority(authority_file, scope, (command, *invalid), identities)
        process, _, base = start(endpoint)
        try:
            with httpx.Client(base_url=base, timeout=15) as client:
                for bad in invalid:
                    request(
                        client,
                        "POST",
                        "/api/internal/v0.2.3/executions",
                        _headers(),
                        bad,
                        409,
                    )
                assert calls == []
                first = request(
                    client,
                    "POST",
                    "/api/internal/v0.2.3/executions",
                    _headers(),
                    command,
                    201,
                )
                replay = request(
                    client,
                    "POST",
                    "/api/internal/v0.2.3/executions",
                    _headers(),
                    command,
                    200,
                )
                assert first["invocation"]["state"] == "SUCCEEDED"
                assert first["skillCallSucceeded"] is True
                assert first["invocation"]["resourceUseId"]
                assert first["invocation"]["evidenceId"]
                assert replay == first
                assert len(calls) == 1
        finally:
            _stop_process(process)
