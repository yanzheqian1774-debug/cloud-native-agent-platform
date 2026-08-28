# S5-ARCH-013 — Definition Publication and Matchability Authority v1

## 1. Status and decision

| Field | Value |
| --- | --- |
| Session | `S5-ARCH-013` |
| Session type | `ARCH` |
| Checkpoint | `C — TERMINAL_ARCHITECTURE_EVIDENCE_AND_HANDOFF_PREPARATION` |
| Lifecycle | `ACTIVE` |
| Decision status | `APPROVED_WITH_CONSTRAINTS`; architecture complete and review-ready; durable integration and Human closure not granted |
| Implementation status | `NOT_STARTED` |
| Baseline | `a485c5f3fb016629bf17c0fcd47c0ecd3d4c6fa3` |
| Portfolio authority | `S5-PLAN-003` |
| Architecture authority | `S5-ARCH-011` and Human-accepted `ARCH-DISCUSS-004-DEF-PUBLISH-MATCH-001` Option B |
| Contract status | internal v0.2 architecture candidate; `NOT_FROZEN`; no public API, CRD, shared DTO, Graph, or persistence grant |

This decision defines the minimum truthful internal v0.2 authority required before
Package 2 can match an approved canonical Workflow revision to existing curated
Digital Employee Definition versions.

```text
authoring revision
→ APPROVED authoring prerequisite
→ immutable DefinitionVersion
→ append-only PublicationDecision
→ append-only MatchAuthorizationDecision
→ deterministic effective-candidate projection
→ read-only Package 2 matcher
→ advisory RoleMatchDecision or ROLE_GAP
```

`APPROVED` is not `PUBLISHED`. Publication is not match authorization. `MATCHABLE` is
not a stored authoring lifecycle state: it is a scoped, effective-at-read result.
Matching grants no execution, credential, permission, Agent, Runtime, Capability, or
Knowledge-access authority.

## 2. Scope and non-goals

The current internal authoring candidate can produce an approved effective revision,
and S5-ARCH-011 requires Package 2 to consume only `PUBLISHED/MATCHABLE` Definitions.
Neither source nor accepted architecture currently names the intervening publication
and match-authorization authority precisely enough for implementation. This decision
closes only that architecture gap.

In scope:

- immutable Definition Version identity and match-relevant content;
- explicit publication and unpublication/revocation decisions;
- separate scoped match authorization and denial/revocation decisions;
- deterministic effective-candidate catalog supply to Package 2;
- append-only Evidence, audit history, failure and provenance contracts;
- exact future internal S5-IMPL-030 implementation boundary.

Out of scope:

- public management APIs, CRDs or Kubernetes authority;
- a marketplace, Agent Factory, generated-role publication, or general catalog UI;
- general persistence or a Definition lifecycle service;
- policy administration, rollout/rollback management, replication, or external
  governance integration;
- Package 2 matcher implementation, Agent/Runtime creation, execution, credentials,
  Capability/Knowledge access, Canonical Graph changes, or shared DTO changes.

Full Definition lifecycle management remains v0.3 or later.

## 3. Owning internal boundary

The future internal owning module is `console/backend`'s replaceable
`agent_console.definition_authority` boundary. The name is an implementation target,
not authorization to create code in this architecture Session.

| Concern | Sole owner | Mutable action | Consumers | Forbidden competing authority |
| --- | --- | --- | --- | --- |
| Authoring | existing internal authoring authority | draft, review, approve/reject authoring revisions | Definition Version assembler | approval cannot publish or authorize matching |
| Definition Version/catalog | Definition Catalog owner inside `definition_authority` | register an immutable version and expose snapshots | publication and match-authorization owners; effective projection | UI, fixture presence, Agent CRD, Kubernetes, cache, matcher |
| Publication | Publication Decision owner inside `definition_authority` | append publish, unpublish, or revoke-publication decisions | effective projection and audit | authoring, catalog presence, matcher, UI |
| Match authorization | Match Authorization owner/port inside `definition_authority` | append grant, deny, revoke, or expiry-bearing decisions | effective projection and audit | publication, matcher, descriptor, UI |
| Effective candidates | deterministic projection owned by `definition_authority` | derive a read-only snapshot for exact scope/time | Package 2 catalog provider port | matcher-local filtering as authority, mutable cache |
| Matching | future Package 2 matcher | read projection, score eligible candidates, emit advisory decision/gap | later separately authorized packages | publication, authorization, revocation, supersession, mutation, execution |
| Execution | existing separately governed execution authorities | separately authorize and execute exact approved work | runtime/evidence boundaries | Definition publication, matchability, match result |

The catalog, publication owner, authorization owner, projection, and matcher MAY be
co-located in-process for v0.2. Logical authority and ports MUST remain separate so
co-location does not collapse decisions or prevent replacement.

### 3.1 Trusted catalog supply boundary

The Definition Catalog owner inside `agent_console.definition_authority` is the
accountable authority for accepting source records into the internal v0.2 catalog. A
repository, build, deployment package, or operator MAY transport curated records, but
transport and file presence are not authority. A record is accepted only through the
catalog owner's ingestion/validation boundary and only with one of these provenance
kinds:

- an exact approved internal authoring revision plus its trusted authoring-authority
  reference;
- a Human-governed curated repository record bound to repository revision, path,
  content digest, curator/decision reference, tenant, and security domain;
- a build or deployment derivative that preserves the exact accepted source identity,
  digest, governance decision, and immutable supply-chain provenance.

Arbitrary callers, UI submissions, demo fixtures, mutable runtime caches, Agent CRDs,
Kubernetes state, discovered files, and unverified build/deployment values are rejected
as catalog authority. Demo fixtures MAY be inputs to tests after a future authorization,
but fixture presence cannot register, publish, authorize, or make a version matchable.

The catalog owner performs schema/size/type validation, canonical serialization and
digest recomputation, source-provenance verification, exact tenant/security-domain
binding, idempotent replay detection, conflict rejection, and append-only registration
Evidence before a version becomes catalog-visible. Repository/build/deployment supply
therefore remains governed and auditable: every accepted record traces to an immutable
source revision and Human/governance decision; derived packaging cannot widen scope or
alter canonical bytes; missing or unverifiable provenance fails closed.

## 4. Definition Version contract

`DefinitionVersion` is immutable after registration and contains at minimum:

- `definition_id`: stable Definition identity;
- `version_id`: stable version identity unique within `definition_id`;
- `definition_digest`;
- `digest_algorithm`: `SHA-256` for the v0.2 candidate;
- `digest_contract_version`: `definition-match-v1`;
- immutable match-relevant content;
- curated `RoleDescriptor` with duties and required Data, Knowledge, Skill,
  Capability, and Runtime coverage metadata where applicable;
- `source_authoring_revision_id` and source-authority kind;
- `tenant_id` and `security_domain` supplied by trusted context;
- schema version, creation time, and provenance.

Match-relevant content includes every field that can affect compatibility, coverage,
risk classification, support state, authorization scope, selection, or match reasons.
Display-only localization, transport metadata, observation time, storage/cache
metadata, tracing IDs, and secrets are excluded. An excluded field MUST NOT alter
matching, authorization, or business semantics.

Registration of the same `(definition_id, version_id)` and identical canonical bytes
is an idempotent replay. The same identity with different bytes, digest, provenance,
tenant, or security domain is `CONFLICTING_DEFINITION_VERSION` and fails closed. A
registered version is never overwritten; changed semantic content creates a new
`version_id` and digest.

## 5. Canonical serialization and digest

Canonical bytes use the versioned `definition-match-v1` serialization contract:

1. UTF-8 encoding and Unicode NFC normalization for strings;
2. schema-defined field names with lexicographic object-key order;
3. no insignificant whitespace;
4. explicit JSON `null` only for schema-authorized nullable fields; missing and null
   are distinct and unauthorized unknown fields reject;
5. integers use base-10 JSON form; floating-point values are prohibited from canonical
   match content unless a later contract defines an exact decimal representation;
6. ordered semantic sequences retain declared order;
7. set-like collections are normalized, deduplicated, and sorted by their canonical
   identity before serialization;
8. timestamps use UTC RFC 3339 with a `Z` suffix and fixed precision where included;
9. `tenant_id` and `security_domain` are canonical digest inputs;
10. secrets, mutable cache values, and storage details are prohibited inputs.

`definition_digest = lowercase_hex(SHA-256(canonical_bytes))`. A consumer recomputes
the digest using the declared algorithm and contract version. Unknown algorithms,
unknown contract versions, malformed canonical content, or mismatch fail closed as
`INVALID_DEFINITION_DIGEST`; no best-effort compatibility path is allowed.

## 6. Publication contract

Publication is an explicit append-only `PublicationDecision` over exactly one
immutable Definition Version. It contains decision identity, exact Definition/version/
digest binding, tenant and security domain, decision type, actor/authority reference,
reason code, policy/version reference where applicable, `decided_at`, `effective_at`,
optional `expires_at`, and provenance.

Decision types are:

- `PUBLISH`: makes the exact version publication-effective when all validations pass;
- `UNPUBLISH`: ends future publication effectiveness at its effective time without
  deleting history;
- `REVOKE_PUBLICATION`: fail-closed safety or governance revocation, append-only and
  effective at its declared time.

`APPROVED` authoring status is a mandatory publication prerequisite but never creates
a decision. A publication owner MUST validate the exact source approval, immutable
version, digest, tenant, security domain, and decision scope. Catalog or record
presence is not publication. Publication alone grants no match eligibility or other
authority.

Exact duplicate decision identity/content is an idempotent replay. Same identity with
different content, overlapping irreconcilable effective decisions, or conflicting
bindings fail closed as `CONFLICTING_PUBLICATION_DECISION`.

## 7. Match-authorization contract

`MatchAuthorizationDecision` is a separate append-only decision over one published
Definition Version and explicit scope. It contains decision identity, exact Definition/
version/digest binding, `tenant_id`, `security_domain`, permitted match-purpose/scope,
decision, authority/policy reference, reason code, `decided_at`, `effective_at`,
optional `expires_at`, and provenance.

Decision types are `GRANT`, `DENY`, and `REVOKE`. Expiry is declared on a decision and
evaluated at read time; expiry never deletes or mutates the historical decision.
Publication cannot imply `GRANT`. A broad or absent scope cannot be inferred. Missing
tenant or security domain fails closed and never means global availability.

When multiple decisions apply to the same exact version and scope, the projection
orders them by `effective_at`, then `decided_at`, then stable decision identity. A
later effective deny or revoke overrides grant. Simultaneous contradictory decisions
that cannot be ordered uniquely yield `CONFLICTING_MATCH_AUTHORIZATION` and exclude the
candidate. The matcher cannot create or repair authorization.

## 8. Effective `MATCHABLE` contract

`MATCHABLE` is derived for one trusted query context and one evaluation instant. It is
true only when all conditions hold:

1. the Definition Version is well-formed, immutable, and its digest validates;
2. an effective `PUBLISH` exists for the exact version and scope;
3. no effective unpublication or publication revocation excludes it;
4. an effective `GRANT` exists for the exact match scope;
5. no effective denial, revocation, or expiry excludes it;
6. trusted query `tenant_id` and `security_domain` exactly equal both version and
   decision bindings;
7. no authoritative successor publication explicitly excludes the predecessor;
8. catalog snapshot validation has no missing, duplicate, or conflicting authority.

Any missing, unknown, malformed, unavailable, mismatched, expired, revoked, or
conflicting input makes `MATCHABLE` false. There is no `UNKNOWN → true` mapping.
The result is not written back as an authoring lifecycle state.

Clock input is an explicit trusted UTC `evaluation_time`. Implementations MUST reject
naive or invalid timestamps and MUST NOT use caller/model time. Inclusive start and
exclusive end semantics apply: effective when `effective_at <= evaluation_time` and,
when expiry exists, `evaluation_time < expires_at`. An `expires_at` not later than
`effective_at` is malformed. Production clock-distribution guarantees remain deferred.

## 9. Supersession and revocation

All versions and decisions remain immutable and auditable. A newer Definition Version
does not by existence, registration, approval, or publication exclude a predecessor.

Default predecessor exclusion requires an effective successor `PUBLISH` decision that:

- binds the successor exact version and digest;
- explicitly identifies the predecessor exact version and digest;
- declares `replacement_effect = EXCLUDE_PREDECESSOR_FOR_MATCH`;
- has the same exact tenant and security domain;
- is itself valid and publication-effective.

Without all bindings, both independently authorized published versions may remain
eligible. Unpublication, publication revocation, authorization denial/revocation/
expiry, and supersession affect future projections only. They never erase or rewrite
historical versions, decisions, match results, or Evidence. Matching at a later time
cannot retroactively alter an earlier snapshot or decision.

## 10. Catalog supply and snapshot contract

Package 2 consumes an `EffectiveDefinitionCatalogProvider` read port. The request binds
trusted `tenant_id`, `security_domain`, match purpose/scope, evaluation time, and the
approved canonical Workflow revision identity/digest. The response is one immutable
`EffectiveDefinitionCatalogSnapshot` containing:

- `snapshot_id` and `snapshot_contract_version`;
- exact request scope and evaluation time;
- ordered eligible Definition Version records with exact digests and provenance;
- authority decision/Evidence references sufficient for audit without leaking denied
  candidates;
- source catalog generation/reference and completeness status;
- limitations and stable failure when a complete authoritative result is unavailable.

The snapshot ID is a domain-separated SHA-256 digest over snapshot contract version,
scope, evaluation time, source generation, and the ordered canonical identities,
digests, and effective decision references. Eligible candidates are sorted by
`definition_id`, then `version_id`, then `definition_digest`. Input order cannot affect
snapshot bytes or ID.

`evaluation_time` is fixed once by the trusted catalog projection boundary and copied
unchanged into the snapshot and subsequent Package 2 request/decision. It MUST be an
aware UTC value encoded with `Z`; naive timestamps, non-UTC offsets, caller/model time,
or time changes during one projection fail closed. `source_authority_revision` binds
the exact accepted catalog generation and decision set used to build the snapshot.

Exact duplicate records collapse only when their complete canonical bytes and
provenance bindings match. Conflicting duplicates fail the complete snapshot closed;
they are not silently dropped or tie-broken. Denied or mismatched candidates contribute
no score, rank, reason detail, count, title, identity, or existence disclosure to the
matcher.

Mutable caches MAY optimize a future implementation but are never authority. A cache
entry must bind the complete snapshot request and source generation, and stale,
partial, or unverifiable cache state fails closed.

## 11. Package 2 consumption and failure contract

Package 2 is a read-only consumer. It MAY request one effective snapshot, validate the
snapshot contract, deterministically score eligible candidates against exact
`RoleRequirement` values, and emit an append-only advisory `RoleMatchDecision` or
`ROLE_GAP`. It MUST NOT publish, unpublish, authorize, deny, revoke, supersede, mutate,
or generate a published Definition; create an Agent or Runtime; grant credentials,
permissions, Capability invocation, or Knowledge access; or turn a match into execution
authority.

Minimum stable fail-closed outcomes are:

| Condition | Outcome |
| --- | --- |
| authority/provider missing | `DEFINITION_AUTHORITY_MISSING` |
| digest or canonical version invalid | `INVALID_DEFINITION_DIGEST` |
| malformed version/decision/snapshot | `MALFORMED_AUTHORITY_RECORD` |
| no effective publication | `DEFINITION_UNPUBLISHED` |
| publication revoked/unpublished | `PUBLICATION_NOT_EFFECTIVE` |
| match authorization absent | `MATCH_AUTHORIZATION_MISSING` |
| authorization denied | `MATCH_AUTHORIZATION_DENIED` |
| authorization revoked | `MATCH_AUTHORIZATION_REVOKED` |
| authorization expired | `MATCH_AUTHORIZATION_EXPIRED` |
| tenant differs or is absent | `TENANT_SCOPE_MISMATCH` |
| security domain differs or is absent | `SECURITY_DOMAIN_SCOPE_MISMATCH` |
| duplicate/conflicting authority | `CONFLICTING_AUTHORITY_RECORDS` |
| catalog unavailable, partial, or unverifiable | `DEFINITION_CATALOG_UNAVAILABLE` |
| valid snapshot but no candidate covers required role | `ROLE_GAP` |

Authority failures block matching; they MUST NOT be downgraded to `ROLE_GAP` because
that would hide an unavailable or invalid authority. `ROLE_GAP` is valid only after a
complete authoritative snapshot contains no eligible sufficient candidate. It grants
nothing and cannot create, publish, or execute a Role.

## 12. Evidence and provenance

The future boundary emits append-only, secret-safe Evidence for version registration,
publication/unpublication/revocation, match grant/deny/revoke/expiry evaluation,
supersession effect, snapshot assembly, and Package 2 consumption. Evidence binds exact
record and decision identities, digests, tenant/security domain, scope, evaluation
time, result/reason, policy/source versions, and snapshot identity.

Evidence records facts and decisions; it is not catalog, publication, authorization,
matching, execution, Graph, or policy authority. Historical snapshots and match
decisions retain their exact Evidence references. Raw credentials, secrets, model
prompts, unrestricted metadata, and denied-candidate identifying details are excluded.

## 13. Exact future S5-IMPL-030 boundary

Only after S5-ARCH-013 and its future REL Session are Human-confirmed closed may a
separately authorized S5-IMPL-030 consume this architecture. Its maximum boundary is:

- internal immutable record types for Definition Version, publication decisions,
  match-authorization decisions, supersession bindings, and effective snapshots;
- an in-memory curated v0.2 catalog/reference provider and replaceable
  `EffectiveDefinitionCatalogProvider` read port;
- deterministic canonicalization, digest verification, time/scope evaluation,
  conflict handling, snapshot assembly, and append-only in-memory Evidence;
- focused internal tests for the contracts and failures above;
- Package 2 integration only through the read port after its own authorization.

S5-IMPL-030 MUST NOT implement a public API, CRD, shared DTO, Canonical Graph change,
general persistence, frontend, dependency, CI workflow, marketplace, policy admin,
generated-role publication, Agent/Runtime creation, or full Definition lifecycle. It
remains `FROZEN_PENDING_ARCHITECTURE_G2` in this Checkpoint.

### 13.1 Candidate paths and resolution rule

The expected maximum implementation/evidence/governance path candidates are:

1. `console/backend/src/agent_console/definition_authority.py`
2. `console/backend/src/agent_console/matching.py`
3. `console/backend/tests/test_definition_authority.py`
4. `console/backend/tests/test_matching.py`
5. `docs/evidence/s5/v0.2/s5-impl-030/README.md`
6. `docs/governance/REGISTRY.md`
7. `PROJECT_STATE.md`

These paths are handoff candidates, not current mutation authorization. Before any
future implementation, S5-IMPL-030 MUST resolve them read-only against the then-current
repository. If an equivalent owning module or test path already exists, it MUST reuse
that path and report the exact substitution at its entry gate. If satisfying the
contract requires any additional public API, CRD, shared DTO, Canonical Graph,
persistence, frontend, dependency, CI workflow, or cross-plane path, S5-IMPL-030 MUST
STOP for a new Human Gate. Ordinary package `__init__` export changes are not assumed
or authorized; implementation should use direct internal module imports unless its
future Gate explicitly adds an export path.

### 13.2 Existing authority reuse

| Existing boundary | Classification | Future rule |
| --- | --- | --- |
| `console/backend/src/agent_console/planning.py` | reused without modification | consume exact canonical Workflow revision identity/digest and matching eligibility; do not change planning lifecycle |
| `console/backend/src/agent_console/authoring.py` | reused without modification | consume exact approved source revision as publication prerequisite; do not reinterpret `APPROVED` or add publishing there |
| Core representation | referenced as an identity/compatibility pattern only | no Core type, schema, public contract, CRD, or shared DTO change; any required change is STOP/new Human Gate |
| existing execution Evidence | referenced as append-only and secret-safe pattern only | Definition authority emits separate internal Evidence; no execution Evidence schema or execution authority change; any required change is STOP/new Human Gate |

### 13.3 Minimum S5-IMPL-030 validation matrix

| Area | Minimum proof |
| --- | --- |
| canonical determinism | reversed map/set input and NFC-equivalent strings produce byte-identical canonical content and digest; locale, floats, unknown fields, and ambiguous arrays reject |
| exact digest binding | algorithm/schema/version/content/scope substitution rejects before catalog visibility |
| publication/authorization separation | approval without publication, publication without grant, and grant without effective publication are never matchable |
| missing scope | absent tenant, security domain, purpose, or trusted scope rejects without global fallback |
| isolation | cross-tenant and cross-security-domain candidates are excluded before scoring with no disclosure |
| UTC and effective time | fixed aware UTC time, inclusive start, exclusive expiry; naive/non-UTC/invalid intervals reject |
| replay and conflict | exact replay is idempotent; identity/content conflicts and unordered contradictory decisions fail closed |
| lifecycle decisions | supersession requires explicit replacement; unpublication and publication/authorization revocation or expiry exclude future snapshots while history remains immutable |
| snapshot determinism | input permutation yields identical ordered candidates and snapshot ID; source revision and decisions are exact |
| disclosure safety | denied/cross-scope candidates affect no rank, reason detail, count, title, identity, or existence response |
| advisory match | successful match grants no Agent, Runtime, credential, permission, Capability, Knowledge, or execution authority |
| honest gap | complete valid empty/insufficient catalog yields `ROLE_GAP` without role creation; authority failure never becomes gap |
| zero downstream effects | authority evaluation and matching make no Kubernetes, provider, Runtime, Capability, Knowledge, network, persistence, or frontend call |

## 14. Security and authority audit

| Threat | Required behavior |
| --- | --- |
| approval treated as publication | reject; require an exact publication decision |
| publication treated as match grant | reject; require a separate exact scoped grant |
| missing tenant/domain treated as global | reject without candidate disclosure |
| digest substitution or algorithm downgrade | recompute exact supported digest; fail closed |
| stale cache restores revoked candidate | cache is non-authoritative; validate generation and decisions at snapshot time |
| denied candidate influences rank/count | exclude before scoring and disclose no identity or existence |
| conflicting duplicate silently selected | fail complete snapshot closed |
| newer version silently replaces predecessor | require explicit effective replacement binding |
| matcher mutates catalog or authorization | no write port exists at the matcher boundary |
| match grants execution or access | advisory result only; later authorities independently decide |
| UI/fixture/CRD/Kubernetes state becomes authority | reject; only named internal owners supply decisions |

## 15. Compatibility and deferred scope

This is an additive internal architecture boundary. It changes no current application
behavior, public API, Kubernetes API group, Agent/Task/Workflow CRD, Workflow lifecycle,
shared DTO, Canonical Graph, persistence, frontend, dependency, lockfile, or CI workflow.
Current source remains implementation authority; accepted architecture remains design
authority. Historical closed Sessions are not reopened.

Deferred to v0.3 or later are public management APIs, persistent lifecycle services,
policy administration, generalized tenant governance, rollout/rollback operations,
cross-service/frozen contracts, replication and consistency architecture, external
governance integration, marketplace/catalog operations, and full Definition lifecycle
management.

## 16. Validation and next gate

Checkpoint C revalidates exactly the five authorized architecture,
Evidence, index, Registry, and Project State paths; audit all six authority stages;
verify fail-closed scope, digest, time, expiry, revocation, supersession, snapshot, and
failure semantics; search for prohibited implementation implications; validate links;
run the full repository checks, all-files pre-commit hooks, and `git diff --check`;
verify the exact commit topology, Draft PR, and exact-head CI; and leave the source
branch present, open, unmerged, and awaiting a separately authorized durable integration.

Checkpoint C does not start S5-IMPL-030, Package 2, REL, Demo, Release, or any other
downstream Session. The next gate is the Human S5-ARCH-013 Terminal Evidence Review
and REL Allocation Decision.
