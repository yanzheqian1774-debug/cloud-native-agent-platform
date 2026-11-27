"""Opt-in persistence of validated same-response intent; no legacy rewrite."""

import json

import pytest
from agent_console.conversation_relation_context import (
    metadata_for_snapshot,
    sealed_snapshot,
    validated_route,
)


@pytest.mark.parametrize("intent", ["TASK", "ANSWER"])
def test_natural_snapshot_preserves_validated_intent_only_when_opted_in(intent):
    result = {"relation": "INDEPENDENT", "currentQuestionToken": None, "intent": intent}
    snapshot = {"kind": "SERVER_CURRENT_CONVERSATION", "currentQuestion": None}

    def payload(value):
        return json.dumps({"input": [{}, {"content": [{"text": json.dumps(value)}]}]})

    assert validated_route(result, payload(snapshot)) == {
        "relation": "INDEPENDENT",
        "currentQuestionToken": None,
    }
    assert validated_route(
        result, payload({**snapshot, "naturalGoalIntentVersion": "v1"})
    ) == {**result}
    sealed = sealed_snapshot(
        "chat", "message", None, {**snapshot, "naturalGoalIntentVersion": "v1"}
    )
    assert metadata_for_snapshot(sealed)["naturalGoalIntentVersion"] == "v1"


@pytest.mark.parametrize("intent", [None, "task", "EXECUTE", {}])
def test_natural_snapshot_rejects_unknown_intent(intent):
    snapshot = {"kind": "SERVER_CURRENT_CONVERSATION", "naturalGoalIntentVersion": "v1"}
    payload = json.dumps({"input": [{}, {"content": [{"text": json.dumps(snapshot)}]}]})
    with pytest.raises((ValueError, TypeError)):
        validated_route(
            {"relation": "INDEPENDENT", "currentQuestionToken": None, "intent": intent},
            payload,
        )


def test_v3_business_origin_is_explicit_and_retains_old_policy_bytes(tmp_path):
    from agent_console.authority_contracts import AuthorityError
    from agent_console.owned_business_policy import (
        OwnedBusinessPolicy,
        OwnedBusinessPolicyV3,
    )
    from agent_console.owned_business_work_reader import OwnedBusinessWorkReader
    from test_owned_business_policy import document

    old = OwnedBusinessPolicy.model_validate({**document(), "enabled": True})
    old_path = tmp_path / "old.json"
    old_path.write_text(json.dumps(old.model_dump(mode="json")))
    old_path.chmod(0o600)
    new = {
        **old.model_dump(mode="json"),
        "schemaVersion": "owned-business-admission.v3",
        "enabled": False,
        "retainedReadPolicyDigests": [old.digest],
        "independentGoalProfile": {
            "profileRevisionId": "exact-v4",
            "profileDigest": "f" * 64,
            "adapterRevision": "v4-structured-conversation",
        },
    }
    new_path = tmp_path / "new.json"
    new_path.write_text(json.dumps(new))
    new_path.chmod(0o600)
    loaded = OwnedBusinessPolicy.load(new_path)
    assert isinstance(loaded, OwnedBusinessPolicyV3)
    assert loaded.enabled is False
    assert "independentGoalProfile" not in old.model_dump()
    assert OwnedBusinessPolicy.load(old_path).digest == old.digest
    owner = OwnedBusinessWorkReader(
        new_path, None, 1, 1, retained_history_paths=[old_path]
    )
    retained = owner.retained_history[old.digest]
    with pytest.raises(AuthorityError, match="HISTORY_ONLY"):
        retained.work(None, None, None)
    with pytest.raises(AuthorityError, match="HISTORY_ONLY"):
        retained.planning_basis(None, None, None)
    from pydantic import ValidationError

    for profile in (None, {**new["independentGoalProfile"], "adapterRevision": "old"}):
        with pytest.raises(ValidationError):
            OwnedBusinessPolicyV3.model_validate(
                {**new, "independentGoalProfile": profile}
            )


@pytest.mark.parametrize(
    "relation",
    ["private_conversation.journeys", "(SELECT * FROM verified_goal_journals)"],
)
def test_execution_navigation_query_preserves_exact_problem_path(monkeypatch, relation):
    from types import SimpleNamespace as N

    from agent_console import (
        conversation_goal_selection,
    )
    from agent_console import (
        workbench_execution_origin as target,
    )

    monkeypatch.setattr(
        conversation_goal_selection, "journal_relation", lambda c: relation
    )
    monkeypatch.setattr(target, "for_call", lambda call: False)
    queries = []

    def execute(sql, args):
        queries.append((sql, args))
        return N(fetchone=lambda: None)

    call = N(
        connection=N(execute=execute),
        context=N(
            principal_id="human:reader",
            scope=N(tenant_id="tenant", security_domain="domain"),
        ),
    )
    assert target.read_execution_origin(call, "exact-execution", "exact-problem") == {
        "originConversationId": None,
        "originVerified": False,
    }
    sql, args = queries[0]
    assert "j.state#>>'{problem,business_problem_id}'=%s" in sql
    assert "LEFT JOIN " + relation + " j" in sql
    assert args == (
        "exact-execution",
        "tenant",
        "domain",
        "human:reader",
        False,
        "exact-problem",
        "exact-execution",
        "exact-execution",
        "exact-problem",
    )
