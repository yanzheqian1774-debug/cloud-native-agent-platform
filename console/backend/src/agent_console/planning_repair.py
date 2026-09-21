"""Deterministic language-only repair guard, not a natural-language truth judge."""

import re
from copy import deepcopy


def _node(document, path):
    node = document
    for key in path[:-1]:
        node = node[key]
    return node, path[-1]


def language_repair_issues(source, revised, paths):
    before, after = deepcopy(source), deepcopy(revised)
    errors = []
    for path in paths:
        try:
            left, key = _node(before, path)
            right, other = _node(after, path)
            # Numbers, dates and quoted technical identifiers are not translation.
            protected = r"\d+(?:[.,:/-]\d+)*|`[^`]+`|https?://\S+"
            if re.findall(protected, left[key]) != re.findall(protected, right[other]):
                errors.append({"path": path, "rule": "REPAIR_PROTECTED_VALUE_CHANGED"})
            left[key] = right[other] = "<language-repair>"
        except (KeyError, IndexError, TypeError):
            errors.append({"path": path, "rule": "REPAIR_FIELD_REMOVED"})
    if before != after:
        errors.append({"path": [], "rule": "REPAIR_UNRELATED_STRUCTURE_CHANGED"})
    return errors[:16]
