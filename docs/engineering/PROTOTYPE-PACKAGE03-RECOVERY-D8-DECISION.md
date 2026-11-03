# Package03 D8 additive recovery and one bounded follow-up decision

Current status: ACCEPTED with user-revised cumulative100/USD50 ceilings;
implemented and installed in the local development candidate. The initial22/USD10
proposal below is historical and superseded by the Human decision section. Business dev/test calls and account/approval
operations are already authorized; this request concerns a persistent authority
extension, not another ordinary call approval. Original 323 remains closed.

## Requested decision

Authorize an additive extension within existing PostgreSQL and existing owners:

1. Append immutable, scoped recovery observations for original invocations20/21.
   Bind exact problem reference, invocation/context, evidence digest/provenance,
   observer identity and observation timestamp. Local diagnostic evidence is
   explicitly LOCAL_ONLY; absence of receipt is not proof of no dispatch or use.
   An observation never changes original status, reservation or settlement and
   does not itself grant a retry or execution.
2. Introduce a distinct, independently signed follow-up request tied to the exact
   original case, predecessor21, both unresolved observations, current criteria,
   resource/configuration digests, original ledger and a new idempotency key.
   Permit at most ONE fresh planning reservation: cumulative ceiling22. Original
   policy8, D6 ceiling20 and D7 ceiling21 remain immutable and unmodified. All
   history, including every unresolved reservation, counts under the same USD10
   budget lock. No alternative ledger, reservation release or automatic retry.
3. Reuse existing task authorization, account revision, independent issuer,
   revocation and configuration gates. A new append-only follow-up table and
   observation table may be introduced; no new database/infrastructure, CRD,
   runtime owner, Plan or execution lifecycle. The old D7 path and schemas retain
   their exact meaning; never widen their Literal21 or database CHECK21 in place.
   New writer version must explicitly recognize the additive schema; unsupported
   configuration fails closed. Actual calling requires installed/tested mechanism
   and ordinary formal signing, not this document or chat approval alone.

## Why an architecture decision is required

Current ConfigurationRevision fixes cumulative_call_cap to Literal21;
0040_task_planning_successor.sql fixes original8/previous20/current21 and one
successor per ledger. A second successor cannot be installed through the current
contract. Adding recovery adjudication and follow-up authority changes persisted
state/authority semantics. AGENTS.md and ARCHITECTURE_GATES.md classify this as G2.
The user's standing operational approval does not silently redefine those contracts.

## Affected components and compatibility

Planning admission, bounded task authorization, recovery projection, budget
reservation guard, migration/version readiness and Workbench operation display.
Existing authorization and budget owners keep their responsibilities. Existing
clients, grants, calls, results and historical observations are unchanged. GET
recovery remains read-only. No old request becomes dispatchable. Rollback stops
the new writer/entry and retains additive facts; no deletion or downgraded schema.

## Required validation before installation or calling

Test scope and exact-reference mismatch, evidence provenance, immutable history,
independent signature, account/configuration drift, expired/revoked authority,
wrong ledger, duplicate/different-key races, shared transaction budget locking,
USD10 including UNKNOWN, at-most-one new reservation, interrupted command and
read recovery, missing provider terminal, old D7 compatibility and no GET effects.
Use a disposable database for fixtures, never the business database. If a fresh
call becomes UNKNOWN, retain it and STOP further dispatch; no automatic23.

## Alternatives

A. Approve this additive mechanism and at-most-one follow-up together: preserves
history and permits the original case to progress after installation and checks.
B. Approve observations only: improves traceability but leaves real planning
blocked at21 until independently verifiable supplier recovery is available.
C. Keep current architecture: continue resources/Native isolated verification and
visual work, retaining original-case acceptance as blocked. A substitute case
cannot close the original supplier case.

Recommendation: A. No external result or usage has been fabricated; this proposal
is not a supplier recovery conclusion or a business acceptance decision.

## Human decision 2026-11-03 accepted with revised development ceilings

The user explicitly directed: “研发与验证阶段，次数可以上调到100次，以保证开发和测试推进的进度”, then “原USD10金额上限，改成USD 50”. D8 additive mechanism is accepted with those limits replacing the proposed22/USD10 ceiling for new development follow-ups. Historical policy8/USD10 and D6-20/D7-21 remain intact. The original ledger continues to count all settlements and unresolved reservations. Each independently signed follow-up request binds one fresh exact invocation; no automatic retry, queue of100, reservation release, supplier adjudication or23-specific approval requirement. The total ceiling is100, not100 new calls. Standing dev/test operational approval applies to formal signatures; final business acceptance remains separate.

Implementation plan: retain old ConfigurationRevision and its serialization;
add an optional development revision excluded from old serialized requests.
Migration0041 adds immutable recovery observations and distinct follow-up links.
Existing task signature, root/account/configuration checks are reused. Each new
signed task binds one exact follower of an observed D7/D8 invocation on the same
ledger. Old request/idempotency keys never dispatch again. Only the new exact
follower can select the100/USD50 effective limits inside the existing budget
transaction. Missing state, mismatch, revocation or expiry fails closed. No
provider/model/price/timeout change and no new infrastructure dependency.

## Installed development checkpoint

Migration0041, immutable local observations, per-task exact follow-up links and
atomic effective limits are implemented. Two original UNKNOWN records remain
unchanged. Each new task/context is formally signed through the existing distinct
test reviewer under user standing authorization. Fresh supplier calls return and
retain invalid candidates rather than promoting them to Plan. No automatic
retry is introduced; engineering checks and actual business results are separate.
The local candidate is not merged or released. Resource review also rejects
identity/digest/version mismatch, withdraws failed reads and halts remaining
publication after new business input. Whole-page visual acceptance remains open.
