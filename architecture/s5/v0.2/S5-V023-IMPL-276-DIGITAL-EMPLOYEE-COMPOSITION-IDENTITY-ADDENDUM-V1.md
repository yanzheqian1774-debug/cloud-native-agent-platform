# IMPL-276 — Digital Employee composition and identity increment

## Decision and implementation authority

Session: `S5-V023-IMPL-276`.
Source classification: `HUMAN_ACCEPTED_NEW_DECISION`.
Status: `HUMAN_ACCEPTED / BRANCH_RECORDED / NOT_MAIN_DURABLE`.

The Human explicitly authorizes recording this decision and implementing its
bounded backend prerequisite in the same branch. This is a new decision, not a
claim that ARCH-204 already specified these rules. It allocates no ARCH identifier
and changes no historical Session, Registry, public API, or CRD authority.

## Composition and eligibility

Publication requires exactly one primary Agent Definition reference. Workflow,
Skill, MCP and Knowledge may have multiple exact references. At most one default
Runtime Profile reference is permitted. Every direct executable member binds its
own resource kind, scoped identity, immutable revision and canonical digest.

Composition cardinality does not change ARCH-266's one managed slot per resource
class per Attempt. Workspace, model and policy are not new P1 authoritative
composition slots. Unverified direct references affecting execution cannot be
published as effective members. Descriptive metadata cannot authorize execution,
permission or matching. Agent-owned dependencies retain their original owner and
are not promoted to verified direct employee bindings.

Publication, matching, instantiation and execution require separate authorization
checks. Publication does not grant matching or execution. Approved/published
content remains immutable; composition changes require a successor revision and
new exact approval/publication. Retry preserves the original exact bindings.

## Related contracts and ownership

ARCH-018 defines resource-domain persistence, immutable revisions and append-only
lifecycle facts. ARCH-013 defines separate exact approval, publication and match
authorization. ARCH-019 and ARCH-204 separate Employee Definition, Instance,
Assignment, Plan, Run, Task Run, Attempt, Agent Instance and Placement. ARCH-208
owns Plan/approval and transactional Workflow Control. ARCH-266 owns later
Attempt Resource Use. None is replaced by a template projection or another
resource's identity.

Run retains its existing Assignment and exact approved Plan relationship; this
decision does not require moving Plan ownership into Assignment. The Execution
boundary validates the complete relationship before persistence or dispatch.

## Compatibility and bounded delivery

Historical Agent-derived employee records and Plan-derived placeholder records
remain unchanged and queryable under authorization. They are not relabelled,
backfilled on read, or admitted into new exact-lineage execution. New records must
be distinguishable from legacy records. Additive migration must not fail merely
because legacy rows lack new lineage.

The first deliverable is the independently verified backend identity chain:
Definition/revision/composition, approval/publication, Instance/Assignment,
approved Plan, start/Attempt/retry and exact Agent Placement reference. Resource
Use implementation follows that prerequisite; this increment does not claim
Resource Use, P1, release or production completion. No frontend, visual builder,
multi-Agent direct assembly, automatic migration or new public API is authorized.

## Acceptance mapping

- Distinct Agent, employee Definition and Plan IDs/revisions/digests prove identity
  separation through real PostgreSQL start/retry and readback.
- Exact member resolution, independent authorization and cross-scope denial prove
  eligibility and zero downstream effects on rejection.
- Immutable revisions, append-only decisions, CAS, replay conflicts and rollback
  prove persistence consistency; restart proves durable identity continuity.
- Unchanged historical records and explicit ineligibility prove compatibility.
- Placement resolves the primary Agent member rather than equating Agent and
  employee revisions. Successor Attempt retains the original composition.

Implementation and this decision are reviewed together in one Draft PR. Main
durability may be claimed only after Human-authorized integration. Session remains
open; merge and deployment are not authorized.
