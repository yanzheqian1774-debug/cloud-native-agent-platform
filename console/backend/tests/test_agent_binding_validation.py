import pytest
from agent_console.agent_binding_validation import (
    BindingResolution,
    BindingValidationFailure,
    validate_bindings,
)
from agent_console.agent_definition_repository import DefinitionScope


class Resolver:
    def resolve(self, scope, kind, resource_id):
        if scope.namespace != "tenant-a" or resource_id == "missing":
            return None
        return BindingResolution(
            resource_id,
            f"{kind}-revision:1",
            "a" * 64,
            True,
            True,
            tools=("search",),
            snapshots=("snapshot:1",),
        )


def test_exact_published_resources_validate_and_model_stays_unverified() -> None:
    result = validate_bindings(
        DefinitionScope("tenant-a", "quality"),
        {
            "skills": [
                {
                    "resourceId": "skill:1",
                    "revisionId": "skill-revision:1",
                    "digest": "a" * 64,
                }
            ],
            "mcpTools": [
                {
                    "resourceId": "mcp:1",
                    "revisionId": "mcp-revision:1",
                    "digest": "a" * 64,
                    "toolName": "search",
                }
            ],
            "knowledge": [
                {
                    "resourceId": "knowledge:1",
                    "revisionId": "knowledge-revision:1",
                    "digest": "a" * 64,
                    "snapshotId": "snapshot:1",
                }
            ],
            "model": {"kind": "model", "resourceId": "opaque:model"},
        },
        Resolver(),
    )
    assert result[-1]["status"] == "UNVERIFIED_OPAQUE_REFERENCE"


@pytest.mark.parametrize(
    "field,reason",
    [
        ("workflow", "WORKFLOW_RESOLVER_UNAVAILABLE"),
        ("runtimeProfile", "RUNTIME_PROFILE_RESOLVER_UNAVAILABLE"),
    ],
)
def test_supplied_future_reference_fails_closed_without_resolver(field, reason) -> None:
    with pytest.raises(BindingValidationFailure, match=reason):
        validate_bindings(
            DefinitionScope("tenant-a", "quality"),
            {
                field: {
                    "kind": field,
                    "resourceId": "future:1",
                    "revisionId": "r1",
                    "digest": "a" * 64,
                }
            },
            None,
        )


def test_omitted_future_references_are_valid_without_fake_authority() -> None:
    assert validate_bindings(DefinitionScope("tenant-a", "quality"), {}, None) == []


def test_scope_mismatch_is_nondisclosing_not_found() -> None:
    with pytest.raises(BindingValidationFailure, match="BOUND_RESOURCE_NOT_FOUND"):
        validate_bindings(
            DefinitionScope("tenant-b", "quality"),
            {
                "skills": [
                    {
                        "resourceId": "skill:1",
                        "revisionId": "skill-revision:1",
                        "digest": "a" * 64,
                    }
                ]
            },
            Resolver(),
        )
