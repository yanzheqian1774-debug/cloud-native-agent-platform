"""Authorization-first and zero-source-read security tests."""

from dataclasses import replace
from datetime import timedelta

import pytest
from agent_console.knowledge_authorization import (
    AuthorizationAction,
    KnowledgeAuthorizationDecision,
)
from agent_console.knowledge_retrieval import (
    RETRIEVAL_POLICY_VERSION,
    InMemoryKnowledgeSource,
    KnowledgeRetrievalRequest,
    KnowledgeStatus,
    retrieve,
)
from test_knowledge_pack_contract import NOW, make_pack


def request_and_decision(
    pack=None, *, query="supplier quality containment corrective action"
):
    pack = make_pack() if pack is None else pack
    document = pack.documents[0]
    request = KnowledgeRetrievalRequest.create(
        request_id="retrieval-001",
        canonical_workflow_revision_id="workflow-revision-001",
        approved_workflow_digest="a" * 64,
        task_requirement_id="task-requirement-001",
        knowledge_binding_id="knowledge-binding-001",
        tenant_id=pack.tenant_id,
        security_domain=pack.security_domain,
        purpose="supplier-quality-analysis",
        authorization_decision_id="authorization-001",
        knowledge_pack_id=pack.knowledge_pack_id,
        knowledge_pack_version=pack.knowledge_pack_version,
        knowledge_pack_digest=pack.canonical_digest,
        document_id=document.document_id,
        document_version=document.document_version,
        document_digest=document.content_digest,
        retrieval_policy_version=RETRIEVAL_POLICY_VERSION,
        query=query,
        filters=(),
        max_results=16,
        required=True,
    )
    decision = KnowledgeAuthorizationDecision.create(
        decision_id=request.authorization_decision_id,
        replay_identity="authorization-replay-001",
        action=AuthorizationAction.ALLOW,
        tenant_id=request.tenant_id,
        security_domain=request.security_domain,
        purpose=request.purpose,
        knowledge_pack_id=request.knowledge_pack_id,
        knowledge_pack_version=request.knowledge_pack_version,
        knowledge_pack_digest=request.knowledge_pack_digest,
        document_id=request.document_id,
        document_version=request.document_version,
        document_digest=request.document_digest,
        policy_version=request.retrieval_policy_version,
        effective_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=1),
        authority="trusted-policy",
    )
    return pack, request, decision


@pytest.mark.parametrize(
    "mutation",
    [
        lambda decision: None,
        lambda decision: replace(decision, action=AuthorizationAction.DENY),
        lambda decision: replace(decision, action=AuthorizationAction.REVOKE),
        lambda decision: replace(decision, expires_at=NOW),
        lambda decision: replace(decision, tenant_id="tenant-b"),
        lambda decision: replace(decision, security_domain="finance"),
        lambda decision: replace(decision, purpose="different-purpose"),
        lambda decision: replace(decision, knowledge_pack_version="v2"),
        lambda decision: replace(decision, knowledge_pack_digest="b" * 64),
        lambda decision: replace(decision, document_version="v2"),
        lambda decision: replace(decision, document_digest="b" * 64),
        lambda decision: replace(decision, policy_version="different-policy"),
        lambda decision: replace(decision, replay_identity="changed-replay"),
        lambda decision: replace(decision, decision_digest="0" * 64),
    ],
)
def test_every_authorization_failure_is_nondisclosing_and_zero_read(mutation) -> None:
    pack, request, decision = request_and_decision()
    source = InMemoryKnowledgeSource(pack)
    result = retrieve(
        request=request,
        authorization=mutation(decision),
        evaluation_time=NOW,
        source=source,
    )
    assert result.status is KnowledgeStatus.DENIED
    assert result.source_read_count == source.read_count == 0
    assert result.references == ()
    assert result.reason_codes == ("KNOWLEDGE_ACCESS_DENIED",)
    serialized = repr(result)
    for secret in (
        pack.knowledge_pack_id,
        request.document_id,
        request.document_digest,
        "Containment",
    ):
        assert secret not in serialized


def test_valid_exact_allow_reads_once() -> None:
    pack, request, decision = request_and_decision()
    source = InMemoryKnowledgeSource(pack)
    result = retrieve(
        request=request, authorization=decision, evaluation_time=NOW, source=source
    )
    assert result.status is KnowledgeStatus.AVAILABLE
    assert result.source_read_count == source.read_count == 1
