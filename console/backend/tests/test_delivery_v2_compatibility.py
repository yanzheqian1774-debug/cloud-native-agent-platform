# ruff: noqa: RUF001 -- Exact observed Chinese source labels.
"""Immutable v1, exact v2 classification, source and role compatibility."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from agent_console.authority_contracts import AuthorityError
from agent_console.delivery_resource_bundle import resource_content as v1_content
from agent_console.delivery_resource_bundle import source_document
from agent_console.execution_preparation import ExecutionPreparationError
from agent_console.plan_suggestion_domain import ExactReference, PlanningConflict
from agent_console.planning_source_reference import approved_source
from agent_console.prepared_delivery_contract import validate_delivery_mapping
from agent_console.resource_automation_validation import EXECUTORS, validate
from agent_console.skill_executor import SkillExecutorFailure
from agent_console.skill_invocation_domain import ExecutorRevision, SkillInvocationError
from agent_console.synthetic_delivery_skill import SyntheticDeliverySkillExecutor
from agent_console.synthetic_delivery_skill_v2 import (
    SyntheticDeliverySkillExecutorV2,
    resource_content,
)
from delivery_v2_support import six_roles
from test_execution_preparation import preparation


def inputs():
    return {
        "schemaVersion": "synthetic-delivery-input.v1",
        "synthetic": True,
        "sourceSnapshot": {
            "resource_id": "knowledge",
            "revision_id": "1",
            "digest": "a" * 64,
        },
        "source": source_document(),
        "dependencies": {},
    }


def source_semantics():
    value = six_roles(preparation().semantics)
    source = ExactReference.model_validate(inputs()["sourceSnapshot"])
    doc = value.model_dump(mode="json")
    doc["requirements"][0]["selected"] = source.model_dump(mode="json")
    doc["boundaries"] = [
        f"仅使用隔离合成只读来源：{source.resource_id}；修订：{source.revision_id}；SHA256：{source.digest}"
    ]
    return type(value).model_validate(doc)


def test_source_projection_used_by_original_question_entry_stays_compatible():
    semantics = source_semantics()
    projection = SimpleNamespace(boundaries=semantics.boundaries)
    assert approved_source(projection) == approved_source(semantics)


def test_v1_stays_exact_and_cannot_advertise_or_run_classification():
    old = v1_content()
    assert (
        SyntheticDeliverySkillExecutor.revision.configuration_digest
        == "428c1a499fa880f12d230cd3d8abfed67448e9373f02973aac9a2a0bd8381a4b"
    )
    assert (
        EXECUTORS.resolve(
            SyntheticDeliverySkillExecutor.revision
        ).revision.executor_revision
        == "1"
    )
    resource_content()
    assert old == v1_content()
    with pytest.raises(SkillExecutorFailure):
        SyntheticDeliverySkillExecutor().invoke(
            "v1", "CLASSIFY_OVERDUE", inputs(), 1000
        )
    forged = deepcopy(old["skill"])
    forged["operations"][0]["name"] = "CLASSIFY_OVERDUE"
    with pytest.raises(AuthorityError, match="OPERATION_UNAVAILABLE"):
        validate("skill", forged, None)


def test_six_role_graph_consumes_real_predecessors_and_has_independent_ranking():
    executor = SyntheticDeliverySkillExecutorV2()
    sem = source_semantics()
    before = sem.model_dump(mode="json")
    validate_delivery_mapping(before, resource_content()["skill"]["operations"])
    outputs = {}
    for task in sem.tasks:
        outputs[task.task_id] = executor.invoke(
            task.task_id,
            task.operation,
            {
                **inputs(),
                "dependencies": {key: outputs[key] for key in task.depends_on},
            },
            1000,
        ).output
        assert outputs[task.task_id]["outputKind"] == task.output_kind
    classified = outputs["step-2"]
    assert [s["supplierId"] for s in classified["suppliers"]] == [
        "SYN-A",
        "SYN-B",
        "SYN-C",
    ]
    assert classified["suppliers"][0]["remainingByUnit"] == {"件": "60", "箱": "15"}
    assert {r["orderId"] for r in classified["excludedOrders"]} == {"PO-S07", "PO-S08"}
    assert {r["orderId"] for r in classified["anomalies"]} == {"PO-S09", "PO-S10"}
    assert outputs["step-5"]["businessConclusion"] == "UNDETERMINED"
    assert sem.model_dump(mode="json") == before


@pytest.mark.parametrize(
    "mutation",
    [
        "raw",
        "v1",
        "digest",
        "source",
        "source_digest",
        "output_kind",
        "operation",
        "synthetic",
    ],
)
def test_classification_rejects_wrong_kind_revision_or_provenance(mutation):
    executor = SyntheticDeliverySkillExecutorV2()
    read = executor.invoke("read", "READ_DATA", inputs(), 1000).output
    validated = executor.invoke(
        "validate", "VALIDATE_DATA", {**inputs(), "dependencies": {"read": read}}, 1000
    ).output
    prior = deepcopy(validated)
    if mutation == "raw":
        prior = read
    elif mutation == "v1":
        prior["executorRevision"] = "1"
    elif mutation == "digest":
        prior["executorConfigurationDigest"] = "0" * 64
    elif mutation == "source":
        prior["sourceSnapshot"]["revision_id"] = "other"
    elif mutation == "source_digest":
        prior["source"]["orders"][0]["orderedQuantity"] = "123"
    elif mutation == "output_kind":
        prior["outputKind"] = "CLASSIFICATION"
    elif mutation == "operation":
        prior["operation"] = "READ_DATA"
    else:
        prior["synthetic"] = False
    with pytest.raises(SkillExecutorFailure):
        executor.invoke(
            "classify",
            "CLASSIFY_OVERDUE",
            {**inputs(), "dependencies": {"prior": prior}},
            1000,
        )


def test_wrong_registry_digest_and_mixed_mapping_cannot_bind():
    rev = SyntheticDeliverySkillExecutorV2.revision
    with pytest.raises(SkillInvocationError, match="UNAVAILABLE"):
        EXECUTORS.resolve(ExecutorRevision(rev.executor_id, "2", "0" * 64))
    operations = resource_content()["skill"]["operations"]
    operations[0] = v1_content()["skill"]["operations"][0]
    with pytest.raises(ExecutionPreparationError, match="REVISION_MIXED"):
        validate_delivery_mapping(
            source_semantics().model_dump(mode="json"), operations
        )
    duplicate_name = [
        v1_content()["skill"]["operations"][0],
        *resource_content()["skill"]["operations"],
    ]
    with pytest.raises(ExecutionPreparationError, match="REVISION_MIXED"):
        validate_delivery_mapping(
            source_semantics().model_dump(mode="json"), duplicate_name
        )
    weakened = resource_content()["skill"]
    weakened["operations"][2]["outputSchema"]["required"].remove("outputKind")
    with pytest.raises(AuthorityError, match="TYPED_SCHEMA_MISMATCH"):
        validate("skill", weakened, None)


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "missing_revision_label",
        "missing_digest_label",
        "selection",
        "prose",
        "digest",
    ],
)
def test_source_compatibility_is_strict_and_does_not_change_proposal(mutation):
    sem = source_semantics()
    before = sem.model_dump(mode="json")
    assert approved_source(sem) == sem.requirements[0].selected
    assert sem.model_dump(mode="json") == before
    doc = deepcopy(before)
    if mutation == "duplicate":
        doc["boundaries"].append(
            doc["boundaries"][0].replace("仅使用隔离合成只读来源：", "隔离合成来源：")
        )
    elif mutation == "missing_revision_label":
        doc["boundaries"][0] = doc["boundaries"][0].replace("修订：", "")
    elif mutation == "missing_digest_label":
        doc["boundaries"][0] = doc["boundaries"][0].replace("SHA256：", "")
    elif mutation == "selection":
        doc["requirements"][0]["selected"]["revision_id"] = "changed"
    elif mutation == "prose":
        doc["boundaries"][0] = "请参考" + doc["boundaries"][0]
    else:
        doc["boundaries"][0] = doc["boundaries"][0][:-1]
    with pytest.raises(PlanningConflict):
        approved_source(type(sem).model_validate(doc))
