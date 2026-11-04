"""Real-PG owner lifecycle, independent review, isolation and semantic rejection."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.ontology_domain import OntologyContent, OntologyError
from agent_console.ontology_postgres import migrate
from agent_console.ontology_query import SemanticQuery, query_sales
from agent_console.ontology_sales_sample import sales_content
from agent_console.ontology_service import OntologyService
from agent_console.prepared_execution_resources import published
from agent_console.sales_diagnostic_skill import SalesDiagnosticSkillExecutor
from prepared_execution_support import seed
from pydantic import ValidationError
from test_plan_suggestion_v2 import repository  # noqa: F401


class ExactOntologyTestAuthority:
    def __init__(self):
        self.denied = set()

    def require(self, principal, owner, action, resource):
        from agent_console.authority_configuration import validate_registered_grant
        from agent_console.authority_contracts import ExactGrant

        validate_registered_grant(ExactGrant(owner, action, resource), allow_meta=False)
        if (owner, action) in self.denied:
            raise AuthorityError("AUTHORIZATION_NOT_FOUND")
        return SimpleNamespace(decision_id="explicit-isolated-test-authority")


@pytest.fixture
def ontology(repository):  # noqa: F811
    p = seed(repository, synthetic_skill="sales")
    with repository.pool.connection() as c, c.transaction():
        migrate(c)
        source = __import__("json").loads(
            published(
                c,
                SimpleNamespace(
                    namespace=p.namespace, security_domain=p.security_domain
                ),
                "KNOWLEDGE",
                p.source_snapshot,
            )["documents"][0]["chunks"][0]["content"]
        )
    content = sales_content(
        source,
        p.source_snapshot.model_dump(mode="json"),
        p.participants[0].skill.reference.model_dump(mode="json"),
        SalesDiagnosticSkillExecutor.revision,
    )
    return repository, p, source, content


def call(
    ontology,
    action,
    *,
    actor="human:author",
    version=0,
    revision="r1",
    digest=None,
    content=None,
    key=None,
    authority=None,
):
    repo, p, _, _ = ontology
    with repo.pool.connection() as c, c.transaction():
        service = OntologyService(
            SimpleNamespace(
                connection=c,
                context=SimpleNamespace(
                    principal_id=actor,
                    scope=SimpleNamespace(
                        tenant_id=p.namespace, security_domain=p.security_domain
                    ),
                ),
                authority=authority or ExactOntologyTestAuthority(),
            )
        )
        return service.handle(
            action,
            "sales",
            {
                "request_key": key or f"{action}-{version}-{revision}",
                "expected_version": version,
                "revision_id": revision,
                "digest": digest,
                "content": content,
                "reason": "isolated lifecycle acceptance",
            },
        )


def publish(ontology):
    content = ontology[3].model_dump(mode="json")
    value = call(ontology, "CREATE", content=content)
    for action in ("VALIDATE", "TEST", "REVIEW", "PUBLISH"):
        value = call(
            ontology,
            action,
            actor="human:reviewer" if action == "REVIEW" else "human:author",
            version=value["version"],
            digest=value["digest"],
        )
    return value


def test_owner_lifecycle_restart_immutable_and_independent_review(ontology):
    value = call(ontology, "CREATE", content=ontology[3].model_dump(mode="json"))
    for action in ("VALIDATE", "TEST"):
        value = call(ontology, action, version=value["version"], digest=value["digest"])
    with pytest.raises(OntologyError, match="INDEPENDENT_REVIEW"):
        call(ontology, "REVIEW", version=value["version"], digest=value["digest"])
    value = call(
        ontology,
        "REVIEW",
        actor="human:reviewer",
        version=value["version"],
        digest=value["digest"],
    )
    value = call(ontology, "PUBLISH", version=value["version"], digest=value["digest"])
    repo, p, _, _ = ontology
    from agent_console.ontology_postgres import PostgresOntologyRepository

    with repo.pool.connection() as c:
        result = PostgresOntologyRepository(c).read(
            (p.namespace, p.security_domain), "sales", "r1"
        )
        assert result["digest"] == value["digest"] and result["state"] == "PUBLISH"
        assert len(result["facts"]) == 5
        with pytest.raises(OntologyError, match="NOT_FOUND"):
            PostgresOntologyRepository(c).read((p.namespace, "foreign"), "sales", "r1")
    import psycopg

    with (
        repo.pool.connection() as c,
        c.transaction(),
        pytest.raises(psycopg.Error, match="ONTOLOGY_IMMUTABLE"),
    ):
        c.execute("UPDATE business_ontology.revisions SET content='{}'")


def test_replay_stale_and_new_revision_does_not_inherit_reviews(ontology):
    args = dict(content=ontology[3].model_dump(mode="json"), key="create")
    value = call(ontology, "CREATE", **args)
    assert call(ontology, "CREATE", **args) == value
    with pytest.raises(OntologyError, match="REPLAY_CONFLICT"):
        call(ontology, "CREATE", **{**args, "revision": "other"})
    with pytest.raises(OntologyError, match="VERSION_CONFLICT"):
        call(ontology, "VALIDATE", digest=value["digest"])
    published_value = value
    for action in ("VALIDATE", "TEST", "REVIEW", "PUBLISH"):
        published_value = call(
            ontology,
            action,
            actor="human:reviewer" if action == "REVIEW" else "human:author",
            version=published_value["version"],
            digest=value["digest"],
        )
    new = call(
        ontology,
        "REVISE",
        version=published_value["version"],
        revision="r2",
        content=args["content"],
    )
    assert new["digest"] != value["digest"]
    with pytest.raises(OntologyError, match="LIFECYCLE"):
        call(
            ontology,
            "PUBLISH",
            version=new["version"],
            revision="r2",
            digest=new["digest"],
        )


def test_denied_before_create(ontology):
    authority = ExactOntologyTestAuthority()
    authority.denied.add(("BUSINESS_ONTOLOGY", "CREATE"))
    with pytest.raises(AuthorityError):
        call(
            ontology,
            "CREATE",
            content=ontology[3].model_dump(mode="json"),
            authority=authority,
        )


def test_concurrent_creates_have_one_winner(ontology):
    from concurrent.futures import ThreadPoolExecutor

    content = ontology[3].model_dump(mode="json")

    def create(key):
        try:
            return call(ontology, "CREATE", content=content, key=key)["state"]
        except OntologyError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(create, ("race-a", "race-b")))
    assert sorted(results) == ["CREATE", "ONTOLOGY_VERSION_CONFLICT"]


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "bad_relation", "unknown_ast", "money_type", "bad_mapping"],
)
def test_bad_definition_is_rejected(ontology, mutation):
    doc = deepcopy(ontology[3].model_dump(mode="json"))
    if mutation == "duplicate":
        doc["objects"].append(doc["objects"][0])
    elif mutation == "bad_relation":
        doc["relations"][0]["target_key"] = "missing"
    elif mutation == "unknown_ast":
        doc["metrics"][0]["expression"] = {"op": "SQL", "field": "netSales"}
    elif mutation == "money_type":
        doc["metrics"][0]["expression"]["field"] = "product"
    else:
        doc["mappings"][0]["object_code"] = "missing"
    with pytest.raises((ValidationError, OntologyError)):
        OntologyContent.model_validate(doc)


def test_semantic_amounts_and_ambiguous_queries(ontology):
    _, _, source, content = ontology
    value = query_sales(content, source, SemanticQuery(metric="net_sales"))
    cny = next(r for r in value["rows"] if r["currency"] == "CNY")
    assert (cny["baseline"], cny["current"], cny["delta"]) == (
        "1000.00",
        "800.00",
        "-200.00",
    )
    with pytest.raises(OntologyError, match="UNKNOWN"):
        query_sales(content, source, SemanticQuery(metric="unknown"))
    with pytest.raises(OntologyError, match="UNSUPPORTED"):
        query_sales(
            content, source, SemanticQuery(metric="net_sales", dimensions=("currency",))
        )


@pytest.mark.parametrize("action", ["READ", "REVISE", "PUBLISH"])
def test_exact_permissions_fail_before_mutation(ontology, action):
    value = publish(ontology)
    authority = ExactOntologyTestAuthority()
    authority.denied.add(("BUSINESS_ONTOLOGY", action))
    with pytest.raises(AuthorityError):
        call(
            ontology,
            action,
            version=value["version"],
            digest=value["digest"],
            revision="r2" if action == "REVISE" else "r1",
            content=ontology[3].model_dump(mode="json") if action == "REVISE" else None,
            authority=authority,
        )
    from agent_console.ontology_postgres import PostgresOntologyRepository

    repo, p, _, _ = ontology
    with repo.pool.connection() as c:
        assert (
            PostgresOntologyRepository(c).read(
                (p.namespace, p.security_domain), "sales", "r1"
            )["state"]
            == "PUBLISH"
        )


def test_bound_digest_mapping_source_and_deprecation(ontology):
    from agent_console.execution_domain import ScopeIdentity
    from agent_console.execution_preparation import ExecutionPreparationError
    from agent_console.ontology_execution import (
        BusinessSemanticsBinding,
        published_content,
    )

    value = publish(ontology)
    repo, p, _, _ = ontology
    binding = BusinessSemanticsBinding(
        ontology={
            "resource_id": "sales",
            "revision_id": "r1",
            "digest": value["digest"],
        },
        mapping_code="sales_csv",
        source=p.source_snapshot,
        queries=(SemanticQuery(metric="net_sales"),),
    )
    scope = ScopeIdentity(p.namespace, p.security_domain)
    with repo.pool.connection() as c:
        assert published_content(c, scope, binding)
        for changed in [
            binding.model_copy(
                update={
                    "ontology": binding.ontology.model_copy(update={"digest": "0" * 64})
                }
            ),
            binding.model_copy(update={"mapping_code": "missing"}),
            binding.model_copy(
                update={
                    "source": binding.source.model_copy(update={"digest": "0" * 64})
                }
            ),
        ]:
            with pytest.raises(ExecutionPreparationError):
                published_content(c, scope, changed)
    value = call(
        ontology, "DEPRECATE", version=value["version"], digest=value["digest"]
    )
    with repo.pool.connection() as c:
        with pytest.raises(
            ExecutionPreparationError, match="PUBLISHED_VERSION_REQUIRED"
        ):
            published_content(c, scope, binding)
        assert published_content(c, scope, binding, current=False)
