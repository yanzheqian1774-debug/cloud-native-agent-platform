# S5-V023-REL-317 bounded combination evidence

## Provenance and symbol-level result

- Approved base: `f189212232fc194859a695f0307e83b0c7b73c0f`, tree
  `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Fixed REL-316: `3cc98cde9452e5036ad9bd44981f5fff9499b011`, tree
  `bb614158fded36277bced028baed88240f29f8d0`.
- Fixed IMPL-315: `91bbb64cb0367ceda31fc47a4cf0745b3ac5b251`, tree
  `6d48a75d2688ffe172a93e95718c7c95698114f6`.
- Receiving merges: REL-316 `1d92ce353693f5f91ccb27051d17cdbb2bee4c2d`;
  IMPL-315 `2849e5bb819471764df742090924eca180c5b0a4`.
- Both fixed inputs are candidate ancestors. The final PR head/tree is recorded
  after it exists.

The [path closure](path-closure.txt) is the exact input-diff union plus
REL-317-only plan, verification, Evidence and CI assets.

| Shared path / symbol | Preserved combination |
| --- | --- |
| `authority_contracts.py` / `CurrentAuthorizationReader` | REL-316 complete current exact-decision port plus the caller-owned atomic multi-grant port used by IMPL-315 |
| `authority_postgres.py` / linearized readers | REL-316 exact decision and continuation-compatible authority plus IMPL-315 grant locks, revocation serialization and `_authorization_grants_locked_checkpoint()` in both owner-transaction read paths |
| `grant_administration_application.py` / `GenerationAuthorizationReader` | REL-316 exact decision, creator receipt and continuation consumers plus the already-strengthened IMPL-315 atomic `has_current_grants()` seam |
| `app.py` | REL-316 Workbench/BFF/bootstrap and product lifecycle plus migration 0022 and `NativeDispatchApplication`; no product route dispatches Native work |
| `REGISTRY.md` | immutable REL-316 and IMPL-315 rows plus a separate REL-317 row |

No public CRD/API-group, frozen Contract, authorization owner, dispatch,
fencing, Task/Workflow/Runtime lifecycle or technical-terminal ownership changed.

## Migrations

- 0020 SHA-256:
  `0d6d0551531c84254e970f11eecb2b7b6b52b8112d1974ee020833e9ab62aec7`.
- 0022 SHA-256:
  `e98bf162b1fdd9dc9e0883894b9afb6612447e45c43110dcc821f2cc0cde238f`.
- 0019 and 0021 are absent; no placeholder was created.
- 0022 owns an independent version-22 ledger and references only
  execution-authority objects created by 0008. It has no source, SQL, loader or
  runtime dependency on 0021.
- The browser database recorded business-problem versions 13 and 20; version 20
  has the exact 0020 checksum and
  `business-problem-creator-receipt-postgresql-v20` adapter.
- The passing L3 database recorded exact checksums for execution version 8,
  authority version 18 and Native version 22. Independent component ledgers
  permit the intentional filename gap.

## Validation

- Merge and normal commit hooks: PASS.
- Native/core/operator targeted suite: `35 passed`, `13 skipped` before a
  database was supplied; every skip was PostgreSQL-only.
- REL-316 unit/BFF/bootstrap suite: `84 passed`.
- Dedicated PostgreSQL authority/Native: `26 passed`, no skips.
- Dedicated PostgreSQL continuation/Employee/exact-authority: `36 passed`, no
  skips.
- Frontend lint and live production build: PASS (existing chunk-size warning).
- Dedicated Playwright allowlist: exactly one REL-317 spec.
- Dedicated HTTPS/PostgreSQL/Chromium applicant/administrator journey: PASS.
  `playwright.json` SHA-256:
  `0bb6124bff13d5ede12c6c5318158e7cd54be2e7852aae924691403be294c1c3`;
  `startup.json` SHA-256:
  `3fc17cd2cb9052144cff1ba3e26f7c93abe3c94de9fe0e7b92191b693ec5e1e6`.
- `make check`: PASS; Ruff passed, 427 Python files were formatted, and pytest
  reported `1686 passed, 181 skipped`. These external-environment skips are
  separate from the no-skip dedicated PostgreSQL suites.

## Fresh combined Native L3 hard gate

The passing rerun is bound to source
`eff1b583ae249bd748d814dbe2ca2be2ced1d98e`, tree
`494383914feba10d2e86a53dd6f62ae102a228d3`, and selected build-context
manifest digest
`23197fbf0d5d59e936a95d941bf17691617ff8e07d6ccefcc3132aaa0da6e03a`.
Later documentation-only commits are outside that manifest and need no rebuild.

- PostgreSQL: container `s5-v023-rel-317-postgres`, database
  `s5_v023_rel_317_native_r2`, host port `127.0.0.1:55427`.
- kind: cluster `s5-v023-rel-317-r2`, context
  `kind-s5-v023-rel-317-r2`, namespace `s5-v023-rel-317-native`.
- Worker tag/config ID: `s5-v023-rel-317-worker:eff1b583ae24` /
  `sha256:9d1e5755b0ef3b5285df9c63c643a06c745e4c04cb30332824f3fb9c2d6407fe`.
  The running Job reported that config ID through kind import digest
  `sha256:a65d8d8fccbd1e058577ad3d2f56afa6c9033f50ce1876e105e84ff6f4867d7f`;
  containerd tag manifest:
  `sha256:ec148116337f6f678d1681db157ebbb057c0c267f73422bb29dd90aa5cfc620c`.
- Runtime tag/config and running ID:
  `s5-v023-rel-317-runtime:eff1b583ae24` /
  `sha256:a5fb6b808bacb0d5d3cd65a9ba9d0e4801f122bade45bb357a001617d73338a0`;
  containerd manifest:
  `sha256:218b66061a2ede1ee32be1102c5612ce375b5597cf46413cfc504d18f4d05ad9`.
- Command:
  `native-dispatch:b44a79ad2f7cc83944b1ddd54a558303f7437310b4047325cd50bda91578c0a4`.
- Attempt:
  `attempt:06b3d0389a53de942f6b0ca6bf7aac6fbda8cafdd951c7a3000444aeb7283b21`.
- Task name/UID: `rel-317-native-1d1f1b5fad9b738cab13955b583c62e6` /
  `374a74cd-0d2b-42ae-b996-972287409590`.
- Ordered facts: `QUEUED`, `CLAIMED`, `EFFECT_STARTED`, `CORRELATED`,
  `SUCCEEDED`; stable worker `rel-317-worker-stable`, claim generation 1.
- Command and Attempt are `SUCCEEDED`; exactly one Evidence, one technical
  Outcome with `business_problem_resolved=false`, and one successful Runtime
  `POST /v1/invoke` were recorded.
- Raw passing bundle `SHA256SUMS` digest:
  `066bfe8b26d8bb9fcb0d36a94b1a03073334494aa73b5c229822dca157350831`.

This proves Native L3 with a mock provider. It does not prove a real model call,
business-problem resolution, L4/L5, production packaging, deployment, release,
or a product-interface-to-Native execution chain.

## Failure history and asset preservation

1. Port 55417 was occupied. The just-created REL-317 container failed before
   startup and was removed; the unrelated port owner was untouched.
2. First L3 source `70d0c0c...` completed the real execution once, but its
   evidence reader used two wrong column projections. The database, cluster,
   Job, Runtime and successful Task remain preserved; Task UID
   `a78cf00d-08d7-4c05-9068-2f711b21605b`. No redispatch occurred.
3. The corrected source was rebuilt and rerun with a separate database and kind
   cluster; the complete hard gate passed.

Raw evidence is preserved under
`/Users/tristan/.codex/evidence/s5-v023-rel-317-trusted-native/`. Both REL-317
clusters and the REL-317 databases remain available. No
299/305/310/314/315/316 runtime asset, credential directory or raw evidence was
used, reset, or deleted.
