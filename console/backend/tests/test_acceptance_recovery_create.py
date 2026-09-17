from types import SimpleNamespace

import pytest
from agent_console.acceptance_recovery import mutation_allowed
from agent_console.acceptance_recovery_create import (
    PAYLOAD,
    RestrictedReadGrants,
    restricted_operation,
)
from agent_console.authority_contracts import AuthorityError, AuthorityScope, ExactGrant
from agent_console.business_problem_schemas import CreateBusinessProblem
from agent_console.workbench_bff import WorkbenchOperation
from agent_console.workbench_owner_authorization import WorkbenchOwnerError


def context(principal="human:alice", tenant="tenant-a", domain="quality"):
    return SimpleNamespace(principal_id=principal, scope=AuthorityScope(tenant, domain))


@pytest.mark.parametrize("field", ["title", "description", "ownerId", "idempotencyKey"])
def test_payload_mismatch_never_reaches_owner(field):
    called = []
    op = WorkbenchOperation(
        "CREATE_PROBLEM",
        "POST",
        "/api/workbench/v1/problems",
        CreateBusinessProblem,
        None,
        lambda *a: (),
        lambda call: called.append(call),
    )
    payload = {**PAYLOAD, field: "wrong"}
    with pytest.raises(WorkbenchOwnerError):
        restricted_operation(op).handler(
            SimpleNamespace(context=context(), payload=payload)
        )
    assert called == []


@pytest.mark.parametrize(
    "ctx", [context("human:admin"), context(tenant="other"), context(domain="other")]
)
def test_identity_mismatch_never_reaches_owner(ctx):
    op = WorkbenchOperation(
        "CREATE_PROBLEM",
        "POST",
        "/api/workbench/v1/problems",
        CreateBusinessProblem,
        None,
        lambda *a: (),
        lambda call: pytest.fail("owner invoked"),
    )
    with pytest.raises(AuthorityError):
        restricted_operation(op).handler(SimpleNamespace(context=ctx, payload=PAYLOAD))


def test_read_grants_are_exact_and_independent():
    target = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:one")
    facade = RestrictedReadGrants(None, None)
    facade.target = lambda: target
    request = SimpleNamespace(
        subject_principal_id="human:alice",
        scope=context().scope,
        members=(target,),
        purpose="CONTINUE_PROBLEM_READ",
    )
    facade.check_request(request)
    for changes in [
        {"subject_principal_id": "human:admin"},
        {"scope": AuthorityScope("other", "quality")},
        {"members": (ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:two"),)},
        {
            "members": (
                ExactGrant("BUSINESS_PROBLEM", "CREATE", "business-problem:collection"),
            )
        },
    ]:
        with pytest.raises(AuthorityError):
            facade.check_request(SimpleNamespace(**{**vars(request), **changes}))
    with pytest.raises(AuthorityError):
        facade.decide_request(context(), SimpleNamespace(request_id="one"))


def test_only_selected_mutations_are_exposed():
    prefix = "/api/workbench/v1"
    assert not mutation_allowed("POST", prefix + "/problems")
    assert mutation_allowed("POST", prefix + "/problems", True)
    assert mutation_allowed(
        "POST", prefix + "/authorization/grant-requests/one/decisions", True
    )
    for path in [
        "/problems/one",
        "/problems/one/transitions",
        "/draft-assistance/invocations",
        "/authorization/grant-requests/one/other/decisions",
    ]:
        assert not mutation_allowed("POST", prefix + path, True)
