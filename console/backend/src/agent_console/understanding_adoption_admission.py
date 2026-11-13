"""Separate explicit successor composition; C1 policy and active profile stay fixed."""

from typing import Literal

from .authority_contracts import AuthorityError
from .context_call_admission import ContextCallAdmission
from .conversation_relation_admission import RelationExperience, RelationPolicy
from .task_delegation import configured_limits
from .understanding_adoption_origin import AdoptionOrigin


class AdoptionPolicy(RelationPolicy):
    schemaVersion: Literal["f3-conversation-relation-admission.v2"]
    scopeMode: Literal["EXISTING_WORK_AND_INITIAL_UNDERSTANDING"]
    predecessorRoutingPolicyDigest: str


class AdoptionExperience(RelationExperience):
    policy_model = AdoptionPolicy

    def __init__(self, root, previous, path, configuration):
        super().__init__(root, path, configuration)
        if (
            previous is None
            or previous.experience.root is not root
            or self.routing_document.predecessorRoutingPolicyDigest
            != previous.experience.understanding_policy_digest
        ):
            raise AuthorityError("UNDERSTANDING_ADOPTION_PREDECESSOR_MISMATCH")
        self.previous = previous


def configure(service, root, previous, grants, authorizer, policy_path):
    from .draft_assistance_authorization import GrantAdministrationDraftAuthorization

    if service.profile.adapter_revision not in {
        "v3-relation-adoption",
        "v3-relation-adoption-source",
        "v3-relation-adoption-source-answers",
    }:
        raise AuthorityError("UNDERSTANDING_ADOPTION_PROFILE_INVALID")
    configuration = configured_limits(
        service.profile, service.transport.configuration, service.budget
    )
    admission = ContextCallAdmission(root.delegation, configuration)
    admission.experience = AdoptionExperience(
        root, previous, policy_path, configuration
    )
    if (
        service.budget.ledger_id != root.configuration["ledger_id"]
        or service.budget.allowance_id != root.experience.document.allowanceId
    ):
        raise AuthorityError("UNDERSTANDING_ADOPTION_ALLOWANCE_MISMATCH")
    previous_origin = getattr(root, "understanding_adoption", None)
    if service.profile.adapter_revision == "v3-relation-adoption-source" and (
        previous_origin is None
        or previous_origin.routing is not previous
        or previous_origin.profile.adapter_revision != "v3-relation-adoption"
    ):
        raise AuthorityError("UNDERSTANDING_ADOPTION_PREDECESSOR_MISMATCH")
    if service.profile.adapter_revision == "v3-relation-adoption-source-answers" and (
        previous_origin is None
        or previous_origin.routing is not previous
        or previous_origin.profile.adapter_revision != "v3-relation-adoption-source"
    ):
        raise AuthorityError("UNDERSTANDING_ADOPTION_PREDECESSOR_MISMATCH")
    service.authorization = GrantAdministrationDraftAuthorization(
        grants, authorizer, clock=grants.clock
    )
    service.authorization.context_admission = admission
    service.budget.context_admission = admission
    service.budget.delegation_configuration = configuration
    root.retained_conversation_relations = (
        previous,
        *getattr(root, "retained_conversation_relations", ()),
    )
    root.conversation_relation = admission
    root.understanding_adoption = AdoptionOrigin(
        root,
        admission,
        service.profile,
        enabled=True,
        retained=(previous_origin,) if previous_origin is not None else (),
    )
    return admission
