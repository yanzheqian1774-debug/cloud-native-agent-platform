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
