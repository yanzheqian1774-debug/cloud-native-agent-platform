from copy import deepcopy

import pytest
from agent_console.delivery_resource_bundle import source_document
from agent_console.native_data_adapters import capabilities, resolve


def test_exact_registered_delivery_and_unsupported_sales():
    descriptors = capabilities("synthetic-delivery-source.v1")
    assert len(descriptors) == 1
    resolve(descriptors[0]).validate(source_document())
    assert capabilities("sales-diagnostic-source.v1") == []
    assert capabilities("unregistered-source.v9") == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("adapterRevision", "2"),
        ("configurationDigest", "f" * 64),
        ("sourceSchema", "sales-diagnostic-source.v1"),
        ("operations", ["START"]),
        ("externalWrites", True),
    ],
)
def test_descriptor_must_match_whole_registered_contract(field, value):
    descriptor = deepcopy(capabilities("synthetic-delivery-source.v1")[0])
    descriptor[field] = value
    with pytest.raises(ValueError, match="NOT_REGISTERED"):
        resolve(descriptor)


def test_body_validation_not_only_schema_label():
    adapter = resolve(capabilities("synthetic-delivery-source.v1")[0])
    with pytest.raises(Exception, match="ASSESSMENT_DATE"):
        adapter.validate(
            {"schemaVersion": adapter.source_schema, "synthetic": True, "orders": []}
        )


def test_runtime_descriptor_selection_default_off_and_exact():
    from agent_console.native_data_adapters import ADAPTERS, configured

    assert configured({}) == ()
    assert configured({"nativeDataAdapters": [ADAPTERS[1].descriptor()]}) == (
        ADAPTERS[1],
    )
    for value in (
        [],
        [ADAPTERS[1].descriptor()] * 2,
        [{"sourceSchema": "synthetic-delivery-source.v1"}],
    ):
        with pytest.raises(ValueError):
            configured({"nativeDataAdapters": value})
