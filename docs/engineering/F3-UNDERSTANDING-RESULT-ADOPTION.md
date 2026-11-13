# Initial understanding: single-call result adoption (G1 plan)

Status: design for an isolated successor to C1, not enabled or registered.
C1 commit 6d60258 and its exact model/policy candidate remain unchanged.

## Owner contract

A routing call always owns a separate real draft invocation, provider receipt and
budget reservation. It does not claim a turn in the pending original context.
One immutable successor model policy returns both relation and, only for a clear
answer to an UNDERSTANDING question, the complete existing understanding result
(DRAFT_READY / NEEDS_DATA / NEEDS_CLARIFICATION). There is no second model call.
Independent or ambiguous answers never adopt, create work, or advance the original
context. A new task is not a reply to the pending question.

Adoption is an internal Draft Assistance owner operation. Input is references,
not caller supplied draft text: exact conversation/message, actual successful
routing invocation, original context/invocation/turn/version, original inputSource,
current owner-question token, and an idempotency key. The authoritative source
fields come from saved owner records; client values are expectations only.

Within one transaction the operation locks the original context and exact
invocation, verifies its unchanged head, pending question and aggregate version,
checks the successful new invocation and retained response, and inserts an
append-only adoption reference. Original subject/tenant/conversation, selected
source revision/digest, input commitment, provider result/profile, current policy,
expiry and settled/no-UNKNOWN status must all agree. The model result itself is
never copied into a synthetic invocation, and its provider/budget receipt remains
on the real invocation. No adoption mints a model call or settles an old UNKNOWN.

A unique original-invocation adoption prevents two different results from consuming
the same question. Exact replay reads the existing reference. Conflicting source,
subject, target, result, version or key is rejected. An old ordinary begin must
also lock the same context and reject a parent consumed by adoption, closing the
race with a second tab. This changes only the internal PostgreSQL owner adapter;
old contexts with no adoption keep existing behavior.

The original physical context/turn rows remain historical. The effective next
question is the adopted REAL invocation, linked by the adoption reference. Its
actual context and turn identities are used for subsequent replies. This is an
explicit reference lineage, not a fake relocated invocation or arbitrary latest
lookup. The UI journal is a projection, never the authority for adoption; a failed
journal update can GET the exact adoption and restore the projection without
replaying a model or adopting a different result.

## Business and planning boundary

A general question-only context remains insufficient for business operations.
Only a validated adoption edge can connect its actual DRAFT_READY invocation to
an original business-authorized understanding context. A central resolver must
recheck BOTH contexts, exact saved source, current original policy/account/grants,
shared allowance and expiry, plus the adoption commitment. It must not remove the
existing blanket rejection for general contexts without this proof.

Business creation binds the exact adopted real invocation in its actual context.
Planning reads that same exact bound invocation and source. The original root
business scope is an explicit validated ancestry reference; neither the context's
first result nor arbitrary latest result may substitute. Subsequent grants remain
existing exact owner requests and audits; source/Skill/rule/execute permissions are
not implied by adoption. Source replacement requires its existing separate process.

## Compatibility and components

- New internal append-only PostgreSQL table, proposed migration 0065 (0064 is
  reserved for Native recovery); no new database/infrastructure.
- Additive private adoption POST + exact readback GET, default unavailable unless
  the new successor profile/admission policy is explicitly installed.
- Internal draft adapter lock/consumption check; additive result/reference resolver;
  minimal integrations in context binding, work authorization and planning reads.
- New immutable model/profile/policy revision for the complete structured result;
  C1 and r5 schema bytes, digests and retained read routing remain unchanged.
- Same fixed input; current-question callback adopts the saved real result once,
  not Journey.answer with another model dispatch.
- No public CRD, Kubernetes group, frozen public Contract, Task/Workflow/Runtime
  lifecycle or cross-plane ownership change is proposed. If implementation needs
  one, stop and enumerate the specific difference before proceeding.

## Validation strategy

Pure owner contract checks: one valid adoption, unrelated/ambiguous/no-question
rejection, wrong source/subject/conversation/profile/receipt, nonterminal/UNKNOWN,
changed original turn/version, malformed result, duplicate and conflicting replay.

Isolated PostgreSQL with real sessions and owner grants: model fixture emits one
actual successful result; adoption and refresh leave invocation/reservation counts
unchanged; two concurrent consumers allow one reference; ordinary begin versus
adoption shares the context lock and cannot both consume the same parent; rollback
leaves no adoption. Business creation, bound-source planning read and another
clarification must follow the exact adopted result without rewriting history.

Controlled browser: same composer; unrelated answer leaves old question/journal
unchanged; clear reply has one understanding dispatch; lost adoption receipt uses
GET, not automatic POST; stale target leaves draft editable and does not retarget.
Real model semantic and full business-chain acceptance remains coordinator-owned.

## Implemented successor composition (default off)

The additive migration uses its own `draft_assistance.adoption_schema_migrations`
checksum record. It does not add version 65 to the old draft owner's closed
migration registry. The original owner migration remains valid after installation.
The new `UNDERSTANDING_ADOPTION_RUNTIME_FILE` and
`F3_UNDERSTANDING_ADOPTION_POLICY` compose the successor only when explicitly set.
The original C1 runtime/policy remain required for exact C1 retained reads; GET
selects the recorded profile and digest and never falls back to the current one.

The private adoption POST and GET are installed but unavailable without this owner.
POST locks the conversation row in the journal's existing order, then the original
draft context; current grants/policy, source, retained message facts and settlement
reads precede the unique reference append. GET never dispatches, repairs or writes.
A stale tab cannot start a new understanding call for an already consumed question.
Ordinary parent claims share the same original-context lock. No source or model
text is copied into an invented invocation. Later clarification uses the real
adopted result and retains the original goal through exact reference ancestry.

The fixed input routes initial replies to the adoption owner and applies its saved
full result to the original journal; it does not call the understanding model again.
Refresh after an uncertain adoption only GETs the exact reference and journal.
If the journal has not advanced, explicit continuation applies the existing result.
A missing reference can be created only by an explicit, current exact-target POST.

Source supplements require the original source to be absent, an existing NEEDS_DATA
question (or the existing CLARIFY source-selection step for source-less DRAFT_READY),
and the exact currently authorized selected source. The model receives provenance
metadata, not the whole document. Replacing an already bound source is rejected.
Current source loss/permission failure blocks adoption; no automatic re-dispatch.

Business continuation resolves the original approved business context and actual
adopted result. General conversation understanding alone remains insufficient to
create or execute a business task. Existing business grants, planning admission,
source coverage and execution permissions are still separate requirements.

## Validation and remaining acceptance

A combined run passed 114 checks, including real session/BFF/grant/retained-result
reads, isolated PostgreSQL single-winner/CAS/rollback/migration tests, authorized
source-version reads and actual business create/bind/planning-source owner reads.
Model outcomes and budget settlement observations in these composition tests are
controlled; actual provider calls and real budget settlement acceptance remain
coordinator-owned. The later source-less DRAFT_READY edge plus pure reference
checks passed 33 checks. Browser tests passed 22 checks (6 new initial-adoption
cases and 16 existing C1/Native/planning cases); the added ready-draft source case
and final complete checks are recorded in the external C2 validation evidence.

The exact new candidate has also reached the real adapter.prepare with network
calls prohibited and without reading any credential: zero dispatch and zero
credential resolution. C1/r5 policy digests remain explicitly pinned by tests.
No public CRD, frozen runtime contract, previous model candidate, real database or
running platform has been modified by this work.

Remaining release gates: completed normal full hooks and independent integration
review; the new immutable candidate's specific human review and formal governance
publication/pricing binding; actual model semantic tests and installed F3 page
acceptance. C1 review cannot authorize this schema/policy. The broader product gap
of business execution in ordinary conversations not authorized by the original
business policy remains explicit; this package does not silently expand that scope.

## Same-request continuation before dispatch

An exact retained-result GET returning CONVERSATION_REQUEST_NOT_DISPATCHED may
expose an explicit same-question continuation. Clicking rechecks the exact GET;
only that reason permits the original message/content/idempotency key to begin.
No new message or key is created. A recovered result is read, not redispatched;
permission errors, unavailable reads and unknown results do not permit retry.
Refresh itself remains read-only. This also supplies business-facing failure
text in the fixed composer instead of exposing internal error codes.
