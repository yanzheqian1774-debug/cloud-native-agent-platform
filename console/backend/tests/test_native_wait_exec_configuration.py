"""Exec harness never deserializes executable objects or a platform database."""

import json
from datetime import UTC, datetime

import pytest
from agent_console.authority_configuration import (
    CredentialConfiguration,
    StaticAuthorityGeneration,
)
from agent_console.authority_contracts import AuthorityScope, GrantSource
from native_wait_exec_configuration import decode, encode, isolated_dsn


def test_generation_roundtrip_preserves_exact_types():
    generation = StaticAuthorityGeneration(
        1,
        "a" * 64,
        "test",
        "isolated-test",
        (
            CredentialConfiguration(
                "test",
                "b" * 64,
                "human:test",
                AuthorityScope("t", "d"),
                datetime.now(UTC),
                GrantSource.SERVICE_ONLY,
                (),
            ),
        ),
        (),
        frozenset(),
    )
    assert decode(json.loads(json.dumps(encode(generation)))) == generation


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://postgres@127.0.0.1:53428/postgres",
        "postgresql://postgres@127.0.0.1:5432/accounts324_" + "a" * 32,
        "postgresql://postgres@other:53428/accounts324_" + "a" * 32,
    ],
)
def test_platform_or_nonfixture_database_rejected(dsn):
    with pytest.raises(ValueError, match="DISPOSABLE_DATABASE_REQUIRED"):
        isolated_dsn(dsn)


def test_non_authority_class_is_not_imported():
    with pytest.raises(ValueError, match="UNREGISTERED"):
        decode({"type": "subprocess:Popen", "fields": {}})
