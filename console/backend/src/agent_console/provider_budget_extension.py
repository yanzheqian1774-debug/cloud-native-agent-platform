"""Explicit, audited cumulative extension; original allowance and ledger survive.

Operator preparation/activation are not HTTP APIs. Runtime selection never grants
scope, creates an allowance, activates a candidate, or changes pricing.
"""

from datetime import datetime
from hashlib import sha256
from typing import Literal

from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .draft_assistance import DraftAssistanceError
from .draft_provider_budget_postgres import _digest
from .provider_budget_allowance import require as require_allowance
from .provider_budget_allowance import scope


class ContextBasis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subjectId: str = Field(min_length=1)
    authorizationDigest: str = Field(pattern="^[a-f0-9]{64}$")
    configurationDigest: str = Field(pattern="^[a-f0-9]{64}$")


class Extension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["provider-budget-extension.v1"]
    extensionId: str = Field(min_length=1, max_length=200)
    namespace: str = Field(min_length=1)
    securityDomain: str = Field(min_length=1)
    ledgerId: str = Field(min_length=1)
    allowanceId: str = Field(min_length=1)
    allowanceDigest: str = Field(pattern="^[a-f0-9]{64}$")
    rootPolicyDigest: str = Field(pattern="^[a-f0-9]{64}$")
    authorizationEvidenceDigest: str = Field(pattern="^[a-f0-9]{64}$")
    predecessorExtensionId: None = None
    previousCallCap: Literal[100]
    previousCostCapMicrousd: Literal[10000000]
    additionalCalls: Literal[100]
    additionalCostMicrousd: Literal[10000000]
    callCap: Literal[200]
    totalCostCapMicrousd: Literal[20000000]
    notBefore: datetime
    expiresAt: datetime
    contextBases: tuple[ContextBasis, ...] = Field(max_length=128)
    externalWrites: Literal[False]

    @model_validator(mode="after")
    def bounded(self):
        if (
            self.notBefore.tzinfo is None
            or self.expiresAt.tzinfo is None
            or self.notBefore >= self.expiresAt
            or len(
                set(
                    (b.subjectId, b.authorizationDigest, b.configurationDigest)
                    for b in self.contextBases
                )
            )
            != len(self.contextBases)
        ):
            raise ValueError("bounded unique extension required")
        return self


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["provider-budget-extension-selection.v1"]
    namespace: str
    securityDomain: str
    ledgerId: str
    allowanceId: str
    extensionId: str
    extensionDigest: str = Field(pattern="^[a-f0-9]{64}$")
    authorizationEvidenceDigest: str = Field(pattern="^[a-f0-9]{64}$")


class Activation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schemaVersion: Literal["provider-budget-extension-activation.v1"]
    selection: Selection
    commandId: str = Field(min_length=1, max_length=200)


def _fail(condition, reason):
    if not condition:
        raise DraftAssistanceError("PROVIDER_BUDGET_EXTENSION_" + reason)


def _available(c):
    return bool(
        c.execute(
            "SELECT to_regclass('draft_provider_budget.extensions') name"
        ).fetchone()["name"]
    )


def _migrate(c, owner):
    path = owner.migration_path.parent / "0075_provider_budget_extension.sql"
    checksum = sha256(path.read_bytes()).hexdigest()
    c.execute("SELECT pg_advisory_xact_lock(3240075)")
    row = c.execute(
        "SELECT checksum,adapter FROM "
        "draft_provider_budget.schema_migrations WHERE version=75"
    ).fetchone()
    expected = {"checksum": checksum, "adapter": "provider-budget-extension-v1"}
    _fail(row is None or row == expected, "SCHEMA_INCOMPATIBLE")
    if row is None:
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO "
            "draft_provider_budget.schema_migrations(version,checksum,adapter) "
            "VALUES(75,%s,%s)",
            (checksum, expected["adapter"]),
        )


def _root_lock(c, owner):
    _fail(
        c.execute(
            "SELECT 1 FROM draft_provider_budget.policies WHERE "
            "namespace=%s AND security_domain=%s AND ledger_id=%s FOR "
            "UPDATE",
            scope(owner),
        ).fetchone(),
        "ROOT_MISSING",
    )


def _validate_parent(c, owner, value):
    old = require_allowance(c, owner)
    _fail(old is not None, "ALLOWANCE_REQUIRED")
    _fail(
        (value.namespace, value.securityDomain, value.ledgerId) == scope(owner)
        and value.allowanceId == old.allowanceId
        and value.allowanceDigest == _digest(old.model_dump(mode="json"))
        and value.rootPolicyDigest == old.rootPolicyDigest
        and value.previousCallCap == old.callCap
        and value.previousCostCapMicrousd == old.totalCostCapMicrousd
        and old.notBefore <= value.notBefore < value.expiresAt <= old.expiresAt,
        "PARENT_MISMATCH",
    )
    return old


def prepare(owner, document):
    """Append candidate only; no automatic activation or runtime selection."""
    value = Extension.model_validate(document)
    record = value.model_dump(mode="json")
    with owner._connection() as c:
        _migrate(c, owner)
        _root_lock(c, owner)
        _validate_parent(c, owner, value)
        c.execute(
            "INSERT INTO "
            "draft_provider_budget.extensions(namespace,security_domain,"
            "ledger_id,extension_id,allowance_id,record,digest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                *scope(owner),
                value.extensionId,
                value.allowanceId,
                Jsonb(record),
                _digest(record),
            ),
        )
        row = c.execute(
            "SELECT record,digest FROM draft_provider_budget.extensions "
            "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s "
            "AND extension_id=%s",
            (*scope(owner), value.extensionId),
        ).fetchone()
        _fail(row == {"record": record, "digest": _digest(record)}, "CONFLICT")
    return record


def _selected(owner):
    selection = getattr(owner, "budget_extension", None)
    if selection is None:
        return None
    value = Selection.model_validate(selection)
    _fail(
        (value.namespace, value.securityDomain, value.ledgerId) == scope(owner)
        and value.allowanceId == owner.allowance_id,
        "SELECTION_MISMATCH",
    )
    return value


def _load(c, owner, selection, *, lock=False):
    _fail(_available(c), "NOT_PREPARED")
    row = c.execute(
        "SELECT extension_id,allowance_id,record,digest,clock_timestamp() now FROM "
        "draft_provider_budget.extensions WHERE namespace=%s AND "
        "security_domain=%s AND ledger_id=%s AND extension_id=%s"
        + (" FOR SHARE" if lock else ""),
        (*scope(owner), selection.extensionId),
    ).fetchone()
    _fail(row is not None, "NOT_PREPARED")
    value = Extension.model_validate(row["record"])
    _fail(
        row["digest"] == _digest(row["record"]) == selection.extensionDigest
        and row["extension_id"] == value.extensionId == selection.extensionId
        and row["allowance_id"] == value.allowanceId == selection.allowanceId
        and value.authorizationEvidenceDigest == selection.authorizationEvidenceDigest,
        "BINDING_MISMATCH",
    )
    _validate_parent(c, owner, value)
    _fail(value.notBefore <= row["now"] < value.expiresAt, "EXPIRED")
    _fail(
        not c.execute(
            "SELECT 1 FROM draft_provider_budget.extension_deactivations "
            "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s "
            "AND extension_id=%s",
            (*scope(owner), value.extensionId),
        ).fetchone(),
        "DEACTIVATED",
    )
    return value


def activate(owner, command_id):
    """Original operator owner, exact candidate CAS; first extension only."""
    selection = _selected(owner)
    _fail(selection is not None and bool(command_id), "SELECTION_REQUIRED")
    with owner._connection() as c:
        _root_lock(c, owner)
        value = _load(c, owner, selection)
        record = Activation(
            schemaVersion="provider-budget-extension-activation.v1",
            selection=selection,
            commandId=command_id,
        ).model_dump(mode="json")
        c.execute(
            "INSERT INTO "
            "draft_provider_budget.extension_activations(namespace,"
            "security_domain,ledger_id,allowance_id,extension_id,"
            "command_id,record,digest) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                *scope(owner),
                value.allowanceId,
                value.extensionId,
                command_id,
                Jsonb(record),
                _digest(record),
            ),
        )
        row = c.execute(
            "SELECT record,digest FROM "
            "draft_provider_budget.extension_activations WHERE "
            "namespace=%s AND security_domain=%s AND ledger_id=%s AND "
            "allowance_id=%s",
            (*scope(owner), value.allowanceId),
        ).fetchone()
        _fail(
            row == {"record": record, "digest": _digest(record)}, "ACTIVATION_CONFLICT"
        )
    return record


def require(c, owner, *, lock=False):
    selection = _selected(owner)
    if selection is None:
        return None
    value = _load(c, owner, selection, lock=lock)
    row = c.execute(
        "SELECT allowance_id,extension_id,command_id,record,digest FROM "
        "draft_provider_budget.extension_activations WHERE namespace=%s "
        "AND security_domain=%s AND ledger_id=%s AND allowance_id=%s",
        (*scope(owner), value.allowanceId),
    ).fetchone()
    _validate_activation(row, selection, value)
    return value


def _validate_activation(row, selection, value):
    _fail(row is not None, "NOT_ACTIVE")
    try:
        record = Activation.model_validate(row["record"])
    except ValueError as exc:
        raise DraftAssistanceError(
            "PROVIDER_BUDGET_EXTENSION_ACTIVATION_INVALID"
        ) from exc
    _fail(
        row["allowance_id"] == value.allowanceId
        and row["extension_id"] == value.extensionId
        and row["command_id"] == record.commandId
        and row["digest"] == _digest(row["record"])
        and row["record"] == record.model_dump(mode="json")
        and record.selection == selection,
        "NOT_ACTIVE",
    )


def deactivate(owner, authorization_evidence_digest):
    _fail(
        isinstance(authorization_evidence_digest, str)
        and len(authorization_evidence_digest) == 64
        and all(x in "0123456789abcdef" for x in authorization_evidence_digest),
        "AUTHORIZATION_REQUIRED",
    )
    selection = _selected(owner)
    _fail(selection is not None, "SELECTION_REQUIRED")
    with owner._connection() as c:
        _root_lock(c, owner)
        _fail(_available(c), "NOT_PREPARED")
        row = c.execute(
            "SELECT digest FROM draft_provider_budget.extensions WHERE "
            "namespace=%s AND security_domain=%s AND ledger_id=%s AND "
            "extension_id=%s FOR UPDATE",
            (*scope(owner), selection.extensionId),
        ).fetchone()
        _fail(row and row["digest"] == selection.extensionDigest, "BINDING_MISMATCH")
        record = {
            "selection": selection.model_dump(mode="json"),
            "authorizationEvidenceDigest": authorization_evidence_digest,
        }
        c.execute(
            "INSERT INTO "
            "draft_provider_budget.extension_deactivations(namespace,"
            "security_domain,ledger_id,extension_id,record,digest) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (*scope(owner), selection.extensionId, Jsonb(record), _digest(record)),
        )
        saved = c.execute(
            "SELECT record,digest FROM "
            "draft_provider_budget.extension_deactivations WHERE "
            "namespace=%s AND security_domain=%s AND ledger_id=%s AND "
            "extension_id=%s",
            (*scope(owner), selection.extensionId),
        ).fetchone()
        _fail(
            saved == {"record": record, "digest": _digest(record)},
            "DEACTIVATION_CONFLICT",
        )


def context_limits(c, owner, row):
    configuration = row["record"]["configuration"]
    original = configuration["calls"], configuration["cost_microusd"]
    value = require(c, owner)
    if value is None:
        return original
    _fail(
        (row["tenant_id"], row["security_domain"], configuration["ledger_id"])
        == scope(owner),
        "CONTEXT_SCOPE_MISMATCH",
    )
    basis = ContextBasis(
        subjectId=row.get("subject_id", ""),
        authorizationDigest=row["record"]["authorization_digest"],
        configurationDigest=_digest(configuration),
    )
    if basis not in value.contextBases:
        return original
    # Even an explicitly listed smaller context must not become the ledger cap.
    if original != (value.previousCallCap, value.previousCostCapMicrousd):
        return original
    return value.callCap, value.totalCostCapMicrousd


def bind_reservation(c, owner, reservation_id, value):
    if value is None:
        return
    record = {
        "schemaVersion": "provider-budget-extension-basis.v1",
        "reservationId": reservation_id,
        "selection": _selected(owner).model_dump(mode="json"),
    }
    c.execute(
        "INSERT INTO "
        "draft_provider_budget.reservation_extension_basis(namespace,"
        "security_domain,ledger_id,reservation_id,extension_id,record,digest) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (
            *scope(owner),
            reservation_id,
            value.extensionId,
            Jsonb(record),
            _digest(record),
        ),
    )


def dispatch(c, owner, invocation):
    """Never infer new authorization for a reservation made before extension."""
    reservation_id = (
        "provider-budget-reservation:"
        + sha256(invocation.invocation_id.encode()).hexdigest()
    )
    if not _available(c):
        _fail(_selected(owner) is None, "NOT_PREPARED")
        return
    row = c.execute(
        "SELECT extension_id,record,digest FROM "
        "draft_provider_budget.reservation_extension_basis WHERE "
        "namespace=%s AND security_domain=%s AND ledger_id=%s AND "
        "reservation_id=%s",
        (*scope(owner), reservation_id),
    ).fetchone()
    if row is None:
        return  # Old reservation retains its original dispatch authorization.
    value = require(c, owner, lock=True)
    expected = {
        "schemaVersion": "provider-budget-extension-basis.v1",
        "reservationId": reservation_id,
        "selection": _selected(owner).model_dump(mode="json") if value else None,
    }
    _fail(
        value is not None
        and row["extension_id"] == value.extensionId
        and row["record"] == expected
        and row["digest"] == _digest(expected),
        "RESERVATION_BINDING_MISMATCH",
    )


def configure_from_environment(owner, environment=None):
    """Explicit deployment pin, separate from immutable model/profile JSON."""
    import json
    import os
    from pathlib import Path

    environment = os.environ if environment is None else environment
    configured = environment.get("PROVIDER_BUDGET_EXTENSION_POLICY")
    if not configured:
        return
    import stat

    path = Path(configured)
    _fail(path.is_absolute() and not path.is_symlink(), "CONFIGURATION_INVALID")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        _fail(
            stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_size <= 32768,
            "CONFIGURATION_INVALID",
        )
        raw = stream.read(32769)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            _fail(key not in result, "CONFIGURATION_INVALID")
            result[key] = value
        return result

    value = Selection.model_validate(json.loads(raw, object_pairs_hook=unique))
    previous = getattr(owner, "budget_extension", None)
    owner.budget_extension = value.model_dump(mode="json")
    try:
        with owner._connection() as c:
            require(c, owner)
    except BaseException:
        owner.budget_extension = previous
        raise
    owner.budget_extension_policy_digest = sha256(raw).hexdigest()
