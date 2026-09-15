# S5-V023-REL-317 — 315/316 trusted preparation and Native bounded combination

## Allocation and fixed inputs

- Session: `S5-V023-REL-317`.
- Type / gate: `REL / G1 / BOUNDED_INTEGRATION`.
- Human allocation: `AUTHORIZED` on 2026-09-15.
- Sole writer: this REL Codex conversation; no sub-agent is permitted.
- Branch: `codex/s5-v023-rel-317-trusted-native-combination`.
- Isolated worktree: `/Users/tristan/.codex/worktrees/18a6/cloud-native-agent-platform`.
- Approved base source/tree: `f189212232fc194859a695f0307e83b0c7b73c0f` / `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Fixed REL-316 source/tree: `3cc98cde9452e5036ad9bd44981f5fff9499b011` / `bb614158fded36277bced028baed88240f29f8d0`.
- Fixed IMPL-315 source/tree: `91bbb64cb0367ceda31fc47a4cf0745b3ac5b251` / `6d48a75d2688ffe172a93e95718c7c95698114f6`.
- Integration order: receive REL-316 first, then add IMPL-315 symbol by symbol.
- Human-only gates: Ready, merge, deployment, release, combination acceptance, original PR/Session disposition, and Session close.

Startup verification found the approved base still equal to `origin/main`, both
fixed objects and trees exact, their merge base equal to the approved base, and
no accessible local/remote branch, worktree, PR, Issue, or Registry allocation
for REL-317. The original #171/#172 branches and worktrees remain read-only inputs.

## Actual path closure

The pre-integration closed set is recorded in
[`path-closure.txt`](../../evidence/s5/v0.2/s5-v023-rel-317/path-closure.txt).
It is the exact union of the two fixed candidates relative to the approved base,
plus these REL-317-owned paths:

- `.github/workflows/s5-v023-rel-317-trusted-native.yml`;
- `console/frontend/playwright.rel-317.config.ts`;
- `docs/engineering/S5-V023-REL-317-HANDOFF.md`;
- `docs/evidence/s5/v0.2/s5-v023-rel-317/**`;
- `docs/exec-plans/active/S5-V023-REL-317-TRUSTED-NATIVE-COMBINATION.md`;
- `docs/governance/REGISTRY.md`;
- `scripts/acceptance/s5_v023_rel_317_run.sh`;
- `scripts/acceptance/s5_v023_rel_317_native_l3.sh`.
- `scripts/acceptance/s5_v023_rel_317_native_l3.py`.

An additional implementation or test path may enter the closure only when a
concrete combination failure proves it necessary and this plan records the
reason. A new owner, contract, public API/CRD, persistence dependency, or
cross-plane boundary is a stop condition rather than permission to expand.

## Symbol-level combination plan

1. Create a provenance-preserving merge commit that receives the exact REL-316
   source without rewriting its history.
2. Merge the exact IMPL-315 source without committing, then resolve the five
   shared paths by symbol rather than choosing either whole file.
3. In `authority_contracts.py`, retain REL-316 exact-decision and continuation
   ports while adding IMPL-315 caller-owned multi-grant and locking interfaces.
4. In `authority_postgres.py`, retain REL-316 replay/CAS/creator-continuation
   behavior while adding IMPL-315 atomic grant reads, revocation serialization,
   and `_authorization_grants_locked_checkpoint()` at its original lock point.
5. In `grant_administration_application.py`, retain REL-316 creator receipt and
   Employee continuation semantics while adding IMPL-315 caller-owned
   transaction and current-grant/revocation behavior.
6. In `app.py`, retain REL-316 Workbench/BFF/bootstrap lifecycle and close order
   while adding IMPL-315 Native dispatch composition only. No product-to-Native
   route is added.
7. In `REGISTRY.md`, retain both immutable input rows and add one REL-317 row;
   neither input acceptance is widened.

## Migration plan

- Receive REL-316 `0020_business_problem_creator_receipt.sql` once at its exact
  accepted blob.
- Keep `0021_openclaw_runtime_binding.sql` absent; REL-314 is excluded.
- Receive IMPL-315 `0022_native_execution_dispatch.sql` at its exact blob.
- Verify the loader orders discovered filenames rather than requiring contiguous
  numbers; verify 0022 SQL references only schema objects provided by the base
  through 0018 or by 0022 itself, and does not depend on 0021.
- Exercise empty-schema and ledger/checksum behavior on a REL-317-owned database.
  Never create an empty migration or rewrite an applied SQL artifact.

## Validation strategy

1. Prove source/tree/parent provenance, shared-symbol matrix, migration checksums
   and combined application startup/close.
2. Run authority unit/PostgreSQL tests for REL-316 exact decision/continuation
   and IMPL-315 atomic grant reads, revocation serialization, lock checkpoint and
   races.
3. Run REL-316 Problem/Criteria/Employee/BFF tests, frontend lint/build, default
   and dedicated Playwright collection, and a fresh REL-317 HTTPS/Chromium
   applicant/administrator click journey using only REL-317 assets.
4. Run IMPL-315 application/PostgreSQL/operator/runtime regressions for
   observe-first recovery, crash recovery, UNKNOWN non-redispatch, fencing and
   technical terminal return.
5. Run `make check`, normal commit hooks, focused diff/status review, push without
   force, and the required CI on one Draft PR.
6. Rebuild the combined source into a REL-317-tagged image and run a fresh
   REL-317 Native L3 using a dedicated PostgreSQL database, kind cluster, ports,
   evidence directory and mock provider. Record Git source/tree, build-context
   manifest and hash, build parameters, image/repo digest, Runtime/Worker running
   image IDs, Task UID and PostgreSQL linkage. If the final source differs from
   the tested source in executable/build inputs, rebuild and rerun.

Environment skips are reported separately from executed passes. Existing
299/305/310/314/315/316 databases, clusters, credentials and evidence are never
used, reset, or deleted. Failure history is append-only; uncertain effects are
observed before any retry.

## Compatibility, risks, rollback, and stop conditions

The intended compatibility change is additive and internal: REL-316 product
preparation and IMPL-315 Native dispatch coexist without being connected into a
new product execution chain. The principal risks are loss of exact-decision or
continuation behavior, loss of the Native lock checkpoint, duplicate lifecycle
composition, accidental migration 0021 dependency, and L3 evidence that is not
bound to the final source/build/image.

Stop for G2 if completion requires a public CRD/API-group or frozen-contract
change, Task/Workflow/Runtime lifecycle change, new persistent infrastructure,
Control Plane boundary change, authentication architecture change, or
product-to-Native ownership decision. Ordinary integration defects may be fixed
within the closed set and rerun through the full affected validation.

Rollback is branch abandonment or normal commit revert. REL-317-owned runtime
assets may be retained for evidence or explicitly deleted only after ownership is
proven. Original input branches, worktrees, PRs, Sessions, databases, clusters,
credentials and evidence remain untouched.

## Candidate validation status

The symbol-level combination, dedicated PostgreSQL suites, frontend lint/live
build, isolated HTTPS/Chromium product journey, `make check`, normal hooks, and
fresh combined-source Native L3 have passed. The L3 source is `eff1b583...`, tree
`4943839...`; later Evidence-only commits are outside its recorded build
context. Draft PR [#173](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/pull/173)
is open and remains Draft. The implementation head `97d5ba1...`, tree
`d79a2ae...`, passed all 9 PR-head checks after two bounded acceptance-isolation
fixes. See the
[handoff](../../engineering/S5-V023-REL-317-HANDOFF.md) and
[Evidence index](../../evidence/s5/v0.2/s5-v023-rel-317/README.md).
