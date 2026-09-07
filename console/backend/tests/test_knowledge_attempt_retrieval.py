import copy
from types import SimpleNamespace

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
from agent_console.knowledge_pack import canonical_digest
from agent_console.knowledge_qdrant import QdrantKnowledgeError
from agent_console.knowledge_repository import InMemoryKnowledgeRepository
from agent_console.resource_use_domain import (
    ResourceKind,
    ResourceUseBinding,
    ResourceUseFactKind,
    stable_id,
)
from agent_core.execution_contract import ScopeIdentity


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


class ResourceUse:
    def __init__(self):
        self.prepared = False
        self.committed = False
        self.terminal_facts = ()

    def prepare_dispatch(self, *args, transaction_hook=None, **kwargs):
        if not self.prepared:
            transaction_hook(object())
            self.prepared = True
        return SimpleNamespace(high_water=1)

    def commit_observation(self, *args, transaction_hook=None, **kwargs):
        if not self.committed:
            transaction_hook(object())
            self.committed = True
            self.terminal_facts = args[2]
        return SimpleNamespace(high_water=2)


def resource_binding(scope, request):
    knowledge_binding = {
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
    knowledge_binding["digest"] = canonical_digest(
        knowledge_binding, domain="attempt-knowledge-binding.v1"
    )
    use_id = stable_id(
        "resource-use",
        scope.namespace,
        scope.security_domain,
        request.attempt_id,
        "KNOWLEDGE",
        "knowledge:primary",
        "1",
    )
    return ResourceUseBinding(
        ScopeIdentity(scope.namespace, scope.security_domain),
        use_id,
        request.attempt_id,
        ResourceKind.KNOWLEDGE,
        "knowledge:primary",
        1,
        request.knowledge_id,
        request.revision_id,
        request.revision_digest,
        request.binding_id,
        knowledge_binding["digest"],
        "plan:1",
        1,
        "a" * 64,
        "workflow:1",
        "task:1",
        "definition:1",
        "definition-revision:1",
        "b" * 64,
        request.digital_employee_instance_id,
        request.agent_instance_id,
        "runtime:1",
        "knowledge-retrieval.v1",
        "1",
        "qdrant",
        "1",
        request.authorization_decision_id,
    )


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


def test_formal_resource_use_path_dispatches_qdrant_once_and_replays_evidence():
    subject, scope, request, _, _, index = setup_subject()
    use = ResourceUse()
    binding = resource_binding(scope, request)
    first = subject.retrieve_with_resource_use(scope, request, use, binding)
    second = subject.retrieve_with_resource_use(scope, request, use, binding)
    assert second == first
    assert index.search_count == 1
    assert use.prepared and use.committed


def test_prepared_dispatch_without_terminal_result_never_redispatches():
    subject, scope, request, _, _, index = setup_subject()
    use = ResourceUse()
    use.prepared = True
    with pytest.raises(
        AttemptKnowledgeFailure, match="KNOWLEDGE_RESULT_PENDING_CONFIRMATION"
    ):
        subject.retrieve_with_resource_use(
            scope, request, use, resource_binding(scope, request)
        )
    assert index.search_count == 0


def test_formal_no_result_maps_to_distinct_resource_use_terminal_state():
    subject, scope, request, _, _, index = setup_subject()
    index.points = []
    use = ResourceUse()
    result = subject.retrieve_with_resource_use(
        scope, request, use, resource_binding(scope, request)
    )
    assert result["retrievalState"] == "NO_RESULT"
    assert use.terminal_facts[0].kind is ResourceUseFactKind.NO_RESULT


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
