# Recovery waiting presentation

G1 frontend-only adjustment for this recovery path. Show the server-observed
pending recovery as waiting for review, in conversation and progress rail. Retain
old UNKNOWN and stream error inside collapsed details; never rewrite journal,
authorization, budget, or original result. Pending observation refresh uses GET
only; approval still requires explicit continue. Manual refresh is secondary.

Input diagnosis: PLAN/pending has no ConversationAnswer slot. Existing scratch
input is rendered only for clarification/source mismatch or an UNKNOWN-code
branch; a localized stream error does not match that code. No input data is
removed. Existing conversation messages/journal and scoped scratch storage remain
unchanged; this package does not add an input or submission path.

Verification: six browser cases passed, including pending/authorized/UNKNOWN,
current request locators, approval withdrawal, and periodic GET transition to
AUTHORIZED with zero POST/model calls and unchanged original journal. Frontend
lint/build passed. Waiting and authorized screenshots were inspected. Existing
ConversationAnswer/useViewString stores unsent text in scoped sessionStorage and
clears only after successful explicit send; those modules are unchanged. This is
source evidence of preservation, not a new waiting-state input capability.
