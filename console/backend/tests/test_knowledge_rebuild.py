from test_knowledge_lifecycle_service import published_service


def test_rebuild_appends_a_new_snapshot_without_mutating_revision():
    service, scope, value = published_service()
    first = service.ingest(scope, value["knowledgeId"], "human", 4)["knowledge"]
    second = service.rebuild(scope, value["knowledgeId"], "human", 5)["knowledge"]
    assert (
        len(second["indexSnapshots"]) == 2
        and first["publishedRevisionId"] == second["publishedRevisionId"]
    )
    assert first["activeIndexSnapshotId"] != second["activeIndexSnapshotId"]
