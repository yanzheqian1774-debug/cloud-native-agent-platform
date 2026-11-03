# Package 03 — current supplier-case verification and recovery boundary

Observed 2026-11-03. This supplements, rather than replaces, the Sep22 and Oct16
historical checkpoints. The original cost Plan is regression only.

## Authenticated current state

Existing demo324 account was reused through normal nonce/password login with
TLS verification. No credential was rotated and no new account/generation was
created. On the user's explicit approval, the existing distinct reviewer324
principal mechanically issued the decision for request
`grant-request-9c349356600e2cc64c8b87856b71c142`: nine exact READ permissions,
not PREPARE, INVOKE, START, RETRY, model budget or publication. The operator is
not represented as the user physically clicking. Existing owner checks remain.
Passwords and session cookies are retained only in private local files outside
Git and deliverables. The user subsequently pre-authorized routine development/
test accounts, model calls, needed quota additions and execution approvals;
this is standing task authority, not a fabricated persisted owner decision.

After approval the original Problem, Criteria, planning-input and BOTH request/
invocation GETs returned HTTP200 under the original business principal/scope.

| Fact | Current evidence |
| --- | --- |
| Problem | `5fe6a7c9-3f92-5a09-bd91-bf3380109087`, ACTIVE, aggregate3, original revision1 |
| Criteria | set `2c0493e0-ab56-550e-94e1-32140957bc93`, six original deterministic members |
| Resources | exact supplier Skill, synthetic Knowledge, duty Agent, Native profile remain PUBLISHED; Employee has original PUBLISH fact |
| Same-case proposal / Plan | zero in scoped current technical snapshot; neither formal invocation returns a proposal |
| 20th invocation | `f078a876-eef8-4cb5-ae69-83bf6cfccd42`, persisted OUTCOME_UNKNOWN / PROVIDER_OUTCOME_UNKNOWN |
| 21st invocation | `e630dcd1-f03b-4228-b01e-0d3393d576fb`, formal projection OUTCOME_UNKNOWN / NO_DURABLE_TERMINAL_RESULT_DO_NOT_REDISPATCH |
| Original planning ledger | 21 reservations, nine unsettled, charged-or-reserved USD6.644500; original policy call_cap8, cumulative revisions20/21, USD10 total cap |

A PUBLISHED profile is a declaration, not runtime health or execution authority.
The monetary total includes retained reservations and estimates, not a supplier
invoice or proof of 21 external sends. The former package notes which mentioned
only invocation20 and USD5.956372 were historical/incomplete, not current state.

## Recovery basis: distinguish the two records

Invocation20 has an immutable provider receipt: SEND_REQUEST/WAIT_HEADERS,
TIMEOUT at 30.734561s, local worker reaped, measurement empty. It has no
settlement and retains USD0.688128. There is no attributable supplier response/
usage in this receipt. Neither local timeout nor worker cleanup proves remote
failure or zero charge. Current evidence does not permit rewriting its terminal
result or releasing the reservation.

Invocation21 has an invocation claim and USD0.688128 reservation, but no durable
result and no provider receipt. The retained local stack/lock evidence points
before provider.suggest; it is engineering evidence, not a persisted owner
zero-dispatch/zero-charge adjudication. Formal GET correctly projects UNKNOWN.
Keep its claim, request key and reservation. Do not manufacture finish/settle.

GET recovery reads the existing record. For invocation20 the existing
planning_measurement.settle sees no settleable measurement and retains the
reservation; invocation21 has no receipt to settle. The before/after scoped
snapshot confirms both records, case state, reservations, policy, allowance
revisions and ledger aggregate unchanged after authenticated GETs.

## Engineering closure achieved here

A separate disposable PostgreSQL15 tmpfs container ran 20 authorization/queued-
writer/shared-lock/planning-successor tests successfully, including same-
transaction re-entry, revocation and immutable budget history. No fixture used
the business DB. The disposable container was stopped and removed afterward.
This closes the formerly environment-blocked engineering check; it does not
create a real provider recovery decision or prove invocation21 had zero cost.

Frontend adds explicit GET-only original-record recovery, distinct UNKNOWN
explanations, exact locator ownership and mismatched-problem write blocking.
Late recovery replies cannot redirect a newly selected record. New P04 primary
save-and-plan action composes criterion/set writes, exact fresh reads and DRAFT
activation if needed; an already ACTIVE problem is not activated again. Failed/
unknown/stale steps stop, original save remains durable, newer composer input
pauses continuation. Entering planning does not invoke a model or start a run.
Existing save-only and frozen-command recovery remain compatible.

## Remaining dependency and proposed next engineering slice

Current evidence does not supply a same-case Plan, valid supplier result/usage,
or an owner adjudication for either unresolved call. No new provider attempt was
made in this stage. Standing business permission does not itself add a persisted
22nd allowance to the fixed existing21 mechanism.

Recommended next design is additive: retain invocation20/21 and every existing
reservation/settlement, introduce a typed append-only recovery observation for
invocation21's local evidence and an independently attributable supplier
observation for invocation20 if available. Neither observation overwrites the
old terminal/claim. If a fresh bounded test is actually needed, bind a distinct
follow-up object to the original case, exact current target/configuration and
predecessor, at most one additional count (candidate cumulative22), still sum
all history/UNKNOWN against the original USD10 cap under the same budget lock.
Never change the original8/D6-20/D7-21 records, create a bypass ledger or reuse
the old request as a retry. Contract/compatibility/lock/idempotency and failure
rules must be specified and verified before installing or dispatching that
follow-up. This is a proposed implementation slice, not implemented allowance
or a claimed supplier recovery. Business/test operation approvals need not be
requested piecemeal again under the user's standing instruction.

Package03 is still ACTIVE: real same-case Plan→Native→artifacts→six-criterion
assessment→human business acceptance and whole-page visual acceptance remain
open. Mock UI and green engineering checks do not close those gates.
