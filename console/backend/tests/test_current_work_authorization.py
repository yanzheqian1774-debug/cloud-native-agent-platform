from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import (
    AuthorityError,
    DynamicAuthorizationState,
    ExactGrant,
)
from agent_console.grant_administration_application import GenerationAuthorizationReader
from agent_console.workbench_current_work_authorization import readable_grants
from agent_console.workbench_owner_authorization import WorkbenchOwnerError
from test_workbench_authorization_postgres import context, generation


def test_unavailable_batch_stays_denied_by_default_and_fails_explicit_mode():
    now = datetime.now(UTC)
    reader = GenerationAuthorizationReader(
        generation(now), None, None, recovery_epoch=1
    )
    reader.read_linearized_authorization_states = lambda *a, **kw: (
        None,
        (DynamicAuthorizationState.UNAVAILABLE,),
    )
    grant = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:one")
    params = dict(now=now, generation=1, recovery_epoch=1)
    assert reader.has_current_grants(context(), (grant,), **params) == (False,)
    with pytest.raises(AuthorityError, match="AUTHORIZATION_STATE_UNAVAILABLE"):
        reader.has_current_grants(context(), (grant,), require_available=True, **params)
    for update in [{"generation": 2}, {"recovery_epoch": 2}]:
        with pytest.raises(AuthorityError, match="AUTHORIZATION_STATE_UNAVAILABLE"):
            reader.has_current_grants(
                context(), (grant,), require_available=True, **(params | update)
            )
    reader.read_linearized_authorization_states = lambda *a, **kw: (None, ())
    with pytest.raises(AuthorityError, match="AUTHORIZATION_STATE_UNAVAILABLE"):
        reader.has_current_grants(context(), (grant,), require_available=True, **params)


def test_directory_deduplicates_exact_checks_and_keeps_denial_distinct():
    allowed = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:one")
    denied = ExactGrant("BUSINESS_PROBLEM", "READ", "business-problem:two")
    connection = object()
    checks = []

    def check(ctx, grants, **values):
        checks.append(grants)
        assert ctx == context()
        assert values["connection"] is connection
        assert values["configure_transaction"] is False
        assert values["require_available"] is True
        return (True, False)

    adapter = SimpleNamespace(
        authorization=SimpleNamespace(has_current_grants=check),
        clock=lambda: datetime.now(UTC),
        controller=SimpleNamespace(readiness=SimpleNamespace(recovery_epoch=1)),
        _decision=lambda ctx, grant, generation: grant,
    )
    authority = SimpleNamespace(adapter=adapter, generation=1, decisions={})
    call = SimpleNamespace(
        authority=authority, context=context(), connection=connection
    )
    assert readable_grants(call, (allowed, denied, allowed)) == (True, False, True)
    assert checks == [(allowed, denied)]
    assert list(authority.decisions.values()) == [allowed]

    def unavailable(*a, **kw):
        raise AuthorityError("AUTHORIZATION_STATE_UNAVAILABLE")

    adapter.authorization.has_current_grants = unavailable
    with pytest.raises(
        WorkbenchOwnerError, match="CURRENT_WORK_AUTHORITY_UNAVAILABLE"
    ) as e:
        readable_grants(call, (allowed,))
    assert e.value.status_code == 503


def test_run_requires_both_roots_and_cannot_substitute_missing_revision(monkeypatch):
    from agent_console import workbench_current_work_authorization as module

    rows = [
        dict(digest="a" * 64),
        dict(
            digest="b" * 64,
            business_problem_id="p1",
            problem_revision_id="r1",
            problem_digest="d" * 64,
        ),
        dict(
            digest="c" * 64,
            business_problem_id="p2",
            problem_revision_id="r2",
            problem_digest="e" * 64,
        ),
    ]
    calls = []

    def decisions(call, grants):
        calls.append(grants)
        return tuple(
            g.exact_resource
            not in {
                "governed-execution:prepared:" + "a" * 64,
                "business-problem:p1",
            }
            for g in grants
        )

    monkeypatch.setattr(module, "readable_grants", decisions)
    assert module.readable_runs(object(), rows) == [rows[2]]
    assert len(calls) == 2
    assert [g.exact_resource for g in calls[1]] == [
        "business-problem:p1",
        "business-problem:p2",
    ]
    # A missing revision on an unreadable execution discloses nothing; on a
    # readable execution it must prevent a misleading complete directory.
    rows[2]["problem_revision_id"] = None
    with pytest.raises(
        WorkbenchOwnerError, match="CURRENT_WORK_PROBLEM_VERSION_UNAVAILABLE"
    ):
        module.readable_runs(object(), rows)
