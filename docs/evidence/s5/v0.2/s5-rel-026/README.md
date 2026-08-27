# S5-REL-026 — Technical View durable integration evidence

## Candidate authority and identity

- Session: `S5-REL-026`
- Task: `[S5-REL-026] Technical View Durable Integration`
- REL ID authority: `HUMAN_ALLOCATED`
- Human naming decision: `PASS`
- Human Implementation Gate: `PASS_WITH_CONSTRAINTS`
- Checkpoint: `B — INDEPENDENT_INTEGRATION_REVIEW_AND_MERGE_READINESS`
- Human Review Gate: `PASS_WITH_CONSTRAINTS`
- Durable baseline: `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`
- Source session: Human-confirmed closed `S5-IMPL-011`
- Source branch: `codex/s5-impl-011-technical-view`
- Source PR: #66, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE` at evidence-writing time
- Source head: `c9cd70108bb3b1bd77458d5340a63a41443b84c9`
- Integration branch: `codex/s5-rel-026-technical-view-integration`
- Integration merge: `7ce4ad11a65a43e7859f59aa5a921de849895eda`
- First parent: `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`
- Second parent: `c9cd70108bb3b1bd77458d5340a63a41443b84c9`
- Evidence commit and reviewed candidate: `367e2eba6cb81fbf48fdb9505ac9bfbc83731cae`
- Draft integration PR: #67, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE`

The merge is explicit and provenance-preserving. It does not squash, rebase,
cherry-pick, fast-forward, amend, or rewrite the two source commits:

1. `8030de13faa60705bd1b7742789c311ca9a51957` — bounded Technical View implementation;
2. `c9cd70108bb3b1bd77458d5340a63a41443b84c9` — fail-closed context correction.

## Exact scope

The integration imports exactly 27 source paths:

1. `console/frontend/src/App.tsx`
2. `console/frontend/src/components/ConsoleShell.tsx`
3. `console/frontend/src/i18n/messages.ts`
4. `console/frontend/src/pages/ProductViewPage.tsx`
5. `console/frontend/src/pages/TechnicalViewPage.tsx`
6. `console/frontend/src/product/ProductNavigation.tsx`
7. `console/frontend/src/product/adapter.ts`
8. `console/frontend/src/product/fixture.ts`
9. `console/frontend/src/product/journey.ts`
10. `console/frontend/src/product/types.ts`
11. `console/frontend/src/shared/SelectedExecutionContext.tsx`
12. `console/frontend/src/shared/ViewSwitcher.tsx`
13. `console/frontend/src/shared/executionSnapshotFixture.ts`
14. `console/frontend/src/shared/executionSnapshotTypes.ts`
15. `console/frontend/src/shared/projections.ts`
16. `console/frontend/src/shared/urlContext.ts`
17. `console/frontend/src/styles/app.css`
18. `console/frontend/src/technical/CapabilityEvidencePanel.tsx`
19. `console/frontend/src/technical/ExecutionIdentityPanel.tsx`
20. `console/frontend/src/technical/OutcomeRecoveryPanel.tsx`
21. `console/frontend/src/technical/RuntimeProviderPanel.tsx`
22. `console/frontend/src/technical/TechnicalGraph.tsx`
23. `console/frontend/src/technical/TechnicalNavigation.tsx`
24. `console/frontend/src/technical/adapter.ts`
25. `console/frontend/tests/test_s5_impl_011_technical_view.py`
26. `docs/evidence/s5/v0.2/s5-impl-011/README.md`
27. `tests/test_s5_impl_011_technical_view.py`

The only three REL-owned additions are:

1. `docs/governance/REGISTRY.md`
2. `PROJECT_STATE.md`
3. `docs/evidence/s5/v0.2/s5-rel-026/README.md`

The expected baseline-to-final-candidate scope is therefore exactly 30 paths.
There are no unexpected deletions, renames, mode changes, submodules, public
API or CRD/schema changes, backend DTO changes, Canonical Graph changes,
dependency or lockfile changes, workflow changes, or production integration
paths.

## Projection, identity, and honesty boundaries

The shared frontend execution snapshot remains deeply frozen, deterministic,
synthetic, non-authoritative, Technical Preview data with no network or live
Runtime/Provider invocation. Product and Technical Views are sibling
projections from that one snapshot; Technical output is not derived from
Product output and neither projection becomes a second data or Graph authority.

The integration preserves the selected Digital Employee, approved revision,
work, Workflow, Task, Platform Execution Identity, graph snapshot identity,
authorization decision and reason, Outcome, Evidence, Citation, Runtime IDs and
support classifications, and Provider correlation IDs. Technical graph edges
consume the supplied raw relations without inferring or reconstructing graph
cardinality. Product regression coverage remains part of the integrated gate.

DENY requires zero Provider calls and no live citation retrieval. UNKNOWN,
failed, skipped, blocked, unavailable, and downstream states remain distinct
from success. Native remains a component-tested candidate and not certified;
OpenClaw remains experimental/currently unavailable; Hermes remains
experimental/not currently certifiable. Citations remain synthetic and
view-only. This work does not add live Runtime, Provider, Knowledge, recovery,
Golden Demo, or Release behavior and does not claim exactly-once recovery.

## Validation evidence

### 1. Source-head CI

GitHub Actions run `33040609882` targeted exact source head
`c9cd70108bb3b1bd77458d5340a63a41443b84c9` and completed successfully:

- Quality Gates: `SUCCESS`
- Frontend Quality Gates: `SUCCESS`

### 2. Integrated-candidate validation and CI

Local integrated-candidate validation on 2026-08-27 passed:

- 27 Technical tests passed;
- 33 Product tests passed;
- 60 combined Product/Technical tests passed;
- exactly 27 root-shim Technical nodes and zero duplicates;
- 676 tests passed in standard collection/full `make check`;
- Ruff lint passed; Ruff inspected 109 files and reported them already
  formatted, rewriting zero files;
- frontend clean install and ESLint passed;
- TypeScript compilation and production build passed with 62 modules transformed;
- exact 30-path, source-blob, API/CRD/schema, backend DTO, Canonical Graph,
  dependency/lockfile, workflow, import/ownership, secret/redaction,
  network/storage/side-effect, claim, relative-link, and rollback audits passed.

The full suite retained one existing Starlette/httpx deprecation warning with
unchanged provenance; it is informational only. Browser QA is inherited from the immutable
source candidate and covers both locales, Product/Technical round trips,
validated URL context and history, accessibility, responsive presentation,
honest empty/error/unavailable/downstream states, and zero browser console
warnings or errors.

GitHub Actions run `33041706623` targeted the exact reviewed candidate head
`367e2eba6cb81fbf48fdb9505ac9bfbc83731cae` and completed successfully:

- Quality Gates: `SUCCESS`
- Frontend Quality Gates: `SUCCESS`
- all expected checkout, toolchain, dependency, lint, test, TypeScript, and
  production-build steps executed.

This evidence update is a bounded, linear post-review successor because a
commit cannot contain its own SHA or the CI run created only after it is
pushed. Its exact head and CI remain GitHub/PR-native evidence. Source-head CI
is not substituted for candidate-head or post-review evidence-head CI.

### 3. Future exact-main-merge CI

No main merge is authorized at this checkpoint. A future Human-authorized main
merge must be validated independently at its exact merge SHA; neither source
CI nor integration-candidate CI constitutes future exact-main-merge CI.

## Rollback and authority limits

Independent prospective merge review against unchanged `origin/main` found
zero conflicts and the same exact 30-path candidate content. GitHub must use
**Create a merge commit**; squash or rebase merge would discard the preserved
internal integration merge and its evidence successors. The future durable
rollback command is:

```text
git revert -m 1 <future-pr-67-main-merge-commit>
```

Rollback is one bounded revert of integration merge
`7ce4ad11a65a43e7859f59aa5a921de849895eda` to first parent
`4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`, plus its REL evidence successor.
No data migration, persistence cleanup, Kubernetes action, Runtime/Provider
reversal, or external side-effect cleanup is required.

This candidate is not merged to durable main and S5-REL-026 is not closed. It
does not grant Product MVS completion, Contract or Schema freeze, Provider
certification, production Runtime, Knowledge or recovery support, Golden Demo
readiness, production readiness, Release readiness, or Release acceptance. The
next decision is the Human S5-REL-026 Merge Gate.

## Terminal durable-integration and closure addendum — 2026-08-27

The open/unmerged, future exact-main CI, and pending Merge Gate statements
above are preserved as historical checkpoint observations that were accurate
when the candidate and independent review evidence were written. They are
superseded for current lifecycle navigation by these terminal facts:

- PR #67 merged with durable-main merge commit
  `b244fa5da3e670fa754278a0559da1a3049fb05a`.
- That durable merge has first parent
  `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`, second parent
  `f89f1520b46087dd08f506f7a7b541744c451ba2`, and merged tree
  `18b17ad135d36d308e90dce33480857571dab2a0`.
- Source PR #66 merged automatically through that durable integration; its
  source head remains `c9cd70108bb3b1bd77458d5340a63a41443b84c9`.
- Exact-main CI run `33042871796` completed with `SUCCESS` at
  `b244fa5da3e670fa754278a0559da1a3049fb05a`.
- The Human-confirmed terminal state is `S5-REL-026 CLOSED /
  PASS_WITH_CONSTRAINTS`.
- The source and REL branches are retained; closure does not authorize branch
  cleanup or history rewriting.

The source head, reviewed candidate head, final PR head, and exact-main merge
remain distinct provenance points. Closure records durable Technical View
integration only. It does not claim Product MVS completion, Golden Demo or
Release start/readiness, production Runtime/Provider/Knowledge completion,
Provider certification, or release acceptance.

For portfolio consistency at this reconciliation point, Product View is also
terminal: PRs #64 and #65 are merged through durable Product merge
`4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`, S5-IMPL-010 and S5-REL-025 are
Human-confirmed closed, and exact-main CI run `33036620588` succeeded. Thus PRs
#64–#67 are merged and S5-IMPL-010, S5-REL-025, S5-IMPL-011, and S5-REL-026
are closed. S5-REL-027 is active for governance reconciliation only; no
downstream task is authorized.
