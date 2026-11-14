# Execution preparation feedback (G1)

Base 9b79bc2. Observed ONTOLOGY_EXECUTOR_BINDING_MISMATCH on the execution
preparation path is displayed as a technical error and a resource-ready log
prematurely claims execution. This patch changes presentation only.

For RESOURCES/EXECUTE with no saved execution reference and the exact binding
error, present execution preparation paused: the resource/check-rule binding
was not verified; original question and plan remain. Do not assert either that
execution started or that nothing executed. Preserve the existing explicit
readback and same-plan recovery gate; no new POST, retry or authority.

Show the original code only inside technical details. Reuse the same business
feedback in the right-side progress. Resource preparation READY records readiness
for start-condition checks, not execution. Only returned executionStarted=true
can label a returned start receipt; task activity still comes from owner progress.
For existing historical premature log wording, normalize that exact presentation
string without rewriting its journal. Existing execution/terminal/UNKNOWN records
and unrelated errors keep their existing behavior.

Browser tests: original binding error and historical log across reload, no model
or execution POST, no invented absence; technical details remain available;
resource READY followed by binding error does not claim execution; accepted
receipt log and readback remain distinct. No backend or real runtime changes.

Prototype follow-up: for this precise saved preparation error and exact confirmed
plan, automatically use the existing read-only continuation GET once per bound
view (including refresh); never POST. Original NOT_FOUND owner reason alone sets
the existing exact absence token. Only that verified token permits the stronger
not-started wording; unauthorized/unknown/unavailable read retains uncertainty.
A valid existing start receipt follows existing strict target/subject/digest checks
and reads the original execution. Recovery controls sit inside details, not an
instruction to the user to repair configuration. State explicitly that no further
business materials are currently requested. No generated timestamps.

The binding feedback alone preserves the existing stage-list structure: first two
stages done, resources paused (no running/current highlight). Execution/results
show not started only with verified absence, otherwise pending verification. Other
feedback branches remain unchanged. No stage carries aria-current during pause.
