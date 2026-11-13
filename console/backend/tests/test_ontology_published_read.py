# ruff: noqa: F401,F811 -- Shared isolated PostgreSQL fixture graph.
"""Real owner publications and exact grant administration; no deployed policy."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule
from agent_console.authority_contracts import AuthenticationSource, AuthorityError
from agent_console.ontology_published_read import resolve
from agent_console.test_resource_read_access import prepare
from agent_console.test_resource_read_policy import TestReadPolicy
from test_ontology_management import (
    create,
    grant_read,
    maintained,
    payload,
    run,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


@pytest.fixture
def published_read(maintained):
    m = maintained
    g = m.manager.grants
    reader = replace(
        m.gen.credentials[0],
        credential_id="reader",
        principal_id="human:reader",
        grants=(),
    )
    m.gen = replace(
        m.gen,
        credentials=(*m.gen.credentials, reader),
        requestability=(
            *m.gen.requestability,
            *(
                RequestabilityRule(
                    "BUSINESS_ONTOLOGY",
                    a,
                    "business-ontology:",
                    "F3_ONTOLOGY_TEST_READ",
                )
                for a in ("READ", "LIST")
            ),
        ),
    )
    g._generation_provider = lambda: m.gen
    g.authorization._generation_provider = lambda: m.gen
    context = replace(
        m.a.subject,
        principal_id=reader.principal_id,
        session_id_or_service_credential_id=reader.credential_id,
        authentication_source=AuthenticationSource.BROWSER_SESSION,
    )
    policy = TestReadPolicy(
        schemaVersion="test-resource-read-policy.v1",
        policyId="published",
        policyVersion="1",
        enabled=True,
        tenant=context.scope.tenant_id,
        securityDomain=context.scope.security_domain,
        subjects=(context.principal_id,),
        issuer=m.a.policy.issuer,
        credentialPath=m.a.policy.credentialPath,
        expiresAt=g.clock() + timedelta(hours=1),
        grantTTLSeconds=120,
        targets=[
            dict(
                owner="BUSINESS_ONTOLOGY",
                action="LIST",
                resource="business-ontology:collection",
                purpose="F3_ONTOLOGY_TEST_READ",
            )
        ],
        publishedOntologyIds=("managed-sales",),
    )

    def select(candidate=None, subject=None):
        with m.a.authority.connection_scope() as c:
            return resolve(candidate or policy, subject or context, c)

    def prepare_read(selection=None, key=None, candidate=None, subject=None):
        selection = selection or select(candidate, subject)
        with m.a.authority.connection_scope() as c:
            return prepare(
                candidate or policy,
                g,
                subject or context,
                c,
                key or f"published:{selection.digest}:first",
                selection.digest,
            )

    return SimpleNamespace(
        m=m, g=g, context=context, policy=policy, select=select, prepare=prepare_read
    )


def release(p, prior=None, suffix="one"):
    m = p.m
    result = create(m) if prior is None else prior
    for action in ("VALIDATE", "TEST", "REVIEW", "PUBLISH"):
        subject = None
        if action == "REVIEW":
            subject = replace(
                m.a.subject,
                principal_id=m.reviewer.principal_id,
                session_id_or_service_credential_id=m.reviewer.credential_id,
            )
            grant_read(m, subject, result["outcome"]["revision_id"])
        result = run(
            m, payload(m, result, action, f"{suffix}-{action}"), subject=subject
        )
    return result


def revise(p, prior, suffix="two"):
    v = prior["outcome"]
    return run(
        p.m,
        dict(
            action="REVISE",
            commandKey="revision-" + suffix,
            ontologyId="managed-sales",
            expectedVersion=v["version"],
            baseRevision=v["revision_id"],
            baseDigest=v["digest"],
            content={**p.m.content, "name": "changed " + suffix},
            reason="isolated successor",
        ),
    )


def read_items(result):
    return [
        i for i in result["items"] if i["resource"] != "business-ontology:collection"
    ]


def test_latest_publish_not_draft_head_and_exact_history_preserved(published_read):
    p = published_read
    old = release(p)
    selected = p.select()
    first = p.prepare(selected)
    assert read_items(first)[0]["state"] == "APPROVED"
    assert p.prepare(selected) == first
    draft = revise(p, old)
    assert p.select() == selected
    newer = release(p, draft, "two")
    current = p.select()
    assert current.digest != selected.digest
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        p.prepare(selected)
    with pytest.raises(AuthorityError, match="KEY_MISMATCH"):
        p.prepare(current, key=f"published:{selected.digest}:first")
    after = p.prepare(current)
    assert read_items(after)[0]["resource"].endswith(newer["outcome"]["revision_id"])
    with p.m.a.authority.connection_scope() as c:
        rows = c.execute(
            "SELECT action,exact_resource FROM authorization_admin.grants "
            "WHERE subject_principal_id=%s",
            (p.context.principal_id,),
        ).fetchall()
    assert {r["action"] for r in rows} == {"READ", "LIST"}
    assert any(
        r["exact_resource"].endswith(old["outcome"]["revision_id"]) for r in rows
    )


def test_deprecated_latest_never_resurrects_older_release(published_read):
    p = published_read
    old = release(p)
    newer = release(p, revise(p, old), "two")
    selected = p.select()
    run(p.m, payload(p.m, newer, "DEPRECATE", "deprecate-new"))
    current = p.select()
    assert not current.targets and current.digest != selected.digest
    assert read_items(p.prepare(current))[0]["state"] == "NOT_PUBLISHED"


def test_unknown_unpublished_and_foreign_scope_never_select_other_content(
    published_read,
):
    p = published_read
    create(p.m)
    assert not p.select().targets
    assert not p.select(
        p.policy.model_copy(update={"publishedOntologyIds": ("outside",)})
    ).targets
    foreign = replace(
        p.context, scope=replace(p.context.scope, security_domain="foreign")
    )
    assert not p.select(subject=foreign).targets
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        p.prepare(subject=foreign)


@pytest.mark.parametrize("blocked", ["DENIED", "REVOKED"])
def test_lineage_denial_and_revocation_block_successor_only_for_same_reader(
    published_read, blocked
):
    from agent_console.grant_administration_application import (
        GrantDecisionCommand,
        GrantRequestCommand,
        GrantRevocationCommand,
    )

    p = published_read
    old = release(p)
    target = p.select().targets[0]
    if blocked == "DENIED":
        request = p.g.submit_request(
            p.context,
            GrantRequestCommand(target.purpose, (target.grant,), "deny-original"),
        )
        issuer, _ = p.policy.authenticate(p.g, p.context)
        p.g.decide_request(
            issuer,
            GrantDecisionCommand(
                request.request_id,
                False,
                "CONTROLLED_REVIEW",
                "POLICY",
                "isolated-denial",
                None,
                None,
                "deny",
                expected_version=1,
            ),
        )
    else:
        receipt = read_items(p.prepare())[0]
        with p.m.a.authority.connection_scope() as c:
            grant = c.execute(
                "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
                (receipt["requestId"],),
            ).fetchone()["grant_id"]
        p.g.revoke_grant(
            p.context,
            GrantRevocationCommand(grant, "USER_REQUESTED", "surrender", True),
        )
    newer = release(p, revise(p, old), "two")
    assert read_items(p.prepare())[0]["state"] == blocked
    with p.m.a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT 1 FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s AND exact_resource=%s",
                (
                    p.context.principal_id,
                    "business-ontology:managed-sales:"
                    + newer["outcome"]["revision_id"],
                ),
            ).fetchone()
            is None
        )
    other = replace(p.context, principal_id="human:other")
    policy = p.policy.model_copy(update={"subjects": (other.principal_id,)})
    assert (
        read_items(p.prepare(candidate=policy, subject=other))[0]["state"] == "APPROVED"
    )


def test_exact_dynamic_key_does_not_renew_expiry_and_disabled_scope_rejects(
    published_read,
):
    p = published_read
    release(p)
    selected = p.select()
    p.prepare(selected)
    clock = p.g.clock
    p.g.clock = lambda: clock() + timedelta(minutes=3)
    assert read_items(p.prepare(selected))[0]["state"] == "EXPIRED"
    assert (
        read_items(p.prepare(selected, key=f"published:{selected.digest}:renew"))[0][
            "state"
        ]
        == "APPROVED"
    )
    for changes in (
        {"enabled": False},
        {"subjects": ("human:other",)},
        {"expiresAt": clock() - timedelta(seconds=1)},
    ):
        with pytest.raises(AuthorityError):
            p.prepare(selected, candidate=p.policy.model_copy(update=changes))


def test_static_policy_digest_and_keys_remain_compatible(published_read):
    from agent_console.resource_use_domain import canonical_digest

    p = published_read
    static = p.policy.model_copy(update={"publishedOntologyIds": ()})
    value = static.model_dump(mode="json")
    value.pop("publishedOntologyIds")
    assert static.digest == canonical_digest(value)
    with p.m.a.authority.connection_scope() as c:
        receipt = prepare(static, p.g, p.context, c, "existing-static-key")
    assert "selectionDigest" not in receipt


def test_shared_selection_lock_excludes_owner_revision_change(published_read):
    import psycopg
    from agent_console.ontology_domain import OntologyCommand
    from agent_console.ontology_postgres import PostgresOntologyRepository

    p = published_read
    published = release(p)
    with p.m.a.authority.connection_scope() as c:
        selected = resolve(p.policy, p.context, c)
        with (
            pytest.raises(psycopg.errors.LockNotAvailable),
            p.m.a.authority.connection_scope() as other,
        ):
            other.execute("SET LOCAL lock_timeout='100ms'")
            PostgresOntologyRepository(other).command(
                (p.context.scope.tenant_id, p.context.scope.security_domain),
                p.m.a.subject.principal_id,
                "managed-sales",
                "REVISE",
                OntologyCommand.model_validate(
                    dict(
                        request_key="concurrent-revise",
                        expected_version=published["outcome"]["version"],
                        revision_id="racing-draft",
                        content=p.m.content,
                        reason="isolated lock verification",
                    )
                ),
            )
        assert resolve(p.policy, p.context, c) == selected
    revise(p, published)
    assert p.select() == selected


def test_http_status_is_readonly_and_dynamic_key_cannot_be_retargeted(published_read):
    import hashlib
    from contextlib import nullcontext

    from agent_console.authority_contracts import GrantSource
    from agent_console.browser_session_application import (
        BrowserSessionPolicy,
        BrowserSessionService,
        StaticGenerationAuthenticator,
    )
    from agent_console.test_resource_read_access import install_test_read_access
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient

    p = published_read
    published = release(p)
    secret_text = "isolated-business-reader-only"
    p.m.gen = replace(
        p.m.gen,
        credentials=tuple(
            replace(
                cred,
                authentication_source=GrantSource.BROWSER_BOOTSTRAP,
                credential_sha256=hashlib.sha256(secret_text.encode()).hexdigest(),
            )
            if cred.principal_id == p.context.principal_id
            else cred
            for cred in p.m.gen.credentials
        ),
    )
    p.m.a.adapter.controller.protected_request = lambda: nullcontext(p.m.gen)
    sessions = BrowserSessionService(
        p.m.a.authority,
        StaticGenerationAuthenticator(p.m.gen, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=1),
            timedelta(minutes=30),
            timedelta(hours=1),
            timedelta(minutes=5),
        ),
        csrf_signing_key=b"isolated-ontology-test-not-production",
        recovery_epoch=1,
    )
    secret = sessions.create_session(sessions.issue_login_nonce(), secret_text)
    browser, _ = sessions.authenticate_session(secret.value)
    app = create_workbench_bff(
        sessions,
        p.m.a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        grant_administration=p.g,
        route_installers=(install_test_read_access(p.policy, p.g, p.m.a.adapter),),
    )
    prefix = "/api/workbench/v1/test-resource-access"
    headers = {
        "origin": "https://workbench.example",
        "x-csrf-token": sessions.issue_csrf(browser),
    }
    with TestClient(app, base_url="https://workbench.example") as client:
        client.cookies.set("__Host-workbench_session", secret.value)
        response = client.get(prefix + "/status")
        assert response.status_code == 200, response.text
        selected = response.json()["result"]["selectionDigest"]
        with p.m.a.authority.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT 1 FROM authorization_admin.grants "
                    "WHERE subject_principal_id=%s",
                    (p.context.principal_id,),
                ).fetchone()
                is None
            )
        payload = {
            "idempotencyKey": f"published:{selected}:http",
            "expectedSelectionDigest": selected,
        }
        assert client.post(prefix + "/prepare", json=payload).status_code == 403
        first = client.post(prefix + "/prepare", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        assert first.json()["result"]["selectionDigest"] == selected
        release(p, revise(p, published), "two")
        assert (
            client.post(prefix + "/prepare", json=payload, headers=headers).status_code
            == 409
        )
        new = client.get(prefix + "/status").json()["result"]["selectionDigest"]
        retarget = client.post(
            prefix + "/prepare",
            json={**payload, "expectedSelectionDigest": new},
            headers=headers,
        )
        assert retarget.status_code == 422, retarget.text


def test_corrupt_publication_fails_before_any_reader_grant(published_read):
    from agent_console.ontology_domain import OntologyError
    from psycopg.types.json import Jsonb

    p = published_read
    scope = (p.context.scope.tenant_id, p.context.scope.security_domain)
    # Corrupt-storage fixture; no deployed database or disabled guards.
    with p.m.a.authority.connection_scope() as c:
        c.execute(
            "INSERT INTO business_ontology.definitions VALUES (%s,%s,'broken',1,'r1')",
            scope,
        )
        c.execute(
            "INSERT INTO business_ontology.revisions VALUES "
            "(%s,%s,'broken','r1',%s,'fixture',NULL,%s)",
            (*scope, "f" * 64, Jsonb(p.m.content)),
        )
        c.execute(
            "INSERT INTO business_ontology.lifecycle_facts(namespace,security_domain,"
            "ontology_id,revision_id,digest,action,actor,request_key,command_digest,"
            "result) VALUES (%s,%s,'broken','r1',%s,'PUBLISH','fixture',"
            "'corrupt-fixture',%s,'{}')",
            (*scope, "f" * 64, "e" * 64),
        )
    policy = p.policy.model_copy(update={"publishedOntologyIds": ("broken",)})
    with pytest.raises(OntologyError, match="CONTENT_CORRUPT"):
        p.prepare(candidate=policy)
    with p.m.a.authority.connection_scope() as c:
        assert (
            c.execute(
                "SELECT 1 FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s",
                (p.context.principal_id,),
            ).fetchone()
            is None
        )


def test_current_issuer_revocation_blocks_new_publication_read(published_read):
    from agent_console.authority_contracts import CredentialId

    p = published_read
    release(p)
    selected = p.select()
    p.m.gen = replace(
        p.m.gen,
        credential_revocation_tombstones=frozenset({CredentialId("policy-test")}),
    )
    with pytest.raises(AuthorityError):
        p.prepare(selected)
