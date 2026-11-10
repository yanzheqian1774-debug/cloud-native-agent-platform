# ruff: noqa: E501 -- Exact scoped SQL and correlations.
"""Read-only employee participation and saved Native execution observations."""

import hashlib
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from pydantic import BaseModel, ConfigDict, Field
from urllib3.exceptions import HTTPError as KubernetesTransportError

from .authority_contracts import AuthorityError
from .execution_postgres import PlacementDecision
from .execution_source_review import ExecutionSourceReview
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_employee import (
    DigitalEmployeeOwnerAdapter,
    EmployeeDefinitionOwnerAdapter,
    _assignment_read,
    _employee_revision_read,
)
from .workbench_execution_origin import read_execution_origin
from .workbench_owner_authorization import WorkbenchOwnerError
from .workbench_prepared_execution import grant


class ObservationConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: str
    kubeconfig: str
    kubeconfigSha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    subject: str
    tenantId: str
    securityDomain: str
    executionDigests: tuple[str, ...] = Field(min_length=1, max_length=20)
    expiresAt: datetime

    def allows(self, context, digest):
        return (
            (self.subject, self.tenantId, self.securityDomain)
            == (
                context.principal_id,
                context.scope.tenant_id,
                context.scope.security_domain,
            )
            and digest in self.executionDigests
            and self.expiresAt.tzinfo is not None
            and self.expiresAt > datetime.now(UTC)
        )

    @classmethod
    def load(cls, path):
        value = cls.model_validate_json(Path(path).read_text())
        if value.schemaVersion != "execution-runtime-observation.v1":
            raise ValueError("RUNTIME_OBSERVATION_CONFIGURATION_INVALID")
        return value


class ExactTaskObserver:
    def __init__(self, configuration):
        self.configuration = configuration

    def read(self, command):
        settings = self.configuration
        path = Path(settings.kubeconfig)
        if (
            path.is_symlink()
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_mode & 0o077
            or hashlib.sha256(path.read_bytes()).hexdigest()
            != settings.kubeconfigSha256
        ):
            raise WorkbenchOwnerError("RUNTIME_OBSERVER_CONFIGURATION_CHANGED", 503)
        kube = client.Configuration()
        config.load_kube_config(config_file=str(path), client_configuration=kube)
        if urlsplit(kube.host).hostname not in {"127.0.0.1", "localhost"}:
            raise WorkbenchOwnerError("RUNTIME_OBSERVER_HOST_NOT_APPROVED", 503)
        kube.retries = 0
        # No ambient kubeconfig, cluster selection, coordinates, writes or list API.
        with client.ApiClient(kube) as api:
            return client.CustomObjectsApi(api).get_namespaced_custom_object(
                group="agentos.io",
                version="v1alpha1",
                namespace=command["namespace"],
                plural="tasks",
                name=command["kubernetes_task_name"],
                _request_timeout=(2, 4),
            )


def correlated_task(command, body):
    if (
        not isinstance(body, dict)
        or body.get("kind") != "Task"
        or body.get("apiVersion") != "agentos.io/v1alpha1"
        or not isinstance(body.get("metadata"), dict)
        or not isinstance(body.get("spec"), dict)
        or not isinstance(body.get("status", {}), dict)
    ):
        raise WorkbenchOwnerError("RUNTIME_TASK_CORRELATION_CHANGED", 409)
    metadata = body.get("metadata", {})
    annotations, labels = metadata.get("annotations", {}), metadata.get("labels", {})
    if (
        metadata.get("uid") != command["kubernetes_task_uid"]
        or metadata.get("namespace") != command["namespace"]
        or metadata.get("name") != command["kubernetes_task_name"]
        or labels.get("agentos.io/native-dispatch-managed") != "true"
        or labels.get("agentos.io/native-dispatch-command")
        != hashlib.sha256(command["command_id"].encode()).hexdigest()[:40]
        or body.get("spec", {}).get("agentRef", {}).get("name") != command["agent_name"]
        or any(
            annotations.get(k) != str(command[v])
            for k, v in {
                "agentos.io/attempt-id": "attempt_id",
                "agentos.io/placement-id": "placement_id",
                "agentos.io/runtime-instance-id": "runtime_instance_id",
                "agentos.io/runtime-generation": "runtime_generation",
            }.items()
        )
    ):
        raise WorkbenchOwnerError("RUNTIME_TASK_CORRELATION_CHANGED", 409)
    status = body.get("status", {})
    return {
        "taskUid": metadata["uid"],
        "taskName": metadata["name"],
        "resourceVersion": metadata.get("resourceVersion"),
        "phase": "Deleting"
        if metadata.get("deletionTimestamp")
        else status.get("phase", "Unknown"),
        "observedAt": datetime.now(UTC).isoformat(),
        "freshUntil": datetime.fromtimestamp(
            datetime.now(UTC).timestamp() + 30, UTC
        ).isoformat(),
        "classification": "CURRENT_KUBERNETES_TASK_OBSERVATION",
        "providerHealth": "NOT_OBSERVED",
        "executionStarted": False,
    }


class EmployeeExecutionTrace:
    def __init__(
        self,
        instances,
        coordinator=None,
        *,
        observer=None,
        policy=None,
        sales_v2_candidate=False,
        definitions=None,
    ):
        self.definitions = (
            EmployeeDefinitionOwnerAdapter(definitions)
            if definitions is not None
            else None
        )
        self.instances = DigitalEmployeeOwnerAdapter(instances)
        self.saved = ExecutionSourceReview(
            {}, coordinator, sales_v2_candidate=sales_v2_candidate
        )
        self.observer, self.policy = observer, policy

    @staticmethod
    def require(call, owner, resource):
        call.authority.require(
            ExecutionSourceReview.principal(call), owner, "READ", resource
        )

    def parents(self, call, instance_id, assignment_id):
        self.require(call, "INSTANCE", "instance:" + instance_id)
        self.require(call, "ASSIGNMENT", "assignment:" + assignment_id)
        path = {"instance_id": instance_id, "assignment_id": assignment_id}
        instance = self.instances(
            replace(call, operation="READ_EMPLOYEE_INSTANCE", path=path)
        )
        assignment = self.instances(
            replace(call, operation="READ_EMPLOYEE_ASSIGNMENT", path=path)
        )
        ref = instance["employeeDefinition"]
        self.require(
            call,
            "EMPLOYEE",
            f"employee:{ref['employeeDefinitionId']}:{ref['employeeDefinitionRevisionId']}",
        )
        if (
            assignment["instanceId"] != instance_id
            or assignment["assignmentId"] != assignment_id
        ):
            raise WorkbenchOwnerError("EMPLOYEE_TRACE_PARENT_MISMATCH", 409)
        return ref

    def links(self, call):
        iid, aid = call.path["instance_id"], call.path["assignment_id"]
        ref = self.parents(call, iid, aid)
        ctx = call.context
        candidates = call.connection.execute(
            "SELECT digest,record FROM execution_authority.prepared_candidates WHERE namespace=%s AND security_domain=%s AND ((record->>'root_instance_id'=%s AND record->>'root_assignment_id'=%s) OR EXISTS(SELECT 1 FROM jsonb_array_elements(record->'participants') p WHERE p->>'instance_id'=%s AND p->>'assignment_id'=%s)) ORDER BY digest LIMIT 201",
            (ctx.scope.tenant_id, ctx.scope.security_domain, iid, aid, iid, aid),
        ).fetchall()
        items = []
        for row in candidates[:200]:
            try:
                view = self.saved.saved(replace(call, path={"digest": row["digest"]}))
            except AuthorityError:
                continue
            p = view["preparation"]
            participants = [
                x
                for x in p["participants"]
                if (x["instance_id"], x["assignment_id"]) == (iid, aid)
            ]
            root = (p["root_instance_id"], p["root_assignment_id"]) == (iid, aid)
            if not root and not participants:
                raise WorkbenchOwnerError("EMPLOYEE_TRACE_EXECUTION_MISMATCH", 409)
            if any(
                x["definition"]
                != {
                    "resource_id": ref["employeeDefinitionId"],
                    "revision_id": ref["employeeDefinitionRevisionId"],
                    "digest": ref["digest"],
                }
                for x in participants
            ):
                raise WorkbenchOwnerError("EMPLOYEE_TRACE_DEFINITION_MISMATCH", 409)
            tasks = [
                t
                for t in p["semantics"]["tasks"]
                if root or any(x["task_id"] == t["task_id"] for x in participants)
            ]
            items.append(
                {
                    "executionDigest": view["digest"],
                    "problemId": p["semantics"]["target"]["problem"]["resource_id"],
                    "title": p["semantics"]["title"],
                    "planVersion": p["plan_version"],
                    "state": (view.get("progress") or {}).get("state", "NOT_STARTED"),
                    "tasks": [
                        {"taskId": t["task_id"], "title": t["title"]} for t in tasks
                    ],
                }
            )
        return {
            "schemaVersion": "employee-execution-links.v1",
            "subject": ctx.principal_id,
            "scope": {
                "tenantId": ctx.scope.tenant_id,
                "securityDomain": ctx.scope.security_domain,
            },
            "instanceId": iid,
            "assignmentId": aid,
            "employeeDefinition": ref,
            "items": items,
            "scanLimited": len(candidates) > 200,
            "visibility": "AUTHORIZED_ONLY",
            "executionStarted": False,
        }

    def employee_links(self, call):
        if self.definitions is None:
            raise WorkbenchOwnerError("EMPLOYEE_WORK_RECORDS_UNAVAILABLE", 503)
        identity, revision = (
            call.path["employee_definition_id"],
            call.path["revision_id"],
        )
        self.require(call, "EMPLOYEE", f"employee:{identity}:{revision}")
        definition = self.definitions(replace(call, operation="READ_EMPLOYEE_REVISION"))
        ref = {
            "resource_id": identity,
            "revision_id": revision,
            "digest": definition["employeeDefinitionDigest"],
        }
        ctx = call.context
        candidates = call.connection.execute(
            "SELECT p.digest,p.record FROM execution_authority.prepared_candidates p "
            "WHERE p.namespace=%s AND p.security_domain=%s AND ("
            "EXISTS(SELECT 1 FROM jsonb_array_elements(p.record->'participants') member "
            "WHERE member->'definition'->>'resource_id'=%s AND member->'definition'->>'revision_id'=%s AND member->'definition'->>'digest'=%s) "
            "OR EXISTS(SELECT 1 FROM digital_employee_definition.instance_bindings b "
            "WHERE b.namespace=p.namespace AND b.security_domain=p.security_domain "
            "AND b.digital_employee_instance_id=p.record->>'root_instance_id' "
            "AND b.definition_id=%s AND b.revision_id=%s AND b.digest=%s)) "
            "ORDER BY p.digest LIMIT 51",
            (
                ctx.scope.tenant_id,
                ctx.scope.security_domain,
                identity,
                revision,
                ref["digest"],
                identity,
                revision,
                ref["digest"],
            ),
        ).fetchall()
        items = []
        parents = {}
        for row in candidates[:50]:
            try:
                view = self.saved.saved(replace(call, path={"digest": row["digest"]}))
            except AuthorityError:
                continue
            preparation = view["preparation"]
            task_ids = set()
            coordinating = False
            pairs = {
                (p["instance_id"], p["assignment_id"])
                for p in preparation["participants"]
                if p["definition"] == ref
            }
            root_pair = (
                preparation["root_instance_id"],
                preparation["root_assignment_id"],
            )
            # The root may coordinate without being a task participant. Its exact
            # owner reference, not the candidate index, determines membership.
            pairs.add(root_pair)
            for iid, aid in sorted(pairs):
                try:
                    if (iid, aid) not in parents:
                        parents[(iid, aid)] = self.parents(call, iid, aid)
                    parent = parents[(iid, aid)]
                except AuthorityError:
                    continue
                actual = {
                    "resource_id": parent["employeeDefinitionId"],
                    "revision_id": parent["employeeDefinitionRevisionId"],
                    "digest": parent["digest"],
                }
                if actual != ref:
                    if any(
                        p["definition"] == ref
                        and (p["instance_id"], p["assignment_id"]) == (iid, aid)
                        for p in preparation["participants"]
                    ):
                        raise WorkbenchOwnerError(
                            "EMPLOYEE_TRACE_DEFINITION_MISMATCH", 409
                        )
                    continue
                if (iid, aid) == root_pair:
                    coordinating = True
                    task_ids.update(
                        t["task_id"] for t in preparation["semantics"]["tasks"]
                    )
                else:
                    task_ids.update(
                        p["task_id"]
                        for p in preparation["participants"]
                        if p["definition"] == ref
                        and (p["instance_id"], p["assignment_id"]) == (iid, aid)
                    )
            if not task_ids:
                continue
            items.append(
                {
                    "executionDigest": view["digest"],
                    **read_execution_origin(
                        call,
                        view["digest"],
                        preparation["semantics"]["target"]["problem"]["resource_id"],
                    ),
                    "participation": "COORDINATION"
                    if coordinating
                    else "TASK_EXECUTION",
                    "title": preparation["semantics"]["title"],
                    "planVersion": preparation["plan_version"],
                    "state": (view.get("progress") or {}).get("state")
                    or (
                        "NOT_STARTED"
                        if view.get("executionStarted") is False
                        else "UNKNOWN"
                    ),
                    "tasks": [
                        {"taskId": task["task_id"], "title": task["title"]}
                        for task in preparation["semantics"]["tasks"]
                        if task["task_id"] in task_ids
                    ],
                }
            )
        return {
            "schemaVersion": "employee-work-records.v1",
            "subject": ctx.principal_id,
            "scope": {
                "tenantId": ctx.scope.tenant_id,
                "securityDomain": ctx.scope.security_domain,
            },
            "employeeDefinition": {
                key: definition[key]
                for key in [
                    "employeeDefinitionId",
                    "employeeDefinitionRevisionId",
                    "employeeDefinitionDigest",
                ]
            },
            "items": items,
            "scanLimited": len(candidates) > 50,
            "visibility": "AUTHORIZED_ONLY",
            "executionStarted": False,
        }

    def review(self, call):
        view = self.saved.saved(call)
        p = view["preparation"]
        tasks = []
        for actor in p["participants"]:
            ref = self.parents(call, actor["instance_id"], actor["assignment_id"])
            if actor["definition"] != {
                "resource_id": ref["employeeDefinitionId"],
                "revision_id": ref["employeeDefinitionRevisionId"],
                "digest": ref["digest"],
            }:
                raise WorkbenchOwnerError("EMPLOYEE_TRACE_DEFINITION_MISMATCH", 409)
            task = next(
                t for t in p["semantics"]["tasks"] if t["task_id"] == actor["task_id"]
            )
            state = next(
                (
                    t
                    for t in (view.get("progress") or {}).get("tasks", [])
                    if t["task_id"] == actor["task_id"]
                ),
                {},
            )
            tasks.append(
                {
                    "taskId": actor["task_id"],
                    "title": task["title"],
                    "state": state.get(
                        "state", "UNKNOWN" if view.get("progress") else "NOT_STARTED"
                    ),
                    "attemptId": state.get("attempt_id"),
                    "instanceId": actor["instance_id"],
                    "assignmentId": actor["assignment_id"],
                    "employee": actor["definition"],
                    "agentInstanceId": actor["agent_instance_id"],
                    "runtimeInstanceId": actor["runtime_instance_id"],
                    "runtimeGeneration": actor["runtime_generation"],
                    "profile": actor["profile"],
                    "providerHealth": "NOT_OBSERVED",
                }
            )
        result = {
            "schemaVersion": "execution-runtime-review.v1",
            "executionDigest": view["digest"],
            "subject": call.context.principal_id,
            "scope": {
                "tenantId": call.context.scope.tenant_id,
                "securityDomain": call.context.scope.security_domain,
            },
            "tasks": tasks,
            "executionStarted": False,
        }
        if call.operation == "READ_EXECUTION_TASK_OBSERVATION":
            task = next((t for t in tasks if t["taskId"] == call.path["task_id"]), None)
            if not task:
                raise WorkbenchOwnerError("RUNTIME_TASK_UNAVAILABLE", 404)
            result["observation"] = self.observe(call, view, task)
        if call.operation == "READ_EXECUTION_RUNTIME_DETAIL":
            task = next((t for t in tasks if t["taskId"] == call.path["task_id"]), None)
            if not task:
                raise WorkbenchOwnerError("RUNTIME_TASK_UNAVAILABLE", 404)
            result["detail"] = self.detail(call, task)
        return result

    def detail(self, call, task):
        path = {
            "instance_id": task["instanceId"],
            "assignment_id": task["assignmentId"],
        }
        instance = self.instances(
            replace(call, operation="READ_EMPLOYEE_INSTANCE", path=path)
        )
        assignment = self.instances(
            replace(call, operation="READ_EMPLOYEE_ASSIGNMENT", path=path)
        )
        result = {
            "taskId": task["taskId"],
            "instance": instance,
            "assignment": assignment,
            "placement": None,
            "placementStatus": "NOT_DISPATCHED",
            "observedAt": datetime.now(UTC).isoformat(),
            "freshUntil": datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + 30, UTC
            ).isoformat(),
            "providerHealth": "NOT_OBSERVED",
            "executionStarted": False,
        }
        if not task["attemptId"]:
            return result
        try:
            command = self.dispatch(call, task)
        except WorkbenchOwnerError:
            result["placementStatus"] = "BINDING_UNAVAILABLE"
            return result
        try:
            self.require(call, "PLACEMENT", "placement:" + command["placement_id"])
            placement = self.saved_placement(call, task, command)
        except (AuthorityError, WorkbenchOwnerError):
            result["placementStatus"] = "UNAVAILABLE"
            return result
        if placement["runtimeInstanceId"] != task["runtimeInstanceId"]:
            raise WorkbenchOwnerError("RUNTIME_PLACEMENT_BINDING_CHANGED", 409)
        result["placement"], result["placementStatus"] = placement, "VERIFIED"
        return result

    def saved_placement(self, call, task, command):
        # A completed dispatch has historical placement evidence, not an active
        # lease. Do not relax the existing active Placement owner read contract.
        row = call.connection.execute(
            "SELECT d.canonical_record,d.digest FROM execution_authority.placement_decisions d JOIN execution_authority.placement_requests r ON r.namespace=d.namespace AND r.security_domain=d.security_domain AND r.request_id=d.request_id WHERE d.namespace=%s AND d.security_domain=%s AND d.placement_id=%s AND r.attempt_id=%s AND r.agent_instance_id=%s",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                command["placement_id"],
                task["attemptId"],
                task["agentInstanceId"],
            ),
        ).fetchone()
        if row is None:
            raise WorkbenchOwnerError("SAVED_PLACEMENT_UNAVAILABLE", 404)
        try:
            decision = PlacementDecision.from_mapping(row["canonical_record"])
        except (KeyError, TypeError, ValueError) as error:
            raise WorkbenchOwnerError("SAVED_PLACEMENT_INVALID", 409) from error
        if (
            decision.digest != row["digest"]
            or decision.digest != command["placement_digest"]
            or str(decision.placement_id) != command["placement_id"]
            or str(decision.runtime_instance_id) != task["runtimeInstanceId"]
        ):
            raise WorkbenchOwnerError("SAVED_PLACEMENT_BINDING_CHANGED", 409)
        return {
            "placementId": str(decision.placement_id),
            "requestId": str(decision.request_id),
            "decision": decision.decision.value,
            "runtimeInstanceId": str(decision.runtime_instance_id),
            "policyVersion": decision.policy_version,
            "compatibilityFacts": decision.compatibility_facts,
            "limitationCodes": decision.limitation_codes,
            "decidedAt": decision.decided_at,
            "digest": decision.digest,
            "binding": {
                "instanceId": task["instanceId"],
                "assignmentId": task["assignmentId"],
                "attemptId": task["attemptId"],
                "agentInstanceId": task["agentInstanceId"],
            },
            "evidenceKind": "SAVED_DISPATCH_PLACEMENT",
        }

    def observe(self, call, view, task):
        if (
            not self.policy
            or not self.policy.allows(call.context, view["digest"])
            or self.observer is None
        ):
            raise WorkbenchOwnerError("RUNTIME_OBSERVATION_SCOPE_REQUIRED", 403)
        if not task["attemptId"]:
            raise WorkbenchOwnerError("RUNTIME_TASK_NOT_DISPATCHED", 409)
        command = self.dispatch(call, task)
        try:
            return correlated_task(command, self.observer.read(command))
        except ApiException as e:
            raise WorkbenchOwnerError(
                "RUNTIME_TASK_UNAVAILABLE"
                if e.status == 404
                else "RUNTIME_OBSERVATION_UNAVAILABLE",
                404 if e.status == 404 else 503,
            ) from e
        except (
            OSError,
            TimeoutError,
            KubernetesTransportError,
            config.ConfigException,
        ) as e:
            raise WorkbenchOwnerError("RUNTIME_OBSERVATION_UNAVAILABLE", 503) from e

    def dispatch(self, call, task):
        command = call.connection.execute(
            "SELECT namespace,command_id,attempt_id,assignment_id,agent_name,agent_instance_id,runtime_instance_id,runtime_generation,placement_id,placement_digest,kubernetes_task_name,kubernetes_task_uid FROM execution_authority.native_dispatch_commands WHERE namespace=%s AND security_domain=%s AND attempt_id=%s",
            (
                call.context.scope.tenant_id,
                call.context.scope.security_domain,
                task["attemptId"],
            ),
        ).fetchone()
        if (
            not command
            or any(
                str(command[a]) != str(task[b])
                for a, b in [
                    ("assignment_id", "assignmentId"),
                    ("agent_instance_id", "agentInstanceId"),
                    ("runtime_instance_id", "runtimeInstanceId"),
                    ("runtime_generation", "runtimeGeneration"),
                ]
            )
            or not command["kubernetes_task_name"]
            or not command["kubernetes_task_uid"]
        ):
            raise WorkbenchOwnerError("RUNTIME_DISPATCH_BINDING_UNAVAILABLE", 409)
        return command

    def __call__(self, call):
        if call.operation == "READ_EMPLOYEE_WORK_RECORDS":
            return self.employee_links(call)
        return (
            self.links(call)
            if call.operation == "READ_ASSIGNMENT_EXECUTIONS"
            else self.review(call)
        )


def operations(
    instances,
    coordinator=None,
    *,
    configuration=None,
    sales_v2_candidate=False,
    definitions=None,
):
    owner = EmployeeExecutionTrace(
        instances,
        coordinator,
        observer=ExactTaskObserver(configuration) if configuration else None,
        policy=configuration,
        sales_v2_candidate=sales_v2_candidate,
        definitions=definitions,
    )
    path = PREFIX + "/prepared-executions/{digest}"
    return (
        (
            WorkbenchOperation(
                "READ_EMPLOYEE_WORK_RECORDS",
                "GET",
                PREFIX
                + "/employees/{employee_definition_id}/revisions/{revision_id}/work-records",
                None,
                None,
                _employee_revision_read,
                owner,
            ),
        )
        if definitions is not None
        else ()
    ) + (
        WorkbenchOperation(
            "READ_ASSIGNMENT_EXECUTIONS",
            "GET",
            PREFIX + "/instances/{instance_id}/assignments/{assignment_id}/executions",
            None,
            None,
            _assignment_read,
            owner,
        ),
        WorkbenchOperation(
            "READ_EXECUTION_RUNTIME_REVIEW",
            "GET",
            path + "/runtime-review",
            None,
            None,
            grant("READ"),
            owner,
        ),
        WorkbenchOperation(
            "READ_EXECUTION_RUNTIME_DETAIL",
            "GET",
            path + "/runtime-details/{task_id}",
            None,
            None,
            grant("READ"),
            owner,
        ),
        WorkbenchOperation(
            "READ_EXECUTION_TASK_OBSERVATION",
            "GET",
            path + "/runtime-observations/{task_id}",
            None,
            None,
            grant("READ"),
            owner,
        ),
    )
