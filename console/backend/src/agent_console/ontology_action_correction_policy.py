"""Exact opt-in permission to correct only an ontology's executor action binding."""

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .authority_contracts import AuthorityError
from .ontology_execution import DocumentSemanticsBinding, published_content
from .plan_suggestion_domain import ExactReference
from .resource_use_domain import canonical_digest


def require(ok, reason):
    if not ok:
        raise AuthorityError("ONTOLOGY_CORRECTION_" + reason)


class CorrectionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["ontology-action-correction.v1"]
    enabled: Literal[True]
    tenantId: str
    securityDomain: str
    subjectId: str
    admissionId: str
    admissionRecordDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    originalPolicyDigest: str = Field(pattern=r"^[a-f0-9]{64}$")
    problem: ExactReference
    plan: ExactReference
    oldBinding: DocumentSemanticsBinding
    newBinding: DocumentSemanticsBinding
    expiresAt: datetime

    @property
    def digest(self):
        return canonical_digest(self.model_dump(mode="json"))

    @classmethod
    def load(cls, path):
        path = Path(path)
        st = path.stat()
        require(
            path.is_absolute()
            and path.is_file()
            and not path.is_symlink()
            and st.st_uid == os.getuid()
            and st.st_mode & 0o077 == 0,
            "POLICY_INVALID",
        )
        result = cls.model_validate_json(path.read_text())
        require(result.expiresAt.tzinfo is not None, "POLICY_INVALID")
        require(result.oldBinding.ontology != result.newBinding.ontology, "NO_CHANGE")
        require(
            result.oldBinding.model_dump(exclude={"ontology"})
            == result.newBinding.model_dump(exclude={"ontology"}),
            "BUSINESS_SCOPE_CHANGED",
        )
        return result


def verify_actions(content, business_scope):
    """Check configuration before publication; this does not grant authority."""
    from .native_typed_document_skill import NativeTypedQuestionDocumentSkillExecutor
    from .ontology_execution import DocumentSemanticsBinding

    require(
        isinstance(business_scope.documentRules, DocumentSemanticsBinding),
        "DOCUMENT_REQUIRED",
    )
    require(len(business_scope.skills) == 1, "EXACT_SINGLE_SKILL_REQUIRED")
    revision = NativeTypedQuestionDocumentSkillExecutor.revision
    expected = {
        (
            business_scope.skills[0],
            op,
            revision.executor_id,
            revision.executor_revision,
            revision.configuration_digest,
            "READ_ONLY",
        )
        for op in business_scope.operations
    }
    actual = [
        (
            a.skill,
            a.operation,
            a.executor_id,
            a.executor_revision,
            a.executor_digest,
            a.side_effect,
        )
        for a in content.actions
    ]
    require(
        len(actual) == len(expected) and set(actual) == expected,
        "ACTION_BINDING_MISMATCH",
    )


def verify_compatibility(c, scope, policy, binding):
    require(
        binding.scope.documentRules == policy.oldBinding, "ORIGINAL_BINDING_CHANGED"
    )
    old = published_content(c, scope, policy.oldBinding)
    new = published_content(c, scope, policy.newBinding)
    require(
        old.model_dump(exclude={"actions"}) == new.model_dump(exclude={"actions"}),
        "BUSINESS_RULES_CHANGED",
    )
    require(
        sorted(a.operation for a in old.actions)
        == sorted(a.operation for a in new.actions),
        "OPERATIONS_CHANGED",
    )
    verify_actions(new, binding.scope)
    # New skill must be actual published v7, not a name declared only by policy.
    from .native_typed_document_skill import NativeTypedQuestionDocumentSkillExecutor
    from .planning_candidates import read_published

    content, _ = read_published(c, scope, "SKILL", binding.scope.skills[0])
    expected = NativeTypedQuestionDocumentSkillExecutor.revision
    # Canonical published skill contract is validated by the normal preparation owner.
    operations = [
        op
        for op in content.get("operations", [])
        if op.get("name") in binding.scope.operations
    ]
    require(
        len(operations) == len(binding.scope.operations)
        and all(
            (
                op.get("executorId"),
                op.get("executorRevision"),
                op.get("executorConfigurationDigest"),
            )
            == (
                expected.executor_id,
                expected.executor_revision,
                expected.configuration_digest,
            )
            for op in operations
        ),
        "SKILL_EXECUTOR_CHANGED",
    )
