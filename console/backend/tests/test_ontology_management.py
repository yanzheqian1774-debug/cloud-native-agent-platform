# ruff: noqa: F401,F811,E501 -- Shared disposable PostgreSQL fixtures and exact SQL.
"""Real grant owner + ontology owner in isolated PG; no deployed environment."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_configuration import RequestabilityRule, StaticGrant
from agent_console.authority_contracts import AuthorityError, ExactGrant, GrantSource
from agent_console.ontology_authorization import OntologyTargets
from agent_console.ontology_domain import OntologyError
from agent_console.ontology_management import OntologyManagement
from agent_console.ontology_management_policy import MaintenancePolicy, MaintenanceScope
from agent_console.ontology_postgres import migrate
from agent_console.ontology_sales_sample import sales_content
from agent_console.ontology_service import OntologyService, resource
from agent_console.sales_diagnostic_skill import SalesDiagnosticSkillExecutor
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation

ACTIONS = ("CREATE", "REVISE", "VALIDATE", "TEST", "REVIEW", "PUBLISH", "DEPRECATE")


@pytest.fixture
def maintained(automation):
    a = automation
    g = a.automation.grants
    deps = tuple(
        StaticGrant(
            ExactGrant(
                owner,
                "READ_RESOURCE",
                prefix + a.refs[kind].resource_id + ":" + a.refs[kind].revision_id,
            ),
            GrantSource.SERVICE_ONLY,
        )
        for owner, prefix, kind in (
            ("KNOWLEDGE", "knowledge:prepared-resource:", "knowledge"),
            ("SKILL", "skill-invocation:prepared-resource:", "skill"),
        )
    )
    user = replace(a.gen.credentials[0], grants=a.gen.credentials[0].grants + deps)
    reviewer = replace(
        user,
        credential_id="reviewer-test",
        principal_id="human:independent-reviewer",
        credential_sha256="e" * 64,
    )
    gen = replace(
        a.gen,
        credentials=(user, a.gen.credentials[1], reviewer),
        requestability=a.gen.requestability
        + tuple(
            RequestabilityRule(
                "BUSINESS_ONTOLOGY",
                action,
                "business-ontology:",
                "ONTOLOGY_MAINTENANCE",
            )
            for action in (*ACTIONS, "READ")
        ),
    )
    g._generation_provider = lambda: gen
    g.authorization._generation_provider = lambda: gen
    g.target_validator.additional += (OntologyTargets(),)
    with a.repository.pool.connection() as c, c.transaction():
        migrate(c)
    scopes = tuple(
        MaintenanceScope(
            namespace=a.subject.scope.tenant_id,
            securityDomain=a.subject.scope.security_domain,
            subject=subject,
            ontologyIds=("managed-sales",),
            actions=ACTIONS,
            expiresAt=g.clock() + timedelta(hours=1),
        )
        for subject in (a.subject.principal_id, reviewer.principal_id)
    )
    policy = MaintenancePolicy(
        enabled=True,
        policyId="isolated-ontology",
        policyVersion="1",
        issuer=a.policy.issuer,
        credentialPath=a.policy.credentialPath,
        workScopes=scopes,
    )
    content = sales_content(
        a.e.source,
        a.refs["knowledge"].model_dump(mode="json"),
        a.refs["skill"].model_dump(mode="json"),
        SalesDiagnosticSkillExecutor.revision,
    )
    manager = OntologyManagement(policy, g)
    return SimpleNamespace(
        a=a,
        manager=manager,
        gen=gen,
        content=content.model_dump(mode="json"),
        reviewer=reviewer,
    )


def run(m, payload=None, *, subject=None, read=None, raw=None, generation=1):
    a = m.a
    subject = subject or a.subject
    with a.authority.connection_scope() as c:
        authority = AuthorizedOwnerAuthority(a.adapter, subject, c, generation, ())
        call = AuthorizedOwnerCall(
            "ONTOLOGY_MAINTENANCE",
            subject,
            c,
            payload or {},
            {},
            {},
            (),
            authority,
            generation,
            1,
        )
        if read:
            return m.manager.receipt(call, read)
        if raw:
            return OntologyService(call).handle(raw[0], "managed-sales", raw[1])
        return m.manager.handle(call)


def create(m, key="create-command-1"):
    return run(
        m,
        dict(
            action="CREATE",
            commandKey=key,
            ontologyId="managed-sales",
            expectedVersion=0,
            content=m.content,
            reason="isolated actual owner creation",
        ),
    )


def payload(m, result, action, key):
    v = result["outcome"]
    return dict(
        action=action,
        commandKey=key,
        ontologyId=v["ontology_id"],
        expectedVersion=v["version"],
        revision=v["revision_id"],
        digest=v["digest"],
        reason="isolated actual lifecycle",
    )


def admission(m, key="create-command-1"):
    from agent_console.ontology_maintenance_binding import command_key

    with m.a.authority.connection_scope() as c:
        return c.execute(
            "SELECT result FROM execution_authority.prepared_resource_commands WHERE command_key=%s",
            (command_key(key),),
        ).fetchone()["result"]


def grant_read(m, subject, revision, identity="managed-sales"):
    # Explicit fixture-only static READ, independent of maintenance write grants.
    grant = StaticGrant(
        ExactGrant("BUSINESS_ONTOLOGY", "READ", resource(identity, revision)),
        GrantSource.SERVICE_ONLY,
    )
    m.gen = replace(
        m.gen,
        credentials=tuple(
            replace(cred, grants=(*cred.grants, grant))
            if cred.principal_id == subject.principal_id
            else cred
            for cred in m.gen.credentials
        ),
    )
    m.manager.grants._generation_provider = lambda: m.gen
    m.manager.grants.authorization._generation_provider = lambda: m.gen


def test_managed_owner_full_lifecycle_precise_sources_and_independent_review(
    maintained,
):
    m = maintained
    first = create(m)
    assert first["outcome"]["revision_id"].startswith("managed-")
    assert create(m) == first
    result = first
    for action in ("VALIDATE", "TEST"):
        result = run(m, payload(m, result, action, "step-" + action))
    with pytest.raises(OntologyError, match="INDEPENDENT_REVIEW"):
        run(m, payload(m, result, "REVIEW", "bad-review-1"))
    reviewer = replace(
        m.a.subject,
        principal_id=m.reviewer.principal_id,
        session_id_or_service_credential_id=m.reviewer.credential_id,
    )
    grant_read(m, reviewer, result["outcome"]["revision_id"])
    result = run(m, payload(m, result, "REVIEW", "good-review-1"), subject=reviewer)
    result = run(m, payload(m, result, "PUBLISH", "good-publish-1"))
    assert result["outcome"]["state"] == "PUBLISH"
    assert result["modelCalls"] == 0 and result["executionStarted"] is False
    with m.a.authority.connection_scope() as c:
        rows = c.execute(
            "SELECT owner,action FROM authorization_admin.grants WHERE owner='BUSINESS_ONTOLOGY'"
        ).fetchall()
    assert rows and all(r["action"] not in {"USE", "EXECUTE"} for r in rows)


def test_revision_binding_blocks_raw_route_swapped_content_actor_key_and_stale_base(
    maintained,
):
    m = maintained
    first = create(m)
    old = admission(m)
    raw = dict(old["ownerCommand"])
    raw["content"] = {**raw["content"], "name": "substitution"}
    with pytest.raises(OntologyError, match="BINDING_MISMATCH"):
        run(m, raw=("CREATE", raw))
    raw = {**old["ownerCommand"], "request_key": "escape-old-route"}
    with pytest.raises(OntologyError, match="BINDING_MISMATCH"):
        run(m, raw=("CREATE", raw))
    changed = dict(
        action="REVISE",
        commandKey="revise-command-1",
        ontologyId="managed-sales",
        expectedVersion=first["outcome"]["version"],
        baseRevision=first["outcome"]["revision_id"],
        baseDigest=first["outcome"]["digest"],
        content={**m.content, "name": "new definition"},
        reason="isolated revise",
    )
    with pytest.raises(OntologyError, match="BASE_INVALID"):
        run(m, {**changed, "baseDigest": "f" * 64})
    second = run(m, changed)
    assert second["outcome"]["revision_id"] != first["outcome"]["revision_id"]
    with pytest.raises(OntologyError, match="COMMAND_CONFLICT"):
        run(m, {**changed, "content": m.content})
    with pytest.raises(OntologyError, match="VERSION_CONFLICT"):
        run(m, {**changed, "commandKey": "stale-revise-2"})


def test_business_reader_foreign_scope_and_disabled_policy_cannot_write(maintained):
    m = maintained
    first = create(m)
    outsider = replace(m.a.subject, principal_id="human:reader")
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(m, payload(m, first, "VALIDATE", "reader-test-1"), subject=outsider)
    foreign = replace(
        m.a.subject, scope=replace(m.a.subject.scope, security_domain="foreign")
    )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(m, payload(m, first, "VALIDATE", "foreign-test-1"), subject=foreign)
    m.manager.policy = m.manager.policy.model_copy(update={"enabled": False})
    with pytest.raises(AuthorityError, match="DISABLED"):
        create(m)


def test_historical_receipt_read_survives_expired_write_policy_without_write_eligibility(
    maintained,
):
    m = maintained
    first = create(m)
    grant_read(m, m.a.subject, first["outcome"]["revision_id"])
    m.manager.policy = m.manager.policy.model_copy(
        update={
            "workScopes": tuple(
                s.model_copy(
                    update={
                        "expiresAt": m.manager.grants.clock() - timedelta(seconds=1)
                    }
                )
                for s in m.manager.policy.workScopes
            )
        }
    )
    old = run(m, read="create-command-1")
    assert old["outcome"] == first["outcome"] and old["writeEligible"] is False
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        create(m)
    with pytest.raises(Exception, match="NOT_FOUND"):
        run(
            m,
            read="create-command-1",
            subject=replace(m.a.subject, principal_id="human:foreign-reader"),
        )


def test_revoked_write_denies_replay_but_current_read_keeps_receipt(maintained):
    from agent_console.authority_contracts import GrantId
    from agent_console.grant_administration_application import GrantRevocationCommand

    m = maintained
    first = create(m)
    with m.a.authority.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE owner='BUSINESS_ONTOLOGY' AND action='CREATE'"
        ).fetchone()["grant_id"]
    m.manager.grants.revoke_grant(
        m.a.subject,
        GrantRevocationCommand(
            GrantId(grant), "USER_REQUESTED", "revoked-maintenance-create", True
        ),
    )
    with pytest.raises(AuthorityError):
        create(m)
    old = run(m, read="create-command-1")
    assert old["outcome"] == first["outcome"] and old["writeEligible"] is False
    raw = admission(m)["ownerCommand"]
    with pytest.raises(AuthorityError):
        run(m, raw=("CREATE", raw))


def test_generation_change_rejects_old_managed_owner_command(maintained):
    m = maintained
    create(m)
    raw = admission(m)["ownerCommand"]
    # Preserve explicit current READ for history, not the previous write lease.
    m.gen = replace(m.gen, generation=2, digest="b" * 64)
    m.manager.grants._generation_provider = lambda: m.gen
    m.manager.grants.authorization._generation_provider = lambda: m.gen
    with pytest.raises((AuthorityError, OntologyError)):
        run(m, raw=("CREATE", raw), generation=2)
    with pytest.raises(
        AuthorityError, match=r"GENERATION_CHANGED|AUTHORIZATION_NOT_FOUND"
    ):
        create(m)


def test_http_actual_owners_csrf_input_identity_and_historical_read(maintained):
    from contextlib import nullcontext

    from agent_console.ontology_management_api import install_ontology_management
    from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
    from fastapi.testclient import TestClient
    from test_workbench_bff import SessionStub

    m = maintained
    a = m.a
    a.adapter.controller.protected_request = lambda: nullcontext(
        SimpleNamespace(generation=1)
    )
    s = SessionStub()
    s.context = a.subject
    app = create_workbench_bff(
        s,
        a.adapter,
        WorkbenchBffPolicy("workbench.example", "https://workbench.example"),
        route_installers=(install_ontology_management(m.manager, a.adapter),),
    )
    body = dict(
        action="CREATE",
        commandKey="http-create-ontology",
        ontologyId="managed-sales",
        expectedVersion=0,
        content=m.content,
        reason="HTTP controlled owner",
    )
    with TestClient(app, base_url="https://workbench.example") as client:
        root = "/api/workbench/v1/ontology-maintenance/commands"
        assert client.get(root + "/http-create-ontology").status_code == 401
        client.cookies.set("__Host-workbench_session", s.secret)
        caps = client.get(
            "/api/workbench/v1/ontology-maintenance/capabilities/managed-sales"
        ).json()["result"]
        assert caps["allowedActions"] == list(ACTIONS)
        assert (
            client.get(
                "/api/workbench/v1/ontology-maintenance/capabilities/foreign"
            ).json()["result"]["allowedActions"]
            == []
        )
        assert client.post(root, json=body).status_code == 403
        headers = {"Origin": "https://workbench.example", "X-CSRF-Token": "csrf-token"}
        assert (
            client.post(
                root, json={**body, "actor": "human:forged"}, headers=headers
            ).status_code
            == 422
        )
        response = client.post(root, json=body, headers=headers)
        assert response.status_code == 200, response.text
        assert client.get(root + "/http-create-ontology").json() == response.json()
        m.manager.policy = m.manager.policy.model_copy(update={"enabled": False})
        assert (
            client.get(
                "/api/workbench/v1/ontology-maintenance/capabilities/managed-sales"
            ).json()["result"]["allowedActions"]
            == []
        )
        historical = client.get(root + "/http-create-ontology")
        assert historical.status_code == 200
        assert historical.json()["result"]["writeEligible"] is False
        assert client.post(root, json=body, headers=headers).status_code in (403, 404)


def test_expired_exact_write_is_not_renewed_and_receipt_stays_readable(maintained):
    import time
    from datetime import datetime

    m = maintained
    m.manager.policy = m.manager.policy.model_copy(
        update={
            "workScopes": tuple(
                s.model_copy(
                    update={
                        "expiresAt": m.manager.grants.clock() + timedelta(seconds=3)
                    }
                )
                for s in m.manager.policy.workScopes
            )
        }
    )
    first = create(m)
    grant_read(m, m.a.subject, first["outcome"]["revision_id"])
    record = admission(m)
    time.sleep(
        max(
            0,
            (
                datetime.fromisoformat(record["expiresAt"]) - m.manager.grants.clock()
            ).total_seconds(),
        )
        + 0.05
    )
    assert run(m, read="create-command-1")["writeEligible"] is False
    with pytest.raises(AuthorityError):
        create(m)
    with pytest.raises((AuthorityError, OntologyError)):
        run(m, raw=("CREATE", record["ownerCommand"]))
    with m.a.authority.connection_scope() as c:
        count = c.execute(
            "SELECT count(*) AS count FROM business_ontology.lifecycle_facts WHERE action='CREATE'"
        ).fetchone()["count"]
    assert count == 1


def test_exact_admission_cannot_be_used_by_other_actor_even_with_test_write_grant(
    maintained,
):
    m = maintained
    first = create(m)
    record = admission(m)
    reviewer = replace(
        m.a.subject,
        principal_id=m.reviewer.principal_id,
        session_id_or_service_credential_id=m.reviewer.credential_id,
    )
    target = resource("managed-sales", first["outcome"]["revision_id"])
    write = StaticGrant(
        ExactGrant("BUSINESS_ONTOLOGY", "CREATE", target), GrantSource.SERVICE_ONLY
    )
    m.gen = replace(
        m.gen,
        credentials=tuple(
            replace(cred, grants=(*cred.grants, write))
            if cred.principal_id == reviewer.principal_id
            else cred
            for cred in m.gen.credentials
        ),
    )
    m.manager.grants._generation_provider = lambda: m.gen
    m.manager.grants.authorization._generation_provider = lambda: m.gen
    with pytest.raises(OntologyError, match="BINDING_MISMATCH"):
        run(m, raw=("CREATE", record["ownerCommand"]), subject=reviewer)


def test_concurrent_successors_use_same_head_cas_and_leave_no_orphan_admission(
    maintained,
):
    from concurrent.futures import ThreadPoolExecutor

    m = maintained
    first = create(m)["outcome"]
    base = dict(
        action="REVISE",
        ontologyId="managed-sales",
        expectedVersion=first["version"],
        baseRevision=first["revision_id"],
        baseDigest=first["digest"],
        content={**m.content, "name": "concurrent successor"},
        reason="isolated concurrent revise",
    )

    def attempt(key):
        try:
            return run(m, {**base, "commandKey": key})["outcome"]["state"]
        except OntologyError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(attempt, ("concurrent-revise-a", "concurrent-revise-b"))
        )
    assert sorted(outcomes) == ["ONTOLOGY_VERSION_CONFLICT", "REVISE"]
    with m.a.authority.connection_scope() as c:
        facts = c.execute(
            "SELECT count(*) AS count FROM business_ontology.lifecycle_facts"
        ).fetchone()["count"]
        admissions = c.execute(
            "SELECT count(*) AS count FROM execution_authority.prepared_resource_commands WHERE result->>'schemaVersion'='ontology-maintenance-admission.v1'"
        ).fetchone()["count"]
    assert facts == admissions == 2


def controlled_creation_scopes(m):
    user, reviewer = m.manager.policy.workScopes
    m.manager.policy = m.manager.policy.model_copy(
        update={
            "workScopes": (
                user.model_copy(
                    update={
                        "ontologyIds": (),
                        "createPrefix": "managed-new-",
                        "actions": (
                            "CREATE",
                            "REVISE",
                            "VALIDATE",
                            "TEST",
                            "REVIEW",
                            "PUBLISH",
                        ),
                    }
                ),
                reviewer.model_copy(
                    update={
                        "ontologyIds": (),
                        "createPrefix": "managed-new-",
                        "actions": ("REVIEW",),
                        "createdBySubjects": (m.a.subject.principal_id,),
                    }
                ),
            )
        }
    )
    return replace(
        m.a.subject,
        principal_id=m.reviewer.principal_id,
        session_id_or_service_credential_id=m.reviewer.credential_id,
    )


def test_controlled_new_definition_full_lifecycle_and_explicit_independent_review(
    maintained,
):
    m = maintained
    reviewer = controlled_creation_scopes(m)
    result = run(
        m,
        dict(
            action="CREATE",
            commandKey="bounded-create-new-1",
            ontologyId="managed-new-fresh",
            expectedVersion=0,
            content=m.content,
            reason="new scoped definition",
        ),
    )
    with m.a.authority.connection_scope() as c:
        call = AuthorizedOwnerCall(
            "READ",
            m.a.subject,
            c,
            {},
            {},
            {},
            (),
            AuthorizedOwnerAuthority(m.a.adapter, m.a.subject, c, 1, ()),
            1,
            1,
        )
        caps = m.manager.capabilities(call, "managed-new-fresh")
    assert "VALIDATE" in caps["allowedActions"] and "PUBLISH" in caps["allowedActions"]
    assert "REVIEW" not in caps["allowedActions"]
    for action in ("VALIDATE", "TEST"):
        result = run(m, payload(m, result, action, "bounded-new-" + action))
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(m, payload(m, result, "REVIEW", "bounded-self-review"))
    with pytest.raises(AuthorityError):
        run(
            m,
            payload(m, result, "REVIEW", "review-missing-exact-read"),
            subject=reviewer,
        )
    grant_read(
        m, reviewer, result["outcome"]["revision_id"], identity="managed-new-fresh"
    )
    result = run(
        m, payload(m, result, "REVIEW", "bounded-independent-review"), subject=reviewer
    )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(
            m,
            payload(m, result, "PUBLISH", "reviewer-cannot-publish"),
            subject=reviewer,
        )
    result = run(m, payload(m, result, "PUBLISH", "bounded-original-publish"))
    assert result["outcome"]["state"] == "PUBLISH"


def test_prefix_never_takes_legacy_or_other_creators_definition_and_review_is_explicit(
    maintained,
):
    m = maintained
    reviewer = controlled_creation_scopes(m)
    first = run(
        m,
        dict(
            action="CREATE",
            commandKey="bounded-other-create",
            ontologyId="managed-new-owned",
            expectedVersion=0,
            content=m.content,
            reason="proved original creator",
        ),
    )
    original_scopes = m.manager.policy.workScopes
    # A different subject with the same prefix and all actions cannot claim ownership.
    other = original_scopes[1].model_copy(
        update={"actions": ACTIONS, "createdBySubjects": ()}
    )
    m.manager.policy = m.manager.policy.model_copy(
        update={"workScopes": (original_scopes[0], other)}
    )
    for action in ("VALIDATE", "REVIEW", "PUBLISH"):
        with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
            run(
                m, payload(m, first, action, "other-prefix-" + action), subject=reviewer
            )
    # Existing legacy CREATE has an actual owner fact, but no managed admission.
    from agent_console.ontology_domain import OntologyCommand
    from agent_console.ontology_postgres import PostgresOntologyRepository

    with m.a.authority.connection_scope() as c:
        PostgresOntologyRepository(c).command(
            (m.a.subject.scope.tenant_id, m.a.subject.scope.security_domain),
            m.a.subject.principal_id,
            "managed-new-legacy",
            "CREATE",
            OntologyCommand(
                request_key="legacy-create-fixture",
                expected_version=0,
                revision_id="legacy-r1",
                content=m.content,
                reason="explicit legacy owner fixture",
            ),
        )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(
            m,
            dict(
                action="VALIDATE",
                commandKey="try-legacy-prefix",
                ontologyId="managed-new-legacy",
                expectedVersion=1,
                revision="legacy-r1",
                digest="a" * 64,
                reason="not proven managed creator",
            ),
        )
    # An admission-shaped row without a successful owner CREATE never proves ownership.
    from agent_console.resource_use_domain import canonical_digest
    from psycopg.types.json import Jsonb

    fake = admission(m, "bounded-other-create")
    fake = {**fake, "ontologyId": "managed-new-uncommitted"}
    with m.a.authority.connection_scope() as c:
        c.execute(
            "INSERT INTO execution_authority.prepared_resource_commands(namespace,security_domain,actor_id,command_key,digest,result) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                m.a.subject.scope.tenant_id,
                m.a.subject.scope.security_domain,
                m.a.subject.principal_id,
                "isolated-uncommitted-fixture",
                canonical_digest(fake),
                Jsonb(fake),
            ),
        )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(
            m,
            dict(
                action="VALIDATE",
                commandKey="uncommitted-proof-test",
                ontologyId="managed-new-uncommitted",
                expectedVersion=1,
                revision="uncommitted",
                digest="a" * 64,
                reason="no successful owner fact",
            ),
        )
    # Even proven creator cannot rely on a historical lease after current scope expires.
    m.manager.policy = m.manager.policy.model_copy(
        update={
            "workScopes": tuple(
                s.model_copy(
                    update={
                        "expiresAt": m.manager.grants.clock() - timedelta(seconds=1)
                    }
                )
                for s in original_scopes
            )
        }
    )
    with pytest.raises(AuthorityError, match="SCOPE_DENIED"):
        run(m, payload(m, first, "VALIDATE", "expired-creator-policy"))
