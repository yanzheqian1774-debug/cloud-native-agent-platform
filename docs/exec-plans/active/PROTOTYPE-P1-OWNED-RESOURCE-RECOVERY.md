# Existing owned-resource deep-link recovery (G1)

2026-11-06. Sole writer; installed source21aa10de2cc8. Provider research remains
41calls/16unsettled/USD12.598116 including reservations. New sales research
4a9034ad is OUTCOME_UNKNOWN, no Plan/Run; no further same-condition sampling.

## Actual defect and boundary

The original published supplier v2 Skill deep link uses managedResource
9e4366e8-5572-4994-a35e-2b35692cd4bd. The actual management directory returns200
with items=[], so the page cannot restore its detail. Directory intentionally
filters current MANAGE_RESOURCE authority even for original create/import actors.
The existing command owner has an access action: exact original creator ownership
is checked, then the current RESOURCE_MANAGEMENT policy decides exact management
and revision READ authority. The UI currently exposes no way to request that
existing action after an inaccessible deep link. An empty directory does not prove
deletion, nonexistence, expiry, or policy permission; no inferred cause is shown.

## Proposed bounded implementation

- Distinguish initial loading, unavailable service, and a loaded directory unable
  to restore the requested original resource. Retain the deep link and do not show
  another resource's detail as its result.
- An explicit button may ask the existing access owner to reevaluate the exact
  requested identity. This is an authorization request, not a read-only GET or
  merely metadata renewal: it can grant MANAGE_RESOURCE plus revision READ under
  the existing policy. Describe that effect truthfully. Do not auto-POST on GET,
  login, focus, refresh or tab selection.
- Retain normal exact ownership, scope, active-policy, independent actor and
  requestability checks. Unknown identities/other creators and denied policy stay
  denied. No backend owner/contract/lifecycle/model/execution change.
- Reuse existing commandKey persistence and GET-only command recovery. A missing
  access response must not emit a second POST. Failed existing access remains an
  explicit error; no manual signatures or broader grants are introduced.
- Existing access currently requires a known aggregateVersion despite changing
  no resource and declaring expectedVersion optional in its schema. An inaccessible
  deep link cannot obtain that value from the filtered directory. Only access may
  omit expectedVersion: after the same creator/policy checks the owner loads
  current revisions and grants their exact READ references. A provided version
  still must match; every content/lifecycle action keeps its existing requirement.
  No automatic version guessing or stale-version retry is added. This is additive
  behavior in the existing action, with no new authority or broader work scope.
- Successful original-owner access restores the original exact resource and
  keeps the tab. It does not change content, revision, tests, publication, employee
  membership, Plan/Run or the provider ledger.

## Verification

Use bounded browser fixtures to verify initial loading, absent deep-link target,
no automatic writes, exact explicit access, denial, other-owner failure and lost
response original-key recovery. Existing resource management regressions remain.
Actual original-resource recovery must separately record its policy/authorization
writes; subsequent Skill tab/refresh screenshots are read-only and do not pretend
the recovery itself was GET-only. Verify source version, unchanged exact resource
content/revision/test records and provider41/16/USD12.598116 before/after. Compare
needed Skill pages at the same viewport with original S-page targets; visual
differences and missing states remain OPEN. Mandatory lint/build/hooks and immutable
installation are required before current product evidence.

This plan is bounded G1 work in the approved resource continuation. It does not
close S01-S14, J11, the92-row matrix, dual-case business acceptance, or six packages.

## Candidate verification and review

Actual management9 backend tests passed on64335, including both dynamic management
and revision READ revocation: access cannot silently regrant either. The existing
23 automatic-policy tests also passed.28 resource browser checks passed, including
six mismatched receipt fields, changed identity, final directory-refresh identity
race, unmount before POST, loading and original-key response recovery. Independent
read-only review found the latter two races; final publication now follows the
whole pinned-principal directory check and active-view assertions. No runtime
access was requested yet and the installed source remains21aa until fixed checks.

Final review also required direct principal-mismatch detection to withdraw the old
owned directory even without a focus event. This is now distinct from a changed
path, and original pending keys are retained. The initial full-check attempt was
interrupted to make this correction; it is preserved as an interrupted result,
not a passing gate. The new28 browser checks pass; mandatory full checks restart
from the corrected candidate.
