# S5-ARCH-009 — Product and Technical Graph Projection Scope Gate v1

## 1. Session and decision state

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-009` |
| Type / track | `ARCH` / `D — PRODUCT_AND_TECHNICAL_VIEWS` |
| Version | `v0.2 CONNECT — Digital Employee Technical Preview` |
| Lifecycle | `CLOSING` |
| Status | `PASS_WITH_CONSTRAINTS` |
| Checkpoint | `B — GRAPH_PROJECTION_DECISION_CONVERGENCE_AND_EXIT` |
| Result | `READY_TO_CLOSE` |
| Authorized baseline | `9d057598bdaf233efc682430d0d6ea7579591ea8` |
| Checkpoint A head | `1a020927aa7c357b04a7127c864a31e27b4ba8b1` |
| Source PR | `#61 / OPEN / DRAFT / UNMERGED` |
| Human review | `PASS_WITH_CONSTRAINTS` |
| Graph Projection | `ARCHITECTURE_COMPLETE / INTERNAL / UNFROZEN / NOT_IMPLEMENTED` |
| Product View / Technical View | `NOT_STARTED / NOT_STARTED` |
| Session closed | `NO` |
| Next action | `WAIT_FOR_HUMAN_S5_ARCH_009_CLOSE_CONFIRMATION` |

This candidate defines a replaceable internal projection boundary. It changes
no production execution, public API, CRD, schema, frozen Contract, dependency,
Task/Workflow semantics, Runtime support, or source-of-truth ownership. Human
Close Confirmation is required before Session closure or implementation.

### 1.1 Correction provenance

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-009-C1` |
| Title | `Human Approval Fixture Direction Correction` |
| Source Session | `S5-ARCH-009 — CLOSED / NOT_REOPENED` |
| Discovered by | `S5-REL-023 CHECKPOINT A` |
| Source head before correction | `a1c77cc7ff23424f09c0438c4dd720be9182f5b5` |
| Correction scope | `HUMAN APPROVAL FIXTURE BLOCKS DIRECTION AND RELATED INTERNAL CONSISTENCY` |
| S5-REL-023 state | `STOPPED / UNMODIFIED / UNMERGED` |
| Final delivery head | `RESOLVED_BY_EXACT_GIT_PR_AND_CI_PROVENANCE` |
| Self-referential head | `NOT_REQUIRED` |
| Recursive correction | `NO` |

This correction uses the accepted non-self-referential head rule. It does not
reopen S5-ARCH-009, resume S5-REL-023, or create a successor to record its own
commit SHA.

### 1.2 Cardinality completeness correction provenance

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-009-C2` |
| Title | `Graph Fixture Cardinality Completeness Correction` |
| Discovered by | `S5-REL-023 CHECKPOINT A RESUMED REVIEW` |
| Source head before correction | `66ca642778a2800883cbf77c7cf67eb2a9ade5bd` |
| Source sessions | `S5-ARCH-009 CLOSED`; `S5-ARCH-009-C1 CLOSED` |
| Correction scope | `COMPLETE CARDINALITY CONTRACT FOR ALL 12 DETERMINISTIC FIXTURES` |
| S5-REL-023 state | `STOPPED / UNMODIFIED / UNMERGED` |
| Final delivery head | `RESOLVED_BY_EXACT_GIT_PR_AND_CI` |
| Self-referential head | `NOT_REQUIRED` |
| Recursive correction | `NO` |

This C2 correction preserves the complete C1 provenance and corrected
`BLOCKS` direction. It changes no graph architecture, relation meaning,
execution behavior, public model, schema, or implementation scope.

## 2. Preflight, scope, and source review

Preflight established a clean isolated worktree, the exact expected branch,
and local `HEAD` plus refreshed `origin/main` at the authorized baseline. The
branch was not attached elsewhere, no remote branch or open PR owned this
Session, no open PR competed for the two authorized architecture paths, and
the writable scope resolved to this artifact plus `architecture/s5/v0.2/README.md`.

Checkpoint B reused that exact task, branch, worktree, and Draft PR #61.
Before correction, local, remote, and PR heads all equalled Checkpoint A head
`1a020927aa7c357b04a7127c864a31e27b4ba8b1`; refreshed `origin/main` still
equalled the authorized baseline; the PR was `OPEN / DRAFT / CLEAN / MERGEABLE
/ UNMERGED`; worktree and index were clean; the baseline diff contained
exactly the same two authorized paths; and no competing open PR, branch, or
worktree owned the Session or paths.

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
| `BLOCKS` | directed blocking gate/failure semantics: `source_node_id` is the blocking prerequisite or blocker, `target_node_id` is the blocked node, and the target cannot proceed while the source remains unsatisfied |
| `COMPENSATES` | explicit compensation path; never normal-path merge |

`declared_cardinality` is semantic metadata for a relation in its defined
context. `observed_source_count` and `observed_target_count` are the distinct
participating endpoint counts in one deterministic fixture. Observed fixture
multiplicity is evidence, not a rule for narrowing the declaration. Every raw
relation MUST carry exactly one of the four canonical values below; prose,
endpoint counts, grouping, aggregation, or a view-local inference is not a
cardinality value.

| Cardinality | Required example | Rule |
| --- | --- | --- |
| `ONE_TO_ONE` | execution occurrence to its Platform Execution Identity context | snapshot may omit unavailable target only with limitation |
| `ONE_TO_MANY` | Definition to Instance; Runtime Realization to Execution | supports future multiplicity without claiming current support |
| `MANY_TO_ONE` | repeated Tasks assigned to one Instance | distinct raw relations retained |
| `MANY_TO_MANY` | Tasks to Capabilities/Evidence | join evidence and direction retained |

Declared cardinality travels with the relation semantic or its source
contract. Observing one node at runtime never narrows `ONE_TO_MANY` to
`ONE_TO_ONE`.

The model explicitly does **not** assume one Task has one Agent, one Instance
handles one Task, one Task has one upstream dependency, one Evidence item
belongs to one Task, or one Runtime Realization corresponds to one Platform
Instance. Those cases are covered by assignment multiplicity, `MANY_TO_ONE`,
fan-in, `MANY_TO_MANY`, and future Instance/Realization `N:M` respectively.

## 7. GP06–GP07 — deterministic edge aggregation

Relations may share one visual edge only when this tuple is equal:

`(source_node_id, target_node_id, direction, projection_context,
tenant_or_security_domain, execution_or_historical_context, path_class,
blocking_class, authorization_class, evidence_authority_class)`.

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
Relations with materially different evidence authority also MUST NOT merge,
even when their Evidence IDs happen to be equal.

Aggregation never declares a replacement semantic cardinality. An aggregated
edge exposes the deterministically sorted set of its members'
`declared_cardinality` values and the ordered raw `relation_id` members. A
single-value set is a visual summary only; a multi-value set MUST remain a set
and MUST NOT be collapsed to a false label. Expansion restores every raw
relation with its original direction, cardinality, evidence, and visibility.

For `BLOCKS`, direction is always source to target:
`blocking prerequisite -- BLOCKS --> blocked node`. The relation is not
automatically equivalent to `DATA_FLOW` or `TRIGGERS`. Product aggregation may
simplify its label, but it must preserve the raw source and target direction;
Technical projection must expose the raw `BLOCKS` relation. `BLOCKS` may share
a node pair with another relation only when direction and safety semantics are
compatible, and it must never merge with an opposite-direction relation or be
hidden by `DATA_FLOW` or `TRIGGERS`.

## 8. GP08 — grouping and expansion

Grouping is presentation-only and never discards raw graph members or evidence.
Deterministic group kinds cover Instances of one Definition, repeated Task
types, parallel branches, Evidence collections, Capability groups, Runtime
pools, and large fan-in/fan-out.

A Group is not an execution entity and cannot become a relation endpoint in
the canonical raw graph. Collapsing Definition/Instance families preserves
`ONE_TO_MANY`; fan-in preserves `MANY_TO_ONE`; shared Capability/Evidence
families preserve `MANY_TO_MANY`. Group summaries expose the sorted underlying
cardinality set, while expansion restores the exact raw relations. No group,
threshold, or view policy changes or reverses a raw cardinality.

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

The numeric thresholds are `IMPLEMENTATION_CONFIGURATION_CANDIDATES`, not
frozen Contract values. Product defaults to the strongest permitted collapse
needed to remain within both budgets. Technical defaults to one less-dense
level (expand the highest-priority Product group) when that remains within the
same budgets; otherwise it retains grouping and exposes raw membership through
detail expansion. Neither policy changes the canonical graph.

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

Runtime scope is exact:

| Capability | v0.2 state |
| --- | --- |
| Native multi-instance support | `NOT_GRANTED` |
| OpenClaw multi-instance support | `NOT_GRANTED` |
| Hermes multi-instance support | `NOT_GRANTED` |
| Runtime Pool | `NOT_IMPLEMENTED` |
| autoscaling | `NOT_IMPLEMENTED` |
| Runtime Realization cardinality | `FUTURE_MODEL_EXTENSIBILITY_ONLY` |

No `N:M` relation or Runtime grouping fixture may be presented as current
product availability, lifecycle behavior, scheduling, or support.

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

### 12.1 GP01–GP16 Human convergence ledger

Each row is binding for the internal v0.2 candidate. “Deferred” content is not
authorized by this decision.

| GP | Decision and rationale | Accepted constraints | v0.2 requirement | Deferred scope | Implementation consequence | Test/fixture consequence | Human disposition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GP01 | One canonical read-only graph is the sole relationship authority so views cannot diverge. | Upstream facts retain authority; no persistence or execution writes. | One builder result feeds both projections. | Public/persistent graph. | Provide one pure construction boundary; prohibit view-local discovery. | Cross-view raw relationship-ID equality. | `ACCEPTED` |
| GP02 | Separate plan, execution dependency, assignment, data/evidence, approval/decision, and visual layers because only execution ordering requires acyclicity. | Execution dependencies form a DAG; cycles elsewhere do not invalidate it. | Validate the dependency subgraph independently. | General process engine or workflow semantic change. | Layer-tag every relation and run scoped DAG validation. | Accept evidence/reference cycles; reject execution dependency cycles. | `ACCEPTED_WITH_CONSTRAINTS` |
| GP03 | Use the minimum typed Node value in Section 5 to preserve identity, state, evidence, and limitations. | Internal, bounded, secret-safe, domain-separated; dispositions remain as classified. | Required node types appear only when supported by source evidence. | Public node schema and new lifecycle resources. | Immutable internal Node model. | Required/optional presence, malformed values, ordering, UNKNOWN. | `ACCEPTED_FOR_INTERNAL_V0_2_CANDIDATE` |
| GP04 | Use the minimum typed Relation value in Section 6 so raw semantics survive presentation. | Direction, cardinality, state, evidence, priority, aggregation, and visibility are explicit. | Preserve every raw relation. | Public relation contract/storage representation. | Immutable internal Relation model with stable enum handling. | Direction, visibility, evidence, and unsupported-type failure tests. | `ACCEPTED_FOR_INTERNAL_V0_2_CANDIDATE` |
| GP05 | Support all four semantic cardinalities because observed counts do not define domain multiplicity. | Never infer narrower cardinality from one snapshot. | `ONE_TO_ONE`, `ONE_TO_MANY`, `MANY_TO_ONE`, `MANY_TO_MANY`. | Runtime lifecycle realization of future multiplicities. | Cardinality is construction input/declared metadata. | Fixtures 2–5 and anti-assumption assertions. | `ACCEPTED` |
| GP06 | Aggregate eligible same-pair relations deterministically to reduce visual noise without losing meaning. | GP06 key includes projection/security/temporal/path/authority context; raw relations and evidence remain expandable. | Primary label, ordered badges, `+N`, stable group ID. | UI interaction design and frozen label counts. | Pure aggregation after security filtering. | Reversed-input byte equality and fixture 6 exact membership. | `ACCEPTED_WITH_CONSTRAINTS` |
| GP07 | Keep safety-significant relations separate because visual merging could misstate control or history. | All Section 7 discriminators, including materially different evidence authority, fail closed to separate edges. | No unsafe cross-boundary merge. | Policy-driven semantic equivalence beyond the accepted key. | Validate discriminator completeness before aggregation. | Fixtures 6/7/9 plus one case per non-mergeable discriminator. | `ACCEPTED` |
| GP08 | Deterministically group bounded complexity while preserving complete drill-down evidence. | Thresholds are implementation configuration candidates; Product is denser than Technical where budgets allow. | Seven group kinds, 50-node/32-edge candidate budgets, stable expansion. | Production scale tuning and Runtime Pool implementation. | Pure view grouping over canonical members. | Fixture 11 collapsed/expanded counts and evidence union. | `ACCEPTED_FOR_BOUNDED_V0_2_VIEW` |
| GP09 | Product projection emphasizes business intent, work, responsibility, progress, Outcome, citations, and approvals. | Technical/native/diagnostic detail hidden by default, never contradicted or deleted. | Product filter/group policy over the canonical graph. | Final Product UI/UX and authoring. | No Product-local graph builder. | Product counts and shared-value equality in all fixtures. | `ACCEPTED` |
| GP10 | Technical projection exposes identities, runtime, authorization, calls, Outcome, evidence, and limitations. | One visual edge per eligible group with raw expansion. | Technical filter/group policy over the same graph. | Final Technical UI and observability product. | No Technical-local graph builder. | Technical counts, aggregation membership, and drill-down equality. | `ACCEPTED` |
| GP11 | Deterministic domain-separated projection IDs preserve reproducibility without competing with Platform identity. | Platform Execution Identity authoritative; native IDs correlation-only; canonical normalized ordering. | Byte-equivalent output for identical normalized input/policy. | Public ID compatibility guarantee. | Versioned SHA-256 ID construction as candidate algorithm. | Input permutation, domain collision, native-ID substitution rejection. | `ACCEPTED` |
| GP12 | Separate authored topology, approved revision, execution snapshot, current state, and history to prevent retroactive rewrite. | Running/historical execution retains exact immutable approved revision. | Explicit revision reference on execution context. | Plan persistence/version API. | Builder consumes revision identity; never derives “latest.” | Later approval cannot change prior execution linkage. | `ACCEPTED` |
| GP13 | Preserve eight explicit states because ambiguity and control outcomes are not binary. | UNKNOWN never maps to success/failure; skipped differs from failed/blocked/denied. | Versioned upstream-state mapping. | Universal public Outcome/Status contract. | Fail closed on unmapped state or emit UNKNOWN with limitation where authorized. | Fixtures 7, 9, and 10 exact state assertions. | `ACCEPTED` |
| GP14 | Model future Definition `1:N` Instance, Instance `N:M` Realization, and Realization `1:N` Execution without claiming support. | Native/OpenClaw/Hermes multi-instance not granted; Runtime Pool/autoscaling not implemented. | Cardinality metadata only. | Multi-instance lifecycle, Runtime Pool, autoscaling, scheduling. | No Runtime behavior or resource changes. | Future-shape fixture only; support-claim audit must remain negative. | `ACCEPTED_AS_FUTURE_EXTENSIBILITY_ONLY` |
| GP15 | Preserve authorization-first Capability/Knowledge evidence so a view cannot invent effects or citations. | DENY means zero calls/citations; Knowledge synthetic only; Evidence IDs exact. | Synthetic nodes and citation linkage when evidence exists. | Production Knowledge, RAG, governance, Provider certification. | Consume existing evidence; perform no retrieval/invocation. | Fixture 5 N:N evidence and fixture 7 DENY-zero-call rejection cases. | `ACCEPTED_WITH_SYNTHETIC_V0_2_BOUNDARY` |
| GP16 | Keep Graph Projection versioned, internal, unfrozen, and replaceable because implementation/public compatibility is unproven. | No API, CRD, schema, Contract freeze, persistence, or library grant. | Candidate policy version is explicit. | Any public or frozen surface. | Implementation stays behind an internal boundary and separate gate. | Compatibility tests are internal only; public-surface audit remains empty. | `ACCEPTED` |

### 12.2 Mandatory architecture and cardinality invariants

The Human review confirms as non-negotiable: one canonical relationship
authority; Product and Technical views as projections rather than builders;
execution dependency DAG validation independent of the general directed
relation graph; cycle tolerance outside that DAG; read-only projection;
distinct plan topology, approved revision, execution snapshot, current state,
and history; immutable approved-plan linkage for running executions; unchanged
Platform Execution Identity authority; graph/node/relation/group IDs that
cannot act as execution identities; correlation-only native/Provider IDs; and
explicit UNKNOWN without success/failure coercion.

All four cardinalities are required. The five forbidden one-to-one assumptions
listed in Section 6 are test obligations, not merely documentation guidance.

## 13. Deterministic visual fixtures

Fixture notation uses `N/R/E` for raw node, raw relation, and aggregated visual
edge counts. `P` and `T` list Product/Technical visible node and edge counts.
All fixtures sort nodes by `(node-type rank, entity_id, node_id)`, relations by
`(source_node_id, target_node_id, direction, display_priority,
declared_cardinality, relation_id)`, and evidence lexicographically. Counts
describe the fixture after its stated projection security filter and before
detail expansion. Cardinality is therefore an explicit deterministic sort
input as well as part of the canonical `gpr` identity input in GP11.

| # | Fixture and raw graph | Aggregation / view expectation | Cardinality and evidence |
| --- | --- | --- | --- |
| 1 | Serial: problem, plan, workflow, tasks A/B/C, definition, instance, runtime, outcome; `N10/R12` | no multi-relation collapse; `E12`; `P7/6`, `T8/10` | A→B→C `ONE_TO_ONE` occurrence dependencies; Outcome evidence on `PRODUCES` |
| 2 | Parallel: workflow, A, B/C, D plus definition/instance/outcome; `N8/R11` | fan-out/fan-in remain explicit; `E11`; `P6/6`, `T8/11` | exact Section 13.2 mapping preserves fan-out and fan-in declarations independently; DAG topological order A,B,C,D |
| 3 | Definition with Instances I1/I2/I3 and runtime; `N5/R7` | three Instances remain visible (<4 threshold); `E7`; `P2/1` (Definition role + count), `T5/7` | declared Definition→Instance `ONE_TO_MANY`; selection evidence per assignment |
| 4 | Tasks T1/T2/T3 to Instance I1; `N4/R3` | repeated Tasks remain distinct; `E3`; `P4/3`, `T4/3` | Task→Instance `MANY_TO_ONE`; each assignment evidence retained |
| 5 | T1/T2, Cap C1/C2, Evidence K1/K2; `N6/R8` | no pair has mergeable duplicate here; `E8`; `P4/4`, `T6/8` | Task↔Capability/Evidence `MANY_TO_MANY`; citation Evidence IDs sorted |
| 6 | Nodes A/B with dependency, data, trigger relations; `N2/R3` | one visual edge: primary `DEPENDS_ON`, badges `TRIGGERS`,`DATA_FLOW`; `E1`; `P2/1`, `T2/1` | exact mapping in Section 13.2: `ONE_TO_ONE`, `ONE_TO_MANY`, and `MANY_TO_MANY` remain distinct in expanded raw detail and evidence union |
| 7 | Task, Capability, Approval/decision, Outcome denied; `N4/R4` | `REQUESTS`, `AUTHORIZED_BY`, `BLOCKS`, `PRODUCES`; `E4`; `P3/3`, `T4/4` | `DENY`, Provider calls `0`, citations `0`; decision evidence linked |
| 8 | Plan, approval, task, Human actor/role evidence; `N3/R3` | approval prerequisite blocks the task until approved (`approval-BLOCKS->task`), then state changes without edge identity change; Product and Technical preserve that direction; `E3`; `P3/3`, `T3/3` | `REQUESTS` + `APPROVED_BY`; immutable actor/time/revision evidence remains linked to the approval relation |
| 9 | A failed, B skipped downstream, Outcome; `N4/R5` | failure and skip are distinct; blocking edge cannot merge with informational dependency; `E5`; `P4/5`, `T4/5` | `B-DEPENDS_ON->A` and `A-BLOCKS->B` preserve their distinct direction and cardinality in separate groups; failure evidence only on A |
| 10 | Task, runtime realization, UNKNOWN Outcome; `N3/R2` | `E2`; `P2/1`, `T3/2`; UNKNOWN styling/count remains separate | execution→Outcome `ONE_TO_ONE`; ambiguity/reason evidence retained; never success/failure |
| 11 | Definition with 12 Instances and assignments; `N13/R24` | one default Instance group; `E2` summary edges; `P2/1`, `T2/2`; expansion restores `N13/R24/E24` | Definition `ONE_TO_MANY`; group exposes count 12 and union of all 12 evidence IDs |
| 12 | Same canonical serial graph as #1 | same snapshot ID; Product `P7/6`, Technical `T8/10`; every shared identity/state/evidence value equal | omissions only; no view-local relation creation; stable byte-equivalent output |

### 13.1 Fixture completeness review

Relation notation is `source-TYPE->target`; indexed expressions expand in
ascending numeric order and therefore define every raw member. `ev-*` values
are exact fixture Evidence IDs. After ID construction, every fixture applies
the common stable ordering stated above; expected sequences are the ascending
tuples produced by that rule, not input order.

| # | Exact raw nodes | Exact raw relations | Evidence linkage and rejection expectation |
| --- | --- | --- | --- |
| 1 | `problem,plan,workflow,A,B,C,definition,instance,runtime,outcome` | `problem-DECOMPOSES_TO->plan`; `workflow-CONTAINS->{A,B,C}`; `B-DEPENDS_ON->A`; `C-DEPENDS_ON->B`; `{A,B,C}-ASSIGNED_TO->definition`; `definition-CONTAINS->instance`; `instance-EXECUTED_BY->runtime`; `C-PRODUCES->outcome` = 12 | `ev-plan`, `ev-dep-ab`, `ev-dep-bc`, `ev-outcome`; accept; Product/Technical counts and order as row 1 |
| 2 | `workflow,A,B,C,D,definition,instance,outcome` | `workflow-CONTAINS->{A,B,C,D}`; `{B,C}-DEPENDS_ON->A`; `D-DEPENDS_ON->{B,C}`; `{A,D}-ASSIGNED_TO->instance`; `D-PRODUCES->outcome` = 11 | one `ev-dep-*` per DAG edge; accept topological tie-break `B,C`; adding `A-DEPENDS_ON->D` rejects `EXECUTION_DEPENDENCY_CYCLE` without rejecting unrelated relation cycles |
| 3 | `definition,I1,I2,I3,runtime` | `definition-CONTAINS->{I1,I2,I3}`; `{I1,I2,I3}-REFERENCES->definition`; `I1-EXECUTED_BY->runtime` = 7 | `ev-select-i1..i3`; declared `ONE_TO_MANY`; accept and retain all Instance identities |
| 4 | `T1,T2,T3,I1` | `{T1,T2,T3}-ASSIGNED_TO->I1` = 3 | `ev-assignment-t1..t3`; `MANY_TO_ONE`; accept; duplicate relation ID rejects |
| 5 | `T1,T2,C1,C2,K1,K2` | `{T1,T2}-REQUESTS->{C1,C2}` and `{T1,T2}-REFERENCES->{K1,K2}` = 8 | `ev-cap-t1-c1..t2-c2`, `ev-knowledge-t1-k1..t2-k2`; `MANY_TO_MANY`; missing citation Evidence ID rejects malformed evidence |
| 6 | `A,B` | `A-DEPENDS_ON->B`; `A-DATA_FLOW->B`; `A-TRIGGERS->B` = 3 | `ev-dependency`, `ev-data`, `ev-trigger`; accept as one edge only when the complete GP06 key matches; differing direction/security/history/evidence authority must yield separate edges |
| 7 | `task,capability,approval,outcome` | `task-REQUESTS->capability`; `capability-AUTHORIZED_BY->approval`; `approval-BLOCKS->task`; `task-PRODUCES->outcome` = 4 | `ev-deny`; `DENY`, calls `0`, citations `0`; any call or citation rejects `DENY_REQUIRES_ZERO_PROVIDER_EFFECTS` |
| 8 | `plan,approval,task` | `plan-REQUESTS->approval`; `approval-BLOCKS->task`; `plan-APPROVED_BY->approval` = 3 | `ev-actor`, `ev-decided-at`, `ev-plan-revision` remain attached to `plan-APPROVED_BY->approval`; the corrected source/target tuple produces the canonical `gpr` relation ID and its deterministic sorted position; Product and Technical preserve `approval-BLOCKS->task`; accept exact immutable approval replay; contradictory authorization state does not merge and conflicting replay rejects |
| 9 | `A,B,workflow,outcome` | `workflow-CONTAINS->{A,B}`; `B-DEPENDS_ON->A`; `A-BLOCKS->B`; `A-PRODUCES->outcome` = 5 | `ev-failure-a`, `ev-skip-b`; accept `A=FAILED`, `B=SKIPPED`; reject any projection that maps B to FAILED or merges blocking with informational semantics |
| 10 | `task,runtime,outcome` | `task-EXECUTED_BY->runtime`; `task-PRODUCES->outcome` = 2 | `ev-ambiguous-effect`; accept `UNKNOWN`; reject success/failure coercion or retry-safe inference |
| 11 | `definition,I01..I12` | `definition-CONTAINS->{I01..I12}` and `{I01..I12}-REFERENCES->definition` = 24 | `ev-instance-01..12`; accept one default group and exact evidence union; expansion order `I01..I12`; missing member evidence is preserved as a limitation, never silently dropped |
| 12 | exactly fixture 1 canonical nodes | exactly fixture 1 canonical relations and IDs | same `ev-*`, snapshot ID, Platform Execution Identity, and raw relationship IDs; reject either view creating, reversing, or changing a shared relation |

For every row, the raw and aggregated counts, Product/Technical visible
node/edge counts, cardinality, and aggregation outcome are those in the main
fixture table. The two tables form one fixture contract. Component tests MUST
assert both tables, the expanded indexed members, exact Evidence-ID unions,
permutation-stable ordering, and each stated rejection.

Fixture implementations MUST name every node and raw relation explicitly,
assert the counts above, assert the exact sorted ID sequences, test reversed
input order, and test at least one non-mergeable discriminator for fixtures 6,
7, and 9. Counts are architecture acceptance data, not production fixtures in
this documentation-only Session.

### 13.2 Complete raw-relation cardinality contract

The tables below are the complete relation-ID mapping for all fixtures. Each
`fNN-rNN` handle identifies exactly one canonical `gpr` relation ID produced by
GP11 from the row values; the handle is fixture notation, not a second graph
identity. Comma-separated handles, endpoint pairs, and Evidence IDs are
positionally aligned, so every expanded member resolves independently. `1:3`,
for example, means one distinct source and three distinct targets participate
in that declared relation family in this fixture; it does not replace or
narrow `declared_cardinality`.

`Dir` is always `S→T`. `Agg` is `—` when the raw relation is not visually
aggregated, or a deterministic fixture aggregation handle whose member list is
defined below. `P` and `T` are Product and Technical projection visibility:
`V` means initially visible under the fixture policy and `D` means retained in
authorized detail/drill-down. Either value consumes the same raw relation ID
and cardinality; a view never infers its own value.

Column names are compact aliases for the required implementation fields:
relation handle → `relation_id`; Source/target → `source_node_id` and
`target_node_id`; Type → `relation_type`; Declared cardinality →
`declared_cardinality`; Observed S:T → `observed_source_count` and
`observed_target_count`; Dir → `direction`; Evidence IDs → `evidence_ids`;
Agg → `aggregation_group`; and P/T → Product/Technical projection visibility.
Thus every expanded raw row resolves every required field without prose-only
inheritance.

#### Fixtures 1 and 12 — fully expanded serial and dual-view contracts

| Relation handle | Source → target | Type | Declared cardinality | Observed S:T | Dir | Evidence IDs | Agg | P | T |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `f01-r01` | `problem→plan` | `DECOMPOSES_TO` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-plan` | — | V | D |
| `f01-r02`,`f01-r03`,`f01-r04` | `workflow→A`,`workflow→B`,`workflow→C` | `CONTAINS` | `ONE_TO_MANY` | `1:3` | `S→T` | `ev-topology-a`,`ev-topology-b`,`ev-topology-c` | — | V | V |
| `f01-r05`,`f01-r06` | `B→A`,`C→B` | `DEPENDS_ON` | `ONE_TO_ONE` | `1:1` per serial dependency | `S→T` | `ev-dep-ab`,`ev-dep-bc` | — | V | V |
| `f01-r07`,`f01-r08`,`f01-r09` | `A→definition`,`B→definition`,`C→definition` | `ASSIGNED_TO` | `MANY_TO_ONE` | `3:1` | `S→T` | `ev-assign-a`,`ev-assign-b`,`ev-assign-c` | — | D | V |
| `f01-r10` | `definition→instance` | `CONTAINS` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-instance` | — | D | D |
| `f01-r11` | `instance→runtime` | `EXECUTED_BY` | `MANY_TO_ONE` | `1:1` | `S→T` | `ev-runtime-binding` | — | D | V |
| `f01-r12` | `C→outcome` | `PRODUCES` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-outcome` | — | D | V |

Fixture 12 contains the exact twelve raw relation IDs `f01-r01` through
`f01-r12`, not aliases newly allocated by either view. Its fully expanded
source, target, type, declared cardinality, observed count, direction,
evidence, aggregation, and visibility values are exactly the twelve rows
above. Product and Technical consume those same canonical IDs and values;
their `V`/`D` differences are omission policy only. Both retain the identical
Graph Snapshot ID and Platform Execution Identity. Neither aggregation nor a
view may create `f12-*` replacement relations.

#### Fixtures 2–5 — fan-out, fan-in, assignment, and shared evidence

| Fixture / relation handles | Source → target | Type | Declared cardinality | Observed S:T | Dir | Evidence IDs | Agg | P | T |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 / `f02-r01`..`f02-r04` | `workflow→A`,`workflow→B`,`workflow→C`,`workflow→D` | `CONTAINS` | `ONE_TO_MANY` | `1:4` | `S→T` | `ev-topology-a`..`ev-topology-d` | — | V | V |
| 2 / `f02-r05`,`f02-r06` | `B→A`,`C→A` | `DEPENDS_ON` | `MANY_TO_ONE` | `2:1` | `S→T` | `ev-dep-ba`,`ev-dep-ca` | — | V | V |
| 2 / `f02-r07`,`f02-r08` | `D→B`,`D→C` | `DEPENDS_ON` | `ONE_TO_MANY` | `1:2` | `S→T` | `ev-dep-db`,`ev-dep-dc` | — | D | V |
| 2 / `f02-r09` | `A→instance` | `ASSIGNED_TO` | `MANY_TO_ONE` | `2:1` with `f02-r10` | `S→T` | `ev-assignment-a` | — | D | V |
| 2 / `f02-r10` | `D→instance` | `ASSIGNED_TO` | `MANY_TO_ONE` | `2:1` with `f02-r09` | `S→T` | `ev-assignment-d` | — | D | V |
| 2 / `f02-r11` | `D→outcome` | `PRODUCES` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-outcome` | — | D | V |
| 3 / `f03-r01`..`f03-r03` | `definition→I1`,`definition→I2`,`definition→I3` | `CONTAINS` | `ONE_TO_MANY` | `1:3` | `S→T` | `ev-select-i1`,`ev-select-i2`,`ev-select-i3` | — | V | V |
| 3 / `f03-r04`..`f03-r06` | `I1→definition`,`I2→definition`,`I3→definition` | `REFERENCES` | `MANY_TO_ONE` | `3:1` | `S→T` | `ev-select-i1`,`ev-select-i2`,`ev-select-i3` | — | D | V |
| 3 / `f03-r07` | `I1→runtime` | `EXECUTED_BY` | `MANY_TO_ONE` | `1:1` | `S→T` | `ev-runtime-binding` | — | D | V |
| 4 / `f04-r01`..`f04-r03` | `T1→I1`,`T2→I1`,`T3→I1` | `ASSIGNED_TO` | `MANY_TO_ONE` | `3:1` | `S→T` | `ev-assignment-t1`,`ev-assignment-t2`,`ev-assignment-t3` | — | V | V |
| 5 / `f05-r01`..`f05-r04` | `T1→C1`,`T1→C2`,`T2→C1`,`T2→C2` | `REQUESTS` | `MANY_TO_MANY` | `2:2` | `S→T` | `ev-cap-t1-c1`,`ev-cap-t1-c2`,`ev-cap-t2-c1`,`ev-cap-t2-c2` | — | V | V |
| 5 / `f05-r05`..`f05-r08` | `T1→K1`,`T1→K2`,`T2→K1`,`T2→K2` | `REFERENCES` | `MANY_TO_MANY` | `2:2` | `S→T` | `ev-knowledge-t1-k1`,`ev-knowledge-t1-k2`,`ev-knowledge-t2-k1`,`ev-knowledge-t2-k2` | — | D | V |

Fixture 2 therefore contains eleven relations, not ten: four `CONTAINS`, four
`DEPENDS_ON`, two `ASSIGNED_TO`, and one `PRODUCES`. The `N8/R10` shorthand
and derived `E10`/Technical edge count in the earlier summary are corrected to
`N8/R11`, `E11`, and `T8/11`; Product remains `P6/6`. This arithmetic
correction does not add a semantic relation—the completeness audit exposed the
pre-existing enumerated eleventh member.

#### Fixture 6 — same-pair multi-relation semantics

| Relation handle | Source → target | Type | Declared cardinality | Observed S:T | Dir | Evidence IDs | Agg | P | T | Rationale |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `f06-r01` | `A→B` | `DEPENDS_ON` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-dependency` | `f06-g01` | V | V | this fixture's dependency occurrence has one exact prerequisite |
| `f06-r02` | `A→B` | `DATA_FLOW` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-data` | `f06-g01` | V | one producer may emit evidence to multiple consumers even though one is observed |
| `f06-r03` | `A→B` | `TRIGGERS` | `MANY_TO_MANY` | `1:1` | `S→T` | `ev-trigger` | `f06-g01` | V | event/activity triggering permits multiple sources and targets |

`f06-g01` exposes the sorted cardinality set
`[MANY_TO_MANY, ONE_TO_MANY, ONE_TO_ONE]` and ordered members
`[f06-r01, f06-r03, f06-r02]` under the GP06 type ordering. It never labels the
aggregate with one invented cardinality. This proves that same-node-pair raw
relations may have different declared semantics and that expansion preserves
them.

#### Fixtures 7–10 — authorization, approval, failure, and ambiguity

| Fixture / relation handle | Source → target | Type | Declared cardinality | Observed S:T | Dir | Evidence IDs | Agg | P | T |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 / `f07-r01` | `task→capability` | `REQUESTS` | `MANY_TO_MANY` | `1:1` | `S→T` | `ev-request` | — | V | V |
| 7 / `f07-r02` | `capability→approval` | `AUTHORIZED_BY` | `MANY_TO_ONE` | `1:1` | `S→T` | `ev-deny` | — | D | V |
| 7 / `f07-r03` | `approval→task` | `BLOCKS` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-deny` | — | V | V |
| 7 / `f07-r04` | `task→outcome` | `PRODUCES` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-deny` | — | V | V |
| 8 / `f08-r01` | `plan→approval` | `REQUESTS` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-plan-revision` | — | V | V |
| 8 / `f08-r02` | `approval→task` | `BLOCKS` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-decided-at` | — | V | V |
| 8 / `f08-r03` | `plan→approval` | `APPROVED_BY` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-actor`,`ev-decided-at`,`ev-plan-revision` | — | V | V |
| 9 / `f09-r01`,`f09-r02` | `workflow→A`,`workflow→B` | `CONTAINS` | `ONE_TO_MANY` | `1:2` | `S→T` | `ev-topology-a`,`ev-topology-b` | — | V | V |
| 9 / `f09-r03` | `B→A` | `DEPENDS_ON` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-skip-b` | — | V | V |
| 9 / `f09-r04` | `A→B` | `BLOCKS` | `ONE_TO_MANY` | `1:1` | `S→T` | `ev-failure-a`,`ev-skip-b` | — | V | V |
| 9 / `f09-r05` | `A→outcome` | `PRODUCES` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-failure-a` | — | V | V |
| 10 / `f10-r01` | `task→runtime` | `EXECUTED_BY` | `MANY_TO_ONE` | `1:1` | `S→T` | `ev-runtime-binding` | — | D | V |
| 10 / `f10-r02` | `task→outcome` | `PRODUCES` | `ONE_TO_ONE` | `1:1` | `S→T` | `ev-ambiguous-effect` | — | V | V |

Fixture 9 therefore contains five relations, not four: two `CONTAINS`, one
`DEPENDS_ON`, one `BLOCKS`, and one `PRODUCES`. Its earlier `N4/R4`, `E4`,
`P4/4`, and `T4/4` shorthand is corrected to `N4/R5`, `E5`, `P4/5`, and
`T4/5`. `f09-r03` remains dependent-to-prerequisite (`B→A`) while `f09-r04`
remains blocker-to-blocked (`A→B`); cardinality never reverses either relation,
and opposite direction plus distinct blocking class prevents their safety
semantics from being collapsed.

#### Fixture 11 — complete collapsed-group membership

| Relation handles | Source → target expansion | Type | Declared cardinality | Observed S:T | Dir | Evidence IDs | Agg | P | T |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `f11-r01`..`f11-r12` | `definition→I01` through `definition→I12` | `CONTAINS` | `ONE_TO_MANY` | `1:12` | `S→T` | positionally `ev-instance-01`..`ev-instance-12` | `f11-g01` | V | V |
| `f11-r13`..`f11-r24` | `I01→definition` through `I12→definition` | `REFERENCES` | `MANY_TO_ONE` | `12:1` | `S→T` | positionally `ev-instance-01`..`ev-instance-12` | `f11-g02` | D | V |

The default group is presentation-only. `f11-g01` summarizes
`ONE_TO_MANY`; `f11-g02` summarizes `MANY_TO_ONE`; neither group is a raw node
or execution entity. Expansion restores all 24 exact members, endpoint
directions, declared cardinalities, and evidence links in cardinality-aware
stable order.

The complete audit totals 94 raw relation occurrences across fixtures 1–12,
counting Fixture 12's deliberate reuse of Fixture 1's twelve canonical IDs.
All 94 resolve to one of the four canonical enum values; zero depend on prose,
observed counts, aggregation, grouping, inheritance, or view-local inference.

### 13.3 Final Product/Technical mapping

| Canonical node/relation | Product visibility | Product aggregation | Technical visibility | Technical aggregation | Drill-down evidence | Hidden by default in Product |
| --- | --- | --- | --- | --- | --- | --- |
| Business Problem / `DECOMPOSES_TO` Plan | visible | business plan summary | visible when trace requested | raw or same eligible edge group | approved plan revision and relation IDs | authoring internals |
| Plan / `CONTAINS` Workflow/Task | Plan and business steps visible | repeated step/parallel groups | Plan revision, Workflow, and Tasks visible | branch and repeated-Task groups as needed | topology source, revision, raw relation IDs | Kubernetes UID and raw spec |
| Task / `DEPENDS_ON`, `TRIGGERS`, `DATA_FLOW` Task | business sequence/progress visible | eligible same-pair semantics aggregate | all semantics visible | one eligible edge plus raw expansion | dependency/data/trigger relation IDs and Evidence IDs | retry/replay and raw diagnostics |
| Task / `ASSIGNED_TO` Definition or Instance | responsible role and Instance count | role/Instance group | Definition and Instance identities visible | repeated assignment group only at thresholds | selection/assignment evidence and cardinality | Instance ID unless explicitly authorized detail |
| Definition / `CONTAINS` Instance | role plus count | Instance group | Definition and every Instance/group visible | bounded Instance group with expansion | exact Definition/Instance IDs and relation IDs | raw logical Instance identity |
| Instance / `EXECUTED_BY` Runtime Realization | execution-environment availability only | Runtime details omitted | requested/effective Runtime and realization visible | Runtime pool group is presentation-only | Platform Execution Identity, binding evidence, correlation IDs | Runtime Binding, Kubernetes UID, Provider-native ID |
| Task / `REQUESTS`, `AUTHORIZED_BY` Capability | permitted/denied business state | Capability group when dense | decision, reason, request, and Provider-call evidence visible | eligible Capability group | decision and call Evidence IDs | raw request arguments and diagnostics |
| Task / `REFERENCES` Knowledge | Citation visible when authorized | Evidence group | synthetic Collection/Asset/Revision/Evidence visible | Evidence group with raw expansion | exact citation and Evidence IDs | raw retrieval diagnostics; no production RAG claim |
| Approval / `BLOCKS` Task; Plan / `APPROVED_BY` Approval | Human gate/state visible with the approval prerequisite pointing to the blocked Task | repeated approvals only when threshold met; raw blocked direction preserved | actor/reference/revision/reason evidence and raw `approval-BLOCKS->task` visible as authorized | blocking edges never merge with informational or opposite-direction edges | immutable approval evidence attached to the correct raw relation | security-sensitive actor detail where policy hides it |
| Task/Workflow / `PRODUCES` Outcome | Outcome summary and explicit state | Outcome summary group only when homogeneous | domain Outcome, reason, UNKNOWN, and limitations visible | raw terminal/ambiguous relations | Outcome Evidence IDs and limitation codes | raw diagnostic evidence |
| Any `COMPENSATES` or historical `REFERENCES` | visible only as business-relevant exception/history | never normal-path merged | visible with temporal/path classification | separate edge group | raw relation, temporal context, evidence authority | historical/native detail |

Both projections carry the same `graph_snapshot_id` and unchanged Platform
Execution Identity when execution-scoped. Every displayed or grouped edge
retains its canonical `aggregation_id` and ordered raw `relation_id` members,
so a Product edge can be traced to the identical Technical raw relationships.
Filtering may omit a node or edge but cannot allocate a replacement identity.

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
| canonical `BLOCKS` direction | source is blocker/prerequisite and target is blocked; fixtures 7/8 use Approval→Task and fixture 9 uses failed A→skipped B |
| no production/public change | architecture artifact and index only |

After the S5-ARCH-009-C1 correction, no contradiction remains with accepted
S5-ARCH-008, the accepted logical Core candidate, the internal shared DTO,
current Workflow DAG behavior, or Platform Execution Identity. This candidate
adds no competing authority: it derives relationships from those sources and
fails closed on conflict.

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

A separately authorized bounded downstream internal implementation slice owns:

- the internal Graph Projection model;
- deterministic node and raw-relation construction;
- isolated execution-dependency DAG validation;
- general directed relation graph handling;
- deterministic edge aggregation and grouping;
- Product and Technical projection policies;
- all twelve deterministic fixtures; and
- pure component tests, including rejection and permutation cases.

It may adapt the existing shared DTO as one input. It must preserve upstream
authority, import direction, Controller behavior, public wire shapes,
Runtime/Capability/Knowledge constraints, and the exact projection equality
rules here. It does **not** own final Product View UI, final Technical View UI,
drag/drop authoring, Runtime multi-instance lifecycle, execution scheduling,
public schema, production Knowledge, persistence, or dependency selection.
Those require separately authorized scopes and gates. This Session allocates
no downstream Session ID and activates no implementation.

Checkpoint B reused the exact C2 task, branch, and isolated worktree at
`d28cf3b536aea0b752a510c9469490364d446784`. The worktree and index were clean;
durable `origin/main` remained
`9d057598bdaf233efc682430d0d6ea7579591ea8`; the C2 remote branch, PR source
remote branch, and PR head all matched the authorized C2 head; and PR #61
remained `OPEN / DRAFT / CLEAN / MERGEABLE / UNMERGED`. Exact-head Quality
Gates and Frontend Quality Gates were successful.

The complete twelve-fixture review reconfirmed 94 raw relation occurrences,
zero missing cardinalities, only the four canonical enum values, fully
resolvable Fixture 12 inheritance, identical Product/Technical underlying
cardinalities, cardinality-preserving aggregation and grouping, deterministic
cardinality-aware ordering, unchanged Platform Execution Identity authority,
and the C1 `BLOCKS` directions. No contradiction, architecture redesign,
implementation authorization, public schema change, or additional writable
path is required.

The S5-ARCH-009-C2 correction is ready for Human Close Confirmation. It does
not reopen either closed architecture source Session, resume or modify
S5-REL-023, merge PR #61, or authorize implementation.

```text
SESSION: S5-ARCH-009-C2
CODEX_TASK_NAME: [S5-ARCH-009-C2] Graph Fixture Cardinality Completeness Correction
LIFECYCLE: CLOSING
STATUS: PASS_WITH_CONSTRAINTS
CHECKPOINT: B — CARDINALITY_CORRECTION_CONVERGENCE_AND_EXIT
RESULT: READY_TO_CLOSE
CURRENT_STEP: 2_OF_3
ALL_12_FIXTURES: CARDINALITY_COMPLETE
RAW_RELATIONS_WITHOUT_CARDINALITY: 0
CANONICAL_CARDINALITY_ENUM: PASS
FIXTURE_INHERITANCE: FULLY_RESOLVABLE
PRODUCT_TECHNICAL_CARDINALITY: CONSISTENT
C1_BLOCKS_DIRECTION: PRESERVED
S5_REL_023_MODIFIED: NO
PR_MERGED: NO
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_S5_ARCH_009_C2_CLOSE_CONFIRMATION
NEXT_GATE: Human S5-ARCH-009-C2 Close Confirmation
```

Rollback for this architecture Session is removal of this artifact and its one
index entry. There is no data migration, execution rollback, dependency
cleanup, or public compatibility action.

```text
SESSION: S5-ARCH-009
CODEX_TASK_NAME: [S5-ARCH-009] Product and Technical Graph Projection Scope Gate
LIFECYCLE: CLOSING
STATUS: PASS_WITH_CONSTRAINTS
CHECKPOINT: B — GRAPH_PROJECTION_DECISION_CONVERGENCE_AND_EXIT
RESULT: READY_TO_CLOSE
CURRENT_STEP: 2_OF_4
GRAPH_PROJECTION: ARCHITECTURE_COMPLETE / INTERNAL / UNFROZEN / NOT_IMPLEMENTED
PRODUCT_VIEW: NOT_STARTED
TECHNICAL_VIEW: NOT_STARTED
PR_STATE: OPEN / DRAFT / CLEAN / UNMERGED
SESSION_CLOSED: NO
NEXT_ACTION: WAIT_FOR_HUMAN_S5_ARCH_009_CLOSE_CONFIRMATION
NEXT_GATE: Human S5-ARCH-009 Close Confirmation
```
