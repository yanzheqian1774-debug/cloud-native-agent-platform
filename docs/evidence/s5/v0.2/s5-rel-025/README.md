# S5-REL-025 — Product View durable integration evidence

## Candidate identity and authority

- Session: `S5-REL-025`
- Task: `[S5-REL-025] Product View Durable Integration`
- REL ID authority: `HUMAN_ALLOCATED`
- Human REL naming decision: `PASS`
- Human Implementation Gate: `PASS_WITH_CONSTRAINTS`
- Human Review Gate: `PASS_WITH_CONSTRAINTS`
- Durable baseline: `25f755432381b40efae2f3e251863db0ca32acee`
- Source session: `S5-IMPL-010`
- Source head: `18fa8f9a0eb5caef18772063c28c8fd414d6959f`
- Source PR: `#64`, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE` at preflight
- REL branch: `codex/s5-rel-025-product-view-integration`
- Integration merge: `93bd1db550a0ca4c96c9c30962d40d97927fac31`
- First parent: `25f755432381b40efae2f3e251863db0ca32acee`
- Second parent: `18fa8f9a0eb5caef18772063c28c8fd414d6959f`
- Reviewed candidate head: `b81e0d7150081a327f3d586d2d1d3ada837b3105`
- Integration PR: `#65`, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE` at
  independent review
- Evidence-only review successor: `RESOLVED_BY_EXACT_GIT_PR_AND_CI`
- Main merge authorization: `NOT_GRANTED`

The explicit merge preserves all three S5-IMPL-010 source commits. It is not a
squash, rebase, cherry-pick, or fast-forward. The Product View is an integration
candidate only and is not durable main.

## Source and REL path inventory

The integration merge adds exactly the 18 authorized source paths:

1. `console/frontend/src/App.tsx`
2. `console/frontend/src/components/ConsoleShell.tsx`
3. `console/frontend/src/i18n/messages.ts`
4. `console/frontend/src/pages/ProductViewPage.tsx`
5. `console/frontend/src/product/BusinessJourney.tsx`
6. `console/frontend/src/product/DigitalEmployeeDirectory.tsx`
7. `console/frontend/src/product/DraftDiffApproval.tsx`
8. `console/frontend/src/product/OutcomeEvidence.tsx`
9. `console/frontend/src/product/ProductGraph.tsx`
10. `console/frontend/src/product/ProductNavigation.tsx`
11. `console/frontend/src/product/RuntimeSupport.tsx`
12. `console/frontend/src/product/adapter.ts`
13. `console/frontend/src/product/fixture.ts`
14. `console/frontend/src/product/journey.ts`
15. `console/frontend/src/product/types.ts`
16. `console/frontend/src/styles/app.css`
17. `docs/evidence/s5/v0.2/s5-impl-010/README.md`
18. `tests/test_s5_impl_010_product_view.py`

The REL successor changes only `docs/governance/REGISTRY.md`,
`PROJECT_STATE.md`, and this file. The total baseline-to-candidate inventory is
therefore exactly 21 paths.

## Authority and honesty boundaries

The Product fixture is deterministic, synthetic, non-authoritative, and a
Technical Preview. It performs no network access, persistence, authorization,
Runtime invocation, or Provider invocation. It does not create a second Product
data authority or Graph authority. The existing Shared DTO and canonical Graph
semantics remain unchanged, and the fixture preserves the single Platform
Execution Identity, Product projection context, canonical snapshot identity,
raw relation evidence, direction, and cardinality.

Approval replay is bound to the exact revision fingerprint. Correction creates
an immutable successor revision and returns to pending Human approval. Reject,
malformed approval, and changed replay facts fail closed. DENY presents zero
Provider calls; UNKNOWN and failure are not presented as success. Runtime and
Knowledge presentation remains explicitly bounded: Native is not certified,
OpenClaw support is not granted, Hermes is not currently certifiable, and
synthetic citations do not claim production Knowledge or RAG.

## Validation evidence separation

These evidence classes are independent and must not substitute for one another:

- Source-head CI: run `32993402567` at
  `18fa8f9a0eb5caef18772063c28c8fd414d6959f`; Quality Gates and Frontend
  Quality Gates passed.
- Local integrated-candidate validation: `PASS` on the merge plus the three REL
  paths before the linear evidence successor commit.
- Exact reviewed-candidate CI: run `33035843711` at
  `b81e0d7150081a327f3d586d2d1d3ada837b3105`; Quality Gates and Frontend
  Quality Gates passed and all expected steps executed.
- Exact evidence-correction-head CI: resolved by the matching local, tracking,
  remote, PR #65, and CI heads after this non-self-referential successor.
- Future exact-main merge CI: `NOT_RUN / NOT_AUTHORIZED`; no main merge is
  authorized by this evidence.

Local reconciliation on 2026-08-27:

- direct Product View suite: **33 passed**;
- approval/correction focus: **4 passed**;
- graph/identity focus: **7 passed**;
- locale/i18n focus: **3 passed**;
- root-shim collection: exactly **33** Product View nodes;
- full `make check`: **649 passed**, with one existing Starlette/httpx
  deprecation warning;
- Ruff lint: passed; Ruff format: **107 files already formatted**;
- frontend lint: passed;
- frontend production build and TypeScript compilation: passed, **49 modules
  transformed**;
- `git diff --check`: passed;
- API/CRD/schema, dependency/lockfile, workflow-path, import/ownership,
  secret/redaction, relative-link, and rollback audits: passed;
- baseline-to-candidate inventory: exactly **21 paths**, comprising the 18
  source paths and 3 authorized REL paths.

Independent Checkpoint B review additionally verified that every one of the 18
source blobs equals the authorized source tree, the three source commits remain
unmodified beneath a true two-parent integration merge, and the evidence commit
changes only the three REL paths. Browser reconfirmation passed complete
`en-US` and `zh-CN` journeys, mid-journey locale switching with stable selected
question and Platform Execution Identity, semantic statuses, existing
`/workflows` navigation, intentional `/` to `/product` routing, visible keyboard
focus, and zero warning/error logs. At **390×844**, viewport, body, and document
widths were exactly **390 px**, with no horizontal overflow.

The prospective merge into unchanged `origin/main` is conflict-free. It has
exactly 21 modified/added paths, no deletion, rename, mode change, submodule,
API/CRD/schema, Shared DTO, canonical Graph semantic, dependency/lockfile, or
workflow change. The required GitHub method is **Create a merge commit**, with
current `origin/main` as first parent and the exact final PR #65 head as second
parent; squash and rebase methods are prohibited because they would not
preserve the integration merge and evidence-successor history.

## Rollback boundary

Before any main merge, rollback is closure of unmerged Draft PR #65 or deletion
of its REL branch. If later authorized and merged with a main merge commit,
rollback is `git revert -m 1 <PR-65-main-merge-commit>`; the expected rollback
scope is exactly the 21 Product and REL paths. No database migration, dependency
cleanup, external-effect reversal, public API rollback, or Kubernetes action is
required.

## Gate

Stop after exact evidence-correction-head CI and return to the Human S5-REL-025
Merge Gate. Do not merge to main, start Technical View, start Golden Demo, or
start Release.

## Terminal durable-integration and closure addendum — 2026-08-27

The open/unmerged and future-CI statements above are preserved as historical
checkpoint observations that were accurate when the candidate and review
evidence were written. They are superseded for current lifecycle navigation by
the following terminal facts:

- PR #65 merged with durable-main merge commit
  `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`.
- Source PR #64 merged automatically through that durable integration; its
  source head remains `18fa8f9a0eb5caef18772063c28c8fd414d6959f`.
- Exact-main CI run `33036620588` completed with `SUCCESS` at
  `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`.
- The Human-confirmed terminal state is `S5-REL-025 CLOSED /
  PASS_WITH_CONSTRAINTS`.
- The source and REL branches are retained; closure does not authorize branch
  cleanup or history rewriting.

Closure records durable Product View integration only. It does not claim that
the Product MVS is complete, that Golden Demo or Release work has started, or
that release or production readiness is granted.

For portfolio consistency at this reconciliation point, the later Technical
View integration is also terminal: PRs #66 and #67 are merged, S5-IMPL-011 and
S5-REL-026 are Human-confirmed closed, durable main is
`b244fa5da3e670fa754278a0559da1a3049fb05a`, and exact-main CI run
`33042871796` succeeded. Thus PRs #64–#67 are merged and S5-IMPL-010,
S5-REL-025, S5-IMPL-011, and S5-REL-026 are closed. S5-REL-027 is active in
`REVIEW / PASS_WITH_CONSTRAINTS / READY_FOR_HUMAN_MERGE_GATE` at Draft PR #68;
it is not merged or closed, and no downstream task is authorized.

The original rollback section describes the pre-merge checkpoint. After the
terminal Product durable integration, the applicable repository rollback is
`git revert -m 1 4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`; branch deletion or PR
closure is no longer a rollback for already-merged Product content.
