"""Versioned commitments and independent numerical checks on fixed synthetic data."""

from copy import deepcopy
from pathlib import Path

import pytest
from agent_console.execution_preparation import ExecutionPreparation
from agent_console.ontology_domain import OntologyContent, OntologyError
from agent_console.ontology_execution import (
    BusinessSemanticsBinding,
    OntologyExecutionPreparation,
    parse_preparation,
)
from agent_console.ontology_query import SemanticQuery, query_sales
from agent_console.ontology_sales_evaluation import CHECKS, evaluate
from agent_console.ontology_sales_sample import sales_content
from agent_console.resource_use_domain import canonical_digest
from agent_console.sales_ontology_executor import SalesOntologyExecutor
from agent_console.sales_resource_bundle import source_document
from agent_console.skill_executor import SkillExecutorFailure
from pydantic import ValidationError
from test_execution_preparation import preparation


def sample():
    source = source_document(
        (
            Path(__file__).parents[3] / "examples/sales-diagnostic/synthetic-sales.csv"
        ).read_bytes()
    )
    p = preparation()
    content = sales_content(
        source,
        p.source_snapshot.model_dump(mode="json"),
        p.participants[0].skill.reference.model_dump(mode="json"),
        SalesOntologyExecutor.revision,
    )
    binding = BusinessSemanticsBinding(
        ontology=p.source_snapshot,
        mapping_code="sales_csv",
        source=p.source_snapshot,
        queries=(
            SemanticQuery(metric="net_sales"),
            SemanticQuery(metric="gross_profit"),
            SemanticQuery(metric="net_sales", dimensions=("region",)),
        ),
    )
    p2 = OntologyExecutionPreparation.model_validate(
        {
            **p.model_dump(mode="json"),
            "schema_version": "execution-preparation.v2",
            "business_semantics": binding.model_dump(mode="json"),
        }
    )
    return source, content, p2


def report(source, content, p):
    executor = SalesOntologyExecutor()
    inputs = {
        "schemaVersion": "ontology-sales-input.v1",
        "source": source,
        "ontologyContent": content.model_dump(mode="json"),
        "businessSemantics": p.business_semantics.model_dump(mode="json"),
    }
    read = executor.invoke("read", "READ_DATA", inputs, 1000).output
    return executor.invoke(
        "report", "RENDER_REPORT", {**inputs, "dependencies": {"read": read}}, 1000
    ).output


def criterion(p, source, check):
    return {
        "criterion_type": "DETERMINISTIC_BOOLEAN",
        "required_evidence_kinds": [
            "NATIVE_EXECUTION_ARTIFACT",
            "PUBLISHED_SYNTHETIC_SOURCE",
        ],
        "measurement": {"expected": True},
        "evaluator_type": "SYNTHETIC_ONTOLOGY_SALES",
        "evaluator_version": "1",
        "applicability": {
            "check": check,
            "bindingDigest": p.business_semantics.digest,
            "sourceContentDigest": canonical_digest(source),
        },
    }


def test_old_v1_bytes_and_new_mapping_commitments():
    old = preparation()
    before = old.model_dump_json(), old.digest, old.mapping_digest, old.run_id
    _, _, new = sample()
    assert parse_preparation(old.model_dump(mode="json")) == old
    assert parse_preparation(new.model_dump(mode="json")) == new
    with pytest.raises(ValidationError):
        ExecutionPreparation.model_validate(new.model_dump(mode="json"))
    assert new.mapping_digest != old.mapping_digest and new.run_id != old.run_id
    changed = new.model_copy(
        update={
            "business_semantics": new.business_semantics.model_copy(
                update={"queries": (SemanticQuery(metric="gross_profit"),)}
            )
        }
    )
    assert changed.mapping_digest != new.mapping_digest and changed.digest != new.digest
    assert before == (old.model_dump_json(), old.digest, old.mapping_digest, old.run_id)


@pytest.mark.parametrize("check", CHECKS)
def test_independent_evaluator_and_tampering(check):
    source, content, p = sample()
    value = report(source, content, p)
    c = criterion(p, source, check)
    assert (
        evaluate(c, source, value, p, content.model_dump(mode="json"))[0] == "SATISFIED"
    )
    broken = deepcopy(value)
    if check == "source":
        broken["sourceSnapshot"]["digest"] = "0" * 64
    elif check == "totals":
        broken["reports"][0]["rows"][0]["current"] = "99999.00"
    elif check == "contributions":
        broken["reports"][2]["rows"][0]["delta"] = "0.00"
    elif check == "exceptions":
        broken["reports"][0]["excludedRows"] = []
    else:
        broken["businessConclusion"] = "SOLVED"
    assert (
        evaluate(c, source, broken, p, content.model_dump(mode="json"))[0]
        == "NOT_SATISFIED"
    )


def test_changed_rule_changes_amount_and_old_criteria_cannot_pass():
    source, content, p = sample()
    doc = content.model_dump(mode="json")
    doc["rules"]["included_kinds"] = ["SALE"]
    doc["metrics"][0]["name"] = "不含退货的销售发生额"
    new_content = OntologyContent.model_validate(doc)
    old = report(source, content, p)
    changed_binding = p.business_semantics.model_copy(
        update={
            "ontology": p.business_semantics.ontology.model_copy(
                update={"revision_id": "r2", "digest": "c" * 64}
            )
        }
    )
    new_p = p.model_copy(update={"business_semantics": changed_binding})
    changed = report(source, new_content, new_p)
    old_cny = next(r for r in old["reports"][0]["rows"] if r["currency"] == "CNY")
    new_cny = next(r for r in changed["reports"][0]["rows"] if r["currency"] == "CNY")
    assert (old_cny["current"], new_cny["current"]) == ("800.00", "850.00")
    assert (
        evaluate(criterion(p, source, "totals"), source, changed, new_p, doc)[0]
        == "UNKNOWN"
    )
    assert (
        evaluate(criterion(new_p, source, "totals"), source, changed, new_p, doc)[0]
        == "SATISFIED"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "metric",
        "dimension",
        "filter",
        "relation",
        "currency",
        "precision",
        "duplicate",
        "digest",
    ],
)
def test_bad_query_or_data_fails_before_effect(bad):
    source, content, _p = sample()
    q = SemanticQuery(metric="net_sales")
    if bad == "metric":
        q = SemanticQuery(metric="missing")
    elif bad == "dimension":
        q = SemanticQuery(metric="net_sales", dimensions=("currency",))
    elif bad == "filter":
        q = SemanticQuery(metric="net_sales", filters={"sql": ("anything",)})
    elif bad == "relation":
        doc = content.model_dump(mode="json")
        doc["relations"][0]["cardinality"] = "ONE_TO_ONE"
        content = OntologyContent.model_validate(doc)
    elif bad == "digest":
        source["metric"] = "unknown"
    else:
        fields = {
            "currency": ("currency", "cny"),
            "precision": ("netSales", "1.001"),
            "duplicate": ("rowId", "S02"),
        }
        key, value = fields[bad]
        source["snapshot"]["rows"][0]["values"][key] = value
    with pytest.raises((OntologyError, SkillExecutorFailure)):
        query_sales(content, source, q)


def test_zero_period_and_alias_ambiguity():
    source, content, _ = sample()
    result = query_sales(content, source, SemanticQuery(metric="销售额"))
    jpy = next(r for r in result["rows"] if r["currency"] == "JPY")
    assert jpy["changeRate"] is None and jpy["rateReason"] == "BASELINE_ZERO"
    doc = content.model_dump(mode="json")
    doc["metrics"][1]["aliases"] = ["销售额"]
    with pytest.raises(OntologyError, match="AMBIGUOUS"):
        query_sales(
            OntologyContent.model_validate(doc), source, SemanticQuery(metric="销售额")
        )


@pytest.mark.parametrize("ontology_use_current", [True, False])
def test_native_authorization_keeps_skill_target_string(
    monkeypatch, ontology_use_current
):
    """Regression for the observed pre-Skill authorization digest failure."""
    from types import SimpleNamespace

    from agent_console import prepared_native_composition as module
    from agent_console.execution_domain import ScopeIdentity

    _, _, p = sample()
    seen = []

    class Reader:
        def has_current_grants(self, context, grants, **kwargs):
            seen.extend(grants)
            return (True, ontology_use_current)

    monkeypatch.setattr(module, "compose_governed_skill_invocation", lambda *args: None)
    monkeypatch.setattr(
        module,
        "prepared_attempt",
        lambda *args: {
            "preparation": p.model_dump(mode="json"),
            "task_id": p.participants[0].task_id,
            "attempt_ordinal": 1,
        },
    )
    caller, _ = module.compose(
        None,
        "unused",
        Path("unused"),
        Reader(),
        SimpleNamespace(policy_version="test"),
        lambda *args: True,
        mode="ontology-sales-v1",
    )
    command = SimpleNamespace(
        scope=ScopeIdentity(p.namespace, p.security_domain),
        attempt_id="attempt",
        principal_id="human:author",
        credential_id="session",
        authentication_source="BROWSER_SESSION",
        authority_generation=SimpleNamespace(value=1),
        recovery_epoch=SimpleNamespace(value=1),
    )
    if not ontology_use_current:
        from agent_console.authority_contracts import AuthorityError

        with pytest.raises(AuthorityError, match="AUTHORIZATION_NOT_FOUND"):
            caller.authorize(None, command)
        return
    decision = caller.authorize(None, command)
    assert decision.startswith("prepared-skill-authorization:")
    assert seen[0].exact_resource.startswith("skill-invocation:prepared:")
    assert seen[1].exact_resource == "business-ontology:controlled:1"


@pytest.mark.parametrize("mismatch", ["executor", "source", "skill"])
def test_execution_rejects_incompatible_exact_bindings(monkeypatch, mismatch):
    from agent_console import ontology_execution as module
    from agent_console.execution_preparation import ExecutionPreparationError

    _source, content, p = sample()
    expected = SalesOntologyExecutor.revision
    participant = p.participants[0].model_copy(
        update={
            "executor_id": expected.executor_id,
            "executor_revision": expected.executor_revision,
            "executor_digest": expected.configuration_digest,
        }
    )
    if mismatch == "executor":
        participant = participant.model_copy(update={"executor_digest": "0" * 64})
    elif mismatch == "source":
        p = p.model_copy(
            update={
                "source_snapshot": p.source_snapshot.model_copy(
                    update={"digest": "0" * 64}
                )
            }
        )
    else:
        participant = participant.model_copy(
            update={
                "skill": participant.skill.model_copy(
                    update={
                        "reference": participant.skill.reference.model_copy(
                            update={"digest": "0" * 64}
                        )
                    }
                )
            }
        )
    monkeypatch.setattr(module, "published_content", lambda *args: content)
    with pytest.raises(ExecutionPreparationError):
        module.validate_semantics(None, None, p, participant)
