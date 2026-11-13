"""Parallel read-only understanding profile on the existing fixed allowance."""

from pathlib import Path
from typing import Literal

from psycopg import Error as StorageError
from pydantic import BaseModel, ConfigDict

from .authority_contracts import AuthorityError
from .context_call_admission import ContextCallAdmission
from .conversation_experience_admission import ConversationExperienceAdmission
from .task_delegation import Limits, configured_limits, digest


class RelationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["f3-conversation-relation-admission.v1"]
    predecessorUnderstandingPolicyDigest: str
    sharedAllowanceId: str
    configuration: Limits
    externalWrites: Literal[False]
    scopeMode: Literal["EXISTING_BUSINESS_WORK"]


class RelationExperience(ConversationExperienceAdmission):
    policy_model = RelationPolicy

    def __init__(self, root, path, configuration):
        if root is None or root.experience is None:
            raise AuthorityError("CONVERSATION_ROUTING_POLICY_INVALID")
        self.root = root
        self.routing_path = Path(path)
        if (
            not self.routing_path.is_absolute()
            or self.routing_path.stat().st_mode & 0o077
        ):
            raise AuthorityError("CONVERSATION_ROUTING_POLICY_INVALID")
        self.routing_document = self.policy_model.model_validate_json(
            self.routing_path.read_text()
        )
        self.path = root.experience.path
        self.document = root.experience.document
        self.policy_digest = root.experience.policy_digest
        expected = self.routing_document.configuration.model_dump()
        original = root.configuration
        if (
            not self.document.ownedConversationUnderstanding
            or self.routing_document.predecessorUnderstandingPolicyDigest
            != root.experience.understanding_policy_digest
            or not self.document.allowanceId
            or self.routing_document.sharedAllowanceId != self.document.allowanceId
            or expected != configuration
            or any(
                expected[k] != original[k]
                for k in ("ledger_id", "calls", "cost_microusd")
            )
            or any(expected[k] > original[k] for k in ("input_tokens", "output_tokens"))
        ):
            raise AuthorityError("CONVERSATION_ROUTING_POLICY_INVALID")
        self.understanding_policy_digest = digest(
            self.routing_document.model_dump(mode="json")
        )
        self.history_policy_digest = digest(
            {
                "relationPolicy": self.understanding_policy_digest,
                "historyPolicy": root.experience.history_policy_digest,
            }
        )

    def _require(self, service, c, context):
        if (
            self.policy_model.model_validate_json(self.routing_path.read_text())
            != self.routing_document
            or self.routing_path.stat().st_mode & 0o077
            or service.configuration != self.routing_document.configuration.model_dump()
        ):
            raise AuthorityError("CONVERSATION_ROUTING_POLICY_CHANGED")
        # Reuse current original account, generation, fixed expiry and allowance
        # validation. Do not replace the old service configuration or context rows.
        return self.root.experience._require(self.root, c, context)


def configure(service, root, grants, authorizer, policy_path):
    from .draft_assistance_authorization import GrantAdministrationDraftAuthorization

    if service.profile.adapter_revision != "v3-relation":
        raise AuthorityError("CONVERSATION_ROUTING_PROFILE_INVALID")
    configuration = configured_limits(
        service.profile, service.transport.configuration, service.budget
    )
    admission = ContextCallAdmission(root.delegation, configuration)
    admission.experience = RelationExperience(root, policy_path, configuration)
    if (
        service.budget.ledger_id != root.configuration["ledger_id"]
        or service.budget.allowance_id != root.experience.document.allowanceId
    ):
        raise AuthorityError("CONVERSATION_ROUTING_ALLOWANCE_MISMATCH")
    service.authorization = GrantAdministrationDraftAuthorization(
        grants, authorizer, clock=grants.clock
    )
    service.authorization.context_admission = admission
    service.budget.context_admission = admission
    service.budget.delegation_configuration = configuration
    root.conversation_relation = admission
    return admission


def available(service, context):
    """Read-only account/policy eligibility, never a dispatch or grant request."""
    if service is None:
        return False
    admission = getattr(service.authorization, "context_admission", None)
    experience = getattr(admission, "experience", None)
    if (
        not isinstance(experience, RelationExperience)
        or not experience.matches(context)
        or service.profile.profile_revision_id
        != admission.configuration["profile_revision_id"]
        or service.profile.profile_digest != admission.configuration["profile_digest"]
    ):
        return False
    try:
        with admission.repository.connection_scope() as c:
            experience._require(admission, c, context)
        return True
    except (AuthorityError, StorageError, OSError, ValueError):
        return False
