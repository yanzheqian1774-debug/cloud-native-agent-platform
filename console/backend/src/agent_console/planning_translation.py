"""Exact-source display projection; never changes Plan or Approval authority."""

import json
import re
from copy import deepcopy
from pathlib import Path

from .business_problem_domain import canonical_digest


def display_translation(proposal):
    record = json.loads(
        Path(__file__).with_name("cost_plan_translation.json").read_text()
    )
    if (
        proposal.proposal_id != record["proposal_id"]
        or proposal.revision != record["revision"]
        or proposal.digest != record["source_digest"]
    ):
        return None
    digest = record.pop("translation_digest")
    if canonical_digest(record) != digest:
        raise ValueError("PLAN_TRANSLATION_INTEGRITY_INVALID")
    semantics = deepcopy(proposal.semantics.model_dump(mode="json"))
    for path, text in record["fields"].items():
        keys = path.split("/")
        if not re.fullmatch(
            r"(?:stages/\d+/title|tasks/\d+/(?:title|responsibility|(?:inputs|outputs)/\d+)"
            r"|requirements/\d+/(?:name|purpose|preparation)|(?:business_rules|boundaries)/\d+)",
            path,
        ):
            raise ValueError("PLAN_TRANSLATION_FIELD_INVALID")
        node = semantics
        for key in keys[:-1]:
            node = node[int(key)] if isinstance(node, list) else node[key]
        key = int(keys[-1]) if isinstance(node, list) else keys[-1]
        node[key] = text
    return {
        "semantics": semantics,
        "metadata": {**record, "translation_digest": digest},
    }
