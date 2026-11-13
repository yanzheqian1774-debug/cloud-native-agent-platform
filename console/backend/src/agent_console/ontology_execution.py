"""Versioned business semantics binding; v1 preparation remains byte-compatible."""

from typing import Literal

from pydantic import Field

from .execution_preparation import ExecutionPreparation, ExecutionPreparationError
from .ontology_domain import DocumentRulesContent, OntologyContent, OntologyError, Value
from .ontology_postgres import PostgresOntologyRepository
from .ontology_query import SemanticQuery, resolve
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


def version_record():
    import hashlib
    from pathlib import Path

    path = Path(__file__).parents[2] / "migrations/0045_ontology_execution_binding.sql"
    return {
        "version": 45,
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "adapter": "ontology-execution-binding-v45",
    }


def migrate(connection):
    from pathlib import Path

    from .prepared_execution_schema import migrate as migrate_base

    migrate_base(connection)
    connection.execute("SELECT pg_advisory_xact_lock(3240034)")
    version = version_record()
    row = connection.execute(
        "SELECT version,checksum,adapter FROM "
        "execution_authority.schema_migrations WHERE version=45"
    ).fetchone()
    if row:
        if row != version:
            raise ExecutionPreparationError("ONTOLOGY_EXECUTION_SCHEMA_INCOMPATIBLE")
        return
    path = Path(__file__).parents[2] / "migrations/0045_ontology_execution_binding.sql"
    connection.execute(path.read_text())
    connection.execute(
        "INSERT INTO "
        "execution_authority.schema_migrations(version,checksum,adapter) "
        "VALUES (%s,%s,%s)",
        (45, version["checksum"], version["adapter"]),
    )


class BusinessSemanticsBinding(Value):
    schema_version: Literal["business-semantics-binding.v1"] = (
        "business-semantics-binding.v1"
    )
    ontology: ExactReference
    mapping_code: str = Field(min_length=1, max_length=64)
    source: ExactReference
    queries: tuple[SemanticQuery, ...] = Field(min_length=1, max_length=16)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))


class OntologyExecutionPreparation(ExecutionPreparation):
    schema_version: Literal["execution-preparation.v2"] = "execution-preparation.v2"
    business_semantics: BusinessSemanticsBinding

    @property
    def mapping_digest(self):
        return canonical_digest(
            {
                "base_mapping": super().mapping_digest,
                "business_semantics": self.business_semantics.model_dump(mode="json"),
            }
        )


class DocumentSemanticsBinding(Value):
    schema_version: Literal["document-semantics-binding.v1"] = (
        "document-semantics-binding.v1"
    )
    ontology: ExactReference
    mapping_code: str = Field(min_length=1, max_length=64)
    source: ExactReference
    scope: str = Field(min_length=1, max_length=200)

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))


class DocumentRuleExecutionPreparation(ExecutionPreparation):
    schema_version: Literal["execution-preparation.v3"] = "execution-preparation.v3"
    business_semantics: DocumentSemanticsBinding

    @property
    def mapping_digest(self):
        return canonical_digest(
            {
                "base_mapping": super().mapping_digest,
                "business_semantics": self.business_semantics.model_dump(mode="json"),
            }
        )


def parse_preparation(value):
    if isinstance(value, ExecutionPreparation):
        return value
    if value.get("schema_version") == "execution-preparation.v3":
        return DocumentRuleExecutionPreparation.model_validate(value)
    if value.get("schema_version") == "execution-preparation.v2":
        return OntologyExecutionPreparation.model_validate(value)
    return ExecutionPreparation.model_validate(value)


def published_content(connection, scope, binding, *, current=True):
    try:
        record = PostgresOntologyRepository(connection).read(
            (scope.namespace, scope.security_domain),
            binding.ontology.resource_id,
            binding.ontology.revision_id,
        )
        if record["digest"] != binding.ontology.digest:
            raise OntologyError("ONTOLOGY_BINDING_DIGEST_MISMATCH")
        actions = [f["action"] for f in record["facts"]]
        if "PUBLISH" not in actions or (current and "DEPRECATE" in actions):
            raise OntologyError("ONTOLOGY_PUBLISHED_VERSION_REQUIRED")
        expected_schema = (
            "business-document-rules.v1"
            if isinstance(binding, DocumentSemanticsBinding)
            else "business-ontology.v1"
        )
        if record["content"].get("schema_version") != expected_schema:
            raise OntologyError("ONTOLOGY_BINDING_DOMAIN_MISMATCH")
        if isinstance(binding, DocumentSemanticsBinding):
            content = DocumentRulesContent.model_validate(record["content"])
            if content.scope != binding.scope:
                raise OntologyError("DOCUMENT_RULE_BINDING_SCOPE_MISMATCH")
        else:
            content = OntologyContent.model_validate(record["content"])
        mappings = [
            m
            for m in content.mappings
            if m.code == binding.mapping_code and m.source == binding.source
        ]
        if len(mappings) != 1:
            raise OntologyError("ONTOLOGY_BINDING_MAPPING_MISMATCH")
        if isinstance(binding, BusinessSemanticsBinding):
            for query in binding.queries:
                resolve(content, query)
        return content
    except OntologyError as exc:
        raise ExecutionPreparationError(str(exc)) from exc


def validate_semantics(connection, scope, preparation, participant):
    binding = getattr(preparation, "business_semantics", None)
    if binding is None:
        return
    from .native_document_skill import (
        NativeDefinitionQuerySkillExecutor,
        NativeDurableDocumentSkillExecutor,
        NativeRuleDocumentSkillExecutor,
    )
    from .native_typed_document_skill import NativeTypedQuestionDocumentSkillExecutor
    from .sales_ontology_executor import SalesOntologyExecutor

    expected = (
        (
            NativeTypedQuestionDocumentSkillExecutor
            if participant.executor_revision == "7"
            else NativeDurableDocumentSkillExecutor
            if participant.executor_revision == "6"
            else NativeDefinitionQuerySkillExecutor
            if participant.executor_revision == "5"
            else NativeRuleDocumentSkillExecutor
        ).revision
        if isinstance(binding, DocumentSemanticsBinding)
        else SalesOntologyExecutor.revision
    )
    if (
        participant.executor_id,
        participant.executor_revision,
        participant.executor_digest,
    ) != (
        expected.executor_id,
        expected.executor_revision,
        expected.configuration_digest,
    ):
        raise ExecutionPreparationError("ONTOLOGY_EXECUTOR_UNSUPPORTED")
    if binding.source != preparation.source_snapshot:
        raise ExecutionPreparationError("ONTOLOGY_PREPARATION_SOURCE_MISMATCH")
    content = published_content(connection, scope, binding)
    if not any(
        (a.skill, a.operation, a.executor_id, a.executor_revision, a.executor_digest)
        == (
            participant.skill.reference,
            participant.skill.operation,
            participant.executor_id,
            participant.executor_revision,
            participant.executor_digest,
        )
        for a in content.actions
    ):
        raise ExecutionPreparationError("ONTOLOGY_EXECUTOR_BINDING_MISMATCH")


def attach_binding(connection, preparation):
    binding = getattr(preparation, "business_semantics", None)
    if binding is not None:
        from psycopg.types.json import Jsonb

        connection.execute(
            "INSERT INTO execution_authority.ontology_bindings VALUES (%s,%s,%s,%s,%s)",
            (
                preparation.namespace,
                preparation.security_domain,
                preparation.run_id,
                binding.digest,
                Jsonb(binding.model_dump(mode="json")),
            ),
        )


def document_mapping_digest(mapping, binding):
    """Commit the policy-selected rules before the execution plan is approved."""
    from .native_document_skill import (
        NativeDefinitionQuerySkillExecutor,
        NativeDurableDocumentSkillExecutor,
        NativeRuleDocumentSkillExecutor,
    )
    from .native_typed_document_skill import NativeTypedQuestionDocumentSkillExecutor

    if mapping["source_snapshot"] != binding.source.model_dump(mode="json"):
        raise ExecutionPreparationError("ONTOLOGY_PREPARATION_SOURCE_MISMATCH")
    accepted = (
        NativeRuleDocumentSkillExecutor.revision,
        NativeDefinitionQuerySkillExecutor.revision,
        NativeDurableDocumentSkillExecutor.revision,
        NativeTypedQuestionDocumentSkillExecutor.revision,
    )
    participants = mapping["participants"]
    if not participants or any(
        (p["executor_id"], p["executor_revision"], p["executor_digest"])
        not in {
            (v.executor_id, v.executor_revision, v.configuration_digest)
            for v in accepted
        }
        for p in participants
    ):
        raise ExecutionPreparationError("ONTOLOGY_EXECUTOR_UNSUPPORTED")
    return canonical_digest(
        {
            "base_mapping": canonical_digest(mapping),
            "business_semantics": binding.model_dump(mode="json"),
        }
    )
