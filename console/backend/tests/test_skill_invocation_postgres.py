# ruff: noqa: E501
"""Real PostgreSQL and HTTP acceptance for governed READ_ONLY Skill invocation."""

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import psycopg
import pytest
from agent_console.execution_domain import ScopeIdentity
from agent_console.resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    canonical_digest,
    stable_id,
)
from agent_console.resource_use_postgres import PostgresResourceUseRepository
from agent_console.skill_executor import (
    HttpReadOnlySkillExecutor,
    SkillExecutorRegistry,
)
from agent_console.skill_invocation_application import (
    FixedReadOnlyPolicyAuthority,
    GovernedAttemptSkillInvocationService,
    ScopedSkillInvocationAuthorization,
)
from agent_console.skill_invocation_domain import (
    ExecutorRevision,
    InvocationState,
    SideEffectClass,
    SideEffectPolicy,
    SkillInvocationConflict,
    SkillInvocationError,
    SkillInvocationRequest,
    SkillIOLimits,
)
from agent_console.skill_invocation_postgres import PostgresSkillInvocationRepository

DATABASE_URL = os.environ.get("SKILL_INVOCATION_TEST_DATABASE_URL") or os.environ.get(
    "RESOURCE_USE_TEST_DATABASE_URL"
)
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="real dedicated PostgreSQL 15 required"
)
MIGRATIONS = Path(__file__).parents[1] / "migrations"


class ReadOnlyHandler(BaseHTTPRequestHandler):
    calls: ClassVar[list[dict]] = []
    mode = "success"

    def log_message(self, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length))
        type(self).calls.append(body)
        if type(self).mode == "timeout":
            time.sleep(0.2)
            return
        if type(self).mode == "disconnect":
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", "100")
            self.end_headers()
            self.wfile.write(b"{")
            self.wfile.flush()
            self.connection.close()
            return
        defects = body["input"]["defects"]
        output = {
            "defectCount": len(defects),
            "highestSeverity": max(item["severity"] for item in defects),
        }
        if type(self).mode == "bad-schema":
            output = {"defectCount": "invalid", "highestSeverity": 3}
        if type(self).mode == "large":
            output["padding"] = "X" * 5000
        payload = json.dumps(
            {
                "schemaVersion": "read-only-skill-response.v1",
                "invocationId": body["invocationId"],
                "accepted": True,
                "observationId": f"observation:{len(type(self).calls)}",
                "output": output,
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


@contextmanager
def protocol_service(mode="success"):
    ReadOnlyHandler.calls = []
    ReadOnlyHandler.mode = mode
    server = ThreadingHTTPServer(("127.0.0.1", 0), ReadOnlyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", ReadOnlyHandler.calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _migrate_base():
    with psycopg.connect(DATABASE_URL or "") as connection:
        for version in (*range(1, 13), 14):
            connection.execute(
                next(MIGRATIONS.glob(f"{version:04d}_*.sql")).read_text()
            )


def _scenario(endpoint, *, terminal_hook=None, timeout_ms=1000):
    _migrate_base()
    suffix = uuid.uuid4().hex
    scope = ScopeIdentity(f"skill-invocation-{suffix}", "acceptance")
    ids = {
        name: f"{name}:{suffix}"
        for name in (
            "workflow-definition",
            "plan",
            "assignment",
            "workflow",
            "task",
            "attempt",
            "employee-definition",
            "employee-revision",
            "employee",
            "skill",
            "skill-revision",
        )
    }
    executor = HttpReadOnlySkillExecutor(
        executor_id="supplier-quality-readonly",
        executor_revision="1.0.0",
        endpoint=endpoint,
    )
    limits = SkillIOLimits("skill-io-policy", "1", 4096, 4096, 8, 64, timeout_ms)
    policy_semantic = {
        "policyId": "skill-readonly-policy",
        "policyRevision": "1",
        "allowedClass": "READ_ONLY",
    }
    policy = SideEffectPolicy(
        policy_semantic["policyId"],
        policy_semantic["policyRevision"],
        canonical_digest(policy_semantic),
        SideEffectClass.READ_ONLY,
    )
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
            "policyId": policy.policy_id,
            "policyRevision": policy.policy_revision,
            "policyDigest": policy.policy_digest,
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
    skill_digest = canonical_digest({"skill": ids["skill"], "operation": operation})
    employee_digest = canonical_digest(
        {"employee": ids["employee-definition"], "skillDigest": skill_digest}
    )
    plan_digest = canonical_digest({"plan": ids["plan"]})
    approval_id = f"approval:{suffix}"
    authorization_id = f"authorization:{suffix}"
    binding_id = stable_id(
        "skill-binding",
        ids["employee-definition"],
        ids["employee-revision"],
        ids["skill"],
        ids["skill-revision"],
    )
    binding_semantic = {
        "bindingId": binding_id,
        "employeeDefinitionId": ids["employee-definition"],
        "employeeRevisionId": ids["employee-revision"],
        "skillId": ids["skill"],
        "skillRevisionId": ids["skill-revision"],
        "skillDigest": skill_digest,
        "operation": operation["name"],
    }
    binding_digest = canonical_digest(binding_semantic)
    employee_record = {
        "members": [
            {
                "kind": "SKILL",
                "resource_id": ids["skill"],
                "revision_id": ids["skill-revision"],
                "digest": skill_digest,
            }
        ]
    }
    skill_record = {
        "resourceId": ids["skill"],
        "kind": "skill",
        "enabled": True,
        "publishedRevisionId": ids["skill-revision"],
        "revisions": [
            {
                "revisionId": ids["skill-revision"],
                "digest": skill_digest,
                "state": "PUBLISHED",
                "content": {"operations": [operation]},
            }
        ],
    }
    with psycopg.connect(DATABASE_URL or "") as connection:
        connection.execute(
            "INSERT INTO workflow_definition.definitions(namespace,security_domain,workflow_definition_id,aggregate_version,record) VALUES(%s,%s,%s,1,'{}')",
            (scope.namespace, scope.security_domain, ids["workflow-definition"]),
        )
        connection.execute(
            """INSERT INTO execution_authority.plans(namespace,security_domain,plan_id,plan_version,
            workflow_definition_id,workflow_definition_revision_id,workflow_definition_digest,status,
            plan_digest,canonical_bytes,created_at,updated_at) VALUES(%s,%s,%s,1,%s,'revision:1',%s,'APPROVED',%s,'{}',now(),now())""",
            (
                scope.namespace,
                scope.security_domain,
                ids["plan"],
                ids["workflow-definition"],
                "a" * 64,
                plan_digest,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.digital_employee_instances(namespace,security_domain,digital_employee_instance_id,definition_revision_id,aggregate_version,record) VALUES(%s,%s,%s,%s,1,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["employee"],
                ids["employee-revision"],
            ),
        )
        connection.execute(
            """INSERT INTO execution_authority.plan_approval_decisions(namespace,security_domain,
            approval_decision_id,plan_id,plan_version,plan_digest,ordinal,decision,actor_id,
            authority_basis,reason_category,decision_digest,decided_at)
            VALUES(%s,%s,%s,%s,1,%s,1,'APPROVE','reviewer','HUMAN_REVIEW','BUSINESS_APPROVAL',%s,now())""",
            (
                scope.namespace,
                scope.security_domain,
                approval_id,
                ids["plan"],
                plan_digest,
                "d" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.assignments(namespace,security_domain,assignment_id,digital_employee_instance_id,approved_input_digest,record) VALUES(%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["assignment"],
                ids["employee"],
                plan_digest,
            ),
        )
        connection.execute(
            """INSERT INTO execution_authority.workflow_runs(namespace,security_domain,workflow_run_id,
            assignment_id,approved_plan_revision_id,record,control_state,plan_id,plan_version,approved_plan_digest)
            VALUES(%s,%s,%s,%s,'revision:1','{}','RUNNING',%s,1,%s)""",
            (
                scope.namespace,
                scope.security_domain,
                ids["workflow"],
                ids["assignment"],
                ids["plan"],
                plan_digest,
            ),
        )
        connection.execute(
            "INSERT INTO execution_authority.task_runs(namespace,security_domain,task_run_id,workflow_run_id,record) VALUES(%s,%s,%s,%s,'{}')",
            (scope.namespace, scope.security_domain, ids["task"], ids["workflow"]),
        )
        connection.execute(
            "INSERT INTO execution_authority.attempts(namespace,security_domain,attempt_id,task_run_id,aggregate_digest,record) VALUES(%s,%s,%s,%s,%s,'{}')",
            (
                scope.namespace,
                scope.security_domain,
                ids["attempt"],
                ids["task"],
                "b" * 64,
            ),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.definitions(namespace,security_domain,definition_id,aggregate_version) VALUES(%s,%s,%s,1)",
            (scope.namespace, scope.security_domain, ids["employee-definition"]),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.revisions(namespace,security_domain,definition_id,revision_id,digest,record) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
            (
                scope.namespace,
                scope.security_domain,
                ids["employee-definition"],
                ids["employee-revision"],
                employee_digest,
                json.dumps(employee_record),
            ),
        )
        connection.execute(
            "INSERT INTO digital_employee_definition.instance_bindings(namespace,security_domain,digital_employee_instance_id,definition_id,revision_id,digest) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                scope.namespace,
                scope.security_domain,
                ids["employee"],
                ids["employee-definition"],
                ids["employee-revision"],
                employee_digest,
            ),
        )
        connection.execute(
            """INSERT INTO digital_employee_definition.execution_bindings(namespace,security_domain,
            attempt_id,digital_employee_instance_id,definition_id,revision_id,digest,plan_digest,
            approval_id,authorization_decision_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                scope.namespace,
                scope.security_domain,
                ids["attempt"],
                ids["employee"],
                ids["employee-definition"],
                ids["employee-revision"],
                employee_digest,
                plan_digest,
                approval_id,
                authorization_id,
            ),
        )
        connection.execute(
            "INSERT INTO skill_mcp_resource.resources(namespace,security_domain,kind,resource_id,aggregate_version,record) VALUES(%s,%s,'skill',%s,1,%s::jsonb)",
            (
                scope.namespace,
                scope.security_domain,
                ids["skill"],
                json.dumps(skill_record),
            ),
        )
    use_id = stable_id(
        "resource-use",
        scope.namespace,
        scope.security_domain,
        ids["attempt"],
        "SKILL",
        "skill:primary",
        "1",
    )
    resource_binding = ResourceUseBinding(
        scope=scope,
        resource_use_id=use_id,
        attempt_id=ids["attempt"],
        resource_kind=ResourceKind.SKILL,
        slot_key="skill:primary",
        occurrence_ordinal=1,
        resource_id=ids["skill"],
        resource_revision_id=ids["skill-revision"],
        resource_digest=skill_digest,
        binding_id=binding_id,
        binding_digest=binding_digest,
        plan_id=ids["plan"],
        plan_version=1,
        plan_digest=plan_digest,
        workflow_run_id=ids["workflow"],
        task_run_id=ids["task"],
        digital_employee_definition_id=ids["employee-definition"],
        digital_employee_definition_revision_id=ids["employee-revision"],
        digital_employee_definition_digest=employee_digest,
        digital_employee_instance_id=ids["employee"],
        agent_instance_id=None,
        runtime_instance_id=None,
        executor_id=executor.revision.executor_id,
        executor_revision=executor.revision.executor_revision,
        provider_id="local-read-only-service",
        provider_revision="1",
        authorization_decision_id=authorization_id,
    )
    request = SkillInvocationRequest(
        scope=scope,
        idempotency_key=f"skill-key:{suffix}",
        attempt_id=ids["attempt"],
        workflow_run_id=ids["workflow"],
        task_run_id=ids["task"],
        plan_id=ids["plan"],
        plan_version=1,
        plan_digest=plan_digest,
        approval_id=approval_id,
        assignment_id=ids["assignment"],
        digital_employee_definition_id=ids["employee-definition"],
        digital_employee_definition_revision_id=ids["employee-revision"],
        digital_employee_definition_digest=employee_digest,
        digital_employee_instance_id=ids["employee"],
        agent_instance_id=None,
        runtime_instance_id=None,
        skill_id=ids["skill"],
        skill_revision_id=ids["skill-revision"],
        skill_digest=skill_digest,
        operation=operation["name"],
        input_schema_digest=canonical_digest(input_schema),
        output_schema_digest=canonical_digest(output_schema),
        binding_id=binding_id,
        binding_digest=binding_digest,
        executor=executor.revision,
        side_effect_class=SideEffectClass.READ_ONLY,
        policy=policy,
        io_limits=limits,
        authorization_decision_id=authorization_id,
        resource_use=resource_binding,
    )
    resource_repo = PostgresResourceUseRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0015_resource_use_measurement.sql",
    )
    resource_repo.migrate()
    repository = PostgresSkillInvocationRepository(
        DATABASE_URL or "",
        migration_path=MIGRATIONS / "0016_skill_invocation.sql",
        resource_use_repository=resource_repo,
        terminal_hook=terminal_hook,
    )
    repository.migrate()
    service = GovernedAttemptSkillInvocationService(
        repository,
        ScopedSkillInvocationAuthorization(
            scope,
            "operator",
            frozenset({"INVOKE_SKILL", "READ_SKILL_INVOCATION"}),
            authorization_id,
        ),
        FixedReadOnlyPolicyAuthority(policy),
        SkillExecutorRegistry((executor,)),
    )
    return service, repository, resource_repo, request


INPUT = {"supplier": "ACME", "defects": [{"severity": 2}, {"severity": 5}]}


def _close(*repositories):
    for repository in repositories:
        repository.close()


def test_real_read_only_protocol_atomic_resource_use_replay_and_restart():
    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            result = service.invoke(request, INPUT)
            assert result.state is InvocationState.SUCCEEDED
            assert result.technical_success_not_business_success
            assert len(calls) == 1
            assert calls[0] == {
                "schemaVersion": "read-only-skill-request.v1",
                "invocationId": request.invocation_id,
                "operation": "supplier-quality.summary",
                "input": INPUT,
            }
            assert service.invoke(request, INPUT) == result
            assert len(calls) == 1
            read = service.read(request.scope, request.invocation_id)
            assert read["state"] == "SUCCEEDED"
            assert read["technicalSuccessNotBusinessSuccess"] is True
            use = resource.get_snapshot(
                request.scope, request.resource_use.resource_use_id
            )
            assert use.effective_state.value == "SUCCEEDED"
            assert use.evidence_references == (result.evidence_id,)
            assert len(use.measurement_ids) == 3
            with repository.pool.connection() as connection:
                row = connection.execute(
                    "SELECT record FROM skill_invocation.evidence WHERE namespace=%s AND evidence_id=%s",
                    (request.scope.namespace, result.evidence_id),
                ).fetchone()["record"]
                assert (
                    row["rawInputStored"] is False and row["rawOutputStored"] is False
                )
                assert "ACME" not in json.dumps(row)
                assert (
                    connection.execute(
                        "SELECT count(*) AS n FROM resource_use.claims WHERE namespace=%s AND resource_use_id=%s",
                        (request.scope.namespace, request.resource_use.resource_use_id),
                    ).fetchone()["n"]
                    == 2
                )
            restarted = PostgresSkillInvocationRepository(
                DATABASE_URL or "",
                migration_path=MIGRATIONS / "0016_skill_invocation.sql",
                resource_use_repository=resource,
            )
            try:
                assert (
                    restarted.get_snapshot(request.scope, request.invocation_id)
                    == result
                )
            finally:
                restarted.close()
        finally:
            _close(repository, resource)


def test_concurrent_replay_dispatches_once_and_payload_mismatch_fails_closed():
    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = tuple(
                    executor.map(lambda _: service.invoke(request, INPUT), range(2))
                )
            assert any(item.state is InvocationState.SUCCEEDED for item in results)
            assert service.invoke(request, INPUT).state is InvocationState.SUCCEEDED
            assert len(calls) == 1
            with pytest.raises(
                SkillInvocationConflict, match="SKILL_IDEMPOTENCY_PAYLOAD_MISMATCH"
            ):
                service.invoke(
                    request, {"supplier": "OTHER", "defects": [{"severity": 1}]}
                )
            assert len(calls) == 1
        finally:
            _close(repository, resource)


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("plan_digest", "0" * 64, "SKILL_RESOURCE_USE_BINDING_MISMATCH"),
        ("skill_digest", "0" * 64, "SKILL_RESOURCE_USE_BINDING_MISMATCH"),
        ("input_schema_digest", "0" * 64, "SKILL_SCHEMA_DIGEST_MISMATCH"),
        ("binding_digest", "0" * 64, "SKILL_RESOURCE_USE_BINDING_MISMATCH"),
        ("approval_id", "approval:stale", "SKILL_EXECUTION_LINEAGE_MISMATCH"),
    ),
)
def test_exact_stale_snapshot_rejected_with_zero_dispatch(field, value, code):
    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            with pytest.raises(SkillInvocationError, match=code):
                bad = replace(request, **{field: value})
                service.invoke(bad, INPUT)
            assert calls == []
        finally:
            _close(repository, resource)


def test_denial_cross_scope_and_missing_permission_do_not_lookup_or_dispatch():
    scope = ScopeIdentity("authorized", "domain")

    class Never:
        def __getattr__(self, _name):
            pytest.fail("denied invocation reached a protected dependency")

    for authorization in (
        None,
        ScopedSkillInvocationAuthorization(scope, "actor", frozenset(), "decision"),
        ScopedSkillInvocationAuthorization(
            ScopeIdentity("foreign", "domain"),
            "actor",
            frozenset({"INVOKE_SKILL"}),
            "decision",
        ),
    ):
        service = GovernedAttemptSkillInvocationService(
            Never(), authorization, Never(), Never()
        )
        request = object.__new__(SkillInvocationRequest)
        object.__setattr__(request, "scope", scope)
        object.__setattr__(request, "attempt_id", "attempt")
        with pytest.raises(SkillInvocationError, match="SKILL_INVOCATION_NOT_FOUND"):
            service.invoke(request, {})


@pytest.mark.parametrize("mode", ("timeout", "disconnect"))
def test_post_dispatch_ambiguity_is_unknown_and_never_redispatched(mode):
    with protocol_service(mode) as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint, timeout_ms=80)
        try:
            first = service.invoke(request, INPUT)
            assert first.state is InvocationState.OUTCOME_UNKNOWN
            assert first.error_code == "SKILL_EXECUTOR_OUTCOME_UNKNOWN"
            assert service.invoke(request, INPUT) == first
            time.sleep(0.25)
            assert len(calls) == 1
        finally:
            _close(repository, resource)


def test_output_schema_failure_is_terminal_failure_not_business_success():
    with protocol_service("bad-schema") as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            result = service.invoke(request, INPUT)
            assert result.state is InvocationState.FAILED
            assert result.error_code == "SKILL_OUTPUT_SCHEMA_MISMATCH"
            assert len(calls) == 1
        finally:
            _close(repository, resource)


def test_terminal_late_failure_rolls_back_then_recovery_blocks_redispatch():
    def fail(_connection):
        raise RuntimeError("INJECTED_TERMINAL_ROLLBACK")

    with protocol_service() as (endpoint, calls):
        service, broken, resource, request = _scenario(endpoint, terminal_hook=fail)
        try:
            with pytest.raises(RuntimeError, match="INJECTED_TERMINAL_ROLLBACK"):
                service.invoke(request, INPUT)
            assert len(calls) == 1
            durable = broken.get_snapshot(request.scope, request.invocation_id)
            assert durable.state is InvocationState.DISPATCH_RECORDED
            healthy = PostgresSkillInvocationRepository(
                DATABASE_URL or "",
                migration_path=MIGRATIONS / "0016_skill_invocation.sql",
                resource_use_repository=resource,
            )
            recovered_service = GovernedAttemptSkillInvocationService(
                healthy,
                service.authorization,
                service.policy_authority,
                service.executors,
            )
            try:
                recovered = recovered_service.recover(request, INPUT)
                assert recovered.state is InvocationState.OUTCOME_UNKNOWN
                assert recovered.error_code == "SKILL_RESULT_PENDING_CONFIRMATION"
                assert len(calls) == 1
            finally:
                healthy.close()
        finally:
            _close(broken, resource)


def test_failed_recovery_still_preserves_durable_dispatch_identity():
    def fail(_connection):
        raise RuntimeError("INJECTED_TERMINAL_ROLLBACK")

    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint, terminal_hook=fail)
        try:
            with pytest.raises(RuntimeError, match="INJECTED_TERMINAL_ROLLBACK"):
                service.invoke(request, INPUT)
            with pytest.raises(RuntimeError, match="INJECTED_TERMINAL_ROLLBACK"):
                service.recover(request, INPUT)
            assert (
                repository.get_snapshot(request.scope, request.invocation_id).state
                is InvocationState.DISPATCH_RECORDED
            )
            assert len(calls) == 1
        finally:
            _close(repository, resource)


def test_second_managed_slot_and_history_rewrite_fail_closed():
    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            first = service.invoke(request, INPUT)
            second = replace(
                request, idempotency_key=f"{request.idempotency_key}:second"
            )
            with pytest.raises(psycopg.Error):
                service.invoke(second, INPUT)
            assert len(calls) == 1
            with (
                repository.pool.connection() as connection,
                pytest.raises(
                    psycopg.Error, match="IMMUTABLE_SKILL_INVOCATION_HISTORY"
                ),
            ):
                connection.execute(
                    "DELETE FROM skill_invocation.facts WHERE namespace=%s AND skill_invocation_id=%s",
                    (request.scope.namespace, first.invocation_id),
                )
        finally:
            _close(repository, resource)


def test_unknown_and_write_side_effects_and_input_contract_fail_before_dispatch():
    with protocol_service() as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            for side_effect in (
                SideEffectClass.UNKNOWN,
                SideEffectClass.IDEMPOTENT_WRITE,
                SideEffectClass.NON_IDEMPOTENT_WRITE,
            ):
                with pytest.raises(
                    SkillInvocationError, match="SKILL_SIDE_EFFECT_NOT_ALLOWED"
                ):
                    replace(request, side_effect_class=side_effect)
            stale_policy = SideEffectPolicy(
                request.policy.policy_id,
                request.policy.policy_revision,
                "0" * 64,
                SideEffectClass.READ_ONLY,
            )
            with pytest.raises(
                SkillInvocationError, match="SKILL_SIDE_EFFECT_POLICY_MISMATCH"
            ):
                service.invoke(replace(request, policy=stale_policy), INPUT)
            with pytest.raises(
                SkillInvocationError, match="EXECUTOR_REVISION_UNAVAILABLE"
            ):
                service.invoke(
                    replace(
                        request,
                        executor=ExecutorRevision(
                            request.executor.executor_id,
                            request.executor.executor_revision,
                            "0" * 64,
                        ),
                    ),
                    INPUT,
                )
            with pytest.raises(
                SkillInvocationError, match="SKILL_OPERATION_NOT_ELIGIBLE"
            ):
                service.invoke(replace(request, operation="stale.operation"), INPUT)
            with pytest.raises(
                SkillInvocationError, match="SKILL_INPUT_SCHEMA_MISMATCH"
            ):
                service.invoke(request, {"supplier": "ACME"})
            with pytest.raises(
                SkillInvocationError, match="SKILL_INPUT_SCHEMA_MISMATCH"
            ):
                service.invoke(
                    request,
                    {"supplier": "ACME", "defects": [{"severity": "high"}]},
                )
            with pytest.raises(SkillInvocationError, match="SKILL_INPUT_TOO_LARGE"):
                service.invoke(request, {"supplier": "X" * 5000, "defects": []})
            assert calls == []
        finally:
            _close(repository, resource)


def test_oversized_output_is_bounded_failure_with_no_raw_output():
    with protocol_service("large") as (endpoint, calls):
        service, repository, resource, request = _scenario(endpoint)
        try:
            result = service.invoke(request, INPUT)
            assert result.state is InvocationState.FAILED
            assert result.error_code == "SKILL_OUTPUT_TOO_LARGE"
            assert len(calls) == 1
            with repository.pool.connection() as connection:
                evidence = connection.execute(
                    "SELECT record FROM skill_invocation.evidence WHERE namespace=%s AND skill_invocation_id=%s",
                    (request.scope.namespace, request.invocation_id),
                ).fetchone()["record"]
            assert "XXXXX" not in json.dumps(evidence)
        finally:
            _close(repository, resource)
