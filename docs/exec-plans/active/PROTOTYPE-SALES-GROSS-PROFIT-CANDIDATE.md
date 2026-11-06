# Sales dimension gross-profit successor — isolated candidate only

Authority:2026-11-07 continuation instruction, same writer. Implement items1/2
of the existing `04-销售分维度毛利差额` finite option, without another model
sample or either original case execution. Installed UI-01 remains4f1bc94,
bundle65b28249…, generation11. Human business acceptance remains OPEN.

## Gate and fixed boundary

G1: write/review this plan before adding a separately versioned internal
executor/output contract and local Skill-content candidate. Existing SkillExecutor
and ResourceContent interfaces only. No endpoint, CRD, store, migration, lifecycle,
authorization, public frozen Contract or production composition changes.

Keep v1 sales executor, bundle, evaluator, CSV bytes and all live Skill revisions,
criteria, two Runs, artifacts, conversations, UNKNOWN/reservations and five READ
requests unchanged. Do not install this candidate or restart the installed UI
baseline. No Skill publication/activation, executor allowlist activation, standards
edit, supplement Run, permission expansion or model invocation.

## Computation and output contract

- Separate input/output `.v2` tags and executor revision2/configuration digest;
  explicitly selected in a local registry only. Existing v1 paths and exact
  serialization stay unchanged. Reject mixed-version dependencies and mismatched
  source/reference commitments; same five operations remain deterministic reads.
- Use the exact fixed synthetic source and ordered baseline/current periods.
  Decimal amounts, per currency only, no implicit FX or all-currency total.
  Posted SALE amounts/cost must be nonnegative; RETURN amounts/cost nonpositive.
  Never infer sign or missing cost; reject invalid posted financial data with a
  bounded reason and source-row/field diagnostic. Cancelled rows are excluded
  before financial aggregation, retained with exact row/line/raw provenance, and
  do not require computable financial amounts.
- Region/channel/product are separate decompositions. Provided nonempty labels
  remain unverified source labels, not certified ontology identities. Empty or
  explicit UNKNOWN/UNSPECIFIED/N/A/未知 labels enter a null unresolved bucket,
  retain raw values and warnings, and remain in totals and reconciliation.
  Never infer a dimension or silently drop it.
- Return netSales/cost/grossProfit baseline/current/delta for currency and groups.
  Group delta is that group's additive change contribution; retain source row IDs
  by period plus each included row's line, signed values, gross profit and signed
  baseline/current change terms. For every dimension and currency, independently
  sum group changes and compare with that currency's total change. Do not add
  the three decompositions together. Zero baseline growth is null with an explicit
  reason; use absolute baseline for nonzero signed bases. Contribution ratios are
  unnecessary and will not invent a denominator or causal interpretation.
- Output stays synthetic/observational/UNDETERMINED. Publish explicit candidate
  JSON schemas including required fields, metric definitions, unresolved groups,
  row proofs, exclusions, reconciliation and limits; contract digest is bound into
  revision2 configuration. Resource-level declarations and all operation schemas
  agree. No fallback or automatic v1-to-v2 interpretation.

## Independently reproducible evidence

Freeze current source/installed baseline, v1 outputs/bytes, original two Run and
artifact identities and protected-row digests before coding. Materialize the same
source from the existing immutable execution evidence, and verify the example
CSV's bytes/mapping reproduce it exactly; mismatch blocks same-source claims.
Use a separate integer-minor-unit CSV oracle that does not import the producing
executor, its validator or comparison helpers. It must bind CSV byte digest,
source lines and source snapshot, derive expected row terms/groups/totals, and
check all three decompositions separately for CNY/EUR/JPY. Preserve the earlier
attached table as historical corroboration, not the oracle or a Native artifact.

Test known row amounts and returns; cancellation, zero and negative bases;
missing cost, unknown/empty dimensions, positive RETURN sales/cost, wrong periods,
duplicate rows, invalid precision/NaN, cross-currency collisions, altered lineage,
omitted/duplicated row terms, tampered GP/group/reconciliation and mixed v1/v2
dependencies. Validate candidate schemas through existing bounded schema checks;
confirm v1 compatibility and exact executor resolution. Run focused isolation
checks then mandatory repository checks. No frontend change, rebuild or UI
installation is needed. Any further fixture repair must retain evidence and
strengthen or preserve checks, never weaken a production authority guard.

## Skill revision candidate and future owner gates

Generate content-addressed local candidate content with predecessor exact Skill
reference and current aggregate version, separate executor/configuration and
contract digests, local test results and independent expected/report digests.
No fabricated published revision ID, review decision, current readiness or Run.

Future formal supplement still requires: original resource owner independently
review/test/publish an actual immutable successor; explicit metric/criteria
confirmation with a separately versioned evaluator and source applicability;
exact registry/native/planning compatibility review; exact Plan/Skill/source and
current execution/Skill permissions; independently admitted distinct supplement
Run linked to the old Run as predecessor; actual durable artifacts/Outcome and
Human business acceptance. Old versions and evidence are not rewritten or
retroactively accepted. All these steps remain NOT REQUESTED/NOT RUN in this batch.

## Deliverable and preservation audit

Provide frozen scope, explicit schema/metric notes, immutable local Skill candidate,
deterministic sample output, CSV-row independent expectations/checks, edge-case
results, focused/full checks, reviewable patch and future-owner checklist. Label
everything LOCAL CANDIDATE / NOT INSTALLED / NOT PUBLISHED / NO NEW RUN.
After local checks, read-only audit must confirm installed4f1bc94 source/bundle,
process birth identities/config hashes, all protected rows, old artifacts and
shared43/16/USD12.669936 ledger facts are unchanged. Keep UI-01 available for
independent read-only review without waiting on its acceptance queue.

Pre-code encoding review: the current bounded Skill schema validator supports
neither null/union types nor conditional schema keywords. Do not widen it for
this candidate. Encode a zero-base rate as `rate:{status:BASELINE_ZERO}` with no
value, and a defined rate as `rate:{status:DEFINED,value:<decimal string>}`.
Encode unresolved dimensions as `valueStatus:UNRESOLVED,value:""`, retaining raw
label/presence on row proofs. These are explicit unavailable states, never a
zero growth percentage or a fabricated business identity. This supersedes only
the null wire encoding above; v1's null fields/bytes remain untouched. Runtime
and independent semantic checks must enforce the conditional invariants in
addition to existing bounded schema shape checks. Limit this new candidate to
1000 rows,4MiB input/output,24 levels and200000 properties,5s deterministic
computation; exceeding limits fails with a known outcome, never truncates.

Determinism review before completion: use a newly constructed Decimal Context
(precision38, ROUND_HALF_EVEN) in producer and oracle, rather than inheriting
host rounding/signal traps. Test a repeating1/3 rate under precision6/ROUND_UP
and an Inexact trap, preserving the host context on return. The first local
candidate is retained under historical content IDf6a436… with its exact source;
its incomplete full check is not acceptance. Regenerate a distinct content-hash
candidate and rerun focused/mandatory checks, without any live installation.
