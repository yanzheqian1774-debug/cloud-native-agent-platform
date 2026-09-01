# S5-IMPL-054 Final Assembly Evidence

## Status

`ASSEMBLED / COMPLETE_SUITE_BLOCKED_BY_TRACK_B_SELECTOR / DRAFT / DO_NOT_MERGE`

- Current durable main: `bd0644dc32303799f6cad57267da742d4bacbca6`.
- Exact-main CI: `33473035538 / SUCCESS`.
- Old source head: `6705620c0e60f58a9fad5b47c8ff1e9552b7b3f1`.
- Source update: normal merge, commit `e68295d170236e376fbfc2a469d5655b6211a9bc`;
  parents are the old source head followed by current durable main. No rebase,
  squash, cherry-pick, or accepted-history rewrite occurred.
- Branch: `codex/s5-impl-054-cross-view-context-evidence-inspector`.
- Architecture gate: G1. No migration, public Contract, lifecycle, execution, or
  Evidence-authority change is included.

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
- Track B's 20 paths are inherited byte-for-byte from durable main and are absent from
  this branch's diff against main. No migration or new Evidence authority is present.
- Exact relationship provenance supplies all five Agent bindings through Evidence
  navigation. Technical facts link back to affected Product claims and business steps.
- Focus restoration waits for the exact invoking claim or fact to render after closing
  the Inspector, including the 390 by 844 keyboard journey.

## Current validation

- Focused backend traceability and unified assembly tests: `11 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- URL Context Playwright contract tests: `2 passed`.
- Focused real-service Wave 3B Playwright: `3 passed`, including all twelve ordered,
  unconditional journeys against the production frontend, PostgreSQL, Qdrant, and a
  restarted real backend.
- `make check` with real PostgreSQL and Qdrant: Ruff and format passed; `1125 passed`
  with no service skips.
- Complete Playwright authoritative attempt 1: `11 passed, 1 failed`. The Wave 3B
  twelve-journey test passed. The failure is the pre-existing Track B
  `skill-mcp-workbench.spec.ts` selector `getByRole("status")`, which resolved both
  the transient saving status and Invocation Evidence status. No manual rerun was
  used.

## Controlled stop

The timing ambiguity cannot be corrected within Track A's exact whitelist: both the
ambiguous test and its `SkillWorkbenchPage` product state are Track B paths. Changing
either would violate the authorized-path and Track B inheritance conditions. PR #109
must remain Draft. A Human must authorize the Track B selector/product-state correction
and a new complete-suite gate before Ready for Review or Durable Integration routing.
