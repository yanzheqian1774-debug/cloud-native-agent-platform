# ruff: noqa: F401,F811 -- Original disposable owner fixture registration.
"""Real publication owners → exact A2 Plan → unchanged Native exact validator."""

import pytest
import test_owned_resource_assembly_chain as chain
from agent_console.execution_domain import ScopeIdentity
from agent_console.execution_preparation import ExecutionPreparationError
from agent_console.ontology_execution import validate_semantics
from agent_console.owned_business_resource_adapter import derive_work
from agent_console.owned_ontology_successor import marker
from owned_ontology_successor_setup import prepare_owned_source, publish
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
    routed,
    setup,
)

pytestmark = [
    pgmark,
    pytest.mark.parametrize("adopted", ["NEEDS_DATA"], indirect=True),
    pytest.mark.parametrize(
        "owned_ready",
        [
            dict(
                mode=None,
                prepare_source=prepare_owned_source,
                configure_scope=configure_scope,
            )
        ],
        indirect=True,
    ),
]


def test_real_independent_published_ontology_successor_reaches_exact_native(
    owned_created, tmp_path, request, monkeypatch
):
    import owned_business_consumer_support as support

    e = owned_created
    original = support.resource_automation

    def capture(*args, **kwargs):
        result = original(*args, **kwargs)
        e.a2_automation = result
        return result

    def publish_actual(e, c, *, suffix=""):
        assert not suffix
        automation, adapter = e.a2_automation
        return publish(e, c, automation, adapter, tmp_path)

    monkeypatch.setattr(support, "resource_automation", capture)
    monkeypatch.setattr(chain, "publish_new_role", publish_actual)

    def inspect(observed, worker, native, preparation, receipt):
        published = e.a2_published
        assert published["author"] != published["reviewer"]
        assert (
            published["ontology"].resource_id
            == e.business_owner.policy.scopes[0].documentRules.ontology.resource_id
        )
        assert (
            published["skill"].resource_id
            == e.business_owner.policy.scopes[0].skills[0].resource_id
        )
        assert preparation.business_semantics.ontology == published["ontology"]
        assert all(
            p.skill.reference == published["skill"] for p in preparation.participants
        )
        assert marker(published["ontology"]) in preparation.semantics.boundaries
        assert (
            marker(published["ontology"]) in observed["successor"].semantics.boundaries
        )
        assert (
            marker(published["ontology"])
            not in observed["original_plan"].semantics.boundaries
        )
        proof = observed["result"]["assemblyAdoption"]["body"]["ontologySuccessor"]
        assert proof["upgradeReceipt"]["command"] == "a2-reviewed-skill-and-employee"
        with native.pool.connection() as c:
            for participant in preparation.participants:
                validate_semantics(
                    c,
                    ScopeIdentity(preparation.namespace, preparation.security_domain),
                    preparation,
                    participant,
                )
                invalid = preparation.model_copy(
                    update={
                        "business_semantics": e.business_owner.policy.scopes[
                            0
                        ].documentRules
                    }
                )
                with pytest.raises(
                    ExecutionPreparationError,
                    match="ONTOLOGY_EXECUTOR_BINDING_MISMATCH",
                ):
                    validate_semantics(
                        c,
                        ScopeIdentity(
                            preparation.namespace, preparation.security_domain
                        ),
                        invalid,
                        participant,
                    )
            old = derive_work(
                e.business_owner,
                c,
                e.context,
                preparation.semantics.target.problem,
                plan=observed["original_plan"],
            )
            assert (
                old.businessScope.documentRules
                == e.business_owner.policy.scopes[0].documentRules
            )
            current = derive_work(
                e.business_owner,
                c,
                e.context,
                preparation.semantics.target.problem,
                plan=observed["successor"],
            )
            assert current.businessScope.documentRules.ontology == published["ontology"]
        from agent_console.plan_suggestion_domain import ConfirmedPlanRevision
        from agent_console.workbench_owner_authorization import (
            AuthorizedOwnerAuthority,
            AuthorizedOwnerCall,
        )

        next_employee = e.a2_publish_next_role()
        executed = ConfirmedPlanRevision.model_validate(
            receipt["executionPlan"]["plan"]
        )
        automation, adapter, _, generation, _ = e.consumer_preparation_context
        with e.repo.connection_scope() as c:
            before_runs = c.execute(
                "SELECT count(*) n FROM execution_authority.workflow_runs"
            ).fetchone()["n"]
            body = dict(
                version=executed.version,
                digest=executed.digest,
                expectedProposalRevision=executed.source_proposal_revision,
                employee=next_employee.model_dump(mode="json"),
                idempotencyKey="a2-use-already-adopted-ontology-for-new-role",
            )
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
            selected = automation.select_employee(call)
            next_plan = ConfirmedPlanRevision.model_validate(
                selected["confirmation"]["plan"]
            )
            assert next_plan.predecessor_digest == executed.digest
            proof = selected["assemblyAdoption"]["body"]
            assert proof["ontologyPredecessor"]["digest"] == executed.digest
            assert "ontologySuccessor" not in proof
            assert len(proof["ontologyPredecessorDigest"]) == 64
            next_work = derive_work(
                e.business_owner,
                c,
                e.context,
                preparation.semantics.target.problem,
                plan=next_plan,
            )
            assert next_work.businessScope.employees == (next_employee,)
            assert (
                next_work.businessScope.documentRules.ontology == published["ontology"]
            )
            assert (
                c.execute(
                    "SELECT count(*) n FROM execution_authority.workflow_runs"
                ).fetchone()["n"]
                == before_runs
            )
        e.a2_native_checked = True

    e.assembly_after_execution = inspect
    exercise_name = (
        "test_ordinary_selected_new_role_reaches_prepared_native_host_"
        "without_policy_rewrite"
    )
    exercise = getattr(chain, exercise_name)
    exercise(e, tmp_path, request, monkeypatch)
    assert e.a2_native_checked
