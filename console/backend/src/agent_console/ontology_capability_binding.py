"""Exact semantic references alongside employee members, never implicit USE."""

from .business_capability import BusinessCapabilityError
from .ontology_domain import DocumentRulesContent, OntologyError
from .ontology_execution import DocumentSemanticsBinding
from .ontology_postgres import PostgresOntologyRepository
from .ontology_service import resource
from .plan_suggestion_domain import ExactReference
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError


def read_reference(call, reference, *, current):
    ref = ExactReference.model_validate(reference)
    principal = OwnerPrincipal(
        call.context.principal_id,
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
    )
    call.authority.require(
        principal,
        "BUSINESS_ONTOLOGY",
        "READ",
        resource(ref.resource_id, ref.revision_id),
    )
    try:
        if current:
            call.connection.execute(
                "SELECT ontology_id FROM business_ontology.definitions "
                "WHERE namespace=%s "
                "AND security_domain=%s AND ontology_id=%s FOR SHARE",
                (principal.tenant_id, principal.security_domain, ref.resource_id),
            ).fetchone()
        value = PostgresOntologyRepository(call.connection).read(
            (principal.tenant_id, principal.security_domain),
            ref.resource_id,
            ref.revision_id,
        )
        if value["digest"] != ref.digest:
            raise BusinessCapabilityError("CAPABILITY_MEMBER_VERSION_MISMATCH")
        actions = {f["action"] for f in value["facts"]}
        if "PUBLISH" not in actions or (current and "DEPRECATE" in actions):
            raise BusinessCapabilityError("CAPABILITY_MEMBER_NOT_PUBLISHED")
        return value
    except OntologyError as exc:
        raise BusinessCapabilityError("CAPABILITY_REFERENCE_UNAVAILABLE") from exc


def document_binding(call, resolved):
    """Resolve only the declared exact reference and uniquely matching source."""
    bindings = resolved["contract"]["bindings"]
    ontologies = [b["reference"] for b in bindings if b["kind"] == "ONTOLOGY"]
    if not ontologies:
        return None
    sources = [b["reference"] for b in bindings if b["kind"] == "KNOWLEDGE"]
    if len(ontologies) != 1 or len(sources) != 1:
        raise WorkbenchOwnerError("CAPABILITY_ONTOLOGY_MAPPING_AMBIGUOUS", 409)
    try:
        value = read_reference(call, ontologies[0], current=True)
        if value["content"].get("schema_version") != "business-document-rules.v1":
            raise WorkbenchOwnerError("CAPABILITY_ONTOLOGY_DOMAIN_UNSUPPORTED", 409)
        content = DocumentRulesContent.model_validate(value["content"])
        source = ExactReference.model_validate(sources[0])
        mappings = [m for m in content.mappings if m.source == source]
        if len(mappings) != 1:
            raise WorkbenchOwnerError("CAPABILITY_ONTOLOGY_MAPPING_MISMATCH", 409)
        return DocumentSemanticsBinding(
            ontology=ExactReference.model_validate(ontologies[0]),
            mapping_code=mappings[0].code,
            source=source,
            scope=content.scope,
        )
    except BusinessCapabilityError as exc:
        raise WorkbenchOwnerError(str(exc), 409) from exc


def require_work_binding(selected, approved):
    if selected is not None and selected != approved:
        raise WorkbenchOwnerError("CAPABILITY_ONTOLOGY_WORK_BINDING_MISMATCH", 409)
