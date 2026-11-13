from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest
from agent_console import current_work_history_access as module
from agent_console.authority_contracts import AuthorityError


def fixture(monkeypatch, *, anchor=True, archived=False):
    seen = []

    class Connection:
        def execute(self, sql, args):
            assert sql.startswith("SELECT")
            seen.append((sql, args))
            if sql.startswith("SELECT created_at"):
                return NS(
                    fetchone=lambda: (
                        {"created_at": "date", "conversation_id": "c19"}
                        if anchor
                        else None
                    )
                )
            start = 20 if "AND (v.created_at" in sql else 0
            rows = [{"conversation_id": f"c{i}"} for i in range(start, 25)]
            return NS(fetchall=lambda: rows[: module.LIMIT + 1])

    @contextmanager
    def connection():
        yield Connection()

    @contextmanager
    def protected():
        yield None

    context = NS(principal_id="alice")
    service = NS(
        experience=NS(
            document=NS(historyReadEnabled=True), _require=lambda *args: None
        ),
        repository=NS(connection_scope=connection),
    )
    authorizer = NS(controller=NS(protected_request=protected))
    records = NS(
        scope=lambda ctx: ("tenant", "domain"),
        owned=lambda *a, **kw: {
            "owner_id": "alice",
            "archived_at": "now" if archived else None,
        },
    )
    prepared = []

    def prepare(service, records, context, identity, c):
        prepared.append(identity)
        return {"available": True, "items": [{"state": "EFFECTIVE"}]}

    monkeypatch.setattr(module, "prepare", prepare)
    return (service, records, authorizer, context), seen, prepared


def test_page_reaches_older_history_without_restarting_first_page(monkeypatch):
    args, seen, prepared = fixture(monkeypatch)
    first = module.prepare_directory(*args)
    assert first["checked"] == 20 and first["hasMore"] and first["partial"]
    second = module.prepare_directory(*args, after=first["nextConversationId"])
    assert second["checked"] == 5 and not second["hasMore"] and not second["partial"]
    assert len(prepared) == len(set(prepared)) == 25
    assert seen[-1][1] == ("tenant", "domain", "alice", "date", "c19", 21)


def test_foreign_cursor_rejected_before_any_history_owner_call(monkeypatch):
    args, seen, prepared = fixture(monkeypatch, anchor=False)
    with pytest.raises(AuthorityError, match="CONVERSATION_HISTORY_SCOPE_DENIED"):
        module.prepare_directory(*args, after="foreign")
    assert prepared == []
    assert seen[0][1] == ("tenant", "domain", "alice", "foreign")


def test_archive_race_never_invokes_history_owner(monkeypatch):
    args, _, prepared = fixture(monkeypatch, archived=True)
    value = module.prepare_directory(*args)
    assert value["partial"] and value["prepared"] == 0 and prepared == []
