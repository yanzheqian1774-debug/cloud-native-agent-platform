import pytest
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_quality import (
    FUSION_K,
    SUMMARY_PROVIDER,
    TOKENIZER_VERSION,
    KnowledgeQualityFailure,
    KnowledgeQualityService,
    tokenize,
)
from agent_console.knowledge_repository import InMemoryKnowledgeRepository


class DerivedIndex:
    def search(self, _vector, **values):
        return [
            {
                "score": 0.91,
                "payload": {"chunkId": self.chunk_id, **values},
            }
        ]


def fixture():
    repository = InMemoryKnowledgeRepository()
    lifecycle = KnowledgeLifecycleService(repository)
    scope = lifecycle.scope("tenant-a", "quality")
    created = lifecycle.create(
        scope,
        "human:owner",
        "Chinese procedure",
        {
            "sourceId": "source:procedure",
            "documentId": "document:procedure",
            "provenance": "human:owner",
            "content": "供应商缺陷必须立即隔离。\n\nRoot cause evidence is required.",
        },
    )["knowledge"]
    created["publishedRevisionId"] = created["currentDraftRevisionId"]
    created["activeIndexSnapshotId"] = "snapshot:one"
    created["aggregateVersion"] = 2
    repository.replace(created, expected_version=1, fact={"factId": "fact:publish"})
    index = DerivedIndex()
    index.chunk_id = created["revisions"][0]["content"]["documents"][0]["chunks"][0][
        "chunkId"
    ]
    return repository, scope, KnowledgeQualityService(repository, index), created


def test_versioned_chinese_lexical_semantic_and_hybrid_are_stable():
    _, scope, service, created = fixture()
    assert tokenize("供应商缺陷") == ("供应", "应商", "商缺", "缺陷")
    lexical = service.search(scope, query="供应商缺陷", mode="LEXICAL")
    semantic = service.search(scope, query="containment", mode="SEMANTIC")
    hybrid = service.search(scope, query="供应商缺陷", mode="HYBRID")
    assert lexical["tokenizerVersion"] == TOKENIZER_VERSION
    assert semantic["results"][0]["semanticRank"] == 1
    assert hybrid["fusion"]["k"] == FUSION_K
    assert (
        hybrid["results"][0]["citation"]["revisionId"] == created["publishedRevisionId"]
    )
    assert (
        service.search(
            KnowledgeLifecycleService.scope("tenant-b", "quality"),
            query="供应商",
            mode="LEXICAL",
        )["results"]
        == []
    )


def test_evaluation_not_measurable_summary_duplicates_import_and_export():
    _, scope, service, created = fixture()
    chunk_id = created["revisions"][0]["content"]["documents"][0]["chunks"][0][
        "chunkId"
    ]
    measured = service.evaluate(
        scope,
        {
            "cases": [
                {"caseId": "one", "query": "缺陷", "expectedChunkIds": [chunk_id]}
            ],
            "mode": "HYBRID",
        },
    )
    assert measured["body"]["metrics"]["recallAtK"] == 1.0
    assert measured["body"]["binding"]["tokenizerVersion"] == TOKENIZER_VERSION
    assert measured["body"]["binding"]["retrievalConfigurationId"].startswith(
        "retrieval-configuration:"
    )
    missing_truth = service.evaluate(
        scope, {"cases": [{"caseId": "two", "query": "缺陷"}], "mode": "LEXICAL"}
    )
    assert missing_truth["body"]["metrics"] == {"status": "NOT_MEASURABLE"}
    not_comparable = service.evaluate(
        scope,
        {
            "cases": [{"caseId": "three", "query": "缺陷"}],
            "mode": "LEXICAL",
            "comparisonToRunId": measured["entityId"],
        },
    )
    assert not_comparable["body"]["comparison"]["status"] == "NOT_MEASURABLE"
    summary = service.summarize(scope, created["knowledgeId"])
    assert summary["body"]["provider"] == SUMMARY_PROVIDER
    assert summary["body"]["model"] == "NOT_APPLICABLE"
    assert (
        summary["body"]["citations"][0]["revisionId"] == created["publishedRevisionId"]
    )
    preview = service.import_preview(
        scope, format="jsonl", content='{"name":"A","content":"B"}'
    )
    assert preview["body"]["status"] == "PREVIEW"
    assert preview["body"]["draftOnly"] is True
    assert service.export(scope)["format"] == "KNOWLEDGE_AUTHORIZED_EXPORT_V1"
    assert service.dashboard(scope)["evaluationRunCount"] == 3


def test_import_execution_progress_retry_and_idempotency_create_drafts_only():
    repository, scope, service, _ = fixture()
    preview = service.import_preview(
        scope,
        format="jsonl",
        content=(
            '{"name":"Imported A","content":"First authorized record"}\n'
            '{"name":"","content":"Rejected record"}'
        ),
    )
    first = service.execute_import(scope, preview["entityId"], "human:importer")
    assert first["body"]["status"] == "PARTIAL"
    assert first["body"]["acceptedCount"] == 1
    assert first["body"]["rejectedCount"] == 1
    assert first["body"]["retryable"] is True
    imported = first["body"]["importedKnowledgeIds"]
    assert repository.get(scope, imported[0])["lifecycleState"] == "DRAFT"
    retried = service.execute_import(scope, preview["entityId"], "human:importer")
    assert retried["body"]["importedKnowledgeIds"] == imported
    assert retried["body"]["acceptedCount"] == 1


def test_metric_comparison_duplicate_decision_and_metadata_are_scoped():
    repository, scope, service, created = fixture()
    chunk_id = created["revisions"][0]["content"]["documents"][0]["chunks"][0][
        "chunkId"
    ]
    before = service.evaluate(
        scope,
        {
            "cases": [
                {"caseId": "one", "query": "缺陷", "expectedChunkIds": [chunk_id]}
            ],
            "mode": "LEXICAL",
        },
    )
    after = service.evaluate(
        scope,
        {
            "cases": [
                {"caseId": "one", "query": "缺陷", "expectedChunkIds": [chunk_id]}
            ],
            "mode": "HYBRID",
            "comparisonToRunId": before["entityId"],
        },
    )
    comparison = after["body"]["comparison"]
    assert comparison["status"] == "MEASURABLE"
    assert comparison["beforeRunId"] == before["entityId"]
    assert comparison["claim"] == "NO_IMPROVEMENT_CLAIM"
    assert set(comparison["deltas"]) == {
        "recallAtK",
        "precisionAtK",
        "mrr",
        "citationCompleteness",
    }
    lifecycle = KnowledgeLifecycleService(repository)
    duplicate = lifecycle.create(
        scope,
        "human:owner",
        "Duplicate",
        {
            "sourceId": "source:duplicate",
            "documentId": "document:duplicate",
            "provenance": "human:owner",
            "content": "供应商缺陷必须立即隔离。\n\nRoot cause evidence is required.",
        },
    )["knowledge"]
    duplicate["publishedRevisionId"] = duplicate["currentDraftRevisionId"]
    duplicate["aggregateVersion"] = 2
    repository.replace(duplicate, expected_version=1, fact={"factId": "fact:dup"})
    candidates = service.duplicates(scope)
    exact = next(
        item for item in candidates if item["body"]["classification"] == "EXACT"
    )
    decision = service.decide_duplicate(
        scope,
        candidate_id=exact["entityId"],
        classification="DISTINCT",
        actor="human:reviewer",
    )
    assert decision["body"]["effect"] == "RECORD_ONLY_NO_CONTENT_MUTATION"
    assert any(
        item["entityId"] == exact["entityId"] and item["decision"] is not None
        for item in service.duplicate_queue(scope)
    )
    metadata = service.metadata(scope)
    assert "source:procedure" in metadata["sourceId"]
    foreign = KnowledgeLifecycleService.scope("tenant-b", "quality")
    assert service.metadata(foreign)["sourceId"] == []
    assert (
        service.search(
            scope,
            query="缺陷",
            mode="LEXICAL",
            source_id="source:duplicate",
        )["results"][0]["citation"]["sourceId"]
        == "source:duplicate"
    )


def test_import_rejects_unknown_fields_controls_archives_and_urls():
    _, scope, service, _ = fixture()
    with pytest.raises(KnowledgeQualityFailure, match="INVALID_JSONL"):
        service.import_preview(
            scope,
            format="jsonl",
            content='{"name":"A","content":"B","url":"https://invalid"}',
        )
    with pytest.raises(KnowledgeQualityFailure, match="IMPORT_FORMAT_NOT_ALLOWED"):
        service.import_preview(scope, format="zip", content="archive")
    with pytest.raises(KnowledgeQualityFailure, match="INVALID_IMPORT_CONTENT"):
        service.import_preview(scope, format="txt", content="bad\u0000content")
