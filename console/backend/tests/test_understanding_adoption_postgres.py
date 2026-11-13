"""Isolated owner transaction races; model/authorization observations are fixtures."""

# ruff: noqa: F401,F811 -- Reuse isolated database and controlled result fixtures.
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.draft_assistance_postgres import PostgresDraftAssistanceRepository
from agent_console.understanding_adoption_postgres import adopt, migrate
from test_context_call_admission import pytestmark
from test_draft_assistance import context
from test_local_accounts_postgres import setup
from test_understanding_result_adoption import case


@pytest.fixture
def owner(setup, case):
    repo, *_ = setup
    migrations = Path(__file__).parents[1] / "migrations"
    with repo.connection_scope() as c:
        c.execute((migrations / "0023_draft_assistance.sql").read_text())
    owner = PostgresDraftAssistanceRepository(
        repo.pool.conninfo, migration_path=migrations / "0023_draft_assistance.sql"
    )
    migrate(owner)
    owner.claim(case["original"])
    owner.claim(case["result"])
    try:
        yield owner
    finally:
        owner.close()


def verify(case):
    fields = (
        "current_snapshot",
        "retained_source",
        "expected_profile_revision",
        "settled_invocations",
        "now",
    )
    return lambda *_: {k: case[k] for k in fields}


def save(owner, case, key="same"):
    with owner.connection_scope() as c:
        return adopt(
            c,
            context(),
            case["target"],
            case["result"].invocation_id,
            key,
            verify(case),
        )


def count(owner):
    with owner.connection_scope() as c:
        return c.execute(
            "SELECT count(*) n FROM draft_assistance.result_adoptions"
        ).fetchone()["n"]


def test_exact_replay_keeps_real_result_and_original_head(owner, case):
    first = save(owner, case)
    assert save(owner, case) == first
    assert count(owner) == 1
    assert (
        owner.get_context_head(case["original"].scope, case["original"].context_id)
        == case["original"]
    )
    assert (
        owner.get(case["result"].scope, case["result"].invocation_id) == case["result"]
    )
    with pytest.raises(DraftAssistanceError, match="CONFLICT"):
        save(owner, case, "different-key")


def test_rollback_leaves_no_partial_adoption(owner, case):
    with (
        pytest.raises(RuntimeError, match="forced rollback"),
        owner.connection_scope() as c,
    ):
        adopt(
            c,
            context(),
            case["target"],
            case["result"].invocation_id,
            "rollback",
            verify(case),
        )
        raise RuntimeError("forced rollback")
    assert count(owner) == 0
    assert (
        save(owner, case)["actualResult"]["invocationId"]
        == case["result"].invocation_id
    )


def normal_child(case):
    return replace(
        case["result"],
        context_id=case["original"].context_id,
        invocation_id="ordinary-child",
        turn_id="ordinary-turn",
        scoped_idempotency_key="ordinary-key",
        turn_ordinal=2,
        turn_version=2,
        parent_turn_id=case["original"].turn_id,
        predecessor_invocation_id=case["original"].invocation_id,
    )


def test_adoption_blocks_later_ordinary_claim_without_new_invocation(owner, case):
    save(owner, case)
    with pytest.raises(DraftAssistanceError, match="PARENT_ALREADY_CONSUMED"):
        owner.claim(normal_child(case))
    assert owner.get(case["original"].scope, "ordinary-child") is None
    assert count(owner) == 1


def test_ordinary_claim_first_blocks_stale_adoption(owner, case):
    owner.claim(normal_child(case))
    with pytest.raises(DraftAssistanceError, match="ORIGINAL_HEAD_CHANGED"):
        save(owner, case)
    assert count(owner) == 0


def test_concurrent_alternative_keys_consume_question_once(owner, case):
    barrier = Barrier(2)

    def attempt(key):
        barrier.wait(timeout=10)
        try:
            return save(owner, case, key)
        except DraftAssistanceError as error:
            return error.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["first", "second"]))
    assert sum(isinstance(x, dict) for x in outcomes) == 1
    assert outcomes.count("UNDERSTANDING_ADOPTION_CONFLICT") == 1
    assert count(owner) == 1


def test_read_chain_returns_exact_reference_and_checks_current_owner(owner, case):
    from agent_console.understanding_adoption_postgres import read_chain

    saved = save(owner, case)
    observed = []
    with owner.connection_scope() as c:
        chain = read_chain(
            c,
            context(),
            case["result"].invocation_id,
            lambda _, actor, old, current: observed.append(
                (actor.principal_id, old.invocation_id, current.invocation_id)
            ),
        )
    assert chain == (saved,)
    assert observed == [
        (
            context().principal_id,
            case["original"].invocation_id,
            case["result"].invocation_id,
        )
    ]


def test_read_chain_denied_or_changed_result_cannot_be_used(owner, case):
    from agent_console.draft_assistance import DraftInvocationState
    from agent_console.understanding_adoption_postgres import read_chain

    save(owner, case)

    def deny(*_):
        raise DraftAssistanceError("DENIED_BY_CURRENT_OWNER")

    with (
        owner.connection_scope() as c,
        pytest.raises(DraftAssistanceError, match="DENIED_BY_CURRENT_OWNER"),
    ):
        read_chain(c, context(), case["result"].invocation_id, deny)
    result = case["result"]
    owner.compare_and_set(
        result.aggregate_version,
        replace(
            result,
            aggregate_version=result.aggregate_version + 1,
            state=DraftInvocationState.CONFLICT_REVIEW_REQUIRED,
        ),
    )
    with (
        owner.connection_scope() as c,
        pytest.raises(DraftAssistanceError, match="REFERENCE_CHANGED"),
    ):
        read_chain(c, context(), result.invocation_id, lambda *_: None)


def test_ordinary_claim_and_adoption_race_cannot_both_consume_parent(owner, case):
    barrier = Barrier(2)

    def compete(kind):
        barrier.wait(timeout=10)
        try:
            if kind == "adopt":
                save(owner, case)
            else:
                owner.claim(normal_child(case))
            return kind
        except DraftAssistanceError as error:
            return error.reason_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(compete, ["adopt", "ordinary"]))
    assert sum(x in {"adopt", "ordinary"} for x in outcomes) == 1
    if "adopt" in outcomes:
        assert "UNDERSTANDING_ADOPTION_PARENT_ALREADY_CONSUMED" in outcomes
        assert owner.get(case["original"].scope, "ordinary-child") is None
    else:
        assert "UNDERSTANDING_ADOPTION_ORIGINAL_HEAD_CHANGED" in outcomes
        assert count(owner) == 0


def test_extension_migration_is_idempotent_and_old_adapter_remains_compatible(owner):
    migrate(owner)
    owner.migrate()
    with owner.connection_scope() as c:
        assert c.execute(
            "SELECT version FROM draft_assistance.schema_migrations"
        ).fetchall() == [{"version": 23}]
        assert c.execute(
            "SELECT version FROM draft_assistance.adoption_schema_migrations"
        ).fetchall() == [{"version": 65}]
