# ruff: noqa: E501 -- Exact scoped owner SQL.
"""PreparedResult-owned acceptance of exact deliverables; never business success."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from psycopg import Error as PsycopgError
from psycopg.types.json import Jsonb

from .authority_contracts import AuthorityError
from .execution_preparation import ArtifactDocument, ExecutionPreparationError
from .prepared_result_review import PreparedResultReview
from .resource_use_domain import canonical_digest, stable_id


def require_artifact_source(content, source):
    # Same bounded report schemas as the original artifactProvenance reader.
    # Raw/other artifacts remain raw content; no inferred report semantics.
    try:
        value = json.loads(content)
    except (ValueError, TypeError):
        return
    if (
        isinstance(value, dict)
        and value.get("schemaVersion")
        in {
            "sales-diagnostic-output.v1",
            "sales-diagnostic-output.v2",
            "synthetic-delivery-output.v1",
            "document-review-output.v1",
            "tabular-diagnostic-output.v1",
        }
        and value.get("sourceSnapshot") != source
    ):
        raise ExecutionPreparationError("DELIVERY_ARTIFACT_SOURCE_MISMATCH")


def migrate(connection):
    path = Path(__file__).parents[2] / "migrations/0074_deliverable_acceptance.sql"
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    connection.execute("SELECT pg_advisory_xact_lock(3240074)")
    present = connection.execute(
        "SELECT to_regclass('prepared_delivery.packages') AS t"
    ).fetchone()["t"]
    if present:
        row = connection.execute(
            "SELECT obj_description('prepared_delivery.packages'::regclass) AS checksum"
        ).fetchone()
        if row["checksum"] != checksum:
            raise ExecutionPreparationError("DELIVERY_SCHEMA_INCOMPATIBLE")
        tables = connection.execute(
            "SELECT to_regclass('prepared_delivery.events') AS events, "
            "to_regclass('prepared_delivery.heads') AS heads"
        ).fetchone()
        if not all(tables.values()):
            raise ExecutionPreparationError("DELIVERY_SCHEMA_INCOMPATIBLE")
        return
    connection.execute(path.read_text())
    connection.execute(
        "SELECT set_config('prepared_delivery.migration_checksum',%s,true)",
        (checksum,),
    )
    # A checksum comment avoids adding a fourth table to the attached owner.
    from psycopg import sql

    connection.execute(
        sql.SQL("COMMENT ON TABLE prepared_delivery.packages IS {}").format(
            sql.Literal(checksum)
        )
    )


class PreparedDeliveryAcceptance(PreparedResultReview):
    def _identity(self, p):
        if (self.principal.tenant_id, self.principal.security_domain) != (
            p.namespace,
            p.security_domain,
        ):
            raise ExecutionPreparationError("DELIVERY_NOT_FOUND")
        return (p.namespace, p.security_domain, p.digest)

    def _schema(self):
        row = self.connection.execute(
            "SELECT to_regclass('prepared_delivery.packages') packages, "
            "to_regclass('prepared_delivery.events') events, "
            "to_regclass('prepared_delivery.heads') heads, "
            "obj_description(to_regclass('prepared_delivery.packages')) checksum"
        ).fetchone()
        path = Path(__file__).parents[2] / "migrations/0074_deliverable_acceptance.sql"
        if (
            not all(row.values())
            or row["checksum"] != hashlib.sha256(path.read_bytes()).hexdigest()
        ):
            raise ExecutionPreparationError("DELIVERY_SCHEMA_INCOMPATIBLE")

    def package(self, p):
        self._identity(p)
        # snapshot and append_artifact share the exact prepared_run_progress lock.
        snapshot = self.snapshot(p)
        self._schema()
        native_present = self.connection.execute(
            "SELECT to_regclass('execution_authority.native_dispatch_commands') AS t"
        ).fetchone()["t"]
        unsettled = (
            native_present
            and self.connection.execute(
                "SELECT 1 FROM execution_authority.native_dispatch_commands WHERE namespace=%s "
                "AND security_domain=%s AND authorization_resource=%s AND state NOT IN ('SUCCEEDED','FAILED') LIMIT 1",
                (
                    p.namespace,
                    p.security_domain,
                    "governed-execution:prepared:" + p.digest,
                ),
            ).fetchone()
        )
        if unsettled:
            raise ExecutionPreparationError("DELIVERY_EXECUTION_UNRESOLVED")
        if not snapshot["artifacts"]:
            raise ExecutionPreparationError("DELIVERY_EMPTY")
        manifest = []
        rows = self.connection.execute(
            "SELECT artifact_id,task_id,attempt_id,digest,content,record FROM execution_authority.run_artifacts "
            "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s ORDER BY artifact_id",
            (p.namespace, p.security_domain, p.run_id),
        ).fetchall()
        for row in rows:
            try:
                artifact = ArtifactDocument.model_validate(row["record"])
            except ValueError as exc:
                raise ExecutionPreparationError("DELIVERY_ARTIFACT_CORRUPT") from exc
            if artifact.model_dump(mode="json") != row["record"] or any(
                row[field] != getattr(artifact, field)
                for field in (
                    "artifact_id",
                    "task_id",
                    "attempt_id",
                    "digest",
                    "content",
                )
            ):
                raise ExecutionPreparationError("DELIVERY_ARTIFACT_CORRUPT")
            require_artifact_source(
                artifact.content, p.source_snapshot.model_dump(mode="json")
            )
            manifest.append(
                {
                    "artifactId": artifact.artifact_id,
                    "taskId": artifact.task_id,
                    "attemptId": artifact.attempt_id,
                    "kind": artifact.kind,
                    "schemaVersion": artifact.schema_version,
                    "contentDigest": artifact.digest,
                    "recordDigest": canonical_digest(row["record"]),
                }
            )
        from .execution_domain import ScopeIdentity
        from .prepared_execution_resources import published
        from .workbench_prepared_resources import reference

        self.require(
            "KNOWLEDGE",
            "READ_RESOURCE",
            reference(
                "knowledge",
                p.source_snapshot.resource_id,
                p.source_snapshot.revision_id,
            ),
        )
        published(
            self.connection,
            ScopeIdentity(p.namespace, p.security_domain),
            "KNOWLEDGE",
            p.source_snapshot,
        )
        self.require("EVALUATION", "READ", "evaluation:prepared:" + p.digest)
        row = self.connection.execute(
            "SELECT o.*,h.version head_version,h.workflow_run_id head_run,"
            "e.record evaluated,e.digest evaluated_digest,e.workflow_run_id evaluated_run,"
            "e.snapshot_id evaluated_snapshot,e.predecessor_id evaluated_predecessor,"
            "s.snapshot_id,s.workflow_run_id snapshot_run,s.digest snapshot_digest,s.record snapshot "
            "FROM product_outcome.heads h JOIN product_outcome.outcomes o "
            "USING(namespace,security_domain,outcome_id) "
            "JOIN success_criteria_evaluation.results e ON "
            "(e.namespace,e.security_domain,e.evaluation_id)=(o.namespace,o.security_domain,o.evaluation_id) "
            "JOIN success_criteria_evaluation.snapshots s ON "
            "(s.namespace,s.security_domain,s.snapshot_id)=(e.namespace,e.security_domain,e.snapshot_id) "
            "WHERE h.namespace=%s AND h.security_domain=%s AND h.workflow_run_id=%s",
            (p.namespace, p.security_domain, p.run_id),
        ).fetchone()
        if not row:
            raise ExecutionPreparationError("DELIVERY_LIMITATIONS_UNAVAILABLE")
        outcome, evaluation = row["record"], row["evaluated"]
        if not (
            isinstance(outcome, dict)
            and isinstance(evaluation, dict)
            and row["namespace"] == p.namespace
            and row["security_domain"] == p.security_domain
            and row["workflow_run_id"]
            == row["head_run"]
            == row["evaluated_run"]
            == row["snapshot_run"]
            == p.run_id
            and canonical_digest(outcome) == row["digest"]
            and outcome.get("outcomeId") == row["outcome_id"]
            and outcome.get("runId") == p.run_id
            and outcome.get("version") == row["head_version"]
            and outcome.get("confirmationId") == row["confirmation_id"]
            and outcome.get("predecessorId") == row["predecessor_id"]
            and outcome.get("businessResolution") == row["resolution"]
            and outcome.get("evaluation") == evaluation
            and outcome.get("evaluationDigest")
            == row["evaluated_digest"]
            == canonical_digest(evaluation)
            and evaluation.get("evaluationId") == row["evaluation_id"]
            and evaluation.get("snapshotId")
            == row["evaluated_snapshot"]
            == row["snapshot_id"]
            and evaluation.get("predecessorId") == row["evaluated_predecessor"]
            and evaluation.get("snapshotDigest")
            == row["snapshot_digest"]
            == canonical_digest(snapshot)
            and row["snapshot"] == snapshot
        ):
            raise ExecutionPreparationError("DELIVERY_SNAPSHOT_CHANGED")
        return {
            "schemaVersion": "prepared-delivery-package.v1",
            "namespace": p.namespace,
            "securityDomain": p.security_domain,
            "preparationDigest": p.digest,
            "workflowRunId": p.run_id,
            "source": p.source_snapshot.model_dump(mode="json"),
            "snapshot": snapshot,
            "artifactManifest": manifest,
            "outcome": outcome,
            "outcomeDigest": row["digest"],
            "limitations": snapshot["limitations"]
            + (
                []
                if snapshot["runState"] == "SUCCEEDED"
                else ["EXECUTION_" + snapshot["runState"]]
            ),
            "acceptanceDoesNotConfirmBusinessResolution": True,
        }

    def _head(self, key, run_id):
        row = self.connection.execute(
            "SELECT e.*,h.version head_version FROM prepared_delivery.heads h JOIN prepared_delivery.events e "
            "USING(namespace,security_domain,event_id) WHERE h.namespace=%s AND "
            "h.security_domain=%s AND h.preparation_digest=%s",
            key,
        ).fetchone()
        if row and (
            not isinstance(row["record"], dict)
            or canonical_digest(row["record"]) != row["digest"]
            or row["record"].get("packageDigest") != row["package_digest"]
            or row["record"].get("commandKey") != row["command_key"]
            or row["record"].get("commandDigest") != row["command_digest"]
            or row["record"].get("actorId") != row["actor_id"]
            or row["record"].get("action") != row["action"]
            or row["record"].get("namespace") != key[0]
            or row["record"].get("securityDomain") != key[1]
            or row["record"].get("workflowRunId") != run_id
            or row["record"].get("preparationDigest") != key[2]
            or row["preparation_digest"] != key[2]
            or row["version"] != row["head_version"]
            or row["record"].get("version") != row["version"]
            or row["record"].get("eventId") != row["event_id"]
            or row["record"].get("predecessorId") != row["predecessor_id"]
        ):
            raise ExecutionPreparationError("DELIVERY_RECORD_CORRUPT")
        if row:
            package = self.connection.execute(
                "SELECT * FROM prepared_delivery.packages WHERE namespace=%s "
                "AND security_domain=%s AND preparation_digest=%s AND package_digest=%s",
                (*key, row["package_digest"]),
            ).fetchone()
            if (
                not package
                or not isinstance(package["record"], dict)
                or canonical_digest(package["record"]) != row["package_digest"]
                or package["namespace"] != key[0]
                or package["security_domain"] != key[1]
                or package["preparation_digest"] != key[2]
                or package["package_digest"] != row["package_digest"]
                or package["record"].get("namespace") != key[0]
                or package["record"].get("securityDomain") != key[1]
                or package["record"].get("preparationDigest") != key[2]
                or package["workflow_run_id"] != package["record"].get("workflowRunId")
                or package["record"].get("workflowRunId")
                != row["record"].get("workflowRunId")
            ):
                raise ExecutionPreparationError("DELIVERY_RECORD_CORRUPT")
        return row

    def _allowed(self, p, action):
        try:
            self.require("EXECUTION", action, "governed-execution:prepared:" + p.digest)
            return self.principal.principal_id.startswith("human:")
        except AuthorityError:
            return False

    def read(self, p):
        try:
            # This optional projection cannot abort the caller's original result
            # read when its attached schema/storage is temporarily unavailable.
            with self.connection.transaction():
                return self._read(p)
        except (AuthorityError, ExecutionPreparationError, PsycopgError):
            return {"status": "UNAVAILABLE"}

    def _read(self, p):
        package = self.package(p)
        key = self._identity(p)
        head = self._head(key, p.run_id)
        digest = canonical_digest(package)
        status = "NOT_RECORDED"
        if head:
            status = (
                "SUPERSEDED"
                if head["package_digest"] != digest
                else "ACCEPTED"
                if head["action"] == "ACCEPT_DELIVERY"
                else "RETRACTED"
            )
        return {
            "status": status,
            "packageDigest": digest,
            "package": package,
            "version": head["version"] if head else 0,
            "event": head["record"] if head else None,
            "canAccept": status != "ACCEPTED" and self._allowed(p, "ACCEPT_DELIVERY"),
            "canRetract": bool(
                head
                and status == "ACCEPTED"
                and head["action"] == "ACCEPT_DELIVERY"
                and head["actor_id"] == self.principal.principal_id
                and self._allowed(p, "RETRACT_DELIVERY")
            ),
        }

    def receipt(self, p, command_key):
        key = self._identity(p)
        self.package(p)  # Current complete source/output READ; never a write grant.
        row = self.connection.execute(
            "SELECT * FROM prepared_delivery.events WHERE namespace=%s AND security_domain=%s "
            "AND actor_id=%s AND command_key=%s AND preparation_digest=%s",
            (*key[:2], self.principal.principal_id, command_key, p.digest),
        ).fetchone()
        if not row:
            raise ExecutionPreparationError("DELIVERY_RECEIPT_NOT_FOUND")
        record = row["record"]
        if (
            not isinstance(record, dict)
            or canonical_digest(record) != row["digest"]
            or record.get("namespace") != key[0]
            or record.get("securityDomain") != key[1]
            or record.get("preparationDigest") != p.digest
            or record.get("workflowRunId") != p.run_id
            or record.get("commandKey") != command_key
            or record.get("commandDigest") != row["command_digest"]
            or record.get("actorId") != self.principal.principal_id
            or record.get("eventId") != row["event_id"]
            or record.get("packageDigest") != row["package_digest"]
            or record.get("version") != row["version"]
            or record.get("action") != row["action"]
            or record.get("predecessorId") != row["predecessor_id"]
        ):
            raise ExecutionPreparationError("DELIVERY_RECORD_CORRUPT")
        stored = self.connection.execute(
            "SELECT * FROM prepared_delivery.packages WHERE namespace=%s AND security_domain=%s "
            "AND preparation_digest=%s AND package_digest=%s",
            (*key, row["package_digest"]),
        ).fetchone()
        if not stored or (
            not isinstance(stored["record"], dict)
            or canonical_digest(stored["record"]) != row["package_digest"]
            or stored["workflow_run_id"] != p.run_id
            or stored["record"].get("workflowRunId") != p.run_id
            or stored["record"].get("namespace") != key[0]
            or stored["record"].get("securityDomain") != key[1]
            or stored["record"].get("preparationDigest") != key[2]
        ):
            raise ExecutionPreparationError("DELIVERY_RECORD_CORRUPT")
        return {"event": record, "digest": row["digest"]}

    def decide(self, p, payload):
        key = self._identity(p)
        action = payload["action"]
        if action not in {"ACCEPT_DELIVERY", "RETRACT_DELIVERY"}:
            raise ExecutionPreparationError("DELIVERY_ACTION_INVALID")
        auth = self.require(
            "EXECUTION", action, "governed-execution:prepared:" + p.digest
        )
        if not self.principal.principal_id.startswith("human:"):
            raise ExecutionPreparationError("DELIVERY_HUMAN_REQUIRED")
        self.connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                json.dumps(
                    [
                        "prepared-delivery-command",
                        *key[:2],
                        self.principal.principal_id,
                        payload["idempotencyKey"],
                    ]
                ),
            ),
        )
        package = self.package(p)  # same lock as artifact writes, before own head
        command_digest = canonical_digest(
            {"preparationDigest": p.digest, "payload": payload}
        )
        old = self.connection.execute(
            "SELECT * FROM prepared_delivery.events WHERE namespace=%s AND security_domain=%s "
            "AND actor_id=%s AND command_key=%s",
            (*key[:2], self.principal.principal_id, payload["idempotencyKey"]),
        ).fetchone()
        if old:
            if old["command_digest"] != command_digest:
                raise ExecutionPreparationError("DELIVERY_COMMAND_CONFLICT")
            return self.receipt(p, payload["idempotencyKey"])
        head = self._head(key, p.run_id)
        version = head["version"] if head else 0
        package_digest = canonical_digest(package)
        if (
            payload["expectedVersion"] != version
            or payload["packageDigest"] != package_digest
        ):
            raise ExecutionPreparationError("DELIVERY_TARGET_CHANGED")
        if action == "RETRACT_DELIVERY":
            if (
                not head
                or head["action"] != "ACCEPT_DELIVERY"
                or head["actor_id"] != self.principal.principal_id
                or head["package_digest"] != package_digest
                or payload.get("targetEventId") != head["event_id"]
                or not payload.get("reason", "").strip()
            ):
                raise ExecutionPreparationError("DELIVERY_RETRACTION_NOT_ALLOWED")
        elif payload.get("targetEventId") is not None:
            raise ExecutionPreparationError("DELIVERY_ACCEPT_TARGET_INVALID")
        elif (
            head
            and head["action"] == "ACCEPT_DELIVERY"
            and head["package_digest"] == package_digest
        ):
            raise ExecutionPreparationError("DELIVERY_ALREADY_ACCEPTED")
        event_id = stable_id(
            "delivery-decision",
            *key,
            self.principal.principal_id,
            payload["idempotencyKey"],
        )
        record = {
            "schemaVersion": "prepared-delivery-decision.v1",
            "namespace": key[0],
            "securityDomain": key[1],
            "eventId": event_id,
            "commandKey": payload["idempotencyKey"],
            "commandDigest": command_digest,
            "preparationDigest": p.digest,
            "workflowRunId": p.run_id,
            "packageDigest": package_digest,
            "version": version + 1,
            "action": action,
            "actorId": self.principal.principal_id,
            "authorityBasis": auth.decision_id,
            "reason": payload.get("reason", ""),
            "predecessorId": head["event_id"] if head else None,
            "targetEventId": payload.get("targetEventId"),
            "createdAt": datetime.now(UTC).isoformat(),
        }
        digest = canonical_digest(record)
        self.connection.execute(
            "INSERT INTO prepared_delivery.packages VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (*key, package_digest, p.run_id, Jsonb(package)),
        )
        persisted = self.connection.execute(
            "SELECT workflow_run_id,record FROM prepared_delivery.packages WHERE namespace=%s "
            "AND security_domain=%s AND preparation_digest=%s AND package_digest=%s",
            (*key, package_digest),
        ).fetchone()
        if persisted != {"workflow_run_id": p.run_id, "record": package}:
            raise ExecutionPreparationError("DELIVERY_RECORD_CORRUPT")
        self.connection.execute(
            "INSERT INTO prepared_delivery.events VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *key,
                event_id,
                version + 1,
                package_digest,
                self.principal.principal_id,
                payload["idempotencyKey"],
                command_digest,
                action,
                record["predecessorId"],
                digest,
                Jsonb(record),
            ),
        )
        self.connection.execute(
            "INSERT INTO prepared_delivery.heads VALUES(%s,%s,%s,%s,%s) "
            "ON CONFLICT(namespace,security_domain,preparation_digest) DO UPDATE "
            "SET version=excluded.version,event_id=excluded.event_id",
            (*key, version + 1, event_id),
        )
        return {"event": record, "digest": digest}
