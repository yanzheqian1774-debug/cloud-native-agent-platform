"""Disclosure-safe failure and read-only boundary tests."""

from dataclasses import fields
from time import perf_counter

from agent_console.knowledge_authorization import AuthorizationAction
from agent_console.knowledge_retrieval import (
    InMemoryKnowledgeSource,
    KnowledgeRetrievalResult,
    KnowledgeStatus,
    retrieve,
)
from test_knowledge_authorization_security import request_and_decision
from test_knowledge_pack_contract import NOW


def test_absent_and_denied_have_bounded_minimal_failure_shapes() -> None:
    pack, request, decision = request_and_decision()
    start = perf_counter()
    denied = retrieve(
        request=request,
        authorization=None,
        evaluation_time=NOW,
        source=InMemoryKnowledgeSource(pack),
    )
    denied_elapsed = perf_counter() - start
    assert denied.status is KnowledgeStatus.DENIED
    assert denied.source_read_count == 0
    assert len(repr(denied)) < 1_024
    assert denied_elapsed < 1.0
    assert denied.references == ()
    assert decision.action is AuthorizationAction.ALLOW


def test_denial_result_contract_contains_no_source_metadata_fields() -> None:
    names = {item.name for item in fields(KnowledgeRetrievalResult)}
    assert names.isdisjoint(
        {
            "pack_id",
            "document_id",
            "title",
            "rank",
            "content",
            "citation_id",
            "document_digest",
            "chunk_id",
        }
    )


def test_source_and_repository_expose_no_write_or_connector_ports() -> None:
    pack, _, _ = request_and_decision()
    source = InMemoryKnowledgeSource(pack)
    prohibited = {
        "create",
        "update",
        "delete",
        "ingest",
        "publish",
        "writeback",
        "connect",
        "mcp",
        "grant",
        "credential",
    }
    assert prohibited.isdisjoint(set(dir(source)))
