"""Focused tests for deterministic advisory published-role matching."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from agent_console.definition_authority import (
    DefinitionAuthorityError,
    InMemoryDefinitionAuthority,
    MatchAuthorizationAction,
    PublicationAction,
    RoleDescriptor,
    create_definition_version,
    create_match_authorization_decision,
    create_publication_decision,
)
from agent_console.matching import (
    MatchingError,
    MatchingRequest,
    MatchOutcome,
    PublishedRoleMatcher,
    RoleRequirement,
    TaskRoleRequirements,
    validate_candidate_evaluation_count,
    validate_serialized_matching_request_size,
)

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def definition(index: int, *, extra_skill=""):
    skills = ("analysis",) if not extra_skill else ("analysis", extra_skill)
    role = RoleDescriptor.create(
        title=f"Role {index}",
        duties=("analyze",),
        data=("quality-data",),
        knowledge=("quality-policy",),
        skills=skills,
        capabilities=("quality.read",),
        runtimes=("native",),
    )
    return create_definition_version(
        definition_id=f"definition.role-{index:03d}",
        version_id="v1",
        role=role,
        source_authoring_revision_id=f"authoring-{index}",
        source_authority_kind="internal-authoring",
        source_authority_revision="source-r1",
        source_authoring_state="APPROVED",
        tenant_id="tenant-a",
        security_domain="quality",
        provenance="human-governed",
        created_at=NOW,
    )


def authority(count=1):
    result = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    for index in range(count):
        item = definition(index)
        result.register(item)
        result.append_publication(
            create_publication_decision(
                version=item,
                decision_id=f"publication-{index}",
                replay_identity=f"publication-replay-{index}",
                action=PublicationAction.PUBLISH,
                actor="human-reviewer",
                reason_code="PUBLISHED",
                policy_ref="publication-v1",
                decided_at=NOW,
                effective_at=NOW,
                provenance="human-decision",
            )
        )
        result.append_match_authorization(
            create_match_authorization_decision(
                version=item,
                decision_id=f"authorization-{index}",
                replay_identity=f"authorization-replay-{index}",
                purpose="published-role-matching",
                action=MatchAuthorizationAction.GRANT,
                authority="policy-authority",
                reason_code="GRANTED",
                policy_ref="match-v1",
                decided_at=NOW,
                effective_at=NOW,
                provenance="policy-decision",
            )
        )
    return result


def requirement(index=0, **overrides):
    values = {
        "requirement_id": f"role-requirement-{index}",
        "duties": ("analyze",),
        "data": ("quality-data",),
        "knowledge": ("quality-policy",),
        "skills": ("analysis",),
        "capabilities": ("quality.read",),
        "runtimes": ("native",),
    }
    values.update(overrides)
    return RoleRequirement.create(**values)


def request(*, task_count=1, requirements_per_task=1, requirements=None):
    if requirements is None:
        counter = 0
        tasks = []
        for task_index in range(task_count):
            task_requirements = []
            for _ in range(requirements_per_task):
                task_requirements.append(requirement(counter))
                counter += 1
            tasks.append(
                TaskRoleRequirements(
                    f"task-requirement-{task_index}", tuple(task_requirements)
                )
            )
    else:
        tasks = [TaskRoleRequirements("task-requirement-0", tuple(requirements))]
    return MatchingRequest(
        canonical_workflow_revision_id="canonical-workflow-revision-1",
        approved_workflow_digest="a" * 64,
        tenant_id="tenant-a",
        security_domain="quality",
        purpose="published-role-matching",
        evaluation_time=NOW,
        tasks=tuple(tasks),
    )


def test_stable_selection_ties_and_zero_downstream_authority() -> None:
    matcher = PublishedRoleMatcher(authority(2))
    result = matcher.match(request())
    decision = result.decisions[0]
    assert decision.outcome is MatchOutcome.MATCHED
    assert decision.selected_definition_id == "definition.role-000"
    assert len(decision.tied_candidates) == 2
    assert "STABLE_TIE_BROKEN_BY_DEFINITION_VERSION_IDENTITY" in decision.reason_codes
    assert decision.advisory_only is True
    assert decision.execution_authorized is False
    assert (
        result.provider_calls,
        result.runtime_calls,
        result.credential_grants,
        result.permission_grants,
    ) == (0, 0, 0, 0)


def test_role_gap_is_honest_only_after_valid_empty_coverage() -> None:
    result = PublishedRoleMatcher(authority()).match(
        request(requirements=(requirement(skills=("unavailable-skill",)),))
    )
    decision = result.decisions[0]
    assert decision.outcome is MatchOutcome.ROLE_GAP
    assert decision.selected_definition_id is None
    assert decision.missing_requirements == (decision.requirement_id,)


def test_authority_failure_is_not_role_gap() -> None:
    item = definition(0)
    missing = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    missing.register(item)
    with pytest.raises(DefinitionAuthorityError, match="DEFINITION_UNPUBLISHED"):
        PublishedRoleMatcher(missing).match(request())
    with pytest.raises(MatchingError, match="DEFINITION_AUTHORITY_MISSING"):
        PublishedRoleMatcher(None)


def test_task_limit_exact_32_and_33() -> None:
    matcher = PublishedRoleMatcher(authority())
    assert len(matcher.match(request(task_count=32)).decisions) == 32
    with pytest.raises(MatchingError, match="TASK_LIMIT_EXCEEDED"):
        matcher.match(request(task_count=33))


def test_requirement_limit_exact_32_and_33() -> None:
    matcher = PublishedRoleMatcher(authority())
    assert len(matcher.match(request(requirements_per_task=32)).decisions) == 32
    with pytest.raises(MatchingError, match="REQUIREMENT_LIMIT_EXCEEDED"):
        matcher.match(request(requirements_per_task=33))


def test_candidate_limit_exact_64_and_65() -> None:
    assert len(PublishedRoleMatcher(authority(64)).match(request()).decisions) == 1
    with pytest.raises(DefinitionAuthorityError, match="CANDIDATE_LIMIT_EXCEEDED"):
        PublishedRoleMatcher(authority(65)).match(request())


def test_evaluation_limit_exact_2048_and_over() -> None:
    validate_candidate_evaluation_count(2_048)
    with pytest.raises(MatchingError, match="EVALUATION_LIMIT_EXCEEDED"):
        validate_candidate_evaluation_count(2_049)
    assert (
        len(
            PublishedRoleMatcher(authority(64))
            .match(request(requirements_per_task=32))
            .decisions
        )
        == 32
    )
    with pytest.raises(MatchingError, match="EVALUATION_LIMIT_EXCEEDED"):
        PublishedRoleMatcher(authority(63)).match(
            request(task_count=2, requirements_per_task=17)
        )


def test_reason_limit_exact_32_and_33() -> None:
    matcher = PublishedRoleMatcher(authority())
    snapshot = authority().snapshot(
        tenant_id="tenant-a",
        security_domain="quality",
        purpose="published-role-matching",
        evaluation_time=NOW,
        workflow_revision_id="canonical-workflow-revision-1",
        workflow_digest="a" * 64,
    )
    decision = matcher._decision(
        requirement(),
        snapshot,
        MatchOutcome.ROLE_GAP,
        None,
        (),
        (),
        tuple(f"R{i}" for i in range(32)),
    )
    assert len(decision.reason_codes) == 32
    with pytest.raises(MatchingError, match="REASON_LIMIT_EXCEEDED"):
        matcher._decision(
            requirement(),
            snapshot,
            MatchOutcome.ROLE_GAP,
            None,
            (),
            (),
            tuple(f"R{i}" for i in range(33)),
        )


def test_payload_limit_exact_32_kib_and_over() -> None:
    validate_serialized_matching_request_size(32 * 1024)
    with pytest.raises(MatchingError, match="MATCHING_REQUEST_PAYLOAD_LIMIT_EXCEEDED"):
        validate_serialized_matching_request_size(32 * 1024 + 1)


def test_matcher_identifier_and_semantic_text_exact_boundaries() -> None:
    assert requirement(requirement_id="a" * 200).requirement_id == "a" * 200
    with pytest.raises(MatchingError, match="IDENTIFIER_LIMIT_EXCEEDED"):
        requirement(requirement_id="a" * 201)
    assert requirement(skills=("x" * 500,)).skills == ("x" * 500,)
    with pytest.raises(MatchingError, match="SEMANTIC_TEXT_LIMIT_EXCEEDED"):
        requirement(skills=("x" * 501,))
    malformed = replace(requirement(), skills=("x" * 501,))
    with pytest.raises(MatchingError, match="SEMANTIC_TEXT_LIMIT_EXCEEDED"):
        PublishedRoleMatcher(authority()).match(request(requirements=(malformed,)))


def test_snapshot_content_substitution_is_rejected() -> None:
    provider = authority()
    governed = provider.snapshot(
        tenant_id="tenant-a",
        security_domain="quality",
        purpose="published-role-matching",
        evaluation_time=NOW,
        workflow_revision_id="canonical-workflow-revision-1",
        workflow_digest="a" * 64,
    )

    class SubstitutingProvider:
        def snapshot(self, **_kwargs):
            return replace(governed, snapshot_id="0" * 64)

    with pytest.raises(MatchingError, match="MALFORMED_AUTHORITY_RECORD"):
        PublishedRoleMatcher(SubstitutingProvider()).match(request())

    class ReferenceSubstitutingProvider:
        def snapshot(self, **_kwargs):
            return replace(governed, decision_references=("substituted",))

    with pytest.raises(MatchingError, match="MALFORMED_AUTHORITY_RECORD"):
        PublishedRoleMatcher(ReferenceSubstitutingProvider()).match(request())


def test_snapshot_reconstruction_rejects_missing_added_and_reordered_candidates() -> (
    None
):
    governed = authority(2).snapshot(
        tenant_id="tenant-a",
        security_domain="quality",
        purpose="published-role-matching",
        evaluation_time=NOW,
        workflow_revision_id="canonical-workflow-revision-1",
        workflow_digest="a" * 64,
    )

    class ReconstructingProvider:
        def __init__(self, snapshot):
            self._snapshot = snapshot

        def snapshot(self, **_kwargs):
            return self._snapshot

    substitutions = (
        replace(governed, definitions=governed.definitions[:-1]),
        replace(governed, definitions=governed.definitions + governed.definitions[:1]),
        replace(governed, definitions=tuple(reversed(governed.definitions))),
    )
    for substituted in substitutions:
        with pytest.raises(
            MatchingError,
            match=r"MALFORMED_AUTHORITY_RECORD|CONFLICTING_AUTHORITY_RECORDS",
        ):
            PublishedRoleMatcher(ReconstructingProvider(substituted)).match(request())


def test_requirement_and_task_permutations_do_not_change_decisions() -> None:
    requirements = (requirement(1), requirement(0))
    first = PublishedRoleMatcher(authority(2)).match(request(requirements=requirements))
    second = PublishedRoleMatcher(authority(2)).match(
        request(requirements=tuple(reversed(requirements)))
    )
    assert first == second


def test_requirement_set_like_order_is_canonical() -> None:
    first = requirement(skills=("analysis", "triage"))
    second = requirement(skills=("triage", "analysis"))
    assert first == second
    with pytest.raises(MatchingError, match="AMBIGUOUS_REQUIREMENT"):
        requirement(skills=("analysis", "analysis"))


def test_cross_scope_and_denied_candidate_details_do_not_leak() -> None:
    denied = authority()
    item = next(iter(denied._versions.values()))
    denied.append_match_authorization(
        create_match_authorization_decision(
            version=item,
            decision_id="authorization-deny",
            replay_identity="authorization-deny-replay",
            purpose="published-role-matching",
            action=MatchAuthorizationAction.DENY,
            authority="policy-authority",
            reason_code="SENSITIVE_POLICY_DETAIL",
            policy_ref="match-v1",
            decided_at=NOW.replace(minute=1),
            effective_at=NOW.replace(minute=1),
            provenance="policy-decision",
        )
    )
    with pytest.raises(DefinitionAuthorityError) as exc_info:
        PublishedRoleMatcher(denied).match(
            replace(request(), evaluation_time=NOW.replace(minute=2))
        )
    assert str(exc_info.value) == "MATCH_AUTHORIZATION_DENIED"
    assert "definition.role" not in str(exc_info.value)
    assert "SENSITIVE_POLICY_DETAIL" not in str(exc_info.value)
