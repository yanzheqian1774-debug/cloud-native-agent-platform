"""Focused tests for the internal Definition publication authority."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from agent_console.definition_authority import (
    DefinitionAuthorityError,
    InMemoryDefinitionAuthority,
    MatchAuthorizationAction,
    PublicationAction,
    ReplacementEffect,
    RoleDescriptor,
    canonical_digest,
    canonical_json,
    create_definition_version,
    create_match_authorization_decision,
    create_publication_decision,
)

NOW = datetime(2026, 8, 28, 12, tzinfo=UTC)


def role(**overrides):
    values = {
        "title": "Supplier Quality Analyst",
        "duties": ("Analyze exceptions",),
        "data": ("supplier-quality",),
        "knowledge": ("quality-procedure",),
        "skills": ("root-cause-analysis",),
        "capabilities": ("quality.read",),
        "runtimes": ("native",),
    }
    values.update(overrides)
    return RoleDescriptor.create(**values)


def version(number=1, **overrides):
    values = {
        "definition_id": "definition.supplier-quality",
        "version_id": f"v{number}",
        "role": role(),
        "source_authoring_revision_id": f"authoring-revision-{number}",
        "source_authority_kind": "internal-authoring",
        "source_authority_revision": "source-revision-1",
        "source_authoring_state": "APPROVED",
        "tenant_id": "tenant-a",
        "security_domain": "quality",
        "provenance": "human-governed",
        "created_at": NOW,
    }
    values.update(overrides)
    return create_definition_version(**values)


def publish(item, suffix="1", **overrides):
    values = {
        "version": item,
        "decision_id": f"publication-{item.version_id}-{suffix}",
        "replay_identity": f"publication-replay-{item.version_id}-{suffix}",
        "action": PublicationAction.PUBLISH,
        "actor": "human-reviewer",
        "reason_code": "CURATED_RELEASE",
        "policy_ref": "definition-publication-v1",
        "decided_at": NOW,
        "effective_at": NOW,
        "provenance": "human-decision",
    }
    values.update(overrides)
    return create_publication_decision(**values)


def grant(item, suffix="1", **overrides):
    values = {
        "version": item,
        "decision_id": f"authorization-{item.version_id}-{suffix}",
        "replay_identity": f"authorization-replay-{item.version_id}-{suffix}",
        "purpose": "published-role-matching",
        "action": MatchAuthorizationAction.GRANT,
        "authority": "policy-authority",
        "reason_code": "MATCH_SCOPE_GRANTED",
        "policy_ref": "match-policy-v1",
        "decided_at": NOW,
        "effective_at": NOW,
        "provenance": "policy-decision",
    }
    values.update(overrides)
    return create_match_authorization_decision(**values)


def authority_with(item):
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    authority.register(item)
    authority.append_publication(publish(item))
    authority.append_match_authorization(grant(item))
    return authority


def snapshot(authority, **overrides):
    values = {
        "tenant_id": "tenant-a",
        "security_domain": "quality",
        "purpose": "published-role-matching",
        "evaluation_time": NOW,
        "workflow_revision_id": "canonical-workflow-revision-1",
        "workflow_digest": "a" * 64,
    }
    values.update(overrides)
    return authority.snapshot(**values)


def test_canonical_serialization_normalizes_nfc_keys_and_set_like_arrays() -> None:
    composed = role(duties=("Café review", "Analyze exceptions"))
    decomposed = role(duties=("Café review", "Analyze exceptions"))
    assert composed == decomposed
    first = version(role=composed)
    second = version(role=decomposed)
    assert first.definition_digest == second.definition_digest
    assert canonical_json({"b": 1, "a": "Café"}) == canonical_json(
        {"a": "Café", "b": 1}
    )
    assert canonical_json({"ordered": ("first", "second")}) != canonical_json(
        {"ordered": ("second", "first")}
    )
    with pytest.raises(
        DefinitionAuthorityError, match="AMBIGUOUS_CANONICAL_SERIALIZATION"
    ):
        canonical_json({"é": 1, "é": 2})
    with pytest.raises(
        DefinitionAuthorityError, match="AMBIGUOUS_CANONICAL_SERIALIZATION"
    ):
        canonical_json({"floating": 1.5})


def test_definition_digest_rejects_substitution_and_unknown_contract() -> None:
    item = version()
    with pytest.raises(DefinitionAuthorityError, match="INVALID_DEFINITION_DIGEST"):
        replace(item, definition_digest="0" * 64).validate()
    with pytest.raises(DefinitionAuthorityError, match="INVALID_DEFINITION_DIGEST"):
        replace(item, digest_contract_version="unknown").validate()


def test_approved_is_required_but_does_not_publish() -> None:
    with pytest.raises(DefinitionAuthorityError, match="AUTHORING_APPROVAL_REQUIRED"):
        version(source_authoring_state="DRAFT")
    item = version()
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    authority.register(item)
    with pytest.raises(DefinitionAuthorityError, match="DEFINITION_UNPUBLISHED"):
        snapshot(authority)


def test_publication_and_authorization_are_both_required() -> None:
    item = version()
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    authority.register(item)
    authority.append_publication(publish(item))
    with pytest.raises(DefinitionAuthorityError, match="MATCH_AUTHORIZATION_MISSING"):
        snapshot(authority)
    authority.append_match_authorization(grant(item))
    assert snapshot(authority).definitions[0].version == item


@pytest.mark.parametrize(
    "timestamp",
    [
        datetime(2026, 8, 28, 12),
        datetime(2026, 8, 28, 20, tzinfo=timezone(timedelta(hours=8))),
    ],
)
def test_naive_and_non_utc_decision_timestamps_fail(timestamp) -> None:
    with pytest.raises(DefinitionAuthorityError, match="INVALID_DECISION_TIMESTAMP"):
        publish(version(), decided_at=timestamp)


def test_inclusive_effective_time_and_exclusive_expiry() -> None:
    item = version()
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    authority.register(item)
    authority.append_publication(publish(item))
    authority.append_match_authorization(
        grant(item, expires_at=NOW + timedelta(hours=1))
    )
    assert snapshot(authority, evaluation_time=NOW).definitions
    with pytest.raises(DefinitionAuthorityError, match="MATCH_AUTHORIZATION_EXPIRED"):
        snapshot(authority, evaluation_time=NOW + timedelta(hours=1))


def test_invalid_expiry_and_snapshot_clock_fail_closed() -> None:
    item = version()
    with pytest.raises(DefinitionAuthorityError, match="INVALID_EXPIRY"):
        grant(item, expires_at=NOW)
    authority = authority_with(item)
    with pytest.raises(DefinitionAuthorityError, match="INVALID_EVALUATION_TIME"):
        snapshot(authority, evaluation_time=NOW.replace(tzinfo=None))


def test_registration_and_decision_replay_are_idempotent_and_conflicts_fail() -> None:
    item = version()
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    assert authority.register(item) == authority.register(item)
    conflicting = version(role=role(title="Different role"))
    with pytest.raises(
        DefinitionAuthorityError, match="CONFLICTING_DEFINITION_VERSION"
    ):
        authority.register(conflicting)
    publication = publish(item)
    assert authority.append_publication(publication) == authority.append_publication(
        publication
    )
    with pytest.raises(
        DefinitionAuthorityError, match="CONFLICTING_PUBLICATION_DECISION"
    ):
        authority.append_publication(
            replace(publication, action=PublicationAction.UNPUBLISH)
        )
    authorization = grant(item)
    assert authority.append_match_authorization(
        authorization
    ) == authority.append_match_authorization(authorization)
    with pytest.raises(
        DefinitionAuthorityError, match="CONFLICTING_MATCH_AUTHORIZATION"
    ):
        authority.append_match_authorization(
            replace(authorization, action=MatchAuthorizationAction.DENY)
        )


def test_decisions_bind_source_revision_and_cannot_replay_across_versions() -> None:
    first, second = version(1), version(2)
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    authority.register(first)
    authority.register(second)
    first_publication = publish(first)
    authority.append_publication(first_publication)
    with pytest.raises(DefinitionAuthorityError, match="MALFORMED_AUTHORITY_RECORD"):
        authority.append_publication(
            replace(first_publication, source_authority_revision="substituted")
        )
    with pytest.raises(
        DefinitionAuthorityError, match="CONFLICTING_PUBLICATION_DECISION"
    ):
        authority.append_publication(
            publish(
                second,
                decision_id="publication-v2-distinct",
                replay_identity=first_publication.replay_identity,
            )
        )
    first_authorization = grant(first)
    authority.append_match_authorization(first_authorization)
    with pytest.raises(
        DefinitionAuthorityError, match="CONFLICTING_MATCH_AUTHORIZATION"
    ):
        authority.append_match_authorization(
            grant(
                second,
                decision_id="authorization-v2-distinct",
                replay_identity=first_authorization.replay_identity,
                purpose="another-purpose",
            )
        )


def test_directly_constructed_malformed_authority_records_fail_closed() -> None:
    item = version()
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    with pytest.raises(DefinitionAuthorityError, match="INVALID_DEFINITION_ID"):
        authority.register(replace(item, definition_id="invalid identity"))
    authority.register(item)
    with pytest.raises(DefinitionAuthorityError, match="IDENTIFIER_LIMIT_EXCEEDED"):
        authority.append_publication(replace(publish(item), actor="a" * 201))
    with pytest.raises(DefinitionAuthorityError, match="INVALID_DECISION_TIMESTAMP"):
        authority.append_match_authorization(
            replace(grant(item), decided_at=NOW.replace(tzinfo=None))
        )


def test_simultaneous_contradictory_decisions_fail_complete_projection() -> None:
    item = version()
    authority = authority_with(item)
    authority.append_match_authorization(
        grant(
            item,
            "2",
            action=MatchAuthorizationAction.DENY,
        )
    )
    with pytest.raises(DefinitionAuthorityError, match="CONFLICTING_AUTHORITY_RECORDS"):
        snapshot(authority)


@pytest.mark.parametrize(
    ("publication_action", "authorization_action", "code"),
    [
        (PublicationAction.UNPUBLISH, None, "PUBLICATION_NOT_EFFECTIVE"),
        (PublicationAction.REVOKE_PUBLICATION, None, "PUBLICATION_NOT_EFFECTIVE"),
        (None, MatchAuthorizationAction.DENY, "MATCH_AUTHORIZATION_DENIED"),
        (None, MatchAuthorizationAction.REVOKE, "MATCH_AUTHORIZATION_REVOKED"),
    ],
)
def test_unpublication_and_revocation_preserve_history_and_exclude_future_matches(
    publication_action, authorization_action, code
) -> None:
    item = version()
    authority = authority_with(item)
    if publication_action is not None:
        authority.append_publication(
            publish(
                item,
                "2",
                action=publication_action,
                decided_at=NOW + timedelta(minutes=1),
                effective_at=NOW + timedelta(minutes=1),
            )
        )
    if authorization_action is not None:
        authority.append_match_authorization(
            grant(
                item,
                "2",
                action=authorization_action,
                decided_at=NOW + timedelta(minutes=1),
                effective_at=NOW + timedelta(minutes=1),
            )
        )
    before = len(authority.evidence)
    with pytest.raises(DefinitionAuthorityError, match=code):
        snapshot(authority, evaluation_time=NOW + timedelta(minutes=2))
    assert len(authority.evidence) == before


def test_newer_version_does_not_exclude_predecessor_without_explicit_binding() -> None:
    first, second = version(1), version(2)
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    for item in (first, second):
        authority.register(item)
        authority.append_publication(publish(item))
        authority.append_match_authorization(grant(item))
    assert [item.version.version_id for item in snapshot(authority).definitions] == [
        "v1",
        "v2",
    ]


def test_effective_successor_excludes_predecessor_from_future_snapshot() -> None:
    first, second = version(1), version(2)
    authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
    for item in (first, second):
        authority.register(item)
        authority.append_match_authorization(grant(item))
    authority.append_publication(publish(first))
    authority.append_publication(
        publish(
            second,
            predecessor=first,
            replacement_effect=ReplacementEffect.EXCLUDE_PREDECESSOR_FOR_MATCH,
        )
    )
    assert [item.version.version_id for item in snapshot(authority).definitions] == [
        "v2"
    ]
    assert first in authority._versions.values()


def test_scope_is_exact_and_cross_scope_candidate_is_not_disclosed() -> None:
    foreign = version(tenant_id="tenant-b", security_domain="restricted")
    authority = authority_with(foreign)
    result = snapshot(authority)
    assert result.definitions == ()
    assert "definition.supplier-quality" not in canonical_json(result)
    for field, value, code in (
        ("tenant_id", "", "TENANT_SCOPE_MISMATCH"),
        ("security_domain", "", "SECURITY_DOMAIN_SCOPE_MISMATCH"),
    ):
        with pytest.raises(DefinitionAuthorityError, match=code):
            snapshot(authority, **{field: value})


def test_snapshot_identity_and_order_are_input_permutation_independent() -> None:
    items = (
        version(2, definition_id="definition.b"),
        version(1, definition_id="definition.a"),
    )
    snapshots = []
    for ordered in (items, tuple(reversed(items))):
        authority = InMemoryDefinitionAuthority(source_authority_revision="catalog-r1")
        for item in ordered:
            authority.register(item)
            authority.append_publication(publish(item))
            authority.append_match_authorization(grant(item))
        snapshots.append(snapshot(authority))
    assert snapshots[0].snapshot_id == snapshots[1].snapshot_id
    assert [item.version.definition_id for item in snapshots[0].definitions] == [
        "definition.a",
        "definition.b",
    ]


def test_identifier_and_semantic_text_exact_boundaries() -> None:
    assert version(definition_id="a" * 200).definition_id == "a" * 200
    with pytest.raises(DefinitionAuthorityError, match="IDENTIFIER_LIMIT_EXCEEDED"):
        version(definition_id="a" * 201)
    assert len(role(title="x" * 500).title) == 500
    with pytest.raises(DefinitionAuthorityError, match="SEMANTIC_TEXT_LIMIT_EXCEEDED"):
        role(title="x" * 501)


def test_canonical_digest_is_domain_separated() -> None:
    value = {"identity": "same"}
    assert canonical_digest(value, domain="a") != canonical_digest(value, domain="b")
