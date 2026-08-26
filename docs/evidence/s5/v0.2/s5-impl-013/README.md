# S5-IMPL-013 — Shared Graph Projection Foundation Evidence

## Session and delivery state

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-013` |
| Title | `Shared Graph Projection Foundation` |
| Type / version | `IMPL` / `v0.2 CONNECT — Digital Employee Technical Preview` |
| Checkpoint | `B — GRAPH_PROJECTION_SAFETY_CONVERGENCE_AND_EXIT_CANDIDATE` |
| Authorized baseline | `f5b5f24249e12a0e8d82962fa7d165e4bbc98c37` |
| Checkpoint A head | `a6ff852f543e8ef5fe38b0f2686256c1f71850e7` |
| Checkpoint B implementation head | `cb033f6a8c2ca1b0bd795cd38b4d1db0ea4f2bdc` |
| Evidence commit | `THIS_DOCUMENTATION_SUCCESSOR_COMMIT / RESOLVED_BY_GIT_HISTORY` |
| Branch | `codex/s5-impl-013-shared-graph-projection-foundation` |
| Draft PR | `#62 / OPEN / DRAFT / CLEAN / MERGEABLE / UNMERGED` at evidence authorization |
| Classification | `INTERNAL / UNFROZEN / REPLACEABLE / NOT_A_PUBLIC_CONTRACT` |

### S5-IMPL-013-C1 correction state

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-013-C1` |
| Title | `Graph Projection Fixture Contract and Aggregation Safety Correction` |
| Implementation source head | `a78c22bc25e2aa23b378a6ea2cb69fed367b9e8f` |
| Architecture-contract authority | `origin/main` at `a76d5cc17e555a34aee63ab1cc18065c8203fb68` |
| Branch | `codex/s5-impl-013-c1-fixture-contract-aggregation-safety` |
| Target PR | `#62 / NEW_PR_PROHIBITED` |
| Rebase / merge-main | `PROHIBITED / NOT_PERFORMED` |

This C1 correction consumes the integrated S5-ARCH-009-C3/C4 fixture contract
as read-only architecture authority without rebasing or merging it. It
completes all twelve fixture visibility mappings, adds the approved
`plan-TRIGGERS->workflow` revision linkage to Fixtures 1/12, aligns the
security-input discriminator, and removes `aggregation_key` from the exact
GP06 safety tuple. It changes no public API, frozen Contract, CRD, execution
behavior, source-of-truth boundary, dependency, or persistence model.

The Human G1 gate authorized the bounded internal implementation slice from
S5-ARCH-009 after confirming S5-ARCH-009, C1, C2, and S5-REL-023 closed and
durably integrated. Architecture terminal-metadata lag was explicitly accepted
as non-blocking and was not changed by this Session. S5-REL-023 remains closed,
unmodified, and reopen-prohibited.

This artifact records durable repository evidence. It changes no implementation
behavior and does not grant merge, release acceptance, production readiness,
public compatibility, Contract/schema freeze, or Provider certification.

### S5-IMPL-013-C2 local correction state

S5-REL-024 reported two P1 findings against the C1 head. First, an aggregate's
`raw_relation_ids` were globally sorted by opaque projection ID after semantic
label ordering, so expansion order did not preserve the binding GP06
presentation order. Second, `RelationSpec.authorization_class` normalized an
omitted aggregation-safety classification to the shared explicit value
`UNCLASSIFIED`, allowing genuinely missing classifications to enter the same
GP07 bucket.

The initial C2 proposal to extend the presentation key with source, target,
cardinality, and evidence order was withdrawn by the Human scope decision. No
such extended ordering is implemented. C2 retains the accepted GP06 order
exactly as `(display_priority, relation-type rank, relation_id)`: it first
flattens relation-type occurrences, derives labels and raw-member presentation
order from that sequence, and keeps a separately sorted member-ID tuple solely
for deterministic aggregate identity. Fixture 6 therefore expands as
`DEPENDS_ON`, `TRIGGERS`, `DATA_FLOW`; reversed inputs produce the same edge and
aggregate identity; and equal-priority occurrences of the same type use
`relation_id` only as the final tie-breaker.

C2 also represents a missing authorization classification as `None`, distinct
from explicit `UNCLASSIFIED` and from a classified string value. During GP07
aggregation, a missing authorization classification receives a deterministic
relation-specific safety boundary and therefore remains a singleton. The exact
same-source/same-target `AUTHORIZED_BY` reproduction with one `DENIED` and one
`SUCCEEDED` relation produces two singleton edges, zero aggregation, two
distinct raw relation identities, and byte-stable replay. Explicitly
`UNCLASSIFIED` members remain eligible to aggregate when every other accepted
safety discriminator is equal. `aggregation_key` remains metadata outside the
GP06/GP07 safety tuple.

C2 local validation at the uncommitted correction candidate:

- focused Graph Projection suite: **19 passed**;
- Graph Projection, Core compatibility, and shared-view regression slice:
  **40 passed**;
- focused Ruff lint: passed;
- focused Ruff format check: **2 files already formatted**;
- full `make check`: Ruff lint passed, Ruff format checked **106 files**, and
  **606 passed** with one pre-existing Starlette/httpx deprecation warning;
- `git diff --check`: passed;
- frontend lint/build: not required because no frontend path changed;
- GitHub PR #62 ownership and exact-head CI: **pending remote verification**;
  no C2 commit, push, PR mutation, Quality Gate claim, or Frontend Quality Gate
  claim is made by this local record.

## Exact changed-path inventory

The final authorized path count is three:

1. `console/backend/src/agent_console/graph_projection.py`
2. `console/backend/tests/test_graph_projection.py`
3. `docs/evidence/s5/v0.2/s5-impl-013/README.md`

No other Console, Core, Gateway, Operator, Runtime, Workflow, frontend,
manifest, CRD, schema, dependency, lockfile, architecture, governance,
experiment, or evidence path is changed.

## Internal architecture

The implementation adds one pure, read-only canonical graph boundary behind
the existing stateless Console projection boundary:

```text
normalized authorized evidence
  -> immutable canonical Graph Projection snapshot
    -> Product graph projection
    -> Technical graph projection
```

Both views consume the same canonical snapshot. A view may filter, group,
aggregate, label, and order canonical values; it cannot discover, reconstruct,
reverse, persist, or replace relationships. Kubernetes and the existing domain
components remain authoritative for their source facts.

The implementation provides:

- immutable internal snapshot, node, raw-relation, visual-edge, group, and view
  values;
- all eleven S5-ARCH-009 node types, fourteen relation types, eight phases, and
  four declared cardinalities;
- deterministic SHA-256 snapshot, node, relation, aggregation, and group IDs
  over normalized canonical JSON;
- independent execution-dependency DAG validation;
- general directed relation layers whose unrelated evidence, approval,
  historical, and compensation cycles are not rejected as execution cycles;
- deterministic safety-aware edge aggregation;
- presentation-only deterministic grouping and exact expansion; and
- Product and Technical projections derived from the same raw identities.

Graph identities remain projection identities only. The unchanged typed
Platform Execution Identity is consumed through the already-authorized shared
view seam. Provider-native and other native identifiers cannot substitute for
Platform authority.

## Determinism and safety invariants

Checkpoint B reviewed the complete baseline-to-candidate diff and corrected
four material evidence gaps before convergence:

1. Graph Snapshot IDs now bind normalized context, node facts, relation facts,
   and bounded Provider-effect facts. Different facts cannot accidentally reuse
   one snapshot ID, while input permutation remains stable.
2. A relation whose security domain differs from the snapshot security domain
   fails closed before graph construction or aggregation.
3. Capability authorization relations require explicit effect evidence.
   `DENY` requires zero Provider calls and zero citations; `ALLOW` requires
   Provider-call evidence; every cited Evidence ID must exist in the canonical
   graph.
4. Fixture 11 now contains the exact architecture-required `N13/R24` raw shape,
   without an unused Runtime node.

Aggregation uses the complete S5-ARCH-009 safety discriminator boundary:
source, target, direction, projection context, security domain,
execution/history context, path class, blocking class, authorization class,
and evidence-authority class. Missing or different safety classifications do
not merge. `BLOCKS` retains blocker/prerequisite to blocked-node direction and
cannot merge with an opposite-direction or informational relation.

`aggregation_key` remains preserved raw fixture/presentation metadata but is
not a GP06 safety discriminator and cannot split relations whose complete
approved safety tuple is equal. Fixture 8 assigns distinct Human approval
request and decision authorization classifications, so its same-pair
relations remain separate for a safety reason rather than a fixture handle.

Aggregated edges retain the ordered raw relation IDs, complete Evidence-ID
union, and the sorted set of original declared cardinalities. Aggregation does
not invent a replacement cardinality. Expansion restores the same canonical
members and identities.

## Fixture acceptance evidence

The component suite implements all twelve S5-ARCH-009 deterministic fixtures:

| Fixture | Raw shape / proof |
| --- | --- |
| 1 | serial graph with exact approved-revision trigger, `N10/R13` |
| 2 | parallel fan-out/fan-in, `N8/R11` |
| 3 | Definition and three Instances, `N5/R7` |
| 4 | three Tasks assigned to one Instance, `N4/R3` |
| 5 | shared Capability and Knowledge evidence, `N6/R8` |
| 6 | same-pair dependency, data, and trigger semantics, `N2/R3` |
| 7 | denied Capability with zero Provider effects, `N4/R4` |
| 8 | Human approval with canonical `approval-BLOCKS->task`, `N3/R3` |
| 9 | failed blocker and skipped dependent remain distinct, `N4/R5` |
| 10 | ambiguous `UNKNOWN` Outcome, `N3/R2` |
| 11 | twelve-Instance grouping and exact expansion, `N13/R24` |
| 12 | Fixture 1 dual-view identity reuse, `N10/R13` |

The suite proves 96 raw relation occurrences, zero missing declared
cardinalities, exactly the four canonical cardinality values, exact Fixture 12
snapshot/relation identity reuse, distinct snapshot identities for different
fixtures, stable reversed-input ordering, execution-cycle rejection, tolerance
of non-execution cycles, unsafe-merge separation, security-domain rejection,
effect-evidence rejection, UNKNOWN preservation, and exact group expansion.

The C1 suite additionally proves every corrected initial Product/Technical
node/group set and edge count for all twelve fixtures; Fixture 3 `P4/3`;
Fixture 7 `P4/3`; Fixtures 1/12 `P7/7` and `T9/11`; exact `I01..I12` expansion
order; the common `fixture-authorized-domain` input; and
`SECURITY_DOMAIN_INPUT_MISMATCH` for cross-domain relation input.

## Compatibility and non-change audit

- Public API or Console HTTP wire change: **no**.
- CRD, Kubernetes API group, resource schema, or lifecycle change: **no**.
- Controller, execution, scheduling, retry, replay, or Workflow DAG behavior
  change: **no**.
- Runtime, Capability Gateway, Knowledge, Provider, or source-of-truth behavior
  change: **no**.
- Persistence, database, migration, backfill, or dual write: **no**.
- Dependency or lockfile change: **no**.
- Product or Technical UI change: **no**.
- Existing Core-consumer allowlist expansion: **no**; the graph module consumes
  Platform identity through the already-authorized shared-view seam.
- Architecture or governance metadata change: **no**.

The final diff contains the two new internal implementation/test files plus
this evidence artifact only.

## Validation and exact-head provenance

S5-IMPL-013-C1 local validation on the authorized implementation branch:

- focused Graph Projection suite: **15 passed**;
- targeted Graph Projection, Core compatibility, and shared-view suite:
  **36 passed**;
- full `make check`: Ruff lint passed, Ruff format passed, **602 passed**;
- one existing Starlette/httpx deprecation warning remained unchanged;
- `uv` reported non-fatal environment-lock warnings because validation reused
  the existing repository environment without writing outside this worktree.

The C1 correction has not been rebased onto or merged with the architecture
authority. No new PR was created; PR #62 remains the sole target. Exact C1
commit and CI provenance remain pending the authorized commit/push workflow.

The original S5-IMPL-013 validation record follows unchanged for historical
provenance.

Local validation against Checkpoint B implementation head
`cb033f6a8c2ca1b0bd795cd38b4d1db0ea4f2bdc`:

- targeted Graph Projection, Core compatibility, and shared-view suite:
  **34 passed**;
- full `make check`: Ruff lint passed, Ruff format passed, **600 passed**;
- `git diff --check`: passed;
- one existing Starlette/httpx deprecation warning remained unchanged.

GitHub CI run
[`32961574619`](https://github.com/yanzheqian1774-debug/cloud-native-agent-platform/actions/runs/32961574619)
records:

- event: `pull_request`;
- branch: `codex/s5-impl-013-shared-graph-projection-foundation`;
- exact head: `cb033f6a8c2ca1b0bd795cd38b4d1db0ea4f2bdc`;
- Quality Gates: **success**;
- Frontend Quality Gates: **success**;
- CI log: `collected 600 items`, `600 passed, 1 warning`, Ruff passed,
  `106 files already formatted`, and `All local quality checks passed`.

Before this evidence-only successor, local HEAD, remote branch head, and Draft
PR #62 head all matched the Checkpoint B implementation head. The evidence
successor commit cannot embed its own Git object ID without recursive mutation;
its identity is resolved from the branch/PR parent chain and exact Git history.

## Limitations and claim boundaries

- The boundary is internal, version-unfrozen, and replaceable.
- No graph builder is connected to a public endpoint, controller, persistence
  store, or UI.
- Grouping thresholds remain internal configuration candidates; production
  usability, scale, accessibility, and performance are unproven.
- Security-domain discrimination prevents cross-domain aggregation but does not
  implement v0.2 multi-tenancy or authorization architecture.
- Knowledge evidence remains synthetic; no production retrieval or RAG claim is
  made.
- Runtime multiplicity remains future cardinality metadata only; no Runtime
  Pool, autoscaling, or multi-instance support is granted.
- Final Product View UI, Technical View UI, public Graph Contract, persistence,
  production readiness, and release acceptance remain outside this Session.

## Rollback

Revert the S5-IMPL-013 commits from Draft PR #62. This removes the two new
internal files and this evidence directory. No data migration, schema rollback,
dual-write reconciliation, dependency cleanup, external effect reversal, or
Kubernetes resource action is required.

## References

- [S5-ARCH-009 Graph Projection Scope Gate](../../../../../architecture/s5/v0.2/S5-ARCH-009-PRODUCT-TECHNICAL-GRAPH-PROJECTION-SCOPE-GATE-V1.md)
- [Graph Projection implementation](../../../../../console/backend/src/agent_console/graph_projection.py)
- [Graph Projection component tests](../../../../../console/backend/tests/test_graph_projection.py)
