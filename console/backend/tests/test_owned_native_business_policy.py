import json
from copy import deepcopy
from hashlib import sha256

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_data_adapters import capabilities
from agent_console.owned_business_native_policy import OwnedBusinessPolicyV4
from agent_console.owned_business_policy import OwnedBusinessPolicy
from agent_console.resource_automation_policy import source_digest
from test_owned_business_policy import document


def candidate():
    old = document()
    value = deepcopy(old)
    value.update(
        schemaVersion="owned-business-admission.v4",
        retainedReadPolicyDigests=[OwnedBusinessPolicy.model_validate(old).digest],
        independentGoalProfile={
            "profileRevisionId": "test",
            "profileDigest": "a" * 64,
            "adapterRevision": "v4-structured-conversation",
        },
    )
    scope = deepcopy(value["scopes"][0])
    descriptor = capabilities("synthetic-delivery-source.v1")[0]
    scope.update(
        case="native_readonly",
        scopeId="native",
        documentRules=None,
        sourceSchema=descriptor["sourceSchema"],
        adapter=descriptor,
        operations=descriptor["operations"],
    )
    content = {
        "documents": [
            {"chunks": [{"content": json.dumps(source_document(), ensure_ascii=False)}]}
        ]
    }
    content["documents"][0]["contentDigest"] = sha256(
        content["documents"][0]["chunks"][0]["content"].encode()
    ).hexdigest()
    scope["sourceContentDigest"] = source_digest(content)
    value["scopes"] = [scope]
    return value, content


def test_v4_exact_source_adapter_and_old_model_stays_closed(tmp_path):
    raw, content = candidate()
    with pytest.raises(ValueError):
        OwnedBusinessPolicy.model_validate(raw)
    policy = OwnedBusinessPolicyV4.model_validate(raw)
    metadata = {
        "source": raw["scopes"][0]["source"],
        "sourceSchema": raw["scopes"][0]["sourceSchema"],
        "sourceContentDigest": raw["scopes"][0]["sourceContentDigest"],
    }
    assert policy.validate_source(metadata, content).case == "native_readonly"
    path = tmp_path / "v4.json"
    path.write_text(json.dumps(raw))
    path.chmod(0o600)
    assert OwnedBusinessPolicy.load(path) == policy
    for key, value in [
        ("sourceSchema", "sales-diagnostic-source.v1"),
        ("sourceContentDigest", "f" * 64),
    ]:
        with pytest.raises(AuthorityError):
            policy.selected({**metadata, key: value})
    altered = deepcopy(content)
    altered["documents"][0]["chunks"][0]["content"] += " "
    with pytest.raises(AuthorityError, match="SOURCE_CORRUPT"):
        policy.validate_source(metadata, altered)


@pytest.mark.parametrize(
    "field,value", [("subjectId", "human:someone-else"), ("externalWrites", True)]
)
def test_original_actor_and_effect_boundary_remain(field, value):
    raw, _ = candidate()
    raw[field] = value
    with pytest.raises(ValueError):
        OwnedBusinessPolicyV4.model_validate(raw)


def test_legacy_scope_still_uses_original_selection():
    raw, _ = candidate()
    raw["scopes"] = document()["scopes"]
    policy = OwnedBusinessPolicyV4.model_validate(raw)
    scope = policy.scopes[0]
    assert (
        policy.selected(
            {
                "source": scope.source.model_dump(),
                "sourceSchema": "document-review-source.v1",
                "sourceContentDigest": scope.sourceContentDigest,
            }
        )
        == scope
    )
