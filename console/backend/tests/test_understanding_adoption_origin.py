"""Default-off composition boundary; no business permission inferred by C1."""

from types import SimpleNamespace as NS

import pytest
from agent_console.draft_assistance import DraftAssistanceError
from agent_console.understanding_adoption_history import source
from agent_console.understanding_adoption_origin import AdoptionOrigin


@pytest.mark.parametrize(
    "enabled,revision,scope_mode",
    [
        (False, "v3-relation-adoption", "EXISTING_WORK_AND_INITIAL_UNDERSTANDING"),
        (True, "v3-relation", "EXISTING_BUSINESS_WORK"),
        (True, "v3-execution", "EXISTING_WORK_AND_INITIAL_UNDERSTANDING"),
        (True, "v3-relation-adoption", "EXISTING_BUSINESS_WORK"),
    ],
)
def test_old_profiles_and_disabled_bridge_cannot_enter_business_resolver(
    enabled, revision, scope_mode
):
    root = NS()
    routing = NS(experience=NS(root=root, routing_document=NS(scopeMode=scope_mode)))
    resolver = AdoptionOrigin(
        root, routing, NS(adapter_revision=revision), enabled=enabled
    )
    with pytest.raises(DraftAssistanceError, match="BRIDGE_DISABLED"):
        resolver.business_source(None, None, "unread-result")
    with pytest.raises(DraftAssistanceError, match="BRIDGE_DISABLED"):
        source(resolver, None, None, "unread-result", "unread-conversation")
