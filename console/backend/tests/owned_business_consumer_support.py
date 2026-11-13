"""Same-database lifecycle setup before the conversation selects any source.

Publication authority here is explicit isolated-fixture setup, never a product
approval. Admission, source selection and consumers use their real owners.
"""

from pathlib import Path
from types import SimpleNamespace as NS

from agent_console.digital_employee_definition import (
    CompositionMember,
    EmployeeRevision,
    MemberKind,
)
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_postgres import PostgresExecutionAuthorityRepository
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import (
    OPERATIONS,
    NativeRuleDocumentSkillExecutor,
)
from agent_console.ontology_postgres import migrate
from agent_console.ontology_service import OntologyService
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from test_document_rule_owner import rules
from test_native_document_tools import SOURCE
from test_ontology_lifecycle import ExactOntologyTestAuthority
from test_prepared_resource_owners import services

ROOT = Path(__file__).parents[1] / "migrations"


def prepare_source(e):
    """Called before select; never rewrite saved understanding or selected source."""
    native = PostgresExecutionAuthorityRepository(
        e.repo.pool.conninfo,
        migration_path=ROOT / "0008_execution_runtime_authority.sql",
    )
    try:
        native.migrate()
        with e.repo.connection_scope() as c:
            c.execute(
                "UPDATE execution_authority.evidence_cutover SET "
                "state='POSTGRES_ACTIVE',authoritative_writer='POSTGRES' "
                "WHERE singleton=true"
            )
    finally:
        native.pool.close()
    PostgresPlanningRepository(e.repo.pool).migrate()
    generator = services.__wrapped__(e.repo)
    owners = next(generator)
    # The parent fixture registers this cleanup, including on later failure.
    e.consumer_cleanup = generator.close
    e.consumer_services = owners
    scope = e.context.scope
    context = NS(principal_id="human:isolated-publication-reviewer", scope=scope)
    authority = NS(require=lambda *args: NS(decision_id="isolated-setup-only"))
    refs, records = {}, {}
    for kind, content in resource_content(SOURCE, rule_bound=True).items():
        service = owners[kind]
        rs = service.scope(scope.tenant_id, scope.security_domain)
        args = (
            (rs, "skill", "human:fixture-author")
            if kind == "skill"
            else (rs, "human:fixture-author")
        )
        value = service.create(*args, "Synthetic owned-business integration", content)
        if kind == "knowledge":
            value = value["knowledge"]
        identity = value[
            {
                "skill": "resourceId",
                "agent": "definitionId",
                "runtime": "runtimeProfileId",
                "knowledge": "knowledgeId",
            }[kind]
        ]
        revision = value["revisions"][-1]
        with e.repo.connection_scope() as c:
            PreparedResourceOwner(owners)(
                NS(
                    operation="REVIEW_PREPARED_RESOURCE",
                    context=context,
                    connection=c,
                    authority=authority,
                    path={
                        "kind": kind,
                        "identity": identity,
                        "revision": revision["revisionId"],
                    },
                    payload={
                        "expectedVersion": value["aggregateVersion"],
                        "digest": revision["digest"],
                        "reason": "Isolated fixture setup only",
                        "idempotencyKey": "joint-publication-" + kind,
                    },
                )
            )
        refs[kind] = ExactReference(
            resource_id=identity,
            revision_id=revision["revisionId"],
            digest=revision["digest"].removeprefix("sha256:"),
        )
        records[kind] = (
            service.repository.get(rs, "skill", identity)
            if kind == "skill"
            else service.repository.get(rs, identity)
        )
    e.consumer_refs, e.consumer_records = refs, records
    source_revision = next(
        r
        for r in records["knowledge"]["revisions"]
        if r["revisionId"] == refs["knowledge"].revision_id
    )
    e.published_source = {
        "reference": refs["knowledge"].model_dump(mode="json"),
        "content": source_revision["content"],
    }


def configure_scope(e, result, policy):
    refs = e.consumer_refs
    assert result["inputSource"]["source"] == refs["knowledge"].model_dump(mode="json")
    scope = e.context.scope
    employee = EmployeeRevision(
        ScopeIdentity(scope.tenant_id, scope.security_domain),
        "employee-definition:joint",
        "employee-revision:joint",
        "Synthetic document reviewer",
        ("Isolated test only",),
        tuple(
            CompositionMember(
                MemberKind("RUNTIME_PROFILE" if kind == "runtime" else kind.upper()),
                ref.resource_id,
                ref.revision_id,
                ref.digest,
            )
            for kind, ref in refs.items()
        ),
    )
    employees = PostgresEmployeeDefinitionRepository(e.repo)
    with e.repo.connection_scope() as c:
        value = employees.create_for_workbench(
            c,
            employee,
            expected_version=0,
            decision_id="isolated-setup",
            command_id="joint-employee-create",
            authorized=True,
        )
        for action in ("VALIDATE", "APPROVE", "PUBLISH"):
            value = employees.decide_for_workbench(
                c,
                employee.scope,
                employee.definition_id,
                employee.revision_id,
                employee.digest,
                action,
                expected_version=value["aggregateVersion"],
                decision_id="isolated-setup",
                command_id="joint-employee-" + action,
                authorized=True,
            )
    employee_ref = ExactReference(
        resource_id=employee.definition_id,
        revision_id=employee.revision_id,
        digest=employee.digest,
    )
    content = rules(
        source=SOURCE,
        reference=refs["knowledge"].model_dump(),
        skill=refs["skill"].model_dump(),
    )
    content = content.model_copy(
        update={
            "scope": "production",
            "mappings": (
                content.mappings[0].model_copy(update={"code": "production"}),
            ),
            "rules": (content.rules[-1],),
        }
    )
    revision = NativeRuleDocumentSkillExecutor.revision
    content = content.model_copy(
        update={
            "actions": tuple(
                content.actions[0].model_copy(
                    update={
                        "executor_id": revision.executor_id,
                        "executor_revision": revision.executor_revision,
                        "executor_digest": revision.configuration_digest,
                        "operation": operation,
                    }
                )
                for operation in OPERATIONS
            )
        }
    )
    with e.repo.connection_scope() as c:
        migrate(c)
    digest = None
    for version, action in enumerate(
        ("CREATE", "VALIDATE", "TEST", "REVIEW", "PUBLISH")
    ):
        with e.repo.connection_scope() as c:
            owner = OntologyService(
                NS(
                    connection=c,
                    context=NS(
                        scope=scope,
                        principal_id="human:fixture-reviewer"
                        if version >= 3
                        else "human:fixture-author",
                    ),
                    authority=ExactOntologyTestAuthority(),
                )
            )
            value = owner.handle(
                action,
                "joint-rules",
                {
                    "request_key": "joint-" + action,
                    "expected_version": version,
                    "revision_id": "r1",
                    "digest": digest,
                    "content": content.model_dump(mode="json")
                    if version == 0
                    else None,
                    "reason": "Isolated setup only",
                },
            )
            if version == 0:
                digest = value["digest"]
    ontology = ExactReference(
        resource_id="joint-rules", revision_id="r1", digest=digest
    )
    selected = policy["scopes"][0]
    selected.update(
        employees=[employee_ref.model_dump()],
        agents=[refs["agent"].model_dump()],
        skills=[refs["skill"].model_dump()],
        runtimes=[refs["runtime"].model_dump()],
        operations=list(OPERATIONS),
        documentRules={
            "ontology": ontology.model_dump(),
            "mapping_code": "production",
            "source": refs["knowledge"].model_dump(),
            "scope": "production",
        },
    )
    e.consumer_employee, e.consumer_ontology = employee_ref, ontology


def resource_automation(e, planning, tmp_path):
    """Bind the real consumer to the same DB/principal and no static work scopes."""
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta
    from hashlib import sha256

    from agent_console.authority_configuration import (
        OWNER_RESOURCE_PREFIXES,
        CredentialConfiguration,
        RequestabilityRule,
        StaticGrant,
    )
    from agent_console.authority_contracts import CredentialId, ExactGrant, GrantSource
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
        GrantAdministrationService,
    )
    from agent_console.ontology_authorization import OntologyTargets
    from agent_console.ontology_execution import migrate as migrate_semantics
    from agent_console.resource_automation import ResourceAutomation, migrate
    from agent_console.resource_automation_policy import AutomationPolicy
    from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator
    from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
    from agent_console.workbench_plan_suggestion import PlanningGrantTargetValidator
    from agent_console.workbench_prepared_execution import PreparedExecutionGrantTargets
    from agent_console.workbench_prepared_resources import PreparedResourceTargets

    scope = e.context.scope
    issuer = "service:joint-resource-policy"
    secret = "isolated-joint-resource-policy-not-deployed"
    credential = tmp_path / "joint-resource-policy.secret"
    credential.write_text(secret)
    credential.chmod(0o600)
    grant = ExactGrant(
        "GRANT_ADMIN",
        "DECIDE",
        f"grant-scope:{scope.tenant_id}:{scope.security_domain}",
    )
    original = e.admission.delegation.grants
    generation = original.generation
    actions = [
        ("BUSINESS_PROBLEM", "READ"),
        ("SUCCESS_CRITERIA_SET", "READ"),
        ("SUCCESS_CRITERION", "READ"),
        ("PLAN", "PREPARE"),
        ("PLAN", "READ"),
        ("PLAN", "APPROVE"),
        ("AGENT", "READ"),
        ("INSTANCE", "CREATE"),
        ("ASSIGNMENT", "CREATE"),
        ("EXECUTION", "START"),
        ("EXECUTION", "READ"),
        ("SKILL", "INVOKE_SKILL"),
        ("EVALUATION", "EVALUATE"),
        ("EVALUATION", "READ"),
        ("HUMAN_CONFIRMATION", "READ"),
        ("EVIDENCE", "READ_REFERENCE"),
        ("RESOURCE_USE", "READ"),
        ("BUSINESS_ONTOLOGY", "READ"),
        ("BUSINESS_ONTOLOGY", "USE"),
        *[
            (owner, action)
            for owner in ("AGENT", "SKILL", "RUNTIME_PROFILE", "KNOWLEDGE")
            for action in ("READ_RESOURCE", "REVIEW_PUBLISH_RESOURCE")
        ],
        *[
            ("EMPLOYEE", action)
            for action in ("CREATE", "READ", "VALIDATE", "APPROVE", "PUBLISH")
        ],
    ]
    generation = replace(
        generation,
        credentials=(
            *generation.credentials,
            CredentialConfiguration(
                CredentialId("joint-resource-policy"),
                sha256(secret.encode()).hexdigest(),
                issuer,
                scope,
                datetime.now(UTC) + timedelta(hours=1),
                GrantSource.SERVICE_ONLY,
                (StaticGrant(grant, GrantSource.STATIC_META),),
            ),
        ),
        requestability=(
            *generation.requestability,
            *(
                RequestabilityRule(
                    owner, action, OWNER_RESOURCE_PREFIXES[owner], purpose
                )
                for purpose in ("RESOURCE_PREPARATION", "READONLY_WORK_EXECUTION")
                for owner, action in actions
            ),
        ),
    )
    reader = GenerationAuthorizationReader(generation, e.repo, e.repo, recovery_epoch=1)
    employees = PostgresEmployeeDefinitionRepository(e.repo)
    targets = WorkbenchGrantTargetValidator(
        planning.problems,
        e.consumer_services["agent"].repository,
        employees,
        additional=(
            PreparedResourceTargets(),
            PlanningGrantTargetValidator(),
            PreparedExecutionGrantTargets(),
            OntologyTargets(),
        ),
    )
    grants = GrantAdministrationService(
        e.repo,
        reader,
        generation,
        continuation_owner=None,
        target_validator=targets,
        recovery_epoch=1,
    )
    adapter = WorkbenchOwnerAuthorization(
        e.draft.authorization.owner_authorization.controller,
        e.repo,
        reader,
        clock=grants.clock,
    )
    policy = AutomationPolicy(
        policyId="joint-resource",
        policyVersion="1",
        issuer=issuer,
        credentialPath=credential,
        kubeconfigPath=tmp_path / "not-used",
        kubeContext="isolated",
        enabled=True,
        workScopes=(),
    )
    with e.repo.connection_scope() as c:
        migrate(c)
        migrate_semantics(c)
    automation = ResourceAutomation(
        policy,
        grants,
        planning,
        {**e.consumer_services, "mcp": e.consumer_services["skill"]},
        employees,
        runtime_probe=lambda namespace: {
            "check": "ISOLATED_RUNTIME_PROBE",
            "status": "PASSED",
            "namespace": namespace,
        },
    )
    automation.owned_business = e.business_owner
    return automation, adapter


def check_question_input_bff(e, automation, adapter, problem):
    """Actual browser session/CSRF/owner route, with LIST explicitly surrendered."""
    from unittest.mock import patch

    from agent_console.grant_administration_application import GrantRevocationCommand
    from agent_console.resource_automation import operations
    from agent_console.workbench_bff import (
        PREFIX,
        WorkbenchBffPolicy,
        create_workbench_bff,
    )
    from fastapi.testclient import TestClient

    with e.repo.connection_scope() as c:
        prior = c.execute(
            "SELECT grant_id FROM authorization_admin.grants "
            "WHERE subject_principal_id=%s AND owner='BUSINESS_PROBLEM' "
            "AND action='LIST' AND exact_resource='business-problem:collection'",
            (e.context.principal_id,),
        ).fetchall()
    for index, grant in enumerate(prior):
        e.admission.delegation.grants.revoke_grant(
            e.context,
            GrantRevocationCommand(
                grant["grant_id"],
                "TEST_WITHDRAWAL",
                f"joint-no-list-{index}",
                surrender=True,
            ),
        )
    with e.repo.connection_scope() as c:
        before = c.execute(
            "SELECT count(*) n FROM draft_provider_budget.reservations"
        ).fetchone()["n"]
    operation = next(
        op
        for op in operations(automation)
        if op.name == "PREPARE_QUESTION_ACTIVITY_INPUT"
    )
    app = create_workbench_bff(
        e.routing_sessions,
        adapter,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=(operation,),
    )
    payload = {
        "problemId": problem["resource_id"],
        "source": e.consumer_refs["knowledge"].model_dump(),
        "question": "检查生产交接资料并报告缺失项",
        "idempotencyKey": "joint-question-input",
    }
    with (
        TestClient(app, base_url="https://testserver") as client,
        patch(
            "agent_console.question_member_capabilities.identities",
            side_effect=AssertionError(
                "owned question input must not scan latest members"
            ),
        ),
    ):
        client.cookies.update(e.adoption_client.cookies)
        response = client.post(
            PREFIX + "/question-activity-input",
            headers=e.adoption_headers,
            json=payload,
        )
        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["state"] == "ACTIVITY_REQUEST_READY_FOR_GOVERNED_PLANNING", result
        assert result["executionStarted"] is False and result["modelCalls"] == 0
        observed = result["activityRequirement"]["memberCapabilityObservation"]
        assert {op["operation"] for op in observed["operations"]} <= set(
            e.business_owner.policy.scopes[0].operations
        )
        assert (
            client.post(
                PREFIX + "/question-activity-input",
                headers=e.adoption_headers,
                json=payload,
            ).json()["result"]
            == result
        )
        assert (
            client.post(
                PREFIX + "/question-activity-input",
                headers=e.adoption_headers,
                json={**payload, "problemId": "not-my-problem"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                PREFIX + "/question-activity-input",
                headers=e.adoption_headers,
                json={
                    k: v for k, v in payload.items() if k not in {"problemId", "source"}
                },
            ).status_code
            == 404
        )
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == before
        )
    return result
