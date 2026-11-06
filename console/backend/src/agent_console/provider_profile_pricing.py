"""Explicit append-only pricing preparation; never execution authority or new quota."""

import hashlib

from psycopg.types.json import Jsonb

from .draft_assistance import DraftAssistanceError
from .draft_provider_budget_postgres import _digest

VERSION = 49
ADAPTER = "provider-profile-pricing-v1"


def _scope(owner):
    return (
        owner.profile.scope.namespace,
        owner.profile.scope.security_domain,
        owner.ledger_id,
    )


def _migration(owner):
    return owner.migration_path.parent / "0049_provider_profile_pricing.sql"


def _record(owner, root):
    if (
        _digest(root) != owner.profile_pricing_root_digest
        or root["profileRevisionId"] == owner.profile.profile_revision_id
        or root["callCap"] != owner.call_cap
        or root["totalCostCapMicrousd"] != owner.total_cost_cap_microusd
    ):
        raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_CONFLICT")
    return {
        "schemaVersion": "provider-profile-pricing.v1",
        "rootPolicyDigest": _digest(root),
        "ledgerId": owner.ledger_id,
        "scope": list(_scope(owner)[:2]),
        "profileRevisionId": owner.profile.profile_revision_id,
        "profileDigest": owner.profile.profile_digest,
        "currency": "USD",
        "callCap": owner.call_cap,
        "totalCostCapMicrousd": owner.total_cost_cap_microusd,
        "inputPriceMicrousdPerMillionTokens": owner.input_price,
        "outputPriceMicrousdPerMillionTokens": owner.output_price,
    }


def _root(c, owner, *, lock=True):
    row = c.execute(
        "SELECT record FROM draft_provider_budget.policies WHERE namespace=%s "
        "AND security_domain=%s AND ledger_id=%s" + (" FOR UPDATE" if lock else ""),
        _scope(owner),
    ).fetchone()
    if not row:
        raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_CONFLICT")
    return row["record"]


def require_revision(c, owner, root=None):
    marker = c.execute(
        "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations "
        "WHERE version=%s",
        (VERSION,),
    ).fetchone()
    expected = {
        "checksum": hashlib.sha256(_migration(owner).read_bytes()).hexdigest(),
        "adapter": ADAPTER,
    }
    if marker != expected:
        raise DraftAssistanceError("PROVIDER_BUDGET_PRICING_NOT_PREPARED")
    record = _record(owner, root if root is not None else _root(c, owner))
    row = c.execute(
        "SELECT revision_digest,record FROM "
        "draft_provider_budget.profile_pricing_revisions "
        "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s "
        "AND profile_revision_id=%s",
        (*_scope(owner), owner.profile.profile_revision_id),
    ).fetchone()
    if row != {"revision_digest": _digest(record), "record": record}:
        raise DraftAssistanceError("PROVIDER_BUDGET_PROFILE_CONFLICT")
    return _digest(record)


def prepare_revision(c, owner):
    """Operator preparation only; caller owns transaction, never called at startup.

    No Grants, invocations, reservations or settlements are created. Exact model
    resources and current platform authority must separately permit any dispatch.
    """
    c.execute("SELECT pg_advisory_xact_lock(232449)")
    record = _record(owner, _root(c, owner))
    path = _migration(owner)
    expected = {
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
        "adapter": ADAPTER,
    }
    marker = c.execute(
        "SELECT checksum,adapter FROM draft_provider_budget.schema_migrations "
        "WHERE version=%s",
        (VERSION,),
    ).fetchone()
    if marker is not None and marker != expected:
        raise DraftAssistanceError("PROVIDER_BUDGET_SCHEMA_INCOMPATIBLE")
    if marker is None:
        c.execute(path.read_text())
        c.execute(
            "INSERT INTO draft_provider_budget.schema_migrations"
            "(version,checksum,adapter) VALUES(%s,%s,%s)",
            (VERSION, expected["checksum"], ADAPTER),
        )
    c.execute(
        "INSERT INTO draft_provider_budget.profile_pricing_revisions"
        "(namespace,security_domain,ledger_id,profile_revision_id,profile_digest,"
        "revision_digest,record) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
        (
            *_scope(owner),
            owner.profile.profile_revision_id,
            owner.profile.profile_digest,
            _digest(record),
            Jsonb(record),
        ),
    )
    return require_revision(c, owner)


def bind_reservation(c, owner, reservation_id):
    if owner.profile_pricing_root_digest is not None:
        revision = require_revision(c, owner)
        c.execute(
            "INSERT INTO draft_provider_budget.reservation_pricing"
            "(namespace,security_domain,ledger_id,reservation_id,revision_digest) "
            "VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (*_scope(owner), reservation_id, revision),
        )
    require_reservation(c, owner, reservation_id)


def require_reservation(c, owner, reservation_id):
    exists = c.execute(
        "SELECT to_regclass('draft_provider_budget.reservation_pricing') AS name"
    ).fetchone()["name"]
    if not exists:
        if owner.profile_pricing_root_digest is not None:
            raise DraftAssistanceError("PROVIDER_BUDGET_PRICING_NOT_PREPARED")
        return
    row = c.execute(
        "SELECT v.profile_revision_id,v.profile_digest,v.record FROM "
        "draft_provider_budget.reservation_pricing b JOIN "
        "draft_provider_budget.profile_pricing_revisions v "
        "USING(namespace,security_domain,ledger_id,revision_digest) "
        "WHERE b.namespace=%s AND b.security_domain=%s AND b.ledger_id=%s "
        "AND b.reservation_id=%s",
        (*_scope(owner), reservation_id),
    ).fetchone()
    if row is None and owner.profile_pricing_root_digest is None:
        return
    if row is None or (
        row["profile_revision_id"] != owner.profile.profile_revision_id
        or row["profile_digest"] != owner.profile.profile_digest
        or row["record"]["inputPriceMicrousdPerMillionTokens"] != owner.input_price
        or row["record"]["outputPriceMicrousdPerMillionTokens"] != owner.output_price
    ):
        raise DraftAssistanceError("PROVIDER_BUDGET_RESERVATION_PROFILE_MISMATCH")


def historical_settlement(owner, invocation_id, receipt):
    """Read an authorized immutable receipt at its own bound price; never settle."""
    from types import SimpleNamespace

    from .draft_provider_budget_postgres import PostgresProviderCallBudget

    reservation_id = receipt["reservation_id"]
    with owner._connection() as c:
        reservation = c.execute(
            "SELECT invocation_id FROM draft_provider_budget.reservations "
            "WHERE namespace=%s AND security_domain=%s AND ledger_id=%s "
            "AND reservation_id=%s",
            (*_scope(owner), reservation_id),
        ).fetchone()
        if reservation != {"invocation_id": invocation_id}:
            raise DraftAssistanceError("PROVIDER_BUDGET_RESERVATION_PROFILE_MISMATCH")
        root = _root(c, owner, lock=False)
        bound = None
        if c.execute(
            "SELECT to_regclass('draft_provider_budget.reservation_pricing') AS name"
        ).fetchone()["name"]:
            bound = c.execute(
                "SELECT v.record,v.revision_digest FROM "
                "draft_provider_budget.reservation_pricing b JOIN "
                "draft_provider_budget.profile_pricing_revisions v "
                "USING(namespace,security_domain,ledger_id,revision_digest) "
                "WHERE b.namespace=%s AND b.security_domain=%s AND b.ledger_id=%s "
                "AND b.reservation_id=%s",
                (*_scope(owner), reservation_id),
            ).fetchone()
        record = bound["record"] if bound else root
        if bound and (
            record.get("schemaVersion") != "provider-profile-pricing.v1"
            or record.get("rootPolicyDigest") != _digest(root)
            or bound["revision_digest"] != _digest(record)
            or record.get("scope") != list(_scope(owner)[:2])
            or record.get("ledgerId") != owner.ledger_id
        ):
            raise DraftAssistanceError("PROVIDER_BUDGET_RESERVATION_PROFILE_MISMATCH")
        historical = SimpleNamespace(
            ledger_id=owner.ledger_id,
            profile=SimpleNamespace(
                profile_revision_id=record["profileRevisionId"],
                profile_digest=record["profileDigest"],
            ),
            input_price=record["inputPriceMicrousdPerMillionTokens"],
            output_price=record["outputPriceMicrousdPerMillionTokens"],
            profile_pricing_root_digest=record.get("rootPolicyDigest")
            if bound
            else None,
        )
        if receipt["pricing"] != PostgresProviderCallBudget.pricing(historical):
            raise DraftAssistanceError("PROVIDER_BUDGET_RESERVATION_PROFILE_MISMATCH")
        row = c.execute(
            "SELECT input_tokens,output_tokens,actual_cost_microusd "
            "FROM draft_provider_budget.settlements WHERE namespace=%s "
            "AND security_domain=%s AND ledger_id=%s AND reservation_id=%s",
            (*_scope(owner), reservation_id),
        ).fetchone()
    return PostgresProviderCallBudget.settlement_projection(row)
