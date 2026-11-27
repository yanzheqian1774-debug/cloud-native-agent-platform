# ruff: noqa: F401,F811 -- Existing owner fixtures, one shared random database.
"""Joint real Human/Service preparation discovery, controlled provider/Kubernetes.

Both identities are declared before the one active generation is installed.
No execution/admission rows are copied from another database.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace

import pytest
import test_bound_service_execution as service_chain
import test_resource_automation as resources
from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_contracts import GrantSource
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.local_accounts import migrate, operate
from agent_operator.native_host_policy_set import (
    DiscoveryLeaf,
    LeafKind,
    PolicySetDiscovery,
)
from agent_operator.native_host_service_discovery import Discovery
from owned_business_consumer_support import configure_scope, prepare_source
from test_bound_service_execution import case, services
from test_bound_service_execution import repository as service_repository
from test_context_call_admission import env
from test_fixed_chat_delivery_postgres import automation as service_automation
from test_local_accounts_postgres import PASSWORD
from test_owned_business_consumer_chain import (
    adopted,
    cleanup_consumer_resources,
    ordinary,
    owned_created,
    owned_ready,
    routed,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as human_chain,
)


@pytest.fixture
def repository(monkeypatch):
    generator = service_repository.__wrapped__(monkeypatch)
    repo = next(generator)
    from psycopg.conninfo import conninfo_to_dict

    print(
        "JOINT_OWN_DATABASE=" + conninfo_to_dict(repo.pool.conninfo)["dbname"],
        flush=True,
    )
    try:
        yield repo
    finally:
        generator.close()


@pytest.fixture(autouse=True)
def joint_generation(monkeypatch):
    import test_conversation_relation_bff as human_bff
    from agent_console.prepared_execution_schema import expected_version
    from psycopg.rows import dict_row

    original_existing_work = human_bff.existing_work

    def existing_work_in_prepared_database(e, authorizer, sessions):
        # The Service fixture already ran the actual v34 migration. Replaying
        # old foundation SQL would revert its FK; verify and reuse it instead.
        with e.repo.connection_scope() as c, c.cursor(row_factory=dict_row) as cur:
            assert (
                cur.execute(
                    "SELECT version,checksum,adapter FROM "
                    "execution_authority.schema_migrations WHERE version=34"
                ).fetchone()
                == expected_version()
            )
            assert cur.execute(
                "SELECT confrelid::regclass::text AS target FROM pg_constraint "
                "WHERE conname='workflow_runs_plan_fk'"
            ).fetchall() == [{"target": "execution_authority.plan_references"}]
        return original_existing_work(e, authorizer, sessions, initialize_schema=False)

    monkeypatch.setattr(human_bff, "existing_work", existing_work_in_prepared_database)
    now = datetime.now(UTC)
    human = {
        "schemaVersion": "static-authority-generation.v1",
        "generation": 1,
        "policyVersion": "test",
        "auditSource": "isolated-joint-owner",
        "credentials": [],
        "localAccounts": [],
        "requestability": [
            {
                "owner": "PLAN",
                "action": "READ",
                "resourcePrefix": "plan:",
                "purpose": "TEST",
            }
        ],
        "credentialRevocationTombstones": [],
        "staticGrantRevocationTombstones": [],
    }
    for username, role, principal, credential in (
        ("demo324", "requester", "human:demo323-requester", "expired-requester"),
        ("reviewer324", "approver", "human:demo323-approver", "expired-approver"),
        ("devadmin", "approver", "human:development-admin", "independent-admin-source"),
    ):
        grants = (
            [
                {
                    "owner": "GRANT_ADMIN",
                    "action": action,
                    "resource": "grant-scope:s5-323-demo:isolated-real-demo",
                    "source": "STATIC_META",
                }
                for action in ("INSPECT", "DECIDE")
            ]
            if role == "approver"
            else [
                {
                    "owner": "BUSINESS_PROBLEM",
                    "action": "CREATE",
                    "resource": "business-problem:collection",
                    "source": "BROWSER_BOOTSTRAP",
                }
            ]
        )
        human["credentials"].append(
            {
                "credentialId": credential,
                "credentialSha256": sha256(credential.encode()).hexdigest(),
                "principalId": principal,
                "tenantId": "s5-323-demo",
                "securityDomain": "isolated-real-demo",
                "expiresAt": (now - timedelta(hours=1)).isoformat(),
                "authenticationSource": "BROWSER_BOOTSTRAP",
                "grants": grants,
            }
        )
        human["localAccounts"].append(
            {"username": username, "grantSourceCredentialId": credential}
        )
    declared = StaticAuthorityLoader._parse(human, digest="a" * 64)
    original = resources.StaticAuthorityGeneration

    def combined(*args, **kwargs):
        service = original(*args, **kwargs)
        return replace(
            service,
            credentials=(*service.credentials, *declared.credentials),
            local_accounts=declared.local_accounts,
            requestability=(*service.requestability, *declared.requestability),
        )

    monkeypatch.setattr(resources, "StaticAuthorityGeneration", combined)


@pytest.fixture
def automation(
    repository, case, services, tmp_path, request, monkeypatch, joint_generation
):
    yield from service_automation.__wrapped__(
        repository, case, services, tmp_path, request, monkeypatch
    )


@pytest.fixture
def setup(automation):
    a = automation
    repo, generation = a.authority, a.gen
    migrate(repo)
    for account in generation.local_accounts:
        operate(
            repo,
            account,
            action="CREATE",
            command_id="joint-create-" + account.username,
            operator_id="operator:isolated-test",
            now=datetime.now(UTC),
            password=PASSWORD,
        )
    sessions = BrowserSessionService(
        repo,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            timedelta(minutes=5),
            timedelta(minutes=30),
            timedelta(hours=8),
            timedelta(minutes=10),
        ),
        csrf_signing_key=b"a" * 32,
        recovery_epoch=1,
    )
    reader = GenerationAuthorizationReader(generation, repo, repo, recovery_epoch=1)
    return repo, generation, sessions, reader


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
@pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True)
@pytest.mark.parametrize(
    "owned_ready",
    [
        dict(
            mode="SOURCE_SUCCESSOR",
            prepare_source=prepare_source,
            configure_scope=configure_scope,
        )
    ],
    indirect=True,
)
def test_two_original_owners_share_database_generation_and_router(
    owned_created, automation, tmp_path, request, monkeypatch
):
    import pending_pipeline_support

    e = owned_created
    original_drive = pending_pipeline_support.drive
    from agent_console.bound_service_execution import BoundServiceExecutionBridge
    from agent_console.fixed_work_service_continuation import ServiceCycleContinuation

    original_continue = ServiceCycleContinuation.continue_once
    captured = {}

    def continued(owner, call, event):
        result = original_continue(owner, call, event)
        captured["bridge"] = BoundServiceExecutionBridge(owner.registry)
        return result

    monkeypatch.setattr(ServiceCycleContinuation, "continue_once", continued)
    seen = []

    def human_ready(work, native, receipt, ready):
        human = Discovery(
            SimpleNamespace(
                worker=SimpleNamespace(
                    repository=SimpleNamespace(work=work),
                    transport=SimpleNamespace(caller=None),
                ),
                execution_repository=native,
            ),
            (
                e.context.scope.tenant_id,
                e.context.scope.security_domain,
                e.context.principal_id,
            ),
            "joint-db",
        )
        assert len(human.page()) == 1
        assert e.repo.pool.conninfo == automation.authority.pool.conninfo

        def drive(*args, **kwargs):
            def inspect(service_work, service_native, caller):
                service = Discovery(
                    SimpleNamespace(
                        worker=SimpleNamespace(
                            repository=SimpleNamespace(work=service_work),
                            transport=SimpleNamespace(caller=caller),
                        ),
                        execution_repository=service_native,
                    ),
                    (
                        automation.subject.scope.tenant_id,
                        automation.subject.scope.security_domain,
                        automation.subject.principal_id,
                    ),
                    "joint-db",
                )
                router = PolicySetDiscovery(
                    (
                        DiscoveryLeaf(LeafKind.HUMAN_OWNED, human),
                        DiscoveryLeaf(LeafKind.BOUND_SERVICE, service),
                    )
                )
                page = router.page()
                assert {v["principalId"] for v in page} == {
                    e.context.principal_id,
                    automation.subject.principal_id,
                }
                assert len({v["preparationDigest"] for v in page}) == 2
                assert all(router.current(v) == v for v in page)
                assert native.pool.conninfo == service_native.pool.conninfo
                assert (
                    e.repo.active_generation()
                    == automation.authority.active_generation()
                    == (1, "a" * 64, 1)
                )
                from native_policy_set_factory_support import assemble

                # Actual loader + both original builders; no owner is swapped.
                # Static generation input and Kubernetes are explicit fixture ports.
                with monkeypatch.context() as factory_patches:
                    assembly = assemble(
                        tmp_path / "joint-factory",
                        factory_patches,
                        work,
                        service_work,
                        service_work.bound_service_execution.registry.authorization.generation,
                    )
                    try:
                        factory_page = assembly.discovery.page()
                        assert {v["preparationDigest"] for v in factory_page} == {
                            v["preparationDigest"] for v in page
                        }
                        assert all(
                            assembly.discovery.current(v) == v for v in factory_page
                        )
                        assert len(assembly.leaves) == 2
                    finally:
                        assembly.close()
                seen.append(tuple(v["preparationDigest"] for v in page))

            return original_drive(
                *args,
                **kwargs,
                discovery_observer=inspect,
                bound_service_execution=captured["bridge"],
            )

        monkeypatch.setattr(pending_pipeline_support, "drive", drive)
        automation.expected_existing_runs = 1
        service_path = tmp_path / "service"
        service_path.mkdir()
        service_chain.original_chain(automation, monkeypatch, service_path)
        assert len(human.page()) == 1  # Service completion does not consume Human work.

    e.consumer_execution_observer = human_ready
    e.consumer_expected_run_count = 2
    human_chain(e, tmp_path, request)
    assert seen
