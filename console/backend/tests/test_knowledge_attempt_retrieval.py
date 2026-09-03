import copy

import pytest
from agent_console.knowledge_attempt_retrieval import (
    AttemptContext,
    AttemptKnowledgeFailure,
    AttemptKnowledgeRequest,
    AttemptKnowledgeRetrievalService,
    InMemoryAttemptKnowledgeEvidenceRepository,
)
from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from agent_console.knowledge_p1_bootstrap import bootstrap_p1_knowledge
from agent_console.knowledge_qdrant import QdrantKnowledgeError
from agent_console.knowledge_repository import InMemoryKnowledgeRepository


class Index:
    collection = "knowledge_test"

    def __init__(self):
        self.points = []
        self.search_count = 0
        self.unavailable = False

    def ensure_collection(self):
        pass

    def upsert(self, points):
        self.points.extend(copy.deepcopy(points))

    def search(self, vector, **filters):
        self.search_count += 1
        if self.unavailable:
            raise QdrantKnowledgeError("QDRANT_UNAVAILABLE")
        key_map = {
            "security_domain": "securityDomain",
            "knowledge_id": "knowledgeId",
            "snapshot_id": "snapshotId",
        }
        return [
            {"payload": item["payload"]}
            for item in self.points
            if all(
                item["payload"].get(key_map.get(key, key)) == value
                for key, value in filters.items()
                if key != "limit"
            )
        ]


def setup_subject():
    knowledge, index = InMemoryKnowledgeRepository(), Index()
    lifecycle = KnowledgeLifecycleService(knowledge, index)
    scope = lifecycle.scope("tenant-p1", "supplier-quality")
    record = bootstrap_p1_knowledge(lifecycle, scope)["knowledge"]
    attempt = AttemptContext(
        "attempt:p1",
        "digital-employee:p1",
        "agent-instance:p1",
        scope.namespace,
        scope.security_domain,
    )
    evidence = InMemoryAttemptKnowledgeEvidenceRepository((attempt,))
    subject = AttemptKnowledgeRetrievalService(knowledge, evidence, index)
    revision = record["revisions"][0]
    request = AttemptKnowledgeRequest(
        attempt.attempt_id,
        attempt.digital_employee_instance_id,
        attempt.agent_instance_id,
        "knowledge-binding:p1",
        record["knowledgeId"],
        revision["revisionId"],
        revision["digest"],
        record["activeIndexSnapshotId"],
        "ALLOW",
        "authorization:p1",
        "根因 永久纠正措施",
    )
    return subject, scope, request, record, evidence, index


def test_attempt_scoped_real_index_retrieval_citation_evidence_and_replay():
    subject, scope, request, record, evidence, _ = setup_subject()
    first = subject.retrieve(scope, request)
    second = subject.retrieve(scope, request)
    assert first == second
    assert first["retrievalState"] == "RETRIEVED"
    citation = first["citations"][0]
    assert citation["knowledgeId"] == record["knowledgeId"]
    assert citation["documentId"] == "knowledge-document:p1-8d-corrective-action"
    assert citation["documentVersion"] == "1"
    assert citation["chunkId"] and citation["chunkDigest"]
    assert first["binding"]["attemptId"] == "attempt:p1"
    assert first["evidence"]["attemptId"] == "attempt:p1"
    assert subject.readback(scope, first["evidence"]["evidenceId"]) == first["evidence"]
    assert len(evidence.evidence) == 1


def test_denial_happens_before_attempt_knowledge_or_qdrant_lookup():
    subject, scope, request, _, evidence, index = setup_subject()
    subject.knowledge = type(
        "Forbidden", (), {"get": lambda *_: pytest.fail("lookup")}
    )()
    evidence.attempts = {}
    denied = AttemptKnowledgeRequest(
        request.attempt_id,
        request.digital_employee_instance_id,
        request.agent_instance_id,
        request.binding_id,
        request.knowledge_id,
        request.revision_id,
        request.revision_digest,
        request.snapshot_id,
        "DENY",
        request.authorization_decision_id,
        request.query,
    )
    with pytest.raises(AttemptKnowledgeFailure, match="KNOWLEDGE_ACCESS_DENIED"):
        subject.retrieve(scope, denied)
    assert index.search_count == 0


def test_no_result_stale_unavailable_and_exact_identity_conflicts():
    subject, scope, request, record, _, index = setup_subject()
    no_result = AttemptKnowledgeRequest(
        request.attempt_id,
        request.digital_employee_instance_id,
        request.agent_instance_id,
        "knowledge-binding:no-result",
        request.knowledge_id,
        request.revision_id,
        request.revision_digest,
        request.snapshot_id,
        "ALLOW",
        "authorization:no-result",
        "不存在词语",
    )
    index.points = []
    assert subject.retrieve(scope, no_result)["retrievalState"] == "NO_RESULT"
    index.unavailable = True
    unavailable = copy.copy(request)
    assert subject.retrieve(scope, unavailable)["reason"] == "QDRANT_UNAVAILABLE"
    with pytest.raises(AttemptKnowledgeFailure, match="KNOWLEDGE_REVISION_CONFLICT"):
        subject.retrieve(
            scope,
            copy.copy(
                AttemptKnowledgeRequest(
                    request.attempt_id,
                    request.digital_employee_instance_id,
                    request.agent_instance_id,
                    request.binding_id,
                    request.knowledge_id,
                    request.revision_id,
                    "0" * 64,
                    request.snapshot_id,
                    "ALLOW",
                    request.authorization_decision_id,
                    request.query,
                )
            ),
        )
    with pytest.raises(AttemptKnowledgeFailure, match="INDEX_SNAPSHOT_CONFLICT"):
        subject.retrieve(
            scope,
            AttemptKnowledgeRequest(
                request.attempt_id,
                request.digital_employee_instance_id,
                request.agent_instance_id,
                request.binding_id,
                request.knowledge_id,
                request.revision_id,
                request.revision_digest,
                "knowledge-snapshot:other",
                "ALLOW",
                request.authorization_decision_id,
                request.query,
            ),
        )
    record["indexSnapshots"][0]["status"] = "STALE"
    subject.knowledge._records[
        (scope.namespace, scope.security_domain, request.knowledge_id)
    ] = record
    assert subject.retrieve(scope, request)["reason"] == "INDEX_STALE"


def test_tenant_and_digital_employee_isolation_fail_closed():
    subject, scope, request, _, _, index = setup_subject()
    with pytest.raises(AttemptKnowledgeFailure, match="ATTEMPT_NOT_FOUND"):
        subject.retrieve(type(scope)("tenant-other", scope.security_domain), request)
    wrong = AttemptKnowledgeRequest(
        request.attempt_id,
        "digital-employee:other",
        request.agent_instance_id,
        request.binding_id,
        request.knowledge_id,
        request.revision_id,
        request.revision_digest,
        request.snapshot_id,
        "ALLOW",
        request.authorization_decision_id,
        request.query,
    )
    with pytest.raises(
        AttemptKnowledgeFailure, match="DIGITAL_EMPLOYEE_BINDING_MISMATCH"
    ):
        subject.retrieve(scope, wrong)
    assert index.search_count == 0
