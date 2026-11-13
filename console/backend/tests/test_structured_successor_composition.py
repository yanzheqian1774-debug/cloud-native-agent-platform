"""Exact retained profile selection; no current-default budget fallback."""

from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.native_typed_answer import settlement_reader_for_services

OLD = "v3-relation-adoption-source-answers"
NEW = "v4-structured-conversation"


def service(revision, identity, calls):
    profile = NS(
        adapter_revision=revision,
        profile_revision_id=identity,
        profile_digest=identity * 64,
    )

    def read(c, invocation):
        calls.append((identity, c, invocation))
        return {"status": "ESTIMATE_SETTLED", "reservation_retained": False}

    return NS(profile=profile, budget=NS(read_invocation_settlement=read))


def invocation(service):
    p = service.profile
    return NS(
        profile_revision_id=p.profile_revision_id,
        snapshot=NS(
            adapter_revision=p.adapter_revision, profile_digest=p.profile_digest
        ),
    )


def test_typed_old_and_structured_select_their_original_same_connection_budget():
    calls = []
    old, new = service(OLD, "a", calls), service(NEW, "b", calls)
    reader = settlement_reader_for_services(old, new)
    connection = object()
    for value in (old, new, old):
        inv = invocation(value)
        assert reader(connection, inv)["status"] == "ESTIMATE_SETTLED"
    assert [item[0] for item in calls] == ["a", "b", "a"]
    assert all(item[1] is connection for item in calls)
    assert settlement_reader_for_services(None) is None


@pytest.mark.parametrize(
    "field", ["profile_revision_id", "profile_digest", "adapter_revision", "missing"]
)
def test_unknown_or_mixed_profile_never_uses_current_budget(field):
    calls = []
    old, new = service(OLD, "a", calls), service(NEW, "b", calls)
    inv = invocation(old)
    if field == "missing":
        inv.snapshot = None
    elif field == "profile_revision_id":
        inv.profile_revision_id = new.profile.profile_revision_id
    else:
        setattr(inv.snapshot, field, getattr(new.profile, field))
    with pytest.raises(AuthorityError, match="TYPED_ANSWER_BINDING_INVALID"):
        settlement_reader_for_services(old, new)(object(), inv)
    assert calls == []


def test_ambiguous_exact_profile_is_rejected_at_composition():
    one = service(OLD, "a", [])
    with pytest.raises(AuthorityError):
        settlement_reader_for_services(one, one)


@pytest.mark.parametrize(
    "previous_revision", [OLD, "v3-relation-adoption-source", None]
)
def test_structured_adoption_requires_the_exact_retained_typed_predecessor(
    monkeypatch, previous_revision
):
    from agent_console import draft_assistance_authorization
    from agent_console import understanding_adoption_admission as module

    previous = NS()
    root = NS(
        delegation=object(),
        configuration={"ledger_id": "original"},
        experience=NS(document=NS(allowanceId="original")),
    )
    if previous_revision is not None:
        root.understanding_adoption = NS(
            routing=previous, profile=NS(adapter_revision=previous_revision)
        )
    calls = []
    current = service(NEW, "b", calls)
    current.transport = NS(configuration=object())
    current.budget.ledger_id = current.budget.allowance_id = "original"
    monkeypatch.setattr(module, "configured_limits", lambda *args: {})
    monkeypatch.setattr(module, "ContextCallAdmission", lambda *args: NS())
    monkeypatch.setattr(module, "AdoptionExperience", lambda *args: NS())
    monkeypatch.setattr(module, "AdoptionOrigin", lambda *args, **kwargs: NS(**kwargs))
    monkeypatch.setattr(
        draft_assistance_authorization,
        "GrantAdministrationDraftAuthorization",
        lambda *args, **kwargs: NS(),
    )
    if previous_revision != OLD:
        with pytest.raises(AuthorityError, match="PREDECESSOR_MISMATCH"):
            module.configure(
                current, root, previous, NS(clock=object()), object(), "private-policy"
            )
        assert not hasattr(current, "authorization")
    else:
        admission = module.configure(
            current, root, previous, NS(clock=object()), object(), "private-policy"
        )
        assert current.authorization.context_admission is admission
        assert root.conversation_relation is admission
        assert root.retained_conversation_relations == (previous,)
        assert root.understanding_adoption.retained[0].profile.adapter_revision == OLD


@pytest.mark.parametrize(
    "mode", ["disabled", "enabled", "missing-typed", "build-failure"]
)
def test_actual_app_composition_retains_profiles_and_closes_successor(
    monkeypatch, mode
):
    from unittest.mock import Mock

    from agent_console import app as target
    from agent_console import draft_assistance_bootstrap, workbench_bootstrap

    keys = [
        "DRAFT_ASSISTANCE_RUNTIME_FILE",
        "CONVERSATION_ROUTING_RUNTIME_FILE",
        "UNDERSTANDING_ADOPTION_RUNTIME_FILE",
        "UNDERSTANDING_SOURCE_ADOPTION_RUNTIME_FILE",
        "TYPED_QUESTION_ANSWER_RUNTIME_FILE",
        "STRUCTURED_UNDERSTANDING_RUNTIME_FILE",
    ]
    for key in (
        *keys,
        "PLANNING_RUNTIME_FILE",
        "WORKFLOW_RUNTIME_DATABASE_URL",
        "PREPARED_EXECUTION_ENABLED",
        "SALES_GROSS_PROFIT_V2_CANDIDATE",
        "SALES_SUPPLEMENT_CANDIDATE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key in keys[:-1]:
        monkeypatch.setenv(key, "/controlled/" + key)
    if mode != "disabled":
        monkeypatch.setenv(keys[-1], "/controlled/" + keys[-1])
    if mode == "missing-typed":
        monkeypatch.delenv(keys[-2])
    monkeypatch.setenv("WORKBENCH_AUTHORITY_RUNTIME_FILE", "/controlled/authority")
    monkeypatch.setenv("WORKBENCH_ALLOWED_HOST", "test.local")
    monkeypatch.setenv("WORKBENCH_ALLOWED_ORIGIN", "https://test.local")
    monkeypatch.setattr(target, "_business_problem_application", object())
    monkeypatch.setattr(target, "_agent_definition_service", NS(repository=object()))
    monkeypatch.setattr(
        target,
        "_digital_employee_assembly",
        NS(employee_definitions=object(), repository=object()),
    )
    for name in (
        "_workbench_composition",
        "_draft_assistance_composition",
        "_conversation_routing_composition",
        "_understanding_adoption_composition",
        "_understanding_source_adoption_composition",
        "_typed_question_answer_composition",
        "_structured_understanding_composition",
        "workbench_app",
        "_workbench_startup_error",
    ):
        monkeypatch.setattr(target, name, None)
    built, received = {}, []

    def compose(**kwargs):
        name = kwargs["runtime_configuration_path"].name
        result = NS(service=object(), model_repository=object(), close=Mock())
        built[name] = result
        return result

    def bootstrap(**kwargs):
        received.append(kwargs)
        if mode == "build-failure":
            raise ValueError("controlled failure after all services constructed")
        return NS(application=object())

    monkeypatch.setattr(
        draft_assistance_bootstrap, "build_draft_assistance_composition", compose
    )
    monkeypatch.setattr(workbench_bootstrap, "build_workbench_composition", bootstrap)
    target._configure_workbench()
    if mode in {"missing-typed", "build-failure"}:
        assert target.workbench_app is None
        assert all(value.close.call_count == 1 for value in built.values())
        assert target._structured_understanding_composition is None
    else:
        assert target.workbench_app is not None
        assert received[0]["conversation_typed_answers"] is built[keys[-2]].service
        assert received[0]["conversation_structured_understanding"] is (
            built[keys[-1]].service if mode == "enabled" else None
        )
        assert all(
            value in received[0]["managed_closeables"] for value in built.values()
        )
        assert not any(value.close.called for value in built.values())
