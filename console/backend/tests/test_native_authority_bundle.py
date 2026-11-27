"""Exact Native authority bundles retain role and Skill checks without a cache."""

from types import SimpleNamespace as NS

import pytest
from agent_console import native_loop_runtime
from agent_console import prepared_native_composition as module
from agent_console.authority_contracts import AuthorityError, ExactGrant
from agent_console.development_administrator import GRANT, PRINCIPAL, SCOPE


def build(monkeypatch, bundle, subject=PRINCIPAL):
    captured = {}
    monkeypatch.setattr(
        module,
        "compose_governed_skill_invocation",
        lambda *args: NS(closeables=(), invocation_repository=object()),
    )
    monkeypatch.setattr(
        module,
        "prepared_attempt",
        lambda *args: {"preparation": {}, "task_id": "task:1", "attempt_ordinal": 2},
    )
    monkeypatch.setattr(module, "parse_preparation", lambda value: NS(digest="a" * 64))

    def runtime(*args, **kwargs):
        captured.update(kwargs)
        return NS(subject=subject)

    monkeypatch.setattr(native_loop_runtime, "NativeLoopRuntime", runtime)
    from tempfile import NamedTemporaryFile

    # Production composition now reads the explicit optional adapter descriptor
    # list; this old authority fixture uses a real default-off configuration.
    with NamedTemporaryFile(mode="w", suffix=".json") as config:
        config.write("{}")
        config.flush()
        module.compose(
            None,
            None,
            None,
            None,
            NS(policy_version="p"),
            lambda *args: True,
            native_loop_path=config.name,
            authorization_bundle_check=bundle,
        )
    command = NS(
        principal_id=PRINCIPAL,
        scope=NS(namespace=SCOPE[0], security_domain=SCOPE[1]),
        attempt_id="attempt:1",
    )
    return captured["authorize_current"], command


def test_every_check_passes_exact_skill_and_role_and_honors_new_denial(monkeypatch):
    calls = []
    allow = True

    def bundle(connection, command, grants):
        calls.append((connection, command, grants))
        return allow

    check, command = build(monkeypatch, bundle)
    connection = object()
    assert check(connection, command)
    assert calls[0] == (
        connection,
        command,
        (
            ExactGrant(
                "SKILL",
                "INVOKE_SKILL",
                "skill-invocation:prepared:" + "a" * 64 + ":task:1:2",
            ),
            GRANT,
        ),
    )
    allow = False
    assert not check(connection, command)
    assert len(calls) == 2
    command.principal_id = "human:other"
    assert not check(connection, command)
    assert len(calls) == 2


def test_missing_prepared_owner_record_cannot_authorize(monkeypatch):
    check, command = build(monkeypatch, lambda *args: pytest.fail("not authorized"))
    monkeypatch.setattr(module, "prepared_attempt", lambda *args: None)
    with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
        check(object(), command)


def test_existing_compositions_keep_legacy_authorization(monkeypatch):
    check, _ = build(monkeypatch, None)
    assert check is None


def test_optional_ontology_grant_is_not_lost_in_bundle(monkeypatch):
    calls = []
    check, command = build(
        monkeypatch, lambda _, __, grants: calls.append(grants) or True
    )
    monkeypatch.setattr(
        module,
        "parse_preparation",
        lambda _: NS(
            digest="a" * 64,
            business_semantics=NS(
                ontology=NS(resource_id="ontology:1", revision_id="revision:1")
            ),
        ),
    )
    assert check(object(), command)
    assert [(g.owner, g.action) for g in calls[0]] == [
        ("SKILL", "INVOKE_SKILL"),
        ("BUSINESS_ONTOLOGY", "USE"),
        ("DEVELOPMENT_ADMIN", "USE"),
    ]


def test_ordinary_subject_keeps_exact_grants_and_fresh_denials(monkeypatch):
    calls = []
    allowed = True

    def bundle(connection, command, grants):
        calls.append(grants)
        return allowed

    check, command = build(monkeypatch, bundle, subject="human:ordinary")
    command.principal_id = "human:ordinary"
    assert check(object(), command)
    assert [(grant.owner, grant.action) for grant in calls[-1]] == [
        ("SKILL", "INVOKE_SKILL")
    ]
    allowed = False
    assert not check(object(), command)
    assert len(calls) == 2
    command.principal_id = PRINCIPAL
    assert not check(object(), command)
    assert len(calls) == 2


def test_ordinary_subject_still_requires_exact_ontology_use(monkeypatch):
    calls = []
    check, command = build(
        monkeypatch,
        lambda _, __, grants: calls.append(grants) or True,
        subject="human:ordinary",
    )
    command.principal_id = "human:ordinary"
    monkeypatch.setattr(
        module,
        "parse_preparation",
        lambda _: NS(
            digest="a" * 64,
            business_semantics=NS(ontology=NS(resource_id="rules", revision_id="r1")),
        ),
    )
    assert check(object(), command)
    assert [(grant.owner, grant.action) for grant in calls[-1]] == [
        ("SKILL", "INVOKE_SKILL"),
        ("BUSINESS_ONTOLOGY", "USE"),
    ]
