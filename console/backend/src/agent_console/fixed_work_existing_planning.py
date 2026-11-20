"""Original planning provider/ledger composition without startup writes."""

import hashlib
import json
from contextlib import ExitStack

from .draft_assistance_bootstrap import _profile
from .fixed_work_service_admission import require
from .plan_suggestion_bootstrap import PlanningInvocationDependencies
from .plan_suggestion_domain import ExactReference
from .plan_suggestion_invocation import PlanningProfile
from .plan_suggestion_runtime import (
    PlanningBudget,
    PlanningModelResolver,
    PlanningResponsesProvider,
    PlanningRuntime,
    budget_quote,
    create_model_repository,
    create_provider_budget,
    planning_credentials,
)


def build_existing_planning(database_url, path, migrations):
    document = json.loads(path.read_text())
    require(
        document.get("transportKind") == "REAL_PROVIDER",
        "FIXED_CYCLE_REAL_PROVIDER_REQUIRED",
    )
    profile, pepper, transport, budget_config = _profile(document, planning=True)
    # Registered successor pricing only; do not silently create a new root ledger.
    require(
        budget_config.get("profilePricingRootDigest"),
        "FIXED_CYCLE_EXISTING_PRICING_REQUIRED",
    )
    commitment = pepper.read_bytes()
    require(len(commitment) >= 32, "FIXED_CYCLE_COMMITMENT_INVALID")
    with ExitStack() as cleanup:
        model = create_model_repository(
            database_url, migration_path=migrations / "0019_model_governance.sql"
        )
        cleanup.callback(model.close)
        model.compatibility()
        budget = create_provider_budget(
            database_url,
            migration_path=migrations / "0024_draft_provider_budget.sql",
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
            profile_pricing_root_digest=budget_config["profilePricingRootDigest"],
            allowance_id=budget_config.get("allowanceId"),
        )
        cleanup.callback(budget.close)
        from .draft_provider_budget_postgres import ADAPTER
        from .provider_profile_pricing import require_revision

        with budget._connection() as c:
            row = c.execute(
                "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations "
                "WHERE version=24"
            ).fetchone()
            require(
                row
                == {
                    "checksum": hashlib.sha256(
                        budget.migration_path.read_bytes()
                    ).hexdigest(),
                    "adapter": ADAPTER,
                },
                "FIXED_CYCLE_BUDGET_SCHEMA_REQUIRED",
            )
            require_revision(c, budget)
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
            model_resolver=PlanningModelResolver(model, transport, profile),
            budget=PlanningBudget(budget),
            quote=budget_quote(transport),
            provider=PlanningResponsesProvider(
                transport, profile, planning_credentials(transport, profile)
            ),
            commitment_key=commitment,
            prepare_resources=lambda *_: None,
        )
        result = PlanningRuntime(dependencies, model, budget)
        cleanup.pop_all()
        return result
