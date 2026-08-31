"""Authorization-first deterministic Knowledge quality and operations."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from agent_console.knowledge_ingestion import deterministic_vector
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_pack import normalize_text
from agent_console.knowledge_qdrant import QdrantKnowledgeError, QdrantKnowledgeIndex
from agent_console.knowledge_repository import (
    KnowledgeConflict,
    KnowledgeNotFound,
    KnowledgeRepository,
    KnowledgeScope,
)

TOKENIZER_VERSION = "CJK_BIGRAM_V1"
RETRIEVAL_POLICY_VERSION = "KNOWLEDGE_QUALITY_RRF_V1"
FUSION_K = 60
SUMMARY_PROVIDER = "DETERMINISTIC_EXTRACTIVE_V1"
SHINGLE_VERSION = "NORMALIZED_TOKEN_SHINGLE_V1"
NEAR_DUPLICATE_THRESHOLD = 0.6
MAX_TOP_K = 20
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_JSONL_BYTES = 5 * 1024 * 1024
MAX_JSONL_RECORDS = 1000
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class KnowledgeQualityFailure(ValueError):
    pass


def tokenize(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    words = _WORD.findall(normalized)
    cjk = "".join(_CJK.findall(normalized))
    cjk_tokens = (
        list(cjk) if len(cjk) == 1 else [cjk[i : i + 2] for i in range(len(cjk) - 1)]
    )
    return tuple(words + cjk_tokens)


def _digest(value: Any, domain: str) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(f"{domain}\n{payload}".encode()).hexdigest()


def _identity(prefix: str, digest: str) -> str:
    return f"{prefix}:{digest[:24]}"


class KnowledgeQualityService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        qdrant: QdrantKnowledgeIndex | None = None,
    ) -> None:
        self.repository = repository
        self.qdrant = qdrant

    @staticmethod
    def _chunks(record: dict[str, Any]) -> list[dict[str, Any]]:
        revision_id = record.get("publishedRevisionId") or record.get(
            "currentDraftRevisionId"
        )
        revision = next(
            (r for r in record["revisions"] if r["revisionId"] == revision_id), None
        )
        if revision is None:
            return []
        source = revision["content"]["source"]
        return [
            {
                "knowledgeId": record["knowledgeId"],
                "revisionId": revision["revisionId"],
                "revisionDigest": revision["digest"],
                "sourceId": source["sourceId"],
                "contentType": source["kind"],
                "provenance": source["provenance"],
                "documentId": document["documentId"],
                "documentDigest": document["contentDigest"],
                "chunkId": chunk["chunkId"],
                "chunkDigest": chunk["contentDigest"],
                "content": chunk["content"],
                "snapshotId": record.get("activeIndexSnapshotId"),
            }
            for document in revision["content"]["documents"]
            for chunk in document["chunks"]
        ]

    def search(
        self,
        scope: KnowledgeScope,
        *,
        query: str,
        mode: str = "HYBRID",
        top_k: int = 5,
        knowledge_id: str | None = None,
        source_id: str | None = None,
        document_id: str | None = None,
        content_type: str | None = None,
        revision_id: str | None = None,
        snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        query = normalize_text(query, "INVALID_RETRIEVAL_QUERY", limit=2000)
        mode = mode.upper()
        if mode not in {"LEXICAL", "SEMANTIC", "HYBRID"}:
            raise KnowledgeQualityFailure("INVALID_RETRIEVAL_MODE")
        if isinstance(top_k, bool) or not 1 <= top_k <= MAX_TOP_K:
            raise KnowledgeQualityFailure("RESULT_LIMIT_EXCEEDED")
        records = self.repository.list(scope)
        if knowledge_id is not None:
            records = [item for item in records if item["knowledgeId"] == knowledge_id]
        chunks = [chunk for record in records for chunk in self._chunks(record)]
        filters = {
            "sourceId": source_id,
            "documentId": document_id,
            "contentType": content_type,
            "revisionId": revision_id,
            "snapshotId": snapshot_id,
        }
        chunks = [
            chunk
            for chunk in chunks
            if all(
                value is None or chunk[key] == value for key, value in filters.items()
            )
        ]
        allowed_knowledge = {chunk["knowledgeId"] for chunk in chunks}
        records = [r for r in records if r["knowledgeId"] in allowed_knowledge]

        def canonical(chunk: dict[str, Any]) -> tuple[str, str, str]:
            return chunk["knowledgeId"], chunk["documentId"], chunk["chunkId"]

        query_tokens = set(tokenize(query))
        lexical = sorted(
            (
                (
                    len(query_tokens & set(tokenize(c["content"])))
                    / max(1, len(query_tokens)),
                    c,
                )
                for c in chunks
            ),
            key=lambda item: (-item[0], canonical(item[1])),
        )
        lexical = [item for item in lexical if item[0] > 0]
        semantic: list[tuple[float, dict[str, Any]]] = []
        if mode in {"SEMANTIC", "HYBRID"}:
            if self.qdrant is None:
                raise KnowledgeQualityFailure("QDRANT_UNAVAILABLE")
            for record in records:
                snapshot = record.get("activeIndexSnapshotId")
                if snapshot is None:
                    continue
                try:
                    hits = self.qdrant.search(
                        deterministic_vector(query),
                        namespace=scope.namespace,
                        security_domain=scope.security_domain,
                        knowledge_id=record["knowledgeId"],
                        snapshot_id=snapshot,
                        limit=MAX_TOP_K,
                    )
                except QdrantKnowledgeError as exc:
                    raise KnowledgeQualityFailure("QDRANT_UNAVAILABLE") from exc
                by_id = {
                    c["chunkId"]: c
                    for c in chunks
                    if c["knowledgeId"] == record["knowledgeId"]
                }
                semantic.extend(
                    (float(hit.get("score", 0)), by_id[hit["payload"]["chunkId"]])
                    for hit in hits
                    if hit.get("payload", {}).get("chunkId") in by_id
                )
            semantic.sort(key=lambda item: (-item[0], canonical(item[1])))
        lexical_rank = {canonical(c): rank for rank, (_, c) in enumerate(lexical, 1)}
        semantic_rank = {canonical(c): rank for rank, (_, c) in enumerate(semantic, 1)}
        if mode == "LEXICAL":
            ranked = [
                (score, c, lexical_rank[canonical(c)], None) for score, c in lexical
            ]
        elif mode == "SEMANTIC":
            ranked = [
                (score, c, None, semantic_rank[canonical(c)]) for score, c in semantic
            ]
        else:
            candidates = {canonical(c): c for _, c in lexical + semantic}
            ranked = []
            for key, chunk in candidates.items():
                lr, sr = lexical_rank.get(key), semantic_rank.get(key)
                score = (1 / (FUSION_K + lr) if lr else 0) + (
                    1 / (FUSION_K + sr) if sr else 0
                )
                ranked.append((score, chunk, lr, sr))
            ranked.sort(key=lambda item: (-item[0], canonical(item[1])))
        results = []
        for rank, (score, chunk, lexical_position, semantic_position) in enumerate(
            ranked[:top_k], 1
        ):
            results.append(
                {
                    "rank": rank,
                    "score": round(score, 8),
                    "classification": mode,
                    "lexicalRank": lexical_position,
                    "semanticRank": semantic_position,
                    "citation": chunk,
                }
            )
        return {
            "classification": mode,
            "queryDigest": _digest(query, "knowledge-quality-query.v1"),
            "topK": top_k,
            "tokenizerVersion": TOKENIZER_VERSION,
            "retrievalPolicyVersion": RETRIEVAL_POLICY_VERSION,
            "fusion": {
                "algorithm": "RECIPROCAL_RANK_FUSION",
                "k": FUSION_K,
                "absentRankContribution": 0,
            },
            "results": results,
            "filters": {
                key: value for key, value in filters.items() if value is not None
            },
        }

    def put_entity(
        self, scope: KnowledgeScope, entity_type: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        semantic = {
            "namespace": scope.namespace,
            "securityDomain": scope.security_domain,
            "entityType": entity_type,
            "body": body,
        }
        digest = _digest(semantic, f"knowledge-quality-{entity_type.lower()}.v1")
        record = {
            **semantic,
            "entityId": _identity(entity_type.lower().replace("_", "-"), digest),
            "digest": digest,
        }
        return self.repository.put_quality_entity(record)

    def _entity(
        self, scope: KnowledgeScope, entity_type: str, entity_id: str
    ) -> dict[str, Any]:
        match = next(
            (
                item
                for item in self.repository.list_quality_entities(scope, entity_type)
                if item["entityId"] == entity_id
            ),
            None,
        )
        if match is None:
            raise KnowledgeQualityFailure("KNOWLEDGE_OPERATION_NOT_FOUND")
        return match

    def _replace_entity(
        self, record: dict[str, Any], body: dict[str, Any]
    ) -> dict[str, Any]:
        changed = {**record, "body": body}
        changed["digest"] = _digest(
            {
                "namespace": changed["namespace"],
                "securityDomain": changed["securityDomain"],
                "entityType": changed["entityType"],
                "body": body,
            },
            f"knowledge-quality-{changed['entityType'].lower()}.v1",
        )
        return self.repository.put_quality_entity(changed)

    def evaluate(self, scope: KnowledgeScope, body: dict[str, Any]) -> dict[str, Any]:
        cases = body.get("cases")
        if not isinstance(cases, list) or not cases:
            raise KnowledgeQualityFailure("EVALUATION_CASES_REQUIRED")
        dataset = self.put_entity(
            scope,
            "EVALUATION_DATASET",
            {"version": body.get("datasetVersion", "1"), "cases": cases},
        )
        configuration = self.put_entity(
            scope,
            "RETRIEVAL_CONFIGURATION",
            {
                "mode": body.get("mode", "HYBRID"),
                "topK": int(body.get("topK", 5)),
                "retrievalPolicyVersion": RETRIEVAL_POLICY_VERSION,
                "tokenizerVersion": TOKENIZER_VERSION,
                "fusionParameters": {"k": FUSION_K},
            },
        )
        facts, measurable = [], True
        for case in cases:
            expected = case.get("expectedChunkIds")
            if not isinstance(expected, list) or not expected:
                measurable = False
                facts.append({"caseId": case.get("caseId"), "status": "NOT_MEASURABLE"})
                continue
            result = self.search(
                scope,
                query=case["query"],
                mode=body.get("mode", "HYBRID"),
                top_k=int(body.get("topK", 5)),
            )
            actual = [item["citation"]["chunkId"] for item in result["results"]]
            relevant = set(expected)
            hits = [item for item in actual if item in relevant]
            first = next(
                (i for i, item in enumerate(actual, 1) if item in relevant), None
            )
            facts.append(
                {
                    "caseId": case.get("caseId"),
                    "status": "MEASURABLE",
                    "recallAtK": len(set(hits)) / len(relevant),
                    "precisionAtK": len(hits) / len(actual) if actual else 0.0,
                    "mrr": 1 / first if first else 0.0,
                    "citationCompleteness": 1.0
                    if all(item.get("citation") for item in result["results"])
                    else 0.0,
                    "unauthorizedResultCount": 0,
                }
            )
        metrics = {"status": "MEASURABLE" if measurable else "NOT_MEASURABLE"}
        if measurable:
            for name in ("recallAtK", "precisionAtK", "mrr", "citationCompleteness"):
                metrics[name] = sum(f[name] for f in facts) / len(facts)
            metrics["unauthorizedResultCount"] = 0
        binding = {
            "datasetVersionId": dataset["entityId"],
            "datasetDigest": dataset["digest"],
            "retrievalConfigurationId": configuration["entityId"],
            "retrievalConfigurationDigest": configuration["digest"],
            "retrievalPolicyVersion": RETRIEVAL_POLICY_VERSION,
            "tokenizerVersion": TOKENIZER_VERSION,
            "fusionParameters": {"k": FUSION_K},
            "knowledgeRevision": body.get("knowledgeRevision", "CURRENT_AUTHORIZED"),
            "postgresAuthorityIdentity": "knowledge-postgresql-v1",
            "qdrantSnapshotIdentity": body.get(
                "qdrantSnapshotIdentity", "AUTHORIZED_ACTIVE_SNAPSHOTS"
            ),
        }
        comparison = None
        comparison_id = body.get("comparisonToRunId")
        if comparison_id:
            before = self._entity(scope, "EVALUATION_RUN", comparison_id)
            before_metrics = before["body"]["metrics"]
            if (
                metrics["status"] != "MEASURABLE"
                or before_metrics["status"] != "MEASURABLE"
            ):
                comparison = {
                    "status": "NOT_MEASURABLE",
                    "beforeRunId": before["entityId"],
                    "beforeDatasetVersionId": before["body"]["binding"][
                        "datasetVersionId"
                    ],
                    "reason": "GROUND_TRUTH_REQUIRED_FOR_BOTH_RUNS",
                }
            else:
                names = ("recallAtK", "precisionAtK", "mrr", "citationCompleteness")
                comparison = {
                    "status": "MEASURABLE",
                    "beforeRunId": before["entityId"],
                    "beforeDatasetVersionId": before["body"]["binding"][
                        "datasetVersionId"
                    ],
                    "deltas": {
                        name: round(metrics[name] - before_metrics[name], 8)
                        for name in names
                    },
                    "claim": "NO_IMPROVEMENT_CLAIM",
                }
        run = self.put_entity(
            scope,
            "EVALUATION_RUN",
            {
                "binding": binding,
                "facts": facts,
                "metrics": metrics,
                "comparison": comparison,
            },
        )
        self.put_entity(scope, "METRIC_FACT", {"runId": run["entityId"], **metrics})
        return run

    def summarize(self, scope: KnowledgeScope, knowledge_id: str) -> dict[str, Any]:
        record = self.repository.get(scope, knowledge_id)
        chunks = self._chunks(record)
        if not chunks:
            raise KnowledgeQualityFailure("KNOWLEDGE_NOT_FOUND")
        selected = chunks[: min(3, len(chunks))]
        text = " ".join(item["content"].strip() for item in selected)
        return self.put_entity(
            scope,
            "SUMMARY",
            {
                "knowledgeId": knowledge_id,
                "provider": SUMMARY_PROVIDER,
                "model": "NOT_APPLICABLE",
                "text": text,
                "generatedContentDigest": _digest(text, "knowledge-summary-content.v1"),
                "citations": selected,
            },
        )

    def duplicates(self, scope: KnowledgeScope) -> list[dict[str, Any]]:
        chunks = [
            chunk
            for record in self.repository.list(scope)
            for chunk in self._chunks(record)
        ]
        candidates = []
        for index, left in enumerate(chunks):
            for right in chunks[index + 1 :]:
                a, b = set(tokenize(left["content"])), set(tokenize(right["content"]))
                similarity = len(a & b) / len(a | b) if a | b else 1.0
                left_normalized_digest = _digest(
                    list(tokenize(left["content"])), "knowledge-duplicate-normalized.v1"
                )
                right_normalized_digest = _digest(
                    list(tokenize(right["content"])),
                    "knowledge-duplicate-normalized.v1",
                )
                exact = left_normalized_digest == right_normalized_digest
                if exact or similarity >= NEAR_DUPLICATE_THRESHOLD:
                    candidates.append(
                        self.put_entity(
                            scope,
                            "DUPLICATE_CANDIDATE",
                            {
                                "left": left,
                                "right": right,
                                "classification": "EXACT" if exact else "NEAR",
                                "similarity": similarity,
                                "normalizedDigest": left_normalized_digest
                                if exact
                                else None,
                                "algorithmVersion": SHINGLE_VERSION,
                                "threshold": NEAR_DUPLICATE_THRESHOLD,
                                "humanDecision": "PENDING",
                            },
                        )
                    )
        return candidates

    def duplicate_queue(self, scope: KnowledgeScope) -> list[dict[str, Any]]:
        decisions = self.repository.list_quality_entities(scope, "DUPLICATE_DECISION")
        decided = {item["body"]["candidateId"]: item for item in decisions}
        return [
            {**candidate, "decision": decided.get(candidate["entityId"])}
            for candidate in self.repository.list_quality_entities(
                scope, "DUPLICATE_CANDIDATE"
            )
        ]

    def decide_duplicate(
        self,
        scope: KnowledgeScope,
        *,
        candidate_id: str,
        classification: str,
        actor: str,
    ) -> dict[str, Any]:
        candidate = self._entity(scope, "DUPLICATE_CANDIDATE", candidate_id)
        classification = classification.upper()
        if classification not in {"DUPLICATE", "DISTINCT", "NEEDS_INVESTIGATION"}:
            raise KnowledgeQualityFailure("INVALID_DUPLICATE_DECISION")
        return self.put_entity(
            scope,
            "DUPLICATE_DECISION",
            {
                "candidateId": candidate_id,
                "candidateDigest": candidate["digest"],
                "classification": classification,
                "actor": actor,
                "effect": "RECORD_ONLY_NO_CONTENT_MUTATION",
            },
        )

    def import_preview(
        self, scope: KnowledgeScope, *, format: str, content: str
    ) -> dict[str, Any]:
        if (
            not isinstance(content, str)
            or "\x00" in content
            or any(ord(c) < 32 and c not in "\n\r\t" for c in content)
        ):
            raise KnowledgeQualityFailure("INVALID_IMPORT_CONTENT")
        size = len(content.encode("utf-8"))
        format = format.lower()
        if format in {"txt", "md"}:
            if size > MAX_DOCUMENT_BYTES:
                raise KnowledgeQualityFailure("IMPORT_SIZE_EXCEEDED")
            records = [{"name": "Imported document", "content": content}]
        elif format == "jsonl":
            if size > MAX_JSONL_BYTES:
                raise KnowledgeQualityFailure("IMPORT_SIZE_EXCEEDED")
            try:
                raw_records = [
                    json.loads(line) for line in content.splitlines() if line.strip()
                ]
            except json.JSONDecodeError as exc:
                raise KnowledgeQualityFailure("INVALID_JSONL") from exc
            if len(raw_records) > MAX_JSONL_RECORDS or any(
                not isinstance(item, dict) or set(item) != {"name", "content"}
                for item in raw_records
            ):
                raise KnowledgeQualityFailure("INVALID_JSONL")
            records = [
                item
                for item in raw_records
                if isinstance(item["name"], str)
                and bool(item["name"].strip())
                and isinstance(item["content"], str)
                and bool(item["content"].strip())
                and "\x00" not in item["content"]
            ]
            preview_rejected = len(raw_records) - len(records)
        else:
            raise KnowledgeQualityFailure("IMPORT_FORMAT_NOT_ALLOWED")
        if format in {"txt", "md"}:
            preview_rejected = 0
        return self.put_entity(
            scope,
            "IMPORT_JOB",
            {
                "status": "PREVIEW",
                "format": format,
                "recordCount": len(records),
                "inputRecordCount": len(records) + preview_rejected,
                "previewRejectedCount": preview_rejected,
                "bytes": size,
                "records": records,
                "draftOnly": True,
                "retryable": True,
            },
        )

    def execute_import(
        self, scope: KnowledgeScope, import_job_id: str, actor: str
    ) -> dict[str, Any]:
        job = self._entity(scope, "IMPORT_JOB", import_job_id)
        body = dict(job["body"])
        if body["status"] == "COMPLETED":
            return job
        if body["status"] not in {"PREVIEW", "FAILED", "PARTIAL"}:
            raise KnowledgeQualityFailure("IMPORT_NOT_EXECUTABLE")
        body.update(
            status="RUNNING",
            processedCount=body.get("processedCount", 0),
            acceptedCount=body.get("acceptedCount", 0),
            rejectedCount=body.get("rejectedCount", 0),
            importedKnowledgeIds=body.get("importedKnowledgeIds", []),
            retryable=False,
        )
        if body["processedCount"] == 0:
            body["rejectedCount"] = body.get("previewRejectedCount", 0)
        job = self._replace_entity(job, body)
        lifecycle = KnowledgeLifecycleService(self.repository, self.qdrant)
        for ordinal, item in enumerate(body["records"], 1):
            if ordinal <= body["processedCount"]:
                continue
            item_digest = _digest(
                {"jobId": import_job_id, "ordinal": ordinal, "record": item},
                "knowledge-import-record.v1",
            )
            knowledge_id = _identity("knowledge-import", item_digest)
            revision_id = _identity("knowledge-revision-import", item_digest)
            try:
                result = lifecycle.create(
                    scope,
                    actor,
                    item["name"],
                    {
                        "sourceId": _identity("source-import", item_digest),
                        "documentId": _identity("document-import", item_digest),
                        "kind": body["format"].upper(),
                        "provenance": import_job_id,
                        "content": item["content"],
                    },
                    knowledge_id=knowledge_id,
                    revision_id=revision_id,
                )["knowledge"]
            except KnowledgeConflict:
                try:
                    result = self.repository.get(scope, knowledge_id)
                except KnowledgeNotFound as exc:
                    body.update(status="FAILED", retryable=True)
                    self._replace_entity(job, body)
                    raise KnowledgeQualityFailure("IMPORT_RETRY_REQUIRED") from exc
            except (ValueError, TypeError):
                body["rejectedCount"] += 1
                body["processedCount"] = ordinal
                body["status"] = "PARTIAL"
                body["retryable"] = True
                job = self._replace_entity(job, body)
                continue
            if result["lifecycleState"] != "DRAFT":
                raise KnowledgeQualityFailure("IMPORT_DRAFT_BOUNDARY_VIOLATION")
            if knowledge_id not in body["importedKnowledgeIds"]:
                body["importedKnowledgeIds"].append(knowledge_id)
                body["acceptedCount"] += 1
            body["processedCount"] = ordinal
            job = self._replace_entity(job, body)
        body["status"] = "COMPLETED" if body["rejectedCount"] == 0 else "PARTIAL"
        body["retryable"] = body["status"] == "PARTIAL"
        body["progress"] = {
            "processed": body["processedCount"],
            "total": body["recordCount"],
        }
        return self._replace_entity(job, body)

    def metadata(self, scope: KnowledgeScope) -> dict[str, list[str]]:
        chunks = [
            chunk
            for record in self.repository.list(scope)
            for chunk in self._chunks(record)
        ]
        return {
            key: sorted({chunk[key] for chunk in chunks if chunk.get(key) is not None})
            for key in (
                "knowledgeId",
                "sourceId",
                "documentId",
                "contentType",
                "revisionId",
                "snapshotId",
            )
        }

    def export(self, scope: KnowledgeScope) -> dict[str, Any]:
        records = self.repository.list(scope)
        documents = [
            {
                "knowledgeId": record["knowledgeId"],
                "revisions": [
                    {"revisionId": r["revisionId"], "digest": r["digest"]}
                    for r in record["revisions"]
                ],
                "citations": [
                    citation
                    for retrieval in record.get("retrievals", [])
                    for citation in retrieval["citations"]
                ],
            }
            for record in records
        ]
        facts = self.repository.list_quality_entities(scope, "METRIC_FACT")
        manifest = {
            "format": "KNOWLEDGE_AUTHORIZED_EXPORT_V1",
            "documents": documents,
            "evaluationFacts": facts,
        }
        return {
            **manifest,
            "digest": _digest(manifest, "knowledge-authorized-export.v1"),
        }

    def dashboard(self, scope: KnowledgeScope) -> dict[str, Any]:
        records = self.repository.list(scope)
        entities = self.repository.list_quality_entities(scope)
        return {
            "authorizedKnowledgeCount": len(records),
            "authorizedChunkCount": sum(len(self._chunks(r)) for r in records),
            "activeSnapshotCount": sum(
                1 for r in records if r.get("activeIndexSnapshotId")
            ),
            "evaluationRunCount": sum(
                e["entityType"] == "EVALUATION_RUN" for e in entities
            ),
            "duplicateCandidateCount": sum(
                e["entityType"] == "DUPLICATE_CANDIDATE" for e in entities
            ),
            "summaryCount": sum(e["entityType"] == "SUMMARY" for e in entities),
            "authority": "POSTGRESQL",
            "semanticIndex": "QDRANT_DERIVED",
        }
