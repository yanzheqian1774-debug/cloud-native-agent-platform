"""Authority and nondisclosure tests for Solution Blueprints."""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from agent_console.blueprint_authority import (
    BlueprintAuthorityError,
    InMemoryBlueprintAuthority,
    MatchAction,
    PublicationAction,
    ReviewAction,
    create_decision,
)
from test_solution_blueprint import NOW, blueprint, ref


def decision(item, facet, action, suffix="1", **overrides):
    values = {
        "blueprint": item,
        "decision_id": f"{facet.lower()}-{suffix}",
        "replay_identity": f"{facet.lower()}-replay-{suffix}",
        "facet": facet,
        "action": action,
        "scope": "registration" if facet == "REVIEW" else "catalog-a",
        "purpose": "registration" if facet == "REVIEW" else "solution-matching",
        "authority": "human-reviewer" if facet == "REVIEW" else "policy-authority",
        "reason_code": f"{facet}_DECISION",
        "decided_at": NOW,
        "effective_at": NOW,
    }
    values.update(overrides)
    return create_decision(**values)


def registered(item=None):
    item = item or blueprint()
    authority = InMemoryBlueprintAuthority()
    authority.propose(item)
    authority.append_decision(decision(item, "REVIEW", ReviewAction.APPROVE))
    authority.register(item)
    return authority, item


def visible(authority, item, **overrides):
    values = {
        "tenant_id": item.tenant_id,
        "security_domain": item.security_domain,
        "blueprint_id": item.blueprint_id,
        "version_id": item.version_id,
        "scope": "catalog-a",
        "purpose": "solution-matching",
        "at": NOW,
    }
    values.update(overrides)
    return authority.evaluate(**values)


def test_proposal_replay_is_idempotent_and_conflicting_version_fails() -> None:
    item = blueprint()
    authority = InMemoryBlueprintAuthority()
    assert authority.propose(item) is authority.propose(item)
    with pytest.raises(BlueprintAuthorityError, match="CONFLICTING_BLUEPRINT_VERSION"):
        authority.propose(blueprint(problem_intent="different semantics"))


def test_approved_does_not_imply_registered_or_published() -> None:
    item = blueprint()
    authority = InMemoryBlueprintAuthority()
    authority.propose(item)
    authority.append_decision(decision(item, "REVIEW", ReviewAction.APPROVE))
    assert authority.registered_versions == ()
    authority.register(item)
    assert visible(authority, item).available is False


def test_rejected_digest_cannot_register() -> None:
    item = blueprint()
    authority = InMemoryBlueprintAuthority()
    authority.propose(item)
    authority.append_decision(decision(item, "REVIEW", ReviewAction.REJECT))
    with pytest.raises(BlueprintAuthorityError, match="BLUEPRINT_REJECTED"):
        authority.register(item)


def test_registered_and_published_do_not_imply_match_authorized() -> None:
    authority, item = registered()
    authority.append_decision(decision(item, "PUBLICATION", PublicationAction.PUBLISH))
    result = visible(authority, item)
    assert result.available is False and result.execution_authorized is False


def test_match_authorization_is_discovery_only_never_execution() -> None:
    authority, item = registered()
    authority.append_decision(decision(item, "PUBLICATION", PublicationAction.PUBLISH))
    authority.append_decision(decision(item, "MATCH", MatchAction.GRANT))
    result = visible(authority, item)
    assert result.available and result.match_authorized
    assert result.execution_authorized is False


def test_unpublication_revocation_and_expiry_preserve_append_only_history() -> None:
    authority, item = registered()
    authority.append_decision(decision(item, "PUBLICATION", PublicationAction.PUBLISH))
    authority.append_decision(
        decision(item, "MATCH", MatchAction.GRANT, expires_at=NOW + timedelta(hours=1))
    )
    before = len(authority.decision_history)
    assert not visible(authority, item, at=NOW + timedelta(hours=1)).available
    authority.append_decision(
        decision(
            item,
            "PUBLICATION",
            PublicationAction.UNPUBLISH,
            "2",
            decided_at=NOW + timedelta(minutes=1),
            effective_at=NOW + timedelta(minutes=1),
        )
    )
    assert len(authority.decision_history) == before + 1
    assert not visible(authority, item, at=NOW + timedelta(minutes=2)).available


def test_hidden_denied_and_cross_scope_results_have_constant_shape() -> None:
    authority, item = registered()
    authority.append_decision(decision(item, "PUBLICATION", PublicationAction.PUBLISH))
    authority.append_decision(decision(item, "MATCH", MatchAction.DENY))
    denied = visible(authority, item)
    foreign = visible(
        authority, item, tenant_id="tenant-b", security_domain="restricted"
    )
    missing = visible(authority, item, blueprint_id="blueprint.unknown")
    assert denied == foreign == missing
    assert denied.reason_code == "UNAVAILABLE" and denied.blueprint is None


def test_exact_scope_and_purpose_bind_decisions() -> None:
    authority, item = registered()
    authority.append_decision(decision(item, "PUBLICATION", PublicationAction.PUBLISH))
    authority.append_decision(decision(item, "MATCH", MatchAction.GRANT))
    assert not visible(authority, item, scope="catalog-b").available
    assert not visible(authority, item, purpose="execution").available


def test_conflicting_decisions_fail_closed_and_replays_conflict() -> None:
    authority, item = registered()
    publish = decision(item, "PUBLICATION", PublicationAction.PUBLISH)
    assert authority.append_decision(publish) == authority.append_decision(publish)
    with pytest.raises(BlueprintAuthorityError, match="CONFLICTING_AUTHORITY_DECISION"):
        authority.append_decision(
            replace(publish, action=PublicationAction.UNPUBLISH.value)
        )
    authority.append_decision(decision(item, "MATCH", MatchAction.GRANT))
    authority.append_decision(decision(item, "MATCH", MatchAction.DENY, "2"))
    assert not visible(authority, item).available


def test_successor_requires_exact_predecessor_and_history_is_retained() -> None:
    authority, first = registered()
    predecessor = ref(first.blueprint_id, first.version_id, first.canonical_digest)
    second = blueprint(version_id="v2", predecessor_version=predecessor)
    authority.propose(second)
    assert first in authority.registered_versions
    forged = blueprint(
        version_id="v3",
        predecessor_version=ref(first.blueprint_id, first.version_id, "b" * 64),
    )
    with pytest.raises(BlueprintAuthorityError, match="INVALID_PREDECESSOR_BINDING"):
        authority.propose(forged)


def test_cross_tenant_identity_does_not_collide() -> None:
    authority = InMemoryBlueprintAuthority()
    first = blueprint()
    second = blueprint(tenant_id="tenant-b")
    assert authority.propose(first) != authority.propose(second)


def test_decisions_are_exact_digest_bound_and_no_side_effect_ports_exist() -> None:
    authority, item = registered()
    forged = replace(
        decision(item, "PUBLICATION", PublicationAction.PUBLISH),
        blueprint_digest="b" * 64,
    )
    with pytest.raises(BlueprintAuthorityError, match="MALFORMED_AUTHORITY_DECISION"):
        authority.append_decision(forged)
    names = set(dir(authority))
    assert not names.intersection(
        {
            "execute",
            "generate",
            "invoke_runtime",
            "invoke_provider",
            "access_kubernetes",
            "ingest_knowledge",
        }
    )


def test_non_utc_and_invalid_expiry_fail_closed() -> None:
    item = blueprint()
    with pytest.raises(ValueError, match="INVALID_DECISION_TIMESTAMP"):
        decision(item, "REVIEW", ReviewAction.APPROVE, decided_at=datetime(2026, 8, 30))
    with pytest.raises(BlueprintAuthorityError, match="INVALID_EXPIRY"):
        decision(item, "REVIEW", ReviewAction.APPROVE, expires_at=NOW)
