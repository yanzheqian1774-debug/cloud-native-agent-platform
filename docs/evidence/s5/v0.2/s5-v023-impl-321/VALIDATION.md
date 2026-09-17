# S5-V023-IMPL-321 verification and recovery

Session OPEN; implementation authorization is the existing G1 plan. No Ready,
merge, release, deployment, cleanup, or Session closure is implied.

## Recovery identity

- Original task `01a0acd1-626a-7b00-a7fc-898f5d734fd3` ended in `systemError`
  (remote compaction transport failure); its implementation turn was failed.
- Original worktree and branch reused. Base source
  `e51334aa9780291b3d077a1edb698dca630a6b3f`, tree
  `535fdd12cd11e4f2a029f03170f2a100e0fd8b49`. Remote main was rechecked unchanged.
- No other 321 writer or active Playwright/build/database preparation process was
  found before takeover. No subagent, replacement branch, worktree or Session.
- Incremental recovery archive (modified/untracked files, binary diff, hashes,
  original browser failures):
  `/Users/tristan/.codex/visualizations/2026/09/17/01a0acf9-0260-76c0-8be0-aa4c92f5ab96/321-recovery-20260917T012944Z`.
- The old final Docker command completed with exit 0 and container ID
  `cc09ee568d385ae9d46e563e8aa3cd5f4500bc3f3c3b2a091861432d3916e2be`.
  Container `s5-v023-impl-321-postgres` was running, with only
  `127.0.0.1:55441 -> 5432/tcp`; database `s5_v023_impl_321_acceptance`
  initially had no relations or ledger. It was reused, never deleted or reset.
- Current local test runtime: `/tmp/s5-v023-impl-321-runtime` (private directory).
  HTTPS Workbench `127.0.0.1:19322`; deterministic HTTPS provider `127.0.0.1:19323`.
  Test-only trust and ephemeral local credentials/TLS are not deployment defaults.
- PR #179 fixed head `89a8dad42e8746d50248015e7c6f8a0cdff7918e` and #180
  `6cd4a644a5ad83976685f2d3019afdfce5ccf6a5` were OPEN/DRAFT when inspected.
  Overlaps: Kimi adapter (#179), draft domain and ProblemWorkspacePage (#180).
  Their recovery/diagnostic implementations were not received or overwritten.
  No overlap with their published frontend test configuration changes. Shared
  source compatibility remains an integration-owner review if they land first.

## Evidence categories (do not combine scores)

1. **Old engineering baseline:** recovered old task records report 75 passing
   domain/adapter tests on the fixed baseline. This is historical, not a new run.
2. **Old browser experiment:** `baseline-ui.json` / `baseline-ui.png` reproduce
   natural correction not adopted and an old draft remaining submitable.
3. **Mock interaction:** B01–B08 and additional race/length cases use page.route.
   They prove UI contracts, not PostgreSQL, real authorization or model quality.
4. **Real backend browser:** production Workbench/Authority/Problem/Draft owners,
   existing PG migrations, independent exact grants, and a local deterministic
   HTTPS Responses fixture. No page.route, direct DB Problem insertion, recovery
   endpoint, real provider, or 319 credential is used.
5. **Real model quality:** baseline and candidate remain `NOT_MEASURED`.

## Failure history preserved

- Original browser run: exit 1, B01/B02/B04/B05/B06 failed. The old writer fixed
  revision trimming, successor handling, a textbox locator and mock continuation
  expiry but did not rerun before interruption.
- `/tmp/s5-321-browser-recovery-01.log`: 22 passed, 2 failed. B05/B06 assumed
  READ after creator receipt. Added an explicit independent authorization journey.
- `/tmp/s5-321-browser-recovery-02.log`: 22 passed, 2 failed. Mock grant endpoints
  incorrectly returned a `result` envelope; their real DTO is top-level. Corrected
  the fixture to the production contract, retaining all disclosure assertions.
- `/tmp/s5-321-browser-recovery-03.log`: B05/B06 both passed after that correction.
- Initial dedicated server attempts failed before imports (missing source paths),
  then at the Workflow owner ledger compatibility check. Existing prerequisite SQL
  was retained; the missing owner ledger was registered through its existing port.
  `--resume` continued preparation; no database reset or duplicate seed was used.
- `/tmp/s5-321-real-01.log`: one passed, one failed. The first real invocation
  completed, but successor authorization was folded behind the previous draft.
  Fixed rendering to expose the current authorization action and fence old cards.
  The authorization-denial test proved zero additional provider calls.
- `/tmp/s5-321-targeted.log`: 102 passed, one existing Kimi slow-body deadline
  scenario failed with CONNECT_DEADLINE while builds/browsers ran concurrently.
  No assertion, timeout or deadline implementation was weakened. Full validation
  is run without concurrent browser builds to distinguish scheduling from logic.

## Quality-case audit

The 16-case JSON carries frozen synthetic inputs, human-review oracles and empty
real metrics. The original 16 parametrized Python/browser cases check envelope
shape and request transmission ONLY. They do not execute their semantic oracle;
none is scored as a quality PASS. Q13's field-edit behavior is exercised by B02;
Q14 additionally has a deterministic exact-repeat/overflow test. Schema tests
cover at most two questions, source-reference validity, unknown/suggestion labels,
authority-field rejection, size limits, profile policy identity and v1 rollback.
These are structural constraints; valid references do not prove entailment.
Q01–Q16 semantic fidelity, repeated-question rates, atomic-fact omissions and
manual-edit reductions all remain pending independently authorized real evaluation.

## Reproduction boundaries

Run `make check`, `npm run lint` and `npm run build` from their documented roots.
Mock UI: from `console/frontend`, use `playwright.s5-321.config.ts` and a NEW
`PLAYWRIGHT_OUTPUT_DIR`. Real UI: `playwright.s5-321-real.config.ts` with
`S5_321_RUNTIME_DIR` pointing to this task's private identity/credential directory.
The dedicated mock provider and browser server are under `console/backend/tests`;
set `PYTHONPATH=console/backend/src:core/src:runtime/src:operator/src` from repo root.
Use `--resume` for an existing database/runtime. Do not replay first initialization.
The real fixture preserves invocation history and the provider budget ledger.

Fresh acceptance preparation requires a new explicitly owned test database/runtime;
the supplied server refuses any database URL other than this task's isolated one.
No command here authorizes accessing 319 assets, clearing ledgers, or real calls.


## Completed isolated browser/PG result

- `/tmp/s5-321-browser-final-01.log`: **27 passed**, retries 0.
- `/tmp/s5-321-real-02.log`: **2 passed**, retries 0; no request routing/mock BFF.
- Formal Problem `14019ced-cc5f-5da2-bda5-c4a12358cec6`, revision 1, one browser
  create command; exact READ approval and refresh readback verified. Synthetic
  acceptance principal is local `human:alice` in this task's separate authority,
  never the 319 runtime identity or credentials.
- Ledger has 3 reservations/3 settlements, 3 model Evidence records, 3 Resource
  Uses; includes the first failed browser journey's completed first invocation.
  Six invocation identities (including rejected/pending history) are retained.
  Formal Problem/revision count is 1/1. See `pg-verification.json` for counts.
- No test sentinel正文 in the 14 queried auxiliary/budget/use/evidence tables.
  Confirmed Product content remains in the existing Business Problem owner.
- Screenshots visually inspected: current-understanding card and authorized
  readback preserve the final `<1%`, no-device-change constraint and explicit
  unknowns; criteria authorization remains separate. These are synthetic fixtures.
- Make-check first failure was a new Kimi test using the OpenAI fixture's response
  model ID, correctly rejected by exact binding. Test now uses Kimi's own model
  response fixture. No production binding check was changed to accept it.
- Final review also added legacy-envelope unwrapping to the deterministic v1
  fallback and a regression; it must not expose the JSON envelope as draft text.


## Final local gates

- `make check`: exit 0; **1851 passed, 200 skipped, 1 warning**. The 200 skips are
  existing external-service/dedicated-database conditions, not newly skipped tests.
  This task's actual PG/HTTPS acceptance is recorded separately above.
- `npm run lint`: exit 0. `npm run build`: exit 0 (also executed by the dedicated
  Playwright webServer); existing bundle-size advisory remains.
- Final mock suite `/tmp/s5-321-browser-final-02.log`: exit 0, **28 passed**, no
  retries. This includes IME/229/held Enter/Tab, stale input, manual fallback,
  field-edit correction, UNKNOWN same-key recovery and independent READ errors.
- Real HTTPS browser suite: **2 passed**. The later local changes were the manual
  fallback unsent-input guard and deterministic-v1 envelope compatibility; they do
  not modify the validated real v2 create/READ path. CI tests the committed source.
- `git diff --check` passed; changed source/evidence and untracked assets reviewed.
  Normal pre-commit hooks and remote CI are recorded in the final delivery receipt.
- No real provider/model quality run occurred. All Q01–Q16 real metrics remain
  NOT_MEASURED; optional real evaluation needs the separate gate document.


## Browser CI recovery — 2026-09-17

Original candidate: source `36737e7f726ebeeaec9a5099ee8d4619c928e7ef`,
tree `ce407a8fbfcf0243dcfb29585656365a6866546f`, Draft PR #181. Previous
writer `01a0acf9-0260-76c0-8be0-aa4c92f5ab96` is idle after compaction transport
failure. Its final command completed (exit 0 for inspection); the preceding
legacy reproduction completed exit 1, 18 passed/1 failed. No competing 321
test/build process or uncommitted file was present at this takeover. Existing
PostgreSQL container ID and loopback port match the recovery identity above;
provider/backend PIDs 4699/11467 remain running. No database reset, initialization,
new Problem, model call, budget/credential change or 319 asset operation occurred.

### Preserved first CI failure

[CI run 35172307975, attempt 1](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/actions/runs/35172307975)
ended FAILURE; total PR checks 11 success/1 failure. Browser job 105046376790
reported 77 selected/executed, 76 passed, 1 failed, 0 flaky/skipped. Its summary
was `BROWSER_DIAGNOSTIC_GAP`, scenario `NOT_RETAINED`, subtype `UNKNOWN`.
GitHub reported no retained artifacts. Original log remains
`/tmp/s5-321-ci-first-failure.log`. No rerun of this failed attempt was requested.
Actual checkout was `aaec7978bed08a2d5e339587d960bed4cdd1c4f7`, with parents
`e51334aa9780291b3d077a1edb698dca630a6b3f` and the candidate above; its tree
exactly equals the candidate tree. The historical CI scenario/cause remains
UNKNOWN; the matching local regression below does not retroactively recover
missing CI diagnostics.

### Proven local defect and bounded fix

`w2a-honest-shell.spec.ts`, “created problem continues through pending approval
to a fresh exact read”, failed at strict scroll-position equality in the old
`/tmp/s5-321-legacy-repro.log` and fresh `/tmp/s5-321-scroll-diagnosis-02.log`.
Structural diagnostics show scrollTop 313 -> 162, viewport height 180, receipt
height 131 plus 20px message margin. The candidate's `!selected` condition
removed the creation-fact card when authorized exact READ completed, triggering
Chromium scroll anchoring. Focus and pending composer text assertions passed.

A diagnostic CSS experiment disabled anchoring: scroll remained 313, but the
next existing assertion failed because reload also hid “已恢复正式业务记录”.
The CSS experiment was discarded. The final product fix removes only that
`!selected` condition, keeping the existing creation/restoration fact card beside
the independently authorized detail. No new disclosure, action or persistence.
`/tmp/s5-321-scroll-fix-02.log` passed the full scenario with default browser
anchoring and scrollTop 313 -> 313. No sleep, weakened assertion or exclusion.
The local diagnosis-01 attempt selected all files before grep and failed test
collection for missing unrelated backend env; diagnosis-02 correctly selected
only the mocked legacy spec. Neither touched the isolated real database.

The harness now allowlists this exact static scenario and scroll assertion step,
retaining classification, source declaration and bounded duration only. It does
not retain error text, credentials, bodies, locators or requests/responses. A
regression injects private sentinel text and checks that it cannot be emitted.

Recovery local gates (fresh executions on the final code):

- Harness: 160 passed; `/tmp/s5-321-harness-recovery.log`.
- W2A/W3: 19 passed, retries 0; `/tmp/s5-321-legacy-fixed-final.log`.
- 321 mock interaction: 28 passed, retries 0;
  `/tmp/s5-321-understanding-recovery-final.log`.
- `make check`: exit 0, 1853 passed, 200 existing external-environment skips,
  one warning; `/tmp/s5-321-recovery-make-check.log`. No tests newly skipped.
- Frontend lint/build: exit 0; `/tmp/s5-321-recovery-frontend-lint.log` and
  `/tmp/s5-321-recovery-frontend-build.log`; existing bundle-size advisory.
- `git diff --check` and the six-file scoped diff reviewed. Temporary geometry
  console logs and the CSS diagnostic experiment are absent from the candidate.

Checkpoint: local validation complete. Next command is normal commit (hooks
expected to run), then non-force push original branch and CI terminal tracking.
Real quality stays NOT_MEASURED. No real create journey is replayed.


Normal commit attempt 1 was blocked by the existing Kimi
`test_parent_deadline_kills_stalled_phase_and_reaps[send]` test:
CONNECT_DEADLINE at 1.0028s (worker reaped), expected TOTAL_DEADLINE.
`/tmp/s5-321-recovery-commit.log` is retained; 1852 passed/1 failed/200 skipped.
No source in that adapter or test changed. This is a separate local gate failure,
not evidence identifying the original browser CI failure. Root cause of missing
connected notification by the 1s deadline is UNKNOWN; host load was observed but
does not establish causation.

One isolated diagnostic of that exact test passed without modification:
TOTAL_DEADLINE at 2.0009s, cleanup 0.0060s, reaped true;
`/tmp/s5-321-hook-send-diagnostic.log` and `.xml`. Given the fresh full make-check
pass plus this exact-test metric, perform one normal commit retry with all hooks
enabled. Do not loop if it fails again.

Read-only 321 PG count check remains unchanged: 1 Problem, 1 revision,
6 invocations, 3 reservations, 3 settlements. No real browser create replay.


### Engineering delivery result

Normal commit retry completed exit 0 with Ruff lint/format and full pytest hooks
PASS; no hook bypass or modified file from hooks. Non-force push updated the
original branch from `36737e7` to `7e01ba392ea0d16311f55aaa75ddb95fa1b29a7d`
(tree `0a1dbe2e2d5cdf58934960f8b3fe146f6eb019d7`). Worktree was clean.

All 12 PR checks completed SUCCESS on that repair candidate, including
[general browser/quality CI 35184497121](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/actions/runs/35184497121)
and the dedicated 321 interaction, Identity Chain, 310, 319-mock, 320-mock,
316 and 317 workflows. These are CI-owned fixtures, not the preserved local
319 or 321 acceptance environments. Watch exited 0.

Browser job `105083525969` actually checked out
`f0fb4ea91333bd6a2fcd30fc2507348726819c22`; parents are base
`e51334aa9780291b3d077a1edb698dca630a6b3f` and repair source above. Its tree is
exactly `0a1dbe2e2d5cdf58934960f8b3fe146f6eb019d7`. Captured results:
`/tmp/s5-321-recovery-ci-terminal.json`, `/tmp/s5-321-recovery-browser-ci.log`,
`/tmp/s5-321-recovery-ci-watch.log`. Original failed attempt remains unchanged.

This documentation-only successor records those completed checks; it changes no
product, test, harness, workflow or dependency file. Final successor source/tree,
actual checkout and its CI terminal state are recorded in the **existing**
[Draft PR #181 delivery receipt](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/pull/181).
No second PR or separate authoritative handoff package is created.

Known limits: first historical CI scenario/cause remain UNKNOWN because its
allowlist omitted the scene; the local same-candidate regression and bounded fix
are proven independently. The preserved local Kimi hook failure is not explained
by evidence beyond its measured deadline phase. Real-model Q01–Q16 baseline and
candidate quality remain NOT_MEASURED, including fact/time/comparison fidelity,
repeated-question/omission rates and manual-edit reduction. Separate authorization
is still required for evaluation. No Ready, merge, deployment or Session closure.

## Fixed-candidate experience review and quality preflight — 2026-09-17

Current reviewer: 01a0addd-ab41-7063-982e-9cd8108b26ee, continuing 321. Prior
321 writers are idle/notLoaded; original branch was clean at fixed source
4001b412340398ea42d813efd7f7f5f2cf9bf01d, tree
846e7b5536ebd68d2e12d31d907d0e32a6195a70. No product change or new engineering
recovery/test-suite rerun. Existing 12/12 CI evidence is reused for that source.

[Seven-step visual walkthrough](/Users/tristan/.codex/visualizations/2026/09/17/01a0addd-ab41-7063-982e-9cd8108b26ee/321-experience-review/index.html)
adds the missing clarification presentation: input → fixture clarification →
answer/understanding → pending correction disables confirmation → corrected
card → fixture creation → independent fixture READ/refresh. Three simulated
assistance requests, one simulated creation command, zero provider calls and
zero database writes. Uses the existing 321 served dist, not a fresh build;
asset hashes, script and receipt are preserved beside the gallery. Screenshots
are browser captures, not generated mockups. This is explicitly a browser-route
fixture and not a new real-backend or model-quality acceptance run.

The fixture's simple understanding generator puts the full text in goal and marks
other fields unknown. Its redundant unknown labels are fixture behavior, not
proof that the real model extracted scope/constraints correctly. Preset responses
cannot prove no repeated questions or factual fidelity. No semantic scores assigned.

Real backend evidence is reused unchanged: existing real-understanding.png,
real-readback-criteria-independent.png and receipt.json; local HTTPS provider was
a deterministic fixture. Existing sole Problem 14019ced-cc5f-5da2-bda5-c4a12358cec6,
revision1, independent exact READ and refresh. No new CREATE or DB mutation.
Prior B01–B08/28 mock cases and real HTTPS2 cases support revision fencing,
no forced full edit, one confirmation, IME/held Enter, independent disclosure;
prior final W2A/W3 evidence supports scroll313→313 through exact READ. These
historical checks were not rerun. Reload recovers identity/content; it does not
establish arbitrary scroll-position persistence across every full-page reload.

Review recommendation: bounded engineering/fixture interaction acceptance is
supported, with original service/provider/CI limitations retained. Real model
fidelity, duplicate-question reduction, omission/manual-edit reduction and
regressions remain NOT_MEASURED for all Q01–Q16. Initial observation was superseded by the clarification-label defect below. Do not grant semantic
quality acceptance or Ready/merge from fixture results.

The existing REAL-QUALITY-GATE.md now contains the concrete parameter table,
credential metadata, immutable policy identities, fair baseline behavior, proposed
56-call/USD8 cap and absolute 8-hour window. quality-comparison-preflight.json
holds 16 paired result rows, all metrics null. No credentials materialized,
real evaluation governance registration, ledger creation or provider dispatch.
The initial documentation-only review was followed by the bounded repair below;
the successor must receive its own source/tree and checks.

### Clarification result label repair

Visual inspection of 02-clarification.png found a confirmed product defect:
SUCCEEDED/NEEDS_CLARIFICATION displayed “草稿已生成”; the real-channel note also
claimed a draft existed. Original screenshot remains in the review gallery.
DraftAssistanceCard now derives the badge, provider note and rejection label from
resultKind, so a successful clarification is not presented as a ready draft.
No request, output schema, policy, authorization or creation behavior changes.
Two browser regressions cover SYNTHETIC and REAL_PROVIDER projections using routed
fixtures, assert no generated-draft claim or confirmation button, and preserve
all prior 28 interaction cases. Real provider dispatch remains zero.

The first edit command used an incorrect working-directory-relative path and
failed before writing. Its trailing browser command ran the old28 suite (28 passed)
and is not repair evidence. The subsequent correct edit and fresh30 suite are
tracked separately; no tests/limits were weakened.

Repair validation: make check exit0, 1853 passed/200 existing environment skips/1 warning; frontend lint exit0; Playwright config performed production build and all30 interaction cases passed, retries0. Logs: /tmp/s5-321-review-make-check.log, /tmp/s5-321-review-lint.log, /tmp/s5-321-review-label-final.log. Corrected seven-step screenshots are in the same gallery corrected/ directory; original screenshots retained. No real model or database creation. Normal commit and successor CI are the next gate.


Normal repair commit/hooks passed and non-force push completed: source
18447f8667b3acbb46f8025e08f28be01d6c5929, tree
5b0248ba8f4cacc07055335831cdff8ccb6f180c, parent4001b412.
All12 new automatic checks started; terminal result is recorded in original PR181.
This documentation successor corrects the proposed ledger composition: existing
PostgresProviderBudgetLedger binds one exact Profile; v1/v2 therefore need two
fixed ledgers, each28/USD4, collectively56/USD8, with no cap transfer. No budget
implementation changed, no ledger instantiated, no authorization inferred.

Concurrency observation: after the initial idle check, the previous321 task
01a0adb5 became systemError after independently producing experience-review/
fixtures. Its last command exec-26882393 completed exit0; all preceding browser
commands completed. No active writer or product edits remained. Its untracked
experience-review/ (including fixture-dto-failure/) is preserved untouched and
excluded from this commit. This review's images live in the external gallery.
Do not describe the worktree as fully clean while that directory remains.

Final successor identity/CI is the existing PR181 receipt. This document-only
successor does not alter the validated repair product bytes/policies. Model
quality remains NOT_MEASURED; 14:30–22:30 +08 window and56/USD8 await Human approval.
