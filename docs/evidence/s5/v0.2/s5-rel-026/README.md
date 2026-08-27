# S5-REL-026 — Technical View durable integration evidence

## Candidate authority and identity

- Session: `S5-REL-026`
- Task: `[S5-REL-026] Technical View Durable Integration`
- REL ID authority: `HUMAN_ALLOCATED`
- Human naming decision: `PASS`
- Human Implementation Gate: `PASS_WITH_CONSTRAINTS`
- Checkpoint: `A — BOUNDED_DURABLE_INTEGRATION_CANDIDATE`
- Durable baseline: `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`
- Source session: Human-confirmed closed `S5-IMPL-011`
- Source branch: `codex/s5-impl-011-technical-view`
- Source PR: #66, `OPEN / DRAFT / UNMERGED / CLEAN / MERGEABLE` at evidence-writing time
- Source head: `c9cd70108bb3b1bd77458d5340a63a41443b84c9`
- Integration branch: `codex/s5-rel-026-technical-view-integration`
- Integration merge: `7ce4ad11a65a43e7859f59aa5a921de849895eda`
- First parent: `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`
- Second parent: `c9cd70108bb3b1bd77458d5340a63a41443b84c9`
- Draft integration PR: pending creation after local candidate validation

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
- Ruff lint passed and 109 files were already formatted;
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

The exact final candidate head and its required Quality Gates and Frontend
Quality Gates are pending the evidence commit, Draft integration PR, and
GitHub Actions run. Source-head CI is not substituted for candidate-head CI.

### 3. Future exact-main-merge CI

No main merge is authorized at this checkpoint. A future Human-authorized main
merge must be validated independently at its exact merge SHA; neither source
CI nor integration-candidate CI constitutes future exact-main-merge CI.

## Rollback and authority limits

Rollback is one bounded revert of integration merge
`7ce4ad11a65a43e7859f59aa5a921de849895eda` to first parent
`4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`, plus its REL evidence successor.
No data migration, persistence cleanup, Kubernetes action, Runtime/Provider
reversal, or external side-effect cleanup is required.

This candidate is not merged to durable main and S5-REL-026 is not closed. It
does not grant Product MVS completion, Contract or Schema freeze, Provider
certification, production Runtime, Knowledge or recovery support, Golden Demo
readiness, production readiness, Release readiness, or Release acceptance. The
next decision is the Human S5-REL-026 Review Gate after exact-candidate CI.
