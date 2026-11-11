"""Reject detached adaptive records and never settle during readback."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.plan_suggestion_domain import PlanningError
from agent_console.planning_adaptive import child_key
from agent_console.planning_readonly_chain import read_chain


def fixture():
    target = {"problem": {"resource_id": "problem", "revision_id": "r1"}}
    first = {
        "invocation": {
            "target": {"invocation_id": "root", "problem": target},
            "request": {
                "idempotency_key": "request",
                "target": target,
                "adaptive_loop": {"maximum_attempts": 3},
            },
        },
        "result": {"technical_status": "SUCCEEDED", "kind": "INVALID"},
    }
    child = deepcopy(first)
    child["invocation"]["target"]["invocation_id"] = "child"
    child["invocation"]["request"].update(
        idempotency_key=child_key("request", 1), predecessor_invocation_id="root"
    )
    rows = {"root": first, "child": child}
    lookup = {"request": "root", child_key("request", 1): "child"}
    reads = []

    def read(principal, identity, *, settle_receipt):
        assert settle_receipt is False
        reads.append(identity)
        return rows[identity]

    service = SimpleNamespace(
        application=SimpleNamespace(scope=lambda p: "scope"),
        invocations=SimpleNamespace(find_request=lambda s, p, k: lookup.get(k)),
        read=read,
    )
    return service, SimpleNamespace(principal_id="actor"), rows, reads


@pytest.mark.parametrize("mismatch", ["key", "predecessor", "target", "limit"])
def test_detached_or_unbounded_chain_is_rejected(mismatch):
    service, principal, rows, _ = fixture()
    request = rows["child"]["invocation"]["request"]
    if mismatch == "key":
        request["idempotency_key"] = "unrelated"
    elif mismatch == "predecessor":
        request["predecessor_invocation_id"] = "unrelated"
    elif mismatch == "target":
        request["target"] = {"problem": {"resource_id": "other"}}
    else:
        rows["root"]["invocation"]["request"]["adaptive_loop"] = {
            "maximum_attempts": 1000
        }
    with pytest.raises(PlanningError, match="PLANNING_CHAIN_"):
        read_chain(service, principal, "request")


def test_no_child_is_created_and_missing_root_is_not_recovered_by_dispatch():
    service, principal, _, reads = fixture()
    result = read_chain(service, principal, "request")
    assert result["rootInvocationId"] == "root"
    assert result["value"]["invocation"]["target"]["invocation_id"] == "child"
    assert reads == ["root", "child"]
    with pytest.raises(PlanningError, match="PLANNING_NOT_FOUND"):
        read_chain(service, principal, "missing")
    assert reads == ["root", "child"]
