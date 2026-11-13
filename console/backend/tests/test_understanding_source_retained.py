"""Explicit retained profile lookup, never latest-profile substitution."""

from types import SimpleNamespace as NS

import pytest
from agent_console.understanding_adoption_origin import AdoptionOrigin


def origin(identity, retained=()):
    return AdoptionOrigin(
        None,
        NS(
            configuration={"profile_revision_id": identity},
            experience=NS(understanding_policy_digest="policy:" + identity),
        ),
        NS(profile_revision_id=identity, profile_digest="digest:" + identity),
        enabled=True,
        retained=retained,
    )


def test_old_result_uses_exact_explicitly_retained_profile():
    old = origin("old-c2")
    active = origin("source-c2", (old,))
    invocation = NS(
        profile_revision_id="old-c2", snapshot=NS(profile_digest="digest:old-c2")
    )
    assert active.for_result(invocation) is old
    assert (
        active.for_record(
            {
                "configuration": old.routing.configuration,
                "owned_understanding_policy_digest": "policy:old-c2",
            }
        )
        is old
    )


@pytest.mark.parametrize("profile", ["unconfigured", "old-c2"])
def test_unregistered_or_wrong_digest_never_falls_back(profile):
    old = origin("old-c2")
    active = origin("source-c2", (old,))
    with pytest.raises(ValueError, match="PROFILE_MISMATCH"):
        active.for_result(
            NS(profile_revision_id=profile, snapshot=NS(profile_digest="other"))
        )


def test_record_requires_both_exact_configuration_and_policy():
    old = origin("old-c2")
    active = origin("source-c2", (old,))
    with pytest.raises(ValueError, match="CONFIGURATION_CHANGED"):
        active.for_record(
            {
                "configuration": old.routing.configuration,
                "owned_understanding_policy_digest": "policy:source-c2",
            }
        )
