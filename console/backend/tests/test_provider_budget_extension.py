"""Original PostgreSQL ledger, isolated random DB; no provider or runtime effects."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from agent_console.draft_assistance import (
    DraftAssistanceError,
    ObservationState,
    ProviderObservation,
)
from agent_console.draft_provider_budget_postgres import _digest
from agent_console.provider_budget_allowance import experience_limits
from agent_console.provider_budget_allowance import prepare as prepare_allowance
from agent_console.provider_budget_extension import (
    activate,
    deactivate,
    prepare,
    require,
)
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from test_draft_provider_budget_postgres import _invocation, _ledger
from test_provider_budget_allowance import QUOTE, document


@pytest.fixture(scope="module")
def database_url():
    url = os.environ.get("PLANNING323_TEST_DATABASE_URL")
    if not url:
        pytest.skip("disposable 53428 PostgreSQL required")
    values = conninfo_to_dict(url)
    assert values.get("host") == "127.0.0.1" and values.get("port") == "53428"
    name = "budget_extension_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(url, dbname=name)
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@pytest.fixture
def owner(database_url):
    owner = _ledger(
        database_url, "extension-" + uuid4().hex, call_cap=20, cost_cap=1_000_000
    )
    old = prepare_allowance(owner, document(owner, calls=100, cost=10_000_000))
    owner.allowance_id = old["allowanceId"]
    owner.extension_test_base = old
    try:
        yield owner
    finally:
        owner.close()


def extension(owner, bases=()):
    old = owner.extension_test_base
    return {
        "schemaVersion": "provider-budget-extension.v1",
        "extensionId": "extension:test",
        "namespace": old["namespace"],
        "securityDomain": old["securityDomain"],
        "ledgerId": old["ledgerId"],
        "allowanceId": old["allowanceId"],
        "allowanceDigest": _digest(old),
        "rootPolicyDigest": old["rootPolicyDigest"],
        "authorizationEvidenceDigest": "c" * 64,
        "predecessorExtensionId": None,
        "previousCallCap": 100,
        "previousCostCapMicrousd": 10_000_000,
        "additionalCalls": 100,
        "additionalCostMicrousd": 10_000_000,
        "callCap": 200,
        "totalCostCapMicrousd": 20_000_000,
        "notBefore": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "expiresAt": old["expiresAt"],
        "contextBases": list(bases),
        "externalWrites": False,
    }


def selected(owner, value):
    owner.budget_extension = {
        "schemaVersion": "provider-budget-extension-selection.v1",
        **{
            k: value[k]
            for k in (
                "namespace",
                "securityDomain",
                "ledgerId",
                "allowanceId",
                "extensionId",
                "authorizationEvidenceDigest",
            )
        },
        "extensionDigest": _digest(value),
    }


def enable(owner, bases=()):
    saved = prepare(owner, extension(owner, bases))
    selected(owner, saved)
    activate(owner, "activate:test")
    return saved


def test_same_ledger_93_91_pending_then_200_and_original_settlement(owner):
    old = []
    observation = ProviderObservation(
        "measured",
        ObservationState.FAILED,
        reason_code="PROVIDER_REFUSAL",
        input_tokens=10,
        output_tokens=10,
    )
    for n in range(93):
        identity = owner.reserve(str(n), _invocation(n), QUOTE)
        old.append(identity)
        if n < 91:
            owner.record_usage("settle:" + str(n), identity, observation)
    with owner._connection() as c:
        before = c.execute(
            "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
            (owner.ledger_id,),
        ).fetchone()
    saved = enable(owner)
    assert prepare(owner, saved) == saved
    assert activate(owner, "activate:test")["commandId"] == "activate:test"
    for n in range(93, 200):
        owner.reserve(str(n), _invocation(n), QUOTE)
    with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
        owner.reserve("201", _invocation(200), QUOTE)
    deactivate(owner, "d" * 64)
    with (
        pytest.raises(DraftAssistanceError, match="DEACTIVATED"),
        owner.dispatch_guard(_invocation(199), QUOTE),
    ):
        pytest.fail("must not dispatch")
    # An old pending reservation can settle at its original price despite deactivation.
    owner.record_usage("late91", old[91], observation)
    owner.record_usage("late91", old[91], observation)
    with owner._connection() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations "
                "WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()["n"]
            == 200
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements "
                "WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()["n"]
            == 92
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM "
                "draft_provider_budget.reservation_extension_basis "
                "WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()["n"]
            == 107
        )
        assert (
            c.execute(
                "SELECT record FROM draft_provider_budget.policies WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()
            == before
        )
        assert (
            c.execute(
                "SELECT record FROM draft_provider_budget.allowances "
                "WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()["record"]
            == owner.extension_test_base
        )
    # Dispatching old pending retains original allowance authorization, not newbasis.
    with owner.dispatch_guard(_invocation(92), QUOTE):
        pass


def test_exact_context_eligibility_not_numeric_cap_or_smaller_limits(owner):
    config = {
        "ledger_id": owner.ledger_id,
        "calls": 100,
        "cost_microusd": 10_000_000,
        "configuration_digest": "a" * 64,
    }
    row = {
        "tenant_id": owner.profile.scope.namespace,
        "security_domain": owner.profile.scope.security_domain,
        "subject_id": "human:test",
        "record": {
            "budget_allowance_id": owner.allowance_id,
            "authorization_digest": "b" * 64,
            "configuration": config,
        },
    }
    small = {**config, "calls": 40, "cost_microusd": 1000}
    bases = [
        {
            "subjectId": row["subject_id"],
            "authorizationDigest": "b" * 64,
            "configurationDigest": _digest(v),
        }
        for v in (config, small)
    ]
    enable(owner, bases)
    with owner._connection() as c:
        assert experience_limits(c, row, owner) == (200, 20_000_000)
        row["subject_id"] = "human:other"
        assert experience_limits(c, row, owner) == (100, 10_000_000)
        row["subject_id"] = "human:test"
        row["record"]["configuration"] = small
        assert experience_limits(c, row, owner) == (40, 1000)
        row["record"]["authorization_digest"] = "f" * 64
        with pytest.raises(Exception, match="ALLOWANCE_MISMATCH"):
            experience_limits(c, row, owner)


def test_prepare_not_active_fork_and_immutable(owner):
    saved = prepare(owner, extension(owner))
    with owner._connection() as c:
        assert require(c, owner) is None
    selected(owner, saved)
    with (
        owner._connection() as c,
        pytest.raises(DraftAssistanceError, match="NOT_ACTIVE"),
    ):
        require(c, owner)
    activate(owner, "one")
    fork = prepare(owner, {**saved, "extensionId": "fork"})
    selected(owner, fork)
    with pytest.raises(DraftAssistanceError, match="ACTIVATION_CONFLICT"):
        activate(owner, "two")
    with (
        owner._connection() as c,
        pytest.raises(psycopg.errors.RaiseException, match="IMMUTABLE"),
    ):
        c.execute(
            "DELETE FROM draft_provider_budget.extensions WHERE ledger_id=%s",
            (owner.ledger_id,),
        )


def test_concurrent_final_slot_has_one_winner(owner):
    enable(owner)
    for n in range(199):
        owner.reserve(str(n), _invocation(n), QUOTE)

    def attempt(n):
        try:
            owner.reserve(str(n), _invocation(n), QUOTE)
            return True
        except DraftAssistanceError as e:
            assert str(e) == "PROVIDER_BUDGET_EXHAUSTED"
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, [200, 201])) == [False, True]


def test_cost_cap_counts_old_pending_and_extension_expiry_does_not_settle_it(owner):
    import time

    from agent_console.draft_assistance import ProviderBudgetQuote

    quote = ProviderBudgetQuote(9_999_800, 100, 9_999_900)
    old = owner.reserve("old-expiry", _invocation(700), quote)
    saved = prepare(
        owner,
        {
            **extension(owner),
            "expiresAt": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
        },
    )
    selected(owner, saved)
    activate(owner, "short-extension")
    owner.reserve("new-expiry", _invocation(701), quote)
    with pytest.raises(DraftAssistanceError, match="EXHAUSTED"):
        owner.reserve(
            "over-money", _invocation(702), ProviderBudgetQuote(200, 100, 300)
        )
    time.sleep(1.05)
    with (
        pytest.raises(DraftAssistanceError, match="EXPIRED"),
        owner.dispatch_guard(_invocation(701), quote),
    ):
        pytest.fail("expired extension dispatched")
    owner.record_usage(
        "old-late",
        old,
        ProviderObservation(
            "original-final",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=10,
            output_tokens=10,
        ),
    )
    with owner._connection() as c:
        counts = c.execute(
            "SELECT count(*) n FROM draft_provider_budget.reservations "
            "WHERE ledger_id=%s",
            (owner.ledger_id,),
        ).fetchone()
        assert counts["n"] == 2
        assert (
            c.execute(
                "SELECT actual_cost_microusd FROM draft_provider_budget.settlements "
                "WHERE ledger_id=%s AND reservation_id=%s",
                (owner.ledger_id, old),
            ).fetchone()["actual_cost_microusd"]
            == 20
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("allowanceDigest", "0" * 64),
        ("rootPolicyDigest", "0" * 64),
        ("ledgerId", "other-ledger"),
        ("namespace", "other-scope"),
    ],
)
def test_wrong_parent_or_scope_never_appends_candidate(owner, field, value):
    with pytest.raises(DraftAssistanceError, match="PARENT_MISMATCH"):
        prepare(owner, {**extension(owner), field: value})
    with owner._connection() as c:
        # Failed preparation rolls back even initial migration, never grants scope.
        if c.execute(
            "SELECT to_regclass('draft_provider_budget.extensions') t"
        ).fetchone()["t"]:
            assert not c.execute(
                "SELECT 1 FROM draft_provider_budget.extensions WHERE ledger_id=%s",
                (owner.ledger_id,),
            ).fetchone()


def test_old_pending_original_price_survives_mixed_profile_extension(owner):
    from dataclasses import replace
    from types import SimpleNamespace

    from agent_console.draft_assistance import ProviderBudgetQuote
    from agent_console.draft_provider_budget_postgres import PostgresProviderCallBudget
    from agent_console.provider_profile_pricing import prepare_revision

    old_id = owner.reserve("native-pending", _invocation(800), QUOTE)
    newer = PostgresProviderCallBudget(
        owner.pool.conninfo,
        migration_path=owner.migration_path,
        profile=replace(
            owner.profile, profile_revision_id="new-profile", profile_digest="d" * 64
        ),
        ledger_id=owner.ledger_id,
        call_cap=owner.call_cap,
        total_cost_cap_microusd=owner.total_cost_cap_microusd,
        input_price_microusd_per_million_tokens=2_000_000,
        output_price_microusd_per_million_tokens=3_000_000,
        allowance_id=owner.allowance_id,
        profile_pricing_root_digest=owner.extension_test_base["rootPolicyDigest"],
    )
    try:
        with newer._connection() as c:
            prepare_revision(c, newer)
        newer.migrate_and_configure()
        enable(owner)
        newer.budget_extension = owner.budget_extension
        invocation = SimpleNamespace(
            scope=newer.profile.scope,
            profile_revision_id=newer.profile.profile_revision_id,
            invocation_id="new-priced",
        )
        new_id = newer.reserve(
            "new-priced", invocation, ProviderBudgetQuote(10, 100, 320)
        )
        deactivate(owner, "d" * 64)
        observation = ProviderObservation(
            "measured-late",
            ObservationState.FAILED,
            reason_code="PROVIDER_REFUSAL",
            input_tokens=10,
            output_tokens=10,
        )
        with pytest.raises(DraftAssistanceError, match="RESERVATION_PROFILE_MISMATCH"):
            newer.record_usage("wrong-old-price", old_id, observation)
        # NativeLoopRuntime uses these exact original metering/settlement functions.
        from agent_console.plan_suggestion_runtime import PlanningBudget
        from agent_console.planning_measurement import measurement, settle

        measured = measurement(
            {
                "id": "response-old",
                "model": "test-model",
                "status": "completed",
                "usage": {"input_tokens": 10, "output_tokens": 10, "total_tokens": 20},
            },
            "request-old",
            "old-native-late",
            10,
            SimpleNamespace(
                native_model_id="test-model",
                maximum_input_tokens=50,
                maximum_output_tokens=100,
            ),
        )
        receipt = {"reservation_id": old_id, "measurement": measured}
        assert measured["settleable"]
        first = settle(PlanningBudget(owner), "old-native-late", receipt)
        assert settle(PlanningBudget(owner), "old-native-late", receipt) == first
        assert settle(
            PlanningBudget(owner),
            "no-proof",
            {"reservation_id": old_id, "measurement": {"settleable": False}},
        )["reservation_retained"]
        newer.record_usage("new-late", new_id, observation)
        assert owner.read_settlement(old_id)["estimate_microusd"] == 20
        assert newer.read_settlement(new_id)["estimate_microusd"] == 50
        with owner._connection() as c:
            assert (
                c.execute(
                    "SELECT count(*) n FROM draft_provider_budget.reservations "
                    "WHERE ledger_id=%s",
                    (owner.ledger_id,),
                ).fetchone()["n"]
                == 2
            )
    finally:
        newer.close()


def test_separate_pin_preserves_configured_limits_and_requires_active_binding(
    owner, tmp_path
):
    import json

    from agent_console.provider_budget_extension import configure_from_environment
    from agent_console.task_delegation import configured_limits
    from test_task_timeout_revision import Configuration

    configuration = Configuration(30, 60, 65536, 500)
    before = configured_limits(owner.profile, configuration, owner)
    configure_from_environment(owner, {})
    enable(owner)
    path = tmp_path / "selection.json"
    path.write_text(json.dumps(owner.budget_extension))
    path.chmod(0o600)
    owner.budget_extension = None
    configure_from_environment(owner, {"PROVIDER_BUDGET_EXTENSION_POLICY": str(path)})
    assert configured_limits(owner.profile, configuration, owner) == before
    selection = json.loads(path.read_text())
    path.write_text(json.dumps({**selection, "extensionDigest": "0" * 64}))
    with pytest.raises(DraftAssistanceError, match="BINDING_MISMATCH"):
        configure_from_environment(
            owner, {"PROVIDER_BUDGET_EXTENSION_POLICY": str(path)}
        )


@pytest.mark.parametrize(
    "case",
    [
        "test_old_unknown_counts_and_concurrent_new_calls_share_original_lock",
        "test_money_cap_retains_previous_unsettled_cost",
        "test_expired_allowance_blocks_reserve_and_dispatch_without_replay",
        "test_immutable_idempotent_allowance_survives_reopen",
        "test_scope_conflict_and_missing_allowance_fail_closed",
        "test_allowance_does_not_override_narrower_context_limits",
        "test_conversation_allowance_binding_and_expiry",
        "test_runtime_configuration_uses_selected_caps_without_rewriting_root",
    ],
)
def test_original_v1_owner_regression_in_private_random_database(
    database_url, monkeypatch, case
):
    import inspect

    import test_provider_budget_allowance as original

    function = getattr(original, case)
    kwargs = {"database_url": database_url}
    if "monkeypatch" in inspect.signature(function).parameters:
        kwargs["monkeypatch"] = monkeypatch
    function(**kwargs)
