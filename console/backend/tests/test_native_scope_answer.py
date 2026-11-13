# ruff: noqa: RUF001 -- Exact original Chinese question/answer regression.
"""Bound confirmation is generic scope interpretation, never execution authority."""

from copy import deepcopy

import pytest
from agent_console.native_document_tools import NativeDocumentTools
from agent_console.native_scope_answer import (
    confirmed_answer_scope,
    record_bound_answer,
)
from test_native_document_tools import REFERENCE, SOURCE

Q = "请确认：本次按“生产环境”交接规范，仅检查合成交接材料，不执行真实上线或回退，对吗？"
A = "对，只检查这份合成交接材料，不执行上线或回退。请继续并把遗漏和冲突返回这里。"


@pytest.mark.parametrize("scope", ["生产环境", "测试环境", "审计范围甲"])
def test_bound_affirmation_uses_actual_policy_scope_not_literal_production(scope):
    q = Q.replace("生产环境", scope)
    assert confirmed_answer_scope(A, [scope], question=q) == scope


@pytest.mark.parametrize(
    "answer",
    [
        "不要按生产环境规范检查。",
        "不是生产环境。",
        "不确定，可能是生产环境。",
        "按生产环境还是测试环境？",
        "“按生产环境规范检查”是原话。",
        "对，但是不要按生产环境。",
        "对，不过我不确定。",
        "对，不执行上线或回退，但不要采用这个范围。",
        "对，改成其他范围。",
        "如果是生产环境就可以。",
        "否",
    ],
)
def test_denial_uncertainty_and_contradiction_never_confirm(answer):
    assert confirmed_answer_scope(answer, ["生产环境", "测试环境"], question=Q) is None


@pytest.mark.parametrize(
    "question",
    [
        "请确认：不按生产环境规范，对吗？",
        "请确认：按生产环境或者测试环境？",
        "请确认：假设按生产环境规范，对吗？",
        "文档原话是按生产环境规范，你收到了吗？",
        "请确认：不用生产环境规范，对吗？",
    ],
)
def test_affirmation_does_not_promote_negative_or_reported_question(question):
    assert (
        confirmed_answer_scope("对", ["生产环境", "测试环境"], question=question)
        is None
    )


def test_explicit_answer_and_unrelated_question_preserve_only_proved_scope():
    assert (
        confirmed_answer_scope(
            "确认，按生产环境规范检查，不执行上线或回退。", ["生产环境"], question=Q
        )
        == "生产环境"
    )
    assert (
        confirmed_answer_scope(
            "请返回这里", ["生产环境"], question="结果发送到哪里？", previous="生产环境"
        )
        == "生产环境"
    )
    assert (
        confirmed_answer_scope("不确认", ["生产环境"], question=Q, previous="生产环境")
        is None
    )


def test_real_document_library_review_after_exact_pair_no_repeated_scope_question():
    source = deepcopy(SOURCE)
    source["documents"][2]["scope"] = "生产环境"
    library = NativeDocumentTools(source, REFERENCE)
    args = {"documentId": "submission", "policyId": "production"}
    assert library.invoke("review_document", args)["state"] == "NEEDS_CLARIFICATION"
    reply = {"question": Q, "answer": A, "questionDigest": "a" * 64}
    record_bound_answer(library, Q, reply)
    assert library.invoke("review_document", args)["missingSections"] == [
        "Verification"
    ]
    assert source == library.source
    record_bound_answer(
        library, "结果返回哪里？", dict(reply, question="结果返回哪里？", answer="这里")
    )
    assert library.confirmed_scope == "生产环境"
    record_bound_answer(library, Q, dict(reply, answer="不要按生产环境规范检查。"))
    assert library.invoke("review_document", args)["state"] == "NEEDS_CLARIFICATION"


@pytest.mark.parametrize(
    "change", [dict(question="another"), dict(questionDigest="bad"), dict(answer=None)]
)
def test_invalid_pair_does_not_change_existing_scope(change):
    library = NativeDocumentTools(SOURCE, REFERENCE)
    library.record_answer("production")
    with pytest.raises(ValueError, match="BINDING_MISMATCH"):
        record_bound_answer(
            library, Q, dict(question=Q, answer=A, questionDigest="a" * 64) | change
        )
    assert library.confirmed_scope == "production"


@pytest.mark.parametrize(
    "answer",
    [
        "对，只检查测试环境。",
        "对，我选择测试环境。",
        "对，拒绝这个范围。",
        "对，我还有别的条件。",
        "对，执行上线。",
    ],
)
def test_short_yes_does_not_ignore_unknown_or_conflicting_tail(answer):
    assert confirmed_answer_scope(answer, ["生产环境"], question=Q) is None


@pytest.mark.parametrize("question", [None, "请确认报告格式。"])
def test_scope_withdrawal_invalidates_previous_even_for_unrelated_question(question):
    assert (
        confirmed_answer_scope(
            "取消之前的检查范围，先等我确认。",
            ["生产环境"],
            question=question,
            previous="生产环境",
        )
        is None
    )


@pytest.mark.parametrize(
    "answer",
    [
        "按生产环境规范检查，只检查测试环境。",
        "按生产环境规范检查，拒绝上述范围。",
        "按生产环境规范检查测试环境。",
    ],
)
def test_explicit_known_scope_cannot_hide_unrecognized_correction(answer):
    assert confirmed_answer_scope(answer, ["生产环境"], question=Q) is None


@pytest.mark.parametrize(
    "question",
    [
        "请确认按生产环境规范，仅检查测试环境，对吗？",
        "请确认先按测试规范，然后按生产环境规范，对吗？",
    ],
)
def test_question_cannot_smuggle_unknown_scope_proposition(question):
    assert confirmed_answer_scope("对", ["生产环境"], question=question) is None


def test_actual_second_confirmation_references_exact_loaded_policy_heading():
    q = (
        "请确认：本次是否按“生产环境”适用范围，依据所提供的生产上线交接检查规范"
        "核对“模拟发布001”（仅检查合成资料，不执行上线或回退）？"
    )
    assert (
        confirmed_answer_scope(
            "对",
            ["生产环境"],
            question=q,
            policy_labels=[("生产环境", "生产上线交接检查规范")],
        )
        == "生产环境"
    )
    assert (
        confirmed_answer_scope(
            "对",
            ["生产环境"],
            question=q,
            policy_labels=[("测试环境", "生产上线交接检查规范")],
        )
        is None
    )
    assert confirmed_answer_scope("对", ["生产环境"], question=q) is None
    assert (
        confirmed_answer_scope(
            "对，只检查测试环境",
            ["生产环境"],
            question=q,
            policy_labels=[("生产环境", "生产上线交接检查规范")],
        )
        is None
    )
