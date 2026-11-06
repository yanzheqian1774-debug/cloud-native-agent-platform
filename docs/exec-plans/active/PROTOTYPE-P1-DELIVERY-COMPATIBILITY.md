# P1 supplier compatibility and original business journey (G1)

2026-11-06. Sole writer: `01a1af1b-f9dd-78a3-a12a-14b6f3cbfa18`,
after the previous writer stopped. Same repository and approved P1 scope.

Owner GET of c989/r1, after renewing only its exact READ using the existing
test-request/decision owners, confirms six logical EMPLOYEE requirements and
one exact KNOWLEDGE requirement. Operations are READ_DATA, VALIDATE_DATA,
CLASSIFY_OVERDUE, SUMMARIZE, ANALYZE_DATA and RENDER_REPORT. No old UNKNOWN is
replayed or promoted. Current empty candidate lists reflect unavailable reads,
not proof that the resource catalog is empty.

Implementation in this batch:

- Preserve delivery executor revision 1, its configuration digest, published
  resources and historical results. Add exact revision 2 with CLASSIFY_OVERDUE
  and explicit operation output kinds/dependency contracts, using the existing
  managed Skill registry, resource owner, Native worker and evaluator. Retain
  the existing v1 transport envelope; v2 adds required typed provenance.
- Validate full executor revision/configuration and operation before matching.
  v2 classification consumes validated output, never aliases ANALYZE_DATA or
  silently accepts a raw snapshot. Wrong revision/digest/kind/source fails closed.
  New resource content is a separate draft/revision, never an edit to v1.
- Accept only the canonical source boundary or the exact observed alternative
  prefix, with a unique complete identity/revision/SHA256 triplet and matching
  selected knowledge. Do not rewrite historical proposals or infer a source
  from prose. Source-changing successors remove either recognized source line
  before adding their new exact boundary; contradictory/duplicate lines reject.
- Let one exact published employee definition cover multiple logical role
  requirements when every task binds its declared operation to that definition's
  authorized exact members. Do not add multi-employee composition, external
  member binding, a new lifecycle, database, execution framework or approval
  owner. Conflicting selected definitions and absent member operations reject.
- Adapt actual resource tests to exercise a typed dependency chain for v2;
  tests remain resource verification, not a Run or business acceptance.

Validation: fixed-source boundary cases; v1 digest/behavior compatibility;
v2 six-operation graph and classification edge cases; wrong version, source,
dependency and missing capability negatives; disposable PostgreSQL owner flow on
64335; policy/actor/exact member evidence; current Native pipeline and evaluation
regression. Run required commit hooks. Install only a committed verified snapshot
after queue/ledger checks; preserve generation and precise grants except finite
same-scope lease renewal where needed. Provider model/timeouts/budget unchanged.

Product exit remains the original J03/J05/J04/J06 journey, including sales,
natural question, capability preparation, admission, fresh execution and cited
outcome/evaluation. This capability addition is not J07 pure configuration.
No J or complete page is accepted from engineering tests alone. All original
92 matrix rows and J01-J12 gates remain. Record actual exits and remaining gaps.
