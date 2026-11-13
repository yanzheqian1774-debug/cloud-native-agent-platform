# F3 ordinary conversation planning recovery

G1 bounded adapter of the accepted D8 independently signed follow-up mechanism.
The original UNKNOWN, provider receipt and budget reservation remain immutable.
No old invocation becomes dispatchable. Existing F3 allowance and expiry apply;
the old D8 USD50 selector is never used. No lifecycle or frozen contract changes.

Implement an immutable local observation/request and one exact fresh invocation
binding in existing authorization PostgreSQL. Prepare through the existing
Planning owner, stop before claim/reservation until an independent administrator
signs the exact context through the existing context-decision owner. Reuse current
account, source, target, model, grant, generation, revocation and budget guards.
The new invocation is FIRST_PROPOSAL; recovery lineage belongs to the new binding,
not the existing clarification predecessor field. No automatic follow-up queue.

Ordinary same-target planning with unresolved history must require this binding,
including requests that merely change the idempotency key. Subsequent authorized
clarifications retain the recovery lineage. This bounded first adapter refuses a target with multiple unresolved invocations;
a second UNKNOWN requires follow-up operator review. GET and refresh never dispatch.

Routes provide prepare/read/continue and preserve the original conversation.
The UI reads the old request, requests a bounded recovery without technical IDs,
shows pending authorization, and explicitly continues the signed request once.
The backend is authoritative; the journey stores display/recovery locators only.
The original successful result flow is reused after a fresh result.

Validation: isolated PostgreSQL owner tests for immutable history, exact source
and target, local-only evidence, account/configuration/expiry/revocation, independent
signature, duplicate and racing keys, one binding and claim, retained budget cost,
GET no effects, old clarification compatibility. Route and browser tests cover
same-conversation recovery, reload, unknown states and no automatic dispatch.
Real platform/model verification belongs to the main integrator; fixtures are
not evidence of supplier success or business acceptance.

Rollback disables the new entry/writer and retains additive records. Unsupported
or missing recovery state fails closed. Deployment must wait for no active call.

Implementation limits: existing-proposal successor recovery is rejected explicitly.
The first release uses an explicit continue click after the independent signature;
it does not claim automatic continuation. The original creator continuation need
not be valid again: this performs no new problem CREATE. Actual model success and
full Native completion remain integrator acceptance gates.

Integrator sequence (same ordinary subject/conversation; no journal patch):
1. Back up and verify restore-readability before startup migration. In the existing
   F3 experience composition, workbench_bootstrap calls migrate_recovery immediately
   after constructing ConversationPlanningAdmission. Migration 0063 adds the two
   conversation_planning_recoveries / conversation_planning_recovery_bindings tables
   and schema_migrations version 63 only. It does not migrate old UNKNOWN rows.
2. Ordinary authenticated GET planning-v2/requests/{old-key}/read-only; GET
   planning-v2/recoveries/for-invocation/{old-invocation}?conversation_id={original}.
   Both use the existing read owner without settlement; neither schedules a call.
3. Ordinary CSRF POST planning-v2/recoveries with conversation_id, invocation_id,
   idempotency_key. This records observation and prepares the exact fresh pending
   context. It cannot claim, reserve or dispatch while unsigned. Save the returned
   context_id, invocation_id, new_request_key, recovery_id and expires_at.
4. Independent administrator GET authorization/context-admissions/{context_id};
   POST that same existing endpoint with its exact request_digest, an expires_at
   no later than returned recovery expiry (and normal eight-hour signature limit),
   and a unique signature idempotency_key. Never approve old UNKNOWN as executable.
5. Ordinary GET planning-v2/recoveries/{recovery_id} must return AUTHORIZED.
   In the original conversation click Continue, or POST the corresponding
   planning-v2/recoveries/{recovery_id}/continue with SSE Accept. This bypasses
   adaptive retries and performs one normal FIRST_PROPOSAL under existing owners.
   Repeat continue after claim reads the existing new invocation; refresh is GET.
6. Browser callback saves the returned proposal/clarification using existing
   journey CAS. A successful proposal enters existing CONFIRM/resource/Native
   continuation; a question enters existing PLANNING_CLARIFY. Do not hand-edit
   journal records. If authorization changes before dispatch, preserve old locator.

Allowed additive writes before the fresh call: new recovery observation/binding,
new context_call_requests, planning_call_preparations, audit record; signing adds
one context_call_decisions record/audit through the existing administrator owner.
Actual fresh invocation, receipt, model-use evidence and budget reservation/settlement
are written only by their normal existing owners after signature. The old problem,
invocation/result/receipt/reservation/settlement and historical context rows must
retain their hashes. Existing budget policy/allowance and expiry are not rewritten.

Review follow-up: recovery prepare uses PlanningSuggestionService.begin with an
internal prepare_only barrier. Even if a second applicant observes OBSERVED and
an administrator signs before that applicant reaches admission, preparation never
claims/reserves/dispatches. Already-claimed replay is read without settlement;
absence of an exact preparation fails closed. Only explicit continue dispatches.
The current pending planning request key is persisted before dispatch; historical
successful planning data is not a locator for a newer clarification/cycle request.
A new recovery result carries its exact request locator back from recovery state.

Follow-up validation: 22 controlled-provider planning owner tests on disposable
PostgreSQL passed, including a two-thread ready-state interleaving with zero claims,
reservations and provider calls, then one normal call. The ready-state switch is a
fixture, not an actual administrator-signature concurrency test. Nine browser
cases passed for original clarification, explicit recovery, approval withdrawal,
and current clarification/cycle/fresh-recovery locators across refresh. Frontend
build/lint passed; no actual platform, administrator signature or model was used.
