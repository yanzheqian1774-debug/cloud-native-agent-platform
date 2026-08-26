# S5-ARCH-009 — Product and Technical Graph Projection Scope Gate v1

## 1. Session and decision state

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-009` |
| Type / track | `ARCH` / `D — PRODUCT_AND_TECHNICAL_VIEWS` |
| Version | `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle | `REVIEW` |
| Status | `PASS_WITH_CONSTRAINTS` |
| Checkpoint | `A — PRODUCT_TECHNICAL_GRAPH_PROJECTION_SCOPE_CANDIDATE` |
| Result | `GRAPH_PROJECTION_SCOPE_CANDIDATE` |
| Authorized baseline | `9d057598bdaf233efc682430d0d6ea7579591ea8` |
| Graph Projection | `ARCHITECTURE_CANDIDATE / INTERNAL / UNFROZEN / NOT_IMPLEMENTED` |
| Product View / Technical View | `NOT_STARTED / NOT_STARTED` |
| Session closed | `NO` |
| Next action | `WAIT_FOR_HUMAN_S5_ARCH_009_GRAPH_PROJECTION_SCOPE_REVIEW_GATE` |

This candidate defines a replaceable internal projection boundary. It changes
no production execution, public API, CRD, schema, frozen Contract, dependency,
Task/Workflow semantics, Runtime support, or source-of-truth ownership. Human
acceptance is required before implementation.

## 2. Preflight, scope, and source review

Preflight established a clean isolated worktree, the exact expected branch,
and local `HEAD` plus refreshed `origin/main` at the authorized baseline. The
branch was not attached elsewhere, no remote branch or open PR owned this
Session, no open PR competed for the two authorized architecture paths, and
the writable scope resolved to this artifact plus `architecture/s5/v0.2/README.md`.

Read-only review covered the integrated Authoring Backend, immutable
`SharedExecutionView`, its Product/Technical projection functions and tests;
current Task/Workflow CRDs, graph validation, controllers, replay/skip/fan-in
behavior; the Core v0.2 Definition/Instance/Platform Execution Identity and
Runtime Binding values; the Native Provider, Capability Gateway decision and
Provider-call evidence, internal Outcome; synthetic Knowledge identities and
citations; S5-SPIKE-008; S5-IMPL-009's durable S5-REL-022 correction and
extensibility evidence; and accepted S5-ARCH-008 Operator-hosting constraints.

The review confirms:

- the shared DTO is `INTERNAL / VERSION_UNFROZEN / NOT_A_PUBLIC_CONTRACT`;
- it is one immutable execution record with two projections, not a canonical
  relationship graph, and it remains replaceable;
- Graph Projection, the Product View UI, and the Technical View UI are not
  implemented;
- current Workflow dependency authority is the validated Workflow DAG, while
  other relationships are bounded evidence/ref semantics; no competing
  general relationship authority exists;
- Kubernetes remains current public desired/observed-state authority;
- S5-ARCH-008 permits only bounded Operator-hosted MVS behavior and prohibits
  redefining identity, Task/Workflow semantics, Provider behavior, or public
  wire shape; and
- production execution behavior must remain byte-for-byte out of scope.

S5-REL-022 itself remained stopped and unmerged after discovering an approval
replay contradiction. The integrated C1 evidence corrects that contradiction
and preserves exact immutable approval evidence. This decision consumes only
that durable conclusion; it does not claim a REL artifact or implementation.

## 3. GP01 — canonical graph authority

There SHALL be exactly one canonical internal **Graph Projection snapshot**
for a projection input. It is the sole relationship source from which Product
and Technical visual projections are derived. A view may filter, group,
aggregate, label, and order the canonical graph; it MUST NOT independently
discover, reconstruct, invent, reverse, or persist relationships.

The graph is a read-only derived value. It is not a desired-state store, event
log, execution engine, workflow authority, Knowledge authority, or replacement
for Kubernetes. Upstream domain authorities retain ownership of their facts.
The graph records provenance and limitations when facts are unavailable.

## 4. GP02 — graph layers

| Layer | Meaning | Shape / authority |
| --- | --- | --- |
| Plan graph | authored topology for an immutable approved plan revision | directed graph; no execution-state mutation |
| Execution dependency graph | actual prerequisite ordering for one execution snapshot | **DAG required**; cycle is `EXECUTION_DEPENDENCY_CYCLE` and projection fails closed |
| Assignment graph | Task/step to Definition, Instance, Runtime, or Capability assignment | general directed graph |
| Data/evidence graph | input, output, citation, result, and evidence lineage | general directed graph; cycles allowed |
| Approval/decision graph | request, authorization, Human approval, blocking, and decision evidence | general directed graph; cycles allowed when historical feedback is explicit |
| Visual projection | view-specific filtering, grouping, and edge aggregation | derived only; never authoritative |

Only `DEPENDS_ON` relations participating in the current execution dependency
layer are subjected to DAG validation. Evidence, feedback, history, approval,
and compensation relations are not rejected merely because the complete
relationship graph contains a cycle.

## 5. GP03 — node model

Every canonical node has:

| Field | Rule |
| --- | --- |
| `node_id` | deterministic domain-separated projection ID; never an entity identity |
| `node_type` | closed candidate enum below |
| `entity_id` | exact upstream authoritative or explicitly synthetic identity |
| `label_key` | locale-neutral message key; display text is not graph truth |
| `phase` | one GP13 state; `UNKNOWN` retained |
| `progress` | optional normalized bounded value plus evidence/limitation; never inferred from layout |
| `execution_identity` | optional unchanged Platform Execution Identity; no native substitute |
| `group_id` | optional deterministic grouping ID; absent on ungrouped nodes |
| `summary` | bounded non-secret semantic summary or message key |
| `evidence_ids` | sorted, de-duplicated evidence references |
| `limitation_codes` | sorted stable codes for missing, synthetic, unsupported, or ambiguous evidence |

Node classification for v0.2:

| Node type | v0.2 disposition | Constraint |
| --- | --- | --- |
| `BUSINESS_PROBLEM` | Required | Product entry/projection only; no new persistent authority |
| `PLAN` | Required | exact immutable approved revision when execution-linked |
| `WORKFLOW` | Required | current Workflow identity/aggregate evidence |
| `TASK` | Required | plan step and execution occurrence remain distinguishable by evidence |
| `DEFINITION` | Required | separate from Instance and runtime |
| `INSTANCE` | Required | logical internal candidate; do not imply a CRD or multi-instance support |
| `RUNTIME_REALIZATION` | Required when observed; otherwise optional | native IDs correlation-only |
| `CAPABILITY` | Required when requested/authorized | authorization precedes invocation |
| `KNOWLEDGE` | Required when cited; otherwise optional | synthetic only in v0.2 |
| `APPROVAL` | Required when a Human or authorization gate exists | immutable decision evidence |
| `OUTCOME` | Required for execution terminality or ambiguity | internal, domain-specific, unfrozen |

No candidate node is authorization for a new public resource.

## 6. GP04–GP05 — relation model and cardinality

Every raw relation has `relation_id`, `source_node_id`, `target_node_id`, one
or more ordered `relation_types`, explicit `direction`, semantic `cardinality`,
`state`, sorted `evidence_ids`, integer `display_priority`, optional
`aggregation_key`, and `projection_visibility`. `projection_visibility` is a
policy value (`PRODUCT`, `TECHNICAL`, `BOTH`, or `DETAIL_ONLY`), not security
authorization. Security filtering occurs before projection and aggregation.

Candidate relation meanings:

| Relation | Minimum meaning |
| --- | --- |
| `CONTAINS` | structural inclusion without execution ordering |
| `DECOMPOSES_TO` | problem/plan decomposition |
| `DEPENDS_ON` | prerequisite; DAG-constrained only in execution dependency layer |
| `DATA_FLOW` | data/result movement with evidence lineage |
| `TRIGGERS` | an event or completion initiates another activity |
| `ASSIGNED_TO` | work assignment to Definition/Instance/group |
| `EXECUTED_BY` | occurrence realized by Instance/Runtime |
| `REQUESTS` | capability, approval, or retrieval request |
| `AUTHORIZED_BY` | machine authorization evidence |
| `PRODUCES` | Outcome or Evidence production |
| `REFERENCES` | non-owning immutable/correlation reference |
| `APPROVED_BY` | Human approval decision linkage |
| `BLOCKS` | blocking gate/failure semantics |
| `COMPENSATES` | explicit compensation path; never normal-path merge |

Cardinality is semantic metadata, not a count inferred from a snapshot:

| Cardinality | Required example | Rule |
| --- | --- | --- |
| `ONE_TO_ONE` | execution occurrence to its Platform Execution Identity context | snapshot may omit unavailable target only with limitation |
| `ONE_TO_MANY` | Definition to Instance; Runtime Realization to Execution | supports future multiplicity without claiming current support |
| `MANY_TO_ONE` | repeated Tasks assigned to one Instance | distinct raw relations retained |
| `MANY_TO_MANY` | Tasks to Capabilities/Evidence | join evidence and direction retained |

Declared cardinality travels with the relation semantic or its source
contract. Observing one node at runtime never narrows `ONE_TO_MANY` to
`ONE_TO_ONE`.

## 7. GP06–GP07 — deterministic edge aggregation

Relations may share one visual edge only when this tuple is equal:

`(source_node_id, target_node_id, direction, projection_context,
tenant_or_security_domain, path_class, temporal_class, blocking_class,
authorization_class)`.

Within an eligible group:

1. remove no raw relation and preserve every evidence ID;
2. order relation types by `(display_priority, relation-type rank, relation_id)`;
3. choose the first relation type as the primary label;
4. show the next two distinct types as secondary badges;
5. render `+N` for remaining distinct types (not relation instances);
6. expose all raw relations, states, evidence, cardinalities, and IDs in detail;
7. calculate the aggregation ID from the complete normalized member IDs; and
8. emit visual edges in `(source display order, target display order,
   aggregation_id)` order.

Fixed type rank is:
`BLOCKS`, `DEPENDS_ON`, `TRIGGERS`, `DATA_FLOW`, `ASSIGNED_TO`, `EXECUTED_BY`,
`REQUESTS`, `AUTHORIZED_BY`, `APPROVED_BY`, `PRODUCES`, `COMPENSATES`,
`DECOMPOSES_TO`, `CONTAINS`, `REFERENCES`.

Relations MUST NOT merge across direction; tenant/security domain; success and
failure paths; normal and compensation paths; current execution and historical
reference; blocking and informational semantics; or contradictory
authorization state. Missing classification fails closed to separate edges.

## 8. GP08 — grouping and expansion

Grouping is presentation-only and never discards raw graph members or evidence.
Deterministic group kinds cover Instances of one Definition, repeated Task
types, parallel branches, Evidence collections, Capability groups, Runtime
pools, and large fan-in/fan-out.

Defaults and limits:

| Policy | Candidate value |
| --- | --- |
| repeated homogeneous nodes collapse | `>= 4` siblings sharing group kind/authority |
| large fan-in/fan-out collapse | `> 8` incident visible edges at one node |
| initial edge-pressure collapse | `> 32` visual edges after ordinary aggregation |
| maximum initial visible nodes | `50` |
| group ID input | snapshot version, projection context, security domain, group kind, parent ID, sorted member node IDs |
| expansion | one deterministic group at a time; stable member/edge order |

If the 50-node budget is exceeded, choose groups by highest node reduction,
then group-kind rank, then group ID. The projection MUST expose member count,
hidden edge count, phase summary including UNKNOWN, all limitation codes, and
an evidence union. Expansion restores raw members and recomputes only affected
visual edges without changing canonical node/relation IDs.

## 9. GP09–GP10 — projection policies

Product View prioritizes, in order: Business Problem, approved Plan, business
Task/step, responsible Digital Employee role (Definition-facing), Instance
count, progress, Outcome, Citation, and Human Approval. It hides by default
Kubernetes UID, Provider-native IDs, raw Runtime Binding, retry/replay detail,
and raw diagnostics. Hidden evidence remains available only through an
authorized Technical/detail projection; it is never deleted or reinterpreted.

Technical View exposes Workflow, Task, Definition, Instance, Runtime
Realization, unchanged Platform Execution Identity, requested/effective
Runtime, Capability authorization, Provider calls, Outcome including UNKNOWN,
synthetic Knowledge evidence, and limitation/reason codes. It uses one edge
per eligible aggregation group and expands to the preserved raw relations.

Both views receive the same canonical snapshot ID and security-filtered graph.
Cross-view values for shared identity, phase, Outcome, authorization,
cardinality, and evidence MUST be equal; Product simplification may omit but
must not contradict Technical evidence.

## 10. GP11 — identity and determinism

IDs use SHA-256 over UTF-8 canonical JSON (`sort_keys=true`, compact separators,
Unicode NFC), prefixed by a versioned domain:

- `gps:v0.2-candidate:<digest>` for a snapshot from normalized authoritative
  input, approved plan revision, execution snapshot, policy version, and
  security-domain discriminator;
- `gpn:v0.2-candidate:<digest>` for `(snapshot_id, node_type, entity_id,
  occurrence_context)`;
- `gpr:v0.2-candidate:<digest>` for `(snapshot_id, layer, source_node_id,
  target_node_id, direction, sorted relation_types, cardinality, state,
  semantic_discriminator)`; and
- `gpa:v0.2-candidate:<digest>` for the GP06 key plus sorted raw relation IDs.

Map keys, nodes, relations, evidence IDs, limitations, and group members use
stable normalized ordering. Volatile collection order, locale, display
coordinates, and wall-clock render time are excluded. Identical normalized
input and policy MUST yield byte-equivalent canonical and view projections.

Platform Execution Identity remains the sole execution authority. Graph IDs
are projection identities only. Definition, Instance, Task, Workflow,
Capability, Knowledge, Approval, Outcome, and native identities remain in
separate domains. Kubernetes and Provider-native IDs are correlation-only and
never become Platform Execution Identity.

## 11. GP12–GP15 — temporal, Outcome, Runtime, Knowledge, Capability

The graph separates authored plan topology, exact approved immutable plan
revision, execution snapshot, current observed execution state, and historical
execution evidence. Every running or historical execution references the
approved plan revision that produced it. Editing or approving a later plan
creates a new revision and never rewrites the earlier execution link.

Canonical phases are `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `DENIED`,
`SKIPPED`, `BLOCKED`, and `UNKNOWN`. Mapping from upstream vocabularies is
explicit and versioned. `UNKNOWN` means evidence cannot establish success or
failure; it is never counted, colored, grouped, or labelled as either.
Skipped downstream work remains distinct from the failed blocker.

The model permits future Definition `1:N` Platform Instance, Platform Instance
`N:M` Runtime Realization, and Runtime Realization `1:N` Execution mappings.
These are cardinality semantics, not current support claims. v0.2 does not
claim Native, OpenClaw, or Hermes multi-instance support. Native remains a
bounded component-tested candidate and not certified; OpenClaw support is not
granted without live exact-profile evidence; Hermes remains experimental and
not currently certifiable.

Capability and Knowledge relations preserve authorization-before-invocation or
retrieval. `DENY` requires zero Provider calls and no produced citations.
Citations reference exact Evidence IDs. Knowledge nodes are deterministic
synthetic v0.2 projection nodes only; they do not claim production retrieval,
RAG, Knowledge persistence, governance, or authority. Provider calls and
native IDs remain evidence/correlation, never relationship authority.

## 12. GP16 — versioning and freeze

The entire boundary is `INTERNAL / UNFROZEN / REPLACEABLE /
VERSIONED_CANDIDATE`. The candidate version identifies normalization and
projection policy, not a public compatibility promise. No public Graph API,
CRD, schema, Contract, persistence representation, library choice, or freeze
is granted. Any public exposure, production persistence, execution behavior
change, or competing relationship authority requires a new Human G2 decision.

## 13. Deterministic visual fixtures

Fixture notation uses `N/R/E` for raw node, raw relation, and aggregated visual
edge counts. `P` and `T` list Product/Technical visible node and edge counts.
All fixtures sort nodes by `(node-type rank, entity_id, node_id)`, relations by
`(source_node_id, target_node_id, direction, display_priority, relation_id)`,
and evidence lexicographically. Counts describe the fixture after its stated
projection security filter and before detail expansion.

| # | Fixture and raw graph | Aggregation / view expectation | Cardinality and evidence |
| --- | --- | --- | --- |
| 1 | Serial: problem, plan, workflow, tasks A/B/C, definition, instance, runtime, outcome; `N10/R12` | no multi-relation collapse; `E12`; `P7/6`, `T8/10` | A→B→C `ONE_TO_ONE` occurrence dependencies; Outcome evidence on `PRODUCES` |
| 2 | Parallel: workflow, A, B/C, D plus definition/instance/outcome; `N8/R10` | fan-out/fan-in remain explicit; `E10`; `P6/6`, `T8/10` | A `ONE_TO_MANY` B/C; B/C `MANY_TO_ONE` D; DAG topological order A,B,C,D |
| 3 | Definition with Instances I1/I2/I3 and runtime; `N5/R7` | three Instances remain visible (<4 threshold); `E7`; `P2/1` (Definition role + count), `T5/7` | declared Definition→Instance `ONE_TO_MANY`; selection evidence per assignment |
| 4 | Tasks T1/T2/T3 to Instance I1; `N4/R3` | repeated Tasks remain distinct; `E3`; `P4/3`, `T4/3` | Task→Instance `MANY_TO_ONE`; each assignment evidence retained |
| 5 | T1/T2, Cap C1/C2, Evidence K1/K2; `N6/R8` | no pair has mergeable duplicate here; `E8`; `P4/4`, `T6/8` | Task↔Capability/Evidence `MANY_TO_MANY`; citation Evidence IDs sorted |
| 6 | Nodes A/B with dependency, data, trigger relations; `N2/R3` | one visual edge: primary `DEPENDS_ON`, badges `TRIGGERS`,`DATA_FLOW`; `E1`; `P2/1`, `T2/1` | three semantic cardinalities preserved in expanded raw detail and evidence union |
| 7 | Task, Capability, Approval/decision, Outcome denied; `N4/R4` | `REQUESTS`, `AUTHORIZED_BY`, `BLOCKS`, `PRODUCES`; `E4`; `P3/3`, `T4/4` | `DENY`, Provider calls `0`, citations `0`; decision evidence linked |
| 8 | Plan, approval, task, Human actor/role evidence; `N3/R3` | approval gate blocks until approved, then state changes without edge identity change; `E3`; `P3/3`, `T3/3` | `REQUESTS` + `APPROVED_BY`; immutable actor/time/revision evidence |
| 9 | A failed, B skipped downstream, Outcome; `N4/R4` | failure and skip are distinct; blocking edge cannot merge with informational dependency; `E4`; `P4/4`, `T4/4` | A→B dependency plus blocking semantics in separate groups; failure evidence only on A |
| 10 | Task, runtime realization, UNKNOWN Outcome; `N3/R2` | `E2`; `P2/1`, `T3/2`; UNKNOWN styling/count remains separate | execution→Outcome `ONE_TO_ONE`; ambiguity/reason evidence retained; never success/failure |
| 11 | Definition with 12 Instances and assignments; `N13/R24` | one default Instance group; `E2` summary edges; `P2/1`, `T2/2`; expansion restores `N13/R24/E24` | Definition `ONE_TO_MANY`; group exposes count 12 and union of all 12 evidence IDs |
| 12 | Same canonical serial graph as #1 | same snapshot ID; Product `P7/6`, Technical `T8/10`; every shared identity/state/evidence value equal | omissions only; no view-local relation creation; stable byte-equivalent output |

Fixture implementations MUST name every node and raw relation explicitly,
assert the counts above, assert the exact sorted ID sequences, test reversed
input order, and test at least one non-mergeable discriminator for fixtures 6,
7, and 9. Counts are architecture acceptance data, not production fixtures in
this documentation-only Session.

## 14. Acceptance proof and contradiction audit

| Required proof | Candidate disposition |
| --- | --- |
| one relationship authority | GP01: one canonical graph; views cannot reconstruct |
| four cardinalities | GP05 matrix and fixtures 2–5 |
| multiple relations per pair | GP06 and fixture 6 |
| deterministic aggregation / safety | GP06–GP07, fixtures 6/9 |
| grouping and progressive expansion | GP08 and fixture 11 |
| Product/Technical consistency | GP09–GP10 and fixture 12 |
| execution DAG plus general graph | GP02 and fixtures 2/8 |
| identity authority | GP11; no new execution identity |
| plan/execution revision linkage | GP12 |
| UNKNOWN preservation | GP13 and fixture 10 |
| Runtime claims unchanged | GP14 |
| Knowledge/Capability invariants | GP15 and fixtures 5/7 |
| no production/public change | architecture artifact and index only |

No contradiction was found with accepted S5-ARCH-008, the accepted logical
Core candidate, the internal shared DTO, current Workflow DAG behavior, or
Platform Execution Identity. This candidate adds no competing authority: it
derives relationships from those sources and fails closed on conflict.

## 15. Limitations and claim boundaries

- No graph builder, validator, serializer, API, UI, graph library, storage, or
  performance evidence is implemented.
- Thresholds and enum vocabularies are internal candidate policy and may change
  before implementation or public exposure.
- Tenancy/security discriminators prevent unsafe aggregation but do not create
  v0.2 multi-tenancy or authorization.
- Progress normalization and historical retention remain implementation-gate
  decisions; missing evidence requires limitation codes.
- Product and Technical view usability, accessibility, localization, scale,
  and production readiness are unproven.
- The fixture counts specify the next implementation's acceptance surface;
  they are not evidence that Graph Projection exists today.

## 16. Implementation handoff, rollback, and gate

A separately authorized implementation may introduce a pure internal graph
model/builder and deterministic fixtures, then adapt the existing shared DTO as
one input. It must preserve upstream authority, import direction, Controller
behavior, public wire shapes, Runtime/Capability/Knowledge constraints, and
the exact projection equality rules here. Public transport/UI exposure,
persistence, schema, dependencies, and production integration require their
own scopes and gates.

Rollback for this architecture Session is removal of this artifact and its one
index entry. There is no data migration, execution rollback, dependency
cleanup, or public compatibility action.

```text
SESSION: S5-ARCH-009
CODEX_TASK_NAME: [S5-ARCH-009] Product and Technical Graph Projection Scope Gate
LIFECYCLE: REVIEW
STATUS: PASS_WITH_CONSTRAINTS
CHECKPOINT: A — PRODUCT_TECHNICAL_GRAPH_PROJECTION_SCOPE_CANDIDATE
RESULT: GRAPH_PROJECTION_SCOPE_CANDIDATE
CURRENT_STEP: 1_OF_4
GRAPH_PROJECTION: ARCHITECTURE_CANDIDATE / INTERNAL / UNFROZEN / NOT_IMPLEMENTED
PRODUCT_VIEW: NOT_STARTED
TECHNICAL_VIEW: NOT_STARTED
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_S5_ARCH_009_GRAPH_PROJECTION_SCOPE_REVIEW_GATE
NEXT_GATE: Human S5-ARCH-009 Graph Projection Scope Review Gate
```
