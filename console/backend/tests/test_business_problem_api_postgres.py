"""297 real HTTP authoring and execution; no business SQL or test resolvers."""

import copy
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import psycopg
import pytest
import test_governed_execution_api_postgres as execution_http
from agent_console.business_problem_authorization import reference_grants
from agent_console.business_problem_schemas import DecidePlan, PreparePlan
from agent_console.governed_execution_authorization import (
    GovernedExecutionAuthority,
    evidence_reference_resource,
    execution_read_resource,
    execution_start_resource,
    resource_use_read_resource,
    skill_invoke_resource,
    skill_read_resource,
)
from agent_console.governed_execution_schemas import StartGovernedExecution
from agent_console.resource_use_domain import canonical_digest, stable_id
from agent_console.skill_executor import HttpReadOnlySkillExecutor

DATABASE_URL = os.environ.get("BUSINESS_PROBLEM_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="297 exclusive real PostgreSQL required"
)
ROOT = "/api/internal/v0.2.3"
TOKEN = "297-test-only-bearer"


def call(client, method, path, payload=None, *, status=None, headers=None):
    response = client.request(method, path, json=payload, headers=headers)
    assert response.status_code == status if status else response.is_success, (
        response.text
    )
    return response.json()


def start_supervisor(port, endpoint, authority_file, *, output):
    """Allow cold local startup, while requiring the real supervised HTTP server."""
    process = execution_http._spawn_supervisor(
        port, endpoint, authority_file, output=output
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError(f"297 supervisor exited: {process.returncode}")
            try:
                if httpx.get(base + "/healthz", timeout=1).status_code == 200:
                    return process, {}, base
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise AssertionError("297 real HTTP startup timed out")
    except BaseException:
        execution_http._stop_process(process)
        raise


@pytest.fixture
def entry(monkeypatch, tmp_path):
    name = "impl297_http_" + uuid4().hex
    with psycopg.connect(DATABASE_URL, autocommit=True) as admin:
        admin.execute(
            psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name))
        )
        url = DATABASE_URL.rsplit("/", 1)[0] + "/" + name
        try:
            # Migrations only. Every business fact below is created through HTTP.
            with psycopg.connect(url) as connection:
                for version in range(1, 8):
                    connection.execute(
                        next(
                            execution_http.MIGRATIONS.glob(f"{version:04d}_*.sql")
                        ).read_text()
                    )
            monkeypatch.setattr(execution_http, "DATABASE_URL", url)
            monkeypatch.setenv("WORKFLOW_RUNTIME_DATABASE_URL", url)
            file = tmp_path / "297-authority.json"
            grants = []
            config = {
                "schemaVersion": "governed-execution-auth.v1",
                "policyVersion": "297.v1",
                "auditSource": "297-human-policy",
                "credentials": [
                    {
                        "credentialId": "297",
                        "credentialSha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
                        "principalId": "297-author",
                        "tenantId": "297",
                        "securityDomain": "test",
                        "expiresAt": "2099-01-01T00:00:00Z",
                        "grants": grants,
                    }
                ],
            }

            def save():
                temporary = file.with_suffix(".tmp")
                temporary.write_text(json.dumps(config))
                temporary.replace(file)

            def grant(owner, action, resource):
                grants.append(dict(owner=owner, action=action, resource=resource))
                save()

            save()
            with execution_http.protocol_service() as (endpoint, calls):
                output = (tmp_path / "297-supervisor.log").open("a")
                process, _, base = start_supervisor(
                    execution_http._free_port(), endpoint, file, output=output
                )
                state = dict(
                    url=url,
                    file=file,
                    grants=grants,
                    config=config,
                    save=save,
                    grant=grant,
                    calls=calls,
                    endpoint=endpoint,
                    process=process,
                    base=base,
                    output=output,
                )
                try:
                    with httpx.Client(
                        base_url=base,
                        timeout=20,
                        headers={"Authorization": f"Bearer {TOKEN}"},
                    ) as client:
                        state["client"] = client
                        yield state
                finally:
                    execution_http._stop_process(state["process"])
                    output.close()
        finally:
            admin.execute(
                psycopg.sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    psycopg.sql.Identifier(name)
                )
            )


def publish(e, kind, content):
    client = e["client"]
    path, wrapper, key = {
        "agent": (
            "/api/internal/v0.2.2/agent-definitions",
            "definition",
            "definitionId",
        ),
        "skill": ("/api/internal/v0.2.2/resources/skill", "resource", "resourceId"),
        "workflow": (
            "/api/internal/v0.2.2/workflow-definitions",
            "definition",
            "workflowDefinitionId",
        ),
        "runtime": (
            "/api/internal/v0.2.2/runtime-profiles",
            "profile",
            "runtimeProfileId",
        ),
    }[kind]
    headers = {
        "X-Tenant-ID": "297",
        "X-Security-Domain": "test",
        "X-Principal-ID": "297-author",
    }

    def unwrap(value):
        return value[wrapper] if wrapper else value

    row = unwrap(
        call(
            client,
            "POST",
            path,
            {"name": "297 resource", "content": content},
            headers=headers,
        )
    )
    identity = row[key]
    path += "/" + identity
    row = unwrap(
        call(
            client,
            "POST",
            path + "/validation",
            {"expectedVersion": row["aggregateVersion"]},
            headers=headers,
        )
    )
    revision = row["revisions"][-1]
    row = unwrap(
        call(
            client,
            "POST",
            path + "/reviews",
            dict(
                expectedVersion=row["aggregateVersion"],
                digest=revision["digest"],
                decision="APPROVE",
                reason="297 exact review",
            ),
            headers=headers,
        )
    )
    call(
        client,
        "POST",
        path + "/publications",
        dict(
            expectedVersion=row["aggregateVersion"],
            digest=revision["digest"],
            reviewId=row["reviews"][-1]["reviewId"],
        ),
        headers=headers,
    )
    return identity, revision["revisionId"], revision["digest"]


def resources(e):
    agent = publish(
        e,
        "agent",
        {
            "title": "Quality analyst",
            "duties": ["Analyze quality"],
            "capabilities": ["supplier-quality.summary"],
        },
    )
    executor = HttpReadOnlySkillExecutor(
        executor_id="supplier-quality-readonly",
        executor_revision="1.0.0",
        endpoint=e["endpoint"],
    )
    operation = {
        "name": "supplier-quality.summary",
        "inputSchema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string"},
                "defects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"severity": {"type": "integer"}},
                        "required": ["severity"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["supplier", "defects"],
            "additionalProperties": False,
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "defectCount": {"type": "integer"},
                "highestSeverity": {"type": "integer"},
            },
            "required": ["defectCount", "highestSeverity"],
            "additionalProperties": False,
        },
        "sideEffectClass": "READ_ONLY",
        "executorId": "supplier-quality-readonly",
        "executorRevision": "1.0.0",
        "executorConfigurationDigest": executor.revision.configuration_digest,
        "sideEffectPolicy": {
            "policyId": "skill-readonly-policy",
            "policyRevision": "1",
            "policyDigest": canonical_digest(
                {
                    "policyId": "skill-readonly-policy",
                    "policyRevision": "1",
                    "allowedClass": "READ_ONLY",
                }
            ),
        },
        "ioLimits": dict(
            policyId="skill-io-policy",
            policyRevision="1",
            maxInputBytes=4096,
            maxOutputBytes=4096,
            maxObjectDepth=8,
            maxProperties=64,
            timeoutMs=1000,
        ),
    }
    skill = publish(
        e,
        "skill",
        {
            "description": "Quality summary",
            "capabilities": ["supplier-quality.summary"],
            "instructions": "Summarize defects",
            "operations": [operation],
        },
    )
    runtime = publish(
        e,
        "runtime",
        {
            "provider": "NATIVE_KUBERNETES",
            "resources": dict(
                cpuRequest="100m",
                cpuLimit="500m",
                memoryRequest="128Mi",
                memoryLimit="512Mi",
            ),
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
            "secretReferences": [],
        },
    )
    workflow = publish(
        e,
        "workflow",
        {
            "description": "Explicit quality workflow",
            "inputs": ["request"],
            "outputs": ["result"],
            "runtimeProfile": dict(
                kind="RUNTIME_PROFILE",
                resourceId=runtime[0],
                revisionId=runtime[1],
                digest=runtime[2],
            ),
            "tasks": [
                dict(
                    taskId="collect",
                    name="Collect",
                    dependsOn=[],
                    inputs=["request"],
                    outputs=["result"],
                    capabilityRequirements=["supplier-quality.summary"],
                    references=[
                        dict(kind="SKILL", resourceId=skill[0], revisionId=skill[1])
                    ],
                    skillOperationBindings=[
                        dict(
                            skillId=skill[0],
                            skillRevisionId=skill[1],
                            skillDigest=skill[2],
                            operation=operation["name"],
                        )
                    ],
                )
            ],
        },
    )
    headers = {
        "X-Tenant-ID": "297",
        "X-Security-Domain": "test",
        "X-Principal-ID": "297-author",
    }
    path = ROOT + "/digital-employees"
    members = [
        dict(kind=k, resourceId=v[0], revisionId=v[1], digest=v[2])
        for k, v in (
            ("AGENT", agent),
            ("SKILL", skill),
            ("WORKFLOW", workflow),
            ("RUNTIME_PROFILE", runtime),
        )
    ]
    row = call(
        e["client"],
        "POST",
        path + "/definitions",
        dict(
            employeeDefinitionId="employee-297",
            employeeDefinitionRevisionId="employee-297-r1",
            role="Quality analyst",
            responsibilities=["Analyze quality"],
            members=members,
            expectedVersion=0,
            commandId="create",
        ),
        headers=headers,
    )
    for action in ("validate", "approve", "publish"):
        row = call(
            e["client"],
            "POST",
            path + "/definitions/employee-297/" + action,
            dict(
                employeeDefinitionRevisionId="employee-297-r1",
                employeeDefinitionDigest=row["employeeDefinitionDigest"],
                expectedVersion=row["aggregateVersion"],
                commandId=action,
            ),
            headers=headers,
        )
    call(
        e["client"],
        "POST",
        path + "/instances",
        dict(
            instanceId="instance-297",
            employeeDefinitionId="employee-297",
            employeeDefinitionRevisionId="employee-297-r1",
            commandId="instance",
        ),
        headers=headers,
    )
    call(
        e["client"],
        "POST",
        path + "/instances/instance-297/assignments",
        dict(
            assignmentId="assignment-297",
            commandId="assignment",
            assigneeId="297-author",
            businessRole="Quality",
            effectiveFrom=datetime.now(UTC).isoformat(),
        ),
        headers=headers,
    )
    e["skill"] = skill
    return dict(
        workflowDefinitionId=workflow[0],
        workflowDefinitionRevisionId=workflow[1],
        workflowDefinitionDigest=workflow[2],
        employeeDefinitionId="employee-297",
        employeeDefinitionRevisionId="employee-297-r1",
        employeeDefinitionDigest=row["employeeDefinitionDigest"],
        digitalEmployeeInstanceId="instance-297",
        assignmentId="assignment-297",
    )


def product(e):
    c, grant = e["client"], e["grant"]
    for action in ("CREATE", "READ", "LIST"):
        grant("BUSINESS_PROBLEM", action, "business-problem:collection")
    command = dict(
        title="质量",
        description="改善交付质量",
        ownerId="297-owner",
        idempotencyKey="problem",
    )
    problem = call(c, "POST", ROOT + "/business-problems", command)["revision"]
    assert call(c, "POST", ROOT + "/business-problems", command)["revision"] == problem
    pid = problem["business_problem_id"]
    for action in ("READ", "REVISE", "TRANSITION"):
        grant("BUSINESS_PROBLEM", action, f"business-problem:{pid}")
    for action in ("CREATE", "READ"):
        grant("SUCCESS_CRITERION", action, "success-criterion:collection")
    criterion = call(
        c,
        "POST",
        ROOT + "/success-criteria",
        dict(
            criterionType="DETERMINISTIC_BOOLEAN",
            measurement={"expected": True},
            requiredEvidenceKinds=["METRIC"],
            evaluatorType="deterministic",
            evaluatorVersion="v1",
            idempotencyKey="criterion",
        ),
    )["revision"]
    grant(
        "SUCCESS_CRITERION",
        "READ",
        f"success-criterion:revision:{criterion['revision_id']}",
    )
    for action in ("CREATE", "READ", "REVISE"):
        grant("SUCCESS_CRITERIA_SET", action, f"success-criteria-set:{pid}")
    criteria = call(
        c,
        "POST",
        ROOT + f"/business-problems/{pid}/criteria-sets",
        dict(
            problemRevisionId=problem["revision_id"],
            orderedCriterionRevisionIds=[criterion["revision_id"]],
            expectedVersion=1,
            idempotencyKey="set",
        ),
    )["revision"]
    call(
        c,
        "POST",
        ROOT + f"/business-problems/{pid}/lifecycle",
        dict(toState="ACTIVE", expectedVersion=2, idempotencyKey="activate"),
    )
    grant("PLAN", "PREPARE", f"plan:prepare:{pid}")
    grant("PLAN", "READ", f"plan:prepared:{pid}")
    e.update(problem=problem, criterion=criterion, criteria=criteria, pid=pid)
    return dict(
        problemRevisionId=problem["revision_id"],
        problemRevisionDigest=problem["digest"],
        criteriaSetRevisionId=criteria["set_revision_id"],
        criteriaSetDigest=criteria["digest"],
        expectedProblemVersion=3,
        idempotencyKey="prepare",
    )


def setup(e):
    command = {**resources(e), **product(e)}
    for grant in reference_grants(PreparePlan(**command)):
        e["grant"](*grant)
    return command


def approve_command(command, plan):
    return {
        **command,
        "planVersion": plan["planVersion"],
        "planDigest": plan["planDigest"],
        "expectedVersion": plan["aggregateVersion"],
        "idempotencyKey": "approve",
        "decision": "APPROVE",
        "reasonCategory": "BUSINESS_APPROVAL",
    }


def test_normal_http_prepare_approve_restart_execute_and_replay(entry):
    e = entry
    command = setup(e)
    c, grant = e["client"], e["grant"]
    path = ROOT + f"/business-problems/{e['pid']}/plans"
    # Every independent reference/entry grant is required, before protected lookup.
    original = copy.deepcopy(e["grants"])
    for denied in list(e["grants"]):
        if denied["action"] not in {"READ", "PREPARE"}:
            continue
        if denied["resource"] in {
            "business-problem:collection",
            "success-criterion:collection",
        }:
            continue
        e["grants"][:] = [g for g in original if g != denied]
        e["save"]()
        call(c, "POST", path, command, status=404)
    e["grants"][:] = original
    e["save"]()
    with ThreadPoolExecutor(max_workers=2) as pool:
        plans = list(pool.map(lambda _: call(c, "POST", path, command), range(2)))
    assert plans[0]["planId"] == plans[1]["planId"]
    assert sorted(p["replayed"] for p in plans) == [False, True]
    plan = plans[0]
    assert plan["status"] == "PENDING_APPROVAL" and plan["approvals"] == []
    call(c, "POST", path, {**command, "expectedProblemVersion": 99}, status=409)
    planpath = ROOT + f"/plans/{plan['planId']}"
    approval = approve_command(command, plan)
    call(c, "POST", planpath + "/approvals", approval, status=404)
    grant("PLAN", "READ", f"plan:{plan['planId']}:1")
    call(c, "POST", planpath + "/approvals", approval, status=404)
    grant("PLAN", "APPROVE", f"plan:{plan['planId']}:1")
    skill = e["skill"]
    execution = dict(
        planId=plan["planId"],
        planVersion=1,
        planDigest=plan["planDigest"],
        approvalId=plan["content"]["workflow"]["approval_id"],
        assignmentId="assignment-297",
        digitalEmployeeInstanceId="instance-297",
        taskId="collect",
        skillId=skill[0],
        skillRevisionId=skill[1],
        skillDigest=skill[2],
        operation="supplier-quality.summary",
        idempotencyKey="execute",
        input={"supplier": "ACME", "defects": [{"severity": 2}]},
    )
    for owner, action, resource in (
        (
            "EXECUTION",
            "START",
            execution_start_resource(StartGovernedExecution(**execution)),
        ),
        (
            "SKILL",
            "INVOKE_SKILL",
            skill_invoke_resource(StartGovernedExecution(**execution)),
        ),
    ):
        grant(owner, action, resource)
    invalid_execution = {
        **execution,
        "assignmentId": "wrong-assignment",
        "idempotencyKey": "wrong-execution",
    }
    grant(
        "EXECUTION",
        "START",
        execution_start_resource(StartGovernedExecution(**invalid_execution)),
    )
    grant(
        "SKILL",
        "INVOKE_SKILL",
        skill_invoke_resource(StartGovernedExecution(**invalid_execution)),
    )
    # Execution retains its existing bootstrap policy snapshot; restart loads grants.
    execution_http._stop_process(e["process"])
    e["process"], _, base = start_supervisor(
        execution_http._free_port(), e["endpoint"], e["file"], output=e["output"]
    )
    c.base_url = base
    call(c, "POST", ROOT + "/executions", execution, status=404)
    assert e["calls"] == []
    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(
            pool.map(
                lambda _: call(c, "POST", planpath + "/approvals", approval), range(2)
            )
        )
    assert sorted(p["replayed"] for p in decisions) == [False, True]
    assert len(decisions[0]["approvals"]) == 1
    assert decisions[0]["approvals"] == decisions[1]["approvals"]
    assert call(
        c,
        "POST",
        planpath + "/approvals",
        {**approval, "reasonCategory": "POLICY_APPROVAL"},
        status=409,
    )
    # Revocation is effective on replay without a process restart.
    approved_grants = copy.deepcopy(e["grants"])
    e["grants"][:] = [g for g in approved_grants if g["action"] != "APPROVE"]
    e["save"]()
    call(c, "POST", planpath + "/approvals", approval, status=404)
    e["grants"][:] = approved_grants
    e["save"]()
    before = call(c, "GET", planpath + "?version=1")
    problem_before = call(c, "GET", ROOT + f"/business-problems/{e['pid']}")
    execution_http._stop_process(e["process"])
    e["process"], _, base = start_supervisor(
        execution_http._free_port(), e["endpoint"], e["file"], output=e["output"]
    )
    c.base_url = base
    assert call(c, "GET", planpath + "?version=1") == before
    assert call(c, "GET", ROOT + f"/business-problems/{e['pid']}") == problem_before
    assert (
        call(
            c,
            "GET",
            ROOT + f"/success-criteria/revisions/{e['criterion']['revision_id']}",
        )["revision"]
        == e["criterion"]
    )
    call(c, "POST", ROOT + "/executions", invalid_execution, status=409)
    assert e["calls"] == []
    first = call(c, "POST", ROOT + "/executions", execution, status=201)
    assert first["invocation"]["state"] == "SUCCEEDED", first
    replay = call(c, "POST", ROOT + "/executions", execution, status=200)
    assert first["identity"] == replay["identity"]
    assert len(e["calls"]) == 1
    assert first["evidenceReferenceAccess"] == "RESTRICTED"
    ids = first["identity"]
    invocation = first["invocation"]
    evidence_id = stable_id("skill-invocation-evidence", invocation["invocationId"])
    grant(
        "EXECUTION",
        "READ",
        execution_read_resource(ids["workflowRunId"], ids["attemptId"]),
    )
    grant(
        "SKILL",
        "READ_SKILL_INVOCATION",
        skill_read_resource(invocation["invocationId"]),
    )
    grant(
        "RESOURCE_USE", "READ", resource_use_read_resource(invocation["resourceUseId"])
    )
    grant("EVIDENCE", "READ_REFERENCE", evidence_reference_resource(evidence_id))
    execution_http._stop_process(e["process"])
    e["process"], _, base = start_supervisor(
        execution_http._free_port(), e["endpoint"], e["file"], output=e["output"]
    )
    c.base_url = base
    readback = call(
        c,
        "GET",
        ROOT
        + f"/executions/{ids['workflowRunId']}/attempts/{ids['attemptId']}"
        + f"/skill-invocations/{invocation['invocationId']}",
    )
    assert readback["resourceUse"]["projectionCompleteness"] == "COMPLETE"
    assert readback["resourceUse"]["evidenceIds"] == [evidence_id]
    assert readback["evidenceContentDisclosed"] is False
    call(c, "POST", ROOT + "/executions", execution, status=200)
    assert len(e["calls"]) == 1
    # Trusted scope comes from credentials, not forged scope headers.
    e["config"]["credentials"][0]["tenantId"] = "foreign"
    e["save"]()
    call(c, "GET", planpath + "?version=1", status=404)
    call(c, "POST", path, command, status=404)


def test_owner_failure_injection_rolls_back_all_plan_facts(entry, monkeypatch):
    """Focused real-DB injection; normal resource setup still uses production HTTP."""
    from types import SimpleNamespace

    from agent_console.business_problem_bootstrap import (
        build_business_problem_application,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from agent_console.digital_employee_postgres import (
        PostgresDigitalEmployeeRepository,
    )
    from agent_console.execution_postgres import PostgresExecutionAuthorityRepository

    e = entry
    command = setup(e)
    authority = PostgresExecutionAuthorityRepository(
        e["url"],
        migration_path=execution_http.MIGRATIONS
        / "0008_execution_runtime_authority.sql",
    )
    assembly = SimpleNamespace(
        employee_definitions=PostgresEmployeeDefinitionRepository(authority),
        repository=PostgresDigitalEmployeeRepository(authority),
    )
    application = build_business_problem_application(e["url"], assembly)

    def refresh():
        application.authority = GovernedExecutionAuthority.from_file(str(e["file"]))
        return application.authority.authenticate(f"Bearer {TOKEN}")

    def facts():
        with psycopg.connect(e["url"]) as connection:
            tables = (
                ("execution_authority", "plans"),
                ("execution_authority", "plan_approval_decisions"),
                ("execution_authority", "idempotency_claims"),
                ("business_problem_authority", "plan_bindings"),
                ("business_problem_authority", "idempotency_claims"),
            )
            counts = tuple(
                connection.execute(
                    psycopg.sql.SQL("SELECT count(*) FROM {}.{}").format(
                        *(psycopg.sql.Identifier(x) for x in table)
                    )
                ).fetchone()[0]
                for table in tables
            )
            statuses = connection.execute(
                "SELECT plan_id,status,aggregate_version "
                "FROM execution_authority.plans "
                "ORDER BY plan_id"
            ).fetchall()
            return counts, statuses

    def injected(original):
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("297_INJECTED_AFTER_OWNER_WRITE")

        return fail

    try:
        principal = refresh()
        for index, (owner, method) in enumerate(
            (
                (application.problems, "bind_prepared_plan"),
                (application.control, "complete_plan_entry"),
            )
        ):
            request = PreparePlan(
                **{**command, "idempotencyKey": f"prepare-failure-{index}"}
            )
            before = facts()
            with monkeypatch.context() as patch:
                patch.setattr(owner, method, injected(getattr(owner, method)))
                with pytest.raises(RuntimeError, match="297_INJECTED"):
                    application.prepare(principal, e["pid"], request)
            assert facts() == before
            plan = application.prepare(principal, e["pid"], request)
            assert (
                application.prepare(principal, e["pid"], request)["planId"]
                == plan["planId"]
            )
            e["grant"]("PLAN", "READ", f"plan:{plan['planId']}:1")
            e["grant"]("PLAN", "APPROVE", f"plan:{plan['planId']}:1")
            principal = refresh()
            decision = DecidePlan(
                **{
                    **approve_command(request.model_dump(), plan),
                    "idempotencyKey": f"approve-{index}",
                }
            )
            method = "approve_plan_entry" if index == 0 else "complete_plan_entry"
            before = facts()
            with monkeypatch.context() as patch:
                patch.setattr(
                    application.control,
                    method,
                    injected(getattr(application.control, method)),
                )
                with pytest.raises(RuntimeError, match="297_INJECTED"):
                    application.approve(principal, plan["planId"], decision)
            assert facts() == before
            accepted = application.approve(principal, plan["planId"], decision)
            assert accepted["status"] == "APPROVED" and len(accepted["approvals"]) == 1
        assert e["calls"] == []
    finally:
        for repository in (
            application.problems,
            application.control,
            application.workflows,
            authority,
        ):
            repository.pool.close()


def test_product_http_revisions_cas_and_independent_grants(entry):
    e = entry
    product(e)
    c = e["client"]
    path = ROOT + f"/business-problems/{e['pid']}"
    before = call(c, "GET", path)
    revision = dict(
        predecessorRevisionId=e["problem"]["revision_id"],
        expectedVersion=3,
        title="质量修订",
        description="改善交付质量并保持历史",
        ownerId="297-owner",
        idempotencyKey="revise",
    )
    grants = copy.deepcopy(e["grants"])
    for owner, action, resource, target, request in (
        (
            "BUSINESS_PROBLEM",
            "REVISE",
            f"business-problem:{e['pid']}",
            path + "/revisions",
            revision,
        ),
        (
            "BUSINESS_PROBLEM",
            "TRANSITION",
            f"business-problem:{e['pid']}",
            path + "/lifecycle",
            dict(toState="IN_PROGRESS", expectedVersion=3, idempotencyKey="transition"),
        ),
        (
            "BUSINESS_PROBLEM",
            "CREATE",
            "business-problem:collection",
            ROOT + "/business-problems",
            dict(title="x", description="y", ownerId="297", idempotencyKey="new"),
        ),
        (
            "SUCCESS_CRITERION",
            "CREATE",
            "success-criterion:collection",
            ROOT + "/success-criteria",
            dict(
                criterionType="NOT_MEASURABLE",
                measurement={"reason": "NOT_MEASURABLE"},
                requiredEvidenceKinds=[],
                evaluatorType="declared",
                evaluatorVersion="v1",
                idempotencyKey="new",
            ),
        ),
    ):
        e["grants"][:] = [
            g
            for g in grants
            if g != dict(owner=owner, action=action, resource=resource)
        ]
        e["save"]()
        call(c, "POST", target, request, status=404)
    e["grants"][:] = grants
    e["save"]()
    assert call(c, "GET", path) == before
    call(c, "POST", path + "/revisions", {**revision, "expectedVersion": 2}, status=409)
    assert call(c, "GET", path) == before
    revised = call(c, "POST", path + "/revisions", revision)["revision"]
    assert call(c, "POST", path + "/revisions", revision)["revision"] == revised
    call(
        c,
        "POST",
        path + "/revisions",
        {**revision, "description": "different"},
        status=409,
    )
    assert call(c, "GET", path)["revisions"] == [e["problem"], revised]
    criterion = e["criterion"]
    change = dict(
        successCriterionId=criterion["success_criterion_id"],
        predecessorRevisionId=criterion["revision_id"],
        expectedVersion=1,
        criterionType="DETERMINISTIC_BOOLEAN",
        measurement={"expected": False},
        requiredEvidenceKinds=["METRIC"],
        evaluatorType="deterministic",
        evaluatorVersion="v2",
        idempotencyKey="criterion-revision",
    )
    call(c, "POST", ROOT + "/success-criteria", change, status=404)
    for action in ("READ", "REVISE"):
        e["grant"](
            "SUCCESS_CRITERION",
            action,
            f"success-criterion:{criterion['success_criterion_id']}",
        )
    new_criterion = call(c, "POST", ROOT + "/success-criteria", change)["revision"]
    assert (
        call(c, "POST", ROOT + "/success-criteria", change)["revision"] == new_criterion
    )
    e["grant"](
        "SUCCESS_CRITERION",
        "READ",
        f"success-criterion:revision:{new_criterion['revision_id']}",
    )
    new_set = call(
        c,
        "POST",
        path + "/criteria-sets",
        dict(
            problemRevisionId=revised["revision_id"],
            predecessorSetRevisionId=e["criteria"]["set_revision_id"],
            orderedCriterionRevisionIds=[new_criterion["revision_id"]],
            expectedVersion=4,
            idempotencyKey="set-revision",
        ),
    )["revision"]
    assert call(c, "GET", path + "/criteria-sets")["revisions"] == [
        e["criteria"],
        new_set,
    ]
    assert call(c, "GET", path + "/criteria")["revisions"] == [criterion, new_criterion]
    # Historical references survive successor revisions; no retirement is invented.
    assert (
        call(
            c, "GET", ROOT + f"/success-criteria/revisions/{criterion['revision_id']}"
        )["revision"]
        == criterion
    )
    call(
        c,
        "POST",
        path + "/revisions",
        {**revision, "authorizationDecision": "forged"},
        status=422,
    )
    call(c, "GET", path, headers={"Authorization": "Bearer invalid"}, status=401)
    assert e["calls"] == []


def test_wrong_exact_resources_and_changed_criteria_cannot_be_approved(entry):
    e = entry
    command = setup(e)
    c = e["client"]
    path = ROOT + f"/business-problems/{e['pid']}/plans"
    for field in (
        "problemRevisionDigest",
        "criteriaSetDigest",
        "workflowDefinitionDigest",
        "employeeDefinitionDigest",
    ):
        call(
            c,
            "POST",
            path,
            {**command, field: "0" * 64, "idempotencyKey": field},
            status=409,
        )
    call(
        c,
        "POST",
        path,
        {**command, "expectedProblemVersion": 99, "idempotencyKey": "stale-version"},
        status=409,
    )
    with psycopg.connect(e["url"]) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM execution_authority.plans"
            ).fetchone()[0]
            == 0
        )
    plan = call(c, "POST", path, command)
    for action in ("READ", "APPROVE"):
        e["grant"]("PLAN", action, f"plan:{plan['planId']}:1")
    criterion = e["criterion"]
    for action in ("REVISE", "READ"):
        e["grant"](
            "SUCCESS_CRITERION",
            action,
            f"success-criterion:{criterion['success_criterion_id']}",
        )
    call(
        c,
        "POST",
        ROOT + "/success-criteria",
        dict(
            successCriterionId=criterion["success_criterion_id"],
            predecessorRevisionId=criterion["revision_id"],
            expectedVersion=1,
            criterionType="DETERMINISTIC_BOOLEAN",
            measurement={"expected": False},
            requiredEvidenceKinds=["METRIC"],
            evaluatorType="deterministic",
            evaluatorVersion="v2",
            idempotencyKey="changed-criterion",
        ),
    )
    planpath = ROOT + f"/plans/{plan['planId']}"
    call(c, "POST", planpath + "/approvals", approve_command(command, plan), status=409)
    unchanged = call(c, "GET", planpath + "?version=1")
    assert unchanged["status"] == "PENDING_APPROVAL" and unchanged["approvals"] == []
    assert unchanged["planDigest"] == plan["planDigest"]
    call(c, "POST", path, {**command, "idempotencyKey": "stale-criteria"}, status=409)
    assert e["calls"] == []
