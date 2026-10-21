"""Same-transaction storage for the Execution Authority's prepared Run.

Not an admission endpoint. The owner supplies its already-authorized transaction,
canonical identities, and durable worker observations. No effects are dispatched.
"""

import hashlib
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .execution_preparation import (
    ArtifactDocument,
    ExecutionPreparation,
    ExecutionPreparationError,
    ProgressEvent,
    RunProgress,
    TaskState,
    initial_progress,
    transition,
)
from .resource_use_domain import canonical_digest


class PreparedExecutionStore:
    def __init__(self, connection):
        self.connection = connection

    def migrate(self):
        path = Path(__file__).parents[2] / "migrations/0033_prepared_execution.sql"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.connection.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(3240033)")
            present = cur.execute(
                "SELECT to_regclass('execution_authority.preparation_migrations') AS t"
            ).fetchone()["t"]
            if present:
                versions = cur.execute(
                    "SELECT version,checksum FROM "
                    "execution_authority.preparation_migrations ORDER BY version"
                ).fetchall()
                if versions != [{"version": 33, "checksum": checksum}]:
                    raise ExecutionPreparationError("PREPARATION_SCHEMA_INCOMPATIBLE")
                return
            cur.execute(path.read_text())
            cur.execute(
                "INSERT INTO execution_authority.preparation_migrations VALUES (33,%s)",
                (checksum,),
            )

    def attach(self, preparation: ExecutionPreparation) -> RunProgress:
        """Attach only to an existing canonical Run created by admission's UoW."""
        key = (preparation.namespace, preparation.security_domain, preparation.run_id)
        with self.connection.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                "SELECT assignment_id FROM execution_authority.workflow_runs "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                "FOR UPDATE",
                key,
            ).fetchone()
            if row is None or row["assignment_id"] != preparation.root_assignment_id:
                raise ExecutionPreparationError("PREPARATION_CANONICAL_RUN_MISMATCH")
            existing = cur.execute(
                "SELECT digest FROM execution_authority.run_preparations "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                key,
            ).fetchone()
            if existing:
                if existing["digest"] != preparation.digest:
                    raise ExecutionPreparationError("PREPARATION_REPLAY_CONFLICT")
                return self.read(*key)[1]
            state = initial_progress(preparation)
            cur.execute(
                "INSERT INTO execution_authority.run_preparations "
                "(namespace,security_domain,workflow_run_id,digest,record) "
                "VALUES (%s,%s,%s,%s,%s)",
                (*key, preparation.digest, Jsonb(preparation.model_dump(mode="json"))),
            )
            cur.execute(
                "INSERT INTO execution_authority.prepared_run_progress "
                "(namespace,security_domain,workflow_run_id,version,record) "
                "VALUES (%s,%s,%s,%s,%s)",
                (*key, state.version, Jsonb(state.model_dump(mode="json"))),
            )
            return state

    def read(self, namespace, security_domain, run_id, *, lock=False):
        with self.connection.cursor(row_factory=dict_row) as cur:
            row = cur.execute(
                "SELECT p.record AS preparation,s.record AS progress "
                "FROM execution_authority.run_preparations p JOIN "
                "execution_authority.prepared_run_progress s "
                "USING(namespace,security_domain,workflow_run_id) "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s"
                + (" FOR UPDATE OF s" if lock else ""),
                (namespace, security_domain, run_id),
            ).fetchone()
            if row is None:
                raise ExecutionPreparationError("PREPARED_RUN_NOT_FOUND")
            return (
                ExecutionPreparation.model_validate(row["preparation"]),
                RunProgress.model_validate(row["progress"]),
            )

    def append_artifact(
        self, namespace, security_domain, run_id, artifact: ArtifactDocument
    ):
        key = (namespace, security_domain, run_id)
        preparation, state = self.read(*key, lock=True)
        record = artifact.model_dump(mode="json")
        with self.connection.cursor(row_factory=dict_row) as cur:
            existing = cur.execute(
                "SELECT record FROM execution_authority.run_artifacts "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                "AND artifact_id=%s",
                (*key, artifact.artifact_id),
            ).fetchone()
            if existing:
                if existing["record"] != record:
                    raise ExecutionPreparationError("ARTIFACT_REPLAY_CONFLICT")
                return
            task = next((t for t in state.tasks if t.task_id == artifact.task_id), None)
            if (
                task is None
                or task.state != TaskState.RUNNING
                or task.attempt_id != artifact.attempt_id
            ):
                raise ExecutionPreparationError("ARTIFACT_ACTIVE_ATTEMPT_REQUIRED")
            definition = next(
                t for t in preparation.semantics.tasks if t.task_id == artifact.task_id
            )
            if artifact.kind != definition.output_kind:
                raise ExecutionPreparationError("ARTIFACT_OUTPUT_KIND_MISMATCH")
            # Canonical lineage check prevents an Attempt from a different Run.
            lineage = cur.execute(
                "SELECT 1 FROM execution_authority.attempts a JOIN "
                "execution_authority.task_runs t "
                "USING(namespace,security_domain,task_run_id) "
                "WHERE a.namespace=%s AND a.security_domain=%s "
                "AND t.workflow_run_id=%s "
                "AND a.attempt_id=%s",
                (*key, artifact.attempt_id),
            ).fetchone()
            if lineage is None:
                raise ExecutionPreparationError("ARTIFACT_LINEAGE_MISMATCH")
            cur.execute(
                "INSERT INTO execution_authority.run_artifacts "
                "(namespace,security_domain,workflow_run_id,artifact_id,task_id,"
                "attempt_id,digest,content,record) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    artifact.artifact_id,
                    artifact.task_id,
                    artifact.attempt_id,
                    artifact.digest,
                    artifact.content,
                    Jsonb(record),
                ),
            )

    def apply(
        self,
        namespace,
        security_domain,
        run_id,
        event: ProgressEvent,
        *,
        expected_version: int,
    ):
        key = (namespace, security_domain, run_id)
        preparation, progress = self.read(*key, lock=True)
        digest = canonical_digest(event.model_dump(mode="json"))
        with self.connection.cursor(row_factory=dict_row) as cur:
            prior = cur.execute(
                "SELECT digest,result FROM execution_authority.prepared_run_events "
                "WHERE namespace=%s AND security_domain=%s "
                "AND workflow_run_id=%s AND event_id=%s",
                (*key, event.evidence_id),
            ).fetchone()
            if prior:
                if prior["digest"] != digest:
                    raise ExecutionPreparationError("EXECUTION_EVENT_REPLAY_CONFLICT")
                return RunProgress.model_validate(prior["result"])
            if progress.version != expected_version:
                raise ExecutionPreparationError("EXECUTION_PROGRESS_VERSION_CONFLICT")
            result = transition(preparation, progress, event)
            if event.action in {"QUEUE", "RETRY"}:
                used = cur.execute(
                    "SELECT 1 FROM execution_authority.prepared_run_events "
                    "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                    "AND record->>'action' IN ('QUEUE','RETRY') "
                    "AND record->>'attempt_id'=%s",
                    (*key, event.attempt_id),
                ).fetchone()
                if used:
                    raise ExecutionPreparationError("EXECUTION_ATTEMPT_ALREADY_USED")
            if event.action == "SUCCEEDED":
                if len(set(event.artifact_ids)) != len(event.artifact_ids):
                    raise ExecutionPreparationError("EXECUTION_DUPLICATE_ARTIFACT")
                rows = cur.execute(
                    "SELECT artifact_id FROM execution_authority.run_artifacts "
                    "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s "
                    "AND task_id=%s AND attempt_id=%s AND artifact_id=ANY(%s)",
                    (*key, event.task_id, event.attempt_id, list(event.artifact_ids)),
                ).fetchall()
                if len(rows) != len(event.artifact_ids):
                    raise ExecutionPreparationError("EXECUTION_OUTPUT_ARTIFACT_MISSING")
            cur.execute(
                "INSERT INTO execution_authority.prepared_run_events "
                "(namespace,security_domain,workflow_run_id,event_id,"
                "version,digest,record,result) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    *key,
                    event.evidence_id,
                    result.version,
                    digest,
                    Jsonb(event.model_dump(mode="json")),
                    Jsonb(result.model_dump(mode="json")),
                ),
            )
            cur.execute(
                "UPDATE execution_authority.prepared_run_progress "
                "SET version=%s,record=%s,"
                "updated_at=clock_timestamp() WHERE namespace=%s "
                "AND security_domain=%s AND workflow_run_id=%s",
                (result.version, Jsonb(result.model_dump(mode="json")), *key),
            )
            return result
