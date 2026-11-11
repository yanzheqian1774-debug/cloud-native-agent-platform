"""Canonical preparation for existing Problem/Criteria owners, not admission."""

from copy import deepcopy


def work_input(resolved):
    contract = resolved["contract"]
    return {
        "problem": {
            "title": contract["objective"][:200],
            "description": contract["objective"],
        },
        "criterion": {
            "criterionType": "HUMAN_EVALUATED",
            "measurement": {"rubric": "\n".join(contract["acceptanceCriteria"])},
            "requiredEvidenceKinds": [],
            "evaluatorType": "HUMAN",
            "evaluatorVersion": "v1",
            "applicability": {
                "capabilityContractDigest": resolved["contractDigest"],
                "capabilityConstraints": deepcopy(contract),
            },
        },
    }
