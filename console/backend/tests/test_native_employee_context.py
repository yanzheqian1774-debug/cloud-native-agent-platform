# ruff: noqa: F401,F811 -- Explicit disposable PostgreSQL fixture composition.
"""Exact owner context and provider payload; live acceptance remains separate."""

import json
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.native_document_skill import (
    NativeDocumentSkillExecutor,
    NativeEmployeeDocumentSkillExecutor,
    document_executor_revision,
)
from agent_console.native_employee_context import read_bound_employee_context
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation
from test_workbench_employee_relations import relations


def preparation(r, ref=None):
    executor = NativeEmployeeDocumentSkillExecutor.revision
    return SimpleNamespace(
        namespace=r.a.e.scope.namespace,
        security_domain=r.a.e.scope.security_domain,
        participants=[
            SimpleNamespace(
                task_id="inspect",
                definition=ref or r.ref,
                executor_id=executor.executor_id,
                executor_revision=executor.executor_revision,
                executor_digest=executor.configuration_digest,
            )
        ],
    )


def test_exact_context_reads_original_bound_revision_not_newer_draft(relations):
    r = relations
    reads = []
    with r.a.repository.pool.connection() as c:
        value = read_bound_employee_context(
            c, preparation(r), "inspect", authorize=reads.append
        )
        old = r.definitions.read_revision_for_workbench(
            c, r.a.e.scope, r.ref.resource_id, r.ref.revision_id, authorized=True
        )
    assert reads == [r.ref]
    assert value["reference"] == r.ref.model_dump(mode="json")
    assert value["reference"]["revision_id"] != r.successor.revision_id
    assert value["role"] == old["revision"]["role"]
    assert value["responsibilities"] == old["revision"]["responsibilities"]
    assert value["authority"] == "TASK_CONTEXT_ONLY_NOT_PERMISSION"


@pytest.mark.parametrize(
    "variant",
    [
        "missing-task",
        "duplicate-task",
        "wrong-executor",
        "wrong-digest",
        "denied",
        "draft",
        "withdrawn",
    ],
)
def test_employee_context_fails_closed(relations, variant):
    r = relations
    p = preparation(r)
    error = ValueError
    if variant == "missing-task":
        p.participants = []
    if variant == "duplicate-task":
        p.participants *= 2
    if variant == "wrong-executor":
        p.participants[0].executor_revision = "1"
    if variant == "wrong-digest":
        p.participants[0].definition = r.ref.model_copy(update={"digest": "0" * 64})
    if variant == "draft":
        p.participants[0].definition = r.ref.model_copy(
            update={
                "revision_id": r.successor.revision_id,
                "digest": r.successor.digest,
            }
        )

    if variant == "withdrawn":
        with r.a.repository.pool.connection() as c, c.transaction():
            current = r.definitions.read_revision_for_workbench(
                c, r.a.e.scope, r.ref.resource_id, r.ref.revision_id, authorized=True
            )
            r.definitions.decide_for_workbench(
                c,
                r.a.e.scope,
                r.ref.resource_id,
                r.ref.revision_id,
                r.ref.digest,
                "UNPUBLISH",
                expected_version=current["aggregateVersion"],
                decision_id="isolated-context-withdrawal",
                command_id="context:withdraw",
                authorized=True,
            )

    def authorize(ref):
        if variant == "denied":
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    if variant == "denied":
        error = AuthorityError
    with r.a.repository.pool.connection() as c, pytest.raises(error):
        read_bound_employee_context(c, p, "inspect", authorize=authorize)


def test_successor_has_distinct_registered_identity_and_rejects_mixed_revisions():
    from agent_console.resource_automation_validation import executor_registry

    old, new = (
        NativeDocumentSkillExecutor.revision,
        NativeEmployeeDocumentSkillExecutor.revision,
    )
    assert old.executor_revision == "1" and new.executor_revision == "2"
    assert old.configuration_digest != new.configuration_digest

    def operation(v):
        return {
            "executorId": v.executor_id,
            "executorRevision": v.executor_revision,
            "executorConfigurationDigest": v.configuration_digest,
        }

    assert document_executor_revision([operation(old)]) == old
    assert document_executor_revision([operation(new)]) == new
    with pytest.raises(ValueError, match="REVISION_MISMATCH"):
        document_executor_revision([operation(old), operation(new)])
    assert executor_registry().resolve(new).revision == new


@pytest.mark.parametrize(
    "with_employee,with_scope", [(False, False), (True, False), (True, True)]
)
def test_provider_receives_exact_duties_without_expanding_tool_policy(
    monkeypatch, with_employee, with_scope
):
    from agent_console import native_loop_provider as module

    context = {"domain": "DOCUMENT_REVIEW"}
    employee = {
        "schemaVersion": "native-employee-context.v1",
        "reference": {
            "resource_id": "employee:one",
            "revision_id": "revision:fixed",
            "digest": "a" * 64,
        },
        "role": "交接检查",
        "responsibilities": ["核对回退步骤和责任人"],
        "authority": "TASK_CONTEXT_ONLY_NOT_PERMISSION",
    }
    if with_employee:
        context["employeeContext"] = employee
    if with_scope:
        context["confirmedScopeEvidence"] = {
            "scope": "生产环境",
            "conversationId": "original",
            "affirmativeMessageIds": ["m1"],
        }
    captured = []

    def exchange(**kwargs):
        captured.append(json.loads(kwargs["request"].payload))
        return 400, b"{}", None, 0

    monkeypatch.setattr(
        module, "planning_transport", lambda _: SimpleNamespace(exchange=exchange)
    )
    monkeypatch.setattr(
        module,
        "planning_credentials",
        lambda *_: SimpleNamespace(resolve=lambda *_: None),
    )
    monkeypatch.setattr(module, "budget_quote", lambda _: None)
    monkeypatch.setattr(module, "measurement", lambda *args, **kwargs: {})
    config = SimpleNamespace(
        native_model_id="isolated-model",
        maximum_output_tokens=256,
        planning_model_policy=None,
        maximum_input_tokens=100000,
        maximum_response_bytes=100000,
    )
    result = module.NativeDecisionJob(
        config, None, "isolated-request", {"context": context, "tools": []}
    ).run(lambda _: None)
    assert result["failure"] == "NATIVE_DECISION_PROVIDER_REJECTED"
    body = captured[0]
    assert ("employeeContext" in json.loads(body["input"])["context"]) is with_employee
    assert ("do not ask the user to repeat" in body["instructions"]) is with_scope
    if with_employee:
        assert json.loads(body["input"])["context"]["employeeContext"] == employee
        assert "cannot add tools" in body["instructions"]
    else:
        assert "employeeContext" not in body["instructions"]


def test_successor_bundle_is_explicit_and_retains_typed_tools():
    from agent_console.native_document_resource_bundle import resource_content
    from test_native_document_tools import SOURCE

    old = resource_content(SOURCE)
    new = resource_content(SOURCE, bound_employee=True)
    assert (
        document_executor_revision(old["skill"]["operations"])
        == NativeDocumentSkillExecutor.revision
    )
    assert (
        document_executor_revision(new["skill"]["operations"])
        == NativeEmployeeDocumentSkillExecutor.revision
    )
    for before, after in zip(
        old["skill"]["operations"], new["skill"]["operations"], strict=True
    ):
        assert before["name"] == after["name"]
        assert before["inputSchema"] == after["inputSchema"]
        assert before["outputSchema"] == after["outputSchema"]
        assert before["ioLimits"] == after["ioLimits"]
