import copy

import httpx
import pytest
from agent_console.knowledge_lifecycle_service import (
    KnowledgeLifecycleFailure,
    KnowledgeLifecycleService,
)
from agent_console.knowledge_qdrant import QdrantKnowledgeIndex
from agent_console.knowledge_repository import InMemoryKnowledgeRepository


def qdrant():
    def handler(request):
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(200, json={"status": "ok", "result": {}})

    return QdrantKnowledgeIndex(
        "http://qdrant", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def source():
    return {
        "sourceId": "source:one",
        "documentId": "document:one",
        "provenance": "human:owner",
        "content": "Approved procedure.\n\nCitable evidence.",
    }


def published_service(index=None):
    service = KnowledgeLifecycleService(
        InMemoryKnowledgeRepository(), index or qdrant()
    )
    scope = service.scope("tenant-a", "quality")
    value = service.create(scope, "human:owner", "Quality Knowledge", source())[
        "knowledge"
    ]
    value = service.validate(scope, value["knowledgeId"], "human:owner", 1)["knowledge"]
    digest = value["revisions"][-1]["digest"]
    value = service.review(scope, value["knowledgeId"], "human:reviewer", 2, digest)[
        "knowledge"
    ]
    value = service.publish(scope, value["knowledgeId"], "human:publisher", 3, digest)[
        "knowledge"
    ]
    return service, scope, value


def test_exact_digest_publication_and_ingestion_snapshot():
    service, scope, value = published_service()
    result = service.ingest(scope, value["knowledgeId"], "human:operator", 4)[
        "knowledge"
    ]
    assert result["lifecycleState"] == "AVAILABLE" and result["activeIndexSnapshotId"]
    assert result["ingestionJobs"][-1]["highWaterMark"] == 4


def test_successor_preserves_published_revision_and_authorized_retrieval_cites_source():
    service, scope, value = published_service()
    value = service.ingest(scope, value["knowledgeId"], "human", 4)["knowledge"]
    published_id = value["publishedRevisionId"]
    snapshot_id = value["activeIndexSnapshotId"]
    revision = next(
        item for item in value["revisions"] if item["revisionId"] == published_id
    )
    chunk = revision["content"]["documents"][0]["chunks"][0]

    def search(*args, **kwargs):
        return [
            {
                "payload": {
                    "chunkId": chunk["chunkId"],
                    "revisionDigest": revision["digest"],
                }
            }
        ]

    service.qdrant.search = search  # type: ignore[method-assign]
    retrieved = service.retrieve(
        scope,
        value["knowledgeId"],
        "human",
        5,
        "ALLOW",
        "authorization:one",
        "approved procedure",
    )["knowledge"]
    citation = retrieved["retrievals"][-1]["citations"][0]
    assert citation["sourceId"] == "source:one"
    assert retrieved["activeIndexSnapshotId"] == snapshot_id
    successor = service.successor(
        scope,
        value["knowledgeId"],
        "human",
        6,
        "Updated approved procedure.",
    )["knowledge"]
    assert successor["publishedRevisionId"] == published_id
    assert successor["revisions"][-1]["predecessorRevisionId"] == published_id


def test_uploaded_revision_successor_records_manual_text_as_its_direct_source():
    service = KnowledgeLifecycleService(InMemoryKnowledgeRepository(), qdrant())
    scope = service.scope("tenant-a", "quality")
    uploaded_source = {
        "sourceId": "source:uploaded",
        "documentId": "document:uploaded",
        "kind": "DOCX",
        "provenance": "document-upload:original-digest",
        "sourceDescription": "质量部门正式制度",
        "externalReference": "SQ-2026-09",
        "fileName": "供应商质量管理制度.docx",
        "mediaType": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        "parserVersion": "KNOWLEDGE_DOCUMENT_PARSER_V1",
        "content": "原始文件正文。",
        "contentDigest": (
            "d99e52dd6da7c7493e1da1d0147025c7d71d585829e0ce8b946229232a70ad4d"
        ),
        "segments": [
            {
                "content": "原始文件正文。",
                "location": {"paragraphNumber": 1},
            }
        ],
    }
    created = service.create(scope, "human:owner", "上传制度", uploaded_source)[
        "knowledge"
    ]
    validated = service.validate(scope, created["knowledgeId"], "human:owner", 1)[
        "knowledge"
    ]
    original_digest = validated["revisions"][0]["digest"]
    service.review(scope, created["knowledgeId"], "human:reviewer", 2, original_digest)
    published = service.publish(
        scope, created["knowledgeId"], "human:publisher", 3, original_digest
    )["knowledge"]
    original_revision = copy.deepcopy(published["revisions"][0])

    successor = service.successor(
        scope,
        created["knowledgeId"],
        "human:editor",
        4,
        "人工修订后的正文。",
    )["knowledge"]

    assert successor["revisions"][0] == original_revision
    revised = successor["revisions"][-1]
    assert revised["predecessorRevisionId"] == original_revision["revisionId"]
    assert revised["content"]["source"] == {
        "sourceId": "source:uploaded",
        "collectionId": "collection:source:uploaded",
        "kind": "TEXT",
        "provenance": "human-edit:human:editor",
        "sourceDescription": "人工编辑后继修订",
    }
    revised_document = revised["content"]["documents"][0]
    assert revised_document["documentId"] == "document:uploaded"
    assert revised_document["chunks"][0]["content"] == "人工修订后的正文。"
    assert "location" not in revised_document["chunks"][0]


def test_denied_retrieval_does_not_read_repository():
    service, scope, _ = published_service()
    with pytest.raises(KnowledgeLifecycleFailure, match="KNOWLEDGE_ACCESS_DENIED"):
        service.retrieve(
            scope,
            "knowledge:foreign",
            "human",
            1,
            "DENY",
            "authorization:denied",
            "query",
        )


def test_missing_source_and_document_ids_are_generated_without_changing_legacy_ids():
    service = KnowledgeLifecycleService(InMemoryKnowledgeRepository())
    scope = service.scope("tenant-a", "quality")
    generated = service.create(
        scope,
        "human:owner",
        "中文知识",
        {"sourceDescription": "人工录入", "content": "正文依据。"},
    )["knowledge"]
    revision = generated["revisions"][0]
    assert revision["content"]["source"]["sourceId"].startswith("knowledge-source:")
    assert revision["content"]["documents"][0]["documentId"].startswith(
        "knowledge-document:"
    )

    legacy = service.create(
        scope,
        "human:owner",
        "Legacy",
        source(),
    )["knowledge"]
    legacy_revision = legacy["revisions"][0]
    assert legacy_revision["content"]["source"]["sourceId"] == "source:one"
    assert legacy_revision["content"]["documents"][0]["documentId"] == ("document:one")
