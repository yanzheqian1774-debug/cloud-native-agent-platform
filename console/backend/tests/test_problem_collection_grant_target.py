"""The task directory's existing LIST permission can be requested exactly."""

from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, AuthorityScope, ExactGrant
from agent_console.workbench_grant_targets import WorkbenchGrantTargetValidator


def test_collection_discovery_does_not_admit_object_reads_or_other_actions():
    validator = WorkbenchGrantTargetValidator(None)
    context = SimpleNamespace(scope=AuthorityScope("test", "synthetic"))
    connection = object()
    assert validator.is_known_exact_target(
        context,
        ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        connection=connection,
    )
    for action, resource in [
        ("LIST", "business-problem:other"),
        ("LIST", "business-problem:collection:other"),
        ("READ", "business-problem:collection"),
        ("CREATE", "business-problem:collection"),
        ("REVISE", "business-problem:collection"),
    ]:
        assert not validator.is_known_exact_target(
            context,
            ExactGrant("BUSINESS_PROBLEM", action, resource),
            connection=connection,
        )
    with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
        validator.is_known_exact_target(
            context,
            ExactGrant("BUSINESS_PROBLEM", "LIST", "business-problem:collection"),
        )
