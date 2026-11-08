"""Only explicitly configured new roots avoid the historical task binding."""

import hashlib
from copy import deepcopy
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


def sales_supplement_fixture():
    from agent_console.sales_gross_profit_evaluation import criterion_candidate
    from agent_console.sales_gross_profit_integration import SOURCE_DIGEST

    binding, context, _ = fixture()
    binding = binding.model_copy(update={"source_content_digest": SOURCE_DIGEST})
    revision = {
        **criterion_candidate("gross_profit_dimensions"),
        "created_by": context.principal_id,
        "revision": 1,
        "predecessor_revision_id": None,
    }
    return binding, context, {"revision": revision}


@pytest.mark.parametrize("enabled", [False, True])
def test_supplement_binding_requires_explicit_mode_and_all_seven_exact_contracts(
    enabled,
):
    from agent_console.sales_gross_profit_evaluation import CHECKS, criterion_candidate

    binding, context, result = sales_supplement_fixture()
    bound = bind_created_object(None, (binding,), sales_supplement_enabled=enabled)
    for check in CHECKS:
        result["revision"].update(criterion_candidate(check))
        if enabled:
            assert (
                bound(None, context, "SUCCESS_CRITERION", result, problem_id="new-root")
                is result
            )
        else:
            with pytest.raises(AuthorityError, match="INITIAL_CASE_CRITERION_DENIED"):
                bound(None, context, "SUCCESS_CRITERION", result, problem_id="new-root")


@pytest.mark.parametrize(
    "field,value",
    [
        ("criterion_type", "NUMERIC_THRESHOLD"),
        ("measurement", {"expected": False}),
        ("measurement", {"expected": 1}),
        ("required_evidence_kinds", []),
        ("evaluator_type", "SYNTHETIC_DELIVERY"),
        ("evaluator_version", "3"),
        ("created_by", "different"),
        ("revision", 2),
        ("predecessor_revision_id", "old-revision"),
        ("applicability", {"check": "gross_profit_dimensions"}),
    ],
)
def test_enabled_supplement_cannot_relax_exact_contract_or_actor(field, value):
    binding, context, result = sales_supplement_fixture()
    result["revision"][field] = value
    with pytest.raises(AuthorityError, match=r"INITIAL_CASE_.*DENIED"):
        bind_created_object(None, (binding,), sales_supplement_enabled=True)(
            None, context, "SUCCESS_CRITERION", result, problem_id="new-root"
        )


@pytest.mark.parametrize("field", ["sourceContentDigest", "contractDigest", "check"])
def test_enabled_supplement_pins_source_contract_and_check(field):
    binding, context, result = sales_supplement_fixture()
    result = deepcopy(result)
    result["revision"]["applicability"][field] = "changed"
    with pytest.raises(AuthorityError, match="INITIAL_CASE_CRITERION_DENIED"):
        bind_created_object(None, (binding,), sales_supplement_enabled=True)(
            None, context, "SUCCESS_CRITERION", result, problem_id="new-root"
        )


def test_enabled_supplement_retains_legacy_v1_and_configured_source_boundary():
    binding, context, result = sales_supplement_fixture()
    wrong_source = binding.model_copy(update={"source_content_digest": "b" * 64})
    with pytest.raises(AuthorityError, match="INITIAL_CASE_CRITERION_DENIED"):
        bind_created_object(None, (wrong_source,), sales_supplement_enabled=True)(
            None, context, "SUCCESS_CRITERION", result, problem_id="new-root"
        )
    result["revision"].update(
        evaluator_version="1",
        applicability={
            "check": "source",
            "sourceContentDigest": binding.source_content_digest,
        },
    )
    assert (
        bind_created_object(None, (binding,), sales_supplement_enabled=True)(
            None, context, "SUCCESS_CRITERION", result, problem_id="new-root"
        )
        is result
    )
