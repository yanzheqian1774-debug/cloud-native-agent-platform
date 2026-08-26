# S5-IMPL-009 — Authoring Backend and Shared View DTO Evidence

## Session

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-009` |
| Correction session | `S5-IMPL-009-C1 — APPROVAL_REPLAY_EXACTNESS_CORRECTION` |
| Checkpoint | `A — AUTHORING_BACKEND_AND_SHARED_VIEW_DTO_CANDIDATE` |
| Authorized baseline | `cf8373d342a7b2c463468cd041527f5b6044ce38` |
| Branch | `codex/s5-impl-009-authoring-backend-shared-view-dto` |
| C1 correction branch | `codex/s5-impl-009-c1-approval-replay-exactness` |
| Final exact head | Recorded by the Draft PR exact-head gate; this in-commit artifact cannot self-reference its own Git object ID |
| C1 correction commit | `9f8e6549a4cb18a5029f11e515bd33dccdf7410c` |
| Classification | `INTERNAL / VERSION_UNFROZEN / NOT_A_PUBLIC_CONTRACT` |

PR #59 was verified merged at the authorized baseline. Fresh `origin/main`, the
new isolated worktree HEAD, and the branch start all matched that commit before
mutation. The unrelated primary checkout was dirty and was not used or changed.

## Exact changed-path inventory

- `console/backend/src/agent_console/authoring.py`
- `console/backend/src/agent_console/shared_views.py`
- `console/backend/tests/test_authoring.py`
- `console/backend/tests/test_shared_views.py`
- `core/tests/test_compatibility.py` (narrow Core consumer allowlist only)
- `docs/evidence/s5/v0.2/s5-impl-009/README.md`

No existing Console HTTP schema, route, frontend type, CRD, public schema,
dependency, lockfile, Gateway, Operator, Runtime, Task, Workflow, Registry, or
governance file is changed. The existing rollback compatibility test adds only
the shared-view module and its focused test to the exact Core-consumer
allowlist; the first full test run proved this update was required.

## Authoring lifecycle

The bounded in-memory candidate implements `DRAFT`, `REVIEW_REQUIRED`,
`APPROVED`, `REJECTED`, and `SUPERSEDED`. An AI-assisted candidate is only a
labelled Draft. The effective Definition changes only after an explicit Human
`APPROVE` decision on the current immutable source revision.

The decision record retains actor, `APPROVE`/`REJECT`, timezone-aware timestamp,
and source revision. Only a repeat with exactly equal immutable Approval
evidence (actor, decision, `decided_at`, and source revision) is idempotent. A
repeat with any different decision evidence is a conflicting repeat decision
and fails closed with `REVISION_ALREADY_DECIDED`; in particular, a changed
`decided_at` is never normalized away, tolerated, or overwritten. Datetimes
retain their existing internal timezone-aware Python value semantics and are
compared directly; no public timestamp representation is introduced. Rejection
leaves the effective Definition unchanged. Approval supersedes other open
revisions. Stale source revision, superseded revision, empty Diff,
malformed/extra/missing fields,
duplicate ambiguous values, bounded-size violations, and secret-shaped values
return stable redacted codes.

Caller mappings and sequences are normalized to frozen dataclasses and tuples.
Diff order is fixed by the owned field inventory. Revision identity is derived
deterministically from normalized content plus its source revision; it is an
internal revision, not a public version contract.

### Checkpoint B transition matrix

| From / request | Result | Effective Definition |
| --- | --- | --- |
| effective Definition + changed valid input | immutable `DRAFT` | unchanged |
| `DRAFT` + review request | `REVIEW_REQUIRED` | unchanged |
| `REVIEW_REQUIRED` + exact Human approval | `APPROVED` | changes to that exact revision |
| `REVIEW_REQUIRED` + Human rejection | `REJECTED` | unchanged |
| other open revision after approval | `SUPERSEDED` | unchanged |
| stale source revision | `STALE_SOURCE_REVISION` | unchanged |
| superseded approval | `SUPERSEDED_REVISION` | unchanged |
| missing actor/source or malformed decision/time | stable rejection code | unchanged |
| exact replay of actor/decision/decided_at/source | original immutable decision | unchanged from first decision |
| different actor, decision, decided_at, or source | `REVISION_ALREADY_DECIDED` | unchanged |
| Draft without review, empty Diff, or unknown revision | stable rejection code | unchanged |

There is no publish method, fallback revision, implicit transition, or silent
overwrite. Diff order is fixed. Each difference is explicitly `ADD`, `REMOVE`,
or `REPLACE`; unchanged values are omitted. Nested collections are copied to
tuples before storage, so later caller mutation cannot change a Draft or Diff.

## Shared source and field mapping

`SharedExecutionView` is the one immutable source consumed by both projection
functions. Neither projection reads Kubernetes, invokes a Runtime/Provider, nor
reconstructs state from the other view.

| Shared evidence | Product projection | Technical projection |
| --- | --- | --- |
| Definition ID/revision | employee revision evidence | Definition object |
| Platform Execution Identity | same unchanged ID | same unchanged ID |
| role/message keys and activity boundaries | employee role and can/cannot-do fields | omitted presentation detail |
| team IDs/count and work-plan keys | team and business plan | identities remain separately available |
| business progress and internal Outcome | business progress/summary | bounded Outcome evidence |
| Human approval state | approval state | shared source remains authoritative |
| requested/effective Runtime | presentation does not reinterpret it | distinct support records |
| capability decision/reason/call count | citations only when allowed | authorization evidence and call count |
| synthetic Knowledge evidence | deterministic citations | Collection/Asset/Revision/Evidence IDs |
| limitation codes | presentation can map separately | stable codes |

### Exact shared-source projection map

| Shared source field | Product output | Technical output |
| --- | --- | --- |
| `digital_employee_name_key` | `digitalEmployeeNameKey` | presentation-neutral omission |
| `role_title_key` / `role_description_key` | `roleTitleKey` / `roleDescriptionKey` | presentation-neutral omission |
| responsibility/allowed/prohibited keys | corresponding Product key arrays | presentation-neutral omission |
| suggested team IDs / Instance count | `suggestedTeamIds` / `instanceCount` | distinct `instanceId` |
| work-plan keys / progress code | `workPlanKeys` / `businessProgressCode` | shared evidence remains source |
| Outcome status/summary key | `outcomeStatus` / `outcomeSummaryKey` | `outcome.status` / `summaryMessageKey` |
| citations | deterministic citation records | `knowledgeEvidence` with Collection/Asset/Revision/Evidence IDs |
| approval state | `approvalState` | shared source remains authority |
| Definition ID/revision | `definitionId` / `definitionRevision` | `definition.id` / `definition.revision` |
| Instance/Task/Workflow IDs | Instance count/team context | `instanceId` / `taskId` / `workflowId` |
| Platform Execution Identity | `platformExecutionIdentity` | identical `platformExecutionIdentity` |
| requested/effective Runtime | no independent reconstruction | separate `requestedRuntime` / `effectiveRuntime` |
| Capability decision/reason/calls | citation visibility constrained by decision | `capability.decision/reasonCode/providerCallCount` |
| native correlation | omitted | `providerNativeCorrelation` with `CORRELATION_ONLY` authority |
| limitation codes | presentation mapping outside DTO | `limitationCodes` |

All presentation content is represented by stable Message Keys. Locale is not
part of the source or either projection, so switching between `zh-CN` and
`en-US` cannot alter IDs, enums, codes, evidence, or counts.

## Identity mapping

- `PlatformExecutionIdentity` is imported from the accepted internal Core
  representation and remains unchanged across views.
- Definition, Instance, Task, and Workflow IDs occupy separate fields and are
  tested not to collapse.
- provider-native correlation is explicitly emitted with
  `authority=CORRELATION_ONLY`; it cannot replace a Platform identity.
- no Kubernetes UID, Runtime-native ID, or Provider-native ID is minted or
  promoted by this implementation.

## Runtime classifications

| Runtime | Classification | Availability/support |
| --- | --- | --- |
| Native | `COMPONENT_TESTED_CANDIDATE / PRIMARY_GOLDEN_PATH_CANDIDATE` | bounded Demo availability; `NOT_CERTIFIED` |
| OpenClaw | `EXACT_VERSION_CANDIDATE` | `CURRENTLY_UNAVAILABLE_WITHOUT_LIVE_MANAGED_PROFILE_EVIDENCE / SUPPORT_NOT_GRANTED` |
| Hermes | `EXPERIMENTAL / NOT_CURRENTLY_CERTIFIABLE` | `UNAVAILABLE / SUPPORT_NOT_GRANTED` |

Requested and effective Runtime are distinct. Effective OpenClaw/Hermes and
unknown Runtime evidence fail closed. There is no substitution, invocation,
adapter, Provider contract, retry, or fallback change.

## Knowledge and Outcome boundaries

Knowledge citations are deterministic synthetic Demo evidence only. Each item
contains Collection, Asset, Revision, Evidence, and Message Key identities.
`ALLOW` requires at least one citation. `DENY` requires zero Provider calls and
zero citations. No Provider, RAG, vector database, embedding, reranking,
connector, Memory publication, authorization contract, or Knowledge Demo
ownership is introduced. Full Knowledge Demo ownership remains unresolved and
outside this session.

Outcome is internal, domain-specific, and unfrozen. `PASS`, `FAIL`, and
`UNKNOWN` preserve ambiguity without an exactly-once, retry, or fallback claim.

Checkpoint B additionally validates that all Knowledge IDs carry deterministic
`synthetic` namespaces, malformed citation objects fail with stable diagnostics,
and a native correlation cannot equal or replace Platform Execution Identity.
Projection construction normalizes caller-owned lists to tuples and enforces
per-string, per-collection, and aggregate text bounds. Projection functions
return new lists/dictionaries, so output mutation cannot alter the shared
source. No I/O, host-path access, retrieval, invocation, or publication code is
present in either module.

## Tests and audits

Focused tests cover deterministic Draft/Diff, Human approval, stale and
superseded revisions, rejection preservation, immutable repeated decisions,
exact approval and rejection replay, changed timestamp/actor/decision
rejection, deterministic repeated rejection, stored Approval and effective
Definition non-mutation, caller-input preservation, redacted replay diagnostics,
malformed/ambiguous/oversized input, defensive copying, diagnostic redaction,
secret-shaped rejection, cross-view equality, identity separation, Runtime
separation, provider correlation authority, Capability ALLOW/DENY,
DENY-with-zero-calls, deterministic citations, UNKNOWN preservation,
locale-neutral semantics, deterministic projection, and unchanged caller
input.

The delivery record reports commands and exact results after all required
targeted, repository, frontend, Diff, import-direction, changed-path,
public-wire, schema, dependency, redaction, bounds, rollback, and relative-link
audits complete.

Checkpoint B validation results:

- focused authoring and shared DTO: `34 passed`;
- explicit A1/A2/A3, Native Provider, Capability Gateway, bounded execution,
  Conformance Harness, and S5-SPIKE-008 regression matrix: `334 passed`;
- full `make check`: Ruff lint passed, Ruff format passed, `586 passed` with
  one pre-existing Starlette/httpx deprecation warning;
- frontend lint and production build: passed;
- `git diff --check`: passed;
- exact changed-path, import direction, experiment isolation, no-I/O,
  public-wire, CRD/schema, dependency/lockfile, identity authority, synthetic
  Knowledge, relative-link, and rollback audits: passed.

Checkpoint B focused coverage also includes transition completeness, Diff
add/remove/replace classification, timezone and source-revision validation,
cyclic and unsupported authoring input, mutable shared DTO inputs, malformed
enums/counts/citations, identity-domain collision, native/Platform ID collision,
non-synthetic Knowledge IDs, collection/string/aggregate bounds, deterministic
reprojection, and host-path-free diagnostics.

## Limitations and claim boundaries

- in-memory lifecycle only; no durability, distribution, concurrency, or
  production publication claim;
- internal DTO semantics are version-unfrozen;
- no HTTP consumer is added because that requires the next Human Public
  Surface/DTO gate;
- no Product View UI, Technical View UI, or Golden Demo integration;
- no Runtime, Knowledge, Capability, or Outcome certification;
- no globalization, production-readiness, release, or schema-freeze claim.

## S5-IMPL-009-C1 correction record

S5-REL-022 discovered a material contradiction: the implementation and focused
test treated a repeated decision with a changed `decided_at` as idempotent even
though the durable evidence described exact replay. S5-IMPL-009-C1 corrects
that contradiction only. S5-IMPL-009 remains closed and is not reopened;
S5-REL-022 remains stopped, unmodified, and unmerged. The correction changes no
claim boundary above: only exact immutable Approval evidence is idempotent, and
a changed `decided_at` returns `REVISION_ALREADY_DECIDED` without modifying the
stored Approval, effective Definition, or caller input.

### Non-recursive provenance registration

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-009-C1` |
| Title | `Approval Replay Exactness Correction` |
| `ORIGINAL_S5_IMPL_009_SOURCE_HEAD` | `6f97ec6457f181f59e0ec444596b18a1b1a2f870` |
| `C1_CORRECTION_IMPLEMENTATION_COMMIT` | `9f8e6549a4cb18a5029f11e515bd33dccdf7410c` |
| `C1_PRE_PROVENANCE_REGISTRATION_HEAD` | `a8d6cc3fa675c0c60530691721d2edb29379cf0f` |
| `PROVENANCE_REGISTRATION_COMMIT` | `THIS_DOCUMENTATION_SUCCESSOR_COMMIT / RESOLVED_BY_GIT_HISTORY` |
| `FINAL_DELIVERY_HEAD` | `RESOLVED_FROM_EXACT_PR_SOURCE_HEAD_AND_GIT_HISTORY` |
| `FINAL_HEAD_SELF_REFERENCE` | `NOT_REQUIRED / CRYPTOGRAPHICALLY_RECURSIVE` |
| `FINAL_HEAD_VERIFICATION_OWNER` | `S5-REL-022 CHECKPOINT_A_RESUME` |

The parent chain from the original source head through the correction
implementation commit and pre-registration head reconstructs the complete C1
lineage. The one documentation successor that contains this registration is
identified by Git history and by the exact local source, remote source, and PR
head; embedding its own SHA here is neither required nor cryptographically
possible.

S5-REL-022 discovered the Approval replay contradiction and remained stopped,
unmodified, and unmerged throughout C1. S5-IMPL-009 remained closed. Only an
exact replay of the same immutable Approval evidence is idempotent. A different
`decided_at`, actor, decision, or source revision fails closed with
`REVISION_ALREADY_DECIDED`; stored Approval evidence, effective Definition, and
caller input remain unchanged. This documentation successor changes no
implementation semantics, and no recursive correction is required.

C1 correction validation results:

- focused Authoring replay tests: `16 passed`;
- complete focused S5-IMPL-009 and rollback compatibility set: `37 passed`;
- full `make check`: Ruff lint passed, Ruff format passed, `587 passed` with
  the one pre-existing Starlette/httpx deprecation warning;
- frontend lint and production build: passed;
- `git diff --check` and exact three-path scope audit: passed;
- public API/HTTP wire/CRD/schema and dependency/lockfile non-change audits:
  passed;
- S5-REL-022 worktree non-mutation audit: passed.

## Rollback

Revert the S5-IMPL-009 commits from PR #60. Five paths are new and the only
existing-path change is the exact Core consumer allowlist. There is no public
migration, dual-write, external effect, or stored state to unwind.

## Next Human gate

Stop at the **Human S5-IMPL-009 Authoring Backend and Shared DTO Review Gate**.
Any HTTP/public DTO needed by S5-IMPL-010 or S5-IMPL-011 requires explicit
Human approval and must not be introduced through this candidate.

## References

- [S5-SPIKE-008 evidence](../s5-spike-008/README.md)
- [Core Representation/API Gate](../../../../../architecture/s5/v0.2/S5-ARCH-007-CORE-REPRESENTATION-API-GATE-V1.md)
- [MVS execution ownership gate](../../../../../architecture/s5/v0.2/S5-ARCH-008-MVS-EXECUTION-ORCHESTRATION-OWNERSHIP-GATE-V1.md)
