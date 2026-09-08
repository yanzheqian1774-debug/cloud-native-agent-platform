# IMPL-288 — Governed Execution authority addendum

## Decision and implementation authority

Session: `S5-V023-IMPL-288`.
Source classification: `HUMAN_ACCEPTED_NEW_DECISION`.
Status: `HUMAN_ACCEPTED / BRANCH_RECORDED / NOT_MAIN_DURABLE`.

The Human authorizes this bounded internal backend decision and its implementation
in the existing IMPL-288 branch and Draft PR. It allocates no ARCH identifier and
does not change a public API, CRD, Kubernetes API group, historical Session, or
previously accepted decision. The
[IMPL-276 composition addendum](S5-V023-IMPL-276-DIGITAL-EMPLOYEE-COMPOSITION-IDENTITY-ADDENDUM-V1.md)
remains supporting identity authority; it does not substitute for this decision.

## Trusted request and authorization

The governed Execution HTTP entry authenticates a bearer credential through a
server-owned credential resolver. Persisted configuration contains only credential
digests and trusted principal/scope facts. Missing, malformed, unmatched or expired
credentials fail closed.

Execution, Skill Invocation, Resource Use and Evidence-reference disclosure retain
separate domain owners and exact `principal/scope/action/resource` authorization
decisions. Authorization precedes protected lookup, binding or executor resolution,
claim disclosure and provider call. Client-supplied identity, authority, policy,
executor or endpoint assertions grant no authority.

## Exact Plan, task and Skill operation binding

Execution consumes one already approved exact Plan. The Plan fixes an immutable
Workflow revision and task; that task must contain the exact Skill ID, revision,
digest and operation binding submitted as request assertions. The published Digital
Employee member, published Skill operation, side-effect policy and allowlisted
executor revision must independently resolve to the same immutable values.

Historical Workflow content and digests are never backfilled or recomputed. A new
binding becomes executable only in a successor Workflow revision after its normal
review/publication and through a new exact approved Plan. Publication and matching
do not grant execution authority.

## Evidence-reference disclosure

Evidence reference disclosure is authorized independently from Execution,
Invocation and Resource Use reads. A restricted projection does not disclose a
restricted Evidence ID, digest or count and does not expose the complete immutable
Resource Use snapshot identity. It reports `FILTERED / RESTRICTED`, while leaving
the underlying append-only Evidence and immutable snapshot unchanged. Evidence
content is not dereferenced by this entry.

## Complete request claim and recovery

Execution owns a durable claim over the complete HTTP request semantic, including
the canonical input digest. The claim and its Workflow Run, Task Run and Attempt
identities are created in one PostgreSQL transaction. Same scoped key and same
payload may continue after a pre-dispatch interruption; a different payload fails
closed. An existing Execution identity without its claim is never backfilled.

Invocation identity, exact binding, request facts and `DISPATCH_RECORDED` remain
durable before the provider boundary. One process-local invocation owner serializes
the synchronous caller; a concurrent replay waits for that active caller and cannot
prematurely recover its in-flight dispatch. This ownership is not a durable lease,
scheduler or new authority.

After process loss, an existing non-terminal durable dispatch is recovered through
the existing Skill recovery operation and atomically appends the Invocation,
Evidence and Resource Use `OUTCOME_UNKNOWN` terminal bundle. Recovery never calls
the provider again. If recovery persistence fails, the entry returns an error and
leaves `DISPATCH_RECORDED` durable; it does not claim that unknown was persisted and
does not redispatch. A retry remains a separately authorized successor Attempt and
Invocation. Exactly-once external effects are not claimed.

## Supervised recovery correction

The Human additionally accepts one bounded, same-host supervised process
constraint for this entry. Every `GovernedExecutionApplication` in one process
uses one process-wide, database-scoped Invocation ownership registry. Releasing
or closing an unrelated application cannot remove another application's active
Invocation ownership.

The governed entry is enabled only in the single Uvicorn child created by
`agent_console.governed_execution_supervisor`. The supervisor holds a
credential-free execution-database keyed lock in a fixed host-local state
directory and passes that same locked file description plus a one-way lifetime
pipe to its child. The child validates the lock inode, database fingerprint,
handshake token and actual parent PID. These are bootstrap facts and cannot be
minted by an HTTP header or request parameter. Ordinary unsupervised startup
leaves only the governed entry unavailable; unrelated Console capabilities are
unchanged.

The supervisor releases ownership only after its managed child has actually
exited. If the supervisor disappears first, the child observes lifetime-pipe
EOF and stops accepting new governed invoke, replay, read or recovery requests,
while its inherited host lock remains held until that child exits. A replacement
supervisor therefore fails closed until the kernel can reacquire the same lock
inode. PostgreSQL connection loss, heartbeat age, missing PID, free port, or a
new PostgreSQL advisory lock is never treated as predecessor-exit proof.

Confirmed platform-process exit says nothing about provider completion. After
confirmed child exit, a successor maps an existing durable dispatch without an
authoritative terminal fact to `OUTCOME_UNKNOWN` and never calls the provider
again. This is not provider cancellation, provider fencing, business failure or
exactly-once external execution.

This constraint is only enforceable on one host through its fixed local lock
directory and one normalized database target. It does not coordinate independent
local state on another host and therefore grants no cross-host takeover, HA or
failover claim. A second host must remain disabled absent a separately accepted
coordination/fencing design.

## Workflow binding edit preservation

Workflow draft edit compares tasks by stable `taskId` against the prior draft.
When a retained prior task has non-empty `skillOperationBindings`, omission or
explicit `null` is rejected before revision persistence. An explicit binding
value continues through the existing validation and revision rules. Historical
content without bindings remains compatible and no historical content or digest
is backfilled or recomputed.

## Bounded proof and open upstream capability

This increment proves execution and authorized readback for an already existing,
legal exact approved Plan. Its real HTTP acceptance provisions Workflow records
through the production domain service and PostgreSQL repository but uses a test
reference resolver. The ordinary Workflow API cannot yet publish the required Skill
reference path end to end. That authoring/resolver capability remains an M2 required
OPEN item; this decision does not authorize a frontend or management-module expansion.

Implementation and this addendum are reviewed together in the existing Draft PR.
Session remains open. Human acceptance, Ready transition, merge, deployment and
main durability are not granted by this record.

## Subsequent Human scope acceptance: single-host support

Checkpoint `SINGLE_HOST_SCOPE_ACCEPTED_AND_FINAL_REVIEW` records a subsequent
Human decision about the supported scope of this increment. IMPL-288 formally
supports governed execution and recovery only when one designated supervisor
starts the execution child on one host for one execution database. Within that
scope, non-overlapping child lifetimes, process-wide Invocation ownership,
supervisor-loss revocation, confirmed predecessor-child exit and recovery to
`OUTCOME_UNKNOWN` remain required implementation and acceptance constraints.

The previously identified cross-host gap remains an implementation fact, but is
no longer an acceptance blocker for this bounded increment. If independent hosts
connect to the same execution database and enable the governed entry, the current
host-local lock, database fingerprint and `EXIT_CONFIRMED` status cannot detect or
exclude the other host. Cross-host ownership, takeover coordination and provider
fencing remain unsupported and OPEN. This scope decision does not declare those
capabilities implemented, waive them for complete P1 or production readiness, or
assign them automatically to a release.

`OUTCOME_UNKNOWN` continues to mean only that the platform has no authoritative
terminal provider result. It does not establish provider termination,
cancellation, business failure or externally exactly-once execution, and recovery
must not redispatch the existing Invocation.

No deployment is authorized or inspected by this decision. Any demonstration or
deployment that relies on IMPL-288 must separately verify that only one execution
host enables this entry for the database. A future cross-host effort must enter
through a separately scoped Human-owned architecture and implementation decision;
this addendum does not preselect a lease, fencing or HA design.

The addendum status remains `HUMAN_ACCEPTED / BRANCH_RECORDED /
NOT_MAIN_DURABLE`. This scope acceptance does not itself accept the final code
candidate, make the PR Ready, authorize merge or deployment, or close the Session.
