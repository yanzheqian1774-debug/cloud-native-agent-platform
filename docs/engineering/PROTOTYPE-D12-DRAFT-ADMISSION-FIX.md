# D12 development administrator draft admission completion

Scope: user authorized the local development administrator and now requests an
unseen-scenario full-path test. First live request was rejected before provider
traffic because the older context-admission path only allowed demo324.

Implementation: recognize the existing D12 role through current server-side
session/account/generation checks; retain actual caller identity in new context
requests; record a distinct D12 policy decision for that caller's understanding
context; use current role decisions instead of creating resource approval requests.
Normal users and the independent approval endpoint are unchanged. Existing
contexts, budget caps, reservations, unknown outcomes, and model configuration
are preserved. No new model provider, public contract, schema, or execution kind.

Validation: isolated real-account context admission, denial after role disable,
revocation, idempotent policy decisions, zero resource-approval requests, unchanged
budget policy, existing ordinary-user context regression; live same-conversation
continuation only after confirming original request made no provider reservation.
Planning and unseen executor completeness are separate acceptance gates.
