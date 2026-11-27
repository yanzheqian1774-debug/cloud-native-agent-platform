"""Default-off complete owner assembly; never constructs an identity from a row."""

from .bound_service_execution import BoundServiceExecutionBridge
from .fixed_question_answer import FixedQuestionAnswers
from .fixed_question_execution import FixedQuestionExecutionAuthority
from .fixed_question_policy import FixedQuestionPolicy
from .fixed_question_presentation import FixedQuestionPresentations


class FixedQuestionComposition:
    def __init__(
        self,
        policy,
        service_registry,
        runtime,
        execution,
        work,
        *,
        settlement_reader,
        clock,
    ):
        if not isinstance(policy, FixedQuestionPolicy) or not policy.enabled:
            raise TypeError("FIXED_QUESTION_POLICY_NOT_ENABLED")
        service = service_registry._policy()
        matching = [
            s
            for s in policy.scopes
            if s.executionSubject == service.subjectId
            and s.serviceCredentialId == service.credentialId
            and s.work == service.work
            and s.bindingDigest == service.sourceBindingDigest
            and (s.tenantId, s.securityDomain)
            == (service.tenantId, service.securityDomain)
        ]
        if len(matching) != len(policy.scopes) or not matching:
            raise TypeError("FIXED_QUESTION_SERVICE_POLICY_MISMATCH")
        if (
            runtime.subject != service.subjectId
            or runtime.service_credential_id != service.credentialId
        ):
            raise TypeError("FIXED_QUESTION_SERVICE_RUNTIME_MISMATCH")
        if (
            runtime.generation.generation != policy.generation
            or runtime.generation.digest != policy.generationDigest
        ):
            raise TypeError("FIXED_QUESTION_GENERATION_MISMATCH")
        binding = getattr(runtime, "bound_service_execution", None)
        if (
            not isinstance(binding, BoundServiceExecutionBridge)
            or binding.registry is not service_registry
        ):
            raise TypeError("FIXED_QUESTION_ORIGINAL_SERVICE_BRIDGE_REQUIRED")
        if (
            not callable(settlement_reader)
            or runtime.skill_repository is None
            or runtime.durable_wait is None
            or runtime.authorize_current is None
        ):
            raise TypeError("FIXED_QUESTION_ORIGINAL_OWNERS_REQUIRED")
        # Reuse the exact original execution bridge. Delegation never adds a
        # service identity/reader to a Human or otherwise unbound runtime.
        self.policy, self.clock = policy, clock
        self.execution = FixedQuestionExecutionAuthority(runtime, execution, work)
        self.settlement_reader = settlement_reader
        self.skill_repository = runtime.skill_repository

    def owners(self, delivery):
        presentations = FixedQuestionPresentations(
            delivery,
            self.policy,
            clock=self.clock,
            validate_execution=self.execution,
        )
        return presentations, FixedQuestionAnswers(
            presentations,
            settlement_reader=self.settlement_reader,
            skill_repository=self.skill_repository,
        )
