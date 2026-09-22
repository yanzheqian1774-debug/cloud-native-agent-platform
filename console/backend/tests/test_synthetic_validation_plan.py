"""D324-7 explicit provenance, legacy hashes, no implicit model or approval."""

from types import SimpleNamespace

import pytest
from agent_console.plan_suggestion_domain import (
    PlanningError,
    ProposalRevision,
    SyntheticValidationOrigin,
)
from agent_console.resource_use_domain import canonical_digest
from pydantic import ValidationError
from test_plan_suggestion_v2 import proposal


def test_legacy_proposal_digest_and_json_are_unchanged():
    value = proposal()
    record = value.model_dump(mode="json")
    assert "origin" not in record
    assert value.digest == canonical_digest(record)
    assert ProposalRevision.model_validate(record) == value


def synthetic():
    old = proposal()
    return ProposalRevision(
        **{**old.model_dump(mode="json"), "invocation_id": None},
        origin=SyntheticValidationOrigin(
            namespace="s5-324-native-capability",
            security_domain="isolated-native-validation",
            root=old.semantics.target.problem,
            source_snapshot=old.semantics.target.problem,
            mapping_digest="a" * 64,
            prepared_by="human:test",
        ),
    )


def test_synthetic_source_is_explicit_and_cannot_carry_invocation():
    value = synthetic()
    assert value.invocation_id is None
    assert (
        value.model_dump(mode="json")["origin"]["kind"] == "HUMAN_SYNTHETIC_VALIDATION"
    )
    for record in (
        {**value.model_dump(mode="json"), "invocation_id": "fake-model"},
        {**proposal().model_dump(mode="json"), "invocation_id": None},
    ):
        with pytest.raises(ValidationError):
            ProposalRevision.model_validate(record)


def test_synthetic_root_cannot_be_substituted():
    record = synthetic().model_dump(mode="json")
    record["origin"]["root"]["resource_id"] = "other"
    with pytest.raises(ValidationError, match="ROOT_MISMATCH"):
        ProposalRevision.model_validate(record)


def test_governed_provider_entry_rejects_synthetic_source_before_io():
    from agent_console.plan_suggestion_application import PlanningApplication

    with pytest.raises(PlanningError, match="GOVERNED_SOURCE_REQUIRED"):
        PlanningApplication(None, None, None).save_suggestion(None, synthetic())


def test_repository_rejects_cross_scope_before_write():
    from agent_console.plan_suggestion_postgres import PostgresPlanningRepository

    with pytest.raises(PlanningError, match="SCOPE_DENIED"):
        PostgresPlanningRepository(None).add_proposal(
            None,
            SimpleNamespace(
                namespace="s5-323-demo", security_domain="isolated-real-demo"
            ),
            synthetic(),
        )
