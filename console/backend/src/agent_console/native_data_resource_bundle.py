"""Draft resource envelopes for an exact registered Native adapter; no publication."""

import json

from .native_data_adapters import resolve
from .native_data_skill import NativeDataSkillExecutor
from .prepared_resource_bundle import resource_content as base_content
from .skill_mcp_schemas import ResourceContent


def resource_content(source, descriptor):
    adapter = resolve(descriptor)
    adapter.validate(source)
    bundle = base_content()
    skill = bundle["skill"]
    skill.update(
        description="Registered read-only evidence analysis",
        instructions=(
            "Use only the exact source and registered tools. "
            "Preserve limitations; no external operations or business acceptance."
        ),
        capabilities=list(adapter.operations),
    )
    revision = NativeDataSkillExecutor(adapter).revision
    skill["operations"] = [
        op for op in skill["operations"] if op["name"] in adapter.operations
    ]
    for op in skill["operations"]:
        op.update(
            executorId=revision.executor_id,
            executorRevision=revision.executor_revision,
            executorConfigurationDigest=revision.configuration_digest,
        )
        op["inputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "native-data-input.v1"
        ]
        op["outputSchema"]["properties"]["schemaVersion"]["enum"] = [
            "native-data-output.v1"
        ]
        op["outputSchema"]["properties"]["operation"]["enum"] = list(adapter.operations)
        # New resource contract, same bounded per-attempt ceiling as document
        # Native resources. This never extends authority or model allowance.
        op["ioLimits"].update(policyId="native-data-bounds", timeoutMs=480000)
    bundle["skill"] = ResourceContent.model_validate(skill).model_dump(
        mode="json", exclude_none=True
    )
    bundle["agent"].update(
        title="Registered evidence analysis",
        businessPurpose="Read exact bounded source evidence without external effects.",
    )
    bundle["knowledge"] = {
        "sourceId": "synthetic-native-data",
        "documentId": "synthetic-native-data-source",
        "documentVersion": "1",
        "kind": "TEXT",
        "provenance": "EXPLICIT_SYNTHETIC_TEST_SOURCE",
        "content": json.dumps(
            source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    }
    return bundle
