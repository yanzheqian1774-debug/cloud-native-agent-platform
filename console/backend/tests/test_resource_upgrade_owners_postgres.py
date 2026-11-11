# ruff: noqa: F401,F811 -- Reuse isolated PostgreSQL fixtures, never production data.
"""Three real owners on PostgreSQL; seed facts/grants are explicit test setup.

Does not claim HTTP or browser acceptance. Execution uses actual authority reads,
resource test gates and lifecycle repositories, without replacing owner methods.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
import test_workbench_employee_commands_postgres as grants_fixture
from agent_console.authority_contracts import ExactGrant
from agent_console.business_capability import (
    BindingKind,
    CapabilityBinding,
    FixedReference,
)
from agent_console.business_capability_postgres import (
    PostgresBusinessCapabilityRepository,
)
from agent_console.business_capability_publication import change_preview
from agent_console.business_capability_publication_postgres import (
    CapabilityPublicationRepository,
)
from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.resource_management import target
from agent_console.resource_upgrade_batch_postgres import UpgradeBatchRepository
from agent_console.resource_upgrade_coordinator import SelectedUpgradeCoordinator
from agent_console.resource_upgrade_owners import (
    CapabilityPublication,
    EmployeePublication,
    SelectedUpgradeOwners,
)
from agent_console.resource_upgrade_preview import (
    ConsumerSelection,
    SelectedUpgradePreview,
    UpgradeSelection,
)
from agent_console.resource_upgrade_selection import (
    SelectedReplacement,
    capability_successor,
    employee_successor,
)
from agent_console.workbench_business_capability import (
    CapabilityOwner,
    CapabilityReferences,
)
from agent_console.workbench_business_problem import OwnerPrincipal
from agent_console.workbench_employee import EmployeeDefinitionCommandOwnerAdapter
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from test_business_capability import capability
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_resource_management import command, manager

MIGRATIONS = Path(__file__).parents[1] / "migrations"


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "employee_authorization",
        "capability_review",
        "stale_preview",
        "existing_employee_draft",
        "http",
    ],
)
def test_three_real_owners_commit_or_rollback(manager, monkeypatch, failure):
    a, resources = manager
    monkeypatch.setattr(grants_fixture, "SCOPE", a.subject.scope)
    employees = a.automation.employees
    caprepo = PostgresBusinessCapabilityRepository(a.repository.pool)
    caprepo.migrate(MIGRATIONS / "0052_business_capability.sql")
    CapabilityPublicationRepository(a.repository.pool).migrate(
        MIGRATIONS / "0053_business_capability_publication.sql"
    )
    UpgradeBatchRepository(a.repository.pool).migrate(
        MIGRATIONS / "0060_resource_upgrade_batch.sql"
    )
    caps = CapabilityOwner(caprepo, CapabilityReferences(employees, a.services), None)
    runner = SelectedUpgradeOwners(
        resources,
        EmployeeDefinitionCommandOwnerAdapter(employees, prepared_resource_reads=True),
        caps,
    )
    counter = 0

    def allow(owner, action, resource):
        nonlocal counter
        counter += 1
        grants_fixture.insert_dynamic_grant(
            a.authority,
            a.adapter.clock(),
            principal=a.subject.principal_id,
            grant=ExactGrant(owner, action, resource),
            key="batch-test-" + str(counter),
        )

    def call(conn):
        return AuthorizedOwnerCall(
            "SELECTED_UPGRADE",
            a.subject,
            conn,
            {},
            {},
            {},
            (),
            AuthorizedOwnerAuthority(a.adapter, a.subject, conn, 1, ()),
            1,
            1,
        )

    fixture = Path(__file__).parents[2] / "frontend/tests"
    content = json.loads(
        (fixture / "resource-management/fixtures/maintenance-skill.json").read_text()
    )
    source = json.loads((fixture / "e2e/fixtures/sales-report.json").read_text())
    resource = command(
        manager,
        "create",
        key="batch-skill-create",
        name="原子更新隔离验证",
        content=content,
    )["resource"]
    identity = resource["resourceId"]
    sequence = 0

    def act(action, **extra):
        nonlocal resource, sequence
        sequence += 1
        resource = command(
            manager,
            action,
            key=f"batch-skill-{sequence}",
            identity=identity,
            expectedVersion=resource["aggregateVersion"],
            **extra,
        )["resource"]

    def test_operations():
        read_output = None
        for op in content["operations"]:
            operation = op["name"]
            act(
                "test",
                operation=operation,
                testName=operation,
                testInput={
                    "schemaVersion": "sales-diagnostic-input.v1",
                    "synthetic": True,
                    "sourceSnapshot": source["sourceSnapshot"],
                    "source": source["source"],
                    "dependencies": {}
                    if operation == "READ_DATA"
                    else {"read": read_output},
                },
                expectedOutput={"operation": operation},
                comparison="subset",
            )
            assert resource["testResults"][-1]["status"] == "PASSED"
            if operation == "READ_DATA":
                read_output = resource["testResults"][-1]["actual"]

    test_operations()
    act("publish-tested")
    oldskill = next(
        r
        for r in resource["revisions"]
        if r["revisionId"] == resource["publishedRevisionId"]
    )
    before = FixedReference(identity, oldskill["revisionId"], oldskill["digest"])
    agent = a.refs["agent"]
    original = EmployeeRevision(
        a.e.scope,
        "employee:batch",
        "employee-revision:batch-old",
        "隔离测试职责",
        ("核对材料",),
        (
            CompositionMember(
                MemberKind.AGENT, agent.resource_id, agent.revision_id, agent.digest
            ),
            CompositionMember(
                MemberKind.SKILL, before.resource_id, before.revision_id, before.digest
            ),
        ),
    )
    with a.authority.connection_scope() as conn:
        seeded = employees.create_for_workbench(
            conn,
            original,
            expected_version=0,
            decision_id="explicit-test-seed",
            command_id="batch-employee-seed",
            authorized=True,
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            seeded = employees.decide_for_workbench(
                conn,
                original.scope,
                original.definition_id,
                original.revision_id,
                original.digest,
                action,
                expected_version=seeded["aggregateVersion"],
                decision_id="explicit-test-seed",
                command_id="batch-employee-seed-" + action,
                authorized=True,
            )
    original_cap = replace(
        capability(),
        scope=a.e.scope,
        bindings=(
            CapabilityBinding(
                BindingKind.EMPLOYEE,
                FixedReference(
                    original.definition_id, original.revision_id, original.digest
                ),
                "核对材料",
            ),
            CapabilityBinding(BindingKind.SKILL, before, "提供技能"),
        ),
    )
    allow(
        "EMPLOYEE", "READ", f"employee:{original.definition_id}:{original.revision_id}"
    )
    allow("BUSINESS_CAPABILITY", "CREATE", "business-capability:collection")
    allow(
        "BUSINESS_CAPABILITY",
        "READ",
        f"business-capability:{original_cap.capability_id}:{original_cap.revision_id}",
    )
    allow(
        "BUSINESS_CAPABILITY",
        "REVIEW_PUBLISH",
        f"business-capability:{original_cap.capability_id}:{original_cap.revision_id}",
    )
    with a.authority.connection_scope() as conn:
        caps(
            replace(
                call(conn),
                operation="SAVE_CAPABILITY_DRAFT",
                payload={
                    "revision": original_cap.canonical_record(),
                    "expectedVersion": 0,
                    "commandId": "batch-cap-seed",
                },
            )
        )
        preview = change_preview(original_cap, None, aggregate_version=1, generation=1)
        initial_publication = caps(
            replace(
                call(conn),
                operation="PUBLISH_CAPABILITY_REVISION",
                path={
                    "capability_id": original_cap.capability_id,
                    "revision_id": original_cap.revision_id,
                },
                payload={
                    "expectedVersion": 1,
                    "digest": original_cap.content_digest,
                    "impactDigest": preview["impactDigest"],
                    "commandId": "batch-cap-seed-publish",
                    "reason": "隔离测试初始事实",
                },
            )
        )
    act("successor")
    test_operations()
    draft = next(
        r
        for r in resource["revisions"]
        if r["revisionId"] == resource["currentDraftRevisionId"]
    )
    after = FixedReference(identity, draft["revisionId"], draft["digest"])
    skill_change = SelectedReplacement(a.e.scope, "SKILL", before, after)
    successor = employee_successor(
        original, "employee-revision:batch-new", [skill_change]
    )
    employee_change = SelectedReplacement(
        a.e.scope,
        "EMPLOYEE",
        FixedReference(original.definition_id, original.revision_id, original.digest),
        FixedReference(
            successor.definition_id, successor.revision_id, successor.digest
        ),
    )
    newcap = capability_successor(
        original_cap, "capability-revision:batch-new", [skill_change, employee_change]
    )
    impact = change_preview(
        newcap,
        original_cap,
        aggregate_version=initial_publication["aggregateVersion"] + 1,
        generation=1,
    )["impactDigest"]
    allow("EMPLOYEE", "CREATE", "employee:collection")
    allow("AGENT", "READ", f"agent:{agent.resource_id}:{agent.revision_id}")
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        if not (failure == "employee_authorization" and action == "APPROVE"):
            allow("EMPLOYEE", action, f"employee:{original.definition_id}:aggregate")
    allow(
        "EMPLOYEE",
        "READ",
        f"employee:{successor.definition_id}:{successor.revision_id}",
    )
    allow(
        "BUSINESS_CAPABILITY",
        "REVISE",
        f"business-capability:{newcap.capability_id}:aggregate",
    )
    for action in ("READ", "REVIEW_PUBLISH"):
        allow(
            "BUSINESS_CAPABILITY",
            action,
            f"business-capability:{newcap.capability_id}:{newcap.revision_id}",
        )
    selection = dict(
        batch="batch:three-owners",
        skill=after,
        skill_version=resource["aggregateVersion"],
        employees=(EmployeePublication(successor, seeded["aggregateVersion"]),),
        capabilities=(
            CapabilityPublication(
                newcap,
                initial_publication["aggregateVersion"],
                "b" * 64 if failure == "capability_review" else impact,
            ),
        ),
        reason="已核对选定对象差异",
    )

    coordinator = SelectedUpgradeCoordinator(
        SelectedUpgradePreview(
            a.services["skill"], employees, caprepo, caps.references
        ),
        runner,
    )
    selected = UpgradeSelection(
        before,
        after,
        (
            ConsumerSelection(
                FixedReference(
                    original.definition_id, original.revision_id, original.digest
                ),
                successor.revision_id,
            ),
        ),
        (
            ConsumerSelection(
                FixedReference(
                    original_cap.capability_id,
                    original_cap.revision_id,
                    original_cap.content_digest,
                ),
                newcap.revision_id,
            ),
        ),
    )
    real_preview = None
    if failure not in {"employee_authorization", "capability_review"}:
        with a.authority.connection_scope() as conn:
            real_preview = coordinator.preview(call(conn), selected)
        if failure == "stale_preview":
            # Fresh successful tests change the actual aggregate after user review.
            test_operations()
        elif failure == "existing_employee_draft":
            with a.authority.connection_scope() as conn:
                employees.create_for_workbench(
                    conn,
                    replace(successor, revision_id="employee-revision:existing-draft"),
                    expected_version=seeded["aggregateVersion"],
                    decision_id="explicit-test-existing-draft",
                    command_id="existing-draft",
                    authorized=True,
                )

    def snapshot(conn):
        return [
            conn.execute(
                "SELECT row_to_json(t) r FROM "
                + table
                + " t ORDER BY row_to_json(t)::text"
            ).fetchall()
            for table in (
                "skill_mcp_resource.resources",
                "digital_employee_definition.definitions",
                "digital_employee_definition.revisions",
                "digital_employee_definition.facts",
                "business_capability.definitions",
                "business_capability.revisions",
                "business_capability.publications",
                "business_capability.receipts",
                "authorization_admin.grant_requests",
                "authorization_admin.grant_decisions",
                "authorization_admin.grants",
                "authorization_admin.effective_grants",
                "resource_upgrade.receipts",
                "execution_authority.prepared_resource_commands",
            )
        ]

    with a.authority.connection_scope() as conn:
        initial = snapshot(conn)

    def execute():
        with a.authority.connection_scope() as conn:
            current = call(conn)
            if real_preview is not None:
                return coordinator.submit(
                    current,
                    selected,
                    command="batch:three-owners",
                    reviewed_digest=real_preview["reviewDigest"],
                    reason=selection["reason"],
                )
            admitted = current.authority.require(
                OwnerPrincipal(
                    a.subject.principal_id,
                    a.subject.scope.tenant_id,
                    a.subject.scope.security_domain,
                ),
                "SKILL",
                "MANAGE_RESOURCE",
                target("skill", identity),
            )
            return UpgradeBatchRepository.apply(
                conn,
                a.e.scope,
                a.subject.principal_id,
                "batch:three-owners",
                request={"testSelection": "exact-fixture"},
                reviewed_digest="a" * 64,
                authority_generation=1,
                recovery_epoch=1,
                decision_ids=(admitted.decision_id,),
                completed_decision_ids=lambda: [
                    d.decision_id for d in current.authority.decisions.values()
                ],
                current_preview_digest=lambda: "a" * 64,
                apply_owners=lambda: runner.apply(current, **selection),
            )

    if failure == "http":
        import hashlib
        from datetime import timedelta

        from agent_console.authority_contracts import CredentialId, GrantSource
        from agent_console.browser_session_application import (
            BrowserSessionPolicy,
            BrowserSessionService,
            StaticGenerationAuthenticator,
        )
        from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
        from agent_console.workbench_resource_upgrade import operations
        from fastapi.testclient import TestClient

        original_generation = a.automation.grants._generation_provider()
        browser_credential = replace(
            original_generation.credentials[0],
            credential_id=CredentialId("batch-browser-test"),
            credential_sha256=hashlib.sha256(b"batch-browser-test-secret").hexdigest(),
            authentication_source=GrantSource.BROWSER_BOOTSTRAP,
            grants=(),
        )
        generation = replace(
            original_generation,
            credentials=(*original_generation.credentials, browser_credential),
        )
        a.automation.grants._generation_provider = lambda: generation
        a.automation.grants.authorization._generation_provider = lambda: generation
        a.adapter.authorization._generation_provider = lambda: generation
        sessions = BrowserSessionService(
            a.authority,
            StaticGenerationAuthenticator(
                generation, source=GrantSource.BROWSER_BOOTSTRAP
            ),
            BrowserSessionPolicy(
                login_nonce_lifetime=timedelta(minutes=5),
                idle_lifetime=timedelta(minutes=30),
                absolute_lifetime=timedelta(hours=1),
                csrf_lifetime=timedelta(minutes=10),
            ),
            csrf_signing_key=b"b" * 32,
            recovery_epoch=1,
        )
        application = create_workbench_bff(
            sessions,
            a.adapter,
            WorkbenchBffPolicy("console.example", "https://console.example"),
            operations=operations(coordinator),
        )

        def ref_body(ref):
            return {
                "resourceId": ref.resource_id,
                "revisionId": ref.revision_id,
                "digest": ref.digest,
            }

        def consumers(values):
            return [
                {
                    "original": ref_body(v.original),
                    "successorRevisionId": v.successor_revision_id,
                }
                for v in values
            ]

        body = {
            "oldSkill": ref_body(before),
            "newSkill": ref_body(after),
            "employees": consumers(selected.employees),
            "capabilities": consumers(selected.capabilities),
        }
        root = "/api/workbench/v1/resource-upgrades"
        with TestClient(application, base_url="https://console.example") as client:
            assert (
                client.post(
                    root + "/preview",
                    json=body,
                    headers={"Origin": "https://console.example"},
                ).status_code
                == 401
            )
            csrf = grants_fixture.login(client, "batch-browser-test-secret")
            headers = grants_fixture.unsafe_headers(csrf)
            assert client.post(root + "/preview", json=body).status_code == 403
            preview_response = client.post(
                root + "/preview", json=body, headers=headers
            )
            assert preview_response.status_code == 200, preview_response.text
            confirm = {
                **body,
                "commandId": "batch:http",
                "reviewDigest": preview_response.json()["result"]["reviewDigest"],
                "reason": "核对后整批发布",
            }
            pending = client.post(root + "/receipt", json=confirm, headers=headers)
            assert pending.json()["result"] == {
                "state": "NOT_RECORDED",
                "safeToReplay": False,
            }
            response = client.post(root + "/submit", json=confirm, headers=headers)
            assert response.status_code == 200, response.text
            with a.authority.connection_scope() as conn:
                committed = snapshot(conn)
            restored = client.post(root + "/receipt", json=confirm, headers=headers)
            assert restored.status_code == 200, restored.text
            assert (
                restored.json()["result"]["receipt"]
                == response.json()["result"]["receipt"]
            )
            changed = {**confirm, "employees": []}
            assert (
                client.post(
                    root + "/receipt", json=changed, headers=headers
                ).status_code
                == 409
            )
            replay = client.post(root + "/submit", json=confirm, headers=headers)
            assert replay.status_code == 200, replay.text
            assert replay.json()["result"]["replayed"]
            with a.authority.connection_scope() as conn:
                assert snapshot(conn) == committed
        return

    if failure:
        with pytest.raises(
            Exception,
            match="AUTHORIZATION_NOT_FOUND"
            if failure == "employee_authorization"
            else {
                "capability_review": "CAPABILITY_IMPACT_CHANGED",
                "stale_preview": "UPGRADE_PREVIEW_CHANGED",
                "existing_employee_draft": "UPGRADE_EMPLOYEE_HEAD_OR_DRAFT_CONFLICT",
            }[failure],
        ):
            execute()
        with a.authority.connection_scope() as conn:
            assert snapshot(conn) == initial
    else:
        result = execute()
        assert (
            result["receipt"]["result"]["employees"][0][-1]["lifecycleState"]
            == "PUBLISHED"
        )
        with a.authority.connection_scope() as conn:
            assert (
                conn.execute(
                    "SELECT head_revision_id FROM business_capability.definitions "
                    "WHERE capability_id=%s",
                    (newcap.capability_id,),
                ).fetchone()["head_revision_id"]
                == newcap.revision_id
            )
            assert (
                UpgradeBatchRepository.read(
                    conn, a.e.scope, a.subject.principal_id, "batch:three-owners"
                )["state"]
                == "COMMITTED"
            )

        assert len(result["receipt"]["decisionIds"]) > 4
        assert all(
            d.startswith("workbench-authorization:")
            for d in result["receipt"]["decisionIds"]
        )
        with a.authority.connection_scope() as conn:
            committed = snapshot(conn)
        replay = execute()
        assert replay == {**result, "replayed": True}
        with a.authority.connection_scope() as conn:
            assert snapshot(conn) == committed
