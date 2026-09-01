# S5-IMPL-054 Final Assembly Evidence

## Status

`ASSEMBLED / CLEAN_BROWSER_GATE_PASSED / DRAFT / DO_NOT_MERGE`

- Current durable main: `9cb31e147d6f7eebf5299a652c0f3fe4f4e6da56`.
- Exact-main CI: `33484450551 / SUCCESS`.
- Accepted pre-resumption source head: `8d8fdb77d29bb0b9bc4e8e98ed2ff1ae54af1ef9`.
- Final resumption update: normal `--no-ff` merge commit
  `1e6231329f179a93d90caa73d3aae5f490e4b57b`; its parents are the accepted source
  head followed by current durable main. No rebase, squash, cherry-pick, amend, or
  accepted-history rewrite occurred.
- Branch: `codex/s5-impl-054-cross-view-context-evidence-inspector`.
- Architecture gate: G1. No migration, dependency, public Contract, lifecycle,
  execution, or Evidence-authority change is included.

## Binding contracts

The internal URL context contains only `kind`, `resourceId`, `revisionId`, `digest`,
`view`, `evidenceId`, `relationshipId`, `claimKey`, `factKey`, `businessStepId`,
`query`, `kindFilter`, `lifecycleFilter`, `timeFrom`, `timeTo`, and `returnTo`.
Parsing rejects unknown, duplicate, partial exact-tuple, unsupported-view, external
return, sensitive-return, control-character, and oversized values. Serialization is
deterministic. Namespace and security domain are not client authorization inputs.

The Traceability DTO is a private derived read model with the approved `subject`,
`claims`, `evidence`, and `technicalFacts` fields. Authorization and exact-subject
resolution precede mapping. It reads existing resource lifecycle, Human review,
Citation, discovery, invocation, and relationship facts without persisting or minting
a generalized Evidence authority.

## Assembled result

- Exact Product, Technical, and Evidence routes preserve one subject tuple.
- Claim-to-Evidence-to-Fact and Fact-to-Claim/business-step links are bidirectional.
- The Evidence Inspector is responsive, modal, keyboard focused, and returns focus to
  an invoking claim or fact.
- Catalog filters, relationship identity, time range, selected Evidence, and return
  context remain canonical URL state.
- Denied and absent responses disclose no requested resource identity and invalid
  exact tuples fail with one disclosure-safe not-found reason.
- Runtime Profile execution and verified Model claims remain explicitly unsupported.
- Shared controlled states cover loading, saving, empty, validation, denied,
  not-found, conflict, stale, unavailable, partial, retryable, recovery-required, and
  unsupported presentations.
- Exact relationship provenance supplies all five Agent bindings through Evidence
  navigation. Technical facts link back to affected Product claims and business steps.
- Focus restoration waits for the exact invoking claim or fact to render after closing
  the Inspector, including the 390 by 844 keyboard journey.

## Durable correction inheritance

The following correction paths are inherited byte-for-byte from durable main and are
absent from the authoritative PR diff:

- `console/frontend/src/resources/SkillWorkbenchPage.tsx`
- `console/frontend/tests/e2e/skill-mcp-workbench.spec.ts`
- `console/frontend/tests/e2e/knowledge-workbench.spec.ts`
- `docs/evidence/s5/v0.2/s5-impl-065/README.md`

Their Git object IDs at the merge head and durable main are respectively
`6b991b5df85aaa2d4bfe10b5328c7144d0a058c1`,
`eac8e1511de6f780390f6fc502c2e345faa88dc5`,
`cf18bb3714993dbc64ec8367ec63f5f816909edf`, and
`15f3588636ea2c501a89dd31f1578140e939409b`.

## Clean real-service browser acceptance

One new complete Chromium suite was run exactly once with one worker against a
production-built frontend and real backend. It passed `12/12` in `36.1s`, with zero
skipped tests, zero retries, and no manual rerun.

- PostgreSQL identity: disposable database `s5_impl_054_final`, PostgreSQL `15.4`,
  container `1cfeddc2713659867d0ff46804b26a4d1279492cdff6e98de9a75a67bb0111df`.
- Qdrant identity: disposable service `0bd4b4974c777d92eb614b0a7a149e9381c34ceaaff4ede4c68cca6bacf4e0c8`,
  Qdrant `1.15.4`, commit `20db14f87c861f3958ad50382cf0b69396e40c10`.
- Before backend startup PostgreSQL had zero user tables and zero application schemas;
  Qdrant had zero collections.
- The backend applied the exact repository migration ledger from empty state. Before
  fixture creation application tables contained zero records, while the startup-created
  `knowledge_v1` collection contained zero points and zero indexed vectors.
- Skill/MCP distinct accessible status assertions passed; the former status ambiguity
  did not recur.
- The Knowledge journey proved a published/indexed Pack with a Qdrant snapshot before
  removing the derived collection. Purge then returned `202 Accepted` and persisted
  `RECOVERY_REQUIRED` for
  `knowledge:690d3ecf-bc63-4f8d-89b2-908ba83ea9c4`, revision
  `knowledge-revision:edb21319-5278-4d96-95f1-d25c7d325695`, digest
  `3b953ef072865cd2f20774175a97f9993e253cd9fafdbbbf0ffabccfbbba7794`, and snapshot
  `index-snapshot:3bc1736d-7a91-4b1b-affd-bff8c9b8fdfb`.
- The Wave 3B test passed all twelve ordered Product/Technical/Evidence journeys,
  including deterministic exact URL context, denial/absence nondisclosure, restart and
  refresh reconstruction, responsive layout, keyboard navigation, and focus return.
- Only the disposable backend, containers, anonymous test volume, and generated test
  artifacts were removed after Evidence capture. No persistent Demo, developer, or
  user data was touched.

The earlier reused-database attempt remains recorded as `11 passed, 1 failed`; it was
not used as acceptance evidence and was not manually rerun. This newly authorized
clean-environment invocation is the sole final browser acceptance evidence.

## Current validation

- Focused backend traceability and unified assembly tests: `11 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- Complete serialized clean-service Playwright: `12 passed`, zero skipped/retry.
- `make check`: Ruff and format passed; `1141 passed`, with 13 expected tests skipped
  after the disposable real services were removed.
- `pre-commit run --all-files`: passed without tracked-file modification.
- `git diff --check`: passed.
- Exact-path, inherited-path, migration, ownership, Secret, and prohibited-scope
  audits: passed.

## Next gate

Push the Evidence commit, obtain fresh exact-head CI, and convert PR #109 to Ready for
Review only if that CI succeeds. Human Durable Integration review remains required.
Do not merge, deploy, allocate REL automatically, or claim Wave 3B or v0.2.2 complete.
