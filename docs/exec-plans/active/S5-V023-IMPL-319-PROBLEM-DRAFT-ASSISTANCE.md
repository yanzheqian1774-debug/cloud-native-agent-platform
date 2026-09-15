# S5-V023-IMPL-319 — Problem Draft Assistance implementation plan

## Status and authority

| Field | Value |
| --- | --- |
| Session | `S5-V023-IMPL-319` |
| Type | `G1 / PLAN_REQUIRED` |
| Task status | `ACTIVE / HUMAN_AUTHORIZED` |
| Implementation base | source `41a7fe8fc2bb7e1951ffd33b676492f6d3a6757e`; tree `88b18b57d11548593a76fdad8e461f786dd2be43` |
| Fixed dependency candidate | source `141a17ecd34ec3b721e1c8a8ae33277c4b454e42`; tree `b195b4612a4ab9f295e3c6f9a82199b05db7ac0e` |
| Governing decision | accepted `S5-V023-ARCH-318`, including its itemized Human decisions and constraints |
| Real provider gate | `PENDING / NOT_AUTHORIZED`; no credential read or provider dispatch |
| Merge, deploy, release | `NOT_AUTHORIZED` |

The bounded product journey is:

```text
problem description -> clarification -> user supplement -> structured draft
-> edit/reject/confirm -> existing formal Problem create and authorized readback
```

Draft Assistance owns only its metadata and invocation state. It does not own Model
Governance, authorization, provider effects, Resource Use, Evidence, or Business
Problem state, and it never creates an Attempt, Plan, Run, or business-success fact.

## 1. Startup and allocation result

The identifier was checked before mutation across repository content and history,
local and remote refs, branches, tags, registered worktrees, all visible GitHub PRs
and issues, and visible Codex tasks. No conflicting owner was found; the only visible
`S5-V023-IMPL-319` task is this Human-authorized task. The attachment
`S5-V023-ARCH-318-PRE-CLOSE-AND-G1-STARTER-41a7fe8-20260915.md` matched the supplied
SHA-256 `81c613c51bb125c81a53601e9c78ac21267ed6918a8c3490fe5312045cfbaf66`.

The pre-created isolated worktree was clean and has been placed on
`codex/s5-v023-impl-319-problem-draft-assistance` at the exact implementation base.

## 2. Dependency and conflict matrix

| Dependency / path | Reception | Conflict finding | Compatibility rule |
| --- | --- | --- | --- |
| `model_governance.py` domain values and ports | receive exact symbols from the fixed 308 candidate | add-only on the common ancestor | preserve Model Governance as sole owner; no Draft Assistance writes |
| `model_governance_postgres.py` | receive exact repository implementation | add-only; uses caller-owned connection support | retain exact scope/revision/digest reads and transactional readback |
| `model_binding_resolution.py` | receive exact binding/use/resolution types, then add a Draft Assistance-specific exact target builder outside the Attempt form | 308's `invoke_model_use` helper is Attempt-shaped and cannot represent ARCH-318 by substitution | do not fake `attempt_id`; use the generic `ExactModelUse` contract with the ARCH-318 exact invocation target |
| `model_governance_authorization.py` | receive authorization adapter, exact resolver, caller-owned reader/binder and target validation symbols | overlaps current authority modules only through typed interfaces | merge narrowly; do not replace current Workbench/BFF or Problem authority |
| authority contracts/PostgreSQL/grant service additions from 308 | receive only the current-decision batch/binder capability required by exact Model use | current base contains later browser authority and BFF behavior | preserve current source as authority; integrate additive methods and tests, rejecting whole-branch replacement |
| `0019_model_governance.sql` | receive under its original filename and content | current base already contains `0020` and `0022`; `0019` is absent, not applied by this task DB, and not owned by another current migration | late additive reception is explicit; do not renumber, overwrite, edit `0020`/`0022`, or use another task database; repository-specific migration remains checksum guarded |
| 308 browser harness changes | do not receive | unrelated to required Model Governance symbols | keep current base browser harness and acceptance assets |
| existing Workbench/BFF and Problem create continuation | reuse current base | 308 predates and therefore appears to delete these paths in a whole-branch diff | current base wins completely; Draft Assistance is added through new operations and coordinator ports |

No architecture/implementation drift requiring G2 was found at plan time. Any later
need to change a public CRD/API group, frozen contract, existing owner, Attempt/Task/
Workflow lifecycle, or persistent infrastructure stops implementation for escalation.

## 3. Affected components and interfaces

### Draft Assistance owner

- Add internal typed context, turn, profile revision, binding snapshot, invocation,
  append-only fact/reducer, scoped idempotency claim, dispatch admission and pending
  obligation contracts.
- Add a PostgreSQL adapter and an additive migration for non-content metadata only.
- Add HMAC-SHA-256 commitment with versioned canonicalization and a purpose-scoped
  pepper resolver. Persist only algorithm/version/reference/commitment and replay
  window; never persist raw input, output, plain digest, pepper, or credential.
- Add a coordinator that performs lookup-before-mint, atomic first-writer claim,
  two exact authorization decisions, post-allow exact Model resolution, current
  validate-and-admit, Resource Use/budget gate, credential resolution,
  persist-before-dispatch, observation/cancel and explicit-successor recovery.

### Provider-neutral boundary

- Define sealed `dispatch`, `observe`, and `cancel` ports plus a purpose-scoped
  credential resolver.
- Ship only a deterministic synthetic transport for this task. It returns strict,
  allowlisted `NEEDS_CLARIFICATION` or `DRAFT_READY` fields and exposes deterministic
  ambiguity/cancellation scenarios without any external call.

### Execution-owned Resource Use and Evidence

- Add the reader-first `ContextualResourceUseV2` union shape and PostgreSQL sibling
  family for `DRAFT_ASSISTANCE_INVOCATION` + `MODEL`; leave Attempt v1 tables and
  required fields unchanged.
- Add the versioned allowlisted
  `model-draft-assistance-invocation-evidence.v1` Evidence writer/reader boundary.
- Use stable operation IDs for B/E/F/G repair. Recovery may append only missing
  Resource Use/Evidence/reference facts and must never resolve content or credentials
  or dispatch the provider.

### Workbench and formal Problem creation

- Add Workbench operations for begin/read/resubmit/observe/cancel/reject/successor
  and provenance-link completion, with exact target builders and current disclosure
  checks.
- Replace the local title suggestion in the existing Problem conversation with the
  governed Draft Assistance journey, retaining an explicit manual fallback.
- Keep editable clarification/draft content in React memory only. Principal, scope,
  context, logout, and session changes clear volatile content and fence late results.
- `确认创建` continues to call the existing `createBusinessProblem` command and
  recovery key. The coordinator appends only an exact non-content provenance link;
  link failure never recreates the Problem.

## 4. Implementation sequence

1. Receive and validate the bounded 308 Model Governance symbols and original `0019`
   migration against current authority behavior.
2. Publish Draft Assistance, contextual Resource Use, and Evidence typed readers and
   unknown-version fail-closed projections before enabling their writers.
3. Add migrations/repositories and PostgreSQL restart/concurrency tests using the
   `S5-V023-IMPL-319`-dedicated database assets.
4. Implement authorization, HMAC, CAS, transport, observation/cancel, state reduction,
   and A-G obligation recovery with deterministic synthetic transport.
5. Compose BFF operations and the complete Chinese-first Problem Workbench flow while
   preserving the existing formal Problem create/read path.
6. Run focused unit/integration/security/restart tests, dedicated real PostgreSQL,
   frontend lint/build, native HTTPS Chromium journeys, and `make check`; inspect the
   full diff and status.
7. Commit normally, non-force push, create the sole Draft PR, and follow automatic CI
   to terminal. Do not mark Ready, merge, deploy, release, or close the Session.

## 5. Test strategy and acceptance

- Domain/repository: owner boundaries, immutable exact refs, reader-first unknown
  versions, reducer legality, no raw-content persistence, restart readback.
- Idempotency: first writer, same key/same body, different body conflict, replay after
  pepper rotation, unavailable pepper, expired window, and no orphan identities.
- Authorization: first request allow/deny, zero protected read before allow, exact
  target validation, replay disclosure current READ, revocation/expiry versus
  admission race, and zero credential/transport on denial.
- Dispatch: synchronous clarification/draft/failure, cancellation causal order,
  timeout/transport ambiguity to `OUTCOME_UNKNOWN`, observation idempotency, terminal
  conflict review, late result isolation, and explicit successor identity.
- Cross-owner recovery: every A-G interruption; Resource Use, Evidence and provenance
  completion replay without another provider invocation; formal Problem UNKNOWN
  recovery without duplicate write.
- Product: native Chromium over HTTPS covers clarification, supplement, editable
  draft, reject, cancel, manual fallback, confirm, authorized formal readback, and
  visible synthetic-versus-real-provider labeling.
- Security: database/log/error/Evidence/Resource Use scans contain no raw prompt,
  response, plain digest, HMAC, pepper, credential, secret value, or Authorization
  header.

## 6. Compatibility and risks

- All persistence is additive in the existing PostgreSQL dependency. No new database,
  CRD, public API group, or Control Plane source of truth is introduced.
- Existing Attempt Resource Use v1, formal Problem APIs, Workbench authorization,
  browser session behavior, and current routes remain compatible.
- `0019` arrives after higher-numbered files already exist in Git, so acceptance must
  prove clean install and restart of schemas both with and without prior `0020/0022`;
  no assumption is made that filename ordering is a global transaction ledger.
- The most important irreversible boundary is `DISPATCH_RECORDED`; crashes after it
  remain unknown/observable and never auto-redispatch.
- Raw content is intentionally unrecoverable on the server. Recovery requires the
  browser to resubmit the same body before first dispatch or an explicit successor.
- Exact metadata retention and production governance remain deferred. This task adds
  no automatic deletion and makes no indefinite-retention or compliance claim.
- Real provider acceptance remains pending until a separate Human-approved call
  package exists; deterministic transport cannot satisfy that gate.

## 7. Real-provider call package status

The implementation will prepare, but not execute, a package containing exact
provider/model/endpoint/profile/adapter revisions and digests, immutable synthetic
inputs, purpose-scoped credential reference, maximum two dispatches with no automatic
retry, Human-set token/cost ceilings, connect/read/total timeouts, provider data
policy, Evidence/redaction settings, acceptance criteria, and stop conditions. Until
Human approval, credential reads and real dispatches are prohibited and the gate is
reported `PENDING`.
