# S5-IMPL-054 Checkpoint A Evidence

## Status

`PRE_ASSEMBLY_IMPLEMENTED / TRACK_B_INTEGRATION_REQUIRED / DO_NOT_MERGE`

- Authorized baseline: `4200bd33c489bd544c04c3209f58b5b84c80bd14`.
- Exact baseline CI: `33467767800 / SUCCESS`.
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

## Implemented pre-assembly result

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

## Current validation

- Focused backend traceability and unified assembly tests: `11 passed`.
- Frontend lint: passed.
- Frontend production build: passed.
- URL Context Playwright contract tests: `2 passed`.
- `make check`: Ruff passed; `1112 passed`, 13 explicit external-service skips.
- Pre-commit: Ruff lint, Ruff format, and pytest passed outside the socket sandbox.

## Controlled pause

S5-IMPL-055 is still active and is not durably integrated. The final 12-journey
real-service browser assembly, full regression, restart recovery, and final exact-head
CI must occur only after Track B is integrated into durable main and normally merged
into this branch. Track B paths must remain inherited and absent from this task's diff.
