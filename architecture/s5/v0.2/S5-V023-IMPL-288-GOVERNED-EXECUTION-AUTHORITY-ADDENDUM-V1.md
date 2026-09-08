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
