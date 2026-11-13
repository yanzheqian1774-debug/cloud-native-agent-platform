"""Actual ordinary browser BFF over the disposable durable document owner chain."""

import json
import os
from contextlib import contextmanager
from types import SimpleNamespace as NS
from unittest.mock import patch

from agent_console.native_document_skill import NativeDurableDocumentSkillExecutor
from agent_console.workbench_bff import (
    PREFIX,
    WorkbenchBffPolicy,
    create_workbench_bff,
)
from agent_console.workbench_business_problem import business_problem_operations
from agent_console.workbench_prepared_execution import prepared_execution_operations
from agent_runtime.native_loop import digest
from fastapi.testclient import TestClient


@contextmanager
def browser(
    e,
    work,
    native,
    preparation,
    runtime,
    directory,
    *,
    executor_type=NativeDurableDocumentSkillExecutor,
    typed_questions=False,
    typed_settlement_reader=None,
):
    with native.pool.connection() as c:
        _, authority = work.authority_factory(
            c, NS(principal_id=e.context.principal_id)
        )
        adapter = authority.adapter
    runtime_file = directory / "controlled-native-runtime.json"
    runtime_file.write_text(json.dumps(runtime.config))
    executor = executor_type.revision
    wait_file = directory / "controlled-durable-wait.json"
    wait_file.write_text(
        json.dumps(
            dict(
                schemaVersion="native-durable-wait.v2"
                if typed_questions
                else "native-durable-wait.v1",
                **({"typedQuestions": True} if typed_questions else {}),
                enabled=True,
                executorId=executor.executor_id,
                executorRevision=executor.executor_revision,
                executorConfigurationDigest=executor.configuration_digest,
                nativeRuntimePolicyDigest=digest(runtime.config),
                maximumHumanWaitSeconds=1200,
            )
        )
    )
    environment = {
        "NATIVE_LOOP_RUNTIME_FILE": str(runtime_file),
        "NATIVE_DURABLE_WAIT_CONFIGURATION": str(wait_file),
        "OWNED_BUSINESS_ADMISSION_POLICY": str(e.business_owner.path),
    }
    operations = tuple(
        o
        for o in prepared_execution_operations(
            typed_settlement_reader=typed_settlement_reader
        )
        if o.name in {"READ_NATIVE_PROGRESS", "ANSWER_NATIVE_QUESTION"}
    )
    operations += tuple(
        o
        for o in business_problem_operations(e.business_app)
        if o.name == "READ_PROBLEM"
    )
    app = create_workbench_bff(
        e.routing_sessions,
        adapter,
        WorkbenchBffPolicy("testserver", "https://testserver"),
        operations=operations,
        conversation_database_url=e.repo.pool.conninfo,
    )
    with (
        TestClient(app, base_url="https://testserver") as client,
        patch.dict(os.environ, environment),
    ):
        client.cookies.update(e.adoption_client.cookies)
        yield client, PREFIX + "/prepared-executions/" + preparation.digest


def link_created_problem(client, e, conversation_id):
    """Perform the product's formal link step omitted by the creation fixture."""
    path = PREFIX + "/conversations/" + conversation_id
    current = client.get(path)
    assert current.status_code == 200, current.text
    revision = e.created["revision"]
    if not hasattr(e, "durable_link_command"):
        e.durable_link_command = {
            "idempotencyKey": "durable-test-original-problem-link",
            "expectedVersion": current.json()["result"]["conversation"]["version"],
            "target": {
                "problemId": revision["business_problem_id"],
                "revisionId": revision["revision_id"],
                "problemDigest": revision["digest"],
            },
        }
    response = client.post(
        path + "/links", headers=e.adoption_headers, json=e.durable_link_command
    )
    assert response.status_code == 200, response.text
