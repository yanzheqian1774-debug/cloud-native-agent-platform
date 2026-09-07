# S5-V023-IMPL-281 evidence checkpoint

## Continuity and authorization

- Workspace: `/Users/tristan/.codex/worktrees/2d1c/cloud-native-agent-platform`
- Branch/base: `codex/s5-v023-impl-281-digital-employee-level-2` at `8160adbc04ff1508ba5c9d093407edf5948be611`
- The prior 281 executor stopped with `systemError`; this task is the only active 281 writer. Task metadata shows 282 modifies migration 0015, Knowledge attempt and Resource Use paths only; no path in this compatibility fix overlaps 282.
- On 2026-09-07 Human explicitly extended 281 to repair the HTTP/Employee composition digest compatibility defect, add necessary backend tests, and retain this evidence file. This is the authorization source for the backend changes; the earlier read-only takeover diagnosis was not retroactive backend authorization.

## Compatibility repair

- Workflow and Runtime Profile authorities persist SHA-256 revision digests as `sha256:` plus exactly 64 lowercase hexadecimal characters. Their existing Agent binding resolvers expose the same SHA-256 value as exactly 64 lowercase hexadecimal characters. Those public and internal representations remain unchanged.
- `PostgresEmployeeDefinitionRepository.validate_members` now parses only those two exact SHA-256 encodings and compares their decoded 32-byte values with `hmac.compare_digest`. Wrong algorithms, lengths, casing, prefixes and values remain rejected.
- The comparison does not mutate either resource record or Employee member record. Employee revision digest calculation is unchanged and continues to cover the originally supplied member representation.
- Unified reads the verified Workflow/Runtime binding projection back through the formal Agent HTTP response and supplies it directly to Employee composition. It does not read database values or add a prefix.
- The isolated browser harness now supplies its already validated task PostgreSQL URL as `EXECUTION_DATABASE_URL`; without this existing Digital Employee assembly intentionally returned storage unavailable.

## Validation

- Focused backend: `20 passed`, including strict encoding controls, wrong digest/revision/ID rejection, Agent member regression coverage, Workflow/Runtime binding compatibility, publication lifecycle, and unchanged source/Employee history; one existing Starlette/httpx deprecation warning.
- Harness regression after its source change: `150 passed`.
- Targeted backend Ruff and format checks: PASS. Unified ESLint: PASS. Candidate frontend TypeScript/Vite build: PASS with the existing chunk-size warning.
- Complete Unified durable scenario: PASS through the isolated harness; browser code 0, two owned restarts, identical before/after release manifest digest, and no first-failure record. Minimum-disclosure evidence: `/private/tmp/s5-281-digest-fix-unified-pass.m2Z1DC/runtime/acceptance-evidence.json`.
- Wave 3B isolated follow-up: 3 selected, 2 passed, 1 failed. The independent failure remains `WAVE3B_08_CONFLICT_RECOVERY` after `WAVE3B_07_KNOWLEDGE_HIERARCHY`, with scenario timeout. Evidence: `/private/tmp/s5-281-digest-fix-unified-pass.m2Z1DC/runtime-wave3b/acceptance-evidence.json` and its minimum-disclosure first-failure record.
- The conflict journey now has fixed top-level allowlisted steps for navigation, stale preparation, conflict write, error UI, authoritative readback, explicit recovery and final assertion. Four related synthetic harness checks pass; 148 unrelated harness tests were not rerun. Targeted Ruff/format and Wave-spec ESLint pass.
- The first diagnostic rerun established a scenario timeout at `240090ms`: `WAVE3B_08_MAKE_STALE` completed in `30ms`, while `WAVE3B_08_CONFLICT_WRITE` consumed `231737ms`. The page request was not sent because the test had not waited for its asynchronous catalog selection to finish; a late authoritative refresh could observe the externally created successor and remove the stale-page action. Waiting for the successor action before advancing the authority makes the stale setup deterministic without changing product behavior, timeout, retries or assertions.
- The corrected Wave 3B scenario passed through the immutable owned harness. A subsequent complete run exposed an independent mobile Evidence focus failure after close. `EvidencePage` previously stopped focus restoration after ten animation frames, before a loaded Product projection necessarily rendered. It now observes the page until the exact claim/fact target appears, focuses it once, and does not install an observer for Catalog returns that have no focus target. Workflow frontend and backend remained read-only.
- Two intermediate candidates were built without `VITE_SUPPLIER_QUALITY_DEMO_MODE=live`; their early Catalog failures are invalid environment runs and are excluded from product evidence. The source was rebuilt with the required live flag before final validation.
- Final Wave 3B and complete Browser Acceptance both pass on the corrected immutable `LIVE_DEMO` candidate with clean, exclusive PostgreSQL/Qdrant, one worker and zero retries. The complete harness performed five owned backend restarts and preserved the exact release manifest (`4c87905589e2a5cf4f5d58fe0b8b357ade037ddd089c1c093b37501743d019cf`) before and after. Evidence: `/private/tmp/s5-281-focus-fix-c916/runtime-wave/acceptance-evidence.json` and `/private/tmp/s5-281-focus-fix-c916/runtime-full/acceptance-evidence.json`.

No request body, credential, raw response, or dynamic business data is copied into this checkpoint. Existing staged/unstaged/untracked changes were preserved; nothing was reset, restored, or stashed.
