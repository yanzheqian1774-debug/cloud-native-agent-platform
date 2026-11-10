"""Managed Skill adapter used only by the existing Native effect owner."""

import json

from .execution_preparation import ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore
from .ontology_execution import parse_preparation
from .prepared_execution_lineage import prepared_attempt
from .prepared_execution_resources import published
from .prepared_skill_invocation import build_request
from .skill_invocation_application import ScopedSkillInvocationAuthorization


def input_snapshot(connection, command, *, sales_v2_candidate=False):
    row = prepared_attempt(connection, command.scope, command.attempt_id)
    if row is None:
        raise ExecutionPreparationError("PREPARED_ATTEMPT_REQUIRED")
    p = parse_preparation(row["preparation"])
    _, progress = PreparedExecutionStore(connection).read(
        p.namespace, p.security_domain, p.run_id, lock=True
    )
    task = next(t for t in p.semantics.tasks if t.task_id == row["task_id"])
    current = next(t for t in progress.tasks if t.task_id == task.task_id)
    if current.state != "RUNNING" or current.attempt_id != str(command.attempt_id):
        raise ExecutionPreparationError("PREPARED_RUNNING_ATTEMPT_REQUIRED")
    if progress.cancellation_request_id:
        raise ExecutionPreparationError("PREPARED_CANCEL_REQUESTED_BEFORE_SKILL")
    dependencies = {}
    for dependency in task.depends_on:
        prior = next(t for t in progress.tasks if t.task_id == dependency)
        if prior.state != "SUCCEEDED" or len(prior.output_artifact_ids) != 1:
            raise ExecutionPreparationError("PREPARED_DEPENDENCY_OUTPUT_REQUIRED")
        artifact = connection.execute(
            "SELECT content FROM execution_authority.run_artifacts WHERE namespace=%s "
            "AND security_domain=%s AND workflow_run_id=%s AND artifact_id=%s "
            "AND task_id=%s AND attempt_id=%s",
            (
                p.namespace,
                p.security_domain,
                p.run_id,
                prior.output_artifact_ids[0],
                dependency,
                prior.attempt_id,
            ),
        ).fetchone()
        if artifact is None:
            raise ExecutionPreparationError("PREPARED_DEPENDENCY_OUTPUT_REQUIRED")
        dependencies[dependency] = json.loads(artifact["content"])
    participant = next(t for t in p.participants if t.task_id == task.task_id)
    from .prepared_delivery_contract import delivery_revision

    is_delivery = (
        delivery_revision(
            participant.executor_id,
            participant.executor_revision,
            participant.executor_digest,
        )
        is not None
    )
    from .sales_diagnostic_skill import SalesDiagnosticSkillExecutor

    sales = SalesDiagnosticSkillExecutor.revision
    is_sales = (
        participant.executor_id,
        participant.executor_revision,
        participant.executor_digest,
    ) == (sales.executor_id, sales.executor_revision, sales.configuration_digest)
    from .sales_gross_profit_integration import is_v2, require_source

    sales_v2 = is_v2(
        participant.executor_id,
        participant.executor_revision,
        participant.executor_digest,
    )
    if sales_v2 and not sales_v2_candidate:
        raise ExecutionPreparationError("SALES_V2_CANDIDATE_NOT_ENABLED")
    from .tabular_diagnostic_skill import TabularDiagnosticSkillExecutor

    tabular = TabularDiagnosticSkillExecutor.revision
    from .native_loop_skill import (
        NativeLoopSkillExecutor,
        NativeValidatedLoopSkillExecutor,
    )

    is_tabular = any(
        (
            participant.executor_id,
            participant.executor_revision,
            participant.executor_digest,
        )
        == (v.executor_id, v.executor_revision, v.configuration_digest)
        for v in (
            tabular,
            NativeLoopSkillExecutor.revision,
            NativeValidatedLoopSkillExecutor.revision,
        )
    )
    from .native_document_skill import (
        NativeDocumentSkillExecutor,
        NativeEmployeeDocumentSkillExecutor,
    )

    is_document = (
        participant.executor_id,
        participant.executor_revision,
        participant.executor_digest,
    ) in {
        (doc.executor_id, doc.executor_revision, doc.configuration_digest)
        for doc in (
            NativeDocumentSkillExecutor.revision,
            NativeEmployeeDocumentSkillExecutor.revision,
        )
    }
    result = {
        "schemaVersion": "document-review-input.v1"
        if is_document
        else "tabular-diagnostic-input.v1"
        if is_tabular
        else "sales-diagnostic-input.v2"
        if sales_v2
        else "sales-diagnostic-input.v1"
        if is_sales
        else "synthetic-delivery-input.v1"
        if is_delivery
        else "synthetic-cost-input.v1",
        "synthetic": True,
        "sourceSnapshot": p.source_snapshot.model_dump(mode="json"),
        "dependencies": dependencies,
    }
    binding = getattr(p, "business_semantics", None)
    if binding is not None:
        from .ontology_execution import published_content

        ontology = published_content(connection, command.scope, binding)
        result.update(
            schemaVersion="ontology-sales-input.v1",
            ontologyContent=ontology.model_dump(mode="json"),
            businessSemantics=binding.model_dump(mode="json"),
        )
    if task.operation == "READ_DATA" or sales_v2:
        knowledge = published(connection, command.scope, "KNOWLEDGE", p.source_snapshot)
        documents = knowledge.get("documents", [])
        if len(documents) != 1 or len(documents[0].get("chunks", [])) != 1:
            raise ExecutionPreparationError("PREPARED_SINGLE_SOURCE_DOCUMENT_REQUIRED")
        content = documents[0]["chunks"][0]["content"]
        import hashlib

        if (
            hashlib.sha256(content.encode()).hexdigest()
            != documents[0]["contentDigest"]
        ):
            raise ExecutionPreparationError("PREPARED_SOURCE_DOCUMENT_CORRUPT")
        result["source"] = json.loads(content)
        if sales_v2:
            require_source(result["source"])
    return row, result


class PreparedNativeSkillCaller:
    """Authorization port is composition-owned; no caller-supplied Skill request."""

    def __init__(self, pool, skill_composition, authorize, *, sales_v2_candidate=False):
        self.pool = pool
        self.skill = skill_composition
        self.authorize = authorize
        self.sales_v2_candidate = sales_v2_candidate

    def invoke(self, command):
        with self.pool.connection() as connection, connection.transaction():
            # Recheck current admission and independent Skill authority before lookup.
            decision_id = self.authorize(connection, command)
            row, inputs = input_snapshot(
                connection, command, sales_v2_candidate=self.sales_v2_candidate
            )
            request = build_request(
                connection, command.scope, command.attempt_id, decision_id
            )
        authorization = ScopedSkillInvocationAuthorization(
            command.scope,
            command.principal_id,
            frozenset({"INVOKE_SKILL"}),
            decision_id,
        )
        from .native_loop_runtime import COMMAND

        token = COMMAND.set(command)
        try:
            snapshot = self.skill.service(authorization).invoke(request, inputs)
        finally:
            COMMAND.reset(token)
        if snapshot.state != "SUCCEEDED":
            return snapshot.state.value, None
        with self.pool.connection() as connection:
            artifact = connection.execute(
                "SELECT artifact_id,digest FROM execution_authority.run_artifacts "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                "AND task_id=%s AND attempt_id=%s",
                (
                    command.scope.namespace,
                    command.scope.security_domain,
                    row["workflow_run_id"],
                    row["task_id"],
                    str(command.attempt_id),
                ),
            ).fetchall()
        if len(artifact) != 1 or artifact[0]["digest"] != snapshot.output_digest:
            raise ExecutionPreparationError("PREPARED_SKILL_OUTPUT_READBACK_MISMATCH")
        return "SUCCEEDED", json.dumps(
            {
                "schemaVersion": "prepared-output-reference.v1",
                "artifactId": artifact[0]["artifact_id"],
                "digest": artifact[0]["digest"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
