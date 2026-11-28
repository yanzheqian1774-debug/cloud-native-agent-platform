"""Retained source content never substitutes current business-use authority."""

import json
from copy import deepcopy
from hashlib import sha256

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_admission import observed_source
from agent_console.owned_business_policy import OwnedBusinessPolicy
from agent_console.plan_suggestion_domain import PlanningError
from agent_console.resource_automation_policy import source_digest
from test_native_document_tools import SOURCE
from test_owned_business_policy import document


def source(schema="document-review-source.v1", synthetic=True):
    value = deepcopy(SOURCE)
    value.update(schemaVersion=schema, synthetic=synthetic)
    raw = json.dumps(value)
    return {
        "documents": [
            {
                "contentDigest": sha256(raw.encode()).hexdigest(),
                "chunks": [{"content": raw}],
            }
        ]
    }


def test_retained_exact_content_read_does_not_authorize_future_old_source():
    content = source()
    policy = document()
    metadata = {
        "source": deepcopy(policy["scopes"][0]["source"]),
        "sourceSchema": "document-review-source.v1",
        "sourceContentDigest": source_digest(content),
    }
    policy["scopes"][0]["source"]["resource_id"] = "knowledge:authorized-successor"
    observed_source(metadata, content)
    with pytest.raises(AuthorityError, match="SOURCE_NOT_AUTHORIZED"):
        OwnedBusinessPolicy.model_validate(policy).selected(metadata)


@pytest.mark.parametrize("damage", ["content", "schema", "synthetic", "unknown_schema"])
def test_retained_content_digest_and_type_still_required(damage):
    content = source()
    metadata = {
        "sourceSchema": "document-review-source.v1",
        "sourceContentDigest": source_digest(content),
    }
    if damage == "content":
        value = deepcopy(SOURCE)
        value["title"] += "changed"
        raw = json.dumps(value)
        content["documents"][0].update(
            contentDigest=sha256(raw.encode()).hexdigest(), chunks=[{"content": raw}]
        )
    elif damage == "schema":
        metadata["sourceSchema"] = "sales-diagnostic-source.v1"
    elif damage == "synthetic":
        content = source(synthetic=False)
        metadata["sourceContentDigest"] = content["documents"][0]["contentDigest"]
    else:
        content = source(schema="unknown-source.v1")
        metadata.update(
            sourceSchema="unknown-source.v1",
            sourceContentDigest=content["documents"][0]["contentDigest"],
        )
    with pytest.raises((AuthorityError, ValueError, PlanningError)):
        observed_source(metadata, content)


@pytest.mark.parametrize(
    "schema",
    [
        "document-review-source.v1",
        "sales-diagnostic-source.v1",
        "synthetic-delivery-source.v1",
        "tabular-diagnostic-source.v1",
    ],
)
@pytest.mark.parametrize(
    "damage", [None, "metadata_schema", "synthetic", "digest", "corrupt_digest"]
)
def test_all_existing_readonly_source_contracts(schema, damage):
    from pathlib import Path

    from agent_console.delivery_resource_bundle import source_document as delivery
    from agent_console.sales_resource_bundle import source_document as sales
    from test_native_diagnostic_tools import SOURCE as TABULAR

    if schema == "document-review-source.v1":
        value = deepcopy(SOURCE)
    elif schema == "sales-diagnostic-source.v1":
        value = sales(
            (
                Path(__file__).resolve().parents[3]
                / "examples/sales-diagnostic/synthetic-sales.csv"
            ).read_bytes()
        )
    elif schema == "synthetic-delivery-source.v1":
        value = delivery()
    else:
        value = deepcopy(TABULAR)
    if damage == "synthetic":
        value["synthetic"] = False
    raw = json.dumps(value)
    digest = sha256(raw.encode()).hexdigest()
    content = {"documents": [{"contentDigest": digest, "chunks": [{"content": raw}]}]}
    metadata = {"sourceSchema": schema, "sourceContentDigest": digest}
    if damage == "metadata_schema":
        metadata["sourceSchema"] = "not-registered-source.v1"
    elif damage == "digest":
        metadata["sourceContentDigest"] = "0" * 64
    elif damage == "corrupt_digest":
        content["documents"][0]["contentDigest"] = "0" * 64
    if damage is None:
        observed_source(metadata, content)
    else:
        with pytest.raises((AuthorityError, ValueError, PlanningError)):
            observed_source(metadata, content)
