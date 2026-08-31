"""Authoritative Knowledge lifecycle, indexing, recovery and purge service."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from agent_console.knowledge_ingestion import deterministic_vector, ingest_text
from agent_console.knowledge_pack import canonical_digest, identifier, normalize_text
from agent_console.knowledge_qdrant import QdrantKnowledgeError, QdrantKnowledgeIndex
from agent_console.knowledge_repository import KnowledgeRepository, KnowledgeScope


class KnowledgeLifecycleFailure(ValueError):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def identity(prefix: str) -> str:
    return f"{prefix}:{uuid4()}"


class KnowledgeLifecycleService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        qdrant: QdrantKnowledgeIndex | None = None,
    ) -> None:
        self.repository = repository
        self.qdrant = qdrant

    @staticmethod
    def scope(namespace: str, security_domain: str) -> KnowledgeScope:
        return KnowledgeScope(
            identifier(namespace, "INVALID_SCOPE"),
            identifier(security_domain, "INVALID_SCOPE"),
        )

    def _fact(self, event: str, actor: str, **values: Any) -> dict[str, Any]:
        return {
            "factId": identity("knowledge-fact"),
            "event": event,
            "actor": identifier(actor, "INVALID_ACTOR"),
            "recordedAt": now(),
            **values,
        }

    def create(
        self,
        scope: KnowledgeScope,
        actor: str,
        name: str,
        source: dict[str, Any],
        *,
        knowledge_id: str | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        source_id = identifier(source.get("sourceId"), "INVALID_SOURCE_ID")
        document_id = identifier(source.get("documentId"), "INVALID_DOCUMENT_ID")
        chunks, content_digest = ingest_text(document_id, source.get("content"))
        revision_id = (
            identifier(revision_id, "INVALID_REVISION_ID")
            if revision_id is not None
            else identity("knowledge-revision")
        )
        content = {
            "name": normalize_text(name, "INVALID_NAME"),
            "source": {
                "sourceId": source_id,
                "kind": identifier(source.get("kind", "TEXT"), "INVALID_SOURCE_KIND"),
                "provenance": identifier(
                    source.get("provenance"), "INVALID_PROVENANCE"
                ),
            },
            "documents": [
                {
                    "documentId": document_id,
                    "contentDigest": content_digest,
                    "chunks": chunks,
                }
            ],
        }
        digest = canonical_digest(
            {
                "scope": {
                    "namespace": scope.namespace,
                    "securityDomain": scope.security_domain,
                },
                "content": content,
            },
            domain="knowledge-revision.v1",
        )
        knowledge_id = (
            identifier(knowledge_id, "INVALID_KNOWLEDGE_ID")
            if knowledge_id is not None
            else identity("knowledge")
        )
        fact = self._fact(
            "KNOWLEDGE_DRAFT_CREATED", actor, revisionId=revision_id, digest=digest
        )
        record = {
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "knowledgeId": knowledge_id,
            "name": content["name"],
            "aggregateVersion": 1,
            "lifecycleState": "DRAFT",
            "archived": False,
            "currentDraftRevisionId": revision_id,
            "publishedRevisionId": None,
            "revisions": [
                {
                    "revisionId": revision_id,
                    "predecessorRevisionId": None,
                    "state": "DRAFT",
                    "digest": digest,
                    "content": content,
                    "createdAt": now(),
                }
            ],
            "ingestionJobs": [],
            "indexSnapshots": [],
            "retrievals": [],
            "activeIndexSnapshotId": None,
            "purge": None,
            "facts": [fact],
            "limitations": [
                "Qdrant is a derived index",
                "No cross-store atomicity or exactly-once claim",
            ],
        }
        return self.project(self.repository.create(record))

    def _change(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        event: str,
        mutate: Any,
    ) -> dict[str, Any]:
        record = self.repository.get(scope, knowledge_id)
        if record["aggregateVersion"] != expected_version:
            raise KnowledgeLifecycleFailure("STALE_KNOWLEDGE")
        changed = copy.deepcopy(record)
        fact = self._fact(event, actor)
        mutate(changed, fact)
        changed["aggregateVersion"] += 1
        return self.project(
            self.repository.replace(
                changed, expected_version=expected_version, fact=fact
            )
        )

    @staticmethod
    def _draft(record: dict[str, Any]) -> dict[str, Any]:
        revision = next(
            (
                item
                for item in record["revisions"]
                if item["revisionId"] == record["currentDraftRevisionId"]
            ),
            None,
        )
        if revision is None:
            raise KnowledgeLifecycleFailure("KNOWLEDGE_DRAFT_REQUIRED")
        return revision

    def validate(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            draft = self._draft(record)
            if draft["state"] != "DRAFT":
                raise KnowledgeLifecycleFailure("INVALID_LIFECYCLE_TRANSITION")
            draft["state"] = "VALIDATED"
            record["lifecycleState"] = "VALIDATED"
            fact.update(revisionId=draft["revisionId"], digest=draft["digest"])

        return self._change(
            scope, knowledge_id, actor, expected_version, "KNOWLEDGE_VALIDATED", mutate
        )

    def review(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        digest: str,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            draft = self._draft(record)
            if draft["state"] != "VALIDATED" or draft["digest"] != digest:
                raise KnowledgeLifecycleFailure("EXACT_DIGEST_REQUIRED")
            draft["state"] = "HUMAN_REVIEWED"
            record["lifecycleState"] = "HUMAN_REVIEWED"
            fact.update(
                revisionId=draft["revisionId"], digest=digest, decision="APPROVE"
            )

        return self._change(
            scope,
            knowledge_id,
            actor,
            expected_version,
            "KNOWLEDGE_HUMAN_REVIEWED",
            mutate,
        )

    def publish(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        digest: str,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            draft = self._draft(record)
            if draft["state"] != "HUMAN_REVIEWED" or draft["digest"] != digest:
                raise KnowledgeLifecycleFailure("EXACT_REVIEW_REQUIRED")
            draft["state"] = "PUBLISHED"
            record["publishedRevisionId"] = draft["revisionId"]
            record["currentDraftRevisionId"] = None
            record["lifecycleState"] = "PUBLISHED"
            fact.update(revisionId=draft["revisionId"], digest=digest)

        return self._change(
            scope, knowledge_id, actor, expected_version, "KNOWLEDGE_PUBLISHED", mutate
        )

    def successor(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        source_content: str,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            published = next(
                (
                    item
                    for item in record["revisions"]
                    if item["revisionId"] == record["publishedRevisionId"]
                ),
                None,
            )
            if published is None or record["currentDraftRevisionId"] is not None:
                raise KnowledgeLifecycleFailure("PUBLISHED_REVISION_REQUIRED")
            content = copy.deepcopy(published["content"])
            document = content["documents"][0]
            chunks, content_digest = ingest_text(document["documentId"], source_content)
            document.update(chunks=chunks, contentDigest=content_digest)
            revision_id = identity("knowledge-revision")
            digest = canonical_digest(
                {
                    "scope": {
                        "namespace": scope.namespace,
                        "securityDomain": scope.security_domain,
                    },
                    "content": content,
                    "predecessorRevisionId": published["revisionId"],
                },
                domain="knowledge-revision.v1",
            )
            record["revisions"].append(
                {
                    "revisionId": revision_id,
                    "predecessorRevisionId": published["revisionId"],
                    "state": "DRAFT",
                    "digest": digest,
                    "content": content,
                    "createdAt": now(),
                }
            )
            record["currentDraftRevisionId"] = revision_id
            record["lifecycleState"] = "DRAFT"
            fact.update(
                revisionId=revision_id,
                predecessorRevisionId=published["revisionId"],
                digest=digest,
            )

        return self._change(
            scope,
            knowledge_id,
            actor,
            expected_version,
            "KNOWLEDGE_SUCCESSOR_CREATED",
            mutate,
        )

    def ingest(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            revision = next(
                (
                    item
                    for item in record["revisions"]
                    if item["revisionId"] == record["publishedRevisionId"]
                ),
                None,
            )
            if revision is None:
                raise KnowledgeLifecycleFailure("PUBLISHED_REVISION_REQUIRED")
            job_id, snapshot_id = identity("ingestion-job"), identity("index-snapshot")
            job = {
                "jobId": job_id,
                "revisionId": revision["revisionId"],
                "status": "RUNNING",
                "highWaterMark": len(record["facts"]),
                "startedAt": now(),
                "completedAt": None,
            }
            record["ingestionJobs"].append(job)
            points = []
            for document in revision["content"]["documents"]:
                for chunk in document["chunks"]:
                    points.append(
                        {
                            "id": str(uuid5(NAMESPACE_URL, chunk["contentDigest"])),
                            "vector": deterministic_vector(chunk["content"]),
                            "payload": {
                                "namespace": scope.namespace,
                                "securityDomain": scope.security_domain,
                                "knowledgeId": knowledge_id,
                                "revisionId": revision["revisionId"],
                                "revisionDigest": revision["digest"],
                                "snapshotId": snapshot_id,
                                "documentId": document["documentId"],
                                "documentDigest": document["contentDigest"],
                                "chunkId": chunk["chunkId"],
                                "chunkDigest": chunk["contentDigest"],
                            },
                        }
                    )
            try:
                if self.qdrant is None:
                    raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")
                self.qdrant.ensure_collection()
                self.qdrant.upsert(points)
                job.update(status="COMPLETED", completedAt=now())
                record["indexSnapshots"].append(
                    {
                        "snapshotId": snapshot_id,
                        "revisionId": revision["revisionId"],
                        "revisionDigest": revision["digest"],
                        "indexDigest": canonical_digest(
                            [point["payload"] for point in points],
                            domain="knowledge-index.v1",
                        ),
                        "qdrantReference": f"{self.qdrant.collection}:{snapshot_id}",
                        "status": "ACTIVE",
                        "createdAt": now(),
                    }
                )
                record["activeIndexSnapshotId"] = snapshot_id
                record["lifecycleState"] = "AVAILABLE"
            except QdrantKnowledgeError:
                job["status"] = "RECOVERY_REQUIRED"
                record["lifecycleState"] = "RECOVERY_REQUIRED"
            fact.update(jobId=job_id, snapshotId=snapshot_id, status=job["status"])

        return self._change(
            scope,
            knowledge_id,
            actor,
            expected_version,
            "KNOWLEDGE_INGESTION_RECORDED",
            mutate,
        )

    def rebuild(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
    ) -> dict[str, Any]:
        return self.ingest(scope, knowledge_id, actor, expected_version)

    def retrieve(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        authorization: str,
        authorization_decision_id: str,
        query: str,
    ) -> dict[str, Any]:
        if authorization != "ALLOW":
            raise KnowledgeLifecycleFailure("KNOWLEDGE_ACCESS_DENIED")
        authorization_decision_id = identifier(
            authorization_decision_id, "KNOWLEDGE_ACCESS_DENIED"
        )
        query = normalize_text(query, "INVALID_RETRIEVAL_QUERY", limit=2_000)

        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            revision = next(
                (
                    item
                    for item in record["revisions"]
                    if item["revisionId"] == record["publishedRevisionId"]
                ),
                None,
            )
            snapshot_id = record["activeIndexSnapshotId"]
            if revision is None or snapshot_id is None or self.qdrant is None:
                raise KnowledgeLifecycleFailure("KNOWLEDGE_UNAVAILABLE")
            try:
                hits = self.qdrant.search(
                    deterministic_vector(query),
                    namespace=scope.namespace,
                    security_domain=scope.security_domain,
                    knowledge_id=knowledge_id,
                    snapshot_id=snapshot_id,
                    limit=5,
                )
            except QdrantKnowledgeError as exc:
                raise KnowledgeLifecycleFailure("KNOWLEDGE_UNAVAILABLE") from exc
            chunks = {
                chunk["chunkId"]: (document, chunk)
                for document in revision["content"]["documents"]
                for chunk in document["chunks"]
            }
            citations = []
            for hit in hits:
                payload = hit.get("payload", {})
                match = chunks.get(payload.get("chunkId"))
                if match is None or payload.get("revisionDigest") != revision["digest"]:
                    continue
                document, chunk = match
                citations.append(
                    {
                        "citationId": identity("citation"),
                        "knowledgeId": knowledge_id,
                        "revisionId": revision["revisionId"],
                        "revisionDigest": revision["digest"],
                        "sourceId": revision["content"]["source"]["sourceId"],
                        "provenance": revision["content"]["source"]["provenance"],
                        "documentId": document["documentId"],
                        "documentDigest": document["contentDigest"],
                        "chunkId": chunk["chunkId"],
                        "chunkDigest": chunk["contentDigest"],
                        "content": chunk["content"],
                    }
                )
            retrieval = {
                "retrievalId": identity("retrieval"),
                "authorizationDecisionId": authorization_decision_id,
                "queryDigest": canonical_digest(query, domain="knowledge-query.v1"),
                "snapshotId": snapshot_id,
                "citations": citations,
                "recordedAt": now(),
            }
            record.setdefault("retrievals", []).append(retrieval)
            fact.update(
                retrievalId=retrieval["retrievalId"],
                authorizationDecisionId=authorization_decision_id,
                citationIds=[item["citationId"] for item in citations],
            )

        return self._change(
            scope,
            knowledge_id,
            actor,
            expected_version,
            "KNOWLEDGE_RETRIEVAL_RECORDED",
            mutate,
        )

    def recover(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
    ) -> dict[str, Any]:
        record = self.repository.get(scope, knowledge_id)
        if record["lifecycleState"] != "RECOVERY_REQUIRED":
            raise KnowledgeLifecycleFailure("RECOVERY_NOT_REQUIRED")
        return self.ingest(scope, knowledge_id, actor, expected_version)

    def archive(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
    ) -> dict[str, Any]:
        def mutate(record: dict[str, Any], fact: dict[str, Any]) -> None:
            record["archived"] = True
            record["lifecycleState"] = "ARCHIVED"

        return self._change(
            scope, knowledge_id, actor, expected_version, "KNOWLEDGE_ARCHIVED", mutate
        )

    def purge(
        self,
        scope: KnowledgeScope,
        knowledge_id: str,
        actor: str,
        expected_version: int,
        authorization_id: str,
        reason_classification: str,
    ) -> dict[str, Any]:
        record = self.repository.get(scope, knowledge_id)
        if record["aggregateVersion"] != expected_version:
            raise KnowledgeLifecycleFailure("STALE_KNOWLEDGE")
        authorization_id = identifier(authorization_id, "PURGE_AUTHORIZATION_REQUIRED")
        reason_classification = identifier(
            reason_classification, "PURGE_REASON_REQUIRED"
        )
        snapshot_ids = [item["snapshotId"] for item in record["indexSnapshots"]]
        try:
            if self.qdrant is None:
                raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")
            for snapshot_id in snapshot_ids:
                self.qdrant.delete_snapshot(
                    scope.namespace, scope.security_domain, knowledge_id, snapshot_id
                )
        except QdrantKnowledgeError:

            def failed(changed: dict[str, Any], fact: dict[str, Any]) -> None:
                changed["purge"] = {
                    "authorizationId": authorization_id,
                    "reasonClassification": reason_classification,
                    "status": "RECOVERY_REQUIRED",
                    "remainingSnapshotIds": snapshot_ids,
                }
                changed["lifecycleState"] = "RECOVERY_REQUIRED"
                fact.update(status="RECOVERY_REQUIRED")

            return self._change(
                scope,
                knowledge_id,
                actor,
                expected_version,
                "KNOWLEDGE_PURGE_RECORDED",
                failed,
            )
        tombstone = {
            "knowledgeId": knowledge_id,
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "revisionDigests": [item["digest"] for item in record["revisions"]],
            "authorizationId": authorization_id,
            "reasonClassification": reason_classification,
            "status": "COMPLETED",
            "purgedAt": now(),
        }
        self.repository.tombstone(
            scope, knowledge_id, expected_version=expected_version, tombstone=tombstone
        )
        return {"purge": tombstone}

    def get(self, scope: KnowledgeScope, knowledge_id: str) -> dict[str, Any]:
        return self.project(self.repository.get(scope, knowledge_id))

    def list(self, scope: KnowledgeScope) -> list[dict[str, Any]]:
        return [self.project(item)["knowledge"] for item in self.repository.list(scope)]

    @staticmethod
    def project(record: dict[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(record)
        technical = {
            "knowledgeId": value["knowledgeId"],
            "namespace": value["namespace"],
            "securityDomain": value["securityDomain"],
            "aggregateVersion": value["aggregateVersion"],
            "publishedRevisionId": value["publishedRevisionId"],
            "activeIndexSnapshotId": value["activeIndexSnapshotId"],
            "revisionDigests": [
                {
                    "revisionId": item["revisionId"],
                    "digest": item["digest"],
                    "state": item["state"],
                }
                for item in value["revisions"]
            ],
        }
        return {
            "knowledge": value,
            "productProjection": {
                "knowledgeId": value["knowledgeId"],
                "name": value["name"],
                "state": value["lifecycleState"],
                "documentCount": sum(
                    len(item["content"]["documents"])
                    for item in value["revisions"][-1:]
                ),
            },
            "technicalProjection": technical,
        }
