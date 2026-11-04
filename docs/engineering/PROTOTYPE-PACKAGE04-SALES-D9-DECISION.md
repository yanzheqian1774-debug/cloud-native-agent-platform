# D9 — Independent sales-case authority under existing owners

Status: ACCEPTED by explicit user decision on 2026-11-04: “批准D9方案，继续研发验证”. Implementation and installation checks remain required; this decision alone does not dispatch a call.

Requested decision: permit an additive, explicitly configured new development case
(synthetic two-period sales diagnosis) under the existing tenant/security domain,
with its own exact problem, criteria, source/Skill/employee/runtime revisions and
independent request/signature. Preserve supplier D8 as supplier-only. No sales
request may borrow its predecessor, UNKNOWN recovery evidence or a supplier grant.

Why: bounded_task_policy.require_scope and the existing purpose/root binding and
D8 successor schemas admit specific historical case/root pairs, not an arbitrary
new case. Making initial authorization reusable changes persisted authority
semantics. AGENTS.md and ARCHITECTURE_GATES.md classify frozen authorization/state
contract changes as G2. User standing approval covers dev/test operations; this
proposal specifies the mechanism to which that authority would apply.

Concrete recommended mechanism:

1. Add a separate versioned initial-case authorization record, immutable and
   exact-reference bound, using the existing authorization owner and independent
   test reviewer. Explicit operator configuration lists allowed case/purpose/root
   triples; no wildcard, arbitrary root supplied by browser, or implicit inheritance.
   Existing D7/D8 root files and signed/serialized records retain their meaning.
2. Use the existing budget owner and original development ledger. The total
  100-call/USD50 ceiling includes supplier history and all UNKNOWN reservations;
   it is not a new per-sales budget. One signed request admits one fresh invocation.
   Concurrent supplier/sales admission shares the same transaction budget lock.
   GET/read/reload cannot authorize, reserve or dispatch. Unknown outcomes remain
   reserved and require evidence-based recovery; no blind retry.
3. Register the sales CSV snapshot/readonly executor and evaluator through existing
   resource, Native dispatch and result owners. Data/manifest hashes and criterion
   applicability bind to this new case. Synthetic diagnosis remains UNDETERMINED;
   no automatic real-business acceptance, CRM update, supplier replay, new database,
   CRD, tenant model, provider bypass or second runtime framework.

Affected components: bounded authorization and bootstrap version selection, exact
initial-case admission, shared budget validation, resource composition allowlist,
Native sales executor registration and exact result evaluation registration.
Compatibility: old paths/records reject or behave identically; migration additive
in current PostgreSQL. Rollback stops new writer/admission, retaining facts.

Required checks before installation: wrong root/case/purpose/criteria/source,
applicant/issuer separation, signature/account/configuration drift, expiration and
revocation, duplicate/racing requests, shared aggregate budget including UNKNOWN,
read-only GET, old D7/D8 compatibility, exact resource/evaluator versions, stopped
writer and backup, then authenticated sales planning→Native artifacts→evaluation.
Existing supplier is regressed by readback, not repeated execution.

Alternative without D9: continue CSV/Skill/evaluator tests and visual closeout,
keep sales authenticated end-to-end gate open. Do not label offline checks as a
second real run. Recommendation: approve the additive exact-case mechanism above.

Implementation detail: the existing create owner first checks its ordinary CREATE
grant and persists its normal creator receipt. An opt-in v2 operator configuration
pins the fresh deterministic root ID, current creator/scope, exact title and
description/source commitments before creation; that one new root and its exact
sales criterion applicability use an independent creation binding. They cannot
inherit or reopen expired ARCH-323 continuity. Any unconfigured case follows the
unchanged legacy binding. This configuration issues no grant and does not admit
planning, budget reservation or execution. After creation, exact root/criteria
references are separately signed through the D9 request and context gates.
