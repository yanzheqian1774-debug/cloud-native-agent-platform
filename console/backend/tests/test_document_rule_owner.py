"""Finite rules and isolated PostgreSQL evidence, not live acceptance."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityScope
from agent_console.document_rule_evaluation import evaluate_document_rules
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import NativeDocumentSkillExecutor
from agent_console.ontology_domain import (
    DocumentRulesContent,
    OntologyCommand,
    OntologyError,
)
from agent_console.ontology_postgres import PostgresOntologyRepository, migrate
from agent_console.ontology_service import OntologyService
from agent_console.resource_use_domain import canonical_digest
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from psycopg.rows import dict_row
from pydantic import ValidationError
from test_ontology_lifecycle import ExactOntologyTestAuthority
from test_plan_suggestion_v2 import repository  # noqa: F401
from test_prepared_resource_owners import services  # noqa: F401

SOURCE = {
    "schemaVersion": "document-review-source.v1",
    "synthetic": True,
    "documents": [
        {
            "id": "interview",
            "title": "Synthetic interview",
            "role": "SUBMISSION",
            "text": (
                "# Interview\n## Handover\nOwner: Alice\nScope: TBD\n"
                "Reviewer: Bob\nReviewer: Eve\n## Evidence\nTranscript saved.\n"
            ),
        },
        {
            "id": "policy",
            "title": "Policy",
            "role": "POLICY",
            "scope": "interview",
            "text": "# Policy\n## Handover\nIdentify owner, scope and reviewer.\n",
        },
    ],
}


def rules(source=SOURCE, reference=None, skill=None):
    ref = reference or {
        "resource_id": "source",
        "revision_id": "r1",
        "digest": "a" * 64,
    }
    executor = NativeDocumentSkillExecutor.revision
    return DocumentRulesContent.model_validate(
        {
            "schema_version": "business-document-rules.v1",
            "name": "Interview handover rules",
            "business_owner": "test-business",
            "data_owner": "test-data",
            "synthetic": True,
            "scope": "interview",
            "mappings": [
                {
                    "code": "interview",
                    "source": ref,
                    "source_digest": canonical_digest(source),
                    "source_schema": "document-review-source.v1",
                }
            ],
            "rules": [
                {
                    "code": "owner",
                    "name": "One owner",
                    "kind": "SINGLE_VALUE_FIELD",
                    "section": "Handover",
                    "field": "Owner",
                },
                {
                    "code": "scope",
                    "name": "Scope known",
                    "kind": "SINGLE_VALUE_FIELD",
                    "section": "Handover",
                    "field": "Scope",
                },
                {
                    "code": "reviewer",
                    "name": "One reviewer",
                    "kind": "SINGLE_VALUE_FIELD",
                    "section": "Handover",
                    "field": "Reviewer",
                },
                {
                    "code": "rollback",
                    "name": "Rollback exists",
                    "kind": "REQUIRED_SECTION",
                    "section": "Rollback",
                },
            ],
            "actions": [
                {
                    "skill": skill or ref,
                    "executor_id": executor.executor_id,
                    "executor_revision": executor.executor_revision,
                    "executor_digest": executor.configuration_digest,
                    "operation": "ANALYZE_DATA",
                    "side_effect": "READ_ONLY",
                }
            ],
        }
    )


def test_explicit_outcomes_line_evidence_and_rule_change_without_source_change():
    original = rules()
    result = evaluate_document_rules(original, SOURCE)
    assert [x["status"] for x in result["findings"]] == [
        "SATISFIED",
        "UNKNOWN",
        "CONFLICT",
        "MISSING",
    ]
    assert result["findings"][0]["evidence"][-1] == {
        "documentId": "interview",
        "line": 3,
        "text": "Owner: Alice",
    }
    assert result["findings"][2]["observedValues"] == ["Bob", "Eve"]
    assert result["findings"][3]["absenceCheckedAgainst"] == canonical_digest(
        SOURCE["documents"][0]
    )
    revision = original.model_dump(mode="json")
    revision["rules"][-1]["section"] = "Evidence"
    newer = DocumentRulesContent.model_validate(revision)
    changed = evaluate_document_rules(newer, SOURCE)
    assert changed["findings"][-1]["status"] == "SATISFIED"
    assert (
        changed["sourceDigest"] == result["sourceDigest"]
        and changed["rulesDigest"] != result["rulesDigest"]
    )
    assert evaluate_document_rules(original, SOURCE) == result


def test_rejects_unbound_source_unknown_contract_and_duplicate_rules():
    content = rules()
    source = deepcopy(SOURCE)
    source["documents"][0]["text"] += "Altered"
    with pytest.raises(OntologyError, match="SOURCE_DIGEST"):
        evaluate_document_rules(content, source)
    value = content.model_dump(mode="json")
    value["rules"].append(value["rules"][0])
    with pytest.raises(ValueError, match="DUPLICATE_CODE"):
        DocumentRulesContent.model_validate(value)
    value = content.model_dump(mode="json")
    value["schema_version"] = "unsupported"
    with pytest.raises(ValidationError):
        OntologyCommand.model_validate(
            {
                "request_key": "x",
                "expected_version": 0,
                "revision_id": "r1",
                "reason": "test",
                "content": value,
            }
        )


def test_real_postgres_owner_records_exact_rule_test_and_preserves_old_revision(
    repository,  # noqa: F811
    services,  # noqa: F811
):
    # Publish only the actual source and document skill in the isolated database.
    # Fixture review facts do not represent live human review or execution.
    p = SimpleNamespace(namespace="document-fixture", security_domain="isolated")
    bundle = resource_content(SOURCE)
    refs = {}
    for kind in ("skill", "knowledge"):
        service = services[kind]
        scope = service.scope(p.namespace, p.security_domain)
        args = (
            (scope, "skill", "agent:fixture")
            if kind == "skill"
            else (scope, "agent:fixture")
        )
        created = service.create(*args, "Synthetic document fixture", bundle[kind])
        if kind == "knowledge":
            created = created["knowledge"]
        identity = created["resourceId" if kind == "skill" else "knowledgeId"]
        revision = created["revisions"][0]
        with repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            PreparedResourceOwner(services)(
                SimpleNamespace(
                    operation="REVIEW_PREPARED_RESOURCE",
                    context=SimpleNamespace(
                        principal_id="human:fixture-reviewer",
                        scope=AuthorityScope(p.namespace, p.security_domain),
                    ),
                    authority=SimpleNamespace(
                        require=lambda *args: SimpleNamespace(
                            decision_id="fixture-only"
                        )
                    ),
                    connection=c,
                    path={
                        "kind": kind,
                        "identity": identity,
                        "revision": revision["revisionId"],
                    },
                    payload={
                        "expectedVersion": 1,
                        "digest": revision["digest"],
                        "reason": "Isolated fixture only",
                        "idempotencyKey": "document-fixture-" + kind,
                    },
                )
            )
        refs[kind] = {
            "resource_id": identity,
            "revision_id": revision["revisionId"],
            "digest": revision["digest"].removeprefix("sha256:"),
        }
    content = rules(reference=refs["knowledge"], skill=refs["skill"])
    with repository.pool.connection() as c, c.transaction():
        migrate(c)

    def command(
        action, version, revision, *, value=None, digest=None, actor="human:author"
    ):
        with repository.pool.connection() as c, c.transaction():
            owner = OntologyService(
                SimpleNamespace(
                    connection=c,
                    context=SimpleNamespace(
                        principal_id=actor,
                        scope=SimpleNamespace(
                            tenant_id=p.namespace, security_domain=p.security_domain
                        ),
                    ),
                    authority=ExactOntologyTestAuthority(),
                )
            )
            return owner.handle(
                action,
                "interview-rules",
                {
                    "request_key": f"{action}-{revision}-{version}",
                    "expected_version": version,
                    "revision_id": revision,
                    "digest": digest,
                    "content": value,
                    "reason": "isolated synthetic rule acceptance",
                },
            )

    created = command("CREATE", 0, "r1", value=content.model_dump(mode="json"))
    validated = command("VALIDATE", 1, "r1", digest=created["digest"])
    tested = command("TEST", 2, "r1", digest=created["digest"])
    assert [r["status"] for r in tested["checks"][0]["findings"]] == [
        "SATISFIED",
        "UNKNOWN",
        "CONFLICT",
        "MISSING",
    ]
    assert command("TEST", 2, "r1", digest=created["digest"]) == tested
    changed = content.model_dump(mode="json")
    changed["rules"][-1]["section"] = "Evidence"
    successor = command("REVISE", 3, "r2", value=changed)
    command("VALIDATE", 4, "r2", digest=successor["digest"])
    retested = command("TEST", 5, "r2", digest=successor["digest"])
    assert retested["checks"][0]["findings"][-1]["status"] == "SATISFIED"
    with repository.pool.connection() as c:
        record = PostgresOntologyRepository(c).read(
            (p.namespace, p.security_domain), "interview-rules", "r1"
        )
        assert record["digest"] == created["digest"] and record[
            "content"
        ] == content.model_dump(mode="json")
        assert record["facts"][-1]["result"] == tested
    assert validated["state"] == "VALIDATE"
    # Exact published document binding reads owner history, not an in-memory rule.
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.execution_preparation import ExecutionPreparationError
    from agent_console.ontology_execution import (
        DocumentSemanticsBinding,
        published_content,
    )

    command("REVIEW", 6, "r2", digest=successor["digest"], actor="human:reviewer")
    command("PUBLISH", 7, "r2", digest=successor["digest"], actor="human:reviewer")
    binding = DocumentSemanticsBinding(
        ontology={
            "resource_id": "interview-rules",
            "revision_id": "r2",
            "digest": successor["digest"],
        },
        mapping_code="interview",
        source=refs["knowledge"],
        scope="interview",
    )
    with repository.pool.connection() as c:
        scope = ScopeIdentity(p.namespace, p.security_domain)
        assert published_content(c, scope, binding).model_dump(mode="json") == changed
        from agent_console.ontology_execution import BusinessSemanticsBinding
        from agent_console.ontology_query import SemanticQuery

        sales_binding = BusinessSemanticsBinding(
            ontology=binding.ontology,
            mapping_code=binding.mapping_code,
            source=binding.source,
            queries=(SemanticQuery(metric="net_sales"),),
        )
        with pytest.raises(ExecutionPreparationError, match="DOMAIN_MISMATCH"):
            published_content(c, scope, sales_binding)
        with pytest.raises(ExecutionPreparationError, match="SCOPE_MISMATCH"):
            published_content(c, scope, binding.model_copy(update={"scope": "other"}))
    command("DEPRECATE", 8, "r2", digest=successor["digest"], actor="human:reviewer")
    with repository.pool.connection() as c:
        with pytest.raises(
            ExecutionPreparationError, match="PUBLISHED_VERSION_REQUIRED"
        ):
            published_content(c, scope, binding)
        assert (
            published_content(c, scope, binding, current=False).model_dump(mode="json")
            == changed
        )


@pytest.mark.parametrize(
    "body,expected",
    [
        ("## Handover\nOwner: \n", "UNKNOWN"),
        ("## Handover\nOther: Alice\n", "MISSING"),
        ("## Handover\nOwner: Alice\n## Handover\nOwner: Alice\n", "CONFLICT"),
    ],
)
def test_missing_unknown_and_duplicate_section_are_distinct(body, expected):
    source = deepcopy(SOURCE)
    source["documents"][0]["text"] = body
    assert (
        evaluate_document_rules(rules(source), source)["findings"][0]["status"]
        == expected
    )


def test_oversized_repeated_evidence_is_rejected_without_truncation():
    source = deepcopy(SOURCE)
    source["documents"][0]["text"] = "## Handover\n" + "Owner: Alice\n" * 1000
    value = rules(source).model_dump(mode="json")
    value["rules"] = [dict(value["rules"][0], code=f"owner{i}") for i in range(32)]
    with pytest.raises(OntologyError, match="DOCUMENT_RULE_RESULT_TOO_LARGE"):
        evaluate_document_rules(DocumentRulesContent.model_validate(value), source)


def test_document_preparation_roundtrip_and_binding_changes_commitment():
    from agent_console.ontology_execution import (
        DocumentRuleExecutionPreparation,
        DocumentSemanticsBinding,
        parse_preparation,
    )
    from test_execution_preparation import preparation

    old = preparation()
    original = old.model_dump_json(), old.digest, old.mapping_digest
    binding = DocumentSemanticsBinding(
        ontology=old.source_snapshot,
        mapping_code="interview",
        source=old.source_snapshot,
        scope="interview",
    )
    value = {
        **old.model_dump(mode="json"),
        "schema_version": "execution-preparation.v3",
        "business_semantics": binding.model_dump(mode="json"),
    }
    new = DocumentRuleExecutionPreparation.model_validate(value)
    assert parse_preparation(value) == new
    assert (old.model_dump_json(), old.digest, old.mapping_digest) == original
    assert new.mapping_digest != old.mapping_digest
    changed = deepcopy(value)
    changed["business_semantics"]["scope"] = "another-scope"
    assert parse_preparation(changed).mapping_digest != new.mapping_digest
    changed["business_semantics"]["queries"] = []
    with pytest.raises(ValidationError):
        parse_preparation(changed)


def test_rule_tools_require_scope_and_reads_and_verify_exact_report():
    from agent_console.native_document_rule_tools import NativeDocumentRuleTools
    from agent_console.ontology_execution import DocumentSemanticsBinding

    content = rules()
    ref = content.mappings[0].source
    binding = DocumentSemanticsBinding(
        ontology=ref, source=ref, mapping_code="interview", scope="interview"
    )
    library = NativeDocumentRuleTools(
        SOURCE,
        ref.model_dump(mode="json"),
        content.model_dump(mode="json"),
        binding.model_dump(mode="json"),
    )
    args = {"documentId": "interview", "policyId": "policy"}
    assert library.invoke("review_document", args)["state"] == "NEEDS_CLARIFICATION"
    library.record_answer("interview")
    result = library.invoke("review_document", args)
    assert [f["status"] for f in result["ruleResult"]["findings"]] == [
        "SATISFIED",
        "UNKNOWN",
        "CONFLICT",
        "MISSING",
    ]
    report = library.invoke("build_report", {})
    observations = [{"kind": "TOOL_RESULT", "tool": "build_report", "output": report}]
    assert not library.verify(
        {"observations": observations}, report["completionAnswer"]
    )["passed"]
    observations += [
        {
            "kind": "TOOL_RESULT",
            "tool": "read_document",
            "arguments": {"id": identity},
            "output": library.invoke("read_document", {"id": identity}),
        }
        for identity in ["interview", "policy"]
    ]
    assert library.verify({"observations": observations}, report["completionAnswer"])[
        "passed"
    ]
    altered = deepcopy(report["completionAnswer"])
    altered["missingSections"] = []
    assert not library.verify({"observations": observations}, altered)["passed"]
    assert {t.revision for t in library.tools if t.name == "review_document"} == {"2"}


def test_rule_executor_typed_io_and_rejects_old_unbound_report():
    from agent_console.native_document_rule_tools import NativeDocumentRuleTools
    from agent_console.native_document_skill import NativeRuleDocumentSkillExecutor
    from agent_console.ontology_execution import DocumentSemanticsBinding
    from agent_console.skill_executor import SkillExecutorFailure
    from agent_console.skill_invocation_postgres import _validate_json_schema

    content = rules()
    ref = content.mappings[0].source.model_dump(mode="json")
    binding = DocumentSemanticsBinding(
        ontology=ref, source=ref, mapping_code="interview", scope="interview"
    ).model_dump(mode="json")
    library = NativeDocumentRuleTools(
        SOURCE, ref, content.model_dump(mode="json"), binding
    )
    library.record_answer("interview")
    library.invoke("review_document", {"documentId": "interview", "policyId": "policy"})
    report = library.invoke("build_report", {})

    # Isolated executor contract only; this runner is explicitly a test double.
    def runner(*_):
        return {
            "status": "SUCCEEDED",
            "trace": [{"observation": {"tool": "build_report", "output": report}}],
        }

    executor = NativeRuleDocumentSkillExecutor(runner)
    bundle = resource_content(SOURCE, rule_bound=True)
    inputs = {
        "schemaVersion": "document-review-input.v1",
        "synthetic": True,
        "sourceSnapshot": ref,
        "source": SOURCE,
        "dependencies": {},
        "ontologyContent": content.model_dump(mode="json"),
        "businessSemantics": binding,
    }
    previous = None
    for operation in bundle["skill"]["operations"]:
        args = {**inputs, "dependencies": {"prior": previous} if previous else {}}
        _validate_json_schema(args, operation["inputSchema"], "INPUT")
        previous = executor.invoke("fixture", operation["name"], args, 1000).output
        _validate_json_schema(previous, operation["outputSchema"], "OUTPUT")
    wrong = deepcopy(previous)
    del wrong["documentReview"]["ruleBinding"]
    with pytest.raises(SkillExecutorFailure, match="DOCUMENT_RULE_REPORT_MISMATCH"):
        executor.invoke(
            "fixture",
            "RENDER_REPORT",
            {**inputs, "dependencies": {"prior": wrong}},
            1000,
        )


def test_document_continuation_mapping_is_committed_and_transport_accepts_v3():
    from agent_console.execution_preparation import ExecutionPreparationError
    from agent_console.native_document_skill import NativeRuleDocumentSkillExecutor
    from agent_console.ontology_execution import (
        DocumentRuleExecutionPreparation,
        DocumentSemanticsBinding,
        document_mapping_digest,
    )
    from agent_console.workbench_prepared_execution import PreparationCommand
    from test_execution_preparation import preparation

    old = preparation()
    data = old.model_dump(mode="json")
    mapping = {
        k: data[k]
        for k in (
            "namespace",
            "security_domain",
            "root_assignment_id",
            "root_instance_id",
            "participants",
            "source_snapshot",
            "synthetic",
            "execution_boundary",
        )
    }
    executor = NativeRuleDocumentSkillExecutor.revision
    for p in mapping["participants"]:
        p.update(
            executor_id=executor.executor_id,
            executor_revision=executor.executor_revision,
            executor_digest=executor.configuration_digest,
        )
    binding = DocumentSemanticsBinding(
        ontology=old.source_snapshot,
        source=old.source_snapshot,
        mapping_code="interview",
        scope="interview",
    )
    current = DocumentRuleExecutionPreparation.model_validate(
        {
            **data,
            **mapping,
            "schema_version": "execution-preparation.v3",
            "business_semantics": binding.model_dump(mode="json"),
        }
    )
    assert document_mapping_digest(mapping, binding) == current.mapping_digest
    assert (
        PreparationCommand.model_validate(current.model_dump(mode="json")).root
        == current
    )
    bad = deepcopy(mapping)
    bad["participants"][0]["executor_revision"] = "3"
    with pytest.raises(ExecutionPreparationError, match="EXECUTOR_UNSUPPORTED"):
        document_mapping_digest(bad, binding)
    bad = deepcopy(mapping)
    bad["source_snapshot"]["digest"] = "f" * 64
    with pytest.raises(ExecutionPreparationError, match="SOURCE_MISMATCH"):
        document_mapping_digest(bad, binding)


def test_readonly_rule_policy_preserves_old_digest_and_rejects_wrong_case():
    from datetime import UTC, datetime, timedelta

    from agent_console.ontology_execution import DocumentSemanticsBinding
    from agent_console.readonly_continuation_policy import (
        ReadonlyContinuationPolicy,
        ReadonlyWork,
    )
    from test_execution_preparation import preparation

    p = preparation()
    base = dict(
        namespace=p.namespace,
        securityDomain=p.security_domain,
        subject="fixture",
        problem=p.semantics.target.problem,
        sourceContentDigests=("a" * 64,),
        case="document",
        nativeAgentName="document-worker",
        expiresAt=datetime.now(UTC) + timedelta(hours=1),
    )
    old = ReadonlyContinuationPolicy(
        policyId="fixture", policyVersion="1", works=(ReadonlyWork(**base),)
    )
    old_json = old.model_dump(mode="json", exclude_none=True)
    assert "documentRules" not in old_json["works"][0]
    assert old.digest == canonical_digest(old_json)
    binding = DocumentSemanticsBinding(
        ontology=p.source_snapshot,
        source=p.source_snapshot,
        mapping_code="interview",
        scope="interview",
    )
    new = ReadonlyContinuationPolicy(
        policyId="fixture",
        policyVersion="1",
        works=(ReadonlyWork(**base, documentRules=binding),),
    )
    assert new.digest != old.digest
    with pytest.raises(ValueError, match="DOCUMENT_RULE_CASE_MISMATCH"):
        ReadonlyWork(**{**base, "case": "sales"}, documentRules=binding)
