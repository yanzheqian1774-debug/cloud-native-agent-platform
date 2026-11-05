# Employee resource composition and continuous delivery

G1, user-authorized package03/04 continuation, 2026-11-05.

## Current gap and approved boundary
Existing owner supports AGENT/WORKFLOW/SKILL/MCP/KNOWLEDGE/RUNTIME_PROFILE composition, exactly one Agent, at most one Runtime Profile, no duplicate kind/resource. Trusted create projection is unnecessarily Agent-only. Extend this projection additively without changing owner contracts, lifecycle, authority architecture, database, CRDs or D11 limits. Existing single Agent commands remain compatible. Reuse current exact READ mappings including existing MCP prepared reference. No implicit grants, no substitution, no auto-upgrade. Existing continuation interfaces remain authoritative for instantiation/execution/evaluation.

## Implementation
- Extend trusted create schema/types to existing owner composition shapes; retain bounded cardinality and strict input checks.
- Published readable resource directory supplies selectable exact candidates; one Agent required, optional grouped resources. Preserve selected exact references across pages, reject duplicates, limit128, no hidden/draft/disabled candidates offered.
- Guard stale session/candidate fetch responses; frozen create payload and existing unknown-result behavior stay unchanged. Existing explicit IDs retained for compatibility; automatic local identity generation follows existing owner identity constraints, no identity architecture change.
- Visual grouping with direct preview, declared readiness separate from execution readiness. Scope UI CSS to employee assembly.
- Inspect/reuse continuation policy and prepared execution path for bounded sales/supplier successor cases, never replay original Runs or unknown calls; no wider permissions or budget.

## Validation
Backend schema/cardinality/member authorization tests and isolated PG tests; frontend multi-resource selection, paging, disabled/unauthorized, frozen payload, identity switch and mobile tests. Lint/build and repository hooks. Actual authenticated create/readback, exact resource preparation, successor execution/evaluation if supported by existing policy; otherwise retain explicit limitations and progress independently. Read-only regress original supplier/sales history, compare baseline owner rows and budgets. Same viewport prototype/actual screenshots, inspect and record remaining visual gaps. No full-package closure without all page evidence.
