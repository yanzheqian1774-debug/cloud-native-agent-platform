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


def test_create_collection_dispatches_to_real_problem_owner_without_wildcards():
    from agent_console.business_problem_postgres import (
        PostgresBusinessProblemRepository,
    )

    class NoQueries:
        def execute(self, *args):
            pytest.fail("collection discovery must not query or create a problem")

    validator = WorkbenchGrantTargetValidator(PostgresBusinessProblemRepository)
    context = SimpleNamespace(scope=AuthorityScope("test", "synthetic"))
    connection = NoQueries()
    assert validator.is_known_exact_target(
        context,
        ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        connection=connection,
    )
    for resource in [
        "business-problem:other",
        "business-problem:collection:other",
    ]:
        assert not validator.is_known_exact_target(
            context,
            ExactGrant("BUSINESS_PROBLEM", "CREATE", resource),
            connection=connection,
        )
    for malformed in ["business-problem:*", "business-problem:collection "]:
        with pytest.raises(AuthorityError, match="INVALID_GRANT_TARGET"):
            ExactGrant("BUSINESS_PROBLEM", "CREATE", malformed)
    assert not validator.is_known_exact_target(
        context,
        ExactGrant("BUSINESS_PROBLEM", "DELETE", "business-problem:collection"),
        connection=connection,
    )
    with pytest.raises(AuthorityError, match="AUTHORITY_STORAGE_UNAVAILABLE"):
        validator.is_known_exact_target(
            context,
            ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
        )
