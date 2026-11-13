"""Real PG owners/signature; understanding/model outcomes are controlled fixtures."""

from copy import deepcopy
from datetime import datetime
from hashlib import sha256

import pytest
from agent_console.authority_configuration import StaticAuthorityLoader
from agent_console.authority_contracts import AuthorityError
from agent_console.context_call_admission import (
    ContextApproval,
    bind_problem,
    request_row,
)
from agent_console.conversation_planning_admission import (
    ConversationPlanningAdmission,
    bound_source_input,
)
from agent_console.conversation_planning_recovery import prepare_observation, projection
from agent_console.plan_suggestion_invocation import PlanningRequest
from agent_console.planning_call_admission import PlanningCallAdmission
from psycopg.types.json import Jsonb
from test_context_call_admission import env  # noqa: F401
from test_conversation_experience_admission import (
    configure,
)
from test_conversation_experience_admission import (
    prepare as prepare_source,
)
from test_conversation_experience_admission import pytestmark as pytestmark
from test_conversation_planning_recovery import make_unknown, prepare, request, spec
from test_conversation_planning_source import SOURCE, boundary
from test_local_accounts_postgres import login
from test_local_accounts_postgres import setup as base_setup


@pytest.fixture
def setup(monkeypatch):
    # Configure a third independent administrator before bootstrapping the real
    # isolated authority/account owners. No authorization checks are replaced.
    parse = StaticAuthorityLoader._parse

    def with_independent_admin(document, *, digest):
        document = deepcopy(document)
        original = next(
            c
            for c in document["credentials"]
            if c["principalId"] == "human:demo323-approver"
        )
        document["credentials"].append(
            {
                **original,
                "credentialId": "independent-admin-source",
                "credentialSha256": sha256(b"isolated-independent-admin").hexdigest(),
                "principalId": "human:development-admin",
            }
        )
        document["localAccounts"].append(
            {
                "username": "devadmin",
                "grantSourceCredentialId": "independent-admin-source",
            }
        )
        return parse(document, digest=digest)

    monkeypatch.setattr(
        StaticAuthorityLoader, "_parse", staticmethod(with_independent_admin)
    )
    yield from base_setup.__wrapped__()


def result(e, identity, **changes):
    with e.repo.connection_scope() as c:
        c.execute(
            "INSERT INTO draft_assistance.invocation_versions "
            "SELECT namespace,security_domain,invocation_id,aggregate_version+1,"
            "%s,record || %s,now() FROM draft_assistance.invocation_versions "
            "WHERE invocation_id=%s ORDER BY aggregate_version DESC LIMIT 1",
            (changes.get("state", "SUCCEEDED"), Jsonb(changes), identity),
        )


@pytest.fixture
def selected_source(env, setup, tmp_path):  # noqa: F811
    e = env
    sessions = setup[2]
    _, e.independent_admin = sessions.authenticate_session(
        login(sessions, "devadmin").value
    )
    first, owner, _, _ = configure(e, tmp_path)
    prepare_source(e, first, owner)
    result(
        e,
        first.invocation_id,
        state="SUCCEEDED",
        resultKind="NEEDS_DATA",
        inputSource=None,
    )
    bound = e.draft.begin(
        e.reviewer,
        key="selected-source",
        content="selected source",
        parent_context_id=first.context_id,
        parent_turn_id=first.turn_id,
        expected_parent_version=first.turn_version,
        predecessor_invocation_id=first.invocation_id,
    ).invocation
    result(
        e,
        bound.invocation_id,
        state="SUCCEEDED",
        resultKind="DRAFT_READY",
        inputSource={"source": SOURCE},
    )
    with e.repo.connection_scope() as c:
        assert bind_problem(
            c,
            e.reviewer,
            {"revision": {"business_problem_id": "ordinary-new-problem"}},
            bound.invocation_id,
        )
    e.planning = PlanningCallAdmission(
        e.admission.delegation, dict(e.admission.configuration)
    )
    e.planning.migrate()
    e.planning.conversation_experience = ConversationPlanningAdmission(
        e.admission, e.planning.configuration
    )
    e.first, e.bound = first, bound
    make_unknown(e, request("old").model_copy(update={"answers": (boundary(SOURCE),)}))
    observed = prepare_observation(e.planning, e.reviewer, spec())
    pending = prepare(e, PlanningRequest.model_validate(observed["record"]["request"]))
    e.recovery_id, e.new_context = (
        observed["recovery_id"],
        pending["admission"]["context_id"],
    )
    with e.repo.connection_scope() as c:
        row = request_row(c, e.new_context)
    e.signature = ContextApproval(
        request_digest=row["digest"],
        expires_at=datetime.fromisoformat(observed["record"]["expires_at"]),
        idempotency_key="independent-bound-source",
    )
    return e


@pytest.mark.parametrize("late_old_return", [False, True])
def test_problem_bound_second_turn_allows_independent_administrator_signature(
    selected_source,
    late_old_return,
):
    e = selected_source
    # A later successful turn in the same context must not replace the bound one.
    later = e.draft.begin(
        e.reviewer,
        key="unbound-later",
        content="another source",
        parent_context_id=e.bound.context_id,
        parent_turn_id=e.bound.turn_id,
        expected_parent_version=e.bound.turn_version,
        predecessor_invocation_id=e.bound.invocation_id,
    ).invocation
    result(
        e,
        later.invocation_id,
        state="SUCCEEDED",
        resultKind="DRAFT_READY",
        inputSource={"source": {**SOURCE, "digest": "c" * 64}},
    )
    if late_old_return:
        result(
            e,
            e.first.invocation_id,
            state="SUCCEEDED",
            resultKind="DRAFT_READY",
            inputSource={"source": {**SOURCE, "digest": "d" * 64}},
        )
    with e.repo.connection_scope() as c:
        source = request_row(c, e.first.context_id)
        assert source["first_invocation_id"] == e.first.invocation_id
        assert e.first.invocation_id != e.bound.invocation_id
        assert bound_source_input(c, source, "ordinary-new-problem") == {
            "source": SOURCE
        }
        with pytest.raises(AuthorityError, match="BINDING_REQUIRED"):
            bound_source_input(c, source, "another-problem")
    with pytest.raises(AuthorityError):
        e.planning.approve(e.reviewer, e.new_context, e.signature)
    signed = e.planning.approve(e.independent_admin, e.new_context, e.signature)
    assert signed["issuer_id"] == e.independent_admin.principal_id
    assert signed["issuer_id"] != e.reviewer.principal_id
    readback = projection(e.planning, e.reviewer, e.recovery_id)
    assert readback["state"] == "AUTHORIZED"
    assert projection(e.planning, e.reviewer, e.recovery_id) == readback
    assert e.planning.approve(e.independent_admin, e.new_context, e.signature) == signed
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM workflow_planning.invocations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.settlements"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize(
    "change",
    [
        {"initiatingPrincipalId": "human:wrong-subject"},
        {"contextId": "wrong-context"},
        {"state": "INVOKING", "resultKind": None},
        {"resultKind": "NEEDS_DATA"},
        {"inputSource": {"source": {**SOURCE, "digest": "f" * 64}}},
    ],
)
def test_bound_source_mismatch_never_gets_a_signature(selected_source, change):
    e = selected_source
    result(e, e.bound.invocation_id, **change)
    with pytest.raises(AuthorityError):
        e.planning.approve(e.independent_admin, e.new_context, e.signature)
    with e.repo.connection_scope() as c:
        assert (
            c.execute(
                "SELECT count(*) n FROM authorization_admin.context_call_decisions "
                "WHERE context_id=%s",
                (e.new_context,),
            ).fetchone()["n"]
            == 0
        )
