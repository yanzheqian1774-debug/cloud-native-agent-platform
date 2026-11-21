# ruff: noqa: E501 -- Exact immutable-history fixture SQL.
"""Historical immutable row fixtures; no claim that 21 live cycles were executed."""

from copy import deepcopy
from datetime import timedelta

from agent_console.digital_employee_definition import digest
from agent_console.fixed_work_bound_policy import (
    BoundServicePlanningPolicy,
    ScheduleWindow,
    compile_windows,
)
from agent_console.fixed_work_service_admission import event_key
from agent_console.plan_suggestion_invocation import PlanningRequest
from psycopg.types.json import Jsonb


def seed_history(a):
    with a.authority.connection_scope() as c:
        original = c.execute(
            "SELECT * FROM fixed_work_service.planning_preparations LIMIT 1"
        ).fetchone()
        saved = c.execute(
            "SELECT record FROM fixed_work_authoring.revisions WHERE namespace=%s AND security_domain=%s AND work_id=%s AND revision_id=%s",
            (
                original["namespace"],
                original["security_domain"],
                original["work_id"],
                original["revision_id"],
            ),
        ).fetchone()
        old = BoundServicePlanningPolicy.model_validate(original["policy"])
        window = ScheduleWindow(
            notBefore=old.scheduleWindow.notBefore - timedelta(days=30),
            expiresAt=old.scheduleWindow.expiresAt,
            windowSeconds=old.scheduleWindow.windowSeconds,
        )
        events = compile_windows(old.work, saved["record"]["trigger"], window)
        policy = BoundServicePlanningPolicy.model_validate(
            {
                **old.model_dump(mode="json"),
                "scheduleWindow": window.model_dump(mode="json"),
                "allowedEventIds": list(events),
                "eventWindows": events,
            }
        )
        chosen = [e for e in events if e != original["event_id"]][-21:]
        assert len(chosen) == 21
        for event in chosen:
            row = deepcopy(original)
            row["event_id"] = event
            row["invocation_id"] = "historical-fixture:" + digest(event)
            row["record"]["target"]["invocation_id"] = row["invocation_id"]
            row["record"]["target_digest"] = digest(row["record"]["target"])
            row["record_digest"] = digest(row["record"])
            row["request_digest"] = digest(
                PlanningRequest(
                    target=policy.target,
                    policy=policy.planningPolicy,
                    idempotency_key=event_key(policy.work, event),
                ).model_dump(mode="json")
            )
            row["policy"] = policy.model_dump(mode="json")
            row["policy_digest"] = policy.digest
            columns = list(row)
            from psycopg import sql

            c.execute(
                sql.SQL(
                    "INSERT INTO fixed_work_service.planning_preparations ({}) VALUES ({})"
                ).format(
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.SQL(",").join(sql.Placeholder() for _ in columns),
                ),
                [
                    Jsonb(row[k]) if k in {"record", "context", "policy"} else row[k]
                    for k in columns
                ],
            )
