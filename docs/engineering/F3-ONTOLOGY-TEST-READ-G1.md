# Existing ontology test-resource read coverage

The ordinary account receives AUTHORIZATION_NOT_FOUND from the ontology directory.
The existing test-resource read policy supports other published resources but
cannot describe BUSINESS_ONTOLOGY collection or exact revision reads.

Extend only the existing policy's READ/LIST inventory and exact digest lookup,
using business_ontology.revisions and its existing namespace/security-domain
boundary. No new grant action, endpoint, lifecycle, migration or execution
permission is introduced. Loading this code does not activate or issue grants.
The existing authorizer still checks target identity, current revocations,
denials, generation, issuer, expiry and auditable requests.

Validation covers the exact collection, required revision digest, mismatched
digest, missing revision and rejection of USE/CREATE/REVISE/TEST/PUBLISH. Run
existing policy regression and normal repository commit checks. Real activation
must separately bind actual revision digests within the existing authorized test
scope and then verify ordinary-account reads. This does not solve the observed
60-second preparation wait or authorize maintenance operations.

## Controlled latest publication selection (G1 follow-up)

Approved implementation boundary: extend the existing bounded test READ policy,
not ontology USE, maintenance, model access or an enterprise-wide permission model.
No new table, deployment activation, credential or graph UI is included.

`publishedOntologyIds` is an optional exact logical-identity list (up to 64,
default empty) inside the existing tenant/domain/subject/issuer/expiry policy.
The empty default preserves the previous canonical policy digest and static keys.
A collection LIST target remains explicitly configured in `targets`; it is not
inferred from this list. Current requestability must allow BUSINESS_ONTOLOGY READ
with purpose `F3_ONTOLOGY_TEST_READ` and the ordinary grant issuer must still be valid.

For each identity the existing owner transaction locks its definition FOR SHARE,
selects the latest successful PUBLISH fact by ordinal and validates the exact
revision through the owner repository's content digest verification. A newer draft
head cannot replace this selection. If the latest release is deprecated, no older
release is silently promoted; existing history grants remain unchanged. An explicit
READ rejection or revocation for this subject and any revision of the exact same
ontology blocks automatic successor READ derivation. Existing static-only policy
semantics and other subjects are unaffected. No refusal is automatically removed.

GET `/test-resource-access/status` adds `selectionDigest` only when this feature is
configured. It writes no grant. POST `/prepare` then requires both
`expectedSelectionDigest` and an idempotency key of the form
`published:<selectionDigest>:<bounded nonce>`. Server-side strict validation binds
the digest in the original key itself, not merely in a replaceable request field.
A changed current selection returns 409 before grant writes; changing the digest
while retaining the old key returns 422. Same-selection replay reuses existing
immutable grant receipts and cannot extend expiry. Grant decisions retain the
existing precise target, policy, issuer, subject, lifetime and audit mechanisms.

The existing resource-preparation component keeps stable per-selection keys and
an unresolved-selection pointer before POST. A network-unknown request is never
silently retargeted after a new publication or refresh. The existing status area
says the material version changed, preserves the old pending record, and permits
an explicit "读取新版资料" action to start a new READ preparation. This starts no
business execution or model invocation. Known successful requests permit the next
published selection to be prepared normally. Performance caching is a separate
work package; this change does not claim to solve repeated preparation latency.

Validation includes real isolated PostgreSQL owner publication, newer draft,
new publication, deprecation, exact historical grants, refusal/revocation lineage,
expiry, current issuer revocation, aggregate-lock exclusion, corrupt storage and
HTTP session/CSRF/key binding. Controlled browser tests cover static compatibility,
unchanged-key recovery, changed-selection UNKNOWN preservation and explicit new READ.
Actual ordinary-account activation/read/use acceptance remains a separate deployment
step owned by the integration coordinator.
