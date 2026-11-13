# F3 original work history READ continuity — G1

The coordinator approved this bounded plan before implementation: reuse the explicit history-access POST to renew only previously granted exact READ targets derived from the original owned conversation and work; reject revoked/denied grants and preserve execution, model, budget and history. The subsequent approved clarification separates ontology historical READ from execution USE according to accepted ONTOLOGY-SALES-01 sections 5–6.

## Components and interfaces

- Existing `POST /conversations/{id}/history-access`, CSRF and current account/policy deadline remain the entry. GET does not issue grants.
- Derive current journal problem revision/digest from exact conversation link, original context_call_objects binding, actual original SUCCEEDED/DRAFT_READY invocation, current policy configuration, same subject/domain and non-revoked context. No arbitrary latest invocation.
- For original prepared execution, require its prepared_by subject and immutable problem/source references to match the original work. Derive only exact BUSINESS_PROBLEM READ, EXECUTION READ, KNOWLEDGE READ_RESOURCE and RUNTIME_PROFILE READ_RESOURCE. Ontology projection adds exact BUSINESS_ONTOLOGY READ; never USE.
- Every renewal requires a prior grant, current owner target validation and original request purpose/requestability. Existing history request/decision/audit and expiry bounded by 8h/current authorized window are reused. No wildcard, new ledger, quota, migration or model call.
- Native progress currently goes through `native_interaction.records -> resource_read_grants`, whose ontology entry is USE. Accepted architecture requires READ for historical exact content and USE for execution. A local `projection_read_grants` changes only the historical records/progress requirement to exact ontology READ. The global execution helper, `answer -> app.validate`, START, retry and runtime USE remain unchanged.

## Compatibility and risks

Old conversations without a formal work journal keep existing draft-history behavior. Work history renewal requires the configured relation capability and original scoped policy; a general owned context requires its exact original policy and message ownership as well as a previously granted work READ. This cannot create work permissions from ordinary question-only authority. Expired old call leases may be read, but explicit context/grant revocation or rejection blocks renewal. An expired execution grant is never restored as execution authority. UNKNOWN and historical model records are untouched.

Source metadata mismatch, prepared owner mismatch, changed problem revision, or missing exact origin fails closed. A denied ontology READ blocks progress; an expired/revoked USE alone must not erase authorized historical progress, while answering still fails execution validation. No public CRD or frozen runtime contract change.

## Validation plan and current status

Executed isolated validation:

- `C1_WORK_HISTORY_G1_TEST_R1.txt`: 37 passed / 1 skipped, 83.91s. This combines five new real BFF/history-authority cases, prepared-target fixtures, prior history regression and Native progress regression. The skipped old `test_native_interaction.py:21` requires a separate exclusive 323 database; it was not forced onto the real platform.
- `C1_WORK_HISTORY_G1_PROJECTION_R2.txt`: four separately rerun cases / 0.70s after adding START-effective/USE-denied answer coverage. These are controlled authority checks through actual progress and PreparedExecutionApplication code, not separate real provider calls.
- `C1_WORK_HISTORY_G1_BFF_R3.txt`: eight passed / 9.10s. One actual isolated BFF/session/administrator-grant test proves exact ontology READ allows GET with expired USE, START alone cannot answer when USE expired, and READ for another version cannot replace expired original-version READ. Seven exact prepared-target positive/negative cases use canonical typed metadata fixtures.

The BFF projection fixture inserts a canonical prepared candidate and supplies a bounded exact-target registry; it does not claim a real Approved Plan or Native execution. Actual grant requests/decisions, session identity, BFF owner authorization and PostgreSQL reads are exercised. The snapshot compares all existing execution_authority, skill_invocation and business_problem_authority tables, along with journal/messages/links, model invocation versions and budget reservations/settlements. No execution/model write occurs.

Ruff and formatting checks pass. Coordinator integrated full-hook and real C1 original-request acceptance remain pending. No model configuration, migration, real runtime or user approval record was changed by this package.
