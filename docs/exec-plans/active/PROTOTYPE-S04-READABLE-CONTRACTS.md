# S04 accurate read-only contract projection (G1)

2026-11-06, sole writer, original third/fourth package scope. Installed baseline
75a60bd0bcbb510bda3ce22df494ac7f95286260;41calls/16unsettled/USD12.598116,
no pending Native/model jobs. Main dual-case business acceptance remains OPEN.

## Scope and interfaces

Replace S04's top-level {} and raw operation JSON default with an operation
selector, readable input/output field tables and validation declarations. Only
already-authorized exact resource revision facts are projected. No API/backend,
resource schema, owner, permission, lifecycle, model or execution change.

- Empty resource-level schema means no resource-level declaration; it never means
  no operation inputs/outputs. Read the selected operation's own schemas. Missing
  fields/type/description/source remain explicitly undeclared. Nested objects,
  arrays and required references need honest bounded projection; retain raw JSON.
- Show declared type, required membership, enum/const, numeric/string/array bounds,
  pattern, additional-properties and descriptions without inventing business
  fields from the S04 image or treating schema agreement as execution validation.
  Field source is its exact resource/revision + operation/input/output schema path;
  a business-data source or mapping is not inferred from a field name.
- Detect only certain structural contradictions (e.g. required field absent under
  additionalProperties=false, duplicate operation names, conflicting explicit type
  and const/enum). Unsupported references/compositions remain not fully projected,
  not declared compatible or rewritten. No executable validator or inferred
  cross-operation compatibility is added.
- Associate the exact resource/current and published revision/digest, executor
  revision/config digest, already-saved current-revision test facts, and existing
  authorized reference-impact GET. Tests/publication/actual use remain separate;
  readonly links to existing tabs do not run tests or alter resources.

## Layout and validation

1280x900 is the primary viewport; render the same original S04 source at that
viewport and record its unchanged matrix SHA. Main field tables and a compact
right context column follow the existing S04 layout; raw JSON and long exact IDs
are progressive disclosure. No copying sample business fields or reference counts.

Browser checks cover actual declaration shapes, empty/missing schemas, certain
contradictions, partially projected unions/references, absent/denied impact, exact
revision/test separation, operation selection restoration, narrow layout and zero
POST on browsing/refresh. Regress access, dynamic revocation and identity-change
guards without weakening them. Mandatory lint/build/commit checks precede immutable
installation. Actual normal-resource READ checks preserve resource/test/publication/
employee rows and the provider ledger; controlled missing/incompatible/denied states
are separately labelled and cannot stand in for live business acceptance.

Parallel independent read-only review checks existing old-call READ renewal and
diagnostic owner routes. It cannot write, renew, dispatch or expand old323/324
authority. Deterministic S04 work does not wait for a diagnostic result. No model
sampling, profile/timeout/budget change, replay or automatic release of UNKNOWN.

The previous resource-recovery plan's bare supplier UUID is only its leaf, not a
formal managedResource identity. Actual authoritative resource identity is
skill-definition:9e4366e8-5572-4994-a35e-2b35692cd4bd and published revision is
skill-revision:f19626a1-76de-419c-b56e-cefe32b63b36. The rejected missing-prefix
test is retained separately; this batch uses original owner receipts for identity.

## Bounded review and targeted checks

35 resource browser checks passed;32 isolated PostgreSQL boundary checks passed,
including original access and dynamic management/revision READ revocation. The
access harness now waits until the original failed receipt read finishes before
switching identity or permitting recovery: previously it sampled/counts or changed
fixture response availability while that initial GET was still in flight. No
product timeout, permission assertion or no-repeat assertion was weakened.

Independent review caught a certain-conflict false positive for patternProperties
and object/nonobject unions. The finite contradiction check is now restricted to
simple single-object declarations without unresolved matching/composition; unions
and patterns remain explicitly partial. A negative browser case proves both stay
unlabelled as incompatible. Raw declarations remain exact and untouched.

Authority audit: exact PLAN/READ renewal exists under WORKBENCH_PLANNING; old usage
READ under PROVIDER_USAGE_REVIEW requires its original independent grant owner.
There is no standalone existing resource-policy metadata READ auto-renewal action.
The new salesR2 usage READ is a first exact grant, not an old renewal. A future
bounded UI may submit exact READ requests and recover their state, but cannot
approve them or trigger resource preparation/plan confirmation just to read a
failure. Old323 diagnostics have inactive gen2 continuity and mismatched config;
that is not a missing-UI permission. No grants/diagnostics/model calls were made
for this audit. Deterministic S04 delivery proceeds independently.
