# ruff: noqa: F401,F811,E501 -- Explicit isolated owner fixtures.
"""Real owner SQL and loopback Kubernetes GET checks; not live acceptance."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.employee_execution_trace import (
    EmployeeExecutionTrace,
    ExactTaskObserver,
    ObservationConfiguration,
    correlated_task,
)
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerCall,
    WorkbenchOwnerError,
)
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_workbench_employee_relations import relations


@pytest.fixture
def trace(relations):
    r = relations
    a = r.a
    ref = r.ref.model_dump(mode="json")
    digest = "e" * 64
    actor = {
        "task_id": "read",
        "definition": ref,
        "instance_id": "instance:relations-1",
        "assignment_id": "assignment:relations-1",
        "agent_instance_id": "agent:isolated",
        "runtime_instance_id": "runtime:isolated",
        "runtime_generation": 1,
        "profile": {
            "resource_id": "profile:isolated",
            "revision_id": "1",
            "digest": "b" * 64,
        },
    }
    p = {
        "plan_version": 1,
        "root_instance_id": "instance:relations-1",
        "root_assignment_id": "assignment:relations-1",
        "participants": [actor],
        "semantics": {
            "title": "Explicit isolated task participation",
            "target": {
                "problem": {"resource_id": a.e.p.semantics.target.problem.resource_id}
            },
            "tasks": [{"task_id": "read", "title": "Read original source"}],
        },
    }
    view = {
        "digest": digest,
        "preparation": p,
        "progress": {
            "state": "SUCCEEDED",
            "tasks": [{"task_id": "read", "state": "SUCCEEDED", "attempt_id": None}],
        },
    }
    denied = set()

    class ACL:
        def require(self, principal, owner, action, resource):
            if owner in denied:
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            if owner == "EXECUTION":
                return SimpleNamespace(
                    decision_id="explicit-isolated-execution-fixture"
                )
            return r.acl.require(principal, owner, action, resource)

    handler = EmployeeExecutionTrace(r.instances)
    handler.saved.execution = lambda _: deepcopy(view)
    with a.repository.pool.connection() as c, c.transaction():
        c.execute(
            "INSERT INTO execution_authority.prepared_candidates(namespace,security_domain,digest,plan_id,plan_version,record,prepared_by) VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)",
            (
                a.e.scope.namespace,
                a.e.scope.security_domain,
                digest,
                a.e.p.plan_id,
                a.e.p.plan_version,
                json.dumps(p),
                a.subject.principal_id,
            ),
        )

    def call(operation, path=None):
        with a.repository.pool.connection() as c, c.transaction():
            return handler(
                AuthorizedOwnerCall(
                    context=a.subject,
                    connection=c,
                    decisions=(),
                    operation=operation,
                    authority=ACL(),
                    path=path
                    or {
                        "instance_id": "instance:relations-1",
                        "assignment_id": "assignment:relations-1",
                        "digest": digest,
                        "task_id": "read",
                    },
                    payload={},
                    query={},
                )
            )

    return SimpleNamespace(r=r, handler=handler, view=view, denied=denied, call=call)


def test_assignment_to_exact_saved_work_and_runtime_binding(trace):
    r = trace
    items = r.call("READ_ASSIGNMENT_EXECUTIONS")["items"]
    assert (
        len(items) == 1
        and items[0]["state"] == "SUCCEEDED"
        and items[0]["tasks"] == [{"taskId": "read", "title": "Read original source"}]
    )
    view = r.call("READ_EXECUTION_RUNTIME_REVIEW")
    assert view["executionStarted"] is False
    assert view["tasks"][0]["runtimeInstanceId"] == "runtime:isolated"
    assert view["tasks"][0]["providerHealth"] == "NOT_OBSERVED"


@pytest.mark.parametrize("owner", ["INSTANCE", "ASSIGNMENT", "EMPLOYEE", "EXECUTION"])
def test_current_exact_permission_required_without_revealing_old_trace(trace, owner):
    trace.denied.add(owner)
    if owner == "EXECUTION":
        assert trace.call("READ_ASSIGNMENT_EXECUTIONS")["items"] == []
    else:
        with pytest.raises(AuthorityError):
            trace.call("READ_ASSIGNMENT_EXECUTIONS")
    with pytest.raises(AuthorityError):
        trace.call("READ_EXECUTION_RUNTIME_REVIEW")


def test_foreign_assignment_and_definition_mismatch_fail_closed(trace):
    with pytest.raises((AuthorityError, WorkbenchOwnerError)):
        trace.call(
            "READ_ASSIGNMENT_EXECUTIONS",
            {
                "instance_id": "instance:relations-2",
                "assignment_id": "assignment:relations-1",
            },
        )
    trace.view["preparation"]["participants"][0]["definition"]["digest"] = "0" * 64
    with pytest.raises(WorkbenchOwnerError, match="DEFINITION_MISMATCH"):
        trace.call("READ_EXECUTION_RUNTIME_REVIEW")


def command():
    return {
        "namespace": "isolated-native",
        "command_id": "dispatch:isolated",
        "attempt_id": "attempt:isolated",
        "agent_name": "agent:isolated",
        "placement_id": "placement:isolated",
        "runtime_instance_id": "runtime:isolated",
        "runtime_generation": 1,
        "kubernetes_task_name": "task-isolated",
        "kubernetes_task_uid": "task-uid-isolated",
    }


def task_body(c):
    return {
        "apiVersion": "agentos.io/v1alpha1",
        "kind": "Task",
        "metadata": {
            "namespace": c["namespace"],
            "name": c["kubernetes_task_name"],
            "uid": c["kubernetes_task_uid"],
            "resourceVersion": "17",
            "labels": {
                "agentos.io/native-dispatch-managed": "true",
                "agentos.io/native-dispatch-command": hashlib.sha256(
                    c["command_id"].encode()
                ).hexdigest()[:40],
            },
            "annotations": {
                "agentos.io/attempt-id": c["attempt_id"],
                "agentos.io/placement-id": c["placement_id"],
                "agentos.io/runtime-instance-id": c["runtime_instance_id"],
                "agentos.io/runtime-generation": str(c["runtime_generation"]),
            },
        },
        "spec": {
            "agentRef": {"name": c["agent_name"]},
            "input": {"prompt": "DO_NOT_RETURN_PROMPT"},
        },
        "status": {"phase": "Succeeded", "output": "DO_NOT_RETURN_OUTPUT"},
    }


@pytest.mark.parametrize(
    "field", ["uid", "attempt", "generation", "agent", "command", "kind", "apiVersion"]
)
def test_replaced_or_unrelated_task_never_counts_as_current_observation(field):
    c = command()
    body = task_body(c)
    if field == "kind":
        body["kind"] = "Other"
    elif field == "apiVersion":
        body["apiVersion"] = "other/v1"
    elif field == "uid":
        body["metadata"]["uid"] = "replaced"
    elif field == "agent":
        body["spec"]["agentRef"]["name"] = "other"
    elif field == "command":
        body["metadata"]["labels"]["agentos.io/native-dispatch-command"] = "other"
    else:
        body["metadata"]["annotations"][
            "agentos.io/"
            + ("attempt-id" if field == "attempt" else "runtime-generation")
        ] = "other"
    with pytest.raises(WorkbenchOwnerError, match="CORRELATION_CHANGED"):
        correlated_task(c, body)


def test_actual_kubernetes_client_uses_only_exact_get_and_sanitized_current_result(
    tmp_path,
):
    c = command()
    body = task_body(c)
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append(("GET", self.path))
            value = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(value)))
            self.end_headers()
            self.wfile.write(value)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        path = tmp_path / "kubeconfig"
        path.write_text(
            json.dumps(
                {
                    "apiVersion": "v1",
                    "kind": "Config",
                    "current-context": "isolated",
                    "contexts": [
                        {
                            "name": "isolated",
                            "context": {"cluster": "isolated", "user": "isolated"},
                        }
                    ],
                    "clusters": [
                        {
                            "name": "isolated",
                            "cluster": {
                                "server": f"http://127.0.0.1:{server.server_port}"
                            },
                        }
                    ],
                    "users": [{"name": "isolated", "user": {}}],
                }
            )
        )
        path.chmod(0o600)
        cfg = ObservationConfiguration(
            schemaVersion="execution-runtime-observation.v1",
            kubeconfig=str(path),
            kubeconfigSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            subject="human:fixture",
            tenantId="fixture",
            securityDomain="isolated",
            executionDigests=("e" * 64,),
            expiresAt=datetime.now(UTC) + timedelta(minutes=5),
        )
        observed = correlated_task(c, ExactTaskObserver(cfg).read(c))
        assert (
            observed["phase"] == "Succeeded"
            and observed["providerHealth"] == "NOT_OBSERVED"
        )
        assert requests == [
            (
                "GET",
                "/apis/agentos.io/v1alpha1/namespaces/isolated-native/tasks/task-isolated",
            )
        ]
        assert "DO_NOT_RETURN" not in json.dumps(observed)
        path.write_text(path.read_text() + " ")
        with pytest.raises(WorkbenchOwnerError, match="CONFIGURATION_CHANGED"):
            ExactTaskObserver(cfg).read(c)
        assert len(requests) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_unapproved_or_not_dispatched_observation_never_touches_cluster(trace):
    calls = []
    trace.handler.observer = SimpleNamespace(read=lambda c: calls.append(c))
    with pytest.raises(WorkbenchOwnerError, match="SCOPE_REQUIRED"):
        trace.call("READ_EXECUTION_TASK_OBSERVATION")
    trace.handler.policy = SimpleNamespace(allows=lambda *_: True)
    with pytest.raises(WorkbenchOwnerError, match="NOT_DISPATCHED"):
        trace.call("READ_EXECUTION_TASK_OBSERVATION")
    assert calls == []


def test_deleting_task_retains_history_but_does_not_report_current_success():
    c = command()
    body = task_body(c)
    body["metadata"]["deletionTimestamp"] = "2026-11-08T00:00:00Z"
    result = correlated_task(c, body)
    assert result["phase"] == "Deleting"
    assert result["providerHealth"] == "NOT_OBSERVED"
    assert result["executionStarted"] is False


def test_runtime_detail_reads_actual_lifecycle_without_dispatch(trace):
    detail = trace.call("READ_EXECUTION_RUNTIME_DETAIL")["detail"]
    assert detail["instance"]["lifecycle"] == "ENABLED"
    assert detail["assignment"]["lifecycle"] == "ACTIVE"
    assert detail["placement"] is None
    assert detail["placementStatus"] == "NOT_DISPATCHED"
    assert detail["providerHealth"] == "NOT_OBSERVED"
    assert detail["executionStarted"] is False


@pytest.mark.parametrize("mode", ["verified", "denied", "missing", "wrong-runtime"])
def test_runtime_detail_uses_exact_owner_placement_and_never_infers_health(trace, mode):
    trace.view["progress"]["tasks"][0]["attempt_id"] = "attempt:isolated"
    calls = []
    real_owner = trace.handler.instances
    trace.handler.dispatch = lambda *_: {"placement_id": "placement:isolated"}
    original_require = trace.handler.require

    def require(call, owner, resource):
        if owner == "PLACEMENT":
            calls.append((owner, resource))
            if mode == "denied":
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")
            return
        return original_require(call, owner, resource)

    def placement(call):
        if call.operation != "READ_EMPLOYEE_PLACEMENT":
            return real_owner(call)
        calls.append((call.path, call.query))
        assert call.path == {
            "instance_id": "instance:relations-1",
            "assignment_id": "assignment:relations-1",
            "placement_id": "placement:isolated",
        }
        assert call.query == {
            "attemptId": "attempt:isolated",
            "agentInstanceId": "agent:isolated",
        }
        if mode == "missing":
            raise WorkbenchOwnerError("PLACEMENT_NOT_FOUND", 404)
        return {
            "runtimeInstanceId": "runtime:foreign"
            if mode == "wrong-runtime"
            else "runtime:isolated"
        }

    trace.handler.require = require
    from dataclasses import replace

    trace.handler.saved_placement = lambda call, task, command: placement(
        replace(
            call,
            operation="READ_EMPLOYEE_PLACEMENT",
            path={
                "instance_id": task["instanceId"],
                "assignment_id": task["assignmentId"],
                "placement_id": command["placement_id"],
            },
            query={
                "attemptId": task["attemptId"],
                "agentInstanceId": task["agentInstanceId"],
            },
        )
    )
    if mode == "wrong-runtime":
        with pytest.raises(WorkbenchOwnerError, match="PLACEMENT_BINDING_CHANGED"):
            trace.call("READ_EXECUTION_RUNTIME_DETAIL")
    else:
        detail = trace.call("READ_EXECUTION_RUNTIME_DETAIL")["detail"]
        assert detail["placementStatus"] == (
            "VERIFIED" if mode == "verified" else "UNAVAILABLE"
        )
        assert detail["providerHealth"] == "NOT_OBSERVED"
    assert calls[0] == ("PLACEMENT", "placement:placement:isolated")
    assert len(calls) == (1 if mode == "denied" else 2)


def test_started_execution_missing_task_state_is_unknown(trace):
    trace.view["progress"]["tasks"] = []
    assert trace.call("READ_EXECUTION_RUNTIME_REVIEW")["tasks"][0]["state"] == "UNKNOWN"


def test_placement_read_target_requires_same_scope_and_never_grants(trace):
    from agent_console.authority_contracts import ExactGrant
    from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator

    calls = []

    class Connection:
        def execute(self, sql, params):
            calls.append((sql, params))
            assert "execution_authority.placement_decisions" in sql
            return SimpleNamespace(
                fetchone=lambda: (
                    {"exists": 1}
                    if params
                    == (
                        trace.r.a.subject.scope.tenant_id,
                        trace.r.a.subject.scope.security_domain,
                        "placement:fixture",
                    )
                    else None
                )
            )

    v = WorkbenchGrantTargetValidator(None)
    context = trace.r.a.subject
    exact = ExactGrant("PLACEMENT", "READ", "placement:placement:fixture")
    assert v.is_known_exact_target(context, exact, connection=Connection())
    assert not v.is_known_exact_target(
        context,
        ExactGrant("PLACEMENT", "READ", "placement:missing"),
        connection=Connection(),
    )
    from dataclasses import replace

    assert not v.is_known_exact_target(
        replace(context, scope=replace(context.scope, tenant_id="foreign")),
        exact,
        connection=Connection(),
    )
    with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
        v.is_known_exact_target(context, exact)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "mode", ["valid", "missing", "canonical", "dispatch-digest", "runtime"]
)
def test_saved_completed_placement_is_canonical_and_bound_without_active_lease(mode):
    from agent_console.execution_postgres import (
        PlacementDecision,
        PlacementDecisionKind,
        PlacementId,
        PlacementRequestId,
        RuntimeInstanceId,
    )

    value = PlacementDecision.create(
        placement_id=PlacementId("placement:saved"),
        request_id=PlacementRequestId("request:saved"),
        decision=PlacementDecisionKind.PLACED,
        runtime_instance_id=RuntimeInstanceId("runtime:saved"),
        policy_version="policy:saved",
        compatibility_facts=(),
        limitation_codes=(),
        decided_at=datetime.now(UTC),
    )
    record = {**value.canonical_payload, "digest": value.digest}
    if mode == "canonical":
        record["policy_version"] = "tampered"
    queries = []

    class Connection:
        def execute(self, sql, args):
            assert "active" not in sql.lower()
            assert args == (
                "tenant",
                "domain",
                "placement:saved",
                "attempt:saved",
                "agent:saved",
            )
            queries.append(sql)
            return SimpleNamespace(
                fetchone=lambda: (
                    None
                    if mode == "missing"
                    else {"canonical_record": record, "digest": value.digest}
                )
            )

    call = SimpleNamespace(
        connection=Connection(),
        context=SimpleNamespace(
            scope=SimpleNamespace(tenant_id="tenant", security_domain="domain")
        ),
    )
    task = {
        "instanceId": "instance:saved",
        "assignmentId": "assignment:saved",
        "attemptId": "attempt:saved",
        "agentInstanceId": "agent:saved",
        "runtimeInstanceId": "foreign" if mode == "runtime" else "runtime:saved",
    }
    command = {
        "placement_id": "placement:saved",
        "placement_digest": "0" * 64 if mode == "dispatch-digest" else value.digest,
    }
    if mode != "valid":
        with pytest.raises(WorkbenchOwnerError):
            EmployeeExecutionTrace.saved_placement(None, call, task, command)
    else:
        result = EmployeeExecutionTrace.saved_placement(None, call, task, command)
        assert result["evidenceKind"] == "SAVED_DISPATCH_PLACEMENT"
        assert result["digest"] == value.digest
        assert result["binding"]["assignmentId"] == "assignment:saved"
    assert len(queries) == 1
