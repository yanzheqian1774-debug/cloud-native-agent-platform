"""Private JSON-only disposable-test owner reconstruction; no pickled code/pools."""

import dataclasses
import enum
import importlib
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

from psycopg.conninfo import conninfo_to_dict

MODULES = {
    "agent_console.authority_configuration",
    "agent_console.authority_contracts",
}


def encode(value):
    if isinstance(value, enum.Enum):
        return {
            "enum": type(value).__module__ + ":" + type(value).__name__,
            "value": value.value,
        }
    if dataclasses.is_dataclass(value):
        return {
            "type": type(value).__module__ + ":" + type(value).__name__,
            "fields": {
                f.name: encode(getattr(value, f.name))
                for f in dataclasses.fields(value)
            },
        }
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, (tuple, frozenset)):
        return {"sequence": type(value).__name__, "items": [encode(v) for v in value]}
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(type(value).__name__)


def decode(value):
    if not isinstance(value, dict):
        return value
    if "datetime" in value:
        return datetime.fromisoformat(value["datetime"])
    if "sequence" in value:
        return {"tuple": tuple, "frozenset": frozenset}[value["sequence"]](
            decode(v) for v in value["items"]
        )
    module, name = value.get("type", value.get("enum", "")).split(":")
    if module not in MODULES:
        raise ValueError("UNREGISTERED_TEST_CONFIGURATION_TYPE")
    cls = getattr(importlib.import_module(module), name)
    if "enum" in value:
        return cls(value["value"])
    if not dataclasses.is_dataclass(cls):
        raise ValueError("INVALID_TEST_CONFIGURATION_TYPE")
    return cls(**{k: decode(v) for k, v in value["fields"].items()})


def isolated_dsn(dsn):
    parts = conninfo_to_dict(dsn)
    if (
        parts.get("host") != "127.0.0.1"
        or parts.get("port") != "53428"
        or not re.fullmatch(r"accounts324_[0-9a-f]{32}", parts.get("dbname", ""))
    ):
        raise ValueError("DISPOSABLE_DATABASE_REQUIRED")
    return dsn


def reconstruct(config):
    from agent_console.authority_postgres import PostgresAuthorityRepository
    from agent_console.grant_administration_application import (
        GenerationAuthorizationReader,
    )
    from agent_console.owned_business_work_reader import OwnedBusinessWorkReader
    from agent_console.workbench_owner_authorization import (
        AuthorizedOwnerAuthority,
        WorkbenchOwnerAuthorization,
    )

    repo = PostgresAuthorityRepository(
        isolated_dsn(config["database"]),
        migration_path=Path(config["authorityMigration"]),
    )
    context = decode(config["context"])
    generation = decode(config["generation"])
    owned_generation = decode(config["ownedGeneration"])
    reader = GenerationAuthorizationReader(
        generation, repo, repo, recovery_epoch=config["epoch"]
    )
    adapter = WorkbenchOwnerAuthorization(
        NS(readiness=NS(recovery_epoch=config["epoch"])), repo, reader
    )
    owned_reader = GenerationAuthorizationReader(
        owned_generation, repo, repo, recovery_epoch=config["ownedEpoch"]
    )
    owner = OwnedBusinessWorkReader(
        Path(config["policy"]),
        owned_reader,
        owned_generation.generation,
        config["ownedEpoch"],
    )

    def authority(c, command):
        if command.principal_id != context.principal_id:
            raise ValueError("TEST_COMMAND_SUBJECT_MISMATCH")
        return context, AuthorizedOwnerAuthority(
            adapter, context, c, generation.generation, ()
        )

    e = NS(
        context=context,
        business_owner=owner,
        wait_runtime_expiry=datetime.fromisoformat(config["expiry"]),
    )
    return e, authority, repo
