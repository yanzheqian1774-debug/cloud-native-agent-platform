# S5-IMPL-009 — Authoring Backend and Shared View DTO Evidence

## Session

| Field | Value |
| --- | --- |
| Session | `S5-IMPL-009` |
| Checkpoint | `A — AUTHORING_BACKEND_AND_SHARED_VIEW_DTO_CANDIDATE` |
| Authorized baseline | `cf8373d342a7b2c463468cd041527f5b6044ce38` |
| Branch | `codex/s5-impl-009-authoring-backend-shared-view-dto` |
| Final exact head | Recorded by the Draft PR exact-head gate; this in-commit artifact cannot self-reference its own Git object ID |
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
and source revision. A byte-equivalent repeated decision is idempotent; a
different repeated decision fails closed. Rejection leaves the effective
Definition unchanged. Approval supersedes other open revisions. Stale source
revision, superseded revision, empty Diff, malformed/extra/missing fields,
duplicate ambiguous values, bounded-size violations, and secret-shaped values
return stable redacted codes.

Caller mappings and sequences are normalized to frozen dataclasses and tuples.
Diff order is fixed by the owned field inventory. Revision identity is derived
deterministically from normalized content plus its source revision; it is an
internal revision, not a public version contract.

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

## Tests and audits

Focused tests cover deterministic Draft/Diff, Human approval, stale and
superseded revisions, rejection preservation, immutable repeated decisions,
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

## Limitations and claim boundaries

- in-memory lifecycle only; no durability, distribution, concurrency, or
  production publication claim;
- internal DTO semantics are version-unfrozen;
- no HTTP consumer is added because that requires the next Human Public
  Surface/DTO gate;
- no Product View UI, Technical View UI, or Golden Demo integration;
- no Runtime, Knowledge, Capability, or Outcome certification;
- no globalization, production-readiness, release, or schema-freeze claim.

## Rollback

Revert the single S5-IMPL-009 implementation commit. The five paths are new and
have no existing production consumer, public migration, dual-write, or stored
state to unwind.

## Next Human gate

Stop at the **Human S5-IMPL-009 Authoring Backend and Shared DTO Review Gate**.
Any HTTP/public DTO needed by S5-IMPL-010 or S5-IMPL-011 requires explicit
Human approval and must not be introduced through this candidate.

## References

- [S5-SPIKE-008 evidence](../s5-spike-008/README.md)
- [Core Representation/API Gate](../../../../../architecture/s5/v0.2/S5-ARCH-007-CORE-REPRESENTATION-API-GATE-V1.md)
- [MVS execution ownership gate](../../../../../architecture/s5/v0.2/S5-ARCH-008-MVS-EXECUTION-ORCHESTRATION-OWNERSHIP-GATE-V1.md)
