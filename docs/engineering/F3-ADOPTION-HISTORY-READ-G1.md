# C2 adopted work: historical READ renewal compatibility (G1)

Status: isolated implementation; not deployed, no actual model or production DB use.

## Problem and boundary

The original work-history guard expects the primary understanding configuration.
A C2 business problem is correctly bound to its actual adopted result, whose
configuration is C2. Historical READ renewal must validate that reference back to
the original authorized business context rather than pretending it is primary.
C1 policy, model schema, allowance, execution eligibility and old facts stay unchanged.

## Implementation

Add a dedicated historical resolver, enabled only by the existing explicit C2
AdoptionOrigin. Reuse the canonical immutable adoption chain validator, exact saved
result/version/source and original subject/scope/conversation. Require the oldest
context to be the original named business context, never general owned chat.
Validate every intermediate C2 context against the configured profile/account/
allowance and reject explicit context revocation. Expired call leases are permitted
only for historical reading; execution's business_source remains unchanged.

For lineage inspection require an existing exact READ grant for each original and
result invocation, reject explicit denial/revocation/storage failure, then preserve
the normal work-target renewal checks. This is renewal eligibility, not a grant or
permission to execute. Lock context admissions in deterministic order, revalidate
under those locks, and leave the existing grant decision/audit owner in charge.
No new migration, no new model call, no READ inferred from USE.

## Verification

Use isolated PostgreSQL and actual adoption owner, actual business create/bind,
real sessions and existing policy grant owners with controlled model outputs.
Cover primary and adopted work, exact source/version, general-context rejection,
cross subject/tenant and explicit revocation. Snapshot work, model invocation,
adoption and budget records around history access. Legacy C1 without 0065 remains
supported. Record executed results separately; this plan is not acceptance evidence.

## Implementation and evidence (2026-11-13)

Two production files: a dedicated `understanding_adoption_history.source` resolver
and a bounded branch in `conversation_work_history.targets`. The execution resolver
`AdoptionOrigin.business_source`, published C1 settings and all model schemas are
unchanged. No migration or runtime configuration is added. Disabled/old profiles
fail before any database access; ordinary C1 stays on its existing path.

The new history resolver performs current policy/account/allowance checks, canonical
actual adoption-chain checks, exact prior READ eligibility and revocation/denial
checks, then locks all ancestry context admissions in sorted order and repeats the
chain checks. Every root/intermediate context must match the same subject, scope,
conversation, configuration, account and allowance. The root must be the named
original business context. The bound result remains the actual C2 result. Chain
errors at the history BFF are translated to the existing safe source-mismatch error.
No legacy result, context, source or model record is copied or updated.

Evidence lives in `work/evidence/f3-understanding-parallel-20261113/` outside this
checkout. `C2_ADOPTION_HISTORY_R5.txt`: 18 isolated PG tests passed in 143.46s,
including actual adoption/create/bind/history access, source/version mismatch,
wrong subject/tenant/conversation, explicit original/result context revocation,
exact READ revocation/no prior READ, general-root rejection and existing C1 history.
These use real owner transactions and sessions with controlled provider outcomes;
links/journal are saved test fixtures, not a browser-driven business acceptance.
Original invocation/budget/business/execution tables and adoption records remain
unchanged around renewal. The original business create fixture was extracted without
changing its existing assertions so the test exercises the same owner path.

`C2_ADOPTION_HISTORY_OFF_R1.txt`: 4 pure default-off/old-profile cases passed.
Earlier R1/R2 fixture errors attempted to alter immutable call decisions and were
correctly rejected; no trigger was disabled. R4 exposed a version-fixture mismatch
(SQL row version changed but JSON version did not); the negative fixture now appends
a consistent owner-format version. These failed runs are retained, not counted as
passing evidence. Expired call leases are allowed by code review; only expired READ
renewal is exercised in the final PG checks, not a time-travelled call lease.

Remaining acceptance: root integration checks, independent review, separately
approved C2 configuration/activation and actual model/browser acceptance. This patch
does not make C2 active and does not inherit C1's specific model approval.

Final additive check `C2_ADOPTION_HISTORY_R6.txt`: 7 passed, 5 deselected,
104.77s. This reruns both current/expired ancestry READ positive cases and changed
source/version/no-prior/original-context-revoked/result-context-revoked cases with
actual history HTTP rejection assertions. Ruff, format and diff checks pass. The
sets overlap R5 and are not summed as unique tests. No child full hook was launched;
root owns the scheduled integration check.
