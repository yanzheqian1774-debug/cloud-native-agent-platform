"""Standing scope is exact and separate from conversation/model permission."""

from copy import deepcopy

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_policy import OwnedBusinessPolicy
from pydantic import ValidationError


def document():
    def ref(name):
        return dict(resource_id=name, revision_id=name + ":r1", digest="a" * 64)

    source = ref("source")
    return dict(
        schemaVersion="owned-business-admission.v1",
        policyId="test",
        policyVersion="1",
        enabled=False,
        tenantId="s5-323-demo",
        securityDomain="isolated-real-demo",
        subjectId="human:demo323-approver",
        accountId="local-account:reviewer324",
        rootPolicyDigest="a" * 64,
        rootUnderstandingPolicyDigest="b" * 64,
        adoptionPolicyDigest="c" * 64,
        ledgerId="ledger:f3-main-experience:20261112",
        allowanceId="existing",
        expiresAt="2026-11-13T20:00:00Z",
        externalWrites=False,
        scopes=[
            dict(
                scopeId="document",
                authorizationBasisDigest="d" * 64,
                source=source,
                sourceContentDigest="e" * 64,
                case="document",
                capability=None,
                employees=[ref("employee")],
                agents=[ref("agent")],
                skills=[ref("skill")],
                runtimes=[ref("runtime")],
                nativeAgentName="document-check",
                operations=["check"],
                effectPolicy="READ_ONLY",
                externalWrites=False,
                documentRules=dict(
                    ontology=ref("rules"),
                    mapping_code="document",
                    source=source,
                    scope="production",
                ),
            )
        ],
    )


def test_direct_employee_scope_needs_no_invented_capability():
    policy = OwnedBusinessPolicy.model_validate(document())
    scope = policy.scopes[0]
    assert policy.enabled is False and scope.capability is None
    assert (
        policy.selected(
            dict(
                source=scope.source.model_dump(),
                sourceContentDigest=scope.sourceContentDigest,
                sourceSchema="document-review-source.v1",
            )
        )
        == scope
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("agents", []),
        ("skills", []),
        ("employees", []),
        ("runtimes", []),
        ("operations", []),
        ("externalWrites", True),
        ("effectPolicy", "WRITE"),
    ],
)
def test_optional_capability_does_not_relax_exact_execution_tuple(field, value):
    data = document()
    data["scopes"][0][field] = value
    with pytest.raises(ValidationError):
        OwnedBusinessPolicy.model_validate(data)


def test_no_source_or_changed_source_never_authorizes_business():
    policy = OwnedBusinessPolicy.model_validate(document())
    with pytest.raises(AuthorityError, match="SOURCE_REQUIRED"):
        policy.selected(None)
    metadata = dict(
        source=policy.scopes[0].source.model_dump(),
        sourceContentDigest="f" * 64,
        sourceSchema="document-review-source.v1",
    )
    with pytest.raises(AuthorityError, match="SOURCE_NOT_AUTHORIZED"):
        policy.selected(metadata)


def test_ambiguous_source_and_unrelated_rule_binding_rejected():
    data = document()
    duplicate = deepcopy(data["scopes"][0])
    duplicate["scopeId"] = "different-name-same-source"
    data["scopes"].append(duplicate)
    with pytest.raises(ValidationError, match="AMBIGUOUS"):
        OwnedBusinessPolicy.model_validate(data)
    data = document()
    data["scopes"][0]["documentRules"]["source"] = dict(
        data["scopes"][0]["source"],
        digest="f" * 64,
    )
    with pytest.raises(ValidationError, match="DOCUMENT_BINDING_REQUIRED"):
        OwnedBusinessPolicy.model_validate(data)
