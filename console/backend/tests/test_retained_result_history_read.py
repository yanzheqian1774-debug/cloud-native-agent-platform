"""Real scoped owners; progress fixture is controlled, no Native/model dispatch."""
# ruff: noqa: E501,F401,F811 -- Reuse disposable database fixture registration.

import pytest
from agent_console.conversation_work_history import result_read_targets
from agent_console.execution_domain import ScopeIdentity
from agent_console.workbench_bff import PREFIX
from agent_console.workbench_prepared_execution import candidate
from psycopg.types.json import Jsonb
from test_conversation_work_history import snapshot
from test_owned_business_consumer_chain import (
    adopted,
    cleanup_consumer_resources,
    env,
    ordinary,
    owned_created,
    owned_ready,
    pytestmark,
    routed,
    setup,
)
from test_owned_business_consumer_chain import (
    test_same_owned_problem_confirms_prepares_and_worker_reads as exercise,
)


@pytest.mark.parametrize("blocked", [None, "REVOKED", "DENIED", "NO_PRIOR_READ"])
def test_saved_result_reads_renew_only_prior_currently_allowed_rights(
    owned_created, tmp_path, request, monkeypatch, blocked
):
    import owned_business_consumer_support as support

    e = owned_created
    original = support.resource_automation

    def automation(*args, **kwargs):
        result = original(*args, **kwargs)
        e.history_automation = result[0]
        return result

    monkeypatch.setattr(support, "resource_automation", automation)

    def observe(worker, repository, receipt, ready):
        scope = (e.context.scope.tenant_id, e.context.scope.security_domain)
        with e.repo.connection_scope() as c:
            p = candidate(c, ScopeIdentity(*scope), receipt["preparationDigest"])
            # Stored queued execution exists. Controlled recorded-attempt fixture:
            # no actual tool/provider effect or fabricated successful artifact.
            row = c.execute(
                "SELECT record FROM execution_authority.prepared_run_progress "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (*scope, p.run_id),
            ).fetchone()["record"]
            for task in row["tasks"]:
                task["attempt_ordinal"] = 1
            c.execute(
                "UPDATE execution_authority.prepared_run_progress SET record=%s "
                "WHERE namespace=%s AND security_domain=%s AND workflow_run_id=%s",
                (Jsonb(row), *scope, p.run_id),
            )
            expected = result_read_targets(c, p)
            assert {
                "EVIDENCE",
                "RESOURCE_USE",
                "EVALUATION",
                "SUCCESS_CRITERION",
                "SUCCESS_CRITERIA_SET",
            } <= {g.owner for g in expected}
            # Use actual saved revision identity, not any client-created target.
            target = p.semantics.target.problem
            c.execute(
                "INSERT INTO private_conversation.links "
                "(tenant_id,security_domain,conversation_id,link_id,target,created_by,request_key,request_digest) "
                "VALUES(%s,%s,%s,'result-history',%s,%s,'result-history','fixture')",
                (
                    *scope,
                    e.conv,
                    Jsonb(
                        dict(
                            problemId=target.resource_id,
                            revisionId=target.revision_id,
                            problemDigest=target.digest,
                        )
                    ),
                    e.context.principal_id,
                ),
            )
            c.execute(
                "UPDATE private_conversation.journeys SET state=%s WHERE conversation_id=%s",
                (
                    Jsonb(
                        dict(
                            problem=dict(
                                business_problem_id=target.resource_id,
                                revision_id=target.revision_id,
                                digest=target.digest,
                            ),
                            execution=p.digest,
                        )
                    ),
                    e.conv,
                ),
            )
            for grant in expected:
                c.execute(
                    "UPDATE authorization_admin.grants SET not_before=now()-interval '2 hours',"
                    "expires_at=now()-interval '1 hour' WHERE subject_principal_id=%s "
                    "AND owner=%s AND action=%s AND exact_resource=%s",
                    (
                        e.context.principal_id,
                        grant.owner,
                        grant.action,
                        grant.exact_resource,
                    ),
                )
            denied = next(g for g in expected if g.owner == "EVALUATION")
            prior = c.execute(
                "SELECT grant_id,request_id FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s AND owner=%s AND action=%s AND exact_resource=%s",
                (
                    e.context.principal_id,
                    denied.owner,
                    denied.action,
                    denied.exact_resource,
                ),
            ).fetchall()
            assert prior
            if blocked == "NO_PRIOR_READ":
                c.execute(
                    "UPDATE authorization_admin.grants SET exact_resource=exact_resource||':unrelated' "
                    "WHERE grant_id=ANY(%s)",
                    ([r["grant_id"] for r in prior],),
                )
        if blocked == "DENIED":
            from agent_console.grant_administration_application import (
                GrantRequestCommand,
            )

            denied_request = e.history_automation.grants.submit_request(
                e.context,
                GrantRequestCommand(
                    "READONLY_WORK_EXECUTION", (denied,), "denied-history-read"
                ),
            )
            with e.repo.connection_scope() as c:
                c.execute(
                    "UPDATE authorization_admin.grant_requests SET state='REJECTED' WHERE request_id=%s",
                    (denied_request.request_id,),
                )
        if blocked == "REVOKED":
            from agent_console.grant_administration_application import (
                GrantRevocationCommand,
            )

            for r in prior:
                e.admission.delegation.grants.revoke_grant(
                    e.reviewer,
                    GrantRevocationCommand(
                        r["grant_id"],
                        "USER_REQUESTED",
                        "history-" + r["grant_id"],
                        True,
                    ),
                )
        # Same real requestability/target validator installed for actual preparation.
        monkeypatch.setattr(
            e.admission.delegation, "grants", e.history_automation.grants
        )
        before = snapshot(e)
        for _ in range(2):
            response = e.route_client.post(
                PREFIX + f"/conversations/{e.conv}/history-access",
                headers=e.route_headers,
                json={},
            )
            assert response.status_code == 200, response.text
            if blocked:
                assert blocked in {
                    i["state"] for i in response.json()["result"]["items"]
                }
        assert snapshot(e) == before
        with e.repo.connection_scope() as c:
            renewed = c.execute(
                "SELECT owner,action,exact_resource FROM authorization_admin.grants "
                "WHERE subject_principal_id=%s AND issuer_principal_id='policy:f3-conversation-history-read'",
                (e.context.principal_id,),
            ).fetchall()
            actual = {(r["owner"], r["action"], r["exact_resource"]) for r in renewed}
            wanted = {
                (g.owner, g.action, g.exact_resource)
                for g in expected
                if not blocked or g != denied
            }
            assert wanted <= actual
            if blocked:
                assert (
                    denied.owner,
                    denied.action,
                    denied.exact_resource,
                ) not in actual
            assert all(
                r["action"]
                in {
                    "READ",
                    "READ_RESOURCE",
                    "READ_REFERENCE",
                    "READ_DRAFT_ASSISTANCE_INVOCATION",
                }
                for r in renewed
            )
            assert len(renewed) == len(actual)
        assert len(e.calls) == e.business_model_call_count

    e.consumer_execution_observer = observe
    exercise(e, tmp_path, request)
