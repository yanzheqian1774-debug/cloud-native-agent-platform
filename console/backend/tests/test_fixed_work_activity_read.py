"""Controlled boundary tests; real issuer/session proof lives in the PG test."""

from types import SimpleNamespace as N
from unittest.mock import Mock

import pytest
from agent_console import fixed_work_activity_read as module
from agent_console.authority_contracts import AuthenticationSource, ExactGrant


def setup(monkeypatch):
    p = N(
        digest="d" * 64,
        semantics=N(target=N(problem=N(resource_id="problem"))),
        source_snapshot=N(resource_id="source", revision_id="r", digest="s" * 64),
    )
    progress = N(tasks=[N(output_artifact_ids=("artifact",))])
    monkeypatch.setattr(
        module, "PreparedExecutionStore", lambda c: N(read=lambda *a: (p, progress))
    )
    validation = Mock()
    monkeypatch.setattr(module, "validate", validation)
    context = N(
        authentication_source=AuthenticationSource.BROWSER_SESSION,
        principal_id="human:viewer",
        scope=N(tenant_id="t", security_domain="d"),
    )
    row = {"workflow_run_id": "run", "preparation_digest": p.digest}
    c = N(
        execute=Mock(
            side_effect=[
                N(fetchone=lambda: row),
                N(fetchall=lambda: [{"artifact_id": "artifact"}]),
            ]
        )
    )
    auth = N(require=Mock())
    call = N(
        context=context,
        connection=c,
        authority=auth,
        payload={"workDigest": "a" * 64, "commandId": "read-one"},
    )
    # replace() requires the actual dataclass shape; no trusted context is derived
    # from this fixture, and no repository or issuer is simulated as real evidence.
    from agent_console.workbench_owner_authorization import AuthorizedOwnerCall

    call = AuthorizedOwnerCall(
        "PREPARE_FIXED_WORK_ACTIVITY_READ",
        context,
        c,
        call.payload,
        {},
        {},
        (),
        auth,
        1,
    )
    saved = {"digest": "a" * 64, "draft": {"workId": "w", "revisionId": "r"}}
    authoring = Mock(return_value=saved)
    automation = N(
        resources=Mock(return_value={"revision": {"digest": "s" * 64, "content": {}}}),
        grants=N(clock=lambda: None),
        work=Mock(return_value=N()),
        authenticate=Mock(return_value=N(principal_id="service:issuer")),
        decide=Mock(),
        proof_grants=Mock(),
    )
    return (
        module.FixedWorkActivityReadOwner(authoring, automation),
        call,
        automation,
        validation,
    )


def test_default_off_registers_no_operation():
    assert module.fixed_work_activity_read_operations(None, None) == ()
    with pytest.raises(ValueError):
        module.fixed_work_activity_read_operations(None, None, enabled=True)


def test_exact_read_only_members_and_stable_command_key(monkeypatch):
    owner, call, a, v = setup(monkeypatch)
    result = owner(call)
    assert result["state"] == "READ_READY"
    members = a.decide.call_args.args[1]
    assert members == (
        ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + "d" * 64),
        ExactGrant(
            "EVIDENCE",
            "READ_REFERENCE",
            "evidence-reference:prepared:" + "d" * 64 + ":artifact",
        ),
    )
    assert a.decide.call_args.kwargs["request_key"] == a.decide.call_args.args[2]
    v.assert_called_once()


@pytest.mark.parametrize(
    "case", ["service", "work", "problem", "source", "digest", "scope", "issuer"]
)
def test_rejections_cannot_issue_grants(monkeypatch, case):
    owner, call, a, _ = setup(monkeypatch)
    if case == "service":
        call.context.authentication_source = AuthenticationSource.SERVICE_CREDENTIAL
    if case == "work":
        owner.authoring.side_effect = ValueError("denied")
    if case in {"problem", "source"}:

        def deny(_p, kind, *_):
            if kind == ("BUSINESS_PROBLEM" if case == "problem" else "KNOWLEDGE"):
                raise ValueError("denied")

        call.authority.require.side_effect = deny
    if case == "digest":
        a.resources.return_value["revision"]["digest"] = "x" * 64
    if case == "scope":
        a.work.side_effect = ValueError("scope denied")
    if case == "issuer":
        a.authenticate.return_value.principal_id = call.context.principal_id
    with pytest.raises(ValueError):
        owner(call)
    a.decide.assert_not_called()


def test_existing_admin_reads_use_current_authorizer_without_policy_grant(monkeypatch):
    from datetime import UTC, datetime, timedelta

    from agent_console.plan_suggestion_domain import ExactReference
    from agent_console.resource_automation_policy import AdministratorWorkScope

    owner, call, a, _ = setup(monkeypatch)
    a.work.return_value = AdministratorWorkScope(
        namespace="t",
        securityDomain="d",
        subject="human:viewer",
        problem=ExactReference(resource_id="problem", revision_id="r", digest="a" * 64),
        expiresAt=datetime.now(UTC) + timedelta(minutes=1),
    )
    call.authority.current_action_grants = Mock(return_value=(True, True))
    assert owner(call)["state"] == "READ_READY"
    a.authenticate.assert_not_called()
    a.decide.assert_not_called()
