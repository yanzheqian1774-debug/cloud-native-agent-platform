"""Disposable SQL and browser boundary tests; no provider calls or live grants."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, AuthorityScope, ExactGrant
from agent_console.model_binding_resolution import ExactModelBinding
from agent_console.model_governance import ModelLifecycleAction
from agent_console.model_governance_authorization import (
    model_catalog_grant,
    model_revision_grant,
)
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_model_directory import ModelReadTargets, operations
from agent_console.workbench_pagination import WorkbenchCursorCodec
from fastapi.testclient import TestClient
from test_model_governance_postgres import (
    DATABASE_URL,
    fact,
    migrated_repository,
    persist_exact_graph,
    records,
)
from test_workbench_bff import SessionStub

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="real PostgreSQL 15 required")


def grant(revision):
    return model_revision_grant(
        ExactModelBinding(revision.model_id, revision.revision_id, revision.digest)
    )


@pytest.fixture
def case():
    from uuid import uuid4

    repo = migrated_repository()
    values = records(uuid4().hex)
    persist_exact_graph(repo, values)
    scope, definition, *_configuration, r1 = values
    repo.advance_head(
        scope, definition.model_id, r1.revision_id, expected_aggregate_version=1
    )
    for ordinal, action in enumerate(
        (
            ModelLifecycleAction.VALIDATED,
            ModelLifecycleAction.HUMAN_REVIEWED,
            ModelLifecycleAction.PUBLISHED,
        ),
        1,
    ):
        repo.append_fact(fact(r1, ordinal, action))
    r2 = replace(
        r1,
        revision_id=r1.revision_id + ":next",
        revision=2,
        predecessor_revision_id=r1.revision_id,
        digest="",
    )
    repo.add_revision(r2)
    repo.advance_head(
        scope, definition.model_id, r2.revision_id, expected_aggregate_version=2
    )
    sessions = SessionStub()
    sessions.context = replace(
        sessions.context, scope=AuthorityScope(scope.namespace, scope.security_domain)
    )
    sessions.session = replace(
        sessions.session,
        principal=replace(sessions.session.principal, scope=sessions.context.scope),
    )
    allowed = {model_catalog_grant(), grant(r1), grant(r2)}
    require_calls = []

    def require(_principal, owner, action, resource):
        exact = ExactGrant(owner, action, resource)
        require_calls.append(exact)
        if exact not in allowed:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def execute(context, grants, *, operation, payload, path, query, handler):
        for g in grants:
            require(None, g.owner, g.action, g.exact_resource)
        with repo.pool.connection() as c, c.transaction():
            return handler(
                SimpleNamespace(
                    context=context,
                    operation=operation,
                    payload=payload,
                    path=path,
                    query=query,
                    connection=c,
                    authority=SimpleNamespace(require=require),
                )
            )

    ops = operations(repo, WorkbenchCursorCodec(b"m" * 32))
    client = TestClient(
        create_workbench_bff(
            sessions,
            SimpleNamespace(execute=execute),
            WorkbenchBffPolicy("console.test", "https://console.test"),
            operations=ops,
        ),
        base_url="https://console.test",
    )
    client.cookies.set("__Host-workbench_session", sessions.secret)
    yield SimpleNamespace(
        repo=repo,
        r1=r1,
        r2=r2,
        allowed=allowed,
        sessions=sessions,
        ops=ops,
        client=client,
        execute=execute,
        require_calls=require_calls,
    )
    client.close()
    repo.close()


def read(case, **query):
    response = case.client.get("/api/workbench/v1/model-directory", params=query)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def exact(case, revision=None, digest=None):
    r = revision or case.r1
    return case.client.get(
        f"/api/workbench/v1/model-directory/{r.model_id}/revisions/{r.revision_id}",
        params={"digest": digest or r.digest},
    )


def test_history_current_head_and_lifecycle_are_distinct_and_no_config_disclosure(case):
    data = read(case)
    assert len(data["items"]) == 2
    old, new = data["items"]
    assert old["digest"] == case.r1.digest
    assert old["state"] == "PUBLISHED_ENABLED" and not old["isCurrentRevision"]
    assert old["lifecycleHighWater"]["ordinal"] == 3
    assert new["state"] == "NOT_RECORDED" and new["isCurrentRevision"]
    assert new["lifecycleHighWater"] is None
    assert data["executionAuthority"] == "NONE"
    serialized = json.dumps(data)
    for forbidden in (
        "secret_reference",
        "secret:model",
        "models.example.invalid",
        "request_timeout",
        "normalized_address",
    ):
        assert forbidden not in serialized
    assert exact(case).json()["result"]["item"] == old
    # Reading the old version did not advance, alter or invoke it.
    assert (
        case.repo.get_revision(case.r1.scope, case.r1.model_id, case.r1.revision_id)
        == case.r1
    )
    assert case.repo.get(case.r1.scope, case.r1.model_id).aggregate_version == 3


def test_catalog_never_implies_exact_read_and_exact_read_does_not_need_catalog(case):
    case.allowed.remove(grant(case.r2))
    assert [x["revisionId"] for x in read(case)["items"]] == [case.r1.revision_id]
    assert exact(case, case.r2).status_code == 404
    case.allowed.remove(model_catalog_grant())
    assert case.client.get("/api/workbench/v1/model-directory").status_code == 404
    assert exact(case).status_code == 200
    case.allowed.remove(grant(case.r1))
    assert exact(case).status_code == 404


def test_exact_wrong_digest_not_substituted_even_if_granted(case):
    wrong = ExactGrant(
        "MODEL_GOVERNANCE",
        "READ_MODEL",
        f"model:revision:{case.r1.model_id}:{case.r1.revision_id}:" + "0" * 64,
    )
    case.allowed.add(wrong)
    assert exact(case, digest="0" * 64).status_code == 404
    assert exact(case, digest="bad").status_code == 422
    assert exact(case).json()["result"]["item"]["revisionId"] == case.r1.revision_id


def test_cursor_binds_actor_filter_scope_and_page_size(case):
    first = read(case, pageSize=1)
    token = first["nextCursor"]
    assert token and len(first["items"]) == 1
    assert len(read(case, pageSize=1, cursor=token)["items"]) == 1
    assert read(case, pageSize=1, cursor=token)["nextCursor"] is None
    for query in ({"pageSize": 2}, {"pageSize": 1, "query": "x"}):
        assert (
            case.client.get(
                "/api/workbench/v1/model-directory", params={**query, "cursor": token}
            ).status_code
            == 422
        )
    case.sessions.context = replace(case.sessions.context, principal_id="human:other")
    assert (
        case.client.get(
            "/api/workbench/v1/model-directory", params={"pageSize": 1, "cursor": token}
        ).status_code
        == 422
    )
    case.sessions.context = replace(
        case.sessions.context, scope=AuthorityScope("foreign", "other")
    )
    assert (
        case.client.get(
            "/api/workbench/v1/model-directory", params={"pageSize": 1, "cursor": token}
        ).status_code
        == 422
    )
    assert read(case)["items"] == []


def test_scope_and_missing_exact_have_no_latest_fallback(case):
    case.sessions.context = replace(
        case.sessions.context, scope=AuthorityScope("foreign", "other")
    )
    assert read(case)["items"] == []
    assert exact(case).status_code == 404


def test_browser_boundary_rejects_foreign_identity_and_no_write_routes(case):
    assert (
        case.client.get(
            "/api/workbench/v1/model-directory", headers={"X-Principal-Id": "foreign"}
        ).status_code
        == 400
    )
    assert (
        case.client.post(
            "/api/workbench/v1/model-directory",
            headers={"Origin": "https://console.test", "X-CSRF-Token": "csrf-token"},
            json={},
        ).status_code
        == 405
    )
    case.client.cookies.clear()
    assert case.client.get("/api/workbench/v1/model-directory").status_code == 401


def test_read_target_lookup_does_not_register_create_or_manage(case):
    targets = ModelReadTargets(case.repo)
    with case.repo.pool.connection() as c:
        assert targets.is_known_exact_target(
            case.sessions.context, grant(case.r1), connection=c
        )
        assert targets.is_known_exact_target(
            case.sessions.context, model_catalog_grant(), connection=c
        )
        assert not targets.is_known_exact_target(
            case.sessions.context,
            ExactGrant("MODEL_GOVERNANCE", "CREATE_MODEL", "model:collection"),
            connection=c,
        )
        assert not targets.is_known_exact_target(
            case.sessions.context,
            ExactGrant(
                "MODEL_GOVERNANCE",
                "MANAGE_MODEL_REVISION",
                f"model:management:PUBLISH:{case.r1.model_id}:{case.r1.revision_id}",
            ),
            connection=c,
        )
    assert not targets.is_known_exact_target(case.sessions.context, grant(case.r1))


def test_permission_storage_failure_is_not_mislabeled_as_empty(case):
    def unavailable(*_):
        raise AuthorityError("AUTHORITY_STORAGE_UNAVAILABLE")

    with (
        case.repo.pool.connection() as c,
        pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"),
    ):
        case.ops[0].handler(
            SimpleNamespace(
                operation="LIST_MODEL_DIRECTORY",
                context=case.sessions.context,
                query={},
                connection=c,
                authority=SimpleNamespace(require=unavailable),
            )
        )
