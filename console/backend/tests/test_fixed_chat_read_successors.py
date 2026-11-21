"""Bounded READ set transitions. These unit tests issue no real grants."""

import pytest
from agent_console.authority_contracts import ExactGrant
from agent_console.fixed_chat_read_access import permits_target_successor, target_digest

A = ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + "a" * 64)
B = ExactGrant("EVIDENCE", "READ_REFERENCE", "evidence-reference:prepared:a:result")
C = ExactGrant("EXECUTION", "READ", "governed-execution:prepared:" + "c" * 64)


@pytest.mark.parametrize(
    "state,prior,current,allowed",
    [
        ("READ_READY", (A,), (A, B), True),
        ("READ_READY", (A,), (A,), False),
        ("EXPIRED", (A,), (A,), True),
        ("EXPIRED", (A,), (A, B), True),
        ("UNKNOWN", (A,), (A, B), False),
        ("NOT_PREPARED", (A,), (A, B), False),
        ("READ_READY", (A, B), (A,), False),
        ("EXPIRED", (A,), (C,), False),
        ("READ_READY", (), (A,), False),
    ],
)
def test_only_completed_exact_sets_can_have_bounded_successors(
    state, prior, current, allowed
):
    assert permits_target_successor(state, prior, current) is allowed


def test_target_digest_is_order_independent_but_never_drops_identity():
    assert target_digest((A, B)) == target_digest((B, A))
    assert target_digest((A, B)) != target_digest((A,))
    assert target_digest((A, B)) != target_digest((C, B))
