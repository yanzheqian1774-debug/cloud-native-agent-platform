# ruff: noqa: F401,F811 -- Isolated PostgreSQL fixtures.
"""Actual published skill/ontology owners; controlled grant boundary, no model."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError, AuthorityScope
from agent_console.automatic_document_inputs import resolve
from agent_console.automatic_skill_testing import verify_skill
from agent_console.native_document_resource_bundle import resource_content
from agent_console.native_document_skill import NativeRuleDocumentSkillExecutor
from agent_console.ontology_execution import DocumentSemanticsBinding
from agent_console.ontology_postgres import migrate
from agent_console.ontology_service import OntologyService
from agent_console.plan_suggestion_domain import ExactReference
from agent_console.readonly_continuation_policy import (
    ReadonlyContinuationPolicy,
    ReadonlyWork,
)
from agent_console.resource_automation_policy import WorkScope, source_digest
from agent_console.workbench_prepared_resources import PreparedResourceOwner
from psycopg.rows import dict_row
from test_document_rule_owner import SOURCE, rules
from test_ontology_lifecycle import ExactOntologyTestAuthority
from test_plan_suggestion_v2 import repository
from test_prepared_resource_owners import services


@pytest.fixture(params=[False, True], ids=["ordinary", "published-rules-v4"])
def documents(repository, services, request):
    scope = AuthorityScope("document-input-fixture", "isolated")
    context = SimpleNamespace(principal_id="human:reader", scope=scope)
    bundle = resource_content(SOURCE, rule_bound=request.param)
    refs, records = {}, {}
    for kind in ("skill", "knowledge"):
        service = services[kind]
        rs = service.scope(scope.tenant_id, scope.security_domain)
        args = (
            (rs, "skill", "human:author") if kind == "skill" else (rs, "human:author")
        )
        created = service.create(*args, "Isolated document", bundle[kind])
        if kind == "knowledge":
            created = created["knowledge"]
        identity = created["resourceId" if kind == "skill" else "knowledgeId"]
        rev = created["revisions"][0]
        with repository.pool.connection() as c, c.transaction():
            c.row_factory = dict_row
            PreparedResourceOwner(services)(
                SimpleNamespace(
                    operation="REVIEW_PREPARED_RESOURCE",
                    connection=c,
                    context=SimpleNamespace(principal_id="human:reviewer", scope=scope),
                    authority=SimpleNamespace(
                        require=lambda *a: SimpleNamespace(decision_id="fixture-only")
                    ),
                    path={
                        "kind": kind,
                        "identity": identity,
                        "revision": rev["revisionId"],
                    },
                    payload={
                        "expectedVersion": 1,
                        "digest": rev["digest"],
                        "reason": "Isolated fixture, not real human acceptance",
                        "idempotencyKey": "fixture-" + kind,
                    },
                )
            )
        refs[kind] = ExactReference(
            resource_id=identity,
            revision_id=rev["revisionId"],
            digest=rev["digest"].removeprefix("sha256:"),
        )
        records[kind] = (
            service.repository.get(rs, "skill", identity)
            if kind == "skill"
            else service.repository.get(rs, identity)
        )
    content = rules(
        reference=refs["knowledge"].model_dump(mode="json"),
        skill=refs["skill"].model_dump(mode="json"),
    )
    if request.param:
        rev = NativeRuleDocumentSkillExecutor.revision
        action = content.actions[0].model_copy(
            update={
                "executor_id": rev.executor_id,
                "executor_revision": rev.executor_revision,
                "executor_digest": rev.configuration_digest,
            }
        )
        content = content.model_copy(update={"actions": (action,)})
    with repository.pool.connection() as c, c.transaction():
        migrate(c)
    digest = None
    for version, op in enumerate(("CREATE", "VALIDATE", "TEST", "REVIEW", "PUBLISH")):
        with repository.pool.connection() as c, c.transaction():
            owner = OntologyService(
                SimpleNamespace(
                    connection=c,
                    context=SimpleNamespace(
                        principal_id="human:reviewer"
                        if version >= 3
                        else "human:author",
                        scope=scope,
                    ),
                    authority=ExactOntologyTestAuthority(),
                )
            )
            result = owner.handle(
                op,
                "rules",
                {
                    "request_key": op,
                    "expected_version": version,
                    "revision_id": "r1",
                    "digest": digest,
                    "content": content.model_dump(mode="json")
                    if version == 0
                    else None,
                    "reason": "Isolated setup",
                },
            )
            if version == 0:
                digest = result["digest"]
    binding = DocumentSemanticsBinding(
        ontology=ExactReference(resource_id="rules", revision_id="r1", digest=digest),
        mapping_code="interview",
        source=refs["knowledge"],
        scope="interview",
    )
    now = datetime.now(UTC)
    work = WorkScope(
        namespace=scope.tenant_id,
        securityDomain=scope.security_domain,
        subject=context.principal_id,
        problem=ExactReference(resource_id="problem", revision_id="1", digest="a" * 64),
        sourceContentDigests=(
            source_digest(records["knowledge"]["revisions"][0]["content"]),
        ),
        expiresAt=now + timedelta(hours=1),
    )
    approved = ReadonlyWork(
        **work.model_dump(),
        case="document",
        nativeAgentName="native",
        documentRules=binding,
    )
    policy = ReadonlyContinuationPolicy(
        policyId="isolated", policyVersion="1", enabled=True, works=(approved,)
    )
    events = []

    def decide(call, grants, key, work, issuer):
        events.append(("decide", grants))
        return SimpleNamespace(decision_id="isolated-read-decision")

    def require(call, grants):
        events.append(("require", grants))

    automation = SimpleNamespace(
        continuation=SimpleNamespace(policy=policy),
        grants=SimpleNamespace(clock=lambda: now),
        decide=decide,
        proof_grants=require,
    )
    yield SimpleNamespace(
        repository=repository,
        services=services,
        context=context,
        work=work,
        automation=automation,
        refs=refs,
        records=records,
        rule_bound=request.param,
        events=events,
    )


def run_test(d, *, load=True):
    with d.repository.pool.connection() as c, c.transaction():
        c.row_factory = dict_row
        call = SimpleNamespace(connection=c, context=d.context)

        def loader():
            return resolve(
                d.automation,
                call,
                d.work,
                "isolated-issuer",
                "test-key",
                d.refs["knowledge"],
                d.records["knowledge"]["revisions"][0],
            )

        return verify_skill(
            call,
            d.services["skill"],
            d.refs["skill"],
            d.refs["knowledge"],
            d.records["knowledge"]["revisions"][0],
            SimpleNamespace(
                issuer="isolated-issuer", decision_id="isolated-skill-read"
            ),
            persist=False,
            document_inputs=loader if load else None,
        )


def test_actual_published_document_test_contract_and_no_owner_rewrite(documents):
    d = documents
    result = run_test(d)
    assert result["passed"] and result["modelCalls"] == 0
    assert result["ownerTestRecordsWritten"] is False
    assert all(
        t["status"] == "PASSED" and t["actualExecution"] for t in result["tests"]
    )
    assert len(result["tests"]) == 4
    assert all(
        t["verificationContext"]["nativeDecisionValidation"]
        == "NOT_RUN_REQUIRES_NATIVE_ATTEMPT"
        for t in result["tests"]
    )
    assert [x[0] for x in d.events] == (["decide", "require"] if d.rule_bound else [])
    if d.rule_bound:
        assert d.events[0][1][0].owner == "BUSINESS_ONTOLOGY"
        assert d.events[0][1][0].action == "READ"
        assert all(
            t["verificationContext"]["documentRules"]["source"]
            == d.refs["knowledge"].model_dump(mode="json")
            for t in result["tests"]
        )
    service = d.services["skill"]
    assert (
        service.repository.get(
            service.scope(d.context.scope.tenant_id, d.context.scope.security_domain),
            "skill",
            d.refs["skill"].resource_id,
        )
        == d.records["skill"]
    )


@pytest.mark.parametrize("documents", [True], indirect=True)
@pytest.mark.parametrize(
    "invalid", ["missing", "source", "subject", "expired", "denied"]
)
def test_rule_inputs_fail_closed_without_actual_test(documents, invalid, monkeypatch):
    d = documents
    policy = d.automation.continuation.policy
    work = policy.works[0]
    if invalid == "source":
        work = work.model_copy(
            update={
                "documentRules": work.documentRules.model_copy(
                    update={"source": d.refs["skill"]}
                )
            }
        )
    if invalid == "subject":
        work = work.model_copy(update={"subject": "human:other"})
    if invalid == "expired":
        work = work.model_copy(
            update={"expiresAt": datetime.now(UTC) - timedelta(hours=1)}
        )
    d.automation.continuation.policy = policy.model_copy(update={"works": (work,)})
    if invalid == "denied":

        def deny(*args):
            raise AuthorityError("READ_DENIED")

        d.automation.proof_grants = deny
    import agent_console.automatic_skill_testing as testing

    calls = []
    monkeypatch.setattr(testing, "run", lambda *a, **kw: calls.append(kw))
    with pytest.raises(AuthorityError):
        run_test(d, load=invalid != "missing")
    assert calls == []


@pytest.mark.parametrize("documents", [True], indirect=True)
@pytest.mark.parametrize("invalid", ["digest", "scope"])
def test_exact_published_rule_mismatch_cannot_reach_actual_test(
    documents, invalid, monkeypatch
):
    from agent_console.execution_preparation import ExecutionPreparationError

    d = documents
    policy = d.automation.continuation.policy
    work = policy.works[0]
    binding = work.documentRules
    if invalid == "digest":
        binding = binding.model_copy(
            update={
                "ontology": binding.ontology.model_copy(update={"digest": "f" * 64})
            }
        )
    else:
        binding = binding.model_copy(update={"scope": "another-scope"})
    d.automation.continuation.policy = policy.model_copy(
        update={"works": (work.model_copy(update={"documentRules": binding}),)}
    )
    import agent_console.automatic_skill_testing as testing

    calls = []
    monkeypatch.setattr(testing, "run", lambda *a, **kw: calls.append(kw))
    with pytest.raises(ExecutionPreparationError):
        run_test(d)
    assert calls == []
    assert [event[0] for event in d.events] == ["decide", "require"]
