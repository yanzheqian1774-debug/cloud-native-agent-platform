"""Independent exact grants, scope checks, and no lookup on denial."""

from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError, AuthorityScope
from agent_console.draft_assistance_authorization import (
    GrantAdministrationDraftAuthorization,
)
from agent_console.plan_suggestion_authorization import PlanningCurrentAuthority
from agent_console.plan_suggestion_service import PlanningSuggestionService
from agent_console.provider_usage import grants
from test_draft_assistance import build, context
from test_planning_runtime import formal as formal
from test_planning_runtime import send


class Current:
    def __init__(self):
        self.allowed = set()

    def authorize_current(self, context, grant, **kwargs):
        key = (
            context.principal_id,
            context.scope.tenant_id,
            context.scope.security_domain,
            grant.owner,
            grant.action,
            grant.exact_resource,
        )
        return NS(decision_id="controlled") if key in self.allowed else None


@pytest.mark.parametrize("kind", ["understanding", "planning"])
def test_two_independent_grants_before_lookup_and_scope(kind):
    ctx = context()
    current = Current()
    lookups = []
    identity = "synthetic-invocation"

    def lookup(*args):
        lookups.append(args)
        return None

    if kind == "understanding":
        service, *_ = build()
        service.authorization = GrantAdministrationDraftAuthorization(
            NS(authorization=current), NS()
        )
        service.repository.get = lookup

        def read(actor):
            return service.read_usage(actor, identity)
    else:
        service = object.__new__(PlanningSuggestionService)
        service.application = NS(
            authority=PlanningCurrentAuthority(ctx, current), scope=lambda actor: actor
        )
        service.invocations = NS(receipt=lookup)

        def read(actor):
            return service.read_usage(
                NS(
                    principal_id=actor.principal_id,
                    tenant_id=actor.scope.tenant_id,
                    security_domain=actor.scope.security_domain,
                ),
                identity,
            )

    for count in (0, 1):
        current.allowed = {
            (ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain, *g)
            for g in grants(kind, identity)[:count]
        }
        with pytest.raises((AuthorityError, ValueError)):
            read(ctx)
        assert lookups == []
    current.allowed = {
        (ctx.principal_id, ctx.scope.tenant_id, ctx.scope.security_domain, *g)
        for g in grants(kind, identity)
    }
    for actor in (
        context("other-actor"),
        replace(ctx, scope=AuthorityScope("other-tenant", "quality")),
    ):
        with pytest.raises((AuthorityError, ValueError)):
            read(actor)
        assert lookups == []
    with pytest.raises((AuthorityError, ValueError)):
        read(ctx)  # exact-granted but absent uses the same minimum-disclosure failure
    assert len(lookups) == 1


def test_formal_planning_usage_route_does_not_inherit_plan_read(formal):
    client = formal.start()
    result = send(client)
    identity = result.json()["result"]["invocation"]["target"]["invocation_id"]
    path = f"/api/workbench/v1/planning-v2/invocations/{identity}/usage"
    allowed = client.get(path)
    assert allowed.status_code == 200
    assert allowed.json()["result"]["pricing"]["price_version_digest"]
    formal.denied = True
    denied = client.get(path)
    absent = client.get(path.replace(identity, "absent"))
    assert denied.status_code == absent.status_code == 404
    assert denied.json() == absent.json() == {"reasonCode": "PROVIDER_USAGE_NOT_FOUND"}
    assert len(formal.calls) == 1


def test_demo_templates_fail_closed_without_fabricated_references():
    import json
    from pathlib import Path

    from agent_console.draft_assistance_bootstrap import _profile
    from agent_console.model_binding_resolution import ModelBindingResolutionFailure

    root = Path(__file__).parents[3] / "docs/exec-plans/active"
    for kind in ("UNDERSTANDING", "PLANNING"):
        document = json.loads(
            (root / f"S5-V023-ARCH-323-{kind}-RUNTIME.template.json").read_text()
        )
        assert document["credential"]["reference"] is None
        assert document["model"]["digest"] is None
        assert document.get("realCallsEnabled", False) is False
        with pytest.raises(
            ModelBindingResolutionFailure, match="MODEL_IDENTITY_REQUIRED"
        ):
            _profile(document, planning=kind == "PLANNING")


def test_cancel_race_rejects_stale_success_but_preserves_billable_measurement():
    from agent_console.draft_assistance import (
        DraftInvocationState,
        DraftResultKind,
        ObservationState,
        ProviderObservation,
    )

    service, *_ = build()
    original = service.begin(
        context(), key="cancel-race", content="[UNKNOWN] synthetic"
    )
    stale = original.invocation
    service._replace(stale, state=DraftInvocationState.CANCELLATION_REQUESTED)
    measurement = {"settleable": True, "local_request_id": stale.invocation_id}
    late = ProviderObservation(
        "late-metered",
        ObservationState.SUCCEEDED,
        result_kind=DraftResultKind.DRAFT_READY,
        title="late",
        description="must not display",
        measurement=measurement,
        input_tokens=12,
        output_tokens=3,
        local_cleanup={"reaped": True},
    )
    observed = service._record_observation(stale, late)
    assert observed.invocation.state is DraftInvocationState.CANCELLATION_REQUESTED
    assert observed.title is None
    assert observed.invocation.measurement == measurement
    assert observed.invocation.local_cleanup == {"reaped": True}


def test_legacy_invocation_without_usage_remains_explicitly_unmeasured():
    from agent_console.draft_assistance_postgres import _invocation, _record

    service, *_ = build()
    value = service.begin(
        context(), key="legacy", content="synthetic legacy"
    ).invocation
    legacy = _record(value)
    for key in ("measurement", "pricing", "settlementStatus", "localCleanup"):
        legacy.pop(key)
    recovered = _invocation(legacy)
    assert recovered.measurement is None
    assert recovered.pricing is None
    assert recovered.settlement_status == "NOT_MEASURED"
    assert recovered.local_cleanup is None
