"""Historical ontology READ must never become execution USE or START."""

from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.native_interaction import answer, progress
from agent_console.native_progress_projection import projection_read_grants
from agent_console.prepared_execution_resources import resource_read_grants


def preparation():
    def ref(identity):
        return NS(resource_id=identity, revision_id="r1", digest="a" * 64)

    member = NS(profile=ref("runtime"))
    return NS(
        namespace="t",
        security_domain="d",
        digest="b" * 64,
        run_id="old-run",
        participants=[member],
        source_snapshot=ref("source"),
        business_semantics=NS(ontology=ref("ontology")),
    ), member


@pytest.mark.parametrize("read_allowed", [True, False])
@pytest.mark.parametrize("execution_denial", ["START", "USE"])
def test_exact_ontology_read_allows_only_progress_when_use_is_denied(
    read_allowed, execution_denial
):
    p, member = preparation()
    original = resource_read_grants(p, member)
    projection = projection_read_grants(p, member)
    use = next(g for g in original if g.owner == "BUSINESS_ONTOLOGY")
    read = next(g for g in projection if g.owner == "BUSINESS_ONTOLOGY")
    assert use.action == "USE" and read.action == "READ"
    assert use.exact_resource == read.exact_resource
    queries, checks = [], []

    class Connection:
        def execute(self, sql, params=None):
            assert sql.startswith("SELECT")
            queries.append((sql, params))
            return NS(fetchone=lambda: {"present": True}, fetchall=lambda: [])

    class Authority:
        def require(self, actor, owner, action, resource):
            checks.append((owner, action, resource))
            if action == execution_denial or (
                owner == "BUSINESS_ONTOLOGY" and not read_allowed
            ):
                raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    principal = NS(principal_id="ordinary", tenant_id="t", security_domain="d")
    call = NS(
        connection=Connection(),
        authority=Authority(),
        context=NS(principal_id="ordinary"),
    )
    from agent_console.prepared_execution_application import (
        PreparedExecutionApplication,
    )

    app = PreparedExecutionApplication(call.connection, principal, call.authority)
    if read_allowed:
        assert progress(call, app, p)["steps"] == []
        assert ("BUSINESS_ONTOLOGY", "READ", read.exact_resource) in checks
    else:
        with pytest.raises(AuthorityError):
            progress(call, app, p)
        assert not queries
    before = list(queries)
    with pytest.raises(AuthorityError):
        answer(call, app, p)
    assert queries == before
    assert checks[-1][1] == execution_denial
    assert all(g.action not in {"USE", "START", "RETRY"} for g in projection)
