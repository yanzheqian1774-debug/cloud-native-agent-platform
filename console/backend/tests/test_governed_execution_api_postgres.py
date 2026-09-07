"""Production-bootstrap HTTP/PostgreSQL/protocol acceptance for governed execution."""

import importlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import psycopg
import pytest
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("GOVERNED_EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class _Protocol(BaseHTTPRequestHandler):
    calls: ClassVar[list[dict]] = []
    mode: ClassVar[str] = "success"

    def log_message(self, *_args):
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        type(self).calls.append(body)
        if type(self).mode == "timeout":
            time.sleep(0.2)
            return
        if type(self).mode == "disconnect":
            self.connection.close()
            return
        defects = body["input"]["defects"]
        payload = json.dumps(
            {
                "schemaVersion": "read-only-skill-response.v1",
                "invocationId": body["invocationId"],
                "accepted": True,
                "observationId": f"protocol-observation:{len(type(self).calls)}",
                "output": {
                    "defectCount": len(defects),
                    "highestSeverity": max(item["severity"] for item in defects),
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def protocol_service(mode="success"):
    _Protocol.calls = []
    _Protocol.mode = mode
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Protocol)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", _Protocol.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class _EmployeeAuthorization:
    def __init__(self, scope):
        self.scope = scope

    def require(self, scope, action, identity):
        if scope != self.scope:
            raise AssertionError("cross-scope preparation")
        return f"preparation:{action}:{identity}"


def _publish(service, scope, key, content):
    row = service.create(
        scope, "preparation:owner", "Governed execution resource", content
    )
    resource_id = row[key]
    row = service.validate(
        scope, resource_id, "preparation:owner", row["aggregateVersion"]
    )
    record = row.get("definition", row)
    revision = record["revisions"][0]
    row = service.review(
        scope,
        resource_id,
        "preparation:reviewer",
        record["aggregateVersion"],
        revision["digest"],
        "APPROVE",
        "Exact test preparation review",
    )
    record = row.get("definition", row)
    row = service.publish(
        scope,
        resource_id,
        "preparation:publisher",
        record["aggregateVersion"],
        revision["digest"],
        record["reviews"][0]["reviewId"],
    )
    return resource_id, revision["revisionId"], revision["digest"]


def _prepare(endpoint, *, timeout_ms=1000):
    from agent_console.agent_definition_postgres import (
        PostgresAgentDefinitionRepository,
    )
    from agent_console.agent_definition_service import AgentDefinitionService
    from agent_console.digital_employee_application import (
        AssignmentLifecycle,
        AssignmentRecord,
        DigitalEmployeeApplicationService,
    )
    from agent_console.digital_employee_bootstrap import _validate_execution_v8
    from agent_console.digital_employee_definition import (
        CompositionMember,
        EmployeeDefinitionService,
        EmployeeRevision,
        MemberKind,
        PublishedEmployeeDefinitionAuthority,
    )
    from agent_console.digital_employee_definition_postgres import (
        PostgresEmployeeDefinitionRepository,
    )
    from agent_console.digital_employee_postgres import (
        PostgresDigitalEmployeeRepository,
    )
    from agent_console.execution_application import execution_plan_bytes
    from agent_console.execution_domain import ExecutionSchemaIncompatible
    from agent_console.execution_postgres import (
        AssignmentId,
        DigitalEmployeeInstanceId,
        PostgresExecutionAuthorityRepository,
        ScopeIdentity,
    )
    from agent_console.planning import (
        CanonicalWorkflowRevision,
        IntentRevision,
        TaskRequirement,
    )
    from agent_console.resource_use_domain import canonical_digest
    from agent_console.runtime_profile_postgres import PostgresRuntimeProfileRepository
    from agent_console.runtime_profile_service import RuntimeProfileService
    from agent_console.skill_executor import HttpReadOnlySkillExecutor
    from agent_console.skill_invocation_domain import SkillIOLimits
    from agent_console.skill_mcp_postgres import PostgresSkillMcpRepository
    from agent_console.skill_mcp_service import SkillMcpService
    from agent_console.workflow_control_domain import (
        ApprovalDecision,
        PlanRecord,
        PlanStatus,
    )
    from agent_console.workflow_control_postgres import (
        PostgresWorkflowControlRepository,
    )
    from agent_console.workflow_definition_postgres import (
        PostgresWorkflowDefinitionRepository,
    )
    from agent_console.workflow_definition_service import WorkflowDefinitionService

    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in range(1, 8):
            paths = tuple(MIGRATIONS.glob(f"{version:04d}_*.sql"))
            if paths:
                connection.execute(paths[0].read_text())

    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"governed-{suffix}", "acceptance")
    agent_repo = PostgresAgentDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0001_agent_definition_lifecycle.sql",
        governed_bindings_migration_path=MIGRATIONS
        / "0006_agent_governed_bindings.sql",
    )
    skill_repo = PostgresSkillMcpRepository(
        DATABASE_URL or "", migration_path=MIGRATIONS / "0002_skill_mcp_lifecycle.sql"
    )
    runtime_repo = PostgresRuntimeProfileRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql",
    )
    workflow_repo = PostgresWorkflowDefinitionRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql",
    )
    authority = PostgresExecutionAuthorityRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0008_execution_runtime_authority.sql",
    )
    for repository in (agent_repo, skill_repo, runtime_repo, workflow_repo):
        repository.migrate()
    try:
        authority.migrate()
    except ExecutionSchemaIncompatible:
        _validate_execution_v8(authority)
    for version, name in (
        (9, "workflow_control_persistence"),
        (10, "workflow_control_uow_extension"),
        (11, "workflow_control_plan_evidence_outcome"),
    ):
        candidate = PostgresWorkflowControlRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / f"{version:04d}_{name}.sql",
        )
        candidate.migrate()
        if version == 11:
            control = candidate
        else:
            candidate.pool.close()
    employee_repo = PostgresEmployeeDefinitionRepository(authority)
    employee_repo.migrate(MIGRATIONS / "0014_digital_employee_identity.sql")

    executor = HttpReadOnlySkillExecutor(
        executor_id="supplier-quality-readonly",
        executor_revision="1.0.0",
        endpoint=endpoint,
    )
    policy_semantic = {
        "policyId": "skill-readonly-policy",
        "policyRevision": "1",
        "allowedClass": "READ_ONLY",
    }
    limits = SkillIOLimits("skill-io-policy", "1", 4096, 4096, 8, 64, timeout_ms)
    input_schema = {
        "type": "object",
        "required": ["supplier", "defects"],
        "additionalProperties": False,
        "properties": {
            "supplier": {"type": "string"},
            "defects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity"],
                    "additionalProperties": False,
                    "properties": {"severity": {"type": "integer"}},
                },
            },
        },
    }
    output_schema = {
        "type": "object",
        "required": ["defectCount", "highestSeverity"],
        "additionalProperties": False,
        "properties": {
            "defectCount": {"type": "integer"},
            "highestSeverity": {"type": "integer"},
        },
    }
    operation = {
        "name": "supplier-quality.summary",
        "inputSchema": input_schema,
        "outputSchema": output_schema,
        "sideEffectClass": "READ_ONLY",
        "executorId": executor.revision.executor_id,
        "executorRevision": executor.revision.executor_revision,
        "executorConfigurationDigest": executor.revision.configuration_digest,
        "sideEffectPolicy": {
            "policyId": policy_semantic["policyId"],
            "policyRevision": policy_semantic["policyRevision"],
            "policyDigest": canonical_digest(policy_semantic),
        },
        "ioLimits": {
            "policyId": limits.policy_id,
            "policyRevision": limits.policy_revision,
            "maxInputBytes": limits.max_input_bytes,
            "maxOutputBytes": limits.max_output_bytes,
            "maxObjectDepth": limits.max_object_depth,
            "maxProperties": limits.max_properties,
            "timeoutMs": limits.timeout_ms,
        },
    }
    agent = _publish(
        AgentDefinitionService(agent_repo),
        AgentDefinitionService.scope(scope.namespace, scope.security_domain),
        "definitionId",
        {
            "title": "Quality analyst",
            "duties": ["Analyze quality"],
            "capabilities": ["supplier-quality.summary"],
        },
    )
    skill_service = SkillMcpService(skill_repo)
    skill_scope = skill_service.scope(scope.namespace, scope.security_domain)
    skill_record = skill_service.create(
        skill_scope,
        "skill",
        "preparation:owner",
        "Governed execution Skill",
        {
            "description": "Read supplier defects",
            "capabilities": ["supplier-quality.summary"],
            "instructions": "Summarize supplied defect facts",
            "operations": [operation],
        },
    )
    skill_id = skill_record["resourceId"]
    skill_record = skill_service.validate(
        skill_scope,
        "skill",
        skill_id,
        "preparation:owner",
        skill_record["aggregateVersion"],
    )["resource"]
    skill_revision = skill_record["revisions"][0]
    skill_record = skill_service.review(
        skill_scope,
        "skill",
        skill_id,
        "preparation:reviewer",
        skill_record["aggregateVersion"],
        skill_revision["digest"],
        "APPROVE",
        "Exact test preparation review",
    )["resource"]
    skill_service.publish(
        skill_scope,
        "skill",
        skill_id,
        "preparation:publisher",
        skill_record["aggregateVersion"],
        skill_revision["digest"],
        skill_record["reviews"][0]["reviewId"],
    )
    skill = (skill_id, skill_revision["revisionId"], skill_revision["digest"])
    runtime_service = RuntimeProfileService(runtime_repo)
    runtime_scope = runtime_service.scope(scope.namespace, scope.security_domain)
    runtime = _publish(
        runtime_service,
        runtime_scope,
        "runtimeProfileId",
        {
            "provider": "NATIVE",
            "resources": {
                "cpuRequest": "100m",
                "cpuLimit": "500m",
                "memoryRequest": "128Mi",
                "memoryLimit": "512Mi",
            },
            "isolation": "NAMESPACE",
            "stateMode": "STATELESS",
            "sessionAffinity": "NONE",
            "secretReferences": [],
        },
    )
    workflow_service = WorkflowDefinitionService(workflow_repo, lambda _s, _r: True)
    workflow_scope = workflow_service.scope(scope.namespace, scope.security_domain)
    workflow = _publish(
        workflow_service,
        workflow_scope,
        "workflowDefinitionId",
        {
            "description": "Governed supplier quality execution",
            "inputs": ["request"],
            "outputs": ["result"],
            "runtimeProfile": {
                "kind": "RUNTIME_PROFILE",
                "resourceId": runtime[0],
                "revisionId": runtime[1],
                "digest": runtime[2],
            },
            "tasks": [
                {
                    "taskId": "collect",
                    "name": "Collect",
                    "dependsOn": [],
                    "inputs": ["request"],
                    "outputs": ["result"],
                    "capabilityRequirements": ["supplier-quality.summary"],
                    "references": [],
                    "retryLimit": 0,
                    "timeoutSeconds": 30,
                    "failurePolicy": "FAIL_WORKFLOW",
                }
            ],
        },
    )
    revision = EmployeeRevision(
        scope,
        f"employee-definition:{suffix}",
        f"employee-revision:{suffix}",
        "Quality analyst",
        ("Analyze supplier quality",),
        (
            CompositionMember(MemberKind.AGENT, *agent),
            CompositionMember(MemberKind.SKILL, *skill),
            CompositionMember(MemberKind.WORKFLOW, *workflow),
            CompositionMember(MemberKind.RUNTIME_PROFILE, *runtime),
        ),
    )
    employee_auth = _EmployeeAuthorization(scope)
    employee_service = EmployeeDefinitionService(employee_repo, employee_auth)
    current = employee_service.create(
        revision, expected_version=0, command_id=f"create:{suffix}"
    )
    for action in ("VALIDATE", "APPROVE", "PUBLISH"):
        current = employee_service.decide(
            scope,
            revision.definition_id,
            revision.revision_id,
            revision.digest,
            action,
            expected_version=current["aggregateVersion"],
            command_id=f"{action}:{suffix}",
        )
    employee_application = DigitalEmployeeApplicationService(
        PostgresDigitalEmployeeRepository(authority),
        PublishedEmployeeDefinitionAuthority(employee_repo, employee_auth),
    )
    instance_id = DigitalEmployeeInstanceId(f"employee-instance:{suffix}")
    instance, _ = employee_application.create_instance(
        scope=scope,
        instance_id=instance_id,
        definition_id=revision.definition_id,
        definition_revision_id=revision.revision_id,
        owner_id="operator",
        organization_id=scope.namespace,
        command_id=f"instance:{suffix}",
    )
    assignment = AssignmentRecord(
        scope,
        AssignmentId(f"assignment:{suffix}"),
        instance.instance_id,
        "operator",
        "quality-analysis",
        AssignmentLifecycle.ACTIVE,
        datetime.now(UTC),
        None,
        1,
        f"assignment-command:{suffix}",
    )
    employee_application.assign(assignment)
    approval_id = f"approval:{suffix}"
    canonical = CanonicalWorkflowRevision(
        f"canonical-workflow:{suffix}",
        1,
        None,
        scope.namespace,
        scope.security_domain,
        "a" * 64,
        approval_id,
        "policy.v1",
        IntentRevision(
            f"intent:{suffix}",
            f"intent-revision:{suffix}",
            1,
            None,
            "planning.v1",
            "policy.v1",
            f"question:{suffix}",
            "Analyze quality",
            (),
            ("summary produced",),
            "b" * 64,
        ),
        (
            TaskRequirement(
                f"requirement:{suffix}",
                "collect",
                f"intent-revision:{suffix}",
                "COLLECT",
                "Analyze supplier quality",
                (),
                ("result",),
                (),
                (),
                ("summary produced",),
                "LOW",
                "REQUIRED",
                (),
                0,
            ),
        ),
        ("collect",),
        (),
        True,
    )
    plan_bytes = execution_plan_bytes(
        canonical, assignment.assignment_id, instance.instance_id
    )
    plan_digest = __import__("hashlib").sha256(plan_bytes).hexdigest()
    plan_id = f"plan:{suffix}"
    now = datetime.now(UTC)
    control.create_plan(
        PlanRecord(
            scope,
            plan_id,
            1,
            workflow[0],
            workflow[1],
            workflow[2].removeprefix("sha256:"),
            PlanStatus.PENDING_APPROVAL,
            1,
            plan_digest,
            plan_bytes,
            now,
            now,
        )
    )
    control.append_approval(
        scope,
        ApprovalDecision(
            approval_id,
            plan_id,
            1,
            plan_digest,
            1,
            "APPROVE",
            "preparation:reviewer",
            "HUMAN_REVIEW",
            "BUSINESS_APPROVAL",
            "c" * 64,
            now,
        ),
    )
    for repository in (agent_repo, skill_repo, runtime_repo, workflow_repo, control):
        repository.pool.close()
    authority.pool.close()
    return scope, {
        "planId": plan_id,
        "planVersion": 1,
        "planDigest": plan_digest,
        "approvalId": approval_id,
        "assignmentId": str(assignment.assignment_id),
        "digitalEmployeeInstanceId": str(instance.instance_id),
        "taskId": "collect",
        "skillId": skill[0],
        "skillRevisionId": skill[1],
        "skillDigest": skill[2],
        "operation": operation["name"],
        "idempotencyKey": f"start:{suffix}",
        "input": {"supplier": "ACME", "defects": [{"severity": 2}, {"severity": 5}]},
    }


def _headers(scope, principal="operator"):
    return {
        "X-Tenant-ID": scope.namespace,
        "X-Security-Domain": scope.security_domain,
        "X-Principal-ID": principal,
    }


def test_production_bootstrap_http_dispatch_read_replay_and_non_disclosure(monkeypatch):
    with protocol_service() as (endpoint, calls):
        scope, command = _prepare(endpoint)
        monkeypatch.setenv("AGENT_DEFINITION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_MCP_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("EXECUTION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_EXECUTOR_ENDPOINT", endpoint)
        module = importlib.import_module("agent_console.app")
        module._configure_agent_definitions()
        module._configure_digital_employees()
        module._configure_governed_execution()
        client = TestClient(module.app)

        endpoint_path = "/api/internal/v0.2.3/executions"
        assert client.post(endpoint_path, json=command).status_code == 401
        assert (
            client.post(
                endpoint_path,
                json=command,
                headers={"X-Principal-ID": "operator"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                endpoint_path,
                json={**command, "authorizationDecisionId": "ALLOW"},
                headers=_headers(scope),
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint_path,
                json={**command, "executorUrl": "http://127.0.0.1:1"},
                headers=_headers(scope),
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint_path,
                json=command,
                headers=_headers(type(scope)("foreign", scope.security_domain)),
            ).status_code
            == 404
        )
        assert calls == []
        started = client.post(endpoint_path, json=command, headers=_headers(scope))
        assert started.status_code == 201
        body = started.json()
        assert body["executionStarted"] is True
        assert body["skillCallSucceeded"] is True
        assert body["businessOutcome"] is None
        assert body["invocation"]["state"] == "SUCCEEDED"
        assert len(calls) == 1
        with psycopg.connect(DATABASE_URL or "") as connection:
            counts = connection.execute(
                """SELECT
                (SELECT count(*) FROM execution_authority.workflow_runs
                 WHERE namespace=%s),
                (SELECT count(*) FROM execution_authority.attempts
                 WHERE namespace=%s),
                (SELECT count(*) FROM skill_invocation.invocations
                 WHERE namespace=%s)""",
                (scope.namespace, scope.namespace, scope.namespace),
            ).fetchone()
        assert counts == (1, 1, 1)

        replay = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers(scope)
        )
        assert replay.status_code == 200 and replay.json() == body
        assert len(calls) == 1
        identity = body["identity"]
        invocation_id = body["invocation"]["invocationId"]
        read = client.get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/{invocation_id}",
            headers=_headers(scope),
        )
        assert read.status_code == 200
        result = read.json()
        assert result["identity"] == identity
        assert result["exactBinding"]["planId"] == command["planId"]
        assert result["exactBinding"]["skillRevisionId"] == command["skillRevisionId"]
        assert result["exactBinding"]["bindingId"]
        assert result["exactBinding"]["executorId"] == "supplier-quality-readonly"
        assert (
            result["invocation"]["evidenceId"] in result["resourceUse"]["evidenceIds"]
        )
        assert result["resourceUse"]["snapshotId"]
        assert result["evidenceContentDisclosed"] is False
        assert result["businessOutcome"] is None
        assert "ACME" not in json.dumps(result)

        foreign = client.get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/{invocation_id}",
            headers=_headers(type(scope)("foreign", scope.security_domain)),
        )
        assert foreign.status_code == 404

        bad = {**command, "skillDigest": "0" * 64, "idempotencyKey": "bad-digest"}
        rejected = client.post(
            "/api/internal/v0.2.3/executions", json=bad, headers=_headers(scope)
        )
        assert rejected.status_code == 409
        assert len(calls) == 1
        with psycopg.connect(DATABASE_URL or "") as connection:
            not_invoked = connection.execute(
                """SELECT a.attempt_id,t.workflow_run_id
                FROM execution_authority.attempts a
                JOIN execution_authority.task_runs t
                USING(namespace,security_domain,task_run_id)
                WHERE a.namespace=%s AND NOT EXISTS (
                  SELECT 1 FROM skill_invocation.invocations i
                  WHERE i.namespace=a.namespace
                    AND i.security_domain=a.security_domain
                    AND i.attempt_id=a.attempt_id)
                ORDER BY a.attempt_id LIMIT 1""",
                (scope.namespace,),
            ).fetchone()
        from agent_console.resource_use_domain import stable_id

        expected_invocation_id = stable_id(
            "skill-invocation",
            scope.namespace,
            scope.security_domain,
            not_invoked[0],
            "bad-digest",
        )
        pending = client.get(
            f"/api/internal/v0.2.3/executions/{not_invoked[1]}"
            f"/attempts/{not_invoked[0]}/skill-invocations/{expected_invocation_id}",
            headers=_headers(scope),
        )
        assert pending.status_code == 200
        assert pending.json()["invocation"]["state"] == "NOT_INVOKED"
        bad_input = {
            **command,
            "idempotencyKey": "bad-schema",
            "input": {"supplier": "ACME", "defects": "not-an-array"},
        }
        rejected = client.post(
            "/api/internal/v0.2.3/executions",
            json=bad_input,
            headers=_headers(scope),
        )
        assert rejected.status_code == 422
        assert len(calls) == 1


def test_concurrent_http_start_has_one_identity_and_one_dispatch(monkeypatch):
    with protocol_service() as (endpoint, calls):
        scope, command = _prepare(endpoint)
        monkeypatch.setenv("AGENT_DEFINITION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_MCP_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("EXECUTION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_EXECUTOR_ENDPOINT", endpoint)
        module = importlib.import_module("agent_console.app")
        module._configure_agent_definitions()
        module._configure_digital_employees()
        module._configure_governed_execution()
        client = TestClient(module.app)

        def start(_):
            return client.post(
                "/api/internal/v0.2.3/executions", json=command, headers=_headers(scope)
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = tuple(executor.map(start, range(2)))
        assert {item.status_code for item in responses} <= {200, 201}
        identities = {
            json.dumps(item.json()["identity"], sort_keys=True) for item in responses
        }
        assert len(identities) == 1
        assert len(calls) == 1


def test_timeout_restart_remains_unknown_and_never_redispatches(monkeypatch):
    with protocol_service("timeout") as (endpoint, calls):
        scope, command = _prepare(endpoint, timeout_ms=50)
        monkeypatch.setenv("AGENT_DEFINITION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_MCP_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("EXECUTION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_EXECUTOR_ENDPOINT", endpoint)
        module = importlib.import_module("agent_console.app")
        module._configure_agent_definitions()
        module._configure_digital_employees()
        module._configure_governed_execution()
        client = TestClient(module.app)
        first = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers(scope)
        )
        assert first.status_code == 201
        assert first.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert len(calls) == 1

        module._configure_governed_execution()
        restarted = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers(scope)
        )
        assert restarted.status_code == 200
        assert restarted.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert len(calls) == 1
