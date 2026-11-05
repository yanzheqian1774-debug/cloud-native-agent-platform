# ruff: noqa: F401,F811 -- Existing disposable owner/permission fixtures.
"""Capability facts are metadata, not predecessor tasks or execution admission."""

from types import SimpleNamespace

from agent_console.authority_contracts import AuthorityError
from agent_console.question_member_capabilities import observe
from agent_console.workbench_owner_authorization import AuthorizedOwnerAuthority
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_resource_automation import automation


def test_only_readable_exact_source_members_supply_registered_capability_facts(
    automation,
):
    a = automation
    assert a.run()["state"] == "READY"
    with a.repository.pool.connection() as c:
        authority = AuthorizedOwnerAuthority(a.adapter, a.subject, c, 1, ())
        call = SimpleNamespace(connection=c, context=a.subject, authority=authority)
        facts = observe(
            a.automation,
            call,
            a.refs["knowledge"],
            "sales-diagnostic-source.v1",
            a.policy.workScopes[0],
        )
        assert facts["state"] == "AUTHORIZED_MEMBER_DECLARATIONS_OBSERVED"
        operations = {x["operation"] for x in facts["operations"]}
        assert "READ_DATA" in operations and "ANALYZE_DATA" in operations
        assert "CLASSIFY_OVERDUE" not in operations
        assert facts["executionReady"] is False and facts["coverageComplete"] is False
        assert "resource_id" not in str(facts) and "tasks" not in facts

        class DenyEmployees:
            def require(self, *args):
                if args[1] == "EMPLOYEE":
                    raise AuthorityError("ISOLATED_EMPLOYEE_READ_DENIED")
                return authority.require(*args)

        call.authority = DenyEmployees()
        hidden = observe(
            a.automation,
            call,
            a.refs["knowledge"],
            "sales-diagnostic-source.v1",
            a.policy.workScopes[0],
        )
        assert hidden["operations"] == []
        assert "employee-definition" not in str(hidden)
