"""Exclusive HTTPS/PG controlled-provider acceptance server for 323 (not deployment)."""

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import uvicorn
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
    StaticGrant,
)
from agent_console.authority_contracts import (
    AuthorityScope,
    CredentialId,
    ExactGrant,
    GrantDecision,
    GrantId,
    GrantRequest,
    GrantRequestStatus,
    GrantSource,
)
from agent_console.authority_postgres import PostgresAuthorityRepository
from agent_console.browser_session_application import (
    BrowserSessionPolicy,
    BrowserSessionService,
    StaticGenerationAuthenticator,
)
from agent_console.business_problem_postgres import PostgresBusinessProblemRepository
from agent_console.digital_employee_definition_postgres import (
    PostgresEmployeeDefinitionRepository,
)
from agent_console.draft_assistance import ProviderBudgetQuote
from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
from agent_console.execution_domain import ScopeIdentity
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.model_governance_authorization import (
    ModelGovernanceExactResolver,
)
from agent_console.model_governance_postgres import PostgresModelGovernanceRepository
from agent_console.plan_invocation_postgres import PostgresPlanningInvocations
from agent_console.plan_suggestion_api import install_planning_invocations
from agent_console.plan_suggestion_application import PlanningApplication
from agent_console.plan_suggestion_bootstrap import PlanningInvocationDependencies
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.plan_suggestion_invocation import PlanningProfile
from agent_console.plan_suggestion_postgres import PostgresPlanningRepository
from agent_console.workbench_bff import WorkbenchBffPolicy, create_workbench_bff
from agent_console.workbench_owner_authorization import WorkbenchOwnerAuthorization
from agent_console.workbench_plan_suggestion import planning_operations
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from s5_v023_arch_323_fixture import MIGRATIONS, PROBLEM_ID, recover, seed, seed_model
from test_workbench_creator_continuation_postgres import Controller


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_dir.resolve()
    identity = json.loads((runtime / "identity.json").read_text())
    database = identity["databaseUrl"]
    if database != "postgresql://postgres@127.0.0.1:25432/planning323_browser":
        raise ValueError("323_EXCLUSIVE_DATABASE_REQUIRED")
    initialized = (runtime / "case.json").exists()
    with psycopg.connect(database) as conn:
        existing = conn.execute(
            "SELECT to_regclass('execution_authority.plans')"
        ).fetchone()[0]
        if not existing:
            for version in range(1, 13):
                conn.execute(next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text())
    authority = PostgresAuthorityRepository(
        database, migration_path=MIGRATIONS / "0018_browser_session_grant_authority.sql"
    )
    authority.migrate()
    if not initialized:
        case = recover(database) if existing else seed(database, authority)
        # Recover the exact model already seeded in this dedicated database.
        # Never load a draft provider or any other task's runtime configuration.
        models = PostgresModelGovernanceRepository(
            database, migration_path=MIGRATIONS / "0019_model_governance.sql"
        )
        models.migrate()
        models.close()
        with psycopg.connect(database) as conn:
            row = conn.execute(
                "SELECT model_id,revision_id,digest "
                "FROM model_governance.model_revisions "
                "WHERE namespace='tenant-a' AND security_domain='quality' "
                "AND model_id IN ('model:s5-321-synthetic','model:s5-323-synthetic')"
            ).fetchone()
        model = (
            dict(zip(("resource_id", "revision_id", "digest"), row, strict=True))
            if row
            else seed_model(database)
        )
        saved = {
            "semantics": case.semantics,
            "employee": case.employee,
            "model": model,
            "planId": str(uuid4()),
        }
        (runtime / "case.json").write_text(json.dumps(saved, ensure_ascii=False))
    saved = json.loads((runtime / "case.json").read_text())
    model = ExactReference.model_validate(saved["model"])
    profile = PlanningProfile(
        profile_revision_id="planning-profile:323:1",
        profile_digest=hashlib.sha256(
            b"323-controlled-planning-profile-v1"
        ).hexdigest(),
        model=model,
        adapter_id="323-controlled-test",
        adapter_revision="1",
        maximum_output_tokens=8192,
        maximum_input_bytes=65536,
    )
    model_target = (
        f"model:invocation:plan-suggestion:{model.resource_id}:"
        f"{model.revision_id}:{model.digest}"
    )
    employee = saved["employee"]
    grants = [
        ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:" + PROBLEM_ID),
        ExactGrant(
            "SUCCESS_CRITERIA_SET", "READ", "success-criteria-set:" + PROBLEM_ID
        ),
        ExactGrant(
            "SUCCESS_CRITERION",
            "READ",
            "success-criterion:revision:criterion:323-report:1",
        ),
        ExactGrant("PLAN", "PREPARE", "plan:prepare:" + PROBLEM_ID),
        ExactGrant("PLAN", "READ", "plan:prepared:" + PROBLEM_ID),
        ExactGrant("PLAN", "READ", "plan:v2:" + saved["planId"]),
        ExactGrant("PLAN", "APPROVE", "plan:v2:" + saved["planId"]),
        ExactGrant(
            "EMPLOYEE",
            "READ",
            f"employee:{employee['resource_id']}:{employee['revision_id']}",
        ),
        ExactGrant("MODEL_GOVERNANCE", "INVOKE_MODEL", model_target),
    ]
    credentials = json.loads((runtime / "credentials.json").read_text())
    generation = StaticAuthorityGeneration(
        generation=1,
        digest="e" * 64,
        policy_version="323-controlled-test.v1",
        audit_source="323-controlled-test",
        credentials=(
            CredentialConfiguration(
                CredentialId("323-test-browser"),
                hashlib.sha256(credentials["browser"].encode()).hexdigest(),
                "human:323",
                AuthorityScope("tenant-a", "quality"),
                datetime.fromisoformat(identity["expiresAt"]),
                GrantSource.BROWSER_BOOTSTRAP,
                tuple(
                    StaticGrant(grant, GrantSource.BROWSER_BOOTSTRAP)
                    for grant in grants
                ),
            ),
        ),
        requestability=(),
        credential_revocation_tombstones=frozenset(),
    )
    active = authority.active_generation()
    if active is None:
        authority.activate_generation(
            1,
            generation.digest,
            1,
            operator_id="323-fixture",
            revoked_credentials=(),
            now=datetime.now(UTC),
        )
    elif active != (1, generation.digest, 1):
        raise ValueError("323_AUTHORITY_GENERATION_MISMATCH")
    issued = datetime.fromisoformat(identity["expiresAt"]) - timedelta(days=1)
    request = GrantRequest(
        "323-fixture-request",
        "human:323",
        AuthorityScope("tenant-a", "quality"),
        tuple(grants),
        "323_CONTROLLED_TEST",
        GrantRequestStatus.PENDING,
        issued,
    )
    authority.submit_request(
        request,
        actor_id="human:323",
        idempotency_key=request.request_id,
        payload_digest="a" * 64,
        target_validation=lambda _: True,
        recovery_epoch=1,
    )
    authority.decide_request(
        GrantDecision(
            "323-fixture-decision",
            request.request_id,
            "human:323-fixture-admin",
            "323-fixture-meta",
            True,
            "TEST_ONLY",
            "TEST_FIXTURE",
            "b" * 64,
            generation.policy_version,
            "323-controlled-test",
            issued,
        ),
        grants=tuple(
            (
                GrantId(f"323-fixture-grant-{i}"),
                grant,
                issued,
                issued + timedelta(hours=8),
            )
            for i, grant in enumerate(grants)
        ),
        expected_status=GrantRequestStatus.PENDING,
        idempotency_key="323-fixture-decision",
        payload_digest="c" * 64,
        recovery_epoch=1,
    )
    sessions = BrowserSessionService(
        authority,
        StaticGenerationAuthenticator(generation, source=GrantSource.BROWSER_BOOTSTRAP),
        BrowserSessionPolicy(
            login_nonce_lifetime=timedelta(minutes=5),
            idle_lifetime=timedelta(hours=1),
            absolute_lifetime=timedelta(hours=8),
            csrf_lifetime=timedelta(minutes=10),
        ),
        csrf_signing_key=(runtime / "csrf.key").read_bytes(),
        recovery_epoch=1,
    )
    authorization = GenerationAuthorizationReader(
        generation, authority, authority, recovery_epoch=1
    )
    authorizer = WorkbenchOwnerAuthorization(
        Controller(generation), authority, authorization
    )
    problems = PostgresBusinessProblemRepository(
        database, migration_path=MIGRATIONS / "0013_business_problem_authority.sql"
    )
    problems.migrate()
    planning = PostgresPlanningRepository(problems.pool)
    planning.migrate()
    with planning.pool.connection() as conn:
        conn.execute((MIGRATIONS / "0023_draft_assistance.sql").read_text())
    invocations = PostgresPlanningInvocations(planning)
    invocations.migrate()
    models = PostgresModelGovernanceRepository(
        database, migration_path=MIGRATIONS / "0019_model_governance.sql"
    )
    models.migrate()
    model_resolver = ModelGovernanceExactResolver(models, models, models)
    budget_profile = SimpleNamespace(
        scope=ScopeIdentity("tenant-a", "quality"),
        profile_revision_id=profile.profile_revision_id,
        profile_digest=profile.profile_digest,
        maximum_output_tokens=profile.maximum_output_tokens,
    )
    budget = PostgresProviderCallBudget(
        database,
        migration_path=MIGRATIONS / "0024_draft_provider_budget.sql",
        profile=budget_profile,
        ledger_id="323-only-controlled-planning",
        call_cap=20,
        total_cost_cap_microusd=1000000,
        input_price_microusd_per_million_tokens=0,
        output_price_microusd_per_million_tokens=0,
    )
    budget.migrate_and_configure()

    class Provider:
        synthetic = True

        def suggest(self, request, binding, profile, business_context):
            if not request.answers:
                return json.dumps(
                    {
                        "kind": "NEEDS_CLARIFICATION",
                        "questions": ["请补充测试快照时点和数据来源说明。"],
                    }
                )
            semantics = json.loads(json.dumps(saved["semantics"]))
            if request.policy:
                from agent_console.planning_contracts import OUTPUTS, PROCUREMENT

                semantics.update(
                    schema_version="planning.v3",
                    policy=request.policy.model_dump(mode="json"),
                )
                for index, task in enumerate(semantics["tasks"]):
                    task.update(
                        operation=PROCUREMENT[index],
                        output_kind=OUTPUTS[PROCUREMENT[index]],
                        input_kinds=[OUTPUTS[PROCUREMENT[index - 1]]]
                        if index
                        else ["CONTEXT"],
                    )
            return json.dumps({"kind": "VALID_SUGGESTION", "semantics": semantics})

    identities = iter(())

    def identity():
        nonlocal identities
        try:
            return next(identities)
        except StopIteration:
            identities = iter((saved["planId"],))
            return str(uuid4())

    factory = PlanningInvocationDependencies(
        profile=profile,
        model_resolver=model_resolver,
        budget=budget,
        quote=ProviderBudgetQuote(65536, 8192, 0),
        provider=Provider(),
        commitment_key=(runtime / "commitment.key").read_bytes(),
        prepare_resources=lambda *args: None,
        identity_factory=identity,
    ).bind(PlanningApplication(planning, problems, None), authorization)

    port = 19324
    app = create_workbench_bff(
        sessions,
        authorizer,
        WorkbenchBffPolicy(f"127.0.0.1:{port}", f"https://127.0.0.1:{port}"),
        operations=planning_operations(
            PlanningApplication(planning, problems, None),
            PostgresEmployeeDefinitionRepository(authority),
        ),
        route_installers=(install_planning_invocations(factory),),
    )
    app.mount("/assets", StaticFiles(directory=args.dist / "assets"), name="assets")

    @app.get("/{path:path}")
    def frontend(path: str):
        return FileResponse(args.dist / "index.html")

    (runtime / "server-ready.json").write_text(
        json.dumps(
            {
                "session": "S5-V023-ARCH-323",
                "planId": saved["planId"],
                "transport": "CONTROLLED_TEST_PROVIDER",
                "realModelCalls": 0,
            }
        )
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        ssl_certfile=str(runtime / "cert.pem"),
        ssl_keyfile=str(runtime / "key.pem"),
        access_log=False,
    )


if __name__ == "__main__":
    main()
