# S5-REL-025 — Product View durable integration evidence

## Candidate identity and authority

- Session: `S5-REL-025`
- Task: `[S5-REL-025] Product View Durable Integration`
- REL ID authority: `HUMAN_ALLOCATED`
- Human REL naming decision: `PASS`
- Human Implementation Gate: `PASS_WITH_CONSTRAINTS`
- Durable baseline: `25f755432381b40efae2f3e251863db0ca32acee`
- Source session: `S5-IMPL-010`
- Source head: `18fa8f9a0eb5caef18772063c28c8fd414d6959f`
- Source PR: `#64`, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE` at preflight
- REL branch: `codex/s5-rel-025-product-view-integration`
- Integration merge: `93bd1db550a0ca4c96c9c30962d40d97927fac31`
- First parent: `25f755432381b40efae2f3e251863db0ca32acee`
- Second parent: `18fa8f9a0eb5caef18772063c28c8fd414d6959f`
- Integration PR: one new Draft PR, identifier recorded PR-natively after push
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
- Exact integrated-head CI: `PENDING_PR_NATIVE_OBSERVATION`; it must execute at
  the final evidence successor head after the Draft integration PR exists.
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

## Rollback boundary

Before any main merge, rollback is deletion of the unmerged REL branch or
closure of its Draft PR. If later authorized and merged, revert the bounded
integration merge plus its linear evidence/governance successor. No database
migration, dependency cleanup, external-effect reversal, public API rollback,
or Kubernetes action is required.

## Gate

Stop after exact integrated-head CI and return to the Human S5-REL-025 Review
Gate. Do not merge to main, start Technical View, start Golden Demo, or start
Release.
