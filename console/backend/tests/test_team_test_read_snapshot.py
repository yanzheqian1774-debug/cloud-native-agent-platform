"""Canonical team snapshots remain exact, scoped and read-only."""

from types import SimpleNamespace

from agent_console.authority_contracts import AuthorityScope
from agent_console.test_resource_read_access import snapshot_matches
from agent_console.test_resource_read_policy import TestReadTarget
from test_team_definition_postgres import fresh, pytestmark, save, store  # noqa: F401


def test_team_snapshot_digest_and_scope_are_checked(store):  # noqa: F811
    revision = fresh()
    save(store, revision)
    context = SimpleNamespace(
        scope=AuthorityScope(revision.scope.namespace, revision.scope.security_domain)
    )
    target = TestReadTarget(
        owner="TEAM",
        action="READ",
        resource=f"team:{revision.team_id}:{revision.revision_id}",
        digest=revision.content_digest,
        purpose="TEST_RESOURCE_READ",
    )
    with store.pool.connection() as connection:
        assert snapshot_matches(connection, context, target)
        assert not snapshot_matches(
            connection, context, target.model_copy(update={"digest": "0" * 64})
        )
        assert not snapshot_matches(
            connection,
            context,
            target.model_copy(update={"resource": target.resource + ":other"}),
        )
        foreign = SimpleNamespace(
            scope=AuthorityScope("foreign", revision.scope.security_domain)
        )
        assert not snapshot_matches(connection, foreign, target)
