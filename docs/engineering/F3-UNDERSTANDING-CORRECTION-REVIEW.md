# F3 understanding and corrected-goal propagation

Baseline reviewed: 12dade1. Candidate-only; no deployment or real-model acceptance.

| Requirement | Existing behavior / evidence boundary |
| --- | --- |
| Simple question without task linking | V3 DIRECT_ANSWER saves a reply and stops before resource discovery or problem creation. Controlled browser coverage; real model routing requires installed-platform acceptance. |
| Necessary clarification in original conversation | V3 NEEDS_CLARIFICATION uses the fixed composer and a predecessor invocation. Native execution clarification has separate existing coverage; this change does not modify it. |
| Corrections kept through task creation | Latest understanding draft creates a problem revision, but downstream criteria and routing still used the original question. This candidate fixes that mismatch. |
| Accurate failure presentation | Settled schema failure is distinct from missing data; UNKNOWN retains the request without automatic redispatch. Existing controlled tests cover both. |
| First model progress | Persisted pending state renders progress before output; stream content is provisional. No narration call is added. |

The completion rubric now takes the created problem revision's complete description.
The bounded planning-routing question takes that revision's title. Planning already
loads the complete current problem description and exact criteria through
`PlanSuggestionApplication.current_input`; it does not depend on an old draft for
this context. The original question and conversation messages remain unchanged.
Missing fields in legacy journal projections retain their existing question fallback;
newly created owner revisions contain both title and description.

Regression coverage follows a controlled clarification response, a user correction,
a corrected model output, problem creation, criteria creation and the planning input.
Both short and over-500-character descriptions are covered: routing does not truncate
the full goal or exceed its 500-character request bound. Reload must not duplicate
owner writes or model requests. This verifies propagation, not model reasoning.

No Native executor, resource binding, budget policy, authorization, model configuration,
shared visual styles, frozen prototype or historical database record changes.
