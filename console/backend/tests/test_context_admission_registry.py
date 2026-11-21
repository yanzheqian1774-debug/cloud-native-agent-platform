from contextlib import contextmanager
from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console import context_admission_registry as m
from agent_console.authority_contracts import AuthorityError


def fixture(monkeypatch):
    @contextmanager
    def scope():
        yield object()

    repo = N(connection_scope=scope)
    root = N(
        repository=repo, configuration={"model": "root"}, delegation=N(_admin=Mock())
    )
    planning = N(repository=repo, configuration={"model": "planning"})
    typed = N(
        repository=repo,
        configuration={"model": "typed"},
        read=Mock(return_value="typed"),
        approve=Mock(return_value="decision"),
        revoke=Mock(return_value="revoked"),
    )
    row = dict(
        tenant_id="t",
        security_domain="d",
        subject_id="u",
        record={"phase": "understanding", "configuration": typed.configuration},
    )
    monkeypatch.setattr(m, "request_row", lambda c, i: row)
    ctx = N(
        authentication_source="BROWSER_SESSION",
        scope=N(tenant_id="t", security_domain="d"),
        principal_id="u",
    )
    registry = m.ContextAdmissionRegistry(
        root, planning, [N(authorization=N(context_admission=typed)), None]
    )
    return registry, ctx, row, root, typed


def test_actual_registered_owner_all_operations(monkeypatch):
    r, ctx, row, root, typed = fixture(monkeypatch)
    assert r.read(ctx, "id") == "typed"
    assert r.approve(ctx, "id", "spec") == "decision"
    assert r.revoke(ctx, "id", "decision") == "revoked"
    typed.approve.assert_called_once_with(ctx, "id", "spec")
    root.delegation._admin.assert_not_called()
    row["record"]["configuration"] = {**typed.configuration, "calls": 200}
    with pytest.raises(AuthorityError, match="CONFIGURATION_MISMATCH"):
        r.read(ctx, "id")


@pytest.mark.parametrize("change", ["scope", "phase", "service"])
def test_no_scope_phase_or_service_fallback(monkeypatch, change):
    r, ctx, row, _, typed = fixture(monkeypatch)
    if change == "scope":
        row["tenant_id"] = "other"
    elif change == "phase":
        row["record"]["phase"] = "planning"
    else:
        ctx.authentication_source = "SERVICE_CREDENTIAL"
    with pytest.raises(AuthorityError):
        r.approve(ctx, "id", "spec")
    typed.approve.assert_not_called()


def test_ambiguous_registry_fails_at_composition(monkeypatch):
    r, _, _, root, typed = fixture(monkeypatch)
    duplicate = N(repository=root.repository, configuration=typed.configuration)
    with pytest.raises(AuthorityError, match="REGISTRY_AMBIGUOUS"):
        m.ContextAdmissionRegistry(
            root,
            r.entries[1][1],
            [N(authorization=N(context_admission=x)) for x in (typed, duplicate)],
        )
