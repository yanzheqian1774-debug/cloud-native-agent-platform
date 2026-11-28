# ruff: noqa: F401,F811 -- Actual existing owner fixture chain.
"""Real v2 composition, controlled provider/Kubernetes and Human source setup."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import test_fixed_work_cycle_host_postgres as host_test
from agent_console import fixed_work_sources_postgres as sources
from agent_console.authority_configuration import StaticGrant
from agent_console.authority_contracts import ExactGrant, GrantSource
from agent_console.authority_foundation import ActivationBarrier
from agent_console.digital_employee_definition import digest
from agent_console.fixed_work_bound_composition import compose_bound_cycle_service
from agent_console.fixed_work_bound_policy import (
    BoundServicePlanningPolicy,
    ScheduleWindow,
    compile_windows,
)
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.planning_candidates import read_published
from agent_console.resource_automation_policy import source_digest
from agent_console.workbench_prepared_resources import reference
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_fixed_work_authoring import body
from test_fixed_work_cycle_host_postgres import automation, case, repository, services


def bound_schedule_fixture(anchor):
    """One clock capture for the HH:MM slot and its original lower boundary."""
    trigger = dict(
        kind="SCHEDULE",
        timezone="UTC",
        cadence="DAILY",
        localTime=(anchor - timedelta(minutes=1)).strftime("%H:%M"),
    )
    return trigger, anchor - timedelta(minutes=2)


@pytest.mark.parametrize(
    "automation", [{"resources": "existing", "continuation": True}], indirect=True
)
@pytest.mark.parametrize(
    "terminal", ["START_COMMITTED", "SUCCEEDED", "SOURCE_MISMATCH"]
)
def test_bound_original_plan_to_start_composition(
    automation, monkeypatch, tmp_path, terminal
):
    original = body()
    anchor = datetime.now(UTC)
    original["trigger"], not_before = bound_schedule_fixture(anchor)
    monkeypatch.setattr(host_test, "body", lambda: original)

    def setup(a, service, readonly, prior, saved, now):
        work = prior.work
        scope = a.e.scope.namespace, a.e.scope.security_domain
        with a.repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            sources.migrate(c)
            ref = a.refs["knowledge"]
            content, _ = read_published(c, a.e.scope, "KNOWLEDGE", ref)
            if terminal == "SOURCE_MISMATCH":
                # Real distinct published source A; normal Plan/readonly scope still
                # chooses original B. Identical bytes must not erase exact identity.
                ref = ref.model_copy(update={"resource_id": "bound-source-A"})
                c.execute(
                    "INSERT INTO knowledge_operation.knowledge "
                    "(namespace,security_domain,knowledge_id,aggregate_version,record) "
                    "VALUES(%s,%s,%s,1,%s)",
                    (
                        *scope,
                        ref.resource_id,
                        Jsonb(
                            dict(
                                name="Exact bound A",
                                publishedRevisionId=ref.revision_id,
                                archived=False,
                                revisions=[
                                    dict(
                                        revisionId=ref.revision_id,
                                        digest=ref.digest,
                                        state="PUBLISHED",
                                        content=content,
                                    )
                                ],
                            )
                        ),
                    ),
                )
                member = ExactGrant(
                    "KNOWLEDGE",
                    "READ_RESOURCE",
                    reference("knowledge", ref.resource_id, ref.revision_id),
                )
                a.gen = replace(
                    a.gen,
                    credentials=(
                        replace(
                            a.gen.credentials[0],
                            grants=(
                                *a.gen.credentials[0].grants,
                                StaticGrant(member, GrantSource.SERVICE_ONLY),
                            ),
                        ),
                        *a.gen.credentials[1:],
                    ),
                )
                a.adapter.authorization._generation_provider = lambda: a.gen
            # Earlier Human confirmation is an explicit immutable fixture. The
            # actual 0073 owner path is tested separately, not replaced in runtime.
            h = dict(
                work=work.model_dump(mode="json"),
                team=saved["record"]["team"],
                subjectId="human:source-author",
                conversationId="source-conversation",
                commandId="fixture-source",
                instructionDigest=digest(original["instruction"]),
                mode="TARGET_REVIEW_ONLY",
                executionEnabled=False,
            )
            handoff = sources.append(c, scope, "handoffs", h)
            bound = sources.append(
                c,
                scope,
                "bindings",
                {
                    **h,
                    "commandId": "fixture-confirm",
                    "handoffDigest": handoff["digest"],
                    "target": prior.target.model_dump(mode="json"),
                    "inputSource": dict(
                        source=ref.model_dump(mode="json"),
                        sourceContentDigest=source_digest(content),
                    ),
                },
            )
        window = ScheduleWindow(
            notBefore=not_before,
            expiresAt=prior.expiresAt,
            windowSeconds=600,
        )
        events = compile_windows(work, original["trigger"], window)
        policy = BoundServicePlanningPolicy.model_validate(
            {
                **prior.model_dump(mode="json"),
                "schemaVersion": "fixed-work-service-planning.v2",
                "sourceBindingDigest": bound["digest"],
                "scheduleWindow": window.model_dump(mode="json"),
                "allowedEventIds": list(events),
                "eventWindows": events,
            }
        )
        path = tmp_path / "bound-cycle.json"
        path.write_text(policy.model_dump_json())
        path.chmod(0o600)
        barrier = ActivationBarrier(a.gen)
        controller = SimpleNamespace(
            protected_request=barrier.read,
            readiness=SimpleNamespace(
                recovery_epoch=1, database_fingerprint="isolated-cycle-db"
            ),
        )
        foundation = SimpleNamespace(
            repository=a.authority,
            generation_controller=controller,
            grants=SimpleNamespace(authorization=a.adapter.authorization),
        )
        return compose_bound_cycle_service(
            foundation=foundation,
            planning_factory=lambda context: service,
            readonly_owner=readonly,
            policy_path=path,
            credential_reader=lambda: "unit-subject-secret",
            enabled=True,
            policy_plan_approval_enabled=True,
        )

    host_test.test_host_restarts_saved_event_through_existing_owners(
        automation,
        monkeypatch,
        "SUCCEEDED" if terminal == "SUCCEEDED" else "CANCELLED",
        bound_setup=setup,
        bound_rejected=terminal == "SOURCE_MISMATCH",
    )
