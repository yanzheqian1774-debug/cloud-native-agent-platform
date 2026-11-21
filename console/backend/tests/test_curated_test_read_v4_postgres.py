# ruff: noqa: F401,F811 -- Reuse isolated original owner fixture graph.
from types import SimpleNamespace

import pytest
import test_published_test_resources as original
from agent_console.test_resource_read_policy import CuratedPublishedTestReadPolicy
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from test_plan_suggestion_v2 import repository
from test_planning_candidates_source_change import case
from test_prepared_resource_owners import services
from test_published_test_resources import curated
from test_resource_automation import automation
from test_test_resource_read_access import read_policy


@pytest.fixture
def expanded(curated):
    a, g, context, old, refs, select, run = curated
    specs = [s.model_dump(mode="json") for s in old.publishedResources]
    service = a.services["skill"]
    scope = service.scope(context.scope.tenant_id, context.scope.security_domain)
    resource = service.repository.get(scope, "skill", refs["skill"].resource_id)
    content = resource["revisions"][0]["content"]
    for i in range(2):
        created = service.create(
            scope, "skill", context.principal_id, f"isolated curated extra {i}", content
        )
        rev = created["revisions"][0]
        with a.authority.connection_scope() as c:
            PreparedResourceOwner(a.services)(
                SimpleNamespace(
                    operation="REVIEW_PREPARED_RESOURCE",
                    context=context,
                    connection=c,
                    authority=SimpleNamespace(
                        require=lambda *args: SimpleNamespace(
                            decision_id="controlled-publication-port"
                        )
                    ),
                    path={
                        "kind": "skill",
                        "identity": created["resourceId"],
                        "revision": rev["revisionId"],
                    },
                    payload={
                        "expectedVersion": created["aggregateVersion"],
                        "digest": rev["digest"],
                        "reason": "Controlled authority; no actual Human review",
                        "idempotencyKey": f"v4-publish-{i}",
                    },
                )
            )
        specs.append(
            dict(
                kind="skill",
                logicalId=created["resourceId"],
                anchorRevision=rev["revisionId"],
                anchorDigest=rev["digest"],
                purpose="RESOURCE_PREPARATION",
            )
        )
    policy = CuratedPublishedTestReadPolicy.model_validate(
        old.model_dump(mode="json")
        | {"schemaVersion": "test-resource-read-policy.v4", "publishedResources": specs}
    )

    def selection(candidate=policy, subject=context):
        return select(candidate, subject)

    def prepare(selected=None, key=None, candidate=policy, subject=context):
        return run(selected, key, candidate, subject)

    return a, g, context, policy, refs, selection, prepare


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_v4_four_curated_objects_original_prepare_and_replay(expanded):
    _, _, _, _, _, selection, run = expanded
    current = selection()
    assert len(current.targets) == 4
    outcome = run(current)
    assert run(current) == outcome
    assert all(t.action in {"READ", "READ_RESOURCE"} for t in current.targets)
    assert all(x["state"] in {"APPROVED", "EFFECTIVE"} for x in outcome["items"])
    original.test_real_published_owners_exact_read_replay_and_cross_scope(expanded)


@pytest.mark.parametrize("automation", ["existing"], indirect=True)
def test_v4_published_descendant_and_revocation_keep_original_gates(expanded):
    original.test_real_draft_is_not_selected_then_publication_invalidates_old_key(
        expanded
    )
    original.test_real_lineage_revocation_and_selection_key_are_not_bypassed(expanded)
