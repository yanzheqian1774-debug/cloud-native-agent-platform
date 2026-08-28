# S5-IMPL-030 Checkpoint C Terminal Implementation Evidence

## Decision and scope

- Session: `S5-IMPL-030` — Curated Descriptor and Published-Role Matcher.
- Gate: Checkpoint C, `PASS_WITH_CONSTRAINTS`.
- Durable baseline and HEAD: `8757adabc9a95e3b3934303fa9c6f8586ff854e9`.
- Branch: `codex/s5-impl-030-curated-descriptor-published-role-matcher`.
- Worktree: `/Users/tristan/.codex/worktrees/5bfc/cloud-native-agent-platform`.
- State before terminal commit: active, implementation-complete, review-ready,
  uncommitted, and unmerged; durable integration is not authorized.

Exactly seven paths are changed: two internal implementation modules, two focused
test modules, this Evidence file, the Governance Registry, and Project State.
There is no public API, CRD/schema, workflow lifecycle, shared DTO, Canonical
Graph, general persistence, dependency/lockfile, workflow CI, or frontend change.

## Definition authority

`definition_authority.py` implements an internal, in-memory trusted authority.
Immutable Definition Version records bind exact identity, canonical digest,
curated descriptor content, approved authoring provenance, tenant, security
domain, schema, and UTC creation time. Approval is only a prerequisite and never
implies publication.

Publication and match authorization are independent append-only decision streams.
Publication supports publish, unpublish, revocation, expiry, and explicit
successor exclusion. Match authorization supports grant, deny, revoke, and
expiry. Decisions bind their exact Definition Version and scope, authority,
policy/reason, UTC times, decision identity, and replay identity. Byte-identical
replay is idempotent; substituted or conflicting identity fails closed.

Effective catalog snapshots are immutable, scope-exact, purpose- and
workflow-bound, fixed-time projections. Their stable identity covers the contract,
source-authority revision, eligible Definition identities and digests, and exact
publication/authorization references. A newer version alone does not remove a
predecessor; only an effective successor publication with
`EXCLUDE_PREDECESSOR_FOR_MATCH` does so.

## Published-role matcher

`matching.py` consumes only `EffectiveDefinitionCatalogProvider` snapshots. It
validates the governed snapshot identity and candidate digests, compares typed
curated descriptor coverage, and deterministically selects or ties existing
eligible Definition Versions. Input task, requirement, set-like value, and
candidate ordering do not affect results.

The result is advisory and explicitly non-executable. It cannot publish,
authorize, mutate, create Agents or Runtimes, or grant credentials, permissions,
Capabilities, or Knowledge access. Valid authority with no covering candidate
returns `ROLE_GAP`; missing or invalid authority remains a distinct failure.
Denied and cross-scope candidates expose no identity, title, count, rank, policy
reason, or existence detail.

## Boundary and behavior evidence

Focused tests prove rejection without truncation or partial matching at:

- 32 accepted / 33 rejected Tasks;
- 32 accepted / 33 rejected requirements per Task;
- 64 accepted / 65 rejected authorized candidates per requirement;
- 2,048 accepted / 2,049 rejected candidate evaluations;
- 32 accepted / 33 rejected stable reasons;
- 200 accepted / 201 rejected identifier characters;
- 500 accepted / 501 rejected semantic text characters;
- 32 KiB accepted / 32 KiB + 1 byte rejected serialized request payload.

Tests also cover NFC and canonical serialization determinism, digest substitution,
publication/authorization separation, UTC-only timestamps, effective-time and
expiry behavior, replay and conflict handling, tenant/security-domain isolation,
unpublication, revocation, supersession, snapshot permutation and identity,
disclosure-safe failures, stable matching and ties, honest `ROLE_GAP`, authority
failure separation, and zero downstream side effects.

## Checkpoint B semantic and security audit

Checkpoint B reviewed the complete implementation against all 31 Gate conditions and
made bounded fail-closed corrections inside the original code/test paths:

- Definition and decision records are fully revalidated at the trusted ingestion
  boundary even when directly instantiated instead of created through helpers.
- Publication and match-authorization decisions explicitly bind the Definition's
  source-authority revision; replay substitution across versions, source revisions,
  or match purposes fails closed.
- Unicode-normalized duplicate map keys and floating-point canonical inputs reject as
  ambiguous, while genuinely ordered sequences retain order and curated set-like
  fields remain permutation-independent.
- Simultaneous contradictory authority decisions fail the complete projection closed.
- Snapshot reconstruction rejects missing, added, reordered, identity-substituted, or
  decision-reference-substituted candidates.
- Directly instantiated matcher requests and requirements receive the same identifier,
  semantic-field, ordering, duplication, payload, and reason validation as helper-built
  inputs.

The Matcher retains only the catalog-provider read port. It imports neither planning,
authoring, Core representation, nor execution Evidence, and it invokes no authority
write, Provider, Runtime, credential, permission, Capability, Knowledge, persistence,
network, Kubernetes, or frontend operation.

## Checkpoint C handoff

The complete Checkpoint B implementation and all accepted fail-closed boundaries were
revalidated before commit. The authorized handoff uses no more than two commits whose
first parent is the exact baseline. The branch may be pushed only normally and the
single pull request must remain open, Draft, and unmerged against `main`.

Repository Evidence records exact-head CI as pending because it is created before the
final commit and CI observation. The unchanged Draft PR description and terminal
CONTROL response may record the later exact-head result. No merge, Durable Integration,
Human closure, Package 3, REL, Golden Demo, or Release authority is claimed here.

## Validation

- `uv run pytest console/backend/tests/test_definition_authority.py console/backend/tests/test_matching.py`:
  `37 passed`.
- Focused `uv run ruff check` for all four code/test files: passed.
- Focused `uv run ruff format --check` for all four code/test files: passed;
  four files already formatted.
- Pre-hook `make check`: passed; repository Ruff lint/format passed and `790 passed`
  with one existing Starlette/httpx deprecation warning.
- `uv run pre-commit run --all-files`: Ruff lint, Ruff format, and pytest hooks passed;
  hooks introduced no out-of-scope path.
- Post-hook `make check`: passed; repository Ruff lint/format passed and `790 passed`
  with the same existing warning.
- `git diff --check`: passed.
- Exact seven-path, unexpected-untracked-file, prohibited-impact, unchanged planning,
  unchanged authoring, unchanged Core, and zero-downstream-import audits: passed.

No commit, push, PR, exact-head CI, Checkpoint C, or downstream Session was created or
started before this terminal handoff gate. Exact terminal Git and PR evidence is
reported by the unchanged Draft PR and CONTROL response.
