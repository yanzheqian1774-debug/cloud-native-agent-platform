"""Explicit immutable wire successor, separate from every published v3 policy."""

from .conversation_typed_answer_policy import INSTRUCTIONS as PREDECESSOR
from .structured_understanding_wire import REVISION as REVISION
from .structured_understanding_wire import VERSION, template_schema

SCHEMA = template_schema()
SCHEMA_VERSION = VERSION
INSTRUCTIONS = (
    PREDECESSOR
    + """
WIRE VERSION conversation-understanding-wire.v4 overrides the previous JSON shape.
Return an object with one result property, matching exactly one supplied branch.
For DRAFT_READY/NEEDS_CLARIFICATION, understanding has five fixed properties goal,
scope, time, constraints, successCriteria, each containing value/source/sourceRefs,
and an openItems array of zero to seven entries with those same three properties.
Put each fact in its one appropriate property. Never repeat a property or invent
provenance. All prior business rules and sourceRefs restrictions still apply.
Copy the supplied exact currentQuestionToken only for CURRENT_QUESTION. Choose
another relation when the latest message does not answer that exact question.
The compiled schema narrows tokens and candidate IDs from the original sealed
server snapshot; these are references, not permissions. Do not fabricate values.
One response supplies the route and complete result. No tools or follow-up model
call are allowed. The platform validates, persists and adopts the result separately.
Compiler version: sealed-question-wire.v1. Decoder version: fixed-slots.v1.
"""
)
