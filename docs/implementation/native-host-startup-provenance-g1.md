# G1: Native host startup provenance and bounded restart

Purpose: inspect the actual installed source and effective startup before Native
claims/effects, preserving315 claim/reclaim fencing and observe-only restart.
This never retries, settles or repairs historical UNKNOWN. Default disabled;
production activation and real host/model acceptance belong to the coordinator.

## Existing owners and compatibility

Host composition/HostRecoveryControl retain current authority. The PostgreSQL
execution owner retains command claim, fencing and effect permission. Existing
CLAIMED JSON facts carry startup observation plus exact command/worker/generation
binding; no new queue, authorization system, budget, schema, migration or fact kind.
Canonical command/claim, lifecycle states, CRDs and public API remain unchanged.
This package is independent of migration0064, REUSED recovery and Task repair.

Compatibility basis: docs/engineering/S5-V023-IMPL-315-NATIVE-EXECUTION-HANDOFF.md
specifies a stable externally configured worker, lease reclaim before effect,
monotonic generation/fencing and EFFECT_STARTED-only observation on restart.
docs/evidence/s5/v0.2/s5-v023-impl-315/README.md records those tested behaviors.
The follow-up retains those transitions under a source-binding restriction,
rather than introducing another recovery lifecycle. No concrete frozen contract
change/G2 transfer is proposed. Existing no-provenance behavior stays compatible.

## Startup inspection

NATIVE_HOST_STARTUP_CONFIGURATION points to an owned0600 non-symlink config with:
workerId, namespace, securityDomain, principalId, manifestPath, manifestDigest,
recordPath, policyFiles, authorizationResources. Restart additionally requires
predecessorRecordPath and predecessorDigest. The logical workerId is stable;
every physical startup gets a fresh startupId and exclusive recordPath.

After host composition but before polling, the startup owner checks the existing
installation composition manifest (source,commit,sourceHashes), every listed
source file, and the actual loaded ManagedSkill transport/caller/host/observer
module locations. It records PID/birth, installed-source/manifest digest, allowed
launch/policy hashes and active authority generation/recovery epoch. This proves
inspected files and loaded locations, not arbitrary process-memory attestation.
Credential values and raw policy contents never enter the observation.

policyFiles pins NATIVE_DISPATCH_AUTHORITY_CONFIGURATION, and also
NATIVE_LOOP_RUNTIME_FILE / NATIVE_DISPATCH_CONTINUATION_POLICY whenever present.
The Native Loop's referenced modelRuntimeFile must match modelRuntimeDigest and
is checked again before claim/effect. Source, configuration, process identity,
effective environment and registration-record drift fail closed.

Registration uses exclusive creation, fsync of file and parent directory. An idle
startup record is observation, not authorization or execution. An actual command
has no worker at QUEUED; binding occurs at the existing CLAIMED boundary.

## Explicit restart lineage and existing claim fencing

The predecessor owned record is read and hashed. Its worker, scope, principal and
exact resource allowlist must match. The new observation carries a bounded
32-entry predecessor-digest chain; original records remain immutable. A current
source observation is required independently; the old file cannot stand in for
the new process's startup. No budget, expiry, action or data scope is enlarged.

The claim owner locks logical worker identity then exact candidate command. All
previous source bindings for that worker must belong to the declared lineage;
two divergent successor observations cannot both claim work. Sources without a
matching ancestor cannot take the worker identity. No-provenance workers cannot
downgrade or reclaim a provenance-bound command.

Fresh QUEUED work is restricted to exact original subject/namespace/domain and
resource allowlist, intersecting current continuation eligibility. A bound
CLAIMED command is reclaimable only after its lease expires, under the same
original worker and exact recorded source chain. The existing owner increments
claim generation and fencing token and appends a genuine CLAIMED fact containing
the new source observation. Old source/claim facts stay unchanged. The old claim
cannot obtain effect permission. Physical host exit is not used as effect proof.

The worker lock and command lock use the same order for claim and effect entry.
If effect wins first, later reclaim sees EFFECT_STARTED and cannot dispatch. If
reclaim wins first, the old generation/fence fails. A second source successor
fails the lineage check after the first successor's claim commits.

## Observe-only restart after effect

EFFECT_STARTED never receives a new effect claim. The existing resume method
returns the original claim/fence; the new source must have the recorded original
source in its exact lineage. permit_effect returns REPLAYED, leading only to
Kubernetes observation, never transport invoke or Task create. Existing terminal
and uncertain owners still record outcomes; UNKNOWN is never selected for retry.

A local immutable startup-linked observation-admission receipt records exact
command/digest/generation and effectInvocationAllowed=false. It is not evidence
that a read succeeded or that the Task reached a terminal state. No artificial
CLAIMED/terminal event is inserted for observer replacement. Source registration
is not an independent authority proof or a replacement for execution grants.

## Tests and limits

Directed tests cover real disposable-PostgreSQL lease reclaim, exact source facts,
old-claim fencing, two-successor contention, unbound downgrade refusal, started
restart retaining generation/fence and REPLAYED, legacy behavior and UNKNOWN
non-retry. Worker tests verify observe-only restart invokes/creates zero times.
Startup fixtures cover source/policy/process drift, exclusive registration,
explicit predecessor hashing and cross-scope/resource refusal.

Commit3f6's initial opt-in first-start profile could not reclaim a bound expired
claim; the follow-up restores the existing315 paths. Negative boundary evidence
for that first version is historical, not a claim that it already recovered.
Controlled tests and local source inspection are not an actual restarted live
host/provider demo. Independent review, normal checks and coordinator-owned
activation remain separate evidence, and no actual host/model/Task is touched
while implementing this candidate.
