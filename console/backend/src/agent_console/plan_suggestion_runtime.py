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


def planning_transport(configuration):
    from .kimi_responses_draft_adapter import (
        KimiResponsesConfiguration,
        KimiResponsesDraftTransport,
    )

    return (
        KimiResponsesDraftTransport(configuration)
        if isinstance(configuration, KimiResponsesConfiguration)
        else OpenAIResponsesDraftTransport(configuration)
    )


def planning_credentials(configuration, profile):
    from .kimi_responses_draft_adapter import (
        ExactFileKimiCredentialResolver,
        KimiResponsesConfiguration,
    )

    resolver = (
        ExactFileKimiCredentialResolver
        if isinstance(configuration, KimiResponsesConfiguration)
        else ExactFileOpenAICredentialResolver
    )
    return resolver(
        configuration,
        expected_profile_revision_id=profile.profile_revision_id,
        expected_connection_profile_id=profile.connection_profile_id,
        expected_connection_profile_revision_id=profile.connection_profile_revision_id,
    )


class PlanningProviderFailure(PlanningError):
    """Only a fixed disclosure-safe reason is retained, never provider bodies."""


class PlanningResponsesProvider:
    def __init__(self, configuration, transport_profile, credentials):
        self.configuration = configuration
        self.transport_profile = transport_profile
        self.credentials = credentials
        self.transport = planning_transport(configuration)
        if not hasattr(self.transport, "progress"):
            self.transport.progress = lambda _stage: None
        self.protocol = (
            "KIMI_RESPONSES_V1"
            if hasattr(configuration, "reasoning_effort")
            else "OPENAI_RESPONSES_V1"
        )
        self.isolation_enabled = True
        self.cleanup_failed = False
        self.synthetic = configuration.execution_class == "LOCAL_HTTPS_MOCK"
        self.diagnostics = {
            "protocol": self.protocol,
            "configured_model": configuration.native_model_id,
            "execution_class": configuration.execution_class,
        }

    def suggest(self, request, binding, profile, business_context):
        del binding  # Already exact-resolved and checked by the governed resolver.
        from .responses_deadline import ResponsesBoundaryError, supervise
        from .responses_jobs import PlanningResponsesJob

        if self.cleanup_failed:
            raise ConnectionError("LOCAL_CLEANUP_BLOCKED")
        if not self.isolation_enabled:  # Explicit in-process unit-test seam only.
            return self._suggest_once(request, profile, business_context)
        try:
            result, diagnostic = supervise(
                PlanningResponsesJob(
                    self.configuration,
                    self.transport_profile,
                    request,
                    profile,
                    business_context,
                ),
                self.configuration,
            )
            result["deadline"] = diagnostic
            return result
        except ResponsesBoundaryError as exc:
            self.cleanup_failed = (
                self.cleanup_failed or exc.diagnostic["reason"] == "CLEANUP_FAILURE"
            )
            return {
                "text": None,
                "failure": "PROVIDER_OUTCOME_UNKNOWN",
                "measurement": {},
                "deadline": exc.diagnostic,
            }

    def _suggest_once(self, request, profile, business_context):
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
        if self.protocol == "KIMI_RESPONSES_V1":
            document["reasoning"] = {"effort": self.configuration.reasoning_effort}
        payload = canonical_bytes(document)
        # Byte count is a conservative token admission bound, including schema.
        if len(payload) > self.configuration.maximum_input_tokens:
            raise PlanningProviderFailure("PLANNING_PROVIDER_INPUT_TOO_LARGE")
        prepared = PreparedProviderRequest(payload, budget_quote(self.configuration))
        try:
            self.transport.progress("CREDENTIAL")
            credential = self.credentials.resolve(self.transport_profile, invocation_id)
            status, body, correlation, latency = self.transport.exchange(
                invocation_id=invocation_id,
                request=prepared,
                credential=credential,
                **(
                    {
                        "connected": lambda: self.transport.progress("SEND_REQUEST"),
                        "progress": self.transport.progress,
                    }
                    if self.protocol == "KIMI_RESPONSES_V1"
                    else {}
                ),
            )
        except (OSError, TimeoutError):
            raise ConnectionError from None
        except DraftAssistanceError as exc:
            if str(exc) == "TRANSPORT_AMBIGUOUS":
                raise ConnectionError from None
            raise PlanningProviderFailure("PLANNING_CREDENTIAL_UNAVAILABLE") from None
        from .plan_suggestion_invocation import PlanningProviderResult
        from .planning_measurement import measurement

        receipt = {
            "local_request_id": invocation_id,
            "provider_request_id": None,
            "provider_response_id": None,
            "usage": None,
            "configured_model": self.configuration.native_model_id,
            "metering": self.protocol,
            "latency_ms": latency,
        }

        def failed(reason):
            return {"text": None, "failure": reason, "measurement": receipt}

        if len(body) > self.configuration.maximum_response_bytes:
            return failed("PLANNING_PROVIDER_RESPONSE_TOO_LARGE")
        try:
            response = json.loads(body)
            receipt = measurement(
                response,
                correlation,
                invocation_id,
                latency,
                self.configuration,
                protocol=self.protocol,
            )
            if not 200 <= status < 300:
                receipt["settleable"] = False
                return failed("PLANNING_PROVIDER_HTTP_REJECTED")
            if response["model"] != self.configuration.native_model_id:
                return failed("PLANNING_PROVIDER_RESPONSE_INVALID")
            if response["status"] in {"queued", "in_progress"}:
                return failed("PROVIDER_OUTCOME_UNKNOWN")
            if response["status"] != "completed":
                return failed("PLANNING_PROVIDER_RESPONSE_INVALID")
            output = response["output"]
            if self.protocol == "KIMI_RESPONSES_V1":
                if not isinstance(output, list) or any(
                    not isinstance(item, dict)
                    or item.get("type") not in {"reasoning", "message"}
                    for item in output
                ):
                    raise ValueError
                output = [item for item in output if item.get("type") == "message"]
            if len(output) != 1 or output[0]["type"] != "message":
                raise ValueError
            content = output[0]["content"]
            if len(content) != 1 or content[0]["type"] != "output_text":
                raise ValueError
            text = content[0]["text"]
            if not isinstance(text, str):
                raise ValueError
        except (KeyError, TypeError, ValueError, IndexError):
            return failed("PLANNING_PROVIDER_RESPONSE_INVALID")
        try:
            parsed = PlanningProviderResult.model_validate_json(text)
            if (
                parsed.semantics is not None
                and parsed.semantics.target != request.target
            ):
                raise ValueError
        except ValueError:
            return {
                "text": None,
                "failure": "PLANNING_OUTPUT_SCHEMA_INVALID",
                "measurement": receipt,
            }
        return {"text": text, "failure": None, "measurement": receipt}


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

    def pricing(self):
        from .draft_provider_budget_postgres import PostgresProviderCallBudget

        return PostgresProviderCallBudget.pricing(self.owner)

    def settle(self, invocation_id, reservation_id, observation):
        self.owner.record_usage(
            invocation_id + ":usage:v1", reservation_id, observation
        )
        return self.owner.read_settlement(reservation_id)


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
        from .kimi_responses_draft_adapter import KimiResponsesConfiguration

        if not isinstance(
            configuration, (OpenAIResponsesConfiguration, KimiResponsesConfiguration)
        ):
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
        credentials = planning_credentials(configuration, profile)
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
