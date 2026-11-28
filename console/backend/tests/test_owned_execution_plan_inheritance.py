# ruff: noqa: F401,F811 -- Original isolated fixture registration.
"""Real approved execution lineage, not arbitrary approved/latest Plans."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
import test_owned_resource_assembly_chain as chain
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_business_resource_adapter import (
    derive_work,
    require_plan,
    require_reference,
)
from agent_console.owned_resource_assembly import project
from agent_console.plan_suggestion_domain import ConfirmedPlanRevision
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from owned_business_consumer_support import prepare_current_resource_reads
from test_conversation_experience_admission import pytestmark as pgmark
from test_owned_resource_assembly_chain import (
    adopted,
    cleanup_consumer_resources,
    configure_scope,
    env,
    ordinary,
    owned_created,
    owned_ready,
    prepare_source,
    publish_new_role,
    routed,
    setup,
)

EXERCISE_NAME = (
    "test_ordinary_selected_new_role_reaches_prepared_native_host_"
    "without_policy_rewrite"
)
exercise = getattr(chain, EXERCISE_NAME)

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode=None,
                prepare_source=prepare_source,
                configure_scope=configure_scope,
            )
        ],
        indirect=True,
    ),
]


@pytest.mark.parametrize("unknown", [False, True])
def test_approved_execution_plan_keeps_fixed_tuple_and_next_selection_is_explicit(
    owned_created, tmp_path, request, monkeypatch, unknown
):
    e = owned_created
    if unknown:
        e.assembly_case = "UNKNOWN"
    observed_next = {}

    def after(observed, work, native, preparation, receipt):
        automation, adapter, _, generation, _ = e.consumer_preparation_context
        executed = ConfirmedPlanRevision.model_validate(
            receipt["executionPlan"]["plan"]
        )
        selected = observed["successor"]
        assert executed.version == selected.version + 1
        with native.pool.connection() as c:
            before = c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            commands = c.execute(
                "SELECT count(*) n FROM execution_authority.native_dispatch_commands"
            ).fetchone()["n"]
            base = e.business_owner.work_reader.work(
                c, e.context, executed.semantics.target.problem
            )
            inherited = derive_work(
                e.business_owner,
                c,
                e.context,
                executed.semantics.target.problem,
                plan=executed,
            )
            assert inherited.assemblyAdoption["sourcePlan"]["digest"] == selected.digest
            assert inherited.assemblyAdoption["plan"]["digest"] == executed.digest
            assert inherited.businessScope.employees == (observed["new_employee"],)
            require_plan(inherited, executed)
            old = derive_work(
                e.business_owner,
                c,
                e.context,
                executed.semantics.target.problem,
                plan=observed["original_plan"],
            )
            assert old.assemblyAdoption is None
            with pytest.raises(AuthorityError, match="RESOURCE_NOT_AUTHORIZED"):
                require_reference(old, "employee", observed["new_employee"])
            row = c.execute(
                "SELECT command_key,result FROM "
                "execution_authority.prepared_resource_commands "
                "WHERE result->>'preparationDigest'=%s",
                (preparation.digest,),
            ).fetchone()

            class FaultRead:
                def __init__(self, value):
                    self.value = value

                def execute(self, query, args=None):
                    if query.startswith(
                        "SELECT command_key,result FROM "
                        "execution_authority.prepared_resource_commands"
                    ):
                        return NS(fetchall=lambda: [self.value])
                    return c.execute(query, args)

                def __getattr__(self, name):
                    return getattr(c, name)

            for damage in (
                "assembly",
                "source",
                "approval",
                "semantics",
                "mapping",
                "run",
            ):
                fake = deepcopy(row)
                result = fake["result"]
                if damage == "assembly":
                    result["ownedBusiness"]["assemblyAdoption"]["digest"] = "0" * 64
                elif damage == "source":
                    result["sourcePlanDigest"] = "0" * 64
                elif damage == "approval":
                    result["executionPlan"]["approval"]["decision"] = "REJECT"
                elif damage == "semantics":
                    result["executionPlan"]["plan"]["semantics"]["title"] += " altered"
                elif damage == "mapping":
                    result["instanceBinding"]["mappingDigest"] = "0" * 64
                else:
                    result["runId"] = "workflow-run:unrelated"
                with pytest.raises(AuthorityError, match="OWNED_ASSEMBLY_"):
                    project(
                        e.business_owner.work_reader,
                        FaultRead(fake),
                        e.context,
                        base,
                        executed,
                    )
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == before
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM "
                    "execution_authority.native_dispatch_commands"
                ).fetchone()["n"]
                == commands
            )

        # Create another genuine published same-contract role, outside the old
        # static tuple arrays, then use the existing normal bounded READ owner.
        from datetime import timedelta

        from agent_console.test_resource_read_access import prepare
        from agent_console.test_resource_read_policy import TestReadPolicy
        from agent_console.workbench_prepared_resources import reference

        with e.repo.connection_scope() as c:
            agent2, employee2 = publish_new_role(e, c, suffix="-second")
        policy = TestReadPolicy(
            schemaVersion="test-resource-read-policy.v1",
            policyId="same-scope-next-selection-read",
            policyVersion="1",
            enabled=True,
            tenant=e.context.scope.tenant_id,
            securityDomain=e.context.scope.security_domain,
            subjects=(e.context.principal_id,),
            issuer=automation.policy.issuer,
            credentialPath=automation.policy.credentialPath,
            expiresAt=automation.grants.clock() + timedelta(minutes=10),
            grantTTLSeconds=120,
            targets=[
                dict(
                    owner="AGENT",
                    action="READ_RESOURCE",
                    resource=reference("agent", agent2.resource_id, agent2.revision_id),
                    digest=agent2.digest,
                    purpose="RESOURCE_PREPARATION",
                ),
                dict(
                    owner="EMPLOYEE",
                    action="READ",
                    resource=f"employee:{employee2.resource_id}:{employee2.revision_id}",
                    digest=employee2.digest,
                    purpose="RESOURCE_PREPARATION",
                ),
            ],
        )
        with e.repo.connection_scope() as c:
            grants = prepare(policy, automation.grants, e.context, c, "next-role-read")
            assert len(grants["items"]) == 2
        body = dict(
            version=executed.version,
            digest=executed.digest,
            expectedProposalRevision=executed.source_proposal_revision,
            employee=employee2.model_dump(mode="json"),
            idempotencyKey="explicit-next-after-execution",
        )
        with e.repo.connection_scope() as c:
            call = AuthorizedOwnerCall(
                "SELECT_POLICY_EMPLOYEE_RESOURCES",
                e.context,
                c,
                body,
                {"proposal_id": executed.plan_id},
                {},
                (),
                AuthorizedOwnerAuthority(adapter, e.context, c, generation, ()),
                generation,
                1,
            )
            if unknown:
                with pytest.raises(AuthorityError, match="PRIOR_EXECUTION_UNRESOLVED"):
                    automation.select_employee(call)
                assert (
                    c.execute(
                        "SELECT count(*) n FROM "
                        "execution_authority.resource_policy_plan_commands"
                    ).fetchone()["n"]
                    == 1
                )
            else:
                result = automation.select_employee(call)
                assert automation.select_employee(call) == result
                next_plan = ConfirmedPlanRevision.model_validate(
                    result["confirmation"]["plan"]
                )
                assert next_plan.version == executed.version + 1
                assert next_plan.predecessor_digest == executed.digest
                assert result["assemblyAdoption"]["body"][
                    "employee"
                ] == employee2.model_dump(mode="json")
                assert next_plan.semantics.target == executed.semantics.target
                assert next_plan.semantics.tasks == executed.semantics.tasks
                assert result["modelCalls"] == result["newRuns"] == 0
                assert result["executionStarted"] is False
                again = derive_work(
                    e.business_owner,
                    c,
                    e.context,
                    executed.semantics.target.problem,
                    plan=executed,
                )
                assert again.businessScope.employees == (observed["new_employee"],)
                assert (
                    c.execute(
                        "SELECT count(*) n FROM execution_authority.workflow_runs"
                    ).fetchone()["n"]
                    == before
                )
                assert (
                    c.execute(
                        "SELECT count(*) n FROM "
                        "execution_authority.native_dispatch_commands"
                    ).fetchone()["n"]
                    == commands
                )
                observed_next["plan"] = next_plan
        observed_next["checked"] = True

    e.assembly_after_execution = after
    exercise(e, tmp_path, request, monkeypatch)
    assert observed_next["checked"]
    if not unknown:
        assert observed_next["plan"].version == 4
