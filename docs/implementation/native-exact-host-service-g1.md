# G1: single-machine service for exact Native hosts

Status: implementation candidate, default off; no runtime activation or acceptance.
Base: 907c296. Scope approved by coordinator for the existing Native main path.
Estimated implementation and validation: 8–12 working hours, not a completion promise.

## Scope and authority

Deploy one service once. Discover subsequently saved, currently authorized owned
business continuation receipts and start/reuse one bounded exact Native host per
preparation. Keep native-host-startup.v1 authorizationResources an exact singleton;
keep existing claim/effect fencing, predecessor scope equality, grants, budget,
CRD, lifecycle and UNKNOWN semantics. No new command, run, grant or admission is
created by this service. No model call belongs to process management.

This is single-machine process assembly (G1), not a new scheduler or execution
owner. Cross-machine takeover, changed frozen/lifecycle contracts, independent
execution authorization, or UNKNOWN recovery are G2 stop conditions. No new DB,
migration, infrastructure, runtime state truth or authorization ledger is added.

## Existing modules reused

- ContinuationWork / OwnedBusinessWorkReader: current exact receipt, source,
  original command principal, approved policy and START eligibility.
- NativeDispatchWorker / prepared ready driver: existing preparation and Native
  dispatch; manager must never run the assembled worker itself.
- StartupObservation: actual immutable source/config inspection and registered
  physical startup, exact list and bounded predecessor chain.
- native_host_provenance / execution owner: claim identity, fencing, effect-time
  authority and observe-only EFFECT_STARTED restart.
- governed_execution_supervisor provides the local lock/owned files/pipe patterns;
  it is not a reusable multi-host manager (its child is fixed to the Web service).

## Proposed internal interface and process records

Opt-in service configuration pins installed manifest, existing policy-file paths,
namespace/domain/principal, state directory and maxHosts/poll/readiness/shutdown
limits. Environment secret values never enter local records. Config has no future
preparation IDs. The manager verifies one existing production composition, reads
eligible receipt/command facts only, and derives an exact launch config.

Stable worker identity hashes database identity + namespace + domain + principal
+ preparation digest. Bounded children each retain their exact allowlist through
restart. A private 0700 local directory contains 0600 immutable boot configs and
startup records plus atomically replaced fsynced process status. Status tracks
identity, launch digest, child PID/birth, boot ordinal, observed startup digest,
exit confirmation, blocked reason and bounded retry timing. These are operational
records only; database owner facts remain execution truth.

A machine-local service lock prevents duplicate discovery writers. Each child
holds an inherited exact-worker lock. Manager crash cannot make the same worker
available while its child still owns that lock. A parent-liveness pipe makes the
child stop polling on supervisor loss; uncertain/live PID is never killed or
replaced based only on stale numeric PID. PID birth and startup identity are
checked. Readiness means exact startup observation and identity verified, not
Popen success. Missing/corrupt registration blocks recovery rather than fabricating
provenance. Startup files are immutable/exclusive; missing or divergent predecessor
and chains exceeding the existing 32 limit remain blocked.

## Discovery and lifecycle boundaries

Only formally saved ownedBusiness receipts under configured subject/domain and
current policy are candidates. Require exact preparation, run and command binding,
current owner scope and original grants. No catalogue or arbitrary SQL row grants
execution. Use bounded fair scanning; cap active hosts and preserve queued work.
No second worker loop runs in the discovery service.

QUEUED or eligible expired CLAIMED can start a host under original owner rules.
EFFECT_STARTED may resume only the original stable worker/provenance as the
existing observe-only branch, never a new invoke. UNKNOWN and settled terminal
commands do not create restart work. Pending questions do not count as drained;
keep their host available. Reclaim capacity only after confirmed child exit and
formal terminal/no pending work, never from a transient empty scan or authorization
read failure. Revocation/expiry must fail closed at claim/effect and may stop local
polling, but never rewrite task outcomes. Generation/policy changes require a
verified physical restart; no in-place config mutation.

## Fault handling and validation

Pure/process tests: stable identities and scope, no secret persistence, insecure
paths/symlinks, duplicate manager/child locks, PID reuse, parent death, unconfirmed
startup, readiness timeout, bounded retries, max concurrency and fair scanning,
state atomicity and exact predecessor handling. Real disposable PostgreSQL tests:
current owner receipt/grants, two preparations created after service startup,
concurrent claim/fencing, revoke/expiry/budget refusal, CLAIMED recovery versus
EFFECT_STARTED observation, UNKNOWN exclusion; no fabricated execution facts.
Use controlled transports, with evidence clearly separated from actual deployment.

Coordinator-owned actual acceptance: deploy once, ordinary account creates at least
two newly authorized preparations afterward; service automatically attaches exact
hosts, necessary questions continue through original conversation and final result
returns there. No operator per-preparation prepare/start; no replay of prior success
or UNKNOWN. Existing original-subject grants, budget totals, audit and historical
records must remain exact. This gate cannot be claimed from unit tests.

## User and installer observation contract

`NATIVE_EXACT_HOST_SERVICE_STATUS_DIRECTORY` enables optional `hostDispatch` on
existing native-progress, only after all its existing exact READ checks. It carries
state QUEUED/STARTING/READY/STOPPING/BLOCKED/UNKNOWN, exact preparationDigest/runId,
nullable ISO observedAt, and a fixed safe reasonCode (WAITING_CAPACITY,
START_BLOCKED, CURRENT_CONDITIONS_BLOCKED, OBSERVATION_UNAVAILABLE, or null).
No PID/path/secret reaches the user. Only an observed capacity limit means QUEUED;
missing/stale/wrong-scope/invalid state is UNKNOWN. TTL is max(30,3*poll) seconds,
at most 180. READY is process readiness, never task or business success. Existing
steps, questions and terminal outcomes remain authoritative.

Installer owns the sole service process and must inspect service-status plus all
exact-worker status/lock files before changing the installed source. SIGTERM
closes child parent pipes, stops additional polls, then waits a bounded interval.
EXIT_UNCONFIRMED is a hard installation blocker; source replacement must not occur
until actual child exit/lock release is verified. No uncertain child is killed to
manufacture safe completion. Each worker PID/birth is checked, not numeric PID
alone. Service and child status files are management evidence, not runtime truth.

Terminal prepared progress is drained only when the existing product_outcome
projection exists. If it is missing, an exact host may run existing after_tick
review to finish delivery; terminal progress is excluded by work.dispatches, so
this does not enqueue/claim/invoke again. UNKNOWN/RECOVERY_REQUIRED remains
ineligible even if no product outcome exists. Result review still has its own
current owner authorization; management state does not certify delivery.

Deployment environment: opt-in `NATIVE_EXACT_HOST_SERVICE_CONFIGURATION` points
to the owned service config. Existing NATIVE_DISPATCH_DATABASE_URL, authority,
continuation, owned-business policy and migration paths are supplied by the same
approved credential loader; NATIVE_DISPATCH_PREPARED_SKILL is exactly
registered-readonly-v1. The assembly requires a fixed discovery-only
NATIVE_DISPATCH_WORKER_ID; that assembled worker is never polled. Per-child worker
IDs override it. Do not provide NATIVE_HOST_STARTUP_CONFIGURATION or inherited
service FDs to the manager. The existing host mode is unchanged when no service
FDs are present. The API's status-directory env must name the same private state
directory, but reading it grants nothing.

A deterministic machine-local database-fingerprint lock is held by the manager
and inherited by every child. Thus an abruptly killed manager cannot be replaced
while any child still holds the lock, even if the new process points to a different
state directory. This intentionally prefers a visible startup block over a
second manager. An unconfirmed child remains a counted capacity slot; there is
no capacity reclamation based solely on a failed status write or pipe failure.

Projection subject lookup: after the requester's existing exact READ checks, use
same-connection Native command -> attempt -> prepared task binding facts, scoped
to the exact namespace/domain/run/preparation resource, to find the unique original
execution subject. An authorized administrator can read that subject's observation;
the requester is never substituted as execution subject. Zero/multiple subjects or
storage failure yields UNKNOWN, with no arbitrary latest selection or file scan.
