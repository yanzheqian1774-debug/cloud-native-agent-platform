"""Bounded business definitions; no execution, authentication or SQL authority."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest

Code = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")]
Label = Annotated[str, Field(min_length=1, max_length=200)]


class OntologyError(ValueError):
    pass


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Property(Value):
    code: Code
    kind: Literal["TEXT", "MONEY", "PERIOD"]
    required: bool = True


class ObjectType(Value):
    code: Code
    identity_fields: tuple[Code, ...] = Field(min_length=1, max_length=8)
    properties: tuple[Property, ...] = Field(min_length=1, max_length=256)


class Relation(Value):
    code: Code
    source_object: Code
    target_object: Code
    source_key: Code
    target_key: Code
    cardinality: Literal["MANY_TO_ONE", "ONE_TO_ONE"]
    missing_reference_policy: Literal["REJECT"] = "REJECT"


class Expression(Value):
    op: Literal["SUM", "SUBTRACT"]
    field: Code | None = None
    operands: tuple["Expression", ...] = Field(default=(), max_length=2)

    @model_validator(mode="after")
    def supported(self):
        if self.op == "SUM" and (self.field is None or self.operands):
            raise OntologyError("ONTOLOGY_EXPRESSION_INVALID")
        if self.op == "SUBTRACT" and (self.field or len(self.operands) != 2):
            raise OntologyError("ONTOLOGY_EXPRESSION_INVALID")
        return self


class Metric(Value):
    code: Code
    name: Label
    aliases: tuple[Label, ...] = Field(default=(), max_length=16)
    object_code: Code
    expression: Expression
    unit: Literal["SOURCE_CURRENCY_2DP"] = "SOURCE_CURRENCY_2DP"
    grain: tuple[Code, ...] = ("rowId",)
    time_field: Code = "period"
    dimensions: tuple[Code, ...] = ("region", "channel", "product")


class SourceMapping(Value):
    code: Code
    source: ExactReference
    source_digest: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    source_schema: Literal["sales-diagnostic-source.v1"]
    object_code: Code
    fields: dict[Code, Code] = Field(min_length=1, max_length=256)
    identity_scope: Literal["SOURCE_SNAPSHOT"] = "SOURCE_SNAPSHOT"


class SalesRules(Value):
    excluded_statuses: tuple[Literal["CANCELLED"], ...] = ("CANCELLED",)
    included_kinds: tuple[Literal["SALE", "RETURN"], ...] = ("SALE", "RETURN")
    currency_policy: Literal["SEPARATE_NO_IMPLICIT_FX"] = "SEPARATE_NO_IMPLICIT_FX"
    max_rows: int = Field(default=10000, ge=1, le=10000)
    claim: Literal["OBSERVATIONAL_NOT_CAUSAL"] = "OBSERVATIONAL_NOT_CAUSAL"

    @model_validator(mode="after")
    def safe(self):
        if self.excluded_statuses != ("CANCELLED",) or not self.included_kinds:
            raise OntologyError("ONTOLOGY_SALES_RULE_UNSUPPORTED")
        if len(set(self.included_kinds)) != len(self.included_kinds):
            raise OntologyError("ONTOLOGY_DUPLICATE_KIND")
        return self


class ActionContract(Value):
    skill: ExactReference
    executor_id: Label
    executor_revision: Label
    executor_digest: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    operation: Literal["READ_DATA", "VALIDATE_DATA", "SUMMARIZE", "RENDER_REPORT"]
    side_effect: Literal["READ_ONLY"] = "READ_ONLY"


def unique(values):
    if len(values) != len(set(values)):
        raise OntologyError("ONTOLOGY_DUPLICATE_CODE")


class OntologyContent(Value):
    schema_version: Literal["business-ontology.v1"] = "business-ontology.v1"
    name: Label
    business_owner: Label
    data_owner: Label
    synthetic: Literal[True] = True
    objects: tuple[ObjectType, ...] = Field(min_length=1, max_length=32)
    relations: tuple[Relation, ...] = Field(default=(), max_length=64)
    metrics: tuple[Metric, ...] = Field(min_length=1, max_length=32)
    mappings: tuple[SourceMapping, ...] = Field(min_length=1, max_length=32)
    rules: SalesRules
    actions: tuple[ActionContract, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def references(self):
        for items in (self.objects, self.relations, self.metrics, self.mappings):
            unique([v.code for v in items])
        objects = {v.code: v for v in self.objects}
        for obj in self.objects:
            unique([p.code for p in obj.properties])
            if not set(obj.identity_fields) <= {p.code for p in obj.properties}:
                raise OntologyError("ONTOLOGY_IDENTITY_FIELD_MISSING")
        for rel in self.relations:
            for obj, field in (
                (rel.source_object, rel.source_key),
                (rel.target_object, rel.target_key),
            ):
                if obj not in objects or field not in {
                    p.code for p in objects[obj].properties
                }:
                    raise OntologyError("ONTOLOGY_RELATION_INVALID")
            source_kind = next(
                p.kind
                for p in objects[rel.source_object].properties
                if p.code == rel.source_key
            )
            target_kind = next(
                p.kind
                for p in objects[rel.target_object].properties
                if p.code == rel.target_key
            )
            if source_kind != target_kind:
                raise OntologyError("ONTOLOGY_RELATION_TYPE_MISMATCH")
        for metric in self.metrics:
            if (
                metric.grain != ("rowId",)
                or metric.time_field != "period"
                or not set(metric.dimensions) <= {"region", "channel", "product"}
            ):
                raise OntologyError("ONTOLOGY_METRIC_GRAIN_UNSUPPORTED")
            obj = objects.get(metric.object_code)
            if obj is None:
                raise OntologyError("ONTOLOGY_METRIC_OBJECT_INVALID")
            fields = {p.code: p.kind for p in obj.properties}
            if (
                not set((*metric.grain, metric.time_field, *metric.dimensions))
                <= fields.keys()
            ):
                raise OntologyError("ONTOLOGY_METRIC_FIELD_INVALID")
            nodes = [metric.expression]
            count = 0
            while nodes:
                exp = nodes.pop()
                count += 1
                if count > 16 or (exp.field and fields.get(exp.field) != "MONEY"):
                    raise OntologyError("ONTOLOGY_EXPRESSION_TYPE_INVALID")
                nodes.extend(exp.operands)
        for mapping in self.mappings:
            if mapping.object_code not in objects or not set(mapping.fields) <= {
                p.code for p in objects[mapping.object_code].properties
            }:
                raise OntologyError("ONTOLOGY_MAPPING_INVALID")
        if len(self.model_dump_json().encode()) > 96 * 1024:
            raise OntologyError("ONTOLOGY_CONTENT_TOO_LARGE")
        return self


class DocumentRule(Value):
    code: Code
    name: Label
    kind: Literal["REQUIRED_SECTION", "SINGLE_VALUE_FIELD"]
    section: Label
    field: Label | None = None

    @model_validator(mode="after")
    def shape(self):
        if (self.kind == "SINGLE_VALUE_FIELD") != (self.field is not None):
            raise OntologyError("DOCUMENT_RULE_FIELD_INVALID")
        if not self.section.strip() or any(c in self.section for c in "\n\r"):
            raise OntologyError("DOCUMENT_RULE_SECTION_INVALID")
        if self.field is not None and (
            not self.field.strip() or any(c in self.field for c in "\n\r\uff1a:")
        ):
            raise OntologyError("DOCUMENT_RULE_FIELD_INVALID")
        return self


class DocumentSourceMapping(Value):
    code: Code
    source: ExactReference
    source_digest: Annotated[str, Field(pattern="^[a-f0-9]{64}$")]
    source_schema: Literal["document-review-source.v1"]


class DocumentRuleAction(ActionContract):
    operation: Literal["READ_DATA", "VALIDATE_DATA", "ANALYZE_DATA", "RENDER_REPORT"]


class DocumentRulesContent(Value):
    schema_version: Literal["business-document-rules.v1"] = "business-document-rules.v1"
    name: Label
    business_owner: Label
    data_owner: Label
    synthetic: Literal[True] = True
    scope: Label
    mappings: tuple[DocumentSourceMapping, ...] = Field(min_length=1, max_length=1)
    rules: tuple[DocumentRule, ...] = Field(min_length=1, max_length=32)
    actions: tuple[DocumentRuleAction, ...] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def bounded(self):
        unique([rule.code for rule in self.rules])
        if len(self.model_dump_json().encode()) > 96 * 1024:
            raise OntologyError("ONTOLOGY_CONTENT_TOO_LARGE")
        return self


def parse_ontology_content(value):
    if value.get("schema_version") == "business-document-rules.v1":
        return DocumentRulesContent.model_validate(value)
    return OntologyContent.model_validate(value)


class OntologyCommand(Value):
    request_key: Annotated[str, Field(min_length=1, max_length=128)]
    expected_version: int = Field(ge=0)
    revision_id: Annotated[str, Field(min_length=1, max_length=128)]
    digest: Annotated[str, Field(pattern="^[a-f0-9]{64}$")] | None = None
    content: OntologyContent | DocumentRulesContent | None = None
    reason: Annotated[str, Field(min_length=1, max_length=500)]


def content_digest(scope, identity, revision, predecessor, content):
    return canonical_digest(
        {
            "schema": "ontology-revision.v1",
            "scope": list(scope),
            "identity": identity,
            "revision": revision,
            "predecessor": predecessor,
            "content": content,
        }
    )
