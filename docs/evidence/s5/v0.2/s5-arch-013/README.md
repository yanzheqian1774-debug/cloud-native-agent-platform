# S5-ARCH-013 — Definition Publication and Matchability Authority Evidence

## Evidence identity

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-013` |
| Type | `ARCH` |
| Checkpoint | `C — TERMINAL_ARCHITECTURE_EVIDENCE_AND_HANDOFF_PREPARATION` |
| Lifecycle | `ACTIVE` |
| Baseline | `a485c5f3fb016629bf17c0fcd47c0ecd3d4c6fa3` |
| Branch | `codex/s5-arch-013-definition-publication-matchability-authority` |
| Human decision | `PASS_WITH_CONSTRAINTS` |
| Publication state | `ARCHITECTURE_COMPLETE / REVIEW_READY / AWAITING_DURABLE_INTEGRATION` |
| Terminal handoff facts | commit, push, Draft PR, and exact-head CI pending at this recording point; later facts belong in PR metadata and the terminal CONTROL response |
| Implementation status | `NOT_STARTED` |
| Architecture artifact | [`S5-ARCH-013-DEFINITION-PUBLICATION-MATCHABILITY-AUTHORITY-V1.md`](../../../../../architecture/s5/v0.2/S5-ARCH-013-DEFINITION-PUBLICATION-MATCHABILITY-AUTHORITY-V1.md) |

## Checkpoint C terminal decision evidence

The candidate formalizes the minimum internal v0.2 boundary between authoring approval
and Package 2 matching:

```text
APPROVED authoring revision
→ immutable Definition Version
→ explicit publication
→ separate scoped match authorization
→ fail-closed effective-candidate snapshot
→ read-only advisory matcher
```

It assigns distinct owners to version/catalog registration, publication decisions,
match-authorization decisions, deterministic effective projection, and matching.
`MATCHABLE` is derived for an exact tenant, security domain, purpose, and evaluation
time; it is not an authoring state. Missing, malformed, conflicting, mismatched,
expired, revoked, or unavailable authority fails closed.

The architecture records deterministic NFC canonical JSON and SHA-256 digest rules,
immutable version/provenance requirements, snapshot identity and ordering, duplicate
handling, inclusive-start/exclusive-expiry semantics, explicit predecessor replacement,
append-only decisions and Evidence, stable failure codes, and non-disclosure of denied
candidates.

Checkpoint B makes the trusted catalog supply boundary explicit. The internal Catalog
owner, not repository/build/deployment transport, accepts records only after schema,
digest, provenance, tenant/domain, replay, and conflict validation. Curated repository
records and their packaged derivatives remain traceable to exact source revisions and
Human/governance decisions; UI, fixtures, arbitrary callers, caches, Agent CRDs, and
Kubernetes state are never authority.

## Authority audit

| Stage | Authority | Checkpoint C result |
| --- | --- | --- |
| authoring | existing internal authoring authority | `APPROVED` is prerequisite only |
| versioning/catalog | future internal Definition Catalog owner | immutable exact version/digest |
| publication | separate Publication Decision owner | explicit append-only decision |
| match authorization | separate scoped authorization owner/port | grant/deny/revoke/expiry; fail closed |
| matching | Package 2 read-only consumer | advisory decision or honest `ROLE_GAP` only |
| execution | existing separately governed authorities | unaffected; match grants nothing |

Tenant and security domain are mandatory trusted bindings on versions, decisions,
requests, and snapshots. Absence or mismatch excludes the candidate without implying
global availability or disclosing denied-candidate identity.

## Scope and impact

Checkpoint C owns exactly five documentation paths:

1. `architecture/s5/v0.2/S5-ARCH-013-DEFINITION-PUBLICATION-MATCHABILITY-AUTHORITY-V1.md`
2. `docs/evidence/s5/v0.2/s5-arch-013/README.md`
3. `architecture/s5/v0.2/README.md`
4. `docs/governance/REGISTRY.md`
5. `PROJECT_STATE.md`

There is no implementation, test, public API, CRD, shared DTO, Canonical Graph,
persistence, dependency, lockfile, CI workflow, frontend, Package 2, Agent, Runtime,
REL, Demo, or Release change. S5-IMPL-030 remains
`FROZEN_PENDING_ARCHITECTURE_G2` until S5-ARCH-013 and its future REL Session are
Human-confirmed closed.

## Validation record

Checkpoint C requires and records:

- clean exact-baseline and remote-main equality before branch attachment;
- absent local/remote/worktree branch and Task-ID/PR collision;
- exactly five authorized changed paths and no other artifact;
- architecture/Evidence/index cross-link validation;
- authoring/versioning/publication/authorization/matching/execution authority audit;
- tenant/security-domain fail-closed audit;
- version/digest/supersession/expiry/revocation audit;
- prohibited-impact search;
- repository-defined non-mutating documentation checks where available;
- `git diff --check` and final uncommitted status review.

Final commit, push, Draft PR, and exact-head CI facts are intentionally not predicted in
this pre-commit repository record. They are reported only after they exist in the
terminal Checkpoint C response and unchanged PR metadata. The candidate remains subject
to Human terminal Evidence review, a separately allocated REL Session, durable
integration, and Human closure. No downstream Session is started.

## S5-IMPL-030 handoff audit

The architecture evaluates the exact seven expected candidate paths for future
Definition authority, matching, tests, Evidence, Registry, and Project State. It also
defines a path-resolution rule for equivalent existing owners and a STOP/new-Human-Gate
rule for any public, cross-plane, persistence, dependency, frontend, or CI expansion.

Existing `planning.py` and `authoring.py` are classified for reuse without modification.
Core representation and existing execution Evidence are patterns only; changing either
requires a future STOP and new Human Gate. The minimum validation matrix covers
canonical determinism, digest binding, decision separation, missing/cross-scope
rejection, UTC/effective time, replay/conflicts, supersession/revocation, snapshots,
disclosure safety, advisory matching, honest `ROLE_GAP`, and zero downstream effects.

Checkpoint C retains the exact five-path architecture scope and grants no implementation
or downstream authority. The source branch must remain present; its Draft PR must remain
open, unmerged, and not Ready.
