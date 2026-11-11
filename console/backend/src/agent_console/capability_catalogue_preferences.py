"""Own-account catalogue preferences; not capability or execution authority."""

import hashlib
from pathlib import Path
from typing import Annotated, Literal

from psycopg.types.json import Jsonb
from pydantic import Field

from .authority_contracts import AuthorityError, ExactGrant
from .business_capability_publication_postgres import CapabilityPublicationRepository
from .digital_employee_definition import digest
from .execution_domain import ScopeIdentity
from .postgres_schema_compatibility import (
    Table,
    columns,
    primary,
    schema_is_compatible,
    unique,
)
from .workbench_bff import PREFIX, WorkbenchOperation
from .workbench_bff_schemas import StrictWorkbenchModel
from .workbench_business_problem import OwnerPrincipal
from .workbench_owner_authorization import WorkbenchOwnerError

MIGRATION = (
    Path(__file__).parents[2] / "migrations/0055_capability_catalogue_preferences.sql"
)
ADAPTER = "capability-catalogue-preferences-v1"
KEY = ("namespace", "security_domain", "principal_id")
STRUCTURE = (
    Table(
        "business_capability.catalogue_preferences",
        columns(
            *(
                (k, "text")
                for k in (*KEY, "command_id", "payload_digest", "decision_id")
            ),
            ("version", "bigint"),
            ("state", "jsonb"),
            ("recorded_at", "timestamp with time zone"),
        ),
        (primary(*KEY, "version"), unique(*KEY, "command_id")),
        ("immutable_catalogue_preferences",),
    ),
)


class CatalogueState(StrictWorkbenchModel):
    query: str = Field(default="", max_length=500)
    layout: Literal["cards", "list"] = "cards"
    domain: str = Field(default="", max_length=80)
    favoritesOnly: bool = False
    favorites: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=500
    )
    scrollTop: int = Field(default=0, strict=True, ge=0, le=10_000_000)
    loadedCount: int = Field(default=50, strict=True, ge=1, le=10_000)


class SaveCataloguePreferences(StrictWorkbenchModel):
    expectedVersion: int = Field(strict=True, ge=0)
    commandId: str = Field(min_length=1, max_length=200)
    state: CatalogueState


def compatibility(conn):
    row = conn.execute(
        "SELECT checksum,adapter FROM business_capability.schema_migrations "
        "WHERE version=55"
    ).fetchone()
    if (
        not row
        or row["checksum"] != hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
        or row["adapter"] != ADAPTER
        or not schema_is_compatible(conn, STRUCTURE)
    ):
        raise WorkbenchOwnerError("CAPABILITY_PREFERENCES_SCHEMA_INCOMPATIBLE", 503)


def migrate(conn):
    conn.execute("SELECT pg_advisory_xact_lock(2760055)")
    conn.execute(MIGRATION.read_text())
    conn.execute(
        "INSERT INTO business_capability.schema_migrations "
        "VALUES(55,%s,%s) ON CONFLICT DO NOTHING",
        (hashlib.sha256(MIGRATION.read_bytes()).hexdigest(), ADAPTER),
    )
    compatibility(conn)


def latest(conn, key):
    return conn.execute(
        "SELECT version,state,command_id FROM "
        "business_capability.catalogue_preferences WHERE "
        "namespace=%s AND security_domain=%s AND principal_id=%s "
        "ORDER BY version DESC LIMIT 1",
        key,
    ).fetchone()


def result(row, replayed=False):
    return {
        "version": row["version"] if row else 0,
        "state": row["state"] if row else CatalogueState().model_dump(),
        "commandId": row["command_id"] if row else None,
        "replayed": replayed,
    }


def readable(call, scope, principal, identity):
    head = call.connection.execute(
        "SELECT head_revision_id FROM "
        "business_capability.definitions WHERE namespace=%s AND "
        "security_domain=%s AND capability_id=%s",
        (scope.namespace, scope.security_domain, identity),
    ).fetchone()
    if head:
        published = CapabilityPublicationRepository.latest(
            call.connection, scope, identity
        )
        for revision in {
            head["head_revision_id"],
            published["revision_id"] if published else head["head_revision_id"],
        }:
            try:
                call.authority.require(
                    principal,
                    "BUSINESS_CAPABILITY",
                    "READ",
                    f"business-capability:{identity}:{revision}",
                )
                return
            except AuthorityError:
                continue
    raise WorkbenchOwnerError("CAPABILITY_NOT_FOUND", 404)


def handle(call):
    key = (
        call.context.scope.tenant_id,
        call.context.scope.security_domain,
        call.context.principal_id,
    )
    scope = ScopeIdentity(*key[:2])
    principal = OwnerPrincipal(key[2], *key[:2])
    decision = call.authority.require(
        principal, "BUSINESS_CAPABILITY", "LIST", "business-capability:collection"
    )
    if call.operation == "READ_CAPABILITY_PREFERENCES":
        return result(latest(call.connection, key))
    command = SaveCataloguePreferences.model_validate(call.payload)
    state = command.state.model_dump()
    if len(set(state["favorites"])) != len(state["favorites"]):
        raise WorkbenchOwnerError("CAPABILITY_FAVORITES_DUPLICATE", 422)
    # Serialize only this account/scope; different accounts cannot overwrite it.
    call.connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,55))", (digest(key),)
    )
    previous = call.connection.execute(
        "SELECT version,state,command_id,payload_digest FROM "
        "business_capability.catalogue_preferences WHERE "
        "namespace=%s AND security_domain=%s AND principal_id=%s "
        "AND command_id=%s",
        (*key, command.commandId),
    ).fetchone()
    payload_digest = digest(command.model_dump())
    if previous and previous["payload_digest"] != payload_digest:
        raise WorkbenchOwnerError("CAPABILITY_PREFERENCES_COMMAND_CONFLICT", 409)
    current = latest(call.connection, key)
    if (
        not previous
        and (current["version"] if current else 0) != command.expectedVersion
    ):
        raise WorkbenchOwnerError("CAPABILITY_PREFERENCES_VERSION_CONFLICT", 409)
    # Recheck every retained favorite, including on replay; removal remains possible.
    for identity in state["favorites"]:
        readable(call, scope, principal, identity)
    if previous:
        return result(previous, True)
    row = call.connection.execute(
        "INSERT INTO "
        "business_capability.catalogue_preferences(namespace,security_domain,principal_id,version,command_id,payload_digest,decision_id,state)"
        " VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING "
        "version,state,command_id",
        (
            *key,
            command.expectedVersion + 1,
            command.commandId,
            payload_digest,
            decision.decision_id,
            Jsonb(state),
        ),
    ).fetchone()
    return result(row)


def operations():
    return tuple(
        WorkbenchOperation(
            name,
            method,
            PREFIX + "/business-capabilities/preferences",
            model,
            None,
            lambda *_: (
                ExactGrant(
                    "BUSINESS_CAPABILITY", "LIST", "business-capability:collection"
                ),
            ),
            handle,
        )
        for name, method, model in (
            ("READ_CAPABILITY_PREFERENCES", "GET", None),
            ("SAVE_CAPABILITY_PREFERENCES", "POST", SaveCataloguePreferences),
        )
    )
