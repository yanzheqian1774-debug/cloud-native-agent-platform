"""Production-bootstrap HTTP/PostgreSQL/protocol acceptance for governed execution."""

import copy
import hashlib
import importlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

DATABASE_URL = os.environ.get("GOVERNED_EXECUTION_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"
TEST_TOKEN = "governed-execution-test-token"


class _Protocol(BaseHTTPRequestHandler):
    calls: ClassVar[list[dict]] = []
    mode: ClassVar[str] = "success"
    entered: ClassVar[threading.Event] = threading.Event()
    release: ClassVar[threading.Event] = threading.Event()

    def log_message(self, *_args):
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        type(self).calls.append(body)
        if type(self).mode == "block":
            type(self).entered.set()
            if not type(self).release.wait(timeout=15):
                raise RuntimeError("blocked protocol call was not released")
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
    _Protocol.entered = threading.Event()
    _Protocol.release = threading.Event()
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
                    "references": [
                        {
                            "kind": "SKILL",
                            "resourceId": skill[0],
                            "revisionId": skill[1],
                        }
                    ],
                    "skillOperationBindings": [
                        {
                            "skillId": skill[0],
                            "skillRevisionId": skill[1],
                            "skillDigest": skill[2],
                            "operation": operation["name"],
                        }
                    ],
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
    command = {
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
    from agent_console.execution_application import _stable_id as execution_id
    from agent_console.resource_use_domain import stable_id

    run_id = execution_id(
        "workflow-run",
        scope.namespace,
        scope.security_domain,
        canonical.canonical_workflow_revision_id,
        canonical.approved_candidate_digest,
        approval_id,
        str(assignment.assignment_id),
        command["taskId"],
        f"operator:{command['idempotencyKey']}",
    )
    task_run_id = execution_id("task-run", run_id, command["taskId"])
    attempt_id = execution_id("attempt", task_run_id, "1")
    invocation_id = stable_id(
        "skill-invocation",
        scope.namespace,
        scope.security_domain,
        attempt_id,
        command["idempotencyKey"],
    )
    resource_use_id = stable_id(
        "resource-use",
        scope.namespace,
        scope.security_domain,
        attempt_id,
        "SKILL",
        "skill:primary",
        "1",
    )
    return (
        scope,
        command,
        {
            "workflowRunId": run_id,
            "taskRunId": task_run_id,
            "attemptId": attempt_id,
            "invocationId": invocation_id,
            "resourceUseId": resource_use_id,
            "evidenceId": stable_id("skill-invocation-evidence", invocation_id),
            "workflowDefinitionId": workflow[0],
            "workflowRevisionId": workflow[1],
        },
    )


def _headers(token=TEST_TOKEN):
    return {"Authorization": f"Bearer {token}"}


def _write_authority(
    path,
    scope,
    commands,
    identities,
    *,
    include_skill_invoke=True,
    include_reads=True,
    include_resource_read=True,
    include_evidence=True,
    extra_grants=(),
):
    from agent_console.governed_execution_authorization import (
        evidence_reference_resource,
        execution_read_resource,
        execution_start_resource,
        resource_use_read_resource,
        skill_invoke_resource,
        skill_read_resource,
    )
    from agent_console.governed_execution_schemas import StartGovernedExecution

    grants = []
    for command in commands:
        parsed = StartGovernedExecution.model_validate(command)
        grants.append(
            {
                "owner": "EXECUTION",
                "action": "START",
                "resource": execution_start_resource(parsed),
            }
        )
        if include_skill_invoke:
            grants.append(
                {
                    "owner": "SKILL",
                    "action": "INVOKE_SKILL",
                    "resource": skill_invoke_resource(parsed),
                }
            )
    if include_reads:
        grants.extend(
            (
                {
                    "owner": "EXECUTION",
                    "action": "READ",
                    "resource": execution_read_resource(
                        identities["workflowRunId"], identities["attemptId"]
                    ),
                },
                {
                    "owner": "SKILL",
                    "action": "READ_SKILL_INVOCATION",
                    "resource": skill_read_resource(identities["invocationId"]),
                },
            )
        )
        if include_resource_read:
            grants.append(
                {
                    "owner": "RESOURCE_USE",
                    "action": "READ",
                    "resource": resource_use_read_resource(identities["resourceUseId"]),
                }
            )
    if include_evidence:
        grants.append(
            {
                "owner": "EVIDENCE",
                "action": "READ_REFERENCE",
                "resource": evidence_reference_resource(identities["evidenceId"]),
            }
        )
    grants.extend(extra_grants)
    configuration = {
        "schemaVersion": "governed-execution-auth.v1",
        "policyVersion": "acceptance.v1",
        "auditSource": "postgres-http-acceptance",
        "credentials": [
            {
                "credentialId": "credential:operator",
                "principalId": "operator",
                "tenantId": scope.namespace,
                "securityDomain": scope.security_domain,
                "credentialSha256": hashlib.sha256(TEST_TOKEN.encode()).hexdigest(),
                "expiresAt": "2100-01-01T00:00:00Z",
                "grants": grants,
            }
        ],
    }
    path.write_text(json.dumps(configuration), encoding="utf-8")


def _configure(module, monkeypatch, endpoint, authority_file):
    monkeypatch.setenv("AGENT_DEFINITION_DATABASE_URL", DATABASE_URL or "")
    monkeypatch.setenv("SKILL_MCP_DATABASE_URL", DATABASE_URL or "")
    monkeypatch.setenv("EXECUTION_DATABASE_URL", DATABASE_URL or "")
    monkeypatch.setenv("SKILL_EXECUTOR_ENDPOINT", endpoint)
    monkeypatch.setenv("GOVERNED_EXECUTION_AUTHORITY_FILE", str(authority_file))
    monkeypatch.setattr(
        module,
        "_governed_execution_supervision",
        type("ActiveSupervision", (), {"allows": lambda _self, _url: True})(),
    )
    module._configure_agent_definitions()
    module._configure_digital_employees()
    module._configure_governed_execution()


def _free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _spawn_supervisor(port, endpoint, authority_file):
    environment = dict(os.environ)
    repository_root = Path(__file__).parents[3]
    source_roots = (
        repository_root / "conformance_harness" / "src",
        repository_root / "core" / "src",
        repository_root / "gateway" / "src",
        repository_root / "operator" / "src",
        repository_root / "runtime" / "src",
        repository_root / "console" / "backend" / "src",
    )
    environment["PYTHONPATH"] = os.pathsep.join(
        value
        for value in (
            *(str(path) for path in source_roots),
            environment.get("PYTHONPATH", ""),
        )
        if value
    )
    environment.update(
        {
            "AGENT_DEFINITION_DATABASE_URL": DATABASE_URL or "",
            "SKILL_MCP_DATABASE_URL": DATABASE_URL or "",
            "EXECUTION_DATABASE_URL": DATABASE_URL or "",
            "SKILL_EXECUTOR_ENDPOINT": endpoint,
            "GOVERNED_EXECUTION_AUTHORITY_FILE": str(authority_file),
        }
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent_console.governed_execution_supervisor",
            "--port",
            str(port),
        ],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _start_supervisor(port, endpoint, authority_file):
    from agent_console.governed_execution_supervisor import supervision_paths

    process = _spawn_supervisor(port, endpoint, authority_file)
    base_url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(
                f"supervisor exited {process.returncode}: {stdout} {stderr}"
            )
        try:
            if httpx.get(f"{base_url}/healthz", timeout=0.2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    else:
        process.kill()
        process.wait(timeout=5)
        raise AssertionError("supervised application did not become healthy")
    _, status_path = supervision_paths(DATABASE_URL or "")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    return process, status, base_url


def _stop_process(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_process_gone(pid):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    raise AssertionError(f"process {pid} did not exit")


def test_production_bootstrap_http_dispatch_read_replay_and_non_disclosure(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        bad = {**command, "skillDigest": "0" * 64, "idempotencyKey": "bad-digest"}
        bad_input = {
            **command,
            "idempotencyKey": "bad-schema",
            "input": {"supplier": "ACME", "defects": "not-an-array"},
        }
        changed_replay = {
            **command,
            "input": {"supplier": "CHANGED", "defects": [{"severity": 1}]},
        }
        authority_file = tmp_path / "authority.json"
        _write_authority(
            authority_file,
            scope,
            (command, bad, bad_input, changed_replay),
            identities,
        )
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)

        endpoint_path = "/api/internal/v0.2.3/executions"
        assert client.post(endpoint_path, json=command).status_code == 401
        assert (
            client.post(
                endpoint_path,
                json=command,
                headers=_headers("not-the-token"),
            ).status_code
            == 401
        )
        assert (
            client.post(
                endpoint_path,
                json={**command, "authorizationDecisionId": "ALLOW"},
                headers=_headers(),
            ).status_code
            == 422
        )
        assert (
            client.post(
                endpoint_path,
                json={**command, "executorUrl": "http://127.0.0.1:1"},
                headers=_headers(),
            ).status_code
            == 422
        )
        assert calls == []
        started = client.post(endpoint_path, json=command, headers=_headers())
        assert started.status_code == 201, started.text
        body = started.json()
        assert body["executionStarted"] is True
        assert body["skillCallSucceeded"] is True
        assert body["businessOutcome"] is None
        assert body["invocation"]["state"] == "SUCCEEDED"
        assert body["evidenceReferenceAccess"] == "AUTHORIZED"
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
            claim = connection.execute(
                "SELECT request_digest,workflow_run_id,task_run_id,attempt_id,state "
                "FROM execution_authority.governed_execution_claims "
                "WHERE namespace=%s AND security_domain=%s AND principal_id='operator' "
                "AND idempotency_key=%s",
                (scope.namespace, scope.security_domain, command["idempotencyKey"]),
            ).fetchone()
            migration = connection.execute(
                "SELECT checksum,adapter FROM governed_execution.schema_migrations "
                "WHERE version=17"
            ).fetchone()
        assert counts == (1, 1, 1)
        assert claim[1:] == (
            identities["workflowRunId"],
            identities["taskRunId"],
            identities["attemptId"],
            "EXECUTION_CREATED",
        )
        assert migration == (
            hashlib.sha256(
                (MIGRATIONS / "0017_governed_execution_claim.sql").read_bytes()
            ).hexdigest(),
            "governed-execution-claim-postgresql-v17",
        )

        replay = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert replay.status_code == 200 and replay.json() == body
        assert len(calls) == 1
        identity = body["identity"]
        invocation_id = body["invocation"]["invocationId"]
        read = client.get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/{invocation_id}",
            headers=_headers(),
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
        assert result["resourceUse"]["projectionCompleteness"] == "COMPLETE"
        assert result["resourceUse"]["immutableSnapshot"]["snapshotId"]
        assert result["evidenceContentDisclosed"] is False
        assert result["businessOutcome"] is None
        assert "ACME" not in json.dumps(result)

        rejected = client.post(
            "/api/internal/v0.2.3/executions", json=bad, headers=_headers()
        )
        assert rejected.status_code == 409
        assert len(calls) == 1
        rejected = client.post(
            "/api/internal/v0.2.3/executions",
            json=bad_input,
            headers=_headers(),
        )
        assert rejected.status_code == 422
        assert len(calls) == 1
        mismatch = client.post(
            "/api/internal/v0.2.3/executions",
            json=changed_replay,
            headers=_headers(),
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["detail"]["reasonCode"] == (
            "GOVERNED_EXECUTION_PAYLOAD_MISMATCH"
        )
        assert len(calls) == 1

        _write_authority(
            authority_file,
            scope,
            (command,),
            identities,
            include_resource_read=False,
        )
        module._configure_governed_execution()
        resource_denied = TestClient(module.app).get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/{invocation_id}",
            headers=_headers(),
        )
        assert resource_denied.status_code == 404

        _write_authority(
            authority_file,
            scope,
            (command,),
            identities,
            include_evidence=False,
        )
        module._configure_governed_execution()
        restricted_client = TestClient(module.app)
        restricted = restricted_client.get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/{invocation_id}",
            headers=_headers(),
        )
        assert restricted.status_code == 200
        restricted_body = restricted.json()
        assert restricted_body["invocation"]["evidenceId"] is None
        assert restricted_body["resourceUse"]["evidenceIds"] == []
        assert restricted_body["resourceUse"]["projectionCompleteness"] == "FILTERED"
        assert restricted_body["resourceUse"]["immutableSnapshot"] is None
        assert restricted_body["evidenceReferenceAccess"] == "RESTRICTED"
        assert identities["evidenceId"] not in json.dumps(restricted_body)


def test_authority_is_required_and_owner_denial_is_non_disclosing(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(
            authority_file,
            scope,
            (command,),
            identities,
            include_skill_invoke=False,
        )
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        denied = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert denied.status_code == 404
        assert denied.json()["detail"] == {"reasonCode": "GOVERNED_EXECUTION_NOT_FOUND"}
        assert calls == []

        monkeypatch.delenv("GOVERNED_EXECUTION_AUTHORITY_FILE")
        module._configure_governed_execution()
        unavailable = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert unavailable.status_code == 503
        assert calls == []


def test_start_evidence_reference_requires_independent_grant(monkeypatch, tmp_path):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(
            authority_file,
            scope,
            (command,),
            identities,
            include_evidence=False,
        )
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        started = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert started.status_code == 201
        body = started.json()
        assert body["invocation"]["evidenceId"] is None
        assert body["evidenceReferenceAccess"] == "RESTRICTED"
        assert identities["evidenceId"] not in json.dumps(body)
        assert len(calls) == 1


def test_concurrent_http_start_has_one_identity_and_one_dispatch(monkeypatch, tmp_path):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)

        def start(_):
            return client.post(
                "/api/internal/v0.2.3/executions", json=command, headers=_headers()
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = tuple(executor.map(start, range(2)))
        assert {item.status_code for item in responses} <= {200, 201}
        identities = {
            json.dumps(item.json()["identity"], sort_keys=True) for item in responses
        }
        assert len(identities) == 1
        assert len(calls) == 1


def test_active_http_request_owns_dispatch_until_terminal(monkeypatch, tmp_path):
    with protocol_service("block") as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)

        def start():
            return client.post(
                "/api/internal/v0.2.3/executions", json=command, headers=_headers()
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            active = executor.submit(start)
            assert _Protocol.entered.wait(timeout=2)
            replay = executor.submit(start)
            time.sleep(0.05)
            assert not replay.done()
            _Protocol.release.set()
            responses = (active.result(timeout=2), replay.result(timeout=2))
        assert {item.status_code for item in responses} <= {200, 201}
        assert {item.json()["invocation"]["state"] for item in responses} == {
            "SUCCEEDED"
        }
        assert len(calls) == 1


def test_process_registry_is_shared_by_two_applications_and_survives_peer_close(
    monkeypatch, tmp_path
):
    from agent_console.governed_execution_schemas import StartGovernedExecution

    with protocol_service("block") as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        standby = module._skill_invocation_composition
        module._configure_governed_execution()
        first = module._governed_execution_application
        module._configure_governed_execution()
        second = module._governed_execution_application
        assert standby is not None and first is not None and second is not None
        first_principal = first.authority.authenticate(f"Bearer {TEST_TOKEN}")
        second_principal = second.authority.authenticate(f"Bearer {TEST_TOKEN}")
        parsed = StartGovernedExecution.model_validate(command)

        with ThreadPoolExecutor(max_workers=2) as executor:
            active = executor.submit(first.start, first_principal, parsed)
            assert _Protocol.entered.wait(timeout=2)
            replay = executor.submit(second.start, second_principal, parsed)
            time.sleep(0.05)
            assert not replay.done()
            standby.close()
            time.sleep(0.05)
            assert not replay.done()
            _Protocol.release.set()
            results = (active.result(timeout=5), replay.result(timeout=5))
        assert {item.document["invocation"]["state"] for item in results} == {
            "SUCCEEDED"
        }
        assert len(calls) == 1


def test_execution_claim_failure_rolls_back_run_task_and_attempt(monkeypatch, tmp_path):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        governed = importlib.import_module("agent_console.governed_execution")
        monkeypatch.setattr(governed, "canonical_digest", lambda _value: "invalid")

        failed = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert failed.status_code == 409
        assert calls == []
        with psycopg.connect(DATABASE_URL or "") as connection:
            counts = connection.execute(
                """SELECT
                (SELECT count(*) FROM execution_authority.workflow_runs
                 WHERE namespace=%s),
                (SELECT count(*) FROM execution_authority.task_runs
                 WHERE namespace=%s),
                (SELECT count(*) FROM execution_authority.attempts
                 WHERE namespace=%s),
                (SELECT count(*) FROM execution_authority.governed_execution_claims
                 WHERE namespace=%s)""",
                (scope.namespace,) * 4,
            ).fetchone()
        assert counts == (0, 0, 0, 0)


def test_execution_commit_before_skill_preparation_replays_exact_payload_only(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        changed = (
            {**command, "skillId": "skill:other"},
            {**command, "operation": "supplier-quality.other"},
            {
                **command,
                "input": {"supplier": "OTHER", "defects": [{"severity": 1}]},
            },
        )
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command, *changed), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        governed = importlib.import_module("agent_console.governed_execution")
        original = governed.GovernedExecutionApplication._skill_request

        def interrupt_after_execution_commit(*_args, **_kwargs):
            raise RuntimeError("simulated process loss before Skill preparation")

        monkeypatch.setattr(
            governed.GovernedExecutionApplication,
            "_skill_request",
            interrupt_after_execution_commit,
        )
        failed = TestClient(module.app, raise_server_exceptions=False).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert failed.status_code == 500
        assert calls == []
        for mismatch in changed:
            rejected = TestClient(module.app).post(
                "/api/internal/v0.2.3/executions", json=mismatch, headers=_headers()
            )
            assert rejected.status_code == 409
        assert calls == []

        monkeypatch.setattr(
            governed.GovernedExecutionApplication, "_skill_request", original
        )
        module._configure_governed_execution()
        continued = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert continued.status_code == 200
        assert continued.json()["invocation"]["state"] == "SUCCEEDED"
        assert len(calls) == 1


def test_existing_execution_without_payload_claim_is_not_backfilled(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)
        first = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert first.status_code == 201
        assert len(calls) == 1
        with psycopg.connect(DATABASE_URL or "") as connection:
            connection.execute(
                "DELETE FROM execution_authority.governed_execution_claims "
                "WHERE namespace=%s AND security_domain=%s AND principal_id='operator' "
                "AND idempotency_key=%s",
                (scope.namespace, scope.security_domain, command["idempotencyKey"]),
            )

        replay = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert replay.status_code == 409
        assert replay.json()["detail"]["reasonCode"] == (
            "GOVERNED_EXECUTION_CLAIM_REQUIRED"
        )
        assert len(calls) == 1


def test_pre_provider_crash_recovers_unknown_and_failed_recovery_never_dispatches(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        repository = module._skill_invocation_composition.invocation_repository
        prepare_dispatch = repository.prepare_dispatch

        def crash_after_durable_dispatch(*args, **kwargs):
            snapshot, created = prepare_dispatch(*args, **kwargs)
            assert created
            assert snapshot.state.value == "DISPATCH_RECORDED"
            raise RuntimeError("simulated process loss before provider call")

        monkeypatch.setattr(
            repository, "prepare_dispatch", crash_after_durable_dispatch
        )
        failed = TestClient(module.app, raise_server_exceptions=False).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert failed.status_code == 500
        assert calls == []

        module._configure_governed_execution()
        recovering = module._skill_invocation_composition.invocation_repository

        def fail_recovery_commit(*_args, **_kwargs):
            raise RuntimeError("simulated recovery persistence failure")

        monkeypatch.setattr(recovering, "commit_terminal", fail_recovery_commit)
        recovery_failed = TestClient(module.app, raise_server_exceptions=False).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert recovery_failed.status_code == 500
        assert calls == []
        assert (
            recovering.get_snapshot(scope, identities["invocationId"]).state.value
            == "DISPATCH_RECORDED"
        )

        module._configure_governed_execution()
        recovered = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert recovered.status_code == 200
        assert recovered.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert calls == []


def test_timeout_restart_remains_unknown_and_never_redispatches(monkeypatch, tmp_path):
    with protocol_service("timeout") as (endpoint, calls):
        scope, command, identities = _prepare(endpoint, timeout_ms=50)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)
        first = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert first.status_code == 201
        assert first.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert len(calls) == 1

        module._configure_governed_execution()
        restarted = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert restarted.status_code == 200
        assert restarted.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert len(calls) == 1


def test_terminal_commit_crash_restart_never_redispatches(monkeypatch, tmp_path):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        repository = module._skill_invocation_composition.invocation_repository

        def crash_before_terminal_commit(*_args, **_kwargs):
            raise RuntimeError("simulated process loss before terminal commit")

        monkeypatch.setattr(repository, "commit_terminal", crash_before_terminal_commit)
        failed = TestClient(module.app, raise_server_exceptions=False).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert failed.status_code == 500
        assert len(calls) == 1
        with psycopg.connect(DATABASE_URL or "") as connection:
            state = connection.execute(
                "SELECT state FROM skill_invocation.projections "
                "WHERE namespace=%s AND security_domain=%s "
                "AND skill_invocation_id=%s",
                (
                    scope.namespace,
                    scope.security_domain,
                    identities["invocationId"],
                ),
            ).fetchone()[0]
        assert state == "DISPATCH_RECORDED"

        module._configure_governed_execution()
        recovered = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert recovered.status_code == 200
        assert recovered.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert len(calls) == 1

        identity = recovered.json()["identity"]
        read = TestClient(module.app).get(
            f"/api/internal/v0.2.3/executions/{identity['workflowRunId']}"
            f"/attempts/{identity['attemptId']}/skill-invocations/"
            f"{identities['invocationId']}",
            headers=_headers(),
        )
        assert read.status_code == 200
        assert read.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
        assert read.json()["resourceUse"]["state"] == "OUTCOME_UNKNOWN"


def test_wrong_execution_parent_combinations_are_non_disclosing(monkeypatch, tmp_path):
    from agent_console.governed_execution_authorization import (
        execution_read_resource,
        skill_read_resource,
    )

    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        wrong_run = "workflow-run:wrong"
        wrong_attempt = "attempt:wrong"
        wrong_invocation = "skill-invocation:wrong"
        authority_file = tmp_path / "authority.json"
        _write_authority(
            authority_file,
            scope,
            (command,),
            identities,
            extra_grants=(
                {
                    "owner": "EXECUTION",
                    "action": "READ",
                    "resource": execution_read_resource(
                        wrong_run, identities["attemptId"]
                    ),
                },
                {
                    "owner": "EXECUTION",
                    "action": "READ",
                    "resource": execution_read_resource(
                        identities["workflowRunId"], wrong_attempt
                    ),
                },
                {
                    "owner": "SKILL",
                    "action": "READ_SKILL_INVOCATION",
                    "resource": skill_read_resource(wrong_invocation),
                },
            ),
        )
        module = importlib.import_module("agent_console.app")
        _configure(module, monkeypatch, endpoint, authority_file)
        client = TestClient(module.app)
        started = client.post(
            "/api/internal/v0.2.3/executions", json=command, headers=_headers()
        )
        assert started.status_code == 201
        assert len(calls) == 1
        paths = (
            f"/api/internal/v0.2.3/executions/{wrong_run}/attempts/"
            f"{identities['attemptId']}/skill-invocations/{identities['invocationId']}",
            f"/api/internal/v0.2.3/executions/{identities['workflowRunId']}/attempts/"
            f"{wrong_attempt}/skill-invocations/{identities['invocationId']}",
            f"/api/internal/v0.2.3/executions/{identities['workflowRunId']}/attempts/"
            f"{identities['attemptId']}/skill-invocations/{wrong_invocation}",
        )
        for path in paths:
            rejected = client.get(path, headers=_headers())
            assert rejected.status_code == 404
            assert rejected.json() == {
                "detail": {"reasonCode": "GOVERNED_EXECUTION_NOT_FOUND"}
            }
        assert len(calls) == 1


def test_postgres_workflow_edit_preserves_binding_and_history(monkeypatch):
    from agent_console.workflow_definition_api import get_service
    from agent_console.workflow_definition_postgres import (
        PostgresWorkflowDefinitionRepository,
    )
    from agent_console.workflow_definition_service import WorkflowDefinitionService

    with protocol_service() as (endpoint, _calls):
        scope, _command, identities = _prepare(endpoint)
        repository = PostgresWorkflowDefinitionRepository(
            DATABASE_URL or "",
            migration_path=MIGRATIONS / "0007_workflow_runtime_profiles.sql",
        )
        repository.migrate()
        service = WorkflowDefinitionService(repository)
        module = importlib.import_module("agent_console.app")
        module.app.dependency_overrides[get_service] = lambda: service
        headers = {
            "X-Tenant-ID": scope.namespace,
            "X-Security-Domain": scope.security_domain,
            "X-Principal-ID": "human:workflow-owner",
        }
        client = TestClient(module.app)
        resource_id = identities["workflowDefinitionId"]
        try:
            successor = client.post(
                f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/successors",
                json={"expectedVersion": 4},
                headers=headers,
            )
            assert successor.status_code == 200, successor.text
            read = client.get(
                f"/api/internal/v0.2.2/workflow-definitions/{resource_id}",
                headers=headers,
            ).json()["definition"]
            original_digest = read["revisions"][0]["digest"]
            draft = copy.deepcopy(read["revisions"][-1]["content"])
            binding = draft["tasks"][0]["skillOperationBindings"]
            draft["description"] = "unrelated governed edit"
            saved = client.put(
                f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/draft",
                json={"expectedVersion": 5, "content": draft},
                headers=headers,
            )
            assert saved.status_code == 200, saved.text
            assert (
                saved.json()["definition"]["revisions"][-1]["content"]["tasks"][0][
                    "skillOperationBindings"
                ]
                == binding
            )

            for explicit_null in (False, True):
                invalid = copy.deepcopy(draft)
                if explicit_null:
                    invalid["tasks"][0]["skillOperationBindings"] = None
                else:
                    invalid["tasks"][0].pop("skillOperationBindings")
                rejected = client.put(
                    f"/api/internal/v0.2.2/workflow-definitions/{resource_id}/draft",
                    json={"expectedVersion": 6, "content": invalid},
                    headers=headers,
                )
                assert rejected.status_code == 409
                assert rejected.json()["detail"]["reasonCode"] == (
                    "SKILL_OPERATION_BINDING_PRESERVATION_REQUIRED"
                )
            unchanged = client.get(
                f"/api/internal/v0.2.2/workflow-definitions/{resource_id}",
                headers=headers,
            ).json()["definition"]
            assert unchanged["aggregateVersion"] == 6
            assert len(unchanged["revisions"]) == 3
            assert unchanged["revisions"][0]["digest"] == original_digest

            historical_content = copy.deepcopy(draft)
            historical_content["tasks"][0].pop("skillOperationBindings")
            historical_content["tasks"][0]["references"] = []
            historical = client.post(
                "/api/internal/v0.2.2/workflow-definitions",
                json={
                    "name": "Historical compatible flow",
                    "content": historical_content,
                },
                headers=headers,
            ).json()["definition"]
            historical_digest = historical["revisions"][0]["digest"]
            historical_content["description"] = "historical unrelated edit"
            compatible = client.put(
                "/api/internal/v0.2.2/workflow-definitions/"
                f"{historical['workflowDefinitionId']}/draft",
                json={"expectedVersion": 1, "content": historical_content},
                headers=headers,
            )
            assert compatible.status_code == 200
            assert (
                compatible.json()["definition"]["revisions"][0]["digest"]
                == historical_digest
            )
        finally:
            module.app.dependency_overrides.pop(get_service, None)
            repository.pool.close()


def test_ordinary_unsupervised_bootstrap_keeps_governed_entry_unavailable(
    monkeypatch, tmp_path
):
    from agent_console.governed_execution_ownership import SupervisedRecoveryGuard

    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        module = importlib.import_module("agent_console.app")
        monkeypatch.setenv("AGENT_DEFINITION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_MCP_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("EXECUTION_DATABASE_URL", DATABASE_URL or "")
        monkeypatch.setenv("SKILL_EXECUTOR_ENDPOINT", endpoint)
        monkeypatch.setenv("GOVERNED_EXECUTION_AUTHORITY_FILE", str(authority_file))
        monkeypatch.setattr(
            module, "_governed_execution_supervision", SupervisedRecoveryGuard()
        )
        module._configure_agent_definitions()
        module._configure_digital_employees()
        module._configure_governed_execution()
        response = TestClient(module.app).post(
            "/api/internal/v0.2.3/executions",
            json=command,
            headers={
                **_headers(),
                "X-Governed-Execution-Supervised": "true",
            },
        )
        assert response.status_code == 503
        assert response.json()["detail"]["reasonCode"] == (
            "GOVERNED_EXECUTION_SUPERVISION_REQUIRED"
        )
        assert calls == []


def test_supervisor_restart_fails_closed_until_managed_child_exit(
    monkeypatch, tmp_path
):
    with protocol_service() as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        first = None
        successor = None
        child_pid = None
        try:
            first, status, base_url = _start_supervisor(
                _free_port(), endpoint, authority_file
            )
            child_pid = int(status["childPid"])
            os.kill(first.pid, signal.SIGKILL)
            first.wait(timeout=5)

            read_path = (
                f"{base_url}/api/internal/v0.2.3/executions/"
                f"{identities['workflowRunId']}/attempts/{identities['attemptId']}"
                f"/skill-invocations/{identities['invocationId']}"
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                response = httpx.get(read_path, headers=_headers(), timeout=0.5)
                if response.status_code == 503:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("orphan child did not revoke governed entry")
            assert response.json()["detail"]["reasonCode"] == (
                "GOVERNED_EXECUTION_SUPERVISION_REQUIRED"
            )

            overlap = _spawn_supervisor(_free_port(), endpoint, authority_file)
            assert overlap.wait(timeout=5) == 75
            assert "SUPERVISED_RECOVERY_PREDECESSOR_UNCONFIRMED" in (
                overlap.stderr.read()
            )
            assert calls == []

            os.kill(child_pid, signal.SIGKILL)
            _wait_process_gone(child_pid)
            successor, _, _ = _start_supervisor(_free_port(), endpoint, authority_file)
        finally:
            if child_pid is not None:
                with suppress(ProcessLookupError):
                    os.kill(child_pid, signal.SIGKILL)
            _stop_process(successor)
            _stop_process(first)


def test_confirmed_child_exit_allows_unknown_recovery_without_redispatch(
    monkeypatch, tmp_path
):
    with protocol_service("block") as (endpoint, calls):
        scope, command, identities = _prepare(endpoint)
        authority_file = tmp_path / "authority.json"
        _write_authority(authority_file, scope, (command,), identities)
        predecessor = None
        successor = None
        request = None
        child_pid = None
        try:
            predecessor, status, base_url = _start_supervisor(
                _free_port(), endpoint, authority_file
            )
            child_pid = int(status["childPid"])
            executor = ThreadPoolExecutor(max_workers=1)
            request = executor.submit(
                httpx.post,
                f"{base_url}/api/internal/v0.2.3/executions",
                json=command,
                headers=_headers(),
                timeout=20,
            )
            assert _Protocol.entered.wait(timeout=5)

            with psycopg.connect(DATABASE_URL or "", autocommit=True) as connection:
                pids = connection.execute(
                    "SELECT pid FROM pg_stat_activity "
                    "WHERE datname=current_database() AND pid<>pg_backend_pid()"
                ).fetchall()
                terminated = sum(
                    bool(
                        connection.execute(
                            "SELECT pg_terminate_backend(%s)", (pid,)
                        ).fetchone()[0]
                    )
                    for (pid,) in pids
                )
            assert terminated > 0

            overlap = _spawn_supervisor(_free_port(), endpoint, authority_file)
            assert overlap.wait(timeout=5) == 75
            assert len(calls) == 1

            os.kill(child_pid, signal.SIGKILL)
            predecessor.wait(timeout=10)
            with suppress(httpx.HTTPError):
                request.result(timeout=5)
            executor.shutdown(wait=True)

            successor, _, successor_url = _start_supervisor(
                _free_port(), endpoint, authority_file
            )
            recovered = httpx.post(
                f"{successor_url}/api/internal/v0.2.3/executions",
                json=command,
                headers=_headers(),
                timeout=10,
            )
            assert recovered.status_code == 200, recovered.text
            assert recovered.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
            assert len(calls) == 1

            identity = recovered.json()["identity"]
            read = httpx.get(
                f"{successor_url}/api/internal/v0.2.3/executions/"
                f"{identity['workflowRunId']}/attempts/{identity['attemptId']}"
                f"/skill-invocations/{identities['invocationId']}",
                headers=_headers(),
                timeout=10,
            )
            replay = httpx.post(
                f"{successor_url}/api/internal/v0.2.3/executions",
                json=command,
                headers=_headers(),
                timeout=10,
            )
            assert read.status_code == 200
            assert read.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
            assert replay.status_code == 200
            assert replay.json()["invocation"]["state"] == "OUTCOME_UNKNOWN"
            assert len(calls) == 1
        finally:
            _Protocol.release.set()
            if request is not None and not request.done():
                with suppress(httpx.HTTPError, TimeoutError):
                    request.result(timeout=5)
            if child_pid is not None:
                with suppress(ProcessLookupError):
                    os.kill(child_pid, signal.SIGKILL)
            _stop_process(successor)
            _stop_process(predecessor)
