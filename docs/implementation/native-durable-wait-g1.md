# G1: durable human waiting within one accepted Native job

Status: concrete design for independent review; implementation not yet started.
Base d3e9d6d plus frozen scope-answer patch4329f509. Root owns actual deployment,
configuration, model calls and publication. Migration0068 is reserved;0067 belongs
to fixed work. Default off. Existing180-second executor and all old jobs unchanged.

## Scope and accepted boundaries

Keep one original Skill invocation, Attempt, Native command, Task UID and managed
slot. Native stays EFFECT_STARTED, Skill stays RUNNING, public Task stays Running.
Human waiting is an internal typed observation, never success, retry, unknown
recovery or a new public state. Reuse original exact identity and grants, and
preserve all old model reservations. No new infrastructure or new dispatch power.

ARCH-263 accepted sections3/4/6/9 allow known accepted/running observations but
prohibit redispatch/extra managed slot/unknown replay. ARCH-208 is currently
PROPOSED/NOT_FROZEN and does not supply an implemented pause adapter. This slice
will not use its PAUSE enum as a shortcut. If a proposed edit needs to change
public CRD states, terminal/UNKNOWN semantics, old immutable executor config or
permit_effect replay behavior, stop and list that concrete conflict.

## Internal types (new opt-in successor only)

`WaitIdentity`: namespace,securityDomain,preparationDigest,workflowRunId,taskId,
attemptId,commandId,skillInvocationId,principal,conversationId. All resolved from
current owner rows and immutable prepared bindings, never trusted client input.

`WaitCheckpoint`: schema=native-human-wait.v1; identity; ordinal; rootKey/rootDigest;
questionKey/questionDigest; executorId/revision/configurationDigest;
sourceSnapshot/sourceDigest; modelProfileDigest; scopeEvidenceDigest;
completedEffects[{key,requestDigest,resultDigest}]; remainingActiveMilliseconds;
maximumDecisions; immutable humanExpiresAt; checkpointDigest. No credential or raw model
request. References point to existing saved effect receipts; no synthetic history.
Question text remains its existing private native_loop_records record.

`WaitObservation` state: QUIESCING, WAITING_FOR_USER, ANSWER_SAVED,
CONTINUATION_CLAIMED, ADVANCING, COMPLETED, EXPIRED, BLOCKED. These are internal
checkpoint states, not public Task/Skill/Native lifecycle states. A subsequent
CLARIFY creates the next immutable checkpoint; previous checkpoint is COMPLETED.
No automatic timeout retry from CONTINUATION_CLAIMED/ADVANCING.

`ContinuationClaim`: checkpointId/version,answerDigest,generation,opaque fence,
workerId,startupRecordDigest,claimDigest. One generation per answer checkpoint;
claim returns {newlyClaimed, claim}; duplicate callers only observe the same claim.
Only newlyClaimed=true for the exact worker/startup may enter continuation; an
existing claim is not an executable bearer token. The proposed
first release does not auto-reclaim a claim that may have advanced: ambiguous
post-claim process death blocks for observation, not another model/tool call.
Pre-claim process restart and waiting restart are supported.

`StopObservation`: exact checkpointDigest and original command/startup/worker,
private process birth/nonce binding, observed exit receipt digest and stoppedAt.
Only the composition-owned manager observer may supply this; no browser route or
boolean stopped=true caller parameter. OS exit alone is not enough: checkpoint
must already prove a safe point with no unsettled model/tool effect. PID reuse,
missing source binding, or unconfirmed exit remains blocked. Private process
identifiers stay out of business projections.

##0068 storage and transaction contracts

Use the existing PostgreSQL authority DB. Add typed checkpoint, append-only wait
observations and unique continuation-claim rows under skill_invocation. Each row
has scope+invocation foreign keys, fixed schema/digest, and version. One open wait
per invocation enforced by unique head; one continuation per checkpoint/answer.
Migration has checksum registration and runs only for explicit successor opt-in;
old runtime/default-off reader never depends on table existence.

Global order follows existing Native effect owner: protected authorization barrier
before DB; current generation authorization/worker identity lock; Native command
FOR UPDATE; Skill projection FOR UPDATE; prepared progress FOR UPDATE;
wait head/checkpoint; native question/answer records. Attempt state is checked under
the command lock; no attempt/task row is acquired before prepared progress. No transaction spans model,
tool, Kubernetes, pipe/OS wait or HTTP. All owner callbacks use caller connection.
Verified lock evidence: SkillInvocationRepository.commit_terminal first locks Skill
projection (skill_invocation_postgres.py:551), then store_skill_output locks prepared
progress (prepared_execution_observations.py:111). Therefore the proposed initial
progress-before-Skill order was WRONG and has been corrected above. Cancellation
request locks prepared progress then syncs run/task projections; it does not acquire
Skill or command (prepared_execution_cancellation.py:15). Native permit/terminal
holds command then updates prepared progress. Durable answer must acquire its
command and Skill before its current progress lock; legacy answer has no command
or Skill write and remains unchanged. No cancellation path may acquire wait head
and subsequently command. Tests must include actual cancellation/terminal races.

`register_wait(c,command,invocation,checkpoint,question,authorize)`:
- current authorization before protected data; exact command EFFECT_STARTED,
  attempt RUNNING, prepared current attempt, Skill nonterminal exact executor;
- all completed MODEL/TOOL receipt digests match, no claimed/unsettled external
  effect, ordinal within original limits; original root claim matches;
- atomically insert question and checkpoint+QUIESCING observation; INPUT effect
  claim is inserted IN THIS SAME transaction with question/checkpoint, not by the
  legacy effect wrapper before calling register_wait; add accepted/running facts if
  required using the existing Skill/ResourceUse reducers in this transaction;
- return `SkillJobWaiting(checkpointRef)` distinct from SkillExecutorResult.
  Synchronous legacy invoke never treats this as accepted terminal output.
  NativeLoop.effect must detect the typed wait return BEFORE snapshot()/INPUT
  finish and propagate it without its exception STOPPED/UNKNOWN conversion.
  SkillApplication must detect it BEFORE reading result.output or commit_terminal;
  PreparedNativeTransport must detect it BEFORE its non-success UNKNOWN branch.
  No dict sentinel or thrown exception may encode a normal human wait.

`confirm_stopped(c,checkpointRef,StopObservation,observerAuthority)`:
- exact safe checkpoint and trusted manager child identity; QUIESCING only;
- store append-only stopped receipt and move to WAITING_FOR_USER, or ANSWER_SAVED
  if a valid answer was saved while draining. Never require an answer before
  release. Manager keeps capacity occupied until stop is confirmed.

`accept_answer(c,NativeAnswer,currentContext)`:
- reuse native_interaction.answer full identity/conversation/digest/current
  START+USE/run/source/expiry checks; original180s route unchanged;
- for opt-in checkpoint atomically save original answer and answered observation,
  and finish the existing INPUT effect receipt with that exact answer reference;
- does not call model, create execution command, or authorize continuation itself;
- idempotent identical payload; conflicting/stale input fails closed.

`claim_continuation(c,checkpointRef,workerIdentity,currentAuthorization)`:
- require stop receipt + exact saved answer + current source/standing/credential,
  grants and untouched original Skill/Attempt/command, no cancellation/terminal;
- recompute checkpoint/effect references; current budget eligibility (no reserve
  until a real new MODEL decision) and remaining ordinal/active duration;
- CAS waiting head version and insert unique claim/fence; repeat returns
  newlyClaimed=false and cannot invoke continuation.
  No original native invoke/prepare_dispatch or new Attempt is called.

`mark_advancing` and every subsequent effect must check the same continuation
fence plus current authority IN THE SAME transaction as effect-journal claim.
A mark_advancing-only check is insufficient; a duplicate or stale caller cannot
insert a model/tool claim or mutate the active root. A resumed loop can produce
another wait, terminal result, or uncertainty. No new work after old claim loses
its fence. Terminal result uses the original Skill commit_terminal and original
Native/Kubernetes terminal observation path; no separate product success writer.

## Loop and executor interfaces

Distinct successor executor config declares DURABLE_OWNER_HUMAN_WAIT_V1 (the
current180s descriptor stays byte-for-byte unchanged). Registry must exact-match
this successor; no implicit latest or automatic replacement of old participants.
New `SkillJobWaiting` return type is internal/opt-in, not valid terminal output.
`SkillInvocationApplication` checks opt-in result identity and committed checkpoint,
returns existing RUNNING projection and does not call commit_terminal. All other
executors keep current code and recovery rules.

`NativeLoop.run` legacy unchanged. New explicit `run_continuation(checkpoint,
claim)` verifies original root plus persisted effect references and begins at
next ordinal. Root result stays unfinished while the positive checkpoint exists;
old uncheckpointed unfinished roots still produce UNKNOWN. No replay of previous
MODEL/TOOL/INPUT keys. Elapsed active execution budget resumes from saved balance;
human waiting does not reset maximum8 decisions, cost ledger or active600s cap.

Document adapter reconstructs in-memory confirmed scope/reviewed state from exact
completed owner observations, not by re-invoking old tools. A recorded successful
review is trusted only after source/rule binding and receipt digest verification;
missing/changed input blocks. Every new tool still passes original current USE.
No restoration from arbitrary chat/model text. A checkpoint cannot be claimed if
its preceding model receipt is unknown/unsettled or its source changed.

## Transport, manager and host release (C connection, not yet implemented)

PreparedNativeSkillCaller propagates a distinct WAIT reference. Prepared transport
and worker recognize only this opt-in positive waiting receipt, leave Task Running
and Native EFFECT_STARTED, and return a local DRAIN_FOR_INPUT result. They do not
map WAIT to Failed/Succeeded/UNKNOWN. Existing REPLAYED path remains observe-only;
new owner `continue_accepted_job` is a separate continuation port and does NOT call
transport.invoke or SkillInvocationApplication.invoke again.

Child stops polling after DRAIN_FOR_INPUT and writes its bound safe-wait receipt;
manager observes exact child exit, calls confirm_stopped and releases its slot.
Discovery checks persisted wait state before spawning: unanswered waiting jobs
consume no child/slot and cannot cause repeated restart. Current-authorized saved
answer makes the same prep eligible for a new exact source-bound observer host.
Startup provenance/parent chain remains unchanged. The new host asks the wait
owner for a continuation fence, then advances the already accepted internal job.
Current expired/revoked policy blocks; service creates no execution grant.
Manager/child state remains process observation, not execution truth.

Crash cases: before checkpoint commit keeps old ambiguity rules; committed wait
but no stop observation retains capacity/block until trustworthy death observation;
answer before stop is saved but cannot execute; stop then unanswered restart just
observes; duplicate spawn cannot claim twice; claimed/advancing crash with unknown
effect does not auto-replay; terminal/UNKNOWN never becomes waiting or resumed.

## Product projection (D connection, not yet implemented)

Existing native-progress result adds optional durableWait with exact preparation,
run/invocation/question key+digest/checkpoint version, state, expiresAt and safe
reason code. Existing EXECUTION+resource READ protects it. Same owner-derived
projection feeds original question card/right progress and current-work/inbox.
No process IDs/secrets. Answer saved differs from execution resumed. Expired or
revoked remains visible as blocked/expired with retained content; no new-key retry.
Old question view unchanged. Read/poll never resumes or extends permissions.

## Implementation/verification sequence and honest milestone boundaries

A: typed values and0068 owner transactions. Pure validation plus disposable PG
real command/Skill/root/question rows, actual foreign keys/reducers; negatives
for scope/version/digest/unfinished effects/terminal/cancel/expiry/revocation.
B: exact answer+stop+unique continuation CAS; concurrent duplicate claims/answers,
crash boundaries, current grants and budgets checked. No mocked all-grant proof.
A/B alone is NOT a delivered durable waiting feature; default off and C/D blocked.
C: new exact executor + real managed caller/transport/worker/manager composition,
controlled provider and actual child exit, then >3min simulated clock wait without
busy host, second prep progresses, same original job advances once and completes.
D: ordinary browser uses same composer/question card/inbox facts; saved answer,
refresh, stale answer, denied continuation and result return; no model fixture
accepted as real provider proof. Root finally deploys once and validates a fresh
ordinary authorized question after >3min, without touching the old failed task.

No production configuration/publication/migration/model or actual worker operation
is authorized to this agent. Root handles final real acceptance and release.

## Deadline and active-time semantics (independent review clarification)

humanExpiresAt is a new immutable successor-executor policy bound, capped by the
current exact standing scope expiry, allowance expiry and original dispatch
credential validity. It is NOT min(180s,remaining wall execution). It must exceed
now when checkpointing and is never extended by answer/read/restart. A newly
current credential can authorize a continuation only inside this original bound;
rotation does not rewrite the checkpoint deadline. remainingActiveMilliseconds
is a separate monotone execution budget, charged for model/tool work before and
after waiting, not for stopped human wait. Original decision count and ledger stay
unchanged. Current grants are independently checked even before this deadline;
expiry/revocation always blocks new advancement. A product deadline beyond these
original bounds would need a distinct explicit policy change, not silent renewal.

Independent review: f3_resource_detail identified typed WAIT interception at all
three synchronous boundaries, actual reverse terminal lock order, deadline
separation, and duplicate continuation ownership. These are incorporated before
production code. Review is not implementation/actual runtime acceptance.

## A/B implementation progress

First owner slice exists in native_wait_types/store/owner/skill and0068, all
unwired/default-off. Six distinct isolated PG checks (five together and the new
same-transaction effect fence rollback separately) and24 pure checks passed.
Tests use real prepared/Native/Skill owner-created rows with controlled executor,
authority and stop observers; they do not prove the deployed release/restart path.
Current C integration must supply actual same-connection authority ports, trusted
physical exit proof and exact worker provenance; the test callbacks are not
production composition. No final stage acceptance is claimed.

Additional controller check: task_controller.py returns for
agentos.io/native-dispatch-managed=true before its legacy timeout/Running replay
handler. Keeping the original managed Task Running while positively checkpointed
therefore does not require changing that public Task schema or resetting its
startedAt. The managed worker still needs explicit WAIT handling; its existing
REPLAYED observation path must not be silently replaced with invoke.

## C composition gates (must not be replaced by test callbacks)

The A/B authorization port must validate checkpoint maximum_decisions against the
pinned successor executor's8 decisions and remaining active time against observed
monotone runtime use. Structural upper bounds32/600000 are not that validation.
Model profile digest, scope evidence digest, original root commitment and exact
source must derive from the original accepted request and current pinned runtime,
never a caller's checkpoint assertion. Resume reconstructs original inputs from
exact source/prepared dependencies and verifies stored Skill input/payload digest;
it must not copy model output or pick current/latest resource revisions.

An independent review found claim_effect originally did not compare the supplied
checkpoint to the claim's stored checkpoint. Fixed by requiring cp.digest equals
claim.checkpoint_digest AND full immutable stored checkpoint equality before any
ordinal/effect claim. The added actual PG negative changes both active budget and
maximum decisions with the old valid fence; it rejects before journal insertion.
Multi-round ADVANCING→COMPLETED+new checkpoint still needs one owner transaction;
current register deliberately rejects an active checkpoint until that C interface
is implemented. This is a listed incomplete connection, not permissive fallback.

## Concrete C/D connection work remaining

1. NativeLoop now has an opt-in defer_input branch returning typed LoopWaiting;
   existing INPUT authorization/deadline checks remain, synchronous effect wrapper
   is not entered.37 loop conformance checks passed, not a production port.
   Resume still needs owner-reconstructed root/trace/observations/seen and a
   next-ordinal entry. Its first operation must win enter_continuation; a repeated
   caller returns an observation without running or terminalizing the root.
2. NativeLoopRuntime must derive the checkpoint from exact original prepared
   inputs, current registered successor config, real receipt digests, pinned
   model binding and actual remaining active time. It must validate all these
   again on resume. Existing output reconstruction is available through
   PreparedNativeSkillCaller.input_snapshot/build_request; verify persisted
   inputDigest/payloadDigest before using it. No new Skill invoke is permitted.
3. New document executor successor alone accepts typed LoopWaiting and forwards
   SkillJobWaiting. SkillInvocationApplication must observe the already saved
   RUNNING projection before touching output/terminal branches. Its recover path
   needs a positive exact checkpoint read case; old unfinished uncheckpointed
   jobs must still become UNKNOWN as today. Final terminal writer already avoids
   adding duplicate accepted/running facts after a genuine RUNNING observation.
4. ManagedSkillNativeTransport/NativeDispatchWorker must return a nonterminal
   drain receipt for exact WAIT, preserving original Task UID and EFFECT_STARTED.
   The new continuation port advances the accepted Skill only after winning the
   checkpoint entry CAS; it does not call transport.invoke/prepare_dispatch.
   Existing generic REPLAYED path remains read-only. No terminal reactivation.
5. ContinuationWork discovery excludes unanswered waits; NativeHostService observes
   the exact child exit before writing StopObservation and freeing a slot. Current
   authority plus saved answer makes the original prep eligible again. Successor
   startup proof must use the existing stable worker/provenance chain, and owner
   validates it at entry and every effect claim. Local process files remain
   observation only. Child stop failures retain capacity and block continuation.
6. native_interaction.answer keeps current original-subject/conversation/digest/
   START/USE checks then uses the wait owner in its existing transaction only for
   a positively identified new successor checkpoint. The old180s path stays.
   Answer receipt never starts work itself. For a second CLARIFY, the old wait's
   completion and next checkpoint/question must commit together under the same
   continuation fence; this transition is not implemented yet.
7. native-progress/rightbar/question/current-work use one optional owner-derived
   durableWait projection, protected by their exact READ contracts. Saved answer,
   queued continuation, advancing and expired are distinct; polling/read never
   resumes execution. D needs ordinary browser evidence after C is wired.

Latest checks after entry-CAS:7 owner PG tests in one final run PASS16.39s;
24 types/Skill-domain pure checks and37 runtime checks PASS. Independent review
fixed checkpoint-tampering fence hole before C. No final fullhook or actual
runtime test has been claimed.

## C/D implementation checkpoint (supersedes incomplete list above)

Implemented in the isolated candidate: exact v6 opt-in executor/configuration;
real original Skill accepted-job continuation (no prepare_dispatch/invoke);
typed WAIT through Skill application, managed transport and Native worker;
command/progress/Skill preservation; fenced actual journal claims AND receipts;
atomic second question; same-root terminal receipt; host inspect/stopped adapter;
manager physical-exit proof and positive-wait discovery filtering; current
Native answer owner bridge. Config remains absent/off in ordinary composition.

Checkpoint source_digest binds the exact source revision digest, not content
hash. Current OwnedBusinessWorkReader independently validates its retained source
content and policy. Its returned scope.source MUST equal preparation.source_snapshot
in full. Passing revision digest into the sourceContentDigest argument was caught
by the real-owner integration test and corrected; no equality check was removed.

Disposable integration evidence: real published v6 document resources and
same-subject owned admission, problem, planning, preparation, original Skill and
Native command; two questions/answers/resumptions, seven unique decision keys,
four original Skill invocations and four artifacts, same-run FINISH. The model
and Kubernetes are controlled fixtures, not actual-provider acceptance. A second
fixture uses real OS child processes and fresh connection pools, with current
owner inspect/stopped checks and original-job restart. It uses test-only fork
and emits the platform's multi-threaded-fork warning; production manager exec/GO
integration is separate and cannot be inferred from this check.

Outstanding acceptance work: real >180-second answer test terminal, manager
capacity plus another authorized prep joint proof (local manager conformance alone
is insufficient), actual NativeLoopRuntime governed-provider/budget composition,
BFF answer current-authority regressions and optional durable-wait UI projection,
known failed continuation terminal mapping, complete normal hooks and root-owned
live deployment/model acceptance. No completed state or old UNKNOWN is revived.
Typed question-meaning v7 is separately owned/configured and is NOT enabled by v6.


Latest evidence update: the physical-child case completed with a real 181-second
human delay (219.60 seconds total), two waits and original-job completion. The
read-only durableWaits projection has one owner PG check; known FAILED
continuation mapping has three controlled worker checks. These do not replace
production manager capacity or real-provider acceptance. The first actual BFF
answer test correctly rejected the fixture's missing private-conversation work
link; the test now performs the normal READ_PROBLEM-validated link operation
before answering, pending rerun. No product ownership check was weakened.

The subsequent actual ordinary BFF test passed (41.23 seconds): formal work link,
two current-authority answer submissions, cross-conversation/wrong-digest refusal,
idempotent original receipts and no decision during answer/GET. The same test
interrupts Skill terminal persistence after root/head COMPLETED, then re-enters
the original command and reads the stored root. All seven decision keys remain
unchanged; original four Skill jobs/artifacts complete. The injected interruption
is controlled, not an actual process crash; the separate physical-child test
covers exit at human wait. Evidence: native-durable-wait-r1/
browser-owner-and-completed-root.log. Earlier BFF runs exposed only the omitted
formal test link and then a test replay changing its expectedVersion; the final
helper replays the original complete link command.

### Deadline clarification within the disabled candidate

`human_expires_at` is the immutable deadline for a NEW human answer, not a second
execution lease. A previously accepted answer is durable evidence of arrival
before that deadline; its exact idempotent readback remains possible. Continuation
and each effect still require the original immutable `authority_expires_at`, all
current authorization checks, remaining active milliseconds and the original
fence. Neither timestamp is extended. An unanswered expired question cannot gain
an answer/claim, and current revoked authority still refuses every write. This
closes the boundary where an answer arriving on time became unusable solely
because the bounded host queue reached it after the human deadline. The read
projection does not call an already-saved answer expired. Existing shipped 180s
executors and records remain untouched. Clock-controlled owner tests cover both
deadlines separately; their execution status belongs in the final test evidence.
