# Native original-subject execution integration (G1)

Status: implementation plan, not deployed acceptance.

The authorized F3 ordinary-account path currently reaches a Native runtime that
only admits the development administrator. This prevents the requested ordinary
original-conversation execution even when exact run and resource grants exist.

Add an explicit operator configuration authorizationMode=EXACT_ORIGINAL_SUBJECT
with one subject. Legacy configuration remains administrator-only. Reject a
command for a different subject before reading its work and on every decision.
Reuse the existing authorization bundle for the original prepared command and
exact Skill/ontology grants; ordinary subjects do not acquire administrator roles.
Administrator execution retains its administrator grant check. Configured subject
selection never issues grants or bypasses owner checks, revocations or expiry.

Reuse the existing provider budget owner and explicit allowance selector on the
original ledger. Its immutable root limits remain unchanged; effective cumulative
limits are enforced by reserve and dispatch. Do not remove the legacy root cap
check or create another ledger. No public CRD, lifecycle, persistent infrastructure
or authentication mechanism changes.

Affected source: native_loop_runtime, prepared_native_composition, one small policy
validator and targeted tests. Validation covers legacy behavior, opt-in, malformed
policy, cross-subject denial, ordinary exact grants, ontology grant retention and
revocation. Full repository checks precede install. Actual ordinary-account
model/clarification/results acceptance remains required after deployment.
