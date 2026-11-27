"""Real identity/grant owners; resource-write authorization is controlled."""

import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as N

import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    RequestabilityRule,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthorityError,
    CredentialId,
    ExactGrant,
    GrantSource,
)
from agent_console.browser_session_application import (
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import (
    GenerationAuthorizationReader,
    GrantAdministrationService,
    GrantRevocationCommand,
)
from agent_console.ontology_published_read import resolve
from agent_console.team_definition_postgres import PostgresTeamDefinitionRepository
from agent_console.test_domain_resource_read import require_subject
from agent_console.test_resource_read_access import prepare
from agent_console.test_resource_read_policy import IsolatedDomainTestReadPolicy
from agent_console.workbench_team import TeamTargets
from test_digital_employee_definition import revision
from test_local_accounts_postgres import login
from test_local_accounts_postgres import pytestmark as pytestmark
from test_local_accounts_postgres import setup as setup
from test_team_definition import team

ROOT = Path(__file__).parents[1] / "migrations"


@pytest.fixture
def domain(setup, tmp_path):
    repo, gen, sessions, _ = setup
    scope = gen.local_accounts[0].scope
    secret = "test-only-service-issuer"
    cred = CredentialConfiguration(
        CredentialId("test-domain-issuer"),
        hashlib.sha256(secret.encode()).hexdigest(),
        "service:test-domain-read",
        scope,
        datetime.now(UTC) + timedelta(hours=2),
        GrantSource.SERVICE_ONLY,
        (
            StaticGrant(
                ExactGrant(
                    "GRANT_ADMIN",
                    "DECIDE",
                    f"grant-scope:{scope.tenant_id}:{scope.security_domain}",
                ),
                GrantSource.STATIC_META,
            ),
        ),
    )
    gen = replace(
        gen,
        generation=2,
        digest="d" * 64,
        credentials=(*gen.credentials, cred),
        requestability=(
            *gen.requestability,
            *(
                RequestabilityRule(owner, "READ", prefix, "TEST_DOMAIN_READ")
                for owner, prefix in [("TEAM", "team:"), ("EMPLOYEE", "employee:")]
            ),
        ),
    )
    repo.activate_generation(
        2,
        gen.digest,
        1,
        operator_id="operator:test",
        revoked_credentials=(),
        now=datetime.now(UTC),
    )
    sessions = BrowserSessionService(
        repo,
        StaticGenerationAuthenticator(gen, source=GrantSource.BROWSER_BOOTSTRAP),
        sessions.policy,
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    _, subject = sessions.authenticate_session(login(sessions).value)
    _, other = sessions.authenticate_session(login(sessions, "reviewer324").value)
    with repo.connection_scope() as c:
        for version in range(1, 13):
            c.execute(next(ROOT.glob(f"{version:04d}_*.sql")).read_text())
    teams = PostgresTeamDefinitionRepository(repo.pool)
    teams.migrate(ROOT / "0051_team_definition.sql")
    employees = PostgresEmployeeDefinitionRepository(repo)
    employees.migrate(ROOT / "0014_digital_employee_identity.sql")

    class Targets:
        def is_known_exact_target(self, context, grant, *, connection=None):
            if grant.owner == "TEAM":
                return TeamTargets().is_known_exact_target(
                    context, grant, connection=connection
                )
            return employees.is_known_grant_target_for_workbench(
                connection,
                ScopeIdentity(context.scope.tenant_id, context.scope.security_domain),
                grant.action,
                grant.exact_resource,
            )

    grants = GrantAdministrationService(
        repo,
        GenerationAuthorizationReader(gen, repo, repo, recovery_epoch=1),
        gen,
        continuation_owner=None,
        recovery_epoch=1,
        target_validator=Targets(),
    )
    t = replace(team(), scope=ScopeIdentity(scope.tenant_id, scope.security_domain))
    emp = replace(revision(), scope=t.scope)
    with repo.connection_scope() as c:
        teams.save(
            c,
            t,
            expected_version=0,
            command_id="team-create",
            actor_id=subject.principal_id,
            decision_id="controlled-authorized-team-create",
        )
        employees.create_for_workbench(
            c,
            emp,
            expected_version=0,
            decision_id="controlled-authorized-employee-create",
            command_id="employee-create",
            authorized=True,
        )
    path = tmp_path / "issuer"
    path.write_text(secret)
    path.chmod(0o600)
    policy = IsolatedDomainTestReadPolicy(
        schemaVersion="test-resource-read-policy.v5",
        policyId="test-domain",
        policyVersion="v5",
        enabled=True,
        tenant=scope.tenant_id,
        securityDomain=scope.security_domain,
        subjects=(subject.principal_id,),
        issuer=cred.principal_id,
        credentialPath=path,
        expiresAt=datetime.now(UTC) + timedelta(hours=1),
        grantTTLSeconds=120,
        targets=[
            dict(
                owner="TEAM",
                action="READ",
                resource=f"team:{t.team_id}:{t.revision_id}",
                digest=t.content_digest,
                purpose="TEST_DOMAIN_READ",
            )
        ],
        publishedResources=[],
        testDomainMode="ISOLATED_TEST_DOMAIN",
        shareWithCurrentLocalHumans=True,
        enrolledResources=[dict(kind="employee", logicalId=emp.definition_id)],
        registeredResources=[
            dict(kind="team", mode="CREATOR_ONLY", purpose="TEST_DOMAIN_READ"),
            dict(
                kind="employee",
                mode="ISOLATED_TEST_DOMAIN_SHARE",
                purpose="TEST_DOMAIN_READ",
            ),
        ],
    )

    def selected(who=subject, candidate=policy):
        with repo.connection_scope() as c:
            candidate.authenticate(grants, who)
            require_subject(candidate, grants, who, c)
            return resolve(candidate, who, c)

    def run(selection=None, key=None, who=subject, candidate=policy):
        selection = selection or selected(who, candidate)
        with repo.connection_scope() as c:
            return prepare(
                candidate,
                grants,
                who,
                c,
                key or "published:" + selection.digest + ":original",
                selection.digest,
            )

    return N(
        repo=repo,
        grants=grants,
        subject=subject,
        other=other,
        teams=teams,
        employees=employees,
        t=t,
        emp=emp,
        policy=policy,
        selected=selected,
        run=run,
        sessions=sessions,
    )


def test_create_success_then_read_prepare_and_same_key(domain):
    e = domain
    s = e.selected()
    assert {t.owner for t in s.targets} == {"TEAM", "EMPLOYEE"}
    result = e.run(s)
    assert e.run(s) == result
    assert all(x["state"] in {"APPROVED", "EFFECTIVE"} for x in result["items"])
    # Explicit Employee sharing; creator-only Team excludes the other actor.
    other = e.selected(e.other)
    assert [t.owner for t in other.targets] == ["EMPLOYEE"]
    assert e.run(other, who=e.other)["items"]


def test_new_head_invalidates_key_and_revocation_blocks_successor(domain):
    e = domain
    s = e.selected()
    first = e.run(s)
    target = f"team:{e.t.team_id}:{e.t.revision_id}"
    request = next(i["requestId"] for i in first["items"] if i["resource"] == target)
    with e.repo.connection_scope() as c:
        grant = c.execute(
            "SELECT grant_id FROM authorization_admin.grants WHERE request_id=%s",
            (request,),
        ).fetchone()["grant_id"]
    e.grants.revoke_grant(
        e.subject, GrantRevocationCommand(grant, "USER_REQUESTED", "surrender", True)
    )
    successor = replace(
        e.t, revision_id="new-team-revision", predecessor_revision_id=e.t.revision_id
    )
    with e.repo.connection_scope() as c:
        e.teams.save(
            c,
            successor,
            expected_version=1,
            command_id="revise",
            actor_id=e.subject.principal_id,
            decision_id="controlled-team-revise",
        )
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        e.run(s)
    latest = e.run()
    assert any(
        i["state"] == "REVOKED" and i["resource"].endswith("new-team-revision")
        for i in latest["items"]
    )


def test_wrong_scope_and_account_revoked_close_before_grants(domain):
    e = domain
    with pytest.raises(AuthorityError):
        e.run(
            who=replace(
                e.subject, scope=replace(e.subject.scope, security_domain="other")
            )
        )
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
    from agent_console.local_accounts import operate

    operate(
        e.repo,
        e.grants.generation.local_accounts[0],
        action="DISABLE",
        command_id="disable-user",
        operator_id="operator:test",
        now=datetime.now(UTC),
    )
    with pytest.raises(AuthorityError):
        e.run()
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == before
        )


def test_employee_successor_is_readable_and_lost_receipt_does_not_reissue(domain):
    e = domain
    old = e.selected()
    first = e.run(old)
    successor = replace(
        e.emp, revision_id="employee-next", predecessor_revision_id=e.emp.revision_id
    )
    with e.repo.connection_scope() as c:
        e.employees.create_for_workbench(
            c,
            successor,
            expected_version=1,
            decision_id="controlled-employee-revise",
            command_id="employee-revise",
            authorized=True,
        )
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        e.run(old)
    current = e.selected()
    e.run(current)  # response intentionally discarded after commit
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM authorization_admin.grant_decisions"
        ).fetchone()["n"]
    restored = e.run(current)
    assert any(
        i["resource"].endswith("employee-next")
        and i["state"] in {"APPROVED", "EFFECTIVE"}
        for i in restored["items"]
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grant_decisions"
            ).fetchone()["n"]
            == before
        )
    assert first


@pytest.mark.parametrize("identity_kind", ["local", "orphan", "other"])
def test_old_lineage_identity_tombstone_blocks_new_head(domain, identity_kind):
    e = domain
    successor = replace(
        e.t, revision_id="next", predecessor_revision_id=e.t.revision_id
    )
    with e.repo.connection_scope() as c:
        e.teams.save(
            c,
            successor,
            expected_version=1,
            command_id="next",
            actor_id=e.subject.principal_id,
            decision_id="controlled",
        )
    identity = (
        e.grants.generation.local_accounts[0].credential_id
        if identity_kind == "local"
        else CredentialId("removed-unknown-identity")
    )
    if identity_kind == "other":
        identity = next(
            a.credential_id
            for a in e.grants.generation.local_accounts
            if a.principal_id != e.subject.principal_id and a.scope == e.subject.scope
        )
    target = ExactGrant("TEAM", "READ", f"team:{e.t.team_id}:{e.t.revision_id}")
    injected_generation = replace(
        e.grants.generation,
        static_grant_revocation_tombstones=frozenset({(identity, target)}),
    )
    e.grants._generation_provider = lambda: injected_generation
    if identity_kind == "orphan":
        with pytest.raises(AuthorityError, match="LINEAGE_IDENTITY_UNVERIFIED"):
            e.run()
        with e.repo.connection_scope() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM authorization_admin.grant_requests"
                ).fetchone()["n"]
                == 0
            )
    else:
        result = e.run()
        assert any(
            x["resource"].endswith(":next")
            and x["state"] == ("APPROVED" if identity_kind == "other" else "REVOKED")
            for x in result["items"]
        )


def test_explicit_denial_is_not_replaced_by_read_preparation(domain):
    from agent_console.grant_administration_application import (
        GrantDecisionCommand,
        GrantRequestCommand,
    )

    e = domain
    target = e.policy.targets[0]
    issuer, _ = e.policy.authenticate(e.grants, e.subject)
    req = e.grants.submit_request(
        e.subject, GrantRequestCommand(target.purpose, (target.grant,), "deny-request")
    )
    e.grants.decide_request(
        issuer,
        GrantDecisionCommand(
            req.request_id,
            False,
            "CONTROLLED_REVIEW",
            "POLICY",
            "test denial",
            None,
            None,
            "deny",
            expected_version=1,
        ),
    )
    result = e.run()
    assert any(
        x["resource"] == target.resource and x["state"] == "DENIED"
        for x in result["items"]
    )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.grants WHERE owner='TEAM'"
            ).fetchone()["n"]
            == 0
        )


def test_head_share_lock_serializes_new_revision(domain):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    e = domain
    entered = Event()
    successor = replace(
        e.t, revision_id="concurrent-next", predecessor_revision_id=e.t.revision_id
    )

    def change():
        with e.repo.connection_scope() as c:

            class Marked:
                def execute(self, sql, args=None):
                    if "FOR UPDATE" in sql:
                        entered.set()
                    return c.execute(sql, args)

            e.teams.save(
                Marked(),
                successor,
                expected_version=1,
                command_id="concurrent",
                actor_id=e.subject.principal_id,
                decision_id="controlled",
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        with e.repo.connection_scope() as c:
            e.policy.authenticate(e.grants, e.subject)
            require_subject(e.policy, e.grants, e.subject, c)
            before = resolve(e.policy, e.subject, c)
            future = pool.submit(change)
            assert entered.wait(3)
            assert not future.done()
        future.result(timeout=5)
    assert e.selected().digest != before.digest
    with pytest.raises(AuthorityError, match="SELECTION_CHANGED"):
        e.run(before)


def test_published_employee_and_new_draft_are_distinct_read_targets(
    domain, monkeypatch
):
    e = domain
    # Real immutable lifecycle writer; member availability is a controlled port.
    monkeypatch.setattr(e.employees, "validate_members", lambda *args: None)
    with e.repo.connection_scope() as c:
        for version, action in enumerate(("VALIDATE", "APPROVE", "PUBLISH"), 1):
            e.employees.decide_for_workbench(
                c,
                e.emp.scope,
                e.emp.definition_id,
                e.emp.revision_id,
                e.emp.digest,
                action,
                expected_version=version,
                decision_id="controlled-" + action,
                command_id="employee-" + action,
                authorized=True,
            )
        draft = replace(
            e.emp,
            revision_id="draft-after-publication",
            predecessor_revision_id=e.emp.revision_id,
        )
        e.employees.create_for_workbench(
            c,
            draft,
            expected_version=4,
            decision_id="controlled-new-draft",
            command_id="new-draft",
            authorized=True,
        )
    result = e.run()
    resources = {
        item["resource"]
        for item in result["items"]
        if item["resource"].startswith("employee:")
    }
    assert resources == {
        f"employee:{e.emp.definition_id}:{e.emp.revision_id}",
        f"employee:{draft.definition_id}:{draft.revision_id}",
    }


def test_unenrolled_private_employee_and_team_are_not_shared(domain):
    e = domain
    hidden = replace(e.emp, definition_id="employee:private-unenrolled")
    with e.repo.connection_scope() as c:
        e.employees.create_for_workbench(
            c,
            hidden,
            expected_version=0,
            decision_id="controlled-private",
            command_id="private-create",
            authorized=True,
        )
    shared = e.policy.model_dump(mode="json")
    shared["registeredResources"][0]["mode"] = "ISOLATED_TEST_DOMAIN_SHARE"
    shared["enrolledResources"].append(
        {"kind": "team", "logicalId": "team:explicit-other"}
    )
    policy = IsolatedDomainTestReadPolicy.model_validate(shared)
    selection = e.selected(e.other, policy)
    resources = {t.resource for t in selection.targets}
    assert not any(hidden.definition_id in resource for resource in resources)
    # Static root stays explicit; dynamic selection cannot add an unlisted successor.
    successor = replace(
        e.t, revision_id="unlisted-successor", predecessor_revision_id=e.t.revision_id
    )
    with e.repo.connection_scope() as c:
        e.teams.save(
            c,
            successor,
            expected_version=1,
            command_id="unlisted-save",
            actor_id=e.subject.principal_id,
            decision_id="controlled",
        )
    result = e.run(who=e.other, candidate=policy)
    assert not any(
        "unlisted-successor" in row["resource"]
        or hidden.definition_id in row["resource"]
        for row in result["items"]
    )
