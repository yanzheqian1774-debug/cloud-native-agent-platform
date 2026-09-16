# S5-V023-IMPL-319 implementation evidence

## Classification

This directory records implementation and deterministic acceptance evidence for
`S5-V023-IMPL-319`. The candidate is not Ready, merged, deployed, released or closed.
Real-provider acceptance is `PENDING / NOT_AUTHORIZED / NOT_EXECUTED`; no real
credential was read and no real provider was contacted. The resumed candidate adds a
dormant OpenAI Responses composition that is exercised only with fake credentials
and a visibly labelled local HTTPS mock until a separate Human gate is granted.

## Fixed inputs and dependency reception

| Item | Verified value |
| --- | --- |
| Implementation base | `41a7fe8fc2bb7e1951ffd33b676492f6d3a6757e` / tree `88b18b57d11548593a76fdad8e461f786dd2be43` |
| Fixed 308 candidate | `141a17ecd34ec3b721e1c8a8ae33277c4b454e42` / tree `b195b4612a4ab9f295e3c6f9a82199b05db7ac0e` |
| Starter attachment | SHA-256 `81c613c51bb125c81a53601e9c78ac21267ed6918a8c3490fe5312045cfbaf66` |
| Identifier audit | no competing `S5-V023-IMPL-319` owner in repository/history/refs/worktrees, GitHub PR/issues, or visible tasks at startup |
| Branch | `codex/s5-v023-impl-319-problem-draft-assistance` |

The G1 dependency/conflict matrix is in the active implementation plan. Reception of
308 was limited to Model Governance domain, PostgreSQL, exact resolver and current
authorization symbols. Existing authority/BFF files were retained and composed; no
whole-branch replacement was used.

Migration `0019_model_governance.sql` retains its original 308 identity and checksum.
The task adds `0023_draft_assistance.sql` and the resumed increment adds the isolated
`0024_draft_provider_budget.sql`; neither edits or claims `0020`, `0022`, the
separately observed but unavailable `0021`, or another task's database. Real
PostgreSQL acceptance used only container `s5-v023-impl-319-postgres` on loopback
port `55431`.

## Implemented boundary

- independent Draft Assistance context/turn/invocation metadata and append-only CAS
  versions, with HMAC-SHA-256 body commitment and no raw-content persistence;
- separate exact Draft request/read/cancel and Model invoke authorization, current
  dispatch admission, exact Model/Provider/Endpoint/Profile/adapter snapshot;
- provider-neutral dispatch/observe/cancel, the deterministic synthetic adapter, and
  a disabled-by-default exact OpenAI Responses foreground composition;
- an exact file credential resolver with no environment fallback and a task-scoped
  PostgreSQL call/worst-case-cost reservation ledger;
- Execution-owned `contextual-resource-use.v2` non-Attempt sibling and independent
  `model-draft-assistance-invocation-evidence.v1` allowlisted Evidence;
- deterministic B/E/F/G operation IDs and repair without credential resolution or
  provider redispatch;
- full Chinese-first Problem Workbench journey, preserving the existing formal
  Problem writer and authorized readback.

Draft invocation responses disclose only whether Resource Use/Evidence was recorded.
Their exact identifiers/content stay behind separate owner read authorization.

## Committed synthetic baseline validation

The checks below apply to the committed synthetic baseline through `e39bcc8`; they
remain historical evidence and are not presented as validation of the resumed
real-adapter increment:

| Check | Result |
| --- | --- |
| Final `make check` | `PASS`; exit 0, 1,759 passed / 188 skipped / 1 deprecation warning on the pre-commit candidate source |
| Normal pre-commit hooks | `PASS`; Ruff lint, Ruff format and pytest |
| Frontend ESLint and default TypeScript/Vite build | `PASS` |
| Focused Draft/Workbench unit tests | `PASS`; 15 tests |
| PostgreSQL migration/restart/immutability/reader compatibility | `PASS`; 2 tests on task-owned PostgreSQL 16 |
| 308 current-grant, revocation, exact lock and caller-owned transaction integration | `PASS`; 1 PostgreSQL test |
| Raw-content scan of Draft, contextual Resource Use and Evidence records | `PASS`; zero matches for the browser input strings in a 70,119-byte data-only dump |
| Native HTTPS Chromium product journey | `PASS`; 1 test in 6.0s, using the live product build with `VITE_PROBLEM_DRAFT_ASSISTANCE=enabled`, two-stage authorization, clarification, supplement/new turn, structured draft, Human edit, formal create and authorized readback |
| Provider type used | `SYNTHETIC`; real provider calls `0` |

## Resumed real-adapter increment validation

The uncommitted resumed increment was checked independently before delivery:

| Check | Result |
| --- | --- |
| Focused adapter, resolver, service, budget and workflow tests | `PASS`; 48 tests, including 5 task-database budget tests |
| Focused Ruff and shell syntax | `PASS`; bash and zsh syntax accepted both acceptance helpers |
| Cleanup failure injection | `PASS`; bash and zsh each preserved exit code `37` |
| Frontend ESLint and exact Vite build | `PASS`; built with both required variables and found both product markers in `dist` |
| Repository `make check` | `PASS`; 1,775 passed / 193 skipped / 1 warning |
| Normal pre-commit hooks | `PASS`; Ruff lint, Ruff format and pytest |
| Reused-database local mock journey | `NOT A PASS`; preserved database state caused fixture `IDEMPOTENCY_PAYLOAD_MISMATCH` before listener readiness, so no browser or provider call ran |
| Dedicated clean PostgreSQL + HTTPS + Chromium + local-mock CI | `PENDING`; this is the required complete-click gate for the resumed candidate |

The passing browser run used the product's buttons and forms, not direct business
API mutation. The server reported `READY` through `LISTENER_READINESS`; its startup
record and final full-page screenshot are retained under `browser-final/`. The
synthetic transport is explicitly labelled in the UI and must not be presented as a
real AI call.

The final source/tree, commit parent chain, Draft PR and CI checkout identities are
recorded in the PR delivery after the final quality gate.

The separate, unexecuted gate request is [REAL-PROVIDER-CALL-PACKAGE.md](./REAL-PROVIDER-CALL-PACKAGE.md).

## Final candidate validation and Human bounded acceptance

This section is the terminal addendum for the implementation candidate. The earlier
“resumed real-adapter increment validation” table is retained verbatim as a
pre-final historical snapshot; its `PENDING` dedicated-CI row and earlier test counts
are superseded for final-candidate status only by the evidence below. They are not
rewritten into a success that had not yet occurred.

The Human decision is `PASS_WITH_CONSTRAINTS / BOUNDED_ACCEPTED` and is bound only
to source `90ee19d43c4b0df2c1e534b53571f7b8d9680b41`, tree
`ea13c04fa28dc846284f6e5d91c90e5d4a456656`. Session
`S5-V023-IMPL-319` remains `OPEN`; PR #176 remains Draft. Any documentation commit
that records this decision is not automatically another accepted implementation
candidate.

### Final local validation

| Check | Final result |
| --- | --- |
| Focused adapter, resolver, service, PostgreSQL budget and workflow tests | `PASS`; 49 tests |
| Frontend ESLint and dedicated Playwright discovery | `PASS`; exactly 3 tests in 1 dedicated file |
| Exact Vite build | `PASS`; `VITE_SUPPLIER_QUALITY_DEMO_MODE=live` and `VITE_PROBLEM_DRAFT_ASSISTANCE=enabled`; both product markers present |
| Repository `make check` | `PASS`; 1,776 passed / 193 skipped / 1 warning |
| Normal pre-commit and commit hooks | `PASS`; Ruff lint, Ruff format and pytest |
| bash/zsh cleanup compatibility | `PASS`; injected exit code `37` was preserved |

### Final-candidate PR checks and actual checkout identities

All ten checks completed successfully at PR source
`90ee19d43c4b0df2c1e534b53571f7b8d9680b41`. The six general jobs checked out the
GitHub PR merge commit `28c0b01e53e5b1cfd14085817b028973540a10b7`, tree
`9193ed579e27d39663a97640593629043fd931dd`, whose ordered parents were the then-base
`e648d9b056b8e219b01355c45be474764db1ed90` and the accepted source. The four
candidate-pinned jobs checked out the accepted source directly, tree
`ea13c04fa28dc846284f6e5d91c90e5d4a456656`.

| Check | Run / job / attempt | Actual checkout / tree |
| --- | --- | --- |
| Quality Gates | `35045718874 / 104634978400 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| Frontend Quality Gates | `35045718874 / 104634978525 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| Agent Workbench Browser Acceptance | `35045718874 / 104634978637 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| PostgreSQL Identity Chain | `35045718829 / 104634978439 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| PostgreSQL Business Problem and Plan Entry | `35045718829 / 104634978518 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| PostgreSQL Skill Invocation | `35045718829 / 104634978543 / 1` | PR merge `28c0b01e...` / `9193ed579...` |
| PostgreSQL HTTPS Chromium Acceptance | `35045718817 / 104634978321 / 1` | source `90ee19d4...` / `ea13c04fa...` |
| PostgreSQL HTTPS Workbench Acceptance | `35045718911 / 104634978923 / 1` | source `90ee19d4...` / `ea13c04fa...` |
| PostgreSQL HTTPS Chromium Mock Provider | `35045718901 / 104634978857 / 1` | source `90ee19d4...` / `ea13c04fa...` |
| PostgreSQL Native and HTTPS Chromium | `35045718826 / 104634978501 / 1` | source `90ee19d4...` / `ea13c04fa...` |

### Dedicated PostgreSQL, HTTPS, Chromium and local Responses mock evidence

Run `35045718901`, job `104634978857`, attempt `1` checked out the accepted source
directly. It built the frontend with both required Vite variables, found
`新建对话=true` and `AI 问题理解与草稿辅助=true`, reached listener readiness, passed
the focused backend/contract tests, proved cleanup retained injected failure `37`,
discovered exactly the dedicated tests, and executed all three browser journeys.

The runner-recorded frontend build digest is
`44706dbbaa7c5fe87b7009a7db5137b0219437e95dff03bc7df502222432182a`.
The uploaded `s5-v023-impl-319-mock-provider-evidence` artifact is GitHub artifact
`10427081723`, size `593172` bytes, archive digest
`sha256:772fd4c8c5acd4ff7d0d6d59f013063fdf5d7e3bd4266f25a014ac3266528210`.
Its Playwright result is exit `0`, expected `3`, unexpected `0`, skipped `0`, flaky
`0`; provider identity is `LOCAL_HTTPS_OPENAI_RESPONSES_MOCK` and
`realProviderCalls=0`.

The journeys and their bounded proof are:

1. `S5-319 completes governed clarification, editable draft, confirmation, and formal readback`
   proves separate Draft/Model authorization, clarification, a separately authorized
   supplemented turn, structured editable draft, explicit Human confirmation,
   existing formal Problem creation and independent authorized readback.
2. `S5-319 shows authorization denial without a provider call` proves the
   non-disclosing not-found surface, retained pending state, absent Resource
   Use/Evidence and an unchanged provider call counter.
3. `S5-319 keeps nonterminal foreground calls observable and cancellation unconfirmed`
   proves correlated foreground `in_progress` becomes `UNKNOWN`, observe/cancel
   return explicit unsupported reasons, cancellation is not fabricated, and neither
   operation redispatches.

### Human-accepted scope and retained limitations

The bounded acceptance covers the governed Problem draft assistance journey,
dual exact authorization, Human edit/confirmation, existing formal Problem create
and authorized readback; the mock-verified Responses adapter, exact credential
resolver, budget reservation, Resource Use/Evidence and repair without redispatch;
and the three dedicated local HTTPS mock browser journeys above.

It does not prove real model quality, provider account/project availability, current
price, provider billing enforcement or retention/ZDR posture. Remote foreground
observe/cancel remains unsupported and cancellation is never reported as confirmed.
It is not a Plan, Workflow, Native business-execution loop or M3-completion claim.
It grants no credential read, real provider dispatch, spend, Ready, merge,
deployment, release or Session closure authority.

The PostgreSQL reservation ledger is a task-scoped admission guard, not a provider
account billing hard cap. Every timeout, disconnect or ambiguous transport result
remains `UNKNOWN`; it is never redispatched automatically. Mock output cannot replace
an inadequate real-provider output, and the full real request—including instructions
and schema—must fit any later Human-approved input ceiling.

### Historical failures remain evidence

- The first resumed local browser attempt loaded a frontend build without both
  required Vite variables; all 3 journeys failed before product invocation.
- A later preserved-database local attempt stopped at
  `IDEMPOTENCY_PAYLOAD_MISMATCH`; it is explicitly `NOT A PASS` and the database was
  not cleaned or rebuilt to manufacture one.
- Dedicated runs `35043663094`, `35044946329` and `35045357853` remain failed runs.
  Their artifacts drove exact scenario/locator corrections; they are not rewritten
  by the successful run.
- Network interruption observations are not relabelled as test failures or successes.
- Transport ambiguity, unsupported observation/cancellation and all documented
  negative/unit/PostgreSQL test layers retain their distinct scope.

### External Human records

The Human records remain external inputs and are referenced by stable filename and
digest rather than a machine-local absolute path:

| External record | SHA-256 |
| --- | --- |
| `HUMAN-BOUNDED-ACCEPTANCE.md` | `f2c76c4c96ae61cba444079d26a73b7cd53b9935585730e56c8682cce2dd1eca` |
| `REAL-PROVIDER-PARAMETERS-PENDING.md` | `91351b818f698813bf87a1ecac4fbd1870348c123b2a6a6993b4a4e82fbb43f9` |

The first record is the bounded acceptance source; the second contains no real-call
authorization and leaves every unconfirmed provider/account/model/price/credential/
retention/authorization/quality value `PENDING`. The real-provider Gate therefore
remains `PENDING / NOT_AUTHORIZED / NOT_EXECUTED`.
