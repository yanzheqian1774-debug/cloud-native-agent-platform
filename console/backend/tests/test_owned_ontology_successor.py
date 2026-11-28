"""The A2 perimeter permits only the exact reviewed Skill reference change."""

from copy import deepcopy

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.owned_ontology_successor import (
    equal_business_content,
    equal_skill_contract,
    marker,
)
from agent_console.plan_suggestion_domain import ExactReference
from test_document_rule_owner import rules

OLD = ExactReference(resource_id="same-skill", revision_id="r1", digest="a" * 64)
NEW = ExactReference(resource_id="same-skill", revision_id="r2", digest="b" * 64)


def content():
    original = rules(skill=OLD.model_dump(mode="json")).model_dump(mode="json")
    successor = deepcopy(original)
    for action in successor["actions"]:
        action["skill"] = NEW.model_dump(mode="json")
    return original, successor


def test_only_action_skill_tuple_is_rebound_not_old_content():
    before, after = content()
    saved = deepcopy(before)
    equal_business_content(before, after, OLD, NEW)
    assert before == saved
    assert all(a["skill"] == NEW.model_dump(mode="json") for a in after["actions"])
    assert '"revision_id":"r2"' in marker(NEW)


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "mapping",
        "rule",
        "scope",
        "owner",
        "operation",
        "effect",
        "executor",
        "extra_action",
    ],
)
def test_same_resource_id_does_not_permit_other_business_or_execution_changes(fault):
    before, after = content()
    if fault == "source":
        after["mappings"][0]["source"]["resource_id"] = "another-source"
    elif fault == "mapping":
        after["mappings"][0]["code"] = "another-mapping"
    elif fault == "rule":
        after["rules"] = []
    elif fault == "scope":
        after["scope"] = "different-business"
    elif fault == "owner":
        after["business_owner"] = "other-owner"
    elif fault == "operation":
        after["actions"][0]["operation"] = "WRITE_DATA"
    elif fault == "effect":
        after["actions"][0]["side_effect"] = "WRITE"
    elif fault == "executor":
        after["actions"][0]["executor_digest"] = "0" * 64
    else:
        after["actions"].append(deepcopy(after["actions"][0]))
    with pytest.raises(AuthorityError, match="BUSINESS_SEMANTICS_CHANGED"):
        equal_business_content(before, after, OLD, NEW)


def test_cross_skill_identity_is_not_a2_even_if_rules_are_equal():
    before, after = content()
    with pytest.raises(AuthorityError, match="SKILL_IDENTITY_CHANGED"):
        equal_business_content(
            before, after, OLD, NEW.model_copy(update={"resource_id": "other-skill"})
        )


@pytest.mark.parametrize(
    "field", ["instructions", "capabilities", "operations", "externalBindings"]
)
def test_complete_skill_contract_is_not_just_an_executor_name(field):
    before = {
        "description": "old display",
        "instructions": "same",
        "capabilities": ["READ_DATA"],
        "operations": [{"name": "READ_DATA", "timeout": 100}],
        "externalBindings": [],
    }
    after = deepcopy(before)
    after["description"] = "new display"
    equal_skill_contract(before, after)
    after[field] = "changed"
    with pytest.raises(AuthorityError, match="EXECUTION_CONTRACT_CHANGED"):
        equal_skill_contract(before, after)


def test_non_ontology_adapter_retains_its_existing_contract_path_without_queries():
    from types import SimpleNamespace as NS

    from agent_console.owned_ontology_successor import resolve

    scope = NS(documentRules=None, skills=(OLD,))
    assert resolve(None, None, None, scope, None, (NEW,)) == (None, None)
    with pytest.raises(AuthorityError, match="UNEXPECTED_ONTOLOGY_SELECTION"):
        resolve(None, None, None, scope, None, (NEW,), requested=NEW)


def test_current_new_ontology_use_is_required_not_inferred_from_publication(
    monkeypatch,
):
    from types import SimpleNamespace as NS

    from agent_console import owned_ontology_successor as module
    from agent_console.ontology_execution import DocumentSemanticsBinding
    from agent_console.owned_resource_assembly import MODE

    before, _ = content()
    ontology = ExactReference(
        resource_id="same-ontology", revision_id="r1", digest="c" * 64
    )
    successor = ontology.model_copy(update={"revision_id": "r2", "digest": "d" * 64})
    source = ExactReference.model_validate(before["mappings"][0]["source"])
    binding = DocumentSemanticsBinding(
        ontology=ontology,
        source=source,
        mapping_code=before["mappings"][0]["code"],
        scope=before["scope"],
    )
    original = NS(documentRules=binding, trustedAssemblyAdoption=MODE, skills=(OLD,))
    contract = {"instructions": "same", "operations": []}
    monkeypatch.setattr(
        module, "read_published", lambda *a, **k: (contract, "metadata")
    )
    monkeypatch.setattr(module, "skill_lineage", lambda *a: None)
    monkeypatch.setattr(module, "upgrade_receipt", lambda *a, **k: {"digest": "e" * 64})
    observed = []
    monkeypatch.setattr(
        module,
        "published_content",
        lambda *a: observed.append(a[2]) or NS(model_dump=lambda **k: before),
    )

    class Connection:
        row_factory = None

        def execute(self, *args):
            raise AssertionError("no fallback or write after current USE denial")

    def current_reads(c, context, grants, now, **kwargs):
        if any(g.owner == "BUSINESS_ONTOLOGY" and g.action == "USE" for g in grants):
            raise AuthorityError("OWNED_BUSINESS_READ_DENIED")

    reader = NS(_reads=current_reads)
    context = NS(
        scope=NS(tenant_id="tenant", security_domain="domain"), principal_id="ordinary"
    )
    with pytest.raises(AuthorityError, match="READ_DENIED"):
        module.resolve(
            reader, Connection(), context, original, None, (NEW,), requested=successor
        )
    assert observed == [binding]


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "work_subject",
        "plan",
        "digest",
        "scope",
        "admission",
        "ontology",
        "generation",
        "recovery",
    ],
)
def test_inheritance_requires_the_exact_already_adopted_predecessor(fault):
    from types import SimpleNamespace as NS

    from agent_console.owned_ontology_successor import adopted_evidence
    from agent_console.owned_resource_assembly import admission_basis
    from agent_console.resource_use_domain import canonical_digest

    ontology = ExactReference(
        resource_id="same-ontology", revision_id="r2", digest="c" * 64
    )
    source = ExactReference(resource_id="same-plan", revision_id="2", digest="d" * 64)
    executed = source.model_copy(update={"revision_id": "3", "digest": "e" * 64})
    scope_record = {"scopeId": "one-source", "skill": NEW.model_dump(mode="json")}
    scope = NS(
        scopeId="one-source",
        authorizationBasisDigest="f" * 64,
        skills=(NEW,),
        documentRules=NS(ontology=ontology),
        model_dump=lambda **k: scope_record,
    )
    work = NS(
        namespace="tenant",
        securityDomain="domain",
        subject="actor",
        admissionId="same-admission",
        admissionRecordDigest="1" * 64,
        admissionPolicyDigest="2" * 64,
        businessScope=scope,
    )
    body = {
        "plan": source.model_dump(mode="json"),
        "admission": admission_basis(work),
        "scope": deepcopy(scope_record),
        "subject": "actor",
        "authorityGeneration": 36,
        "recoveryEpoch": 2,
        "ontologySuccessor": {
            "ontology": ontology.model_dump(mode="json"),
            "newSkill": NEW.model_dump(mode="json"),
        },
    }
    proof = {"body": body, "digest": canonical_digest(body)}
    work.assemblyAdoption = {
        "plan": executed.model_dump(mode="json"),
        "sourcePlan": source.model_dump(mode="json"),
        "requestKey": "real-owner-selection",
        "digest": proof["digest"],
    }
    if fault == "work_subject":
        work.subject = "other-actor"
    elif fault == "plan":
        work.assemblyAdoption["plan"]["digest"] = "0" * 64
    elif fault == "digest":
        proof["digest"] = "0" * 64
    elif fault == "scope":
        body["scope"]["scopeId"] = "other-source"
    elif fault == "admission":
        body["admission"]["admissionId"] = "other-admission"
    elif fault == "ontology":
        body["ontologySuccessor"]["ontology"]["digest"] = "0" * 64
    elif fault == "generation":
        body["authorityGeneration"] = 37
    elif fault == "recovery":
        body["recoveryEpoch"] = 3
    if fault not in {None, "digest", "work_subject", "plan"}:
        proof["digest"] = canonical_digest(body)
        work.assemblyAdoption["digest"] = proof["digest"]
    c = NS(
        execute=lambda *a: NS(fetchone=lambda: {"record": {"assemblyAdoption": proof}})
    )
    context = NS(
        scope=NS(tenant_id="tenant", security_domain="domain"), principal_id="actor"
    )
    reader = NS(generation=36, recovery_epoch=2)
    if fault:
        with pytest.raises(AuthorityError):
            adopted_evidence(reader, c, context, work, executed, (NEW,))
    else:
        value = adopted_evidence(reader, c, context, work, executed, (NEW,))
        assert value["plan"] == executed.model_dump(mode="json")
        assert value["digest"] == canonical_digest(work.assemblyAdoption)
        # A different Skill, never adopted by the exact predecessor, cannot use it.
        assert adopted_evidence(reader, c, context, work, executed, (OLD,)) is None


def test_legacy_selection_request_keeps_absent_optional_ontology_bytes():
    from agent_console.resource_automation import SelectEmployeeResources

    request = SelectEmployeeResources(
        version=1,
        digest="0" * 64,
        expectedProposalRevision=1,
        employee=OLD,
        idempotencyKey="original-request",
    )
    assert "ontologySuccessor" not in request.model_dump(mode="json")
    explicit = request.model_copy(update={"ontologySuccessor": NEW})
    assert explicit.model_dump(mode="json")["ontologySuccessor"] == NEW.model_dump(
        mode="json"
    )


def test_ontology_lineage_read_bound_is_local_and_resets_after_denial():
    from agent_console.owned_ontology_successor import LINEAGE_READ, lineage_guard

    with lineage_guard(OLD):
        with pytest.raises(AuthorityError, match="LINEAGE_LIMIT"), lineage_guard(OLD):
            pass
        with lineage_guard(NEW):
            assert len(LINEAGE_READ.get()) == 2
    assert LINEAGE_READ.get() == ()
