"""Explicit planning composition with caller-supplied governed dependencies."""

from dataclasses import dataclass
from uuid import uuid4

from .model_governance_authorization import ModelUseAuthorizationAdapter
from .plan_invocation_postgres import PostgresPlanningInvocations
from .plan_model_use_postgres import PostgresPlanModelUseOwner
from .plan_suggestion_application import PlanningApplication
from .plan_suggestion_authorization import PlanningCurrentAuthority
from .plan_suggestion_service import PlanningSuggestionService


@dataclass(frozen=True)
class PlanningInvocationDependencies:
    profile: object
    model_resolver: object
    budget: object
    quote: object
    provider: object
    commitment_key: bytes
    prepare_resources: object
    identity_factory: object = lambda: str(uuid4())
    adaptive_limits: object = None
    admission_factory: object = None

    def bind(self, application, authorization):
        invocations = PostgresPlanningInvocations(application.repository)
        invocations.migrate()
        owner = PostgresPlanModelUseOwner(application.repository)

        def factory(context):
            return PlanningSuggestionService(
                PlanningApplication(
                    application.repository,
                    application.problems,
                    PlanningCurrentAuthority(context, authorization),
                ),
                invocations,
                self.profile,
                model_authorizer=ModelUseAuthorizationAdapter(context, authorization),
                model_resolver=self.model_resolver,
                budget=self.budget,
                quote=self.quote,
                provider=self.provider,
                model_use_owner=owner,
                commitment_key=self.commitment_key,
                prepare_resources=self.prepare_resources,
                identity_factory=self.identity_factory,
                adaptive_limits=self.adaptive_limits,
                prepare_admission=self.admission_factory(context)
                if self.admission_factory
                else None,
            )

        return factory
