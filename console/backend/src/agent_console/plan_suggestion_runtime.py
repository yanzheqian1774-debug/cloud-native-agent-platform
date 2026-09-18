"""Explicit planning composition, with no synthetic fallback or import-time IO."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from psycopg import Error as PsycopgError
from psycopg_pool import PoolTimeout

from .business_problem_domain import canonical_bytes
from .draft_assistance import (
    DraftAssistanceError,
    DraftScope,
    PreparedProviderRequest,
    ProviderBudgetQuote,
)
from .draft_assistance_bootstrap import GovernedProfileModelResolver, _profile
from .draft_provider_budget_postgres import PostgresProviderCallBudget
from .model_governance import ModelGovernanceError
from .model_governance_postgres import PostgresModelGovernanceRepository
from .openai_responses_draft_adapter import (
    ExactFileOpenAICredentialResolver,
    OpenAIResponsesConfiguration,
    OpenAIResponsesDraftTransport,
)
from .plan_suggestion_bootstrap import PlanningInvocationDependencies
from .plan_suggestion_domain import ExactReference, PlanningError
from .plan_suggestion_invocation import PlanningProfile
from .plan_suggestion_policy import INSTRUCTIONS, output_schema


class PlanningProviderFailure(PlanningError):
    """Only a fixed disclosure-safe reason is retained, never provider bodies."""


class PlanningResponsesProvider:
    def __init__(self, configuration, transport_profile, credentials):
        self.configuration = configuration
        self.transport_profile = transport_profile
        self.credentials = credentials
        self.transport = OpenAIResponsesDraftTransport(configuration)
        self.synthetic = configuration.execution_class == "LOCAL_HTTPS_MOCK"
        self.diagnostics = {
            "protocol": "OPENAI_RESPONSES_V1",
            "configured_model": configuration.native_model_id,
            "execution_class": configuration.execution_class,
        }

    def suggest(self, request, binding, profile, business_context):
        del binding  # Already exact-resolved and checked by the governed resolver.
        invocation_id = business_context["planning_context"]["invocation_id"]
        document = {
            "model": self.configuration.native_model_id,
            "instructions": INSTRUCTIONS,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": canonical_bytes(
                                {
                                    "target": request.target.model_dump(mode="json"),
                                    "answers": request.answers,
                                    "context": business_context,
                                }
                            ).decode(),
                        }
                    ],
                }
            ],
            "background": False,
            "store": False,
            "max_output_tokens": profile.maximum_output_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "plan_suggestion_output",
                    "strict": True,
                    "schema": output_schema(),
                }
            },
        }
        payload = canonical_bytes(document)
        # Byte count is a conservative token admission bound, including schema.
        if len(payload) > self.configuration.maximum_input_tokens:
            raise PlanningProviderFailure("PLANNING_PROVIDER_INPUT_TOO_LARGE")
        prepared = PreparedProviderRequest(payload, budget_quote(self.configuration))
        try:
            credential = self.credentials.resolve(self.transport_profile, invocation_id)
            status, body, _correlation, _latency = self.transport.exchange(
                invocation_id=invocation_id, request=prepared, credential=credential
            )
        except (OSError, TimeoutError):
            raise ConnectionError from None
        except DraftAssistanceError as exc:
            if str(exc) == "TRANSPORT_AMBIGUOUS":
                raise ConnectionError from None
            raise PlanningProviderFailure("PLANNING_CREDENTIAL_UNAVAILABLE") from None
        if len(body) > self.configuration.maximum_response_bytes:
            raise PlanningProviderFailure("PLANNING_PROVIDER_RESPONSE_TOO_LARGE")
        if not 200 <= status < 300:
            raise PlanningProviderFailure("PLANNING_PROVIDER_HTTP_REJECTED")
        try:
            response = json.loads(body)
            if response["model"] != self.configuration.native_model_id:
                raise ValueError
            if response["status"] in {"queued", "in_progress"}:
                raise ConnectionError
            if response["status"] != "completed":
                raise ValueError
            output = response["output"]
            if len(output) != 1 or output[0]["type"] != "message":
                raise ValueError
            content = output[0]["content"]
            if len(content) != 1 or content[0]["type"] != "output_text":
                raise ValueError
            text = content[0]["text"]
            if not isinstance(text, str):
                raise ValueError
            return text
        except (KeyError, TypeError, ValueError, IndexError):
            raise PlanningProviderFailure(
                "PLANNING_PROVIDER_RESPONSE_INVALID"
            ) from None


def budget_quote(configuration):
    def cost(tokens, price):
        return math.ceil(tokens * price / 1_000_000)

    return ProviderBudgetQuote(
        configuration.maximum_input_tokens,
        configuration.maximum_output_tokens,
        cost(
            configuration.maximum_input_tokens,
            configuration.input_price_microusd_per_million_tokens,
        )
        + cost(
            configuration.maximum_output_tokens,
            configuration.output_price_microusd_per_million_tokens,
        ),
    )


class PlanningModelResolver:
    def __init__(self, repository, configuration, profile):
        self.resolver = GovernedProfileModelResolver(repository, configuration)
        self.profile = profile

    def resolve_exact(self, scope, binding):
        p = self.profile
        if (scope.namespace, scope.security_domain) != (
            p.scope.namespace,
            p.scope.security_domain,
        ) or binding != p.binding:
            raise PlanningError("PLANNING_MODEL_SCOPE_MISMATCH")
        resolved = self.resolver.resolve_exact(p, SimpleNamespace(binding=binding))
        # The model owner resolves all immutable provider references; the profile
        # must not substitute a different endpoint/connection under the same model.
        for ref, expected in (
            (
                resolved.provider,
                (p.provider_id, p.provider_revision_id, p.provider_digest),
            ),
            (
                resolved.endpoint,
                (p.endpoint_id, p.endpoint_revision_id, p.endpoint_digest),
            ),
            (
                resolved.connection_profile,
                (
                    p.connection_profile_id,
                    p.connection_profile_revision_id,
                    p.connection_profile_digest,
                ),
            ),
        ):
            identity = getattr(
                ref,
                "provider_id",
                getattr(ref, "endpoint_id", getattr(ref, "profile_id", None)),
            )
            if (identity, ref.revision_id, ref.digest) != expected:
                raise PlanningError("PLANNING_MODEL_PROFILE_MISMATCH")
        return resolved


class PlanningBudget:
    def __init__(self, owner):
        self.owner = owner

    def reserve(self, key, identity, quote):
        # Existing ledger compares the scope type as well as its values.
        normalized = SimpleNamespace(
            scope=DraftScope(identity.scope.namespace, identity.scope.security_domain),
            invocation_id=identity.invocation_id,
            profile_revision_id=identity.profile_revision_id,
        )
        return self.owner.reserve(key, normalized, quote)


@dataclass
class PlanningRuntime:
    dependencies: PlanningInvocationDependencies
    model_repository: object
    budget: object
    closed: bool = False

    def close(self):
        if not self.closed:
            self.closed = True
            self.budget.close()
            self.model_repository.close()


def build_planning_runtime(
    *,
    database_url,
    runtime_configuration_path,
    migrations_path,
    allow_local_https_mock=False,
):
    """Called by app's formal startup. Tests may explicitly allow loopback HTTPS."""
    model_repository = budget = None
    try:
        path = Path(runtime_configuration_path)
        if not path.is_absolute():
            raise ValueError
        document = json.loads(path.read_text())
        if (
            not isinstance(document, dict)
            or document.get("transportKind") != "REAL_PROVIDER"
        ):
            raise ValueError
        profile, pepper_path, configuration, budget_config = _profile(
            document, planning=True, allow_local_https_mock=allow_local_https_mock
        )
        if not isinstance(configuration, OpenAIResponsesConfiguration):
            raise ValueError
        commitment = pepper_path.read_bytes()
        if len(commitment) < 32:
            raise ValueError
        model_repository = PostgresModelGovernanceRepository(
            database_url, migration_path=migrations_path / "0019_model_governance.sql"
        )
        model_repository.migrate()
        budget = PostgresProviderCallBudget(
            database_url,
            migration_path=migrations_path / "0024_draft_provider_budget.sql",
            profile=profile,
            ledger_id=budget_config["ledgerId"],
            call_cap=budget_config["callCap"],
            total_cost_cap_microusd=budget_config["totalCostCapMicrousd"],
            input_price_microusd_per_million_tokens=budget_config[
                "inputPriceMicrousdPerMillionTokens"
            ],
            output_price_microusd_per_million_tokens=budget_config[
                "outputPriceMicrousdPerMillionTokens"
            ],
        )
        budget.migrate_and_configure()
        credentials = ExactFileOpenAICredentialResolver(
            configuration,
            expected_profile_revision_id=profile.profile_revision_id,
            expected_connection_profile_id=profile.connection_profile_id,
            expected_connection_profile_revision_id=profile.connection_profile_revision_id,
        )
        dependencies = PlanningInvocationDependencies(
            profile=PlanningProfile(
                profile_revision_id=profile.profile_revision_id,
                profile_digest=profile.profile_digest,
                model=ExactReference(
                    resource_id=profile.binding.resource_id,
                    revision_id=profile.binding.revision_id,
                    digest=profile.binding.digest,
                ),
                adapter_id=profile.adapter_id,
                adapter_revision=profile.adapter_revision,
                maximum_output_tokens=profile.maximum_output_tokens,
                maximum_input_bytes=profile.maximum_input_bytes,
                real_calls_enabled=document["realCallsEnabled"],
            ),
            model_resolver=PlanningModelResolver(
                model_repository, configuration, profile
            ),
            budget=PlanningBudget(budget),
            quote=budget_quote(configuration),
            provider=PlanningResponsesProvider(configuration, profile, credentials),
            commitment_key=commitment,
            prepare_resources=lambda *_: None,
        )
        return PlanningRuntime(dependencies, model_repository, budget)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        DraftAssistanceError,
        ModelGovernanceError,
        PsycopgError,
        PoolTimeout,
    ):
        if budget is not None:
            budget.close()
        if model_repository is not None:
            model_repository.close()
        raise PlanningError("PLANNING_CONFIGURATION_INVALID") from None
