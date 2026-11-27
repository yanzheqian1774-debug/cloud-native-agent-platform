"""Exact read projection never turns historical tests into execution authority."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.resource_version_basis import version_basis
from agent_console.workbench_prepared_resources import PreparedResourceOwner, reference


def revision(identity="old", digest="a" * 64):
    return {
        "revisionId": identity,
        "digest": digest,
        "state": "PUBLISHED",
        "content": {"operations": [{"name": "READ_DATA"}]},
        "validatedAt": "2026-11-27T12:00:00Z",
        "validationErrors": [],
    }


def record():
    old = revision()
    return {
        "name": "fixture",
        "aggregateVersion": 4,
        "enabled": False,
        "revisions": [old, revision("middle", "b" * 64)],
        "publishedRevisionId": "newer",
        "savedTests": [{"input": "SECRET", "expected": "SECRET"}],
        "testResults": [
            {
                "revisionId": "old",
                "revisionDigest": old["digest"],
                "verificationLevel": "ISOLATED_SYNTHETIC_EXECUTOR",
                "operation": "READ_DATA",
                "caseName": "SECRET_CASE_NAME",
                "status": "PASSED",
                "actualExecution": True,
                "resultId": "result",
                "actual": "SECRET",
            }
        ],
        "reviews": [
            {
                "revisionId": "old",
                "digest": old["digest"],
                "decision": "APPROVED",
                "policyBasis": {"type": "POLICY", "credentialPath": "SECRET"},
            }
        ],
        "facts": [
            {
                "event": "REVISION_PUBLISHED",
                "subject": {**old, "publishedAt": "2026-11-27T12:01:00Z"},
            }
        ],
    }


def test_exact_historical_publication_has_no_current_execution_authority_or_secrets():
    data = record()
    before = deepcopy(data)
    result = version_basis(data, data["revisions"][0])
    assert result["tests"]["ready"] is True
    assert result["publication"] == {
        "recorded": True,
        "publishedAt": "2026-11-27T12:01:00Z",
        "basisType": "POLICY",
    }
    assert result["executionAuthority"] == "NONE"
    assert result["businessAcceptance"] == "NOT_ESTABLISHED"
    assert "SECRET" not in str(result)
    assert data == before


def test_untested_intermediate_and_wrong_digest_never_borrow_old_success():
    data = record()
    for selected in [data["revisions"][1], revision("old", "c" * 64)]:
        result = version_basis(data, selected)
        assert result["tests"]["ready"] is False
        assert result["tests"]["operations"][0]["caseCount"] == 0
        assert result["publication"]["recorded"] is False


def test_latest_case_failure_overrides_earlier_success():
    data = record()
    data["testResults"].append({**data["testResults"][0], "status": "FAILED"})
    result = version_basis(data, data["revisions"][0])
    assert result["tests"]["ready"] is False
    assert result["tests"]["operations"][0]["passed"] is False


@pytest.mark.parametrize("allowed", [True, False])
def test_owner_requires_exact_read_before_fetching_any_basis(monkeypatch, allowed):
    from agent_console import workbench_prepared_resources as module

    accesses = []
    data = record()

    def require(principal, owner, action, target):
        assert principal.principal_id == "human:reader"
        assert (owner, action, target) == (
            "SKILL",
            "READ_RESOURCE",
            reference("skill", "id", "old"),
        )
        if not allowed:
            raise PermissionError("exact READ absent; MANAGE is insufficient")

    def fetch(*args):
        accesses.append("record")
        return data

    service = SimpleNamespace(
        scope=lambda *args: SimpleNamespace(namespace="tenant", security_domain="test"),
        repository=SimpleNamespace(get=fetch),
    )
    monkeypatch.setattr(module, "bind_service", lambda *args: service)
    call = SimpleNamespace(
        operation="READ_PREPARED_RESOURCE",
        context=SimpleNamespace(
            principal_id="human:reader",
            scope=SimpleNamespace(tenant_id="tenant", security_domain="test"),
        ),
        path={"kind": "skill", "identity": "id", "revision": "old"},
        connection=None,
        authority=SimpleNamespace(require=require),
    )
    handler = PreparedResourceOwner({"skill": service})
    if allowed:
        result = handler(call)
        assert result["enabled"] is False
        assert result["versionBasis"]["tests"]["ready"] is True
        assert result["versionBasis"]["executionAuthority"] == "NONE"
        assert accesses == ["record"]
    else:
        with pytest.raises(PermissionError, match="exact READ absent"):
            handler(call)
        assert accesses == []
