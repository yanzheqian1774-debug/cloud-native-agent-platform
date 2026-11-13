"""Exact prepared metadata fixture; canonical parser, no model/owner mutation."""

from types import SimpleNamespace as NS

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.conversation_work_history import targets
from agent_console.ontology_execution import (
    DocumentRuleExecutionPreparation,
    DocumentSemanticsBinding,
)
from test_execution_preparation import preparation


@pytest.mark.parametrize(
    "mutation",
    [
        None,
        "prepared_subject",
        "source_revision",
        "problem_revision",
        "context_subject",
        "revoked",
        "malformed_problem",
    ],
)
def test_prepared_targets_are_exact_read_only_and_source_bound(mutation):
    old = preparation()
    p = DocumentRuleExecutionPreparation.model_validate(
        {
            **old.model_dump(mode="json"),
            "schema_version": "execution-preparation.v3",
            "business_semantics": DocumentSemanticsBinding(
                ontology=old.source_snapshot,
                source=old.source_snapshot,
                mapping_code="interview",
                scope="interview",
            ).model_dump(mode="json"),
        }
    )
    scope = (p.namespace, p.security_domain)
    ref = p.semantics.target.problem
    problem = {
        "business_problem_id": ref.resource_id,
        "revision_id": ref.revision_id,
        "digest": ref.digest,
    }
    source = p.source_snapshot.model_dump(mode="json")
    if mutation == "source_revision":
        source["revision_id"] = "other"
    policy = NS(policy_digest="policy", document=NS(conversations=["conversation"]))
    service = NS(
        conversation_relation=object(),
        experience=policy,
        configuration={"exact": "config"},
    )
    context = NS(
        principal_id="ordinary", scope=NS(tenant_id=scope[0], security_domain=scope[1])
    )
    records = NS(scope=lambda _: scope)

    class Connection:
        def execute(self, sql, params=None):
            assert sql.startswith("SELECT"), "Target discovery may not write"
            one = None
            many = []
            if "to_regclass" in sql:
                one = {"present": True}
            elif "private_conversation.journeys" in sql:
                one = {
                    "state": {
                        "problem": "malformed"
                        if mutation == "malformed_problem"
                        else problem,
                        "execution": p.digest,
                    }
                }
            elif "private_conversation.links" in sql:
                many = [
                    {
                        "target": {
                            "problemId": ref.resource_id,
                            "revisionId": ref.revision_id,
                            "problemDigest": ref.digest,
                        }
                    }
                ]
            elif "context_call_objects" in sql:
                one = {"context_id": "original", "invocation_id": "bound"}
            elif "context_call_requests" in sql:
                one = {
                    "context_id": "original",
                    "tenant_id": scope[0],
                    "security_domain": scope[1],
                    "subject_id": "other"
                    if mutation == "context_subject"
                    else "ordinary",
                    "record": {
                        "conversation_id": "conversation",
                        "experience_policy_digest": "policy",
                        "configuration": service.configuration,
                    },
                }
            elif "context_call_revocations" in sql:
                one = {"revoked": True} if mutation == "revoked" else None
            elif "invocation_versions" in sql:
                one = {
                    "record": {
                        "contextId": "original",
                        "initiatingPrincipalId": "ordinary",
                        "state": "SUCCEEDED",
                        "resultKind": "DRAFT_READY",
                        "inputSource": {"source": source},
                    }
                }
            elif "business_problem_authority.problems" in sql:
                one = {
                    "owner_id": "ordinary",
                    "current_revision_id": "other"
                    if mutation == "problem_revision"
                    else ref.revision_id,
                    "digest": ref.digest,
                }
            elif "SELECT prepared_by" in sql:
                one = {
                    "prepared_by": "other"
                    if mutation == "prepared_subject"
                    else "ordinary"
                }
            elif "SELECT record FROM execution_authority.prepared_candidates" in sql:
                one = {"record": p.model_dump(mode="json")}
            elif "pg_advisory_xact_lock" not in sql:
                pytest.fail(sql)
            return NS(fetchone=lambda: one, fetchall=lambda: many)

    if mutation:
        with pytest.raises(AuthorityError):
            targets(service, records, Connection(), context, "conversation")
    else:
        grants = targets(service, records, Connection(), context, "conversation")
        assert {g.owner for g in grants} == {
            "BUSINESS_PROBLEM",
            "EXECUTION",
            "KNOWLEDGE",
            "RUNTIME_PROFILE",
            "BUSINESS_ONTOLOGY",
        }
        assert all(g.action in {"READ", "READ_RESOURCE"} for g in grants)
        assert next(
            g for g in grants if g.owner == "EXECUTION"
        ).exact_resource.endswith(p.digest)
        assert next(
            g for g in grants if g.owner == "KNOWLEDGE"
        ).exact_resource.endswith(source["resource_id"] + ":" + source["revision_id"])
