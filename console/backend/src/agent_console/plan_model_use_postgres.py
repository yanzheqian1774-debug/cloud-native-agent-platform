"""Execution/Model Evidence owner adapters for the accepted D2 context variant."""

from psycopg.types.json import Jsonb

from .business_problem_domain import canonical_digest
from .plan_suggestion_domain import PlanningConflict


class PostgresPlanModelUseOwner:
    """Uses existing canonical contextual Resource Use and Model Evidence stores."""

    def __init__(self, planning_repository):
        self.repository = planning_repository

    def requested(self, scope, invocation):
        identity = invocation["target"]["invocation_id"]
        use_id = "contextual-resource-use:" + identity
        record = {
            "schemaVersion": "contextual-plan-suggestion-use.v1",
            "contextKind": "PLAN_SUGGESTION_INVOCATION",
            "contextId": identity,
            "resourceUseId": use_id,
            "resourceKind": "MODEL",
            "target": invocation["target"],
            "targetDigest": invocation["target_digest"],
            "binding": invocation["binding"],
            "bindingSnapshotId": invocation["target_digest"],
            "authorizationDecisionId": invocation["authorization_decision_id"],
            "status": "REQUESTED",
        }
        with self.repository.transaction(scope, use_id, authorized=True) as cursor:
            inserted = cursor.execute(
                "INSERT INTO contextual_resource_use.uses "
                "(namespace,security_domain,resource_use_id,context_kind,context_id,"
                "resource_kind,binding_snapshot_id,record) "
                "VALUES(%s,%s,%s,'PLAN_SUGGESTION_INVOCATION',%s,'MODEL',%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING resource_use_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    use_id,
                    identity,
                    invocation["target_digest"],
                    Jsonb(record),
                ),
            ).fetchone()
            if inserted is None:
                existing = cursor.execute(
                    "SELECT record FROM contextual_resource_use.uses WHERE "
                    "namespace=%s AND security_domain=%s AND resource_use_id=%s",
                    (scope.namespace, scope.security_domain, use_id),
                ).fetchone()
                if existing["record"] != record:
                    raise PlanningConflict("PLAN_RESOURCE_USE_CONFLICT")
        return use_id

    def observed(self, scope, invocation, result):
        identity = invocation["target"]["invocation_id"]
        use_id = "contextual-resource-use:" + identity
        record = {
            "schemaVersion": "model-plan-suggestion-invocation-evidence.v1",
            "invocationId": identity,
            "targetDigest": invocation["target_digest"],
            "binding": invocation["binding"],
            "resourceUseId": use_id,
            "technicalStatus": result["technical_status"],
            "semanticResult": result.get("kind"),
            "outputDigest": result.get("output_digest"),
            "transport": invocation["transport"],
            "inputTokens": None,
            "outputTokens": None,
            "measurementState": "NOT_COLLECTED",
        }
        digest = canonical_digest(record)
        evidence_id = "model-evidence:" + digest
        operation = identity + ":terminal"
        with self.repository.transaction(scope, use_id, authorized=True) as cursor:
            inserted = cursor.execute(
                "INSERT INTO model_evidence.records "
                "(namespace,security_domain,evidence_id,schema_version,operation_id,"
                "payload_digest,record) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT DO NOTHING RETURNING evidence_id",
                (
                    scope.namespace,
                    scope.security_domain,
                    evidence_id,
                    record["schemaVersion"],
                    operation,
                    digest,
                    Jsonb(record),
                ),
            ).fetchone()
            if inserted is None:
                row = cursor.execute(
                    "SELECT payload_digest FROM model_evidence.records WHERE "
                    "namespace=%s AND security_domain=%s AND operation_id=%s",
                    (scope.namespace, scope.security_domain, operation),
                ).fetchone()
                if row["payload_digest"] != digest:
                    raise PlanningConflict("PLAN_MODEL_EVIDENCE_CONFLICT")
            cursor.execute(
                "INSERT INTO contextual_resource_use.facts "
                "(namespace,security_domain,resource_use_id,operation_id,"
                "fact_kind,record) "
                "VALUES(%s,%s,%s,%s,'OBSERVATION',%s) ON CONFLICT DO NOTHING",
                (
                    scope.namespace,
                    scope.security_domain,
                    use_id,
                    operation,
                    Jsonb(
                        {
                            "status": result["technical_status"],
                            "evidenceId": evidence_id,
                            "measurementState": "NOT_COLLECTED",
                        }
                    ),
                ),
            )
        return evidence_id

    def status(self, scope, invocation_id):
        with self.repository.transaction(
            scope, invocation_id, authorized=True
        ) as cursor:
            row = cursor.execute(
                "SELECT evidence_id FROM model_evidence.records WHERE namespace=%s "
                "AND security_domain=%s AND operation_id=%s",
                (scope.namespace, scope.security_domain, invocation_id + ":terminal"),
            ).fetchone()
            return "RECORDED" if row else "PENDING_RECONCILIATION"
