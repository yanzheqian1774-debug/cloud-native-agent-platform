"""Spawn-safe Responses jobs: no repositories or connection pools cross IPC."""

from dataclasses import asdict, dataclass

from .draft_assistance import DraftAssistanceError


@dataclass
class DraftResponsesJob:
    configuration: object
    invocation_id: str
    request: object
    credential: object
    profile: object

    def run(self, progress):
        from .openai_responses_draft_adapter import OpenAIResponsesDraftTransport

        transport = OpenAIResponsesDraftTransport(self.configuration)
        transport.isolation_enabled = False
        transport.progress = progress
        progress("PREPARE")
        return asdict(
            transport.dispatch(
                invocation_id=self.invocation_id,
                request=self.request,
                credential=self.credential,
                profile=self.profile,
            )
        )


@dataclass
class PlanningResponsesJob:
    configuration: object
    transport_profile: object
    request: object
    profile: object
    business_context: dict

    def run(self, progress):
        from .plan_suggestion_runtime import (
            PlanningProviderFailure,
            PlanningResponsesProvider,
            planning_credentials,
        )

        p = self.transport_profile
        credentials = planning_credentials(self.configuration, p)
        provider = PlanningResponsesProvider(self.configuration, p, credentials)
        provider.isolation_enabled = False
        provider.transport.progress = progress
        progress("PREPARE")
        try:
            return provider._suggest_once(
                self.request, self.profile, self.business_context
            )
        except PlanningProviderFailure as exc:
            return {"text": None, "failure": str(exc), "measurement": {}}
        except DraftAssistanceError:
            return {
                "text": None,
                "failure": "PLANNING_CREDENTIAL_UNAVAILABLE",
                "measurement": {},
            }
