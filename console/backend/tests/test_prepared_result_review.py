# ruff: noqa: E501, F811 -- Explicit fixture SQL; isolated database fixture import.
"""Result owner PostgreSQL tests; synthetic facts never count as real acceptance."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from agent_console.execution_preparation import ExecutionPreparationError, ProgressEvent
from agent_console.prepared_execution_application import PreparedExecutionApplication
from agent_console.prepared_result_review import PreparedResultReview, migrate
from prepared_execution_support import ExactTestAuthority, seed
from psycopg.rows import dict_row
from test_execution_preparation import preparation
from test_plan_suggestion_v2 import repository  # noqa: F401


class ReviewAuthority:
    def __init__(self):
        self.denied = None

    def require(self, principal, owner, action, resource):
        if owner == self.denied:
            raise PermissionError("TEST_REVIEW_DENIED")
        return SimpleNamespace(decision_id="test-exact-review-authority")


def seed_criteria(repo, p):
    target = p.semantics.target
    digest = hashlib.sha256(b"fixture").hexdigest()
    key = p.namespace, p.security_domain
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        c.execute(
            (
                Path(__file__).parents[1]
                / "migrations/0013_business_problem_authority.sql"
            ).read_text()
        )
        migrate(c)
        migrate(c)
        c.execute(
            "INSERT INTO business_problem_authority.problems VALUES (%s,%s,%s,'test-human','ACTIVE',1,%s,'test-human',now(),now())",
            (*key, target.problem.resource_id, target.problem.revision_id),
        )
        c.execute(
            "INSERT INTO business_problem_authority.problem_revisions VALUES (%s,%s,%s,%s,1,NULL,%s,%s,'fixture','fixture','test-human','test-human',now())",
            (
                *key,
                target.problem.resource_id,
                target.problem.revision_id,
                digest,
                b"fixture",
            ),
        )
        c.execute(
            "INSERT INTO business_problem_authority.criteria_sets VALUES (%s,%s,%s,%s,%s,1,NULL,%s,%s,'test-human',now())",
            (
                *key,
                target.criteria.revision_id,
                target.problem.resource_id,
                target.problem.revision_id,
                digest,
                b"fixture",
            ),
        )
        for i, revision in enumerate(target.criterion_revision_ids, 1):
            c.execute(
                "INSERT INTO business_problem_authority.criteria VALUES (%s,%s,%s,1,%s)",
                (*key, revision, revision),
            )
            c.execute(
                "INSERT INTO business_problem_authority.criterion_revisions VALUES (%s,%s,%s,%s,1,NULL,'HUMAN_EVALUATED','{}','[]','HUMAN','v1','{}',%s,%s,'test-human',now())",
                (*key, revision, revision, digest, b"fixture"),
            )
            c.execute(
                "INSERT INTO business_problem_authority.criteria_set_members VALUES (%s,%s,%s,%s,%s)",
                (*key, target.criteria.revision_id, i, revision),
            )


def setup_case(repo):
    digest = hashlib.sha256(b"fixture").hexdigest()
    target = preparation().semantics.target
    target = target.model_copy(
        update={
            "problem": target.problem.model_copy(update={"digest": digest}),
            "criteria": target.criteria.model_copy(update={"digest": digest}),
        }
    )
    p = seed(repo, target=target)
    seed_criteria(repo, p)
    principal = SimpleNamespace(
        principal_id="human:test-reviewer",
        tenant_id=p.namespace,
        security_domain=p.security_domain,
    )
    with repo.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        app = PreparedExecutionApplication(c, principal, ExactTestAuthority(p))
        app.start(p, "test-start")
    return p, principal


def terminal_failure(c, p, principal):
    app = PreparedExecutionApplication(c, principal, ExactTestAuthority(p))
    identity = app.queue_attempt(p, "t1-read")
    state = app.store.read(p.namespace, p.security_domain, p.run_id)[1]
    state = app.store.apply(
        p.namespace,
        p.security_domain,
        p.run_id,
        ProgressEvent(
            action="FAILED",
            task_id="t1-read",
            attempt_id=str(identity.attempt.attempt_id),
            evidence_id="test-observed-failure",
        ),
        expected_version=state.version,
    )
    app.store.apply(
        p.namespace,
        p.security_domain,
        p.run_id,
        ProgressEvent(
            action="FINALIZE_FAILURE",
            task_id="t1-read",
            evidence_id="test-decline-retry",
        ),
        expected_version=state.version,
    )


def test_terminal_snapshot_human_successor_replay_and_restart(repository):
    p, principal = setup_case(repository)
    auth = ReviewAuthority()
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        review = PreparedResultReview(c, principal, auth)
        with pytest.raises(ExecutionPreparationError, match="TERMINAL_RUN_REQUIRED"):
            review.evaluate(p, "before-terminal")
        terminal_failure(c, p, principal)
        result = review.evaluate(p, "evaluation")
        assert result["businessResolution"] == "UNDETERMINED"
        assert {r["result"] for r in result["evaluation"]["results"]} == {"UNKNOWN"}
        assert review.evaluate(p, "evaluation") == result
        args = dict(
            evaluation_id=result["evaluation"]["evaluationId"],
            evaluation_digest=result["evaluationDigest"],
            expected_version=1,
            reason="测试人工核对: 合成执行不能证明真实业务解决",
            command_key="human",
        )
        with pytest.raises(ExecutionPreparationError, match="NOT_BUSINESS_PROOF"):
            review.confirm(p, decision="CONFIRM_PROBLEM_SOLVED", **args)
        confirmed = review.confirm(p, decision="ACKNOWLEDGE_UNDETERMINED", **args)
        assert confirmed["version"] == 2
        assert confirmed["predecessorId"] == result["outcomeId"]
        assert (
            review.confirm(p, decision="ACKNOWLEDGE_UNDETERMINED", **args) == confirmed
        )
        with pytest.raises(ExecutionPreparationError, match="REPLAY_CONFLICT"):
            review.confirm(p, decision="DISAGREE", **args)
    with repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        review = PreparedResultReview(c, principal, auth)
        assert review.evaluate(p, "read-after-restart") == confirmed
        assert review.evaluate(p, "evaluation") == result  # exact old command replay
        assert (
            c.execute(
                "SELECT count(*) AS n FROM human_governance.confirmations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) AS n FROM success_criteria_evaluation.results"
            ).fetchone()["n"]
            == 2
        )
        assert (
            c.execute(
                "SELECT current_state FROM business_problem_authority.problems"
            ).fetchone()["current_state"]
            == "ACTIVE"
        )
        auth.denied = "SUCCESS_CRITERION"
        with pytest.raises(PermissionError, match="REVIEW_DENIED"):
            review.evaluate(p, "denied")
