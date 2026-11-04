"""Only explicitly configured new roots avoid the historical task binding."""

import hashlib
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.initial_case_creation import InitialCaseCreation, bind_created_object


def fixture():
    binding = InitialCaseCreation(
        tenant_id="tenant",
        security_domain="isolated",
        subject_id="human",
        root_id="new-root",
        title="sales",
        description_digest=hashlib.sha256(b"synthetic only").hexdigest(),
        source_content_digest="a" * 64,
    )
    context = SimpleNamespace(
        principal_id="human",
        scope=SimpleNamespace(tenant_id="tenant", security_domain="isolated"),
    )
    result = {
        "revision": {
            "business_problem_id": "new-root",
            "revision": 1,
            "title": "sales",
            "description": "synthetic only",
            "created_by": "human",
        }
    }
    return binding, context, result


def test_exact_creation_reuses_owner_grant_and_preserves_legacy_fallback():
    binding, context, result = fixture()
    calls = []
    bound = bind_created_object(
        lambda *a, **k: calls.append((a, k)) or "legacy", (binding,)
    )
    assert bound(None, context, "BUSINESS_PROBLEM", result) is result
    assert not calls
    context.principal_id = "different"
    assert bound(None, context, "BUSINESS_PROBLEM", result) == "legacy"
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("description", "changed"),
        ("title", "other"),
        ("revision", 2),
        ("created_by", "other"),
    ],
)
def test_exact_pinned_creation_rejects_changed_content(field, value):
    binding, context, result = fixture()
    result["revision"][field] = value
    with pytest.raises(AuthorityError, match="CREATION_DENIED"):
        bind_created_object(None, (binding,))(None, context, "BUSINESS_PROBLEM", result)


def test_new_criterion_cannot_borrow_supplier_applicability():
    binding, context, result = fixture()
    result = {
        "revision": {
            "created_by": "human",
            "evaluator_type": "SYNTHETIC_DELIVERY",
            "evaluator_version": "1",
            "applicability": {"check": "source", "sourceContentDigest": "a" * 64},
        }
    }
    with pytest.raises(AuthorityError, match="CRITERION_DENIED"):
        bind_created_object(None, (binding,))(
            None, context, "SUCCESS_CRITERION", result, problem_id="new-root"
        )
