# ruff: noqa: RUF001 -- Existing exact source boundary format.
"""Planning must not silently substitute an understood source."""

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_planning_source import require_same_source

SOURCE = {
    "resource_id": "knowledge:document",
    "revision_id": "knowledge-revision:one",
    "digest": "a" * 64,
}


def boundary(source):
    return (
        f"隔离合成来源：{source['resource_id']}；"
        f"修订：{source['revision_id']}；SHA256：{source['digest']}"
    )


def test_accepts_exact_server_source_inside_existing_multiline_hint():
    require_same_source(
        {"source": SOURCE},
        {"answers": ["Review this document", "Hint\n" + boundary(SOURCE)]},
    )


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("resource_id", "knowledge:other"),
        ("revision_id", "revision:two"),
        ("digest", "b" * 64),
    ],
)
def test_rejects_substitution(field, changed):
    with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
        require_same_source(
            {"source": SOURCE}, {"answers": [boundary({**SOURCE, field: changed})]}
        )


@pytest.mark.parametrize("answers", [[], ["No source"], [boundary(SOURCE)] * 2])
def test_requires_one_unambiguous_source(answers):
    with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
        require_same_source({"source": SOURCE}, {"answers": answers})


def test_historical_absence_is_not_backfilled():
    require_same_source(None, {"answers": []})


def test_malformed_retained_source_fails_closed():
    with pytest.raises(AuthorityError, match="SOURCE_MISMATCH"):
        require_same_source({}, {"answers": [boundary(SOURCE)]})
