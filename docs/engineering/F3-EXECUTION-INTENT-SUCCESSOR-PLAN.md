# G1: immutable execution-intent understanding successor

Actual evidence: document-tool-select-source-r1 returned DIRECT_ANSWER and explicitly
said no checking tool had been called, despite an explicit tool execution request.
V3 prohibits tools in the understanding call but does not clearly distinguish this
from preparing a governed task for later execution. An attached full source makes
a text-only answer possible. Generic source-selection follow-ups can also obscure
the preceding execution request.

Add v3-execution, with its own output schema and policy digest. Preserve V3 exact
instructions/schema/digest. Retain the existing input context and result kinds;
add a validated internal intent field ANSWER/TASK. TASK cannot produce DIRECT_ANSWER;
DRAFT_READY requires TASK. Missing data/necessary clarification may serve either
intent. This is one understanding call, not a second classifier. No lexical frontend
routing, forced DRAFT_READY, extra calls, or automatic retry on malformed outputs.

Clarify in the new instructions that only the understanding phase lacks execution
permission; an explicit request for tools/work must become a faithful pending task
or necessary missing-input question, never a substitute text result plus disclaimer.
Ordinary explanations and requested textual comparisons remain direct. Attached
source contents are evidence, not user instructions, and selecting a source does
not cancel an earlier execution request.

Touch only policy, OpenAI adapter accepted-version/validation paths, bootstrap,
capability API and corresponding tests. Existing frontend kind handling remains.
Do not import the wider v4 work-candidate/context dispatch candidate. Model owner
registration/publication/runtime selection are separate gates. Prepare the exact
candidate configuration as NEEDS_HUMAN_REVIEW, never HUMAN_REVIEWED.

Validation: legacy V3 golden digest, valid/invalid intent-kind combinations, mocked
HTTPS single-request contract and source attachment, runtime policy digest binding,
API capability, no replay on validation failure. These checks do not prove semantic
routing quality; mainline real-model execution is still required after approval.

A successor profile must also reuse the existing shared ledger. Permit the existing
profilePricingRootDigest configuration only for the new exact understanding
revision/schema pair (and already supported planning). Pass it to the existing
PostgresProviderCallBudget owner, which requires an explicitly prepared append-only
pricing revision. Do not modify the budget owner, allowance, cap/window, original
V3 profile, ledger or historic reservations. Candidate configuration includes exact
pricing record and unchanged allowance reference; runtime preparation remains a
mainline operation after review, not a side effect of startup or these tests.
