"""Actual host/answer composition invokes real v2 policy validation; no DB effects."""

import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_work_reader import OwnedBusinessWorkReader
from test_owned_business_retained_history import typed_policies


class ReachedComposition(Exception):
    pass


@pytest.fixture
def policies(tmp_path, monkeypatch):
    old, new, _ = typed_policies(tmp_path)
    monkeypatch.setenv("OWNED_BUSINESS_ADMISSION_POLICY", str(new))
    monkeypatch.setenv(
        "OWNED_BUSINESS_RETAINED_HISTORY_POLICIES", json.dumps([str(old)])
    )
    return old, new


def reader_probe(seen):
    def build(*args, **kwargs):
        # Crucially call the real constructor: missing env, wrong pin or omitted
        # kwarg raises before the controlled downstream sentinel.
        reader = OwnedBusinessWorkReader(*args, **kwargs)
        if kwargs.get("_retained_read_only"):
            return reader
        seen.append(reader)
        raise ReachedComposition()

    return build


@pytest.mark.parametrize("valid", [True, False])
def test_answer_entry_composes_exact_retained_reader(
    policies, tmp_path, monkeypatch, valid
):
    from agent_console import native_wait_answer as target

    runtime = tmp_path / "runtime.json"
    runtime.write_text("{}")
    monkeypatch.setenv("NATIVE_LOOP_RUNTIME_FILE", str(runtime))
    monkeypatch.setenv("NATIVE_DURABLE_WAIT_CONFIGURATION", str(tmp_path / "wait.json"))
    if not valid:
        monkeypatch.delenv("OWNED_BUSINESS_RETAINED_HISTORY_POLICIES")
    monkeypatch.setattr(target.DurableWaitConfiguration, "load", lambda *args: NS())
    c = Mock()
    c.execute.return_value.fetchone.side_effect = [{"t": True}, {"record": {}}]
    call = NS(
        connection=c,
        payload={"invocationId": "actual-question"},
        authority=NS(
            generation=33,
            adapter=NS(
                authorization=object(), controller=NS(readiness=NS(recovery_epoch=1))
            ),
        ),
    )
    seen = []
    monkeypatch.setattr(target, "OwnedBusinessWorkReader", reader_probe(seen))
    with pytest.raises(ReachedComposition if valid else AuthorityError):
        target.accept_if_waiting(call, None, NS(namespace="t", security_domain="d"), {})
    assert len(seen) == int(valid)
    if valid:
        assert len(seen[0].retained_history) == 1
        assert all(r.retained_read_only for r in seen[0].retained_history.values())


@pytest.mark.parametrize("valid", [True, False])
def test_manager_build_entry_composes_exact_retained_reader(
    policies, tmp_path, monkeypatch, valid
):
    from agent_console import (
        authority_configuration,
        authority_postgres,
        authority_recovery,
        execution_postgres,
        grant_administration_application,
        owned_business_work_reader,
        prepared_native_composition,
    )
    from agent_operator import native_dispatch_reconciler as target

    if not valid:
        monkeypatch.delenv("OWNED_BUSINESS_RETAINED_HISTORY_POLICIES")
    cfg = tmp_path / "authority.json"
    cfg.write_text("{}")
    for key, value in {
        "NATIVE_DISPATCH_DATABASE_URL": "controlled-composition-no-connection",
        "NATIVE_DISPATCH_AUTHORITY_CONFIGURATION": str(cfg),
        "NATIVE_DISPATCH_EXECUTION_MIGRATION": str(tmp_path / "execution.sql"),
        "NATIVE_DISPATCH_SCHEMA_MIGRATION": str(tmp_path / "dispatch.sql"),
        "NATIVE_DISPATCH_WORKER_ID": "worker",
        "NATIVE_DISPATCH_PREPARED_SKILL": "registered-readonly-v1",
        "NATIVE_DISPATCH_CONTINUATION_POLICY": str(tmp_path / "continuation.json"),
    }.items():
        monkeypatch.setenv(key, value)
    config = NS(
        database_url="controlled-composition-no-connection",
        generation_path="gen",
        generation_digest="digest",
        migration_path="migration",
        recovery_control_path="control",
        database_fingerprint="db",
    )
    monkeypatch.setattr(
        authority_configuration.AuthorityRuntimeConfiguration,
        "from_mapping",
        lambda *args: config,
    )
    monkeypatch.setattr(
        authority_configuration.StaticAuthorityLoader,
        "load",
        lambda *args, **kwargs: NS(generation=33, digest="digest"),
    )
    repository = Mock()
    repository.active_generation.return_value = (33, "digest", 1)
    monkeypatch.setattr(
        authority_postgres,
        "PostgresAuthorityRepository",
        lambda *args, **kwargs: repository,
    )
    monkeypatch.setattr(
        execution_postgres,
        "PostgresExecutionAuthorityRepository",
        lambda *args, **kwargs: repository,
    )
    monkeypatch.setattr(authority_recovery, "HostRecoveryControl", lambda *args: Mock())
    monkeypatch.setattr(
        grant_administration_application,
        "GenerationAuthorizationReader",
        lambda *args, **kwargs: Mock(),
    )
    monkeypatch.setattr(
        prepared_native_composition, "compose", lambda *args, **kwargs: (Mock(), Mock())
    )
    monkeypatch.setattr(
        prepared_native_composition, "owner_authority_factory", lambda *args: Mock()
    )
    seen = []
    monkeypatch.setattr(
        owned_business_work_reader, "OwnedBusinessWorkReader", reader_probe(seen)
    )
    with pytest.raises(ReachedComposition if valid else AuthorityError):
        target.build_native_dispatch_from_environment()
    assert len(seen) == int(valid)
    if valid:
        assert len(seen[0].retained_history) == 1
        assert all(r.retained_read_only for r in seen[0].retained_history.values())
