# ruff: noqa: F401,F811 -- Original isolated owner fixture graph.
from dataclasses import replace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.ontology_published_read import resolve
from agent_console.published_test_resources import descendant
from agent_console.test_resource_read_access import prepare
from agent_console.test_resource_read_policy import (
    PublishedTestReadPolicy,
    TestReadPolicy,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_test_resource_read_access import read_policy
from test_test_resource_read_policy import policy as v1_policy


def test_v1_unchanged_and_v2_load_is_explicit(tmp_path):
    old = v1_policy()
    payload = old.model_dump(mode="json")
    path = tmp_path / "policy.json"
    path.write_text(old.model_dump_json())
    loaded = TestReadPolicy.load(path)
    assert type(loaded) is TestReadPolicy
    assert loaded.model_dump(mode="json") == payload
    assert loaded.digest == old.digest
    assert "publishedResources" not in payload
    new = PublishedTestReadPolicy.model_validate(
        payload | {"schemaVersion": "test-resource-read-policy.v2"}
    )
    assert not new.enabled and not new.publishedResources
    path.write_text(new.model_dump_json())
    assert type(TestReadPolicy.load(path)) is PublishedTestReadPolicy


@pytest.mark.parametrize(
    "current,anchor,digest",
    [("draft", "a", "a" * 64), ("b", "a", "b" * 64), ("b", "foreign", "a" * 64)],
)
def test_invalid_anchor_or_lineage_rejected(current, anchor, digest):
    with pytest.raises(AuthorityError):
        descendant(
            {"a": {"digest": "a" * 64}, "b": {"digest": "b" * 64, "predecessor": None}},
            current,
            anchor,
            digest,
            "predecessor",
        )


@pytest.fixture
def curated(read_policy):
    a, g, context, old, _ = read_policy
    employee = next(
        r for r in a.e.p.semantics.requirements if r.kind == "EMPLOYEE"
    ).selected
    refs = {"skill": a.refs["skill"], "employee": employee}
    policy = PublishedTestReadPolicy.model_validate(
        old.model_dump(mode="json")
        | {
            "schemaVersion": "test-resource-read-policy.v2",
            "publishedResources": [
                dict(
                    kind=k,
                    logicalId=r.resource_id,
                    anchorRevision=r.revision_id,
                    anchorDigest=r.digest,
                    purpose="RESOURCE_PREPARATION",
                )
                for k, r in refs.items()
            ],
        }
    )

    def selection(candidate=policy, subject=context):
        with a.authority.connection_scope() as c:
            return resolve(candidate, subject, c)

    def run(selected=None, key=None, candidate=policy, subject=context):
        selected = selected or selection(candidate, subject)
        with a.authority.connection_scope() as c:
            return prepare(
                candidate,
                g,
                subject,
                c,
                key or f"published:{selected.digest}:one",
                selected.digest,
            )

    return a, g, context, policy, refs, selection, run


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_real_published_owners_exact_read_replay_and_cross_scope(curated):
    _a, _g, context, policy, _refs, selection, run = curated
    s = selection()
    assert {t.owner for t in s.targets} == {"SKILL", "EMPLOYEE"}
    result = run(s)
    assert run(s) == result  # lost response reuses immutable key, no second decision.
    assert all(t.action in {"READ", "READ_RESOURCE"} for t in s.targets)
    wrong = replace(context, scope=replace(context.scope, security_domain="other"))
    assert not selection(subject=wrong).targets
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(s, subject=wrong)
    bad = policy.model_copy(
        update={
            "publishedResources": (
                policy.publishedResources[0].model_copy(
                    update={"anchorDigest": "f" * 64}
                ),
            )
        }
    )
    with pytest.raises(AuthorityError, match="SNAPSHOT_CHANGED"):
        selection(bad)


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_real_lineage_revocation_and_selection_key_are_not_bypassed(curated):
    from agent_console.grant_administration_application import GrantRevocationCommand

    a, g, context, _policy, _refs, selection, run = curated
    s = selection()
    result = run(s)
    skill_target = next(t for t in s.targets if t.owner == "SKILL")
    item = next(x for x in result["items"] if x["resource"] == skill_target.resource)
    with a.authority.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
            (item["requestId"],),
        ).fetchone()["grant_id"]
    g.revoke_grant(
        context, GrantRevocationCommand(grant, "USER_REQUESTED", "curated-revoke", True)
    )
    outcome = run(s, key=f"published:{s.digest}:new")
    assert (
        next(x for x in outcome["items"] if x["resource"] == skill_target.resource)[
            "state"
        ]
        == "REVOKED"
    )
    with pytest.raises(AuthorityError, match="SELECTION_KEY_MISMATCH"):
        run(s, key=f"published:{'0' * 64}:one")


def publish_successor(a, context):

    service = a.services["skill"]
    scope = service.scope(context.scope.tenant_id, context.scope.security_domain)
    identity = a.refs["skill"].resource_id
    current = service.repository.get(scope, "skill", identity)
    draft = service.successor(
        scope, "skill", identity, context.principal_id, current["aggregateVersion"]
    )["resource"]
    revision = next(
        x
        for x in draft["revisions"]
        if x["revisionId"] == draft["currentDraftRevisionId"]
    )
    return scope, identity, draft, revision


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_real_draft_is_not_selected_then_publication_invalidates_old_key(curated):
    from types import SimpleNamespace

    from agent_console.workbench_prepared_resources import PreparedResourceOwner

    a, _g, context, _policy, _refs, selection, run = curated
    before = selection()
    _scope, identity, draft, revision = publish_successor(a, context)
    assert selection().digest == before.digest
    assert all(t.digest != revision["digest"] for t in selection().targets)
    with a.authority.connection_scope() as c:
        PreparedResourceOwner(a.services)(
            SimpleNamespace(
                operation="REVIEW_PREPARED_RESOURCE",
                context=context,
                connection=c,
                authority=SimpleNamespace(
                    require=lambda *args: SimpleNamespace(
                        decision_id="isolated-publication-authority"
                    )
                ),
                path={
                    "kind": "skill",
                    "identity": identity,
                    "revision": revision["revisionId"],
                },
                payload={
                    "expectedVersion": draft["aggregateVersion"],
                    "digest": revision["digest"],
                    "reason": "Isolated successor owner fixture, no human review claim",
                    "idempotencyKey": "curated-successor-publication",
                },
            )
        )
    after = selection()
    assert after.digest != before.digest
    assert any(t.digest == revision["digest"] for t in after.targets)
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        run(before)
    outcome = run(after)
    assert any(x["resource"].endswith(revision["revisionId"]) for x in outcome["items"])


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_publication_snapshot_locks_both_aggregates_until_read_commit(curated):
    from psycopg.errors import LockNotAvailable

    a, _g, context, policy, refs, _selection, _run = curated
    with a.authority.connection_scope() as first:
        selected = resolve(policy, context, first)
        assert len(selected.targets) == 2
        for table, column, logical in [
            ("skill_mcp_resource.resources", "resource_id", refs["skill"].resource_id),
            (
                "digital_employee_definition.definitions",
                "definition_id",
                refs["employee"].resource_id,
            ),
        ]:
            with (
                a.authority.connection_scope() as second,
                pytest.raises(LockNotAvailable),
                second.transaction(),
            ):
                second.execute("SET LOCAL lock_timeout='100ms'")
                second.execute(
                    f"SELECT 1 FROM {table} WHERE namespace=%s "
                    f"AND security_domain=%s AND {column}=%s FOR UPDATE",
                    (
                        context.scope.tenant_id,
                        context.scope.security_domain,
                        logical,
                    ),
                )


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_real_explicit_denial_applies_to_curated_lineage(curated):
    from agent_console.grant_administration_application import (
        GrantDecisionCommand,
        GrantRequestCommand,
    )

    a, g, context, policy, _refs, selection, run = curated
    target = next(t for t in selection().targets if t.owner == "EMPLOYEE")
    issuer, _ = policy.authenticate(g, context)
    request = g.submit_request(
        context,
        GrantRequestCommand(target.purpose, (target.grant,), "curated-denial-request"),
    )
    g.decide_request(
        issuer,
        GrantDecisionCommand(
            request.request_id,
            False,
            "CONTROLLED_REVIEW",
            "POLICY",
            "isolated-denial",
            None,
            None,
            "curated-denial",
            expected_version=1,
        ),
    )
    result = run()
    assert (
        next(x for x in result["items"] if x["resource"] == target.resource)["state"]
        == "DENIED"
    )
    with a.authority.connection_scope() as c:
        assert not c.execute(
            "SELECT 1 FROM authorization_admin.grants WHERE request_id=%s",
            (request.request_id,),
        ).fetchone()


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_employee_successor_is_exact_and_revoked_anchor_blocks_new_publication(curated):
    from uuid import uuid4

    from agent_console.digital_employee_definition import EmployeeRevision
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from agent_console.grant_administration_application import GrantRevocationCommand

    a, g, context, _policy, refs, selection, run = curated
    before = selection()
    receipt = run(before)
    old = next(t for t in before.targets if t.owner == "EMPLOYEE")
    item = next(x for x in receipt["items"] if x["resource"] == old.resource)
    owner = PostgresEmployeeDefinitionRepository(a.repository)
    ref = refs["employee"]
    with a.authority.connection_scope() as c:
        existing = owner._read(c, a.e.scope, ref.resource_id, ref.revision_id)
        original = EmployeeRevision.from_record(existing["revision"])
        successor = replace(
            original,
            revision_id="employee-revision:" + uuid4().hex,
            predecessor_revision_id=ref.revision_id,
            role="Curated successor isolated test",
        )
        created = owner.create_for_workbench(
            c,
            successor,
            expected_version=existing["aggregateVersion"],
            decision_id="isolated-owner-fixture",
            command_id="curated-employee-successor",
            authorized=True,
        )
    assert selection().digest == before.digest
    with a.authority.connection_scope() as c:
        value = created
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            value = owner.decide_for_workbench(
                c,
                a.e.scope,
                ref.resource_id,
                successor.revision_id,
                successor.digest,
                action,
                expected_version=value["aggregateVersion"],
                decision_id="isolated-owner-fixture",
                command_id="curated-employee-" + action,
                authorized=True,
            )
    after = selection()
    assert any(
        t.resource.endswith(successor.revision_id) and t.digest == successor.digest
        for t in after.targets
    )
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        run(before)
    with a.authority.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
            (item["requestId"],),
        ).fetchone()["grant_id"]
    g.revoke_grant(
        context,
        GrantRevocationCommand(grant, "USER_REQUESTED", "curated-anchor-revoke", True),
    )
    result = run(after)
    assert (
        next(
            x for x in result["items"] if x["resource"].endswith(successor.revision_id)
        )["state"]
        == "REVOKED"
    )


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_current_static_tombstone_cannot_be_escaped_with_dynamic_key(curated):
    a, g, context, _policy, _refs, selection, run = curated
    selected = selection()
    target = next(t for t in selected.targets if t.owner == "SKILL")
    credentials = [
        x
        for x in g.generation.credentials
        if x.principal_id == context.principal_id and x.scope == context.scope
    ]
    assert credentials
    original = g.generation
    successor = replace(
        original,
        static_grant_revocation_tombstones=frozenset(
            {(credentials[0].credential_id, target.grant)}
        ),
    )
    g._generation_provider = lambda: successor
    g.authorization._generation_provider = lambda: successor
    outcome = run(selected)
    assert (
        next(x for x in outcome["items"] if x["resource"] == target.resource)["state"]
        == "REVOKED"
    )
    with a.authority.connection_scope() as c:
        assert not c.execute(
            "SELECT 1 FROM authorization_admin.grants "
            "WHERE owner=%s AND exact_resource=%s",
            ("SKILL", target.resource),
        ).fetchone()


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
@pytest.mark.parametrize(
    "binding", ["local-account", "grant-source", "known-other", "orphan"]
)
def test_successor_tombstone_identity_mapping_is_bounded(curated, binding):
    from types import SimpleNamespace

    from agent_console.authority_configuration import LocalAccountBinding
    from agent_console.authority_contracts import CredentialId
    from agent_console.workbench_prepared_resources import PreparedResourceOwner

    a, g, context, policy, _refs, selection, run = curated
    before = selection()
    old = next(t for t in before.targets if t.owner == "SKILL")
    run(
        before
    )  # Existing targets are already readable; forbidden successor adds nothing.
    _scope, identity, draft, revision = publish_successor(a, context)
    with a.authority.connection_scope() as c:
        PreparedResourceOwner(a.services)(
            SimpleNamespace(
                operation="REVIEW_PREPARED_RESOURCE",
                context=context,
                connection=c,
                authority=SimpleNamespace(
                    require=lambda *args: SimpleNamespace(
                        decision_id="isolated-publication-authority"
                    )
                ),
                path={
                    "kind": "skill",
                    "identity": identity,
                    "revision": revision["revisionId"],
                },
                payload={
                    "expectedVersion": draft["aggregateVersion"],
                    "digest": revision["digest"],
                    "reason": "Isolated immutable successor fixture",
                    "idempotencyKey": "mapping-successor-publication",
                },
            )
        )
    selected = selection()
    current = next(t for t in selected.targets if t.owner == "SKILL")
    assert current.resource != old.resource
    # Isolate the forbidden successor in this policy so unrelated authorized
    # targets cannot legitimately add requests and obscure the zero-write assertion.
    narrowed = policy.model_copy(
        update={
            "targets": (current,),
            "publishedResources": tuple(
                s for s in policy.publishedResources if s.kind == "skill"
            ),
        }
    )
    selected = selection(narrowed)
    generation = g.generation
    source = next(
        x
        for x in generation.credentials
        if x.principal_id == context.principal_id and x.scope == context.scope
    )
    local_id = CredentialId("local-account:curated-test")
    source_id = source.credential_id
    subject = context.principal_id
    credentials = generation.credentials
    if binding == "known-other":
        source_id = CredentialId("credential:other-curated-subject")
        subject = "human:other-curated-subject"
        credentials = (
            *credentials,
            replace(source, credential_id=source_id, principal_id=subject),
        )
    local = LocalAccountBinding(
        local_id, "curated-test", subject, context.scope, source_id, ()
    )
    tombstone_id = source_id if binding == "grant-source" else local_id
    accounts = (*generation.local_accounts, local)
    if binding == "orphan":
        tombstone_id = CredentialId("removed-credential:historical-subject-unknown")
        accounts = generation.local_accounts
    updated = replace(
        generation,
        credentials=credentials,
        local_accounts=accounts,
        static_grant_revocation_tombstones=generation.static_grant_revocation_tombstones
        | frozenset({(tombstone_id, old.grant)}),
    )
    g._generation_provider = lambda: updated
    g.authorization._generation_provider = lambda: updated

    def counts():
        with a.authority.connection_scope() as c:
            return tuple(
                c.execute(f"SELECT count(*) n FROM authorization_admin.{t}").fetchone()[
                    "n"
                ]
                for t in ("grant_requests", "grant_decisions")
            )

    original_counts = counts()
    if binding == "orphan":
        with pytest.raises(AuthorityError, match="LINEAGE_IDENTITY_UNVERIFIED"):
            run(selected, candidate=narrowed)
        assert counts() == original_counts
    else:
        outcome = run(selected, candidate=narrowed)
        state = next(x for x in outcome["items"] if x["resource"] == current.resource)[
            "state"
        ]
        if binding == "known-other":
            assert state in {"APPROVED", "EFFECTIVE"}
        else:
            assert state == "REVOKED"
            assert counts() == original_counts
