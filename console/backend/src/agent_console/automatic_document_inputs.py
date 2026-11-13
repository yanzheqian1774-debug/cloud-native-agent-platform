"""Pinned, authorized rule inputs for actual document resource computation."""

from . import owned_business_resource_adapter as owned_resources
from .authority_contracts import AuthorityError, ExactGrant
from .execution_domain import ScopeIdentity
from .native_document_rule_tools import NativeDocumentRuleTools
from .ontology_execution import published_content
from .ontology_service import resource
from .resource_automation_policy import source_digest


def resolve(automation, call, work, issuer, key, source_ref, source_revision):
    continuation = getattr(automation, "continuation", None)
    if continuation is None:
        raise AuthorityError("RESOURCE_DOCUMENT_RULE_POLICY_REQUIRED")
    if isinstance(work, owned_resources.OwnedResourceWork):
        if not continuation.policy.enabled or work.historyRead:
            raise AuthorityError("RESOURCE_DOCUMENT_RULE_POLICY_REQUIRED")
        current = automation.work(
            call.context,
            work.problem,
            automation.grants.clock(),
            connection=call.connection,
            source_digest=source_digest(source_revision["content"]),
        )
        if owned_resources.evidence(current) != owned_resources.evidence(work):
            raise AuthorityError("OWNED_BUSINESS_ADMISSION_CHANGED")
        approved = owned_resources.readonly_work(current)
    else:
        approved = continuation.policy.work(
            call.context,
            work.problem,
            source_digest(source_revision["content"]),
            automation.grants.clock(),
        )
    binding = approved.documentRules
    if binding is None or binding.source != source_ref:
        raise AuthorityError("RESOURCE_DOCUMENT_RULE_BINDING_REQUIRED")
    grants = [
        ExactGrant(
            "BUSINESS_ONTOLOGY",
            "READ",
            resource(binding.ontology.resource_id, binding.ontology.revision_id),
        )
    ]
    proof = automation.decide(
        call,
        grants,
        key + ":document-rule-test-read:" + continuation.policy.digest,
        work.model_copy(update={"expiresAt": min(work.expiresAt, approved.expiresAt)}),
        issuer,
    )
    automation.proof_grants(call, grants)
    content = published_content(
        call.connection,
        ScopeIdentity(call.context.scope.tenant_id, call.context.scope.security_domain),
        binding,
    )
    return (
        {
            "ontologyContent": content.model_dump(mode="json"),
            "businessSemantics": binding.model_dump(mode="json"),
        },
        {
            "documentRules": binding.model_dump(mode="json"),
            "documentRulePolicyDigest": continuation.policy.digest,
            "documentRuleReadDecisionId": proof.decision_id,
        },
    )


def validate(inputs, source, source_ref):
    # Same rule/source binding validator used by the actual Native executor.
    # This does not run Native reasoning or create a business execution artifact.
    NativeDocumentRuleTools(
        source,
        source_ref.model_dump(mode="json"),
        inputs["ontologyContent"],
        inputs["businessSemantics"],
    )
