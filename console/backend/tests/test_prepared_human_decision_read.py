"""Real immutable owner facts; controlled read denials/corruption, never row edits."""

# ruff: noqa: F401,F811,RUF001 -- fixture registration
import copy
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.prepared_human_decision_read import read_human_decision
from agent_console.prepared_result_review import PreparedResultReview
from agent_console.workbench_prepared_execution import PreparedExecutionOwner
from psycopg.rows import dict_row
from test_plan_suggestion_v2 import repository
from test_prepared_result_review import ReviewAuthority, setup_case, terminal_failure


class Reads:
    def __init__(self):
        self.denied = False
        self.calls = []

    def require(self, principal, owner, action, target):
        self.calls.append((owner, action, target))
        if self.denied:
            raise AuthorityError("AUTHORIZATION_REVOKED")


@pytest.mark.parametrize("decision", ["ACKNOWLEDGE_UNDETERMINED", "DISAGREE"])
def test_original_confirmation_read_exact_and_no_mutation(repository, decision):
    p, principal = setup_case(repository)
    reads = Reads()
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        owner = PreparedResultReview(c, principal, ReviewAuthority())
        terminal_failure(c, p, principal)
        evaluated = owner.evaluate(p, "evaluation")
        assert read_human_decision(c, principal, reads, p, evaluated) == {
            "status": "NOT_RECORDED"
        }
        outcome = owner.confirm(
            p,
            evaluation_id=evaluated["evaluation"]["evaluationId"],
            evaluation_digest=evaluated["evaluationDigest"],
            expected_version=1,
            decision=decision,
            reason="保留原评价，不代表交付接受",
            command_key="original",
        )

        def facts():
            return [
                c.execute(
                    "SELECT record FROM " + table + " ORDER BY record::text"
                ).fetchall()
                for table in [
                    "human_governance.confirmations",
                    "success_criteria_evaluation.results",
                    "product_outcome.outcomes",
                ]
            ]

        before = facts()
        projection = PreparedExecutionOwner.read(
            SimpleNamespace(connection=c, authority=ReviewAuthority()),
            SimpleNamespace(principal=principal, validate=lambda _: None),
            p,
        )
        assert projection["humanReview"]["status"] == "READABLE"
        assert projection["humanReview"]["decision"]["decision"] == decision
        assert projection["outcome"] == outcome
        value = read_human_decision(c, principal, reads, p, outcome)
        assert value["status"] == "READABLE"
        assert value["decision"]["decision"] == decision
        assert value["decision"]["actorId"] == principal.principal_id
        assert outcome["businessResolution"] != "CONFIRMED_SOLVED"
        assert read_human_decision(c, principal, reads, p, outcome) == value
        reads.denied = True
        assert read_human_decision(c, principal, reads, p, outcome) == {
            "status": "UNAVAILABLE"
        }
        reads.denied = False

        # Tamper only read results. Original immutable audit rows remain untouched.
        class ReadView:
            def __init__(self, change):
                self.change = change

            def execute(self, sql, params):
                row = copy.deepcopy(c.execute(sql, params).fetchone())
                return SimpleNamespace(fetchone=lambda: self.change(row))

        for field in [
            "digest",
            "actor_id",
            "namespace",
            "security_domain",
            "evaluation_digest",
            "snapshot_digest",
            "evaluated_predecessor",
            "outcome_predecessor",
            "outcome_resolution",
            "evaluated_snapshot",
            "successor_run",
            "successor_id",
            "successor_snapshot",
            "successor_predecessor",
        ]:

            def change(row, field=field):
                row[field] = "wrong"
                return row

            assert read_human_decision(
                ReadView(change), principal, reads, p, outcome
            ) == {"status": "UNAVAILABLE"}
        assert read_human_decision(
            ReadView(lambda _: None), principal, reads, p, outcome
        ) == {"status": "UNAVAILABLE"}
        assert facts() == before
        assert set(reads.calls) == {
            ("HUMAN_CONFIRMATION", "READ", "human-confirmation:prepared:" + p.digest)
        }
