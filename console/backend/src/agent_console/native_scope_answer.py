# ruff: noqa: RUF001 -- Deliberate Chinese scope-confirmation punctuation.
"""Bound a conservative scope interpretation to the saved current question."""

import re

from .native_confirmed_scope import classify_scope

_UNCERTAIN = (
    r"不确定|未确定|待确认|可能|或许|也许|还是|或者|假设|如果|原话|原文|引用|例如|示例|"
    r"\b(?:maybe|whether|either|perhaps|if|quote)\b"
)
_CONTRADICTION = (
    r"不|没|否|别|未|待|但是|不过|但|改|换|其他|另一个|除外|"
    r"\b(?:no|not|don't|but|instead|except|other)\b"
)


def _constraints_removed(text):
    # A no-effect constraint is not a rejection of the policy scope. Remove only
    # these complete restrictive clauses, not arbitrary text following 'not'.
    return re.sub(
        r"(?:不|不要)(?:执行|进行)(?:真实)?(?:上线|回退|部署|写入)"
        r"(?:(?:或|和|与|/)(?:上线|回退|部署|写入))*"
        r"|\b(?:do not|don't)\s+(?:deploy|write|roll back)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _affirmative(text):
    # Only a fully understood confirmation plus referential/read-only tails.
    # Unknown free-text continuations are not silently treated as consent.
    clauses = [
        part.strip() for part in re.split(r"[，,。；;！!\n]", text) if part.strip()
    ]
    if (
        not clauses
        or re.fullmatch(
            r"对|是的|确认|同意|可以|没错|yes|confirmed|correct|agreed",
            clauses[0],
            re.IGNORECASE,
        )
        is None
    ):
        return False
    for clause in clauses[1:]:
        if not _constraints_removed(clause).strip():
            continue
        if re.fullmatch(
            r"(?:只|仅)(?:检查|核查|核对|分析|审阅)"
            r"(?:(?:这份|该份|上述|当前)(?:合成)?(?:交接)?|合成)"
            r"(?:材料|资料|文档|说明|内容)",
            clause,
        ):
            continue
        if re.fullmatch(
            r"(?:请)?继续(?:并(?:把|将)?(?:遗漏|冲突|结果|结论)"
            r"(?:(?:和|与|及|、)(?:遗漏|冲突|结果|结论))*"
            r"返回(?:这里|本会话|当前会话))?"
            r"|(?:please )?continue",
            clause,
            re.IGNORECASE,
        ):
            continue
        return False
    return True


def confirmed_answer_scope(
    answer, scopes, *, question=None, previous=None, policy_labels=()
):
    """No scope/permission inference from arbitrary model prose or old answers."""
    available = tuple(dict.fromkeys(scopes))
    text = answer.strip()
    mentioned = [scope for scope in available if scope in text]
    if mentioned:
        if len(mentioned) != 1 or re.search(_UNCERTAIN, text, re.IGNORECASE):
            return None
        if text == mentioned[0]:
            return mentioned[0]  # Explicit selection, compatible with old clients.
        direct = re.sub(r"^(?:确认|是的|对)[，,：:\s]+", "", text)
        choice = classify_scope(
            [{"message_id": "current-answer", "content": direct}], available
        )
        # An explicit known scope does not license arbitrary contradictory tails.
        clauses = [
            part.strip()
            for part in re.split(r"[，,。；;！!\n]", direct)
            if part.strip()
        ]
        explicit = (
            r"(?:(?:请|帮我|麻烦|本次|这次|仅)\s*)*(?:按|按照|使用|采用|依据)"
            r"\s*[“「\"]?"
            + re.escape(mentioned[0])
            + r"[”」\"]?(?:交接规范|规范|范围)?(?:检查|核查|核对|审阅|分析)?"
            r"|(?:please\s+)?(?:use|apply)\s+"
            + re.escape(mentioned[0])
            + r"(?:\s+(?:policy|scope))?"
        )
        if (
            not choice
            or not clauses
            or re.fullmatch(explicit, clauses[0], re.IGNORECASE) is None
            or not _affirmative("确认，" + "，".join(clauses[1:]))
        ):
            return None
        return choice["scope"]
    remaining = _constraints_removed(text)
    if re.search(
        r"范围|规范|环境|政策|\b(?:scope|policy|environment)\b",
        remaining,
        re.IGNORECASE,
    ) or (
        re.search(
            r"取消|撤回|撤销|暂停|停止|不|别|先等|\b(?:cancel|stop|withdraw|not)\b",
            remaining,
            re.IGNORECASE,
        )
        and re.search(
            r"检查|前面|之前|原来|先前|先等|\b(?:check|previous|wait)\b",
            remaining,
            re.IGNORECASE,
        )
    ):
        return None  # Unknown new scope or explicit withdrawal is not unrelated.
    if not question:
        return previous
    proposed = [scope for scope in available if scope in question]
    if not proposed:
        return previous  # An unrelated question must not erase an earlier scope.
    if len(proposed) != 1 or re.search(_UNCERTAIN, question, re.IGNORECASE):
        return None
    q = _constraints_removed(question.strip())
    q = re.sub(r"是否(?=按|按照|使用|采用|依据)", "", q)
    if re.search(_CONTRADICTION, q, re.IGNORECASE):
        return None
    scope = proposed[0]
    proposition = re.match(
        r"^(?:请(?:明确)?确认(?:一下)?[：:]?\s*(?:本次|这次)?"
        r"(?:是否)?(?:按|按照|使用|采用|依据|适用的(?:规范)?范围(?:为|是))"
        r"|(?:please )?confirm (?:use|apply) )"
        r"\s*[“「\"]?"
        + re.escape(scope)
        + r"[”」\"]?(?:交接规范|规范|适用范围|范围|\s+policy)?(?=[，,。；;？?\s（(]|$)",
        q,
        re.IGNORECASE,
    )
    if proposition is None:
        return None
    # Exact labels from the already-loaded POLICY of this scope are references,
    # not a second scope proposition. Never learn a label from model/user prose.
    tail = q[proposition.end() :]
    for label_scope, label in policy_labels:
        if label_scope == scope and label:
            tail = tail.replace(label, "")
    # A second unrecognized scope proposition is not confirmed by a leading yes.
    if re.search(
        r"环境|范围|规范|政策|拒绝|取消|撤回|\b(?:scope|policy|environment)\b",
        tail,
        re.IGNORECASE,
    ):
        return None
    return scope if _affirmative(text) else None


def record_bound_answer(library, question, reply):
    """Called only after await_answer verifies the persisted owner question key."""
    if (
        reply.get("question") != question
        or not isinstance(reply.get("answer"), str)
        or not isinstance(reply.get("questionDigest"), str)
        or re.fullmatch(r"[0-9a-f]{64}", reply["questionDigest"]) is None
    ):
        raise ValueError("NATIVE_SCOPE_ANSWER_BINDING_MISMATCH")
    library.record_answer(reply["answer"], question=question)
