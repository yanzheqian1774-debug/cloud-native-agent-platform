from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.workbench_resource_directory import ResourceDirectory


@pytest.mark.parametrize("kind", ["knowledge", "skill", "runtime"])
def test_usage_skips_unrelated_versions_but_rechecks_matching_permissions(
    monkeypatch, kind
):
    def preparation(digest, identity, revision):
        ref = NS(resource_id=identity, revision_id=revision)
        return NS(
            digest=digest,
            source_snapshot=ref,
            participants=[NS(skill=NS(reference=ref), profile=ref)],
            semantics=NS(target=NS(problem=NS(resource_id="problem")), title="Result"),
            plan_version=1,
        )

    records = [
        preparation("other-resource", "other", "1"),
        preparation("other-version", "source", "2"),
        preparation("matching", "source", "1"),
    ]
    monkeypatch.setattr(
        "agent_console.ontology_execution.parse_preparation", lambda record: record
    )
    rows = [{"record": r, "progress": {"state": "SUCCEEDED"}} for r in records]
    queries = []

    def execute(statement, params):
        queries.append((statement, params))
        return NS(fetchall=lambda: rows)

    checks = []
    denied = set()

    def require(principal, owner, action, target):
        checks.append((owner, action, target))
        if owner in denied:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    call = NS(
        context=NS(
            principal_id="reader",
            scope=NS(tenant_id="tenant", security_domain="domain"),
        ),
        path={"kind": kind, "identity": "source", "revision": "1"},
        connection=NS(execute=execute),
        authority=NS(require=require),
    )
    result = ResourceDirectory.usage(call)
    assert [r["digest"] for r in result] == ["matching"]
    assert queries[0][1] == ("tenant", "domain")
    assert checks == [
        ("EXECUTION", "READ", "governed-execution:prepared:matching"),
        ("BUSINESS_PROBLEM", "READ", "business-problem:problem"),
    ]
    for owner in ("EXECUTION", "BUSINESS_PROBLEM"):
        checks.clear()
        denied.clear()
        denied.add(owner)
        assert ResourceDirectory.usage(call) == []
        assert all("other-" not in target for _, _, target in checks)
