"""Contract tests for the internal immutable Solution Blueprint."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from agent_console.solution_blueprint import (
    AssetReference,
    BlueprintContractError,
    canonical_json,
    create_solution_blueprint,
)

NOW = datetime(2026, 8, 30, 8, tzinfo=UTC)
DIGEST = "a" * 64


def ref(name: str, version: str = "v1", value: str = DIGEST) -> AssetReference:
    return AssetReference.create(
        asset_id=name, version_id=version, canonical_digest=value
    )


def blueprint(**overrides):
    values = {
        "blueprint_id": "blueprint.supplier-quality",
        "version_id": "v1",
        "tenant_id": "tenant-a",
        "security_domain": "quality",
        "created_at": NOW,
        "source_authority_revisions": (ref("authority", "r1"),),
        "provenance_classification": "human-governed",
        "lifecycle_decision_references": ("decision-1",),
        "problem_intent": "Resolve café supplier quality exceptions",
        "business_scope": ("supplier quality", "exception resolution"),
        "applicability_constraints": ("approved suppliers",),
        "exclusion_constraints": ("credential handling",),
        "canonical_workflow_revision": ref("workflow.supplier-quality", "r1"),
        "role_definition_references": (ref("definition.analyst"),),
        "skill_references": (ref("skill.root-cause"),),
        "mcp_capability_references": (ref("mcp.quality-read"),),
        "knowledge_references": (ref("knowledge.procedure"),),
        "runtime_requirement_references": (ref("runtime.native-requirement"),),
        "placement_requirement_references": (ref("placement.native"),),
        "permission_prerequisite_references": (ref("permission.quality-read"),),
        "authorization_prerequisite_references": (ref("authorization.match"),),
        "expected_outcomes": ("classified exception",),
        "acceptance_criteria": ("evidence linked",),
        "evidence_references": (ref("evidence.source"),),
        "provenance_references": (ref("provenance.source"),),
        "known_limitations": ("advisory only",),
        "configuration_generation_eligible": False,
    }
    values.update(overrides)
    return create_solution_blueprint(**values)


def test_canonical_bytes_digest_and_semantic_sets_are_deterministic() -> None:
    first = blueprint(business_scope=("supplier quality", "exception resolution"))
    second = blueprint(business_scope=("exception resolution", "supplier quality"))
    assert first.semantic_bytes == second.semantic_bytes
    assert first.canonical_digest == second.canonical_digest
    assert first.canonical_digest.islower() and len(first.canonical_digest) == 64


def test_unicode_nfc_normalization_is_stable() -> None:
    assert (
        blueprint(problem_intent="Resolve café exceptions").canonical_digest
        == blueprint(problem_intent="Resolve cafe\u0301 exceptions").canonical_digest
    )
    assert canonical_json({"intent": "cafe\u0301"}) == canonical_json(
        {"intent": "café"}
    )


def test_meaningful_semantic_and_trusted_scope_changes_change_identity() -> None:
    base = blueprint()
    assert (
        blueprint(problem_intent="Resolve a different exception").canonical_digest
        != base.canonical_digest
    )
    assert blueprint(tenant_id="tenant-b").canonical_digest != base.canonical_digest
    assert (
        blueprint(security_domain="restricted").canonical_digest
        != base.canonical_digest
    )


def test_forged_malformed_and_noncanonical_bindings_fail_closed() -> None:
    item = blueprint()
    with pytest.raises(BlueprintContractError, match="INVALID_CANONICAL_DIGEST"):
        replace(item, canonical_digest="0" * 64).validate()
    with pytest.raises(BlueprintContractError, match="INVALID_SCHEMA_VERSION"):
        replace(item, schema_version="future").validate()
    with pytest.raises(
        BlueprintContractError, match="AMBIGUOUS_CANONICAL_SERIALIZATION"
    ):
        canonical_json({"floating": 1.5})
    with pytest.raises(
        BlueprintContractError, match="AMBIGUOUS_CANONICAL_SERIALIZATION"
    ):
        canonical_json({"é": 1, "e\u0301": 2})


def test_missing_null_semantics_are_explicit_and_generation_is_denied() -> None:
    assert canonical_json({"missing": None}) != canonical_json({})
    with pytest.raises(BlueprintContractError, match="GENERATION_NOT_AUTHORIZED"):
        blueprint(configuration_generation_eligible=True)


def test_references_are_digest_bound_and_semantic_sets_reject_duplicates() -> None:
    base = blueprint()
    changed = blueprint(
        canonical_workflow_revision=ref("workflow.supplier-quality", "r1", "b" * 64)
    )
    assert changed.canonical_digest != base.canonical_digest
    with pytest.raises(BlueprintContractError, match="AMBIGUOUS_SEMANTIC_SET"):
        blueprint(business_scope=("same", "same"))


def test_successor_reference_is_semantic_and_predecessor_is_exact() -> None:
    first = blueprint()
    predecessor = ref(first.blueprint_id, first.version_id, first.canonical_digest)
    second = blueprint(version_id="v2", predecessor_version=predecessor)
    assert second.version_id == "v2"
    assert second.predecessor_version == predecessor
