"""A second real planning/confirmation/preparation, never copied run records."""

from agent_console.plan_suggestion_domain import ProposalRevision
from agent_console.policy_plan_confirmation import PolicyPlanConfirmation
from agent_console.workbench_owner_authorization import (
    AuthorizedOwnerAuthority,
    AuthorizedOwnerCall,
)
from owned_business_planning_support import (
    document_semantics,
    governed_planning_service,
)


def prepare_second(e):
    automation, adapter, continuation, generation, _prior_version = (
        e.consumer_preparation_context
    )
    semantics = document_semantics(e, e.consumer_planning_input["target"])
    with governed_planning_service(e, semantics) as (
        service,
        principal,
        request,
        provider,
    ):
        request = request.model_copy(
            update={"idempotency_key": "second-independent-prep"}
        )
        result = service.begin(principal, request)
        assert result["result"]["technical_status"] == "SUCCEEDED", result
        proposal = ProposalRevision.model_validate(result["result"]["proposal"])
        assert provider.calls == 1

    def invoke(handler, operation, payload):
        with e.repo.connection_scope() as c:
            return handler(
                AuthorizedOwnerCall(
                    operation,
                    e.context,
                    c,
                    payload,
                    {"proposal_id": proposal.proposal_id},
                    {},
                    (),
                    AuthorizedOwnerAuthority(adapter, e.context, c, generation, ()),
                    generation,
                    1,
                )
            )

    confirmed = invoke(
        PolicyPlanConfirmation(automation),
        "CONFIRM_POLICY_PLAN",
        {
            "problem": proposal.semantics.target.problem.model_dump(mode="json"),
            "revision": proposal.revision,
            "digest": proposal.digest,
            "expectedPlanVersion": 0,
            "idempotencyKey": "second-independent-confirm",
        },
    )
    version = confirmed["confirmation"]["plan"]["version"]
    assert version == 1
    assert proposal.proposal_id != e.consumer_proposal["proposal_id"]
    ready = invoke(
        automation,
        "PREPARE_RESOURCE_AUTOMATION",
        {"version": version, "idempotencyKey": "second-independent-prepare"},
    )
    assert ready["state"] == "READY", ready
    value = invoke(continuation, "CONTINUE_READONLY_WORK", {"version": version})
    e.consumer_expected_run_count = 2
    return value["receipt"]
