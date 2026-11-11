"""Provenance filters are exact, authorized and distinct from execution usage."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from agent_console.business_capability import (
    BusinessCapabilityError,
    CapabilityOrigin,
    FixedReference,
    OriginKind,
)
from agent_console.workbench_business_capability import (
    CapabilityListQuery,
    CapabilityOwner,
    CapabilityPublicationRepository,
)
from pydantic import ValidationError
from test_business_capability import capability

QUERY = {
    "workflowId": "workflow:source",
    "workflowRevision": "old",
    "workflowDigest": "a" * 64,
}


@pytest.mark.parametrize("missing", list(QUERY))
def test_partial_workflow_filter_rejected(missing):
    with pytest.raises(ValidationError):
        CapabilityListQuery.model_validate(
            {k: v for k, v in QUERY.items() if k != missing}
        )


def test_empty_and_complete_filter_supported():
    assert CapabilityListQuery().workflowId == ""
    assert CapabilityListQuery.model_validate(QUERY).workflowDigest == "a" * 64


@pytest.mark.parametrize("change", [None, "identity", "revision", "digest", "denied"])
def test_source_authority_and_exact_version_before_reverse_scan(change):
    workflows = Mock()
    workflows.read_revision_for_workbench.return_value = {
        "definition": {
            "workflowDefinitionId": "wrong"
            if change == "identity"
            else QUERY["workflowId"]
        },
        "revision": {
            "revisionId": "new" if change == "revision" else "old",
            "digest": "b" * 64 if change == "digest" else "a" * 64,
        },
    }
    owner = CapabilityOwner(Mock(), SimpleNamespace(workflows=workflows), Mock())
    call = SimpleNamespace(query=QUERY, authority=Mock(), connection=object())
    if change == "denied":
        call.authority.require.side_effect = PermissionError("denied")
        with pytest.raises(PermissionError):
            owner._verify_workflow_filter(call, "scope", "principal")
        workflows.read_revision_for_workbench.assert_not_called()
    elif change:
        with pytest.raises(BusinessCapabilityError, match="MISMATCH"):
            owner._verify_workflow_filter(call, "scope", "principal")
    else:
        owner._verify_workflow_filter(call, "scope", "principal")
    call.authority.require.assert_called_once_with(
        "principal", "WORKFLOW", "READ", "workflow:workflow:source:old"
    )


@pytest.mark.parametrize("match", ["published", "draft", "both", "none"])
def test_published_and_draft_provenance_are_filtered_independently(monkeypatch, match):
    original = capability()
    origin = CapabilityOrigin(
        OriginKind.WORKFLOW_REVISION,
        FixedReference(QUERY["workflowId"], "old", "a" * 64),
    )
    revisions = {
        key: replace(
            original,
            revision_id=key,
            origin=origin if match in (key, "both") else original.origin,
        )
        for key in ("published", "draft")
    }
    repository = Mock()
    repository.read.side_effect = lambda connection, scope, identity, revision: (
        revisions[revision]
    )
    owner = CapabilityOwner(repository, Mock(), Mock())
    monkeypatch.setattr(
        CapabilityPublicationRepository,
        "latest",
        lambda *args: {"revision_id": "published"},
    )
    call = SimpleNamespace(query=QUERY, authority=Mock(), connection=object())
    result = owner._item(
        call,
        original.scope,
        "principal",
        {
            "capability_id": original.capability_id,
            "head_revision_id": "draft",
            "aggregate_version": 2,
        },
    )
    if match == "none":
        assert result is None
    else:
        assert result["revisionId"] == ("draft" if match == "draft" else "published")
        assert bool(result["currentPublished"]) == (match in ("published", "both"))
        assert bool(result["currentDraft"]) == (match in ("draft", "both"))
        assert result["executionAuthorized"] is False


def test_reverse_query_checks_source_before_scanning_and_binds_pagination():
    scope = capability().scope
    principal = SimpleNamespace(principal_id="human:reader")
    workflows = Mock()
    workflows.read_revision_for_workbench.return_value = {
        "definition": {"workflowDefinitionId": QUERY["workflowId"]},
        "revision": {"revisionId": "old", "digest": "a" * 64},
    }
    cursors = Mock()
    cursors.mint.return_value = "opaque-cursor"
    owner = CapabilityOwner(Mock(), SimpleNamespace(workflows=workflows), cursors)
    owner._scan = Mock(
        return_value=iter(
            [
                {
                    "capabilityId": "first",
                    "title": "one",
                    "intent": "",
                    "employeeResponsibilities": [],
                },
                {
                    "capabilityId": "second",
                    "title": "two",
                    "intent": "",
                    "employeeResponsibilities": [],
                },
            ]
        )
    )
    owner._employee_names = lambda call, scope, principal, item: item
    call = SimpleNamespace(
        query={
            **QUERY,
            "pageSize": 1,
            "query": "",
            "domain": "",
            "favoritesOnly": False,
        },
        authority=Mock(),
        connection=object(),
        context=object(),
    )
    first = owner._list(call, scope, principal)
    assert [item["capabilityId"] for item in first["items"]] == ["first"]
    assert first["nextCursor"] == "opaque-cursor"
    source_route = cursors.mint.call_args.kwargs["route"]
    owner._scan.return_value = iter(
        [
            {
                "capabilityId": "first",
                "title": "one",
                "intent": "",
                "employeeResponsibilities": [],
            },
            {
                "capabilityId": "second",
                "title": "two",
                "intent": "",
                "employeeResponsibilities": [],
            },
        ]
    )
    call.query = {**call.query, "workflowDigest": "b" * 64}
    workflows.read_revision_for_workbench.return_value["revision"]["digest"] = "b" * 64
    owner._list(call, scope, principal)
    assert cursors.mint.call_args.kwargs["route"] != source_route
    owner._scan.reset_mock()
    call.authority.require.side_effect = PermissionError("revoked")
    with pytest.raises(PermissionError):
        owner._list(call, scope, principal)
    owner._scan.assert_not_called()
