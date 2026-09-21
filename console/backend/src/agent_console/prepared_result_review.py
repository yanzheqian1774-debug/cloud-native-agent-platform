# ruff: noqa: E501 -- Exact scoped SQL statements.
"""ARCH-264 bounded evaluation and Human result decision for synthetic prepared Runs."""

import hashlib
import json
from pathlib import Path

from psycopg.types.json import Jsonb

from .business_problem_authorization import (
    criteria_resource,
    criterion_revision_resource,
    problem_resource,
)
from .execution_preparation import ExecutionPreparationError
from .execution_preparation_postgres import PreparedExecutionStore
from .resource_use_domain import canonical_digest, stable_id

EVALUATOR = "prepared-synthetic-evidence.v1"


def migrate(connection):
    path = Path(__file__).parents[2] / "migrations/0035_prepared_result_review.sql"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    connection.execute("SELECT pg_advisory_xact_lock(3240035)")
    present = connection.execute(
        "SELECT to_regclass('success_criteria_evaluation.schema_migrations') AS t"
    ).fetchone()["t"]
    if present:
        if connection.execute(
            "SELECT version,checksum FROM success_criteria_evaluation.schema_migrations"
        ).fetchall() != [{"version": 35, "checksum": digest}]:
            raise ExecutionPreparationError("RESULT_REVIEW_SCHEMA_INCOMPATIBLE")
        return
    connection.execute(path.read_text())
    connection.execute(
        "INSERT INTO success_criteria_evaluation.schema_migrations VALUES (35,%s)",
        (digest,),
    )


class PreparedResultReview:
    def __init__(self, connection, principal, authority):
        self.connection, self.principal, self.authority = (
            connection,
            principal,
            authority,
        )

    def require(self, owner, action, reference):
        return self.authority.require(self.principal, owner, action, reference)

    def snapshot(self, p):
        self.require("EXECUTION", "READ", "governed-execution:prepared:" + p.digest)
        target = p.semantics.target
        self.require(
            "BUSINESS_PROBLEM", "READ", problem_resource(target.problem.resource_id)
        )
        self.require(
            "SUCCESS_CRITERIA_SET",
            "READ",
            criteria_resource(target.problem.resource_id),
        )
        key = (p.namespace, p.security_domain)
        stored, progress = PreparedExecutionStore(self.connection).read(
            *key, p.run_id, lock=True
        )
        if stored != p or progress.state not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            raise ExecutionPreparationError("EVALUATION_TERMINAL_RUN_REQUIRED")
        criteria = self.connection.execute(
            "SELECT digest,canonical_bytes,problem_revision_id FROM "
            "business_problem_authority.criteria_sets "
            "WHERE namespace=%s AND security_domain=%s AND set_revision_id=%s AND business_problem_id=%s",
            (*key, target.criteria.revision_id, target.problem.resource_id),
        ).fetchone()
        if (
            criteria is None
            or criteria["digest"] != target.criteria.digest
            or criteria["problem_revision_id"] != target.problem.revision_id
            or hashlib.sha256(bytes(criteria["canonical_bytes"])).hexdigest()
            != target.criteria.digest
        ):
            raise ExecutionPreparationError("EVALUATION_CRITERIA_BINDING_MISMATCH")
        problem = self.connection.execute(
            "SELECT digest,canonical_bytes FROM business_problem_authority.problem_revisions "
            "WHERE namespace=%s AND security_domain=%s AND business_problem_id=%s AND revision_id=%s",
            (*key, target.problem.resource_id, target.problem.revision_id),
        ).fetchone()
        if (
            problem is None
            or problem["digest"] != target.problem.digest
            or hashlib.sha256(bytes(problem["canonical_bytes"])).hexdigest()
            != target.problem.digest
        ):
            raise ExecutionPreparationError("EVALUATION_PROBLEM_BINDING_MISMATCH")
        for revision_id in target.criterion_revision_ids:
            self.require(
                "SUCCESS_CRITERION", "READ", criterion_revision_resource(revision_id)
            )
        members = self.connection.execute(
            "SELECT r.* FROM business_problem_authority.criteria_set_members m "
            "JOIN business_problem_authority.criterion_revisions r "
            "ON r.namespace=m.namespace AND r.security_domain=m.security_domain AND "
            "r.revision_id=m.criterion_revision_id "
            "WHERE m.namespace=%s AND m.security_domain=%s AND m.set_revision_id=%s ORDER BY m.ordinal",
            (*key, target.criteria.revision_id),
        ).fetchall()
        if tuple(r["revision_id"] for r in members) != target.criterion_revision_ids:
            raise ExecutionPreparationError("EVALUATION_CRITERION_SET_MISMATCH")
        criterion_records = []
        for item in members:
            if (
                hashlib.sha256(bytes(item["canonical_bytes"])).hexdigest()
                != item["digest"]
            ):
                raise ExecutionPreparationError("EVALUATION_CRITERION_CORRUPT")
            criterion_records.append(
                {
                    k: item[k]
                    for k in (
                        "success_criterion_id",
                        "revision_id",
                        "digest",
                        "criterion_type",
                        "measurement",
                        "required_evidence_kinds",
                        "evaluator_type",
                        "evaluator_version",
                        "applicability",
                    )
                }
            )
        from .prepared_skill_invocation import planned_outputs

        authorized_outputs = planned_outputs(p, progress)
        for output in authorized_outputs:
            self.require("EVIDENCE", "READ_REFERENCE", output["evidenceGrant"])
            self.require("RESOURCE_USE", "READ", output["resourceGrant"])
        artifact_ids = {o["artifactId"] for o in authorized_outputs}
        resource_use_ids = {o["resourceUseId"] for o in authorized_outputs}
        artifacts = self.connection.execute(
            "SELECT artifact_id,task_id,attempt_id,record,digest,content FROM "
            "execution_authority.run_artifacts "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY artifact_id",
            (*key, p.run_id),
        ).fetchall()
        evidence = []
        for a in artifacts:
            if a["artifact_id"] not in artifact_ids:
                raise ExecutionPreparationError("EVALUATION_ARTIFACT_NOT_AUTHORIZED")
            if hashlib.sha256(a["content"].encode()).hexdigest() != a["digest"]:
                raise ExecutionPreparationError("EVALUATION_ARTIFACT_CORRUPT")
            evidence.append(
                {k: a[k] for k in ("artifact_id", "task_id", "attempt_id", "digest")}
            )
        uses = self.connection.execute(
            "SELECT DISTINCT ON (u.resource_use_id) "
            "u.resource_use_id,s.snapshot_id,s.digest,s.high_water,s.record "
            "FROM resource_use.uses u JOIN resource_use.snapshots s "
            "USING(namespace,security_domain,resource_use_id) "
            "WHERE u.namespace=%s AND u.security_domain=%s AND u.workflow_run_id=%s "
            "ORDER BY u.resource_use_id,s.high_water DESC",
            (*key, p.run_id),
        ).fetchall()
        for use in uses:
            if use["resource_use_id"] not in resource_use_ids:
                raise ExecutionPreparationError(
                    "EVALUATION_RESOURCE_USE_NOT_AUTHORIZED"
                )
            record = use["record"]
            payload = {
                camel: record[snake]
                for camel, snake in (
                    ("resourceUseId", "resource_use_id"),
                    ("highWater", "high_water"),
                    ("reducerVersion", "reducer_version"),
                    ("effectiveState", "effective_state"),
                    ("factIds", "fact_ids"),
                    ("measurementIds", "measurement_ids"),
                    ("evidenceReferences", "evidence_references"),
                    ("limitationCodes", "limitation_codes"),
                    ("conflicts", "conflicts"),
                )
            }
            if (
                canonical_digest(payload) != use["digest"]
                or record["digest"] != use["digest"]
            ):
                raise ExecutionPreparationError("EVALUATION_RESOURCE_SNAPSHOT_CORRUPT")
            if record.get("effective_state") in {
                "OUTCOME_UNKNOWN",
                "CONFLICTED",
            }:
                raise ExecutionPreparationError("EVALUATION_RESOURCE_USE_AMBIGUOUS")
        events = self.connection.execute(
            "SELECT max(version) AS high_water FROM "
            "execution_authority.prepared_run_events "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
            (*key, p.run_id),
        ).fetchone()["high_water"]
        return {
            "schemaVersion": "prepared-terminal-snapshot.v1",
            "runId": p.run_id,
            "preparationDigest": p.digest,
            "plan": {
                "id": p.plan_id,
                "version": p.plan_version,
                "digest": p.plan_digest,
                "approvalId": p.approval_id,
            },
            "problem": target.problem.model_dump(mode="json"),
            "criteriaSet": target.criteria.model_dump(mode="json"),
            "criteria": criterion_records,
            "runState": progress.state,
            "runVersion": progress.version,
            "eventHighWater": events,
            "artifacts": evidence,
            "resourceUseSnapshots": uses,
            "limitations": ["SYNTHETIC_ONLY", "REAL_BUSINESS_OUTCOME_UNPROVEN"]
            + ([] if uses else ["RESOURCE_USE_SNAPSHOT_MISSING"]),
        }

    def evaluate(self, p, command_key):
        self.require("EVALUATION", "EVALUATE", "evaluation:prepared:" + p.digest)
        snapshot = self.snapshot(p)
        digest = canonical_digest(snapshot)
        snapshot_id = stable_id("terminal-snapshot", p.run_id, digest)
        evaluation_id = stable_id("criteria-evaluation", snapshot_id, EVALUATOR)
        key = (p.namespace, p.security_domain)
        existing = self.connection.execute(
            "SELECT record FROM product_outcome.outcomes WHERE namespace=%s AND security_domain=%s AND evaluation_id=%s",
            (*key, evaluation_id),
        ).fetchone()
        command_digest = canonical_digest({"action": "EVALUATE", "snapshot": digest})
        replay = self.command_replay(p, command_key, command_digest)
        if replay:
            return replay
        if existing:
            result = self.connection.execute(
                "SELECT o.record FROM product_outcome.heads h JOIN product_outcome.outcomes o "
                "USING(namespace,security_domain,outcome_id) WHERE h.namespace=%s "
                "AND h.security_domain=%s AND h.workflow_run_id=%s",
                (*key, p.run_id),
            ).fetchone()["record"]
        else:
            # No model self-report can satisfy the exact Human-evaluated original rubric.
            results = [
                {
                    "criterionRevisionId": c["revision_id"],
                    "criterionDigest": c["digest"],
                    "result": "NOT_MEASURABLE"
                    if c["criterion_type"] == "NOT_MEASURABLE"
                    else "UNKNOWN",
                    "reason": "DECLARED_NOT_MEASURABLE"
                    if c["criterion_type"] == "NOT_MEASURABLE"
                    else "HUMAN_REVIEW_REQUIRED"
                    if c["criterion_type"] == "HUMAN_EVALUATED"
                    else "NO_EXACT_MEASUREMENT_EVIDENCE",
                    "artifactIds": [a["artifact_id"] for a in snapshot["artifacts"]],
                }
                for c in snapshot["criteria"]
            ]
            self.connection.execute(
                "INSERT INTO success_criteria_evaluation.snapshots "
                "(namespace,security_domain,snapshot_id,workflow_run_id,digest,record) VALUES (%s,%s,%s,%s,%s,%s)",
                (*key, snapshot_id, p.run_id, digest, Jsonb(snapshot)),
            )
            self.connection.execute(
                "INSERT INTO success_criteria_evaluation.jobs "
                "(namespace,security_domain,job_id,snapshot_id,evaluator_version,state) VALUES (%s,%s,%s,%s,%s,'COMPLETED')",
                (
                    *key,
                    stable_id("evaluation-job", snapshot_id, EVALUATOR),
                    snapshot_id,
                    EVALUATOR,
                ),
            )
            evaluation = {
                "evaluationId": evaluation_id,
                "snapshotId": snapshot_id,
                "snapshotDigest": digest,
                "evaluator": EVALUATOR,
                "results": results,
                "limitations": snapshot["limitations"],
            }
            self.connection.execute(
                "INSERT INTO success_criteria_evaluation.results "
                "(namespace,security_domain,evaluation_id,workflow_run_id,snapshot_id,digest,record) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    evaluation_id,
                    p.run_id,
                    snapshot_id,
                    canonical_digest(evaluation),
                    Jsonb(evaluation),
                ),
            )
            head = self.connection.execute(
                "SELECT outcome_id FROM product_outcome.heads WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (*key, p.run_id),
            ).fetchone()
            result = self.append_outcome(
                p,
                evaluation,
                None,
                head["outcome_id"] if head else None,
                "UNDETERMINED",
            )
        self.remember(p, command_key, command_digest, result["outcomeId"])
        return result

    def command_replay(self, p, key, digest):
        if not key or len(key) > 200:
            raise ExecutionPreparationError("RESULT_COMMAND_KEY_INVALID")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                json.dumps(
                    [p.namespace, p.security_domain, self.principal.principal_id, key]
                ),
            ),
        )
        row = self.connection.execute(
            "SELECT c.digest,o.record FROM product_outcome.commands c JOIN "
            "product_outcome.outcomes o "
            "USING(namespace,security_domain,outcome_id) WHERE c.namespace=%s AND "
            "c.security_domain=%s "
            "AND c.actor_id=%s AND c.command_key=%s",
            (p.namespace, p.security_domain, self.principal.principal_id, key),
        ).fetchone()
        if row and row["digest"] != digest:
            raise ExecutionPreparationError("RESULT_COMMAND_REPLAY_CONFLICT")
        return row["record"] if row else None

    def remember(self, p, key, digest, outcome_id):
        self.connection.execute(
            "INSERT INTO product_outcome.commands VALUES (%s,%s,%s,%s,%s,%s)",
            (
                p.namespace,
                p.security_domain,
                self.principal.principal_id,
                key,
                digest,
                outcome_id,
            ),
        )

    def append_outcome(self, p, evaluation, confirmation_id, predecessor, resolution):
        key = (p.namespace, p.security_domain)
        head = self.connection.execute(
            "SELECT * FROM product_outcome.heads WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s FOR UPDATE",
            (*key, p.run_id),
        ).fetchone()
        if (head["outcome_id"] if head else None) != predecessor:
            raise ExecutionPreparationError("RESULT_HEAD_CONFLICT")
        outcome_id = stable_id(
            "business-outcome",
            evaluation["evaluationId"],
            confirmation_id or "unconfirmed",
        )
        result = {
            "outcomeId": outcome_id,
            "runId": p.run_id,
            "evaluation": evaluation,
            "evaluationDigest": canonical_digest(evaluation),
            "confirmationId": confirmation_id,
            "predecessorId": predecessor,
            "businessResolution": resolution,
            "version": head["version"] + 1 if head else 1,
            "technicalSuccessNotBusinessSuccess": True,
        }
        self.connection.execute(
            "INSERT INTO product_outcome.outcomes "
            "(namespace,security_domain,outcome_id,workflow_run_id,evaluation_id,confirmation_id,predecessor_id,resolution,digest,record) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                outcome_id,
                p.run_id,
                evaluation["evaluationId"],
                confirmation_id,
                predecessor,
                resolution,
                canonical_digest(result),
                Jsonb(result),
            ),
        )
        self.connection.execute(
            "INSERT INTO product_outcome.heads VALUES (%s,%s,%s,%s,%s) "
            "ON CONFLICT(namespace,security_domain,workflow_run_id) DO UPDATE SET version=EXCLUDED.version,outcome_id=EXCLUDED.outcome_id",
            (*key, p.run_id, result["version"], outcome_id),
        )
        return result

    def confirm(
        self,
        p,
        *,
        evaluation_id,
        evaluation_digest,
        expected_version,
        decision,
        reason,
        command_key,
    ):
        authorization = self.require(
            "HUMAN_CONFIRMATION", "CONFIRM", "human-confirmation:prepared:" + p.digest
        )
        if (
            not self.principal.principal_id.startswith("human:")
            or not reason.strip()
            or len(reason) > 1000
        ):
            raise ExecutionPreparationError("HUMAN_RESULT_DECISION_REQUIRED")
        if decision not in {
            "ACKNOWLEDGE_UNDETERMINED",
            "DISAGREE",
            "CONFIRM_PROBLEM_SOLVED",
        }:
            raise ExecutionPreparationError("HUMAN_RESULT_DECISION_INVALID")
        snapshot = self.snapshot(p)
        command_digest = canonical_digest(
            {
                "evaluationId": evaluation_id,
                "evaluationDigest": evaluation_digest,
                "version": expected_version,
                "decision": decision,
                "reason": reason,
                "preparation": p.digest,
            }
        )
        replay = self.command_replay(p, command_key, command_digest)
        if replay:
            return replay
        key = (p.namespace, p.security_domain)
        current = self.connection.execute(
            "SELECT h.version,o.outcome_id,e.digest,e.record FROM "
            "product_outcome.heads h "
            "JOIN product_outcome.outcomes o "
            "USING(namespace,security_domain,outcome_id) "
            "JOIN success_criteria_evaluation.results e "
            "USING(namespace,security_domain,evaluation_id) "
            "WHERE h.namespace=%s AND h.security_domain=%s AND h.workflow_run_id=%s FOR UPDATE OF h",
            (*key, p.run_id),
        ).fetchone()
        if (
            current is None
            or current["version"] != expected_version
            or current["digest"] != evaluation_digest
            or current["record"]["evaluationId"] != evaluation_id
        ):
            raise ExecutionPreparationError("HUMAN_RESULT_TARGET_STALE")
        evaluation = current["record"]
        if canonical_digest(snapshot) != evaluation["snapshotDigest"]:
            raise ExecutionPreparationError("HUMAN_REVIEWED_SNAPSHOT_STALE")
        if decision == "CONFIRM_PROBLEM_SOLVED":
            # This batch explicitly cannot turn synthetic examples into enterprise proof.
            raise ExecutionPreparationError("SYNTHETIC_EXECUTION_NOT_BUSINESS_PROOF")
        confirmation_id = stable_id(
            "human-result-confirmation",
            p.run_id,
            self.principal.principal_id,
            command_key,
        )
        confirmation = {
            "confirmationId": confirmation_id,
            "evaluationId": evaluation_id,
            "evaluationDigest": evaluation_digest,
            "reviewedSnapshotId": evaluation["snapshotId"],
            "reviewedSnapshotDigest": evaluation["snapshotDigest"],
            "actorId": self.principal.principal_id,
            "authorityBasis": authorization.decision_id,
            "decision": decision,
            "reason": reason,
        }
        self.connection.execute(
            "INSERT INTO human_governance.confirmations "
            "(namespace,security_domain,confirmation_id,evaluation_id,snapshot_id,actor_id,authority_basis,decision,reason,digest,record) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                confirmation_id,
                evaluation_id,
                evaluation["snapshotId"],
                self.principal.principal_id,
                authorization.decision_id,
                decision,
                reason,
                canonical_digest(confirmation),
                Jsonb(confirmation),
            ),
        )
        successor = dict(evaluation)
        successor["evaluationId"] = stable_id(
            "criteria-evaluation", evaluation_id, confirmation_id
        )
        successor["predecessorId"] = evaluation_id
        successor["humanConfirmationId"] = confirmation_id
        if decision == "DISAGREE":
            successor["results"] = [
                {**r, "result": "NOT_SATISFIED", "reason": "HUMAN_DISAGREEMENT"}
                if next(
                    c
                    for c in snapshot["criteria"]
                    if c["revision_id"] == r["criterionRevisionId"]
                )["criterion_type"]
                == "HUMAN_EVALUATED"
                else r
                for r in evaluation["results"]
            ]
        self.connection.execute(
            "INSERT INTO success_criteria_evaluation.results "
            "(namespace,security_domain,evaluation_id,workflow_run_id,snapshot_id,predecessor_id,digest,record) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                successor["evaluationId"],
                p.run_id,
                evaluation["snapshotId"],
                evaluation_id,
                canonical_digest(successor),
                Jsonb(successor),
            ),
        )
        statuses = {r["result"] for r in successor["results"]}
        resolution = (
            "NOT_SOLVED"
            if statuses
            and statuses <= {"SATISFIED", "NOT_SATISFIED"}
            and "NOT_SATISFIED" in statuses
            else "UNDETERMINED"
        )
        result = self.append_outcome(
            p, successor, confirmation_id, current["outcome_id"], resolution
        )
        self.remember(p, command_key, command_digest, result["outcomeId"])
        return result
