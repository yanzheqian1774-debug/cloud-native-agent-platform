# ruff: noqa: F401,F811 -- Explicit real isolated service authority fixture.
"""0073 immutable setup -> real service admission, not real Human/model acceptance."""

import json
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256

import pytest
from agent_console import fixed_work_authoring_postgres as authoring
from agent_console import fixed_work_sources_postgres as sources
from agent_console.authority_configuration import StaticGrant
from agent_console.authority_contracts import AuthorityError, ExactGrant, GrantSource
from agent_console.digital_employee_definition import digest
from agent_console.fixed_work_authoring import SaveDraft
from agent_console.fixed_work_bound_policy import (
    BoundServicePlanningPolicy,
    ScheduleWindow,
    compile_windows,
)
from agent_console.fixed_work_service_admission import event_key
from agent_console.fixed_work_service_policy import ServicePlanningPolicy
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.plan_suggestion_invocation import PlanningRequest
from agent_console.resource_automation_policy import source_digest
from agent_console.workbench_prepared_resources import reference
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_fixed_work_authoring import body
from test_fixed_work_service_admission_postgres import fixture
from test_plan_suggestion_v2 import repository


@pytest.fixture
def bound(fixture):
    f = fixture
    minute = (f.now - timedelta(minutes=1)).strftime("%H:%M")
    draft = {
        **body(),
        "revisionId": "revision:2",
        "commandId": "second-config",
        "expectedVersion": 1,
        "predecessorRevisionId": "revision:1",
        "trigger": dict(
            kind="SCHEDULE", timezone="UTC", localTime=minute, cadence="DAILY"
        ),
    }
    from test_native_document_tools import SOURCE

    raw = json.dumps(SOURCE)
    content = {
        "documents": [
            {
                "contentDigest": sha256(raw.encode()).hexdigest(),
                "chunks": [{"content": raw}],
            }
        ]
    }
    source = ExactReference(
        resource_id="knowledge:fixed", revision_id="r", digest=digest(content)
    )
    with f.repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        saved, _ = authoring.save(
            c,
            ("tenant-a", "quality"),
            "human:alice",
            SaveDraft.model_validate(draft),
            dict(teamId="team", revisionId="r", digest="a" * 64),
            "b" * 64,
            "fixture-authoring",
            f.now,
        )
        sources.migrate(c)
        # Published resource and exact Human provenance are immutable fixture input;
        # real authoring/BIND path is separately exercised by the source package.
        c.execute(
            "INSERT INTO knowledge_operation.knowledge "
            "(namespace,security_domain,knowledge_id,aggregate_version,record) "
            "VALUES(%s,%s,%s,1,%s)",
            (
                "tenant-a",
                "quality",
                source.resource_id,
                Jsonb(
                    dict(
                        name="Fixed source",
                        publishedRevisionId="r",
                        archived=False,
                        revisions=[
                            dict(
                                revisionId="r",
                                digest=source.digest,
                                state="PUBLISHED",
                                content=content,
                            )
                        ],
                    )
                ),
            ),
        )
        work = ExactReference(
            resource_id="work:1", revision_id="revision:2", digest=saved["digest"]
        )
        handoff = dict(
            work=work.model_dump(mode="json"),
            team=saved["record"]["team"],
            subjectId="human:alice",
            conversationId="original-conversation",
            commandId="fixture-handoff",
            instructionDigest=digest(draft["instruction"]),
            mode="TARGET_REVIEW_ONLY",
            executionEnabled=False,
        )
        h = sources.append(c, ("tenant-a", "quality"), "handoffs", handoff)
        binding = sources.append(
            c,
            ("tenant-a", "quality"),
            "bindings",
            {
                **handoff,
                "commandId": "fixture-binding",
                "handoffDigest": h["digest"],
                "target": f.policy.target.model_dump(mode="json"),
                "inputSource": dict(
                    source=source.model_dump(mode="json"),
                    sourceContentDigest=source_digest(content),
                ),
            },
        )
    window = ScheduleWindow(
        notBefore=f.now - timedelta(minutes=2),
        expiresAt=f.policy.expiresAt,
        windowSeconds=600,
    )
    events = compile_windows(work, draft["trigger"], window)
    policy = BoundServicePlanningPolicy.model_validate(
        {
            **f.policy.model_dump(mode="json"),
            "schemaVersion": "fixed-work-service-planning.v2",
            "work": work.model_dump(mode="json"),
            "sourceBindingDigest": binding["digest"],
            "scheduleWindow": window.model_dump(mode="json"),
            "allowedEventIds": list(events),
            "eventWindows": events,
        }
    )
    generation = f.generation
    member = ExactGrant(
        "KNOWLEDGE",
        "READ_RESOURCE",
        reference("knowledge", source.resource_id, source.revision_id),
    )
    updated = replace(
        generation,
        credentials=(
            replace(
                generation.credentials[0],
                grants=(
                    *generation.credentials[0].grants,
                    StaticGrant(member, GrantSource.SERVICE_ONLY),
                ),
            ),
            *generation.credentials[1:],
        ),
    )
    f.reader._generation_provider = lambda: updated
    f.current[0] = policy
    f.bound_policy, f.source, f.current_generation = policy, source, updated
    f.event = next(iter(events))
    f.req = PlanningRequest(
        target=policy.target, idempotency_key=event_key(work, f.event)
    )
    return f


def test_bound_service_prepares_once_without_borrowing_human_grants(bound, tmp_path):
    f = bound
    first = f.registry.prepare(f.context, f.event, f.req, f.record)
    assert first["admission"]["ready"]
    assert f.registry.prepare(f.context, f.event, f.req, f.record) == first
    path = tmp_path / "policy.json"
    path.write_text(f.bound_policy.model_dump_json())
    path.chmod(0o600)
    assert ServicePlanningPolicy.load(path) == f.bound_policy
    # Legacy serialization and digest are not expanded with optional v2 fields.
    assert "sourceBindingDigest" not in f.policy.model_dump()
    path.write_text(f.policy.model_dump_json())
    assert ServicePlanningPolicy.load(path).digest == f.policy.digest
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )
    # Human provenance cannot replace the service's current source READ.
    f.reader._generation_provider = lambda: f.generation
    with pytest.raises(AuthorityError, match="SOURCE_READ_REQUIRED"):
        f.registry.prepare(f.context, f.event, f.req, f.record)


@pytest.mark.parametrize("change", ["binding", "target", "schedule", "head", "source"])
def test_changed_source_or_bound_target_cannot_prepare(bound, change):
    f = bound
    if change == "binding":
        f.current[0] = f.bound_policy.model_copy(
            update={"sourceBindingDigest": "f" * 64}
        )
    elif change == "target":
        f.current[0] = f.bound_policy.model_copy(
            update={
                "target": f.bound_policy.target.model_copy(
                    update={"expected_problem_version": 999}
                )
            }
        )
    elif change == "schedule":
        f.current[0] = f.bound_policy.model_copy(
            update={
                "eventWindows": {
                    f.event: (
                        f.now - timedelta(seconds=1),
                        f.now + timedelta(seconds=1),
                    )
                }
            }
        )
    else:
        with f.repository.pool.connection() as c, c.transaction():
            if change == "head":
                c.execute(
                    "UPDATE fixed_work_authoring.heads "
                    "SET head_revision_id='revision:1'"
                )
            else:
                c.execute(
                    "UPDATE knowledge_operation.knowledge "
                    "SET record=jsonb_set(record,'{archived}','true'::jsonb)"
                )
    from agent_console.plan_suggestion_domain import PlanningError

    # _check is also the guard used in budget/continuation transactions.
    with (
        pytest.raises((AuthorityError, PlanningError)),
        f.repository.pool.connection() as c,
        c.transaction(),
    ):
        c.row_factory = dict_row
        f.registry._check(c, f.context, f.current[0])
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 0
        )


def test_composition_verifier_and_readiness_are_read_only(bound, tmp_path, monkeypatch):
    """Real verifier/current-grant/PG; lifecycle composition port is controlled."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    import agent_console.fixed_work_bound_composition as composition

    f = bound
    generation = replace(
        f.current_generation,
        credentials=(
            replace(
                f.current_generation.credentials[0],
                credential_sha256=sha256(b"isolated-secret").hexdigest(),
            ),
            *f.current_generation.credentials[1:],
        ),
    )
    f.reader._generation_provider = lambda: generation

    @contextmanager
    def protected():
        yield generation

    controller = SimpleNamespace(
        protected_request=protected,
        readiness=SimpleNamespace(
            recovery_epoch=1, database_fingerprint="isolated-fixed-db"
        ),
    )
    foundation = SimpleNamespace(
        generation_controller=controller,
        repository=f.authority,
        grants=SimpleNamespace(authorization=f.reader),
    )
    policy = tmp_path / "bound.json"
    policy.write_text(f.bound_policy.model_dump_json())
    policy.chmod(0o600)
    calls = []

    def factory(context):
        calls.append(context)
        return None

    # Explicitly test the production identity/transaction wrapper, not a fake
    # successful execution or a second model invocation.
    def existing_port(**kw):
        return SimpleNamespace(
            enabled=True,
            current_context=kw["current_context"],
            call_scope=kw["authorized_call_scope"],
            host=SimpleNamespace(runtime=SimpleNamespace(registry=f.registry)),
        )

    monkeypatch.setattr(composition, "compose_cycle_service", existing_port)
    args = dict(
        foundation=foundation,
        planning_factory=factory,
        readonly_owner=None,
        policy_path=policy,
        enabled=True,
    )
    with pytest.raises(AuthorityError, match="AUTHENTICATION_REQUIRED"):
        composition.compose_bound_cycle_service(
            **args, credential_reader=lambda: "wrong"
        )
    assert not calls
    loop = composition.compose_bound_cycle_service(
        **args, credential_reader=lambda: "isolated-secret"
    )
    assert calls == [f.context]
    status = composition.inspect_bound_cycle(loop)
    assert status["executionStartedByObservation"] is False
    assert status["dueEventCount"] == 1
    assert status["humanAnswerDelegation"] == "NOT_CONFIGURED"
    with loop.call_scope(f.context) as call:
        assert call.context == f.context
        assert (
            call.connection.execute("SELECT current_database() db")
            .fetchone()["db"]
            .startswith("planning323_")
        )
    with f.repository.pool.connection() as c:
        c.row_factory = dict_row
        assert (
            c.execute(
                "SELECT count(*) n FROM fixed_work_service.planning_preparations"
            ).fetchone()["n"]
            == 0
        )
        assert (
            c.execute(
                "SELECT count(*) n FROM draft_provider_budget.reservations"
            ).fetchone()["n"]
            == 0
        )


@pytest.mark.parametrize("mode", ["bound_once", "budget_full"])
def test_bound_original_model_owner_and_budget(bound, mode):
    from test_fixed_work_service_admission_postgres import (
        test_normal_planning_claim_proposal_original_budget_and_replay as run,
    )

    run(bound, mode, first_event=bound.event)


def test_bound_service_keeps_exact_source_after_later_publication(bound):
    from copy import deepcopy

    f = bound
    with f.repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        record = c.execute(
            "SELECT record FROM knowledge_operation.knowledge WHERE knowledge_id=%s",
            (f.source.resource_id,),
        ).fetchone()["record"]
        old = next(
            r for r in record["revisions"] if r["revisionId"] == f.source.revision_id
        )
        record.setdefault("facts", []).append(
            {
                "event": "KNOWLEDGE_PUBLISHED",
                "revisionId": old["revisionId"],
                "digest": old["digest"],
                "actor": "explicit-isolated-publication-fixture",
            }
        )
        later = deepcopy(old)
        later.update(revisionId="isolated-later-publication", digest="c" * 64)
        record["revisions"].append(later)
        record["publishedRevisionId"] = later["revisionId"]
        c.execute(
            "UPDATE knowledge_operation.knowledge SET record=%s WHERE knowledge_id=%s",
            (Jsonb(record), f.source.resource_id),
        )
    first = f.registry.prepare(f.context, f.event, f.req, f.record)
    assert first["admission"]["ready"]
    assert f.registry.prepare(f.context, f.event, f.req, f.record) == first
    assert f.source.revision_id == "r"
