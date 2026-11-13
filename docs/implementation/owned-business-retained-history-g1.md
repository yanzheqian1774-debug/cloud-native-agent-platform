# Owned business policy window successor and retained history

The immutable allowance remains 100 calls / USD 10 until 2026-12-12T23:30:12Z.
The separately configured document policy expired earlier. Align a new policy
with the already authorized allowance without modifying the old file, admission,
ledger or old execution outcome.

Add an optional bounded list of retained policy paths to the existing reader.
Default is empty. Retained policies must have the same exact subject, account,
source/resource scopes, root/adoption bindings, ledger and allowance as current;
only policy version, expiry and enabled state may differ. Retained expiry may
not exceed current. Duplicate digests and invalid/private paths fail startup.

Only `work(..., history=True)` may select a retained reader by the policy digest
of the formally bound original admission. The selected existing reader repeats
all original checks, current identity, source integrity and revocation checks.
Execution, planning budget admission and ordinary `work()` remain current-only.
No fallback on authorization failure, no new grant, no old UNKNOWN replay.
The current policy file itself must remain unchanged and enabled before selection.

Tests: bounded/perimeter validation; actual isolated owner old admission history
with exact successor, ordinary execution rejection, revocation still rejected,
no additional model calls. Bootstrap uses explicit JSON list environment setting;
no new schema, CRD, external dependency, lifecycle or execution owner.
