# S5-IMPL-011 — Technical View evidence

## Candidate identity

- Session: `S5-IMPL-011 — Technical View`
- Authority: `HUMAN_ALLOCATED`
- Baseline: `4d23f76e6f8a1afa1ada45ac8ac3fb379aa811f9`
- Branch: `codex/s5-impl-011-technical-view`
- Shared snapshot authority: `NON_AUTHORITATIVE`
- Projection direction: `SIBLING`
- Technical derived from Product: `NO`

## Exact authorized path inventory

The candidate changes exactly these 27 Human-authorized paths:

1. `console/frontend/src/pages/ProductViewPage.tsx`
2. `console/frontend/src/product/ProductNavigation.tsx`
3. `console/frontend/src/product/adapter.ts`
4. `console/frontend/src/product/fixture.ts`
5. `console/frontend/src/product/types.ts`
6. `console/frontend/src/product/journey.ts`
7. `console/frontend/src/shared/executionSnapshotTypes.ts`
8. `console/frontend/src/shared/executionSnapshotFixture.ts`
9. `console/frontend/src/shared/projections.ts`
10. `console/frontend/src/shared/urlContext.ts`
11. `console/frontend/src/shared/SelectedExecutionContext.tsx`
12. `console/frontend/src/shared/ViewSwitcher.tsx`
13. `console/frontend/src/pages/TechnicalViewPage.tsx`
14. `console/frontend/src/technical/adapter.ts`
15. `console/frontend/src/technical/TechnicalNavigation.tsx`
16. `console/frontend/src/technical/TechnicalGraph.tsx`
17. `console/frontend/src/technical/ExecutionIdentityPanel.tsx`
18. `console/frontend/src/technical/RuntimeProviderPanel.tsx`
19. `console/frontend/src/technical/CapabilityEvidencePanel.tsx`
20. `console/frontend/src/technical/OutcomeRecoveryPanel.tsx`
21. `console/frontend/src/App.tsx`
22. `console/frontend/src/components/ConsoleShell.tsx`
23. `console/frontend/src/i18n/messages.ts`
24. `console/frontend/src/styles/app.css`
25. `console/frontend/tests/test_s5_impl_011_technical_view.py`
26. `tests/test_s5_impl_011_technical_view.py`
27. `docs/evidence/s5/v0.2/s5-impl-011/README.md`

No public API, backend DTO, Canonical Graph, dependency, lockfile, workflow,
CRD, Runtime, Provider, production Knowledge, Golden Demo, Release, Registry,
or Project State path changes.

## Shared snapshot and projections

`sharedExecutionSnapshot` is one deeply frozen frontend preview dataset. Its
exact classifications are:

- `DETERMINISTIC`
- `SYNTHETIC`
- `NON_AUTHORITATIVE`
- `TECHNICAL_PREVIEW`
- `NO_NETWORK`
- `NO_RUNTIME_OR_PROVIDER_INVOCATION`

The only executable projection flow is:

```text
sharedExecutionSnapshot -> projectProductSnapshot()
sharedExecutionSnapshot -> projectTechnicalSnapshot()
```

The Technical projection rejects Product projection input. Product filtering
copies permitted fields and leaves the shared input unchanged. Technical graph
components iterate the projected raw relations; they do not infer, reverse, or
reconstruct relations or cardinality.

## Identity, context, and evidence

Product and Technical views preserve the same selected Digital Employee,
approved revision, work, Workflow, Task, Platform Execution Identity, graph
snapshot identity, authorization decision/reason, Outcome, Evidence, Citation,
Runtime IDs/support classifications, and Provider correlation IDs. Provider
IDs remain correlation-only.

The URL contains only validated stable identifiers. Unknown, extra,
contradictory, or malformed context falls back to the deterministic safe
selection and never creates an identity or relation. Product → Technical →
Product retains the selected context. Locale state remains separate.

## Honesty and limitations

- Native: `AVAILABLE / COMPONENT_TESTED_CANDIDATE / NOT_CERTIFIED`.
- OpenClaw: `EXPERIMENTAL / CURRENTLY_UNAVAILABLE / SUPPORT_NOT_GRANTED`.
- Hermes: `EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE / SUPPORT_NOT_GRANTED`.
- DENY displays zero Provider calls and no live citation retrieval.
- UNKNOWN, failed, skipped, blocked, unavailable, and downstream states remain
  distinct from success.
- Recovery is visibly downstream; no exactly-once claim is made.
- Citations are synthetic/view-only and do not claim production Knowledge/RAG.
- No live Runtime, Provider, recovery, Golden Demo, or release execution occurs.

## Validation

Local candidate validation on 2026-08-27:

- direct frontend-local Technical tests: **24 passed**;
- existing Product View tests: **33 passed**, unchanged;
- combined Product/Technical root tests: **57 passed**;
- root shim: exactly **24** S5-IMPL-011 nodes;
- duplicate S5-IMPL-011 nodes: **0**;
- full repository `make check`: **673 passed**, with one existing
  Starlette/httpx deprecation warning;
- Ruff lint: passed;
- Ruff format check: **109 files already formatted**;
- frontend ESLint: passed;
- frontend production build: passed, **62 modules transformed**;
- TypeScript compilation: passed through `tsc -b`;
- `git diff --check`: passed;
- API/CRD/schema, backend DTO, Canonical Graph, dependency/lockfile, workflow,
  ownership/import, secret/redaction, network/storage/side-effect, relative-link,
  and rollback audits: passed.

Exact-candidate GitHub Quality Gates and Frontend Quality Gates are resolved by
the immutable Draft PR head and matching Actions run. This non-self-referential
evidence file cannot contain its own final commit SHA or a run created only
after that SHA is pushed.

## Browser QA

Interactive QA passed for English and Simplified Chinese Technical Views,
mid-journey locale switching, Product → Technical → Product round-trip,
validated URL reload, malformed URL fallback, identity drill-down, raw relation
expansion, all Runtime/Provider classifications, ALLOW plus synthetic Citation,
DENY with zero calls, UNKNOWN/failure/unavailable/downstream honesty, recovery
limitations, desktop presentation, keyboard traversal, visible focus,
accessible names and expanded/current states, and zero browser warnings/errors.

At `390×844`, `window.innerWidth`, `document.body.scrollWidth`, and
`document.documentElement.scrollWidth` all measured exactly **390 px**. The
page had no horizontal overflow.

## Rollback and claims

Rollback is a single bounded revert of the S5-IMPL-011 implementation/evidence
commit. It requires no data migration, persistence cleanup, API rollback,
Kubernetes action, Runtime/Provider reversal, or external side-effect cleanup.

This candidate does not grant Product MVS completion, durable integration,
Provider certification, production readiness, Golden Demo completion, Release
acceptance, Contract/Schema freeze, or merge authorization.
