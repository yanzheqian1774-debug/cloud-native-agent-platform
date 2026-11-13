"""Finite question definitions from loaded read-only resources, never permissions."""

from agent_runtime.native_loop import digest

SCHEMA = "native-question-answer.v1"


def scope_contracts(library):
    source_digest = digest(library.source)
    bound_scope = getattr(getattr(library, "binding", None), "scope", None)
    candidates = [
        {
            "id": "policy-scope:" + digest([source_digest, d["id"], digest(d)]),
            "label": d["scope"],
            "resourceId": d["id"],
            "contentDigest": digest(d),
        }
        for d in library.documents.values()
        if d["role"] == "POLICY" and (bound_scope is None or d["scope"] == bound_scope)
    ]
    contracts = []
    for proposed in candidates:
        value = {
            "schemaVersion": SCHEMA,
            "kind": "POLICY_SCOPE",
            "sourceSnapshotDigest": source_digest,
            "sourceReference": library.reference,
            "candidates": candidates,
            "proposedCandidateId": proposed["id"],
        }
        contracts.append({**value, "contractDigest": digest(value)})
    return contracts


def validate_contract(value):
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "kind",
        "sourceSnapshotDigest",
        "sourceReference",
        "candidates",
        "proposedCandidateId",
        "contractDigest",
    }:
        raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    if value["schemaVersion"] != SCHEMA or value["kind"] != "POLICY_SCOPE":
        raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 12:
        raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {
            "id",
            "label",
            "resourceId",
            "contentDigest",
        }:
            raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
        if not all(isinstance(v, str) and v for v in candidate.values()):
            raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    ids = [candidate["id"] for candidate in candidates]
    if len(set(ids)) != len(ids) or value["proposedCandidateId"] not in ids:
        raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    if value["contractDigest"] != digest(
        {k: v for k, v in value.items() if k != "contractDigest"}
    ):
        raise ValueError("NATIVE_QUESTION_CONTRACT_INVALID")
    return value


def validate_meaning(value, contract):
    validate_contract(contract)
    if not isinstance(value, dict) or set(value) != {
        "decision",
        "candidateId",
        "questionContractDigest",
    }:
        raise ValueError("NATIVE_QUESTION_MEANING_INVALID")
    if value["questionContractDigest"] != contract["contractDigest"]:
        raise ValueError("NATIVE_QUESTION_MEANING_INVALID")
    decision, candidate = value["decision"], value["candidateId"]
    if not isinstance(decision, str) or (
        candidate is not None and not isinstance(candidate, str)
    ):
        raise ValueError("NATIVE_QUESTION_MEANING_INVALID")
    legal = {entry["id"] for entry in contract["candidates"]}
    valid = (
        (decision == "CONFIRM" and candidate == contract["proposedCandidateId"])
        or (
            decision == "CHANGE"
            and candidate in legal
            and candidate != contract["proposedCandidateId"]
        )
        or (decision in {"REJECT", "UNCLEAR"} and candidate is None)
    )
    if not valid:
        raise ValueError("NATIVE_QUESTION_MEANING_INVALID")
    return value


def resolve_contract(library, contract_id):
    matches = [
        c for c in scope_contracts(library) if c["contractDigest"] == contract_id
    ]
    if len(matches) != 1:
        raise ValueError("NATIVE_QUESTION_CONTRACT_NOT_AVAILABLE")
    return matches[0]


def consume_interpretation(library, contract, interpretation):
    """Called only after the answer owner has verified the persisted model result."""
    if interpretation.get(
        "schemaVersion"
    ) != "native-verified-question-answer.v1" or interpretation.get(
        "interpretationDigest"
    ) != digest(
        {k: v for k, v in interpretation.items() if k != "interpretationDigest"}
    ):
        raise ValueError("NATIVE_QUESTION_INTERPRETATION_NOT_VERIFIED")
    if resolve_contract(library, contract["contractDigest"]) != contract:
        raise ValueError("NATIVE_QUESTION_SOURCE_CHANGED")
    meaning = {
        k: interpretation[k]
        for k in ("decision", "candidateId", "questionContractDigest")
    }
    validate_meaning(meaning, contract)
    if meaning["decision"] in {"REJECT", "UNCLEAR"}:
        library.confirmed_scope = None
        return
    candidate = next(
        c for c in contract["candidates"] if c["id"] == meaning["candidateId"]
    )
    policy = library.documents[candidate["resourceId"]]
    if policy["role"] != "POLICY" or digest(policy) != candidate["contentDigest"]:
        raise ValueError("NATIVE_QUESTION_SOURCE_CHANGED")
    library.confirmed_scope = policy["scope"]
