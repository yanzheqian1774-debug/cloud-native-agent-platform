# F3 conversation experience admission

Status: opt-in candidate, not enabled by this implementation. This is a bounded
adapter for the approved synthetic document review and sales experience, not a
general permission or tenant architecture change.

## Entry and identity

`F3_CONVERSATION_EXPERIENCE_POLICY` points to an absolute operator-owned JSON file
with no group/other permissions. It is consumed only when existing context-call
admission is enabled. `ExperiencePolicy` defines its closed schema. The operator
binds the existing reviewer324 account, its exact scope, at most two specific
conversation IDs and their approved synthetic scenario, the authorization
evidence digest, and the exact configured understanding profile limits.

The conversation API verifies ownership, original user message and content
before carrying the binding into the synchronous owner call. The model and
browser cannot grant authority by supplying prose or a scenario name. A direct
owner call without this binding is rejected for the configured experience user.
Existing routes and all other account paths remain unchanged when the option is
absent.

## Existing owners and bounded authority

The adapter writes existing context requests/decisions and audit records. It
uses the existing request/model grant request owners, validates every exact
member, and records normal POLICY decisions and grants. It does not issue a
development-administrator role, grant-management authority, arbitrary resource
permissions or execution authority. Decided/revoked requests are not renewed.
Current account revision, authenticated session, policy generation, recovery
epoch and the unchanged operator policy are checked before admission.

## One allowance and fixed time

The ledger is fixed at `ledger:f3-main-experience:20261112`, 20 total model calls
and 1,000,000 microUSD. This adapter neither creates nor edits budgets,
reservations or settlements. Existing budget reservation/settlement enforcement
remains authoritative. The 24-hour ceiling starts at the immutable budget policy
creation time; rereading or upgrading a configuration cannot restart it or create
a second allowance. Individual context decisions and exact grants retain the
existing maximum eight-hour lease, further bounded by the remaining budget
window. Expired or revoked context decisions are not automatically renewed.

The ledger must be created only as part of the separately verified activation
procedure. Before activation, recheck original activation time, every settlement
and unresolved reservation. Later planning/Native integration must use this same
ledger through existing pinned profile-pricing support; this adapter alone does
not enable either path or external writes.

## Validation and remaining release gate

The real isolated PostgreSQL checks exercise ordinary-account admission, exact
request/model grant issuance, replay without new decisions, wrong conversation,
revocation, account disablement, policy changes, expiry and rejection of a second
ledger or increased caps. They do not invoke a paid provider. Existing context
admission and understanding behavior are regression checked separately.

Still required: verified runtime/profile and pricing preparation, disabled-policy
release review, guarded activation, ordinary-account real-model answer in the
original conversation, refresh and followup, visible progress, paid-call counts,
limit evidence, and F3 visual acceptance. Tests are not a substitute for that
product path.
