"""Authorization-first internal execution preview application service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_core.execution_evidence import (
    AuthorizedEvidenceScope,
    EvidenceRepositoryError,
    ExecutionEvidenceRepository,
)
from agent_core.representation.v0_2 import PlatformExecutionIdentity

from agent_console.execution_snapshot import (
    SnapshotAssemblyError,
    assemble_execution_snapshot,
)
from agent_console.graph_projection import (
    Cardinality,
    GraphLayer,
    NodeSpec,
    NodeType,
    Phase,
    ProjectionVisibility,
    RelationSpec,
    RelationType,
    SnapshotContext,
    build_graph,
)
from agent_console.preview_schemas import PreviewResponse
from agent_console.repository import WorkflowRepository


class PreviewServiceError(RuntimeError):
    state = "ERROR"
    reason_code = "PREVIEW_INTERNAL_ERROR"
    status_code = 500


class PreviewDenied(PreviewServiceError):
    state = "DENIED"
    reason_code = "PREVIEW_ACCESS_DENIED"
    status_code = 403


class PreviewNotFound(PreviewServiceError):
    state = "NOT_FOUND"
    reason_code = "PREVIEW_NOT_FOUND"
    status_code = 404


class PreviewAuthorityMissing(PreviewServiceError):
    state = "AUTHORITY_MISSING"
    reason_code = "PREVIEW_AUTHORITY_MISSING"
    status_code = 503


@dataclass(frozen=True, slots=True)
class TrustedPreviewPrincipal:
    """Server-resolved authorization context; never populated from request data."""

    principal_id: str
    namespace: str
    security_domain: str
    authorized: bool

    def permits(self, requested_namespace: str) -> bool:
        return (
            self.authorized
            and bool(self.principal_id.strip())
            and bool(self.security_domain.strip())
            and requested_namespace == self.namespace
        )


class PreviewService:
    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        evidence_repository: ExecutionEvidenceRepository | None,
    ) -> None:
        self._workflows = workflow_repository
        self._evidence = evidence_repository

    def get_preview(
        self,
        *,
        principal: TrustedPreviewPrincipal,
        namespace: str,
        workflow_name: str,
        task_name: str,
    ) -> PreviewResponse:
        if not principal.permits(namespace):
            raise PreviewDenied
        if self._evidence is None:
            raise PreviewAuthorityMissing
        try:
            workflow = self._workflows.get_workflow(namespace, workflow_name)
            tasks = self._workflows.list_workflow_tasks(namespace, workflow_name)
        except Exception as exc:
            status = getattr(exc, "status", None)
            if status == 404:
                raise PreviewNotFound from exc
            raise PreviewAuthorityMissing from exc
        selected = next(
            (
                item
                for item in tasks
                if isinstance(item.get("metadata"), Mapping)
                and item["metadata"].get("name") == task_name
            ),
            None,
        )
        if selected is None:
            raise PreviewNotFound
        scope = AuthorizedEvidenceScope(namespace, principal.security_domain)
        try:
            high_water_mark = self._evidence.high_water_mark(scope)
            evidence = self._evidence.read_task(
                scope, task_name, through_high_water_mark=high_water_mark
            )
        except EvidenceRepositoryError as exc:
            raise PreviewAuthorityMissing from exc
        if not evidence:
            raise PreviewAuthorityMissing
        graph = _build_authoritative_graph(
            namespace=namespace,
            security_domain=principal.security_domain,
            workflow=workflow,
            tasks=tasks,
            evidence=evidence,
            high_water_mark=high_water_mark,
        )
        try:
            snapshot = assemble_execution_snapshot(
                scope=scope,
                workflow=workflow,
                tasks=tasks,
                evidence=evidence,
                evidence_high_water_mark=high_water_mark,
                graph=graph,
            )
        except SnapshotAssemblyError as exc:
            raise PreviewAuthorityMissing from exc
        payload = snapshot.to_dict()
        return PreviewResponse(
            state=snapshot.state.value,
            sharedSnapshotId=snapshot.shared_snapshot_id,
            graphSnapshotId=snapshot.graph_snapshot_id,
            platformExecutionIdentity=snapshot.platform_execution_identity,
            snapshot=payload,
        )


def _phase(task: Mapping[str, Any]) -> Phase:
    status = task.get("status")
    value = status.get("phase") if isinstance(status, Mapping) else None
    return {
        "Pending": Phase.PENDING,
        "Running": Phase.RUNNING,
        "Succeeded": Phase.SUCCEEDED,
        "Failed": Phase.FAILED,
        "Skipped": Phase.SKIPPED,
    }.get(value, Phase.UNKNOWN)


def _build_authoritative_graph(
    *,
    namespace: str,
    security_domain: str,
    workflow: Mapping[str, Any],
    tasks: list[dict[str, Any]],
    evidence,
    high_water_mark: int,
):
    workflow_meta = workflow["metadata"]
    execution_identity = PlatformExecutionIdentity(
        evidence[0].platform_execution_identity
    )
    nodes = [
        NodeSpec(
            NodeType.WORKFLOW,
            workflow_meta["uid"],
            "graph.workflow",
            phase=Phase.UNKNOWN,
            execution_identity=execution_identity,
            evidence_ids=tuple(item.evidence_record_id for item in evidence),
        )
    ]
    task_names: dict[str, str] = {}
    for task in tasks:
        metadata = task["metadata"]
        task_names[metadata["name"]] = metadata["uid"]
        nodes.append(
            NodeSpec(
                NodeType.TASK,
                metadata["uid"],
                "graph.task",
                phase=_phase(task),
                execution_identity=execution_identity,
                evidence_ids=tuple(item.evidence_record_id for item in evidence),
            )
        )
    relations = []
    for task in tasks:
        metadata = task["metadata"]
        spec = task.get("spec", {})
        dependencies = spec.get("dependsOn", ()) if isinstance(spec, Mapping) else ()
        for dependency in dependencies if isinstance(dependencies, list) else ():
            if dependency in task_names:
                relations.append(
                    RelationSpec(
                        source_entity_id=metadata["uid"],
                        target_entity_id=task_names[dependency],
                        relation_types=(RelationType.DEPENDS_ON,),
                        layer=GraphLayer.EXECUTION_DEPENDENCY,
                        declared_cardinality=Cardinality.MANY_TO_ONE,
                        tenant_or_security_domain=security_domain,
                        projection_visibility=ProjectionVisibility.BOTH,
                    )
                )
    return build_graph(
        SnapshotContext(
            authoritative_input_id=f"{workflow_meta['uid']}:{workflow_meta['resourceVersion']}",
            approved_plan_revision=str(workflow_meta["resourceVersion"]),
            execution_snapshot_id=f"evidence-high-water:{high_water_mark}",
            security_domain=security_domain,
        ),
        nodes,
        relations,
    )
