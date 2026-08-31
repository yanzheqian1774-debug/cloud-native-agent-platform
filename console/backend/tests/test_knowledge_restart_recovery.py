from agent_console.knowledge_lifecycle_service import KnowledgeLifecycleService
from test_knowledge_lifecycle_service import published_service, qdrant


def test_restart_recovers_same_identity_revision_digest_and_snapshot():
    service, scope, value = published_service()
    stored = service.ingest(scope, value["knowledgeId"], "human", 4)["knowledge"]
    restarted = KnowledgeLifecycleService(service.repository, qdrant()).get(
        scope, value["knowledgeId"]
    )["knowledge"]
    assert (
        restarted["knowledgeId"] == stored["knowledgeId"]
        and restarted["revisions"] == stored["revisions"]
    )
    assert restarted["activeIndexSnapshotId"] == stored["activeIndexSnapshotId"]
