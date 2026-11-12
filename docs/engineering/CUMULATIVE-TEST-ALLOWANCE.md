# Cumulative test allowance integration

Status: implementation candidate; not activated in the running platform.

This implements the previously authorized test extension on the existing
experience ledger. It does not create a second spendable budget or modify
historical policy, reservations, settlements, UNKNOWN results, or grants.

## Selection and accounting

The operator prepares an immutable allowance using migration 0062 and explicitly
selects its identifier in the provider budget configuration. Understanding,
planning, and Native composition reuse the same budget owner. The root policy
and pricing remain unchanged. Reservation totals include all existing calls and
unsettled worst-case costs, serialized on the original ledger lock. Conversation
caps can narrow but cannot increase the selected allowance.

The allowance binds the original policy digest, namespace, domain, ledger and
human authorization digest. Its fixed time window is at most 30 days, with
cumulative maxima of 100 calls and USD 10. Reserve and dispatch both validate
expiry; reloading configuration does not create a new window.

## Conversation continuity

Experience policy v1 retains its previous shape, digest and 24-hour limit.
Explicit v2 requires a selected allowance. New admission records retain the
allowance identifier, authorization digest and fixed ledger expiry. Planning
must retain the source allowance, authorization and budget limits, while its
model profile can differ from understanding. Existing account, source, grant,
revocation, context expiry and unresolved-outcome checks remain in force.

Existing context usage reads retain cumulative settled and reserved costs;
configuration caps are upper limits, never remaining balances. No allowance is
selected implicitly from the newest database row.

## Validation and rollout

Isolated PostgreSQL tests cover concurrent exhaustion, UNKNOWN reservation
retention, cumulative fee limits, immutable records, scope and selector mismatch,
expired reserve/dispatch/admission, fixed expiry across configuration reloads,
source-to-planning substitution rejection and legacy conversation behavior.
These tests do not demonstrate a real provider call or Native execution.

Activation remains separate: verify the authorized operator document, current
ledger totals, no in-flight work and protected table snapshots; prepare the
additive record and consistent configuration; then verify health and original
conversation behavior. Do not replay historical UNKNOWN work. OpenClaw remains
disabled. Actual UI/demo acceptance and Native continuation remain outstanding.
