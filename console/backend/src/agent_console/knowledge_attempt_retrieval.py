"""Attempt-scoped retrieval over authoritative Knowledge and a derived Qdrant index."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from agent_core.execution_contract import ScopeIdentity

from agent_console.knowledge_ingestion import deterministic_vector
from agent_console.knowledge_pack import canonical_digest, identifier, normalize_text
from agent_console.knowledge_qdrant import QdrantKnowledgeError, QdrantKnowledgeIndex
from agent_console.knowledge_repository import KnowledgeRepository, KnowledgeScope

if TYPE_CHECKING:
    from agent_console.resource_use_application import ResourceUseApplicationService
    from agent_console.resource_use_domain import ResourceUseBinding


class AttemptKnowledgeFailure(ValueError):
    """Stable fail-closed capability failure."""


@dataclass(frozen=True, slots=True)
class AttemptContext:
    attempt_id: str
    digital_employee_instance_id: str
    agent_instance_id: str | None = None
    namespace: str | None = None
    security_domain: str | None = None


class AttemptKnowledgeEvidenceRepository(Protocol):
    def get_attempt(
        self, scope: KnowledgeScope, attempt_id: str
    ) -> AttemptContext | None: ...
    def append_binding(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def append_evidence(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def get_evidence(
        self, scope: KnowledgeScope, evidence_id: str
    ) -> dict[str, Any] | None: ...
    def get_evidence_for_binding(
        self, scope: KnowledgeScope, binding_id: str
    ) -> dict[str, Any] | None: ...
    def append_binding_with_connection(
        self, connection: Any, record: dict[str, Any]
    ) -> dict[str, Any]: ...
    def append_evidence_with_connection(
        self, connection: Any, record: dict[str, Any]
    ) -> dict[str, Any]: ...


class InMemoryAttemptKnowledgeEvidenceRepository:
    def __init__(self, attempts: tuple[AttemptContext, ...] = ()) -> None:
        self.attempts = {item.attempt_id: item for item in attempts}
        self.bindings: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, dict[str, Any]] = {}

    def get_attempt(
        self, scope: KnowledgeScope, attempt_id: str
    ) -> AttemptContext | None:
        value = self.attempts.get(attempt_id)
        if value is None or (
            value.namespace is not None
            and (value.namespace, value.security_domain)
            != (scope.namespace, scope.security_domain)
        ):
            return None
        return value

    @staticmethod
    def _append(
        target: dict[str, dict[str, Any]], record: dict[str, Any]
    ) -> dict[str, Any]:
        key = record[
            next(name for name in ("evidenceId", "bindingId") if name in record)
        ]
        existing = target.get(key)
        if existing is not None and existing != record:
            raise AttemptKnowledgeFailure("KNOWLEDGE_REPLAY_CONFLICT")
        target[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def append_binding(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._append(self.bindings, record)

    def append_binding_with_connection(
        self, connection: Any, record: dict[str, Any]
    ) -> dict[str, Any]:
        return self.append_binding(record)

    def append_evidence(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._append(self.evidence, record)

    def append_evidence_with_connection(
        self, connection: Any, record: dict[str, Any]
    ) -> dict[str, Any]:
        return self.append_evidence(record)

    def get_evidence(
        self, scope: KnowledgeScope, evidence_id: str
    ) -> dict[str, Any] | None:
        value = self.evidence.get(evidence_id)
        if value is None:
            return None
        if (value["namespace"], value["securityDomain"]) != (
            scope.namespace,
            scope.security_domain,
        ):
            return None
        return copy.deepcopy(value)

    def get_evidence_for_binding(
        self, scope: KnowledgeScope, binding_id: str
    ) -> dict[str, Any] | None:
        value = next(
            (
                item
                for item in self.evidence.values()
                if item["bindingId"] == binding_id
                and (item["namespace"], item["securityDomain"])
                == (scope.namespace, scope.security_domain)
            ),
            None,
        )
        return None if value is None else copy.deepcopy(value)


@dataclass(frozen=True, slots=True)
class AttemptKnowledgeRequest:
    attempt_id: str
    digital_employee_instance_id: str
    agent_instance_id: str | None
    binding_id: str
    knowledge_id: str
    revision_id: str
    revision_digest: str
    snapshot_id: str
    authorization_state: str
    authorization_decision_id: str
    query: str
    allow_stale: bool = False


def _stable_id(kind: str, semantic: object) -> str:
    return f"{kind}:{canonical_digest(semantic, domain=f'{kind}.v1')}"


class AttemptKnowledgeRetrievalService:
    def __init__(
        self,
        knowledge: KnowledgeRepository,
        evidence: AttemptKnowledgeEvidenceRepository,
        qdrant: QdrantKnowledgeIndex,
    ) -> None:
        self.knowledge = knowledge
        self.evidence = evidence
        self.qdrant = qdrant

    def retrieve(
        self,
        scope: KnowledgeScope,
        request: AttemptKnowledgeRequest,
        *,
        resource_use_service: ResourceUseApplicationService | None = None,
        resource_use_binding: ResourceUseBinding | None = None,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        # This check intentionally precedes every repository and Qdrant read.
        if request.authorization_state != "ALLOW":
            raise AttemptKnowledgeFailure("KNOWLEDGE_ACCESS_DENIED")
        for value, code in (
            (request.attempt_id, "ATTEMPT_REQUIRED"),
            (request.digital_employee_instance_id, "DIGITAL_EMPLOYEE_REQUIRED"),
            (request.binding_id, "KNOWLEDGE_BINDING_REQUIRED"),
            (request.knowledge_id, "KNOWLEDGE_REQUIRED"),
            (request.revision_id, "KNOWLEDGE_REVISION_REQUIRED"),
            (request.snapshot_id, "INDEX_SNAPSHOT_REQUIRED"),
            (request.authorization_decision_id, "AUTHORIZATION_DECISION_REQUIRED"),
        ):
            identifier(value, code)
        query = normalize_text(request.query, "INVALID_RETRIEVAL_QUERY", limit=2_000)
        attempt = self.evidence.get_attempt(scope, request.attempt_id)
        if attempt is None:
            raise AttemptKnowledgeFailure("ATTEMPT_NOT_FOUND")
        if attempt.digital_employee_instance_id != request.digital_employee_instance_id:
            raise AttemptKnowledgeFailure("DIGITAL_EMPLOYEE_BINDING_MISMATCH")
        if request.agent_instance_id is not None and (
            attempt.agent_instance_id != request.agent_instance_id
        ):
            raise AttemptKnowledgeFailure("AGENT_BINDING_MISMATCH")
        record = self.knowledge.get(scope, request.knowledge_id)
        revision = next(
            (
                item
                for item in record["revisions"]
                if item["revisionId"] == request.revision_id
            ),
            None,
        )
        if revision is None or revision["digest"] != request.revision_digest:
            raise AttemptKnowledgeFailure("KNOWLEDGE_REVISION_CONFLICT")
        snapshot = next(
            (
                item
                for item in record["indexSnapshots"]
                if item["snapshotId"] == request.snapshot_id
            ),
            None,
        )
        if (
            snapshot is None
            or snapshot["revisionId"] != request.revision_id
            or snapshot["revisionDigest"] != request.revision_digest
        ):
            raise AttemptKnowledgeFailure("INDEX_SNAPSHOT_CONFLICT")
        binding = {
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "bindingId": request.binding_id,
            "attemptId": request.attempt_id,
            "digitalEmployeeInstanceId": request.digital_employee_instance_id,
            "agentInstanceId": request.agent_instance_id,
            "knowledgeId": request.knowledge_id,
            "revisionId": request.revision_id,
            "revisionDigest": request.revision_digest,
            "snapshotId": request.snapshot_id,
            "authorizationDecisionId": request.authorization_decision_id,
        }
        binding["digest"] = canonical_digest(
            binding, domain="attempt-knowledge-binding.v1"
        )
        if (resource_use_service is None) != (resource_use_binding is None):
            raise AttemptKnowledgeFailure("KNOWLEDGE_RESOURCE_USE_REQUIRED")
        prepared = None
        integrated = resource_use_service is not None
        if integrated:
            from agent_console.resource_use_knowledge import (
                prepare_knowledge_retrieval,
            )

            timestamp = observed_at or datetime.fromisoformat(
                snapshot["createdAt"].replace("Z", "+00:00")
            )
            prepared, created = prepare_knowledge_retrieval(
                resource_use_service,
                resource_use_binding,
                binding,
                observed_at=timestamp,
                idempotency_key=f"knowledge-dispatch:{resource_use_binding.resource_use_id}",
                transaction_hook=lambda connection: (
                    self.evidence.append_binding_with_connection(connection, binding)
                ),
            )
            if not created:
                prior = self.evidence.get_evidence_for_binding(
                    scope, request.binding_id
                )
                if prior is None:
                    raise AttemptKnowledgeFailure(
                        "KNOWLEDGE_RESULT_PENDING_CONFIRMATION"
                    )
                return self._response_from_evidence(request, record, snapshot, prior)
        else:
            self.evidence.append_binding(binding)

        def finalize(freshness, state, reason, citations):
            result = self._result(
                scope,
                request,
                record,
                snapshot,
                freshness,
                state,
                reason,
                citations,
                persist=not integrated,
            )
            if integrated:
                from agent_console.resource_use_knowledge import (
                    commit_knowledge_retrieval,
                )

                commit_knowledge_retrieval(
                    resource_use_service,
                    ScopeIdentity(scope.namespace, scope.security_domain),
                    resource_use_binding.resource_use_id,
                    result,
                    observed_at=observed_at or datetime.now(UTC),
                    expected_high_water=prepared.high_water,
                    idempotency_key=f"knowledge-terminal:{result['evidence']['evidenceId']}",
                    transaction_hook=lambda connection: (
                        self.evidence.append_evidence_with_connection(
                            connection, result["evidence"]
                        )
                    ),
                )
            return result

        freshness = "FRESH" if snapshot["status"] == "ACTIVE" else "STALE"
        if freshness == "STALE" and not request.allow_stale:
            return finalize("STALE", "STALE", "INDEX_STALE", [])
        try:
            hits = self.qdrant.search(
                deterministic_vector(query),
                namespace=scope.namespace,
                security_domain=scope.security_domain,
                knowledge_id=request.knowledge_id,
                snapshot_id=request.snapshot_id,
                limit=5,
            )
        except QdrantKnowledgeError:
            return finalize(freshness, "UNAVAILABLE", "QDRANT_UNAVAILABLE", [])
        chunks = {
            chunk["chunkId"]: (document, chunk)
            for document in revision["content"]["documents"]
            for chunk in document["chunks"]
        }
        citations = []
        for hit in hits:
            payload = hit.get("payload", {})
            match = chunks.get(payload.get("chunkId"))
            if (
                match is None
                or payload.get("revisionId") != request.revision_id
                or payload.get("revisionDigest") != request.revision_digest
                or payload.get("snapshotId") != request.snapshot_id
            ):
                continue
            document, chunk = match
            identity = {
                "attemptId": request.attempt_id,
                "authorizationDecisionId": request.authorization_decision_id,
                "knowledgeId": request.knowledge_id,
                "sourceId": revision["content"]["source"]["sourceId"],
                "collectionId": revision["content"]["source"]["collectionId"],
                "revisionId": request.revision_id,
                "revisionDigest": request.revision_digest,
                "snapshotId": request.snapshot_id,
                "documentId": document["documentId"],
                "documentVersion": document["documentVersion"],
                "documentDigest": document["contentDigest"],
                "chunkId": chunk["chunkId"],
                "chunkDigest": chunk["contentDigest"],
            }
            citations.append(
                {"citationId": _stable_id("knowledge-citation", identity), **identity}
            )
        state = "RETRIEVED" if citations else "NO_RESULT"
        reason = None if citations else "NO_RESULT"
        return finalize(freshness, state, reason, citations)

    def retrieve_with_resource_use(
        self,
        scope: KnowledgeScope,
        request: AttemptKnowledgeRequest,
        resource_use_service: ResourceUseApplicationService,
        resource_use_binding: ResourceUseBinding,
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Use the durable two-stage PostgreSQL boundary around Qdrant."""
        return self.retrieve(
            scope,
            request,
            resource_use_service=resource_use_service,
            resource_use_binding=resource_use_binding,
            observed_at=observed_at,
        )

    def _failure(self, scope, request, record, snapshot, freshness, state, reason):
        return self._result(
            scope, request, record, snapshot, freshness, state, reason, []
        )

    def _result(
        self,
        scope,
        request,
        record,
        snapshot,
        freshness,
        state,
        reason,
        citations,
        *,
        persist: bool = True,
    ):
        semantic = {
            "schemaVersion": "attempt-knowledge-evidence.v1",
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "attemptId": request.attempt_id,
            "bindingId": request.binding_id,
            "authorizationDecisionId": request.authorization_decision_id,
            "knowledgeId": request.knowledge_id,
            "revisionId": request.revision_id,
            "revisionDigest": request.revision_digest,
            "snapshotId": request.snapshot_id,
            "queryDigest": canonical_digest(request.query, domain="knowledge-query.v1"),
            "retrievalState": state,
            "freshness": freshness,
            "reason": reason,
            "citations": citations,
        }
        evidence_id = _stable_id("attempt-knowledge-evidence", semantic)
        evidence = {"evidenceId": evidence_id, **semantic}
        evidence["evidenceDigest"] = canonical_digest(
            evidence, domain="attempt-knowledge-evidence.v1"
        )
        if persist:
            self.evidence.append_evidence(evidence)
        source = next(
            item
            for item in record["revisions"]
            if item["revisionId"] == request.revision_id
        )["content"]["source"]
        return {
            "knowledgeName": record["name"],
            "source": source,
            "collection": {"collectionId": source["collectionId"]},
            "revision": {
                "revisionId": request.revision_id,
                "digest": request.revision_digest,
            },
            "indexSnapshot": {
                "snapshotId": request.snapshot_id,
                "indexDigest": snapshot["indexDigest"],
            },
            "freshness": freshness,
            "binding": {
                "bindingId": request.binding_id,
                "attemptId": request.attempt_id,
                "digitalEmployeeInstanceId": request.digital_employee_instance_id,
                "agentInstanceId": request.agent_instance_id,
            },
            "authorizationState": "ALLOW",
            "retrievalState": state,
            "citations": citations,
            "evidence": evidence,
            "reason": reason,
        }

    @staticmethod
    def _response_from_evidence(request, record, snapshot, evidence):
        source = next(
            item
            for item in record["revisions"]
            if item["revisionId"] == request.revision_id
        )["content"]["source"]
        return {
            "knowledgeName": record["name"],
            "source": source,
            "collection": {"collectionId": source["collectionId"]},
            "revision": {
                "revisionId": request.revision_id,
                "digest": request.revision_digest,
            },
            "indexSnapshot": {
                "snapshotId": request.snapshot_id,
                "indexDigest": snapshot["indexDigest"],
            },
            "freshness": evidence["freshness"],
            "binding": {
                "bindingId": request.binding_id,
                "attemptId": request.attempt_id,
                "digitalEmployeeInstanceId": request.digital_employee_instance_id,
                "agentInstanceId": request.agent_instance_id,
            },
            "authorizationState": "ALLOW",
            "retrievalState": evidence["retrievalState"],
            "citations": evidence["citations"],
            "evidence": evidence,
            "reason": evidence["reason"],
        }

    def readback(self, scope: KnowledgeScope, evidence_id: str) -> dict[str, Any]:
        value = self.evidence.get_evidence(scope, evidence_id)
        if value is None:
            raise AttemptKnowledgeFailure("EVIDENCE_NOT_FOUND")
        return value
