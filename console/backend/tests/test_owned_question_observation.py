"""Controlled metadata unit boundary; real owner composition is tested in PG."""

# ruff: noqa: F401,F811 -- Shared exact owned-work fixture.
from types import SimpleNamespace as NS

import pytest
from agent_console import planning_candidates
from agent_console import question_member_capabilities as module
from agent_console.authority_contracts import AuthorityError
from agent_console.question_activity_input import entry_grants
from test_owned_business_resource_adapter import case, ref


def test_explicit_problem_entry_never_requires_collection_list():
    assert (
        entry_grants(None, {}, {"problemId": "one"}, {})[0].exact_resource
        == "business-problem:one"
    )
    assert entry_grants(None, {}, {"problemId": "one"}, {})[0].action == "READ"
    assert entry_grants(None, {}, {}, {})[0].action == "LIST"


@pytest.mark.parametrize(
    "unreadable,outside", [(False, False), (True, False), (False, True)]
)
def test_owned_observation_is_exact_and_operations_are_bounded(
    case, monkeypatch, unreadable, outside
):
    a = case
    # More than one allowed revision is an allowlist, not a demand to use both.
    scope = a.work.businessScope.model_copy(
        update={"skills": (ref("skill"), ref("other-allowed"))}
    )
    work = a.work.model_copy(update={"businessScope": scope})
    members = list(a.employee[1]["revision"]["members"])
    if outside:
        members.append({"kind": "AGENT", **ref("outside-agent").model_dump()})
    reads = []

    def require(authority, principal, kind, reference):
        reads.append((kind, reference))
        if unreadable and kind == "SKILL":
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")

    def published(c, s, kind, reference, *, _published_binding=False):
        assert c == "same"
        assert (s.namespace, s.security_domain) == (
            a.context.scope.tenant_id,
            a.context.scope.security_domain,
        )
        assert kind == "EMPLOYEE" or _published_binding is True
        if kind == "EMPLOYEE":
            return {"members": members}, "Employee"
        return {"operations": [{"name": "READ_DATA"}, {"name": "ANALYZE_DATA"}]}, kind

    monkeypatch.setattr(
        module, "identities", lambda *a, **k: pytest.fail("must not scan")
    )
    monkeypatch.setattr(module, "require_read", require)
    monkeypatch.setattr(module, "read_published", published)
    # Exercise the real five-argument frozen employee-member reader.
    monkeypatch.setattr(planning_candidates, "read_published", published)
    monkeypatch.setattr(module, "validate", lambda *a, **k: None)
    value = module.observe(
        NS(services=True, sales_v2_candidate=False),
        NS(connection="same", context=a.context, authority=object()),
        scope.source,
        "document-review-source.v1",
        work,
    )
    assert [o["operation"] for o in value["operations"]] == (
        [] if unreadable or outside else ["READ_DATA"]
    )
    assert value["executionReady"] is False
    assert reads[0] == ("EMPLOYEE", scope.employees[0])
