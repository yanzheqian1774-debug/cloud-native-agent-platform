# S5-V023-IMPL-314 — OpenClaw Production Transport and Explicit Assembly, Batch A

## Task carrier

- Type: `IMPL / Runtime Integration / G1`
- Lifecycle: `ACTIVE / AUTHORIZED / SESSION_OPEN`
- Human scope: Batch A only; production Transport and explicit assembly
- Fixed source: `f189212232fc194859a695f0307e83b0c7b73c0f`
- Fixed tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`
- Branch: `codex/s5-v023-impl-314-openclaw-production-transport`
- Worktree: `/Users/tristan/.codex/worktrees/3198/cloud-native-agent-platform`
- Pull request: `#169 / DRAFT`

The fixed source and tree equal the prior read-only preparation baseline and the
freshly fetched `origin/main` at allocation time. No changed implementation
baseline is substituted.

## Allocation evidence

A fresh global suffix audit covered repository content, local and remote refs,
commit subjects, GitHub pull requests and issues, current Codex tasks, and the
available archived Codex task page. `S5-V023-IMPL-314` had no prior allocation.
This task allocates exactly that identifier and does not reopen `S5-IMPL-080` or
`S5-V023-IMPL-230`.

## Goal

Implement the exact-version production OpenClaw Gateway transport for the
accepted `external-single-gateway-isolated-agent-workspace` profile, explicitly
assemble it through the existing provider, lifecycle adapter and runtime provider
factory, and make the production operator startup entry execute that assembly.

## Fixed target

The authoritative target remains
`manifests/acceptance/openclaw/openclaw-2026.7.1-2.json`:

- npm package: `openclaw@2026.7.1-2`;
- tag commit: `0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c`;
- npm integrity:
  `sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g==`;
- Node constraint:
  `>=22.22.3 <23 || >=24.15.0 <25 || >=25.9.0`;
- profile: `external-single-gateway-isolated-agent-workspace`.

The allocation host reported Node `v22.23.1`. No OpenClaw upgrade, container
digest, Native substitution, or abbreviated integrity is permitted.

## G1 boundary and interfaces

This is G1 because it adds a production external-runtime transport and meaningful
cross-module bootstrap behavior behind existing internal interfaces. It does not
change a public CRD/API, Kubernetes API group, frozen Contract, authentication
architecture, persistence authority, or Runtime lifecycle semantics.

The explicit connection path is:

```text
published Runtime Profile projection
  -> exact manifest and installed npm-lock preflight
  -> authenticated fixed OpenClaw Gateway RPC transport
  -> OpenClawRuntimeProvider
  -> OpenClawRuntimeApplicationAdapter
  -> RuntimeProviderFactory.create(("openclaw",))
  -> agent_operator.main.startup
```

The external Gateway remains externally owned. Provider lifecycle operations map
to no OpenClaw object in this checkpoint. The accepted architecture permits an
OpenClaw Agent or Session to be an opaque native realization, but it does not make
either mapping automatic. In particular, `sessions.patch(archived=true)` plus
`sessions.delete(deleteTranscript=true)` is not accepted as Platform `STOP`.
Production `start`, `observe_runtime`, `stop`, and `replace` therefore return
`RUNTIME_LIFECYCLE_UNSUPPORTED` until the Human decisions below are resolved. They
do not start, stop, restart, or claim ownership of the Gateway process.

## Recovered checkpoint and implementation state

- Checkpoint 1 exists at commit
  `8a058d293ab0db196402e3b6ece1c9d0c22a13f0` with tree
  `3d7f75f929ad9a5ec84f8c0c804b83dece2d07fa`.
- The original worktree and branch are intact at the paths recorded above. The
  implementation diff was recovered there; the interrupted hook exit code is
  `UNKNOWN` and is not represented as success.
- Recovery copies contain only the tracked patch and the two then-untracked Python
  sources. Credential-bearing client configuration and raw Gateway logs were
  excluded.
- No corresponding remote branch or Draft PR existed at recovery time.

## Lifecycle mapping audit

| Object / operation | Exact mapping and authority | Identity, ownership, idempotency and recovery | Deletion / irreversible impact |
| --- | --- | --- | --- |
| Platform Runtime Instance | Stable Platform lifecycle identity from the accepted Placement/desired command; never minted by OpenClaw | Platform identity remains authoritative; provider handles are correlations only | None in Batch A |
| OpenClaw agent | One externally preconfigured agent selected by `agentId` and verified through `agents.list` | External owner provisions it; one agent may serve multiple Runtime Instances; Batch A neither creates nor adopts ownership | No agent mutation or deletion |
| Workspace | Exact filesystem path reported for that external agent | Externally provisioned and compared to the configured absolute path; it is not a Runtime Instance | No workspace mutation or deletion |
| Session | Candidate opaque native realization or execution context only; no accepted Runtime lifecycle mapping yet | A deterministic key could correlate scope/Runtime/Placement/generation, but key shape alone does not prove ownership or safe restart recovery | Archive and transcript deletion are not authorized |
| External Gateway | One shared external process and RPC endpoint | Gateway URL is reduced to an opaque digest; readiness is a shared dependency fact, not per-Runtime liveness | Operator never starts, stops, replaces or deletes it |
| `START` | `UNSUPPORTED_PENDING_HUMAN_DECISION` | `sessions.create` is a possible mapping, but create/adopt ownership and replay semantics are not accepted | No effect issued |
| `OBSERVE` | Shared Gateway, version, authentication, agent and workspace checks are supported; per-Runtime observation is unsupported | Gateway readiness cannot be normalized as one Runtime Instance `RUNNING` | Read-only checks only |
| `STOP` | `UNSUPPORTED_PENDING_HUMAN_DECISION` | Session archive/delete is not automatically graceful Runtime stop; adopted-session ownership cannot be proven from current durable facts | Transcript deletion would be irreversible and is prohibited |
| `REPLACE` | `UNSUPPORTED_PENDING_HUMAN_DECISION` | Delete/recreate session is not an accepted realization replacement or durable recovery protocol | No effect issued |

Contract basis: accepted S5-ARCH-002 permits a Provider to translate only declared
lifecycle capabilities and to remove only Provider-owned realizations; accepted
S5-ARCH-019 permits adapters to support a subset and requires destructive ambiguity
to fail as recovery-required. S5-IMPL-080 and S5-V023-IMPL-230 implement typed
provider/adapter seams, but do not accept a concrete OpenClaw RPC-to-Platform
lifecycle equivalence.

## Exact write scope

Production:

- `runtime/src/agent_runtime/providers/openclaw/production_transport.py`
- `runtime/src/agent_runtime/providers/openclaw/models.py`
- `runtime/src/agent_runtime/providers/openclaw/provider.py`
- `runtime/src/agent_runtime/providers/openclaw/__init__.py`
- `operator/src/agent_operator/runtime_provider_bootstrap.py`
- `operator/src/agent_operator/main.py`

Tests and delivery records:

- `runtime/tests/openclaw/test_production_transport.py`
- `operator/tests/test_runtime_provider_bootstrap.py`
- `operator/tests/test_operator.py`
- `docs/engineering/S5-V023-IMPL-314-OPENCLAW-PRODUCTION-TRANSPORT.md`
- `docs/evidence/s5/v0.2/s5-v023-impl-314/README.md`
- `docs/governance/REGISTRY.md`

## Coordination with 299, 305 and 308

| Task | Active ownership | Shared dependency | File overlap with 314 production scope |
| --- | --- | --- | --- |
| S5-V023-IMPL-299 | Business Workbench and later execution/result experience | consumes future execution/runtime facts | none |
| S5-V023-IMPL-305 | trusted session, CSRF, exact authorization and public BFF | future authorized command source | none |
| S5-V023-IMPL-308 | Model Governance, resolver and Model authorization | future exact model binding | none |

This task is the sole writer for the runtime/operator bootstrap and provider
registration paths above. It will not merge any of the three branches. Their
Console bootstrap work is a future consumer/dependency, not an input to Batch A.

## Concrete open contracts

1. Runtime Profile remains declaration-only and does not freeze a syntax for
   `openClawPackageRef`. Batch A validates the selected provider and uses the
   accepted manifest plus installed npm lock as package authority; it does not
   create a new public package-reference syntax.
2. Runtime Profile `secretReferences` are opaque and no new runtime credential
   resolver Contract is accepted. Batch A requires one declared
   `secret-ref:openclaw-gateway` and reuses Kubernetes `secretKeyRef` projection
   into the single allowlisted `OPENCLAW_GATEWAY_TOKEN` process slot. It creates
   no new authentication vocabulary or secret persistence.
3. Agent/workspace provisioning ownership for the external profile remains
   external. Batch A verifies the configured agent identity and exact workspace
   before lifecycle effects; it does not upload arbitrary configuration.
4. There is no accepted production dispatch claim, execution recovery, or
   terminal Evidence/Outcome path for OpenClaw. Production `execute` and
   `observe_execution` therefore fail explicitly as unsupported in Batch A.

If implementation requires resolving any of these by changing authentication,
public API, lifecycle ownership, persistence authority, or cross-plane ownership,
work stops at a G2 proposal.

## Implementation plan

1. Add a bounded CLI-backed Gateway RPC transport. Validate Node, installed
   package lock, executable version/tag commit, client config, server version,
   authenticated health, method response shape, configured agent identity and
   workspace before lifecycle effects. Use fixed RPC method allowlists, bounded
   JSON, timeouts, a minimal subprocess environment, and sanitized errors.
2. Keep lifecycle and execution operations explicitly unsupported while the
   concrete native-realization mapping is unaccepted. Distinguish missing
   configuration, authentication failure, Gateway unavailability and protocol
   failure. Never fallback to Native.
3. Add production bootstrap parsing for one published Runtime Profile revision,
   resolve the one allowed Secret Reference using the existing Kubernetes Secret
   projection, assemble Transport -> Provider -> Adapter -> Factory, and call it
   from the operator startup entry.
4. Add focused unit/integration tests, then reuse the already-running exact-version
   task-owned Gateway without a model task or duplicate process. Verify the bounded
   live facts that can be recovered; report missing authentication material and
   unrecoverable prior command results as `UNKNOWN`.
5. Run repository quality gates, inspect diff/status, commit normal checkpoints,
   non-force push, and publish a Draft PR.

## Acceptance tests

- production startup selects and retains the OpenClaw application adapter through
  the production transport;
- version, tag commit, npm integrity, Node, profile, config and workspace mismatch
  fail before lifecycle effects;
- missing configuration, authentication failure, unavailable Gateway and malformed
  protocol output have distinct stable codes;
- missing/ambiguous/unknown providers never fallback to Native;
- secrets and raw Gateway payloads are absent from errors, logs and public
  observations;
- start/observe/stop/replace fail explicitly without issuing effects until the
  lifecycle mapping is Human-approved;
- live validation proves exact package, authenticated Gateway readiness and
  controlled lifecycle only, with zero model tasks.

## Out of scope

External model invocation; production execution dispatch or continuous execution
observation; dispatch claims; persistent recovery; terminal Evidence/Outcome;
trusted browser execution; public API/CRD/auth vocabulary; 299/305/308 business
logic; and any 309 environment operation remain excluded.

## PROPOSED contract A — Runtime Instance native realization

Status: `PROPOSED / NOT_ACCEPTED / NOT_IMPLEMENTED`. This comparison does not alter
the accepted lifecycle or authorize any OpenClaw write RPC.

| Candidate | Benefit | Blocking defect |
| --- | --- | --- |
| OpenClaw agent only | Strong agent/workspace identity and simple observation | Agent is long-lived configuration, not generation-scoped execution context; it cannot represent restart/replace or transcript boundaries safely |
| OpenClaw session only | Natural generation and transcript correlation | Session does not prove agent/workspace/file/credential isolation or ownership; archive/delete is not Runtime stop |
| Agent/workspace plus session | Separates isolation host from generation context and retains both correlations | Requires explicit create/adopt proof, durable two-part correlation and verified drain semantics |

Recommendation: use the combination. One Platform Runtime Instance binds exclusively
to one OpenClaw agent and its attested workspace; each Runtime Instance generation
binds to one OpenClaw session. The shared Gateway is only a dependency correlation.
An OpenClaw agent serving multiple Runtime Instances remains a future candidate and
is not accepted by this proposal; it requires independent proof that workspace,
memory, files, credentials and context are partitioned as strongly as the exclusive
mapping.

The proposed invariant is:

```text
(namespace, security_domain, runtime_instance_id)
  -> exclusive agent_id + workspace_attestation
  -> generation
  -> session_id/session_key + ownership_nonce
```

- Platform generation and OpenClaw session are different identities. Platform
  generation is a durable monotonically advancing reconciliation identity owned by
  the Platform. An OpenClaw session is one opaque native correlation selected for
  that generation. Session creation, reset, archive or deletion never mints or
  advances Platform generation, and one generation never silently adopts a session
  correlated to another generation.
- Files are scoped to the Runtime Instance workspace. Across generation replacement,
  the recommended default is to retain the same exclusive workspace and its files;
  a successor workspace or writable overlay is used only when an explicit
  replacement decision requests workspace isolation/reset. No file is copied merely
  because a new session exists. The exact overlay/snapshot mechanism is unresolved.
- Durable Memory References, when explicitly bound, survive generation replacement;
  session-local memory and implicit agent-global memory do not. No current State
  Contract defines export, merge or migration, so any other memory inheritance is
  `UNRESOLVED / NO_IMPLICIT_INHERITANCE`.
- Credentials remain opaque Platform Secret References, resolved only for the exact
  scope and projected into the bounded provider process/invocation slot. A successor
  generation re-resolves the reference and never inherits credential values from the
  predecessor process, agent, workspace, session or transcript.
- Session context is generation-scoped and is not inherited. Cross-generation
  context requires an explicitly authorized, normalized Context or State/Memory
  Reference. Reusing a session or transcript as implicit context inheritance is
  prohibited.
- `CREATE` is permitted only when the provider supports a bounded idempotent agent or
  session create operation. `ADOPT` requires a durable Platform ownership nonce and
  exact scope/Runtime Instance/agent/workspace attestation match; matching name or
  path alone is insufficient. Externally owned objects without that proof remain
  connected dependencies and cannot be deleted by the Platform.
- `START` persists the desired command and idempotency key, observes first, then
  creates or adopts the exclusive agent/workspace and generation session. Success is
  recorded only after both correlations are re-observed.
- `OBSERVE` verifies agent identity, workspace attestation, session correlation,
  generation and freshness separately from shared Gateway health/readiness.
- `STOP` first blocks new dispatch, drains/cancels accepted work through a separately
  accepted operation, and observes no in-flight work. Only then may Platform state be
  `STOPPED`. Session archive is an optional post-stop retention action, not stop
  evidence; transcript deletion is never part of Runtime lifecycle.
- `REPLACE` creates a successor generation/session and correlation, observes it, then
  retires the predecessor. It preserves the predecessor transcript and correlation;
  agent/workspace replacement occurs only when the failed isolation host requires it.
- Transcript is controlled provider-native raw material. It is not assumed immutable
  and does not directly become formal Platform Evidence. Archive changes native
  discoverability only. Deletion requires a distinct authorized retention/privacy
  command and is never part of Runtime stop.
- On restart the reconciler loads the durable correlation and ownership proof,
  observes before effect, and resumes only on an exact match. Timeout, conflicting
  ownership, duplicate matches, missing ownership proof or an effect that may have
  occurred returns `RECOVERY_REQUIRED`; it is never blindly retried or deleted.

Until this proposal passes a Human G2 gate and OpenClaw proves the required bounded
operations, production `start`, `observe_runtime`, `stop` and `replace` remain
`RUNTIME_LIFECYCLE_UNSUPPORTED`.

### Fixed-version RPC evidence classification

This classification is combination-scoped to OpenClaw `2026.7.1-2` at commit
`0790d9f`; source presence is not execution or lifecycle proof.

| Classification | RPC/capability | Exact evidence and permitted claim |
| --- | --- | --- |
| Fixed version, authenticated and live-proven | `health`, `status`, `agents.list` | Batch A executed only these read-only calls; they proved authenticated Gateway health, exact runtime version and configured agent/workspace observation |
| Fixed-version source support only | `agents.create`, `agents.update`, `agents.delete`; `sessions.list`, `sessions.get`, `sessions.describe`, `sessions.resolve`, `sessions.create`, `sessions.patch`, `sessions.abort`, `sessions.delete`; `chat.abort` | The installed fixed package registers handlers/client calls and method scopes. Batch A did not invoke them and does not claim response semantics, idempotency, ownership, drain, terminal observation or Platform lifecycle equivalence |
| Current Platform production transport unsupported | all preceding agent/session/chat write or lifecycle calls; execution dispatch and observation | The allowlist remains exactly `health`, `status`, `agents.list`; `start`, `observe_runtime`, `stop`, `replace`, `execute` and `observe_execution` fail closed without effects |
| Not established by fixed source or Batch A | external exactly-once; transactional agent+session creation; durable Platform idempotency acceptance; atomic replace; activity-free/drained proof; graceful Runtime stop; transcript immutability | No such claim may be inferred from an RPC name or handler registration |

### Ownership proof and external association

Recommended durable Platform record fields are the exact Platform scope, Runtime
Instance ID, Platform generation, agent ID, canonical workspace reference and
attestation digest, session key/ID when known, an unguessable ownership nonce digest,
provider/package version, create/adopt mode, desired-command ID/idempotency key,
observation high-water and timestamps. PostgreSQL remains the accepted owner of these
Product identities and correlations; provider objects remain external facts.

For a Platform-created object, the provider must place the Platform correlation and
ownership nonce, or a verifiable digest of them, into a fixed-version native metadata
surface proven suitable for lookup. For an externally created object, an authorized
external owner must attach the same proof before adoption. If the fixed version has
no bounded metadata field that is preserved and queryable, adoption is unsupported;
agent name, session key, filesystem path and mere existence are insufficient.

The exact native metadata field, nonce encoding, session-key format and PostgreSQL
schema are not determined by existing contracts and require Human acceptance plus a
separate implementation allocation.

### Partial success, timeout and recovery

There is no claim of an external exactly-once transaction. The recommended protocol
is append desired command first, observe, issue at most one authorized effect for the
current recovery decision, append the returned native correlation when available,
then re-observe before convergence.

| Condition | Recommended normalized result | Recovery rule |
| --- | --- | --- |
| Agent exists with exact ownership proof; session absent | `PARTIAL / RECOVERY_REQUIRED` | Re-observe and, only when the accepted session-create contract proves the same idempotency key is safe, create the session; otherwise require Human recovery |
| Session exists with exact proof but agent/workspace correlation is missing or conflicts | `RECOVERY_REQUIRED` | Do not adopt, recreate or delete; preserve both observations for Human reconciliation |
| Create/replace returns a correlation but re-observation times out | `RECOVERY_REQUIRED` | Persist the correlation and timeout fact, then observe on restart; do not blindly reissue |
| Effect call times out before a correlation is returned | `EFFECT_AMBIGUOUS / RECOVERY_REQUIRED` | Search only through an accepted exact ownership/idempotency lookup; absent that capability, require Human recovery |
| Successor generation is ready but predecessor retirement is unconfirmed | `PARTIAL / RECOVERY_REQUIRED` | Route no new work through an ambiguous predecessor; keep both correlations and complete an explicitly authorized drain/retire decision |
| Provider reports a definite pre-effect rejection | stable rejected/unsupported result | Record no native effect and permit a new command only under ordinary Platform policy |

`STOP` remains a dispatch barrier plus verified drain/cancel and no-in-flight
observation. `sessions.patch(archived=true)` and `sessions.delete` are never stop
evidence. If fixed-version source cannot supply the required activity and termination
observations, graceful stop remains unsupported.

### Transcript and existing Evidence authority

Transcript is access-controlled raw material owned in its native storage domain. It
may be appended, compacted, reset, archived or deleted by native behavior and policy;
therefore no default immutability is claimed. Access must be scoped to the exact
Runtime/Agent/Attempt correlation and must not expose credentials, hidden prompts or
unbounded provider payloads.

Formal Evidence remains under the existing Platform Evidence authority. A separately
authorized normalizer may read an exact bounded transcript version, redact secrets
and disallowed content, produce canonical bounded facts, record source locator,
capture time and content digest, and append them through the existing Evidence
repository. The normalized Evidence record, not the transcript, carries Platform
immutability and ordering. Later transcript mutation or retention deletion does not
rewrite existing Evidence; inability to retrieve the raw source remains explicit.

Retention duration, redaction rules, approved transcript fields, source-locator
stability and deletion/legal-hold policy are unresolved. Batch A creates no Evidence
writer, transcript store, normalizer or new Evidence authority.

## PROPOSED contract B — authoritative Runtime Profile projection

Status: `PROPOSED / NOT_ACCEPTED / NOT_IMPLEMENTED`. PostgreSQL remains the sole
Runtime Profile lifecycle authority; a serialized file assembled by a person is not
a production projection.

Recommendation: add a PostgreSQL-owner projection publisher that transactionally
reads the exact published Runtime Profile and publication fact, canonicalizes the
existing `runtime-profile/v1` digest input, and writes two namespaced Kubernetes
`ConfigMap` transport objects:

1. an `immutable: true` revision ConfigMap whose single bounded `projection.json`
   value contains schema version, exact scope, profile ID, revision ID, canonical
   content, digest, publication fact ID and projection sequence; and
2. a mutable current-status ConfigMap whose single bounded `status.json` value
   contains aggregate version, per-revision eligibility, current revision/digest,
   revocation/supersession status, publication fact ID, sequence, `projectedAt`,
   `notBefore` and `expiresAt`.

The immutable object name is derived deterministically from the full revision digest;
the mutable object name is derived from the scoped Profile identity. The exact name
encoding and maximum document size are unresolved acceptance values, not guessed
here. Profile projections contain no secret data and therefore are not Kubernetes
`Secret` objects.

These ConfigMaps are caches/transport, not a second Profile authority. PostgreSQL
remains authoritative for Profile lifecycle, canonical revision/digest, publication,
supersession and revocation. Kubernetes is authoritative only for whether a
particular transported object exists and for its API metadata/resource version.
Deleting or editing a transport object cannot change the PostgreSQL Profile fact.

One dedicated publisher service account is the only intended writer. Kubernetes
RBAC expresses write permission; an admission rule must constrain create/update to
that authenticated service-account identity and the projection namespace/name
pattern. Payload `publisher` text is only a claim and cannot authenticate its own
source. `managedFields.manager`/field manager coordinates field ownership and aids
diagnosis, but is neither authentication nor authorization. The operator trusts the
transport only inside the accepted Kubernetes API/RBAC/admission trust boundary.

The desired Runtime command/Placement supplies the exact
`(namespace, security_domain, runtime_profile_id, revision_id, digest)` binding. The
operator reads both projection artifacts through the Kubernetes API and rejects
unless all of the following hold:

- scope, profile ID, revision ID and digest match the desired binding exactly;
- the revision is `PUBLISHED`, its digest recomputes from canonical bytes, and the
  publication fact and publisher identity are present;
- the mutable index still names that exact revision/digest as active and has a
  projection sequence no older than the immutable projection;
- `projectedAt`, `notBefore` and `expiresAt` satisfy the accepted clock-skew and
  maximum-staleness policy; and
- the bound revision's explicit eligibility permits the requested operation; and
- no revocation, scope denial or incompatible schema is present.

### Profile revision eligibility

Eligibility is explicit and operation-specific. `not latest` is not equivalent to
`ineligible`.

| Event / binding state | New exact binding | Existing exact binding | Recommended effect |
| --- | --- | --- | --- |
| New revision becomes published | Only the new current revision is eligible for newly created bindings after the status sequence advances | Existing bindings to the predecessor remain eligible under their recorded authorization/eligibility lease | Mark predecessor `SUPERSEDED_FOR_NEW_BINDINGS`, not revoked; do not rewrite its exact binding |
| Old revision after ordinary supersession | Reject new bindings to it | Continue already authorized start/dispatch/replace and safe convergence only until binding expiry or terminal completion | Supersession alone does not cancel work or invalidate a running Runtime Instance |
| Existing binding reaches expiry or requests renewal | Requires a fresh eligibility decision | No implicit extension | Rebind to an eligible exact revision or stop safely according to the accepted lifecycle |
| Revision explicitly revoked | Reject new binding, start, dispatch and replace | Reject new effect-producing work; continue observe and explicitly authorized drain/cancel/stop needed for safe convergence | Revocation does not imply delete, archive, transcript deletion or immediate process kill |
| Accepted execution is active when revocation arrives | No new dispatch | Preserve exact correlation; default to controlled drain, with cancel only through a separate explicit authorization | Record the revocation observation and convergence result; do not infer terminal Evidence/Outcome |

Binding eligibility lease duration, renewal lead time, whether an ordinary existing
binding may start after a long delay, and emergency-revocation cancel policy are not
fixed by existing contracts and require Human values. Until accepted, current
serialized projection remains insufficient for production eligibility.

### Publication, CAS and idempotent recovery

No transaction spans PostgreSQL and Kubernetes. The recommended sequence is:

1. in one PostgreSQL transaction, commit the Profile publication/supersession or
   revocation fact and a durable outbox item with monotonically increasing projection
   sequence;
2. create the immutable revision ConfigMap. `AlreadyExists` is idempotent only when
   canonical bytes, digest, scope, revision and sequence match exactly; otherwise
   stop with projection conflict;
3. update the mutable current-status ConfigMap using Kubernetes `resourceVersion`
   CAS and the expected predecessor projection sequence;
4. re-read both objects and verify exact bytes, sequence and status;
5. acknowledge the outbox item in PostgreSQL only after verified transport state.

| Intermediate state | Eligibility and recovery |
| --- | --- |
| PostgreSQL commit exists; immutable ConfigMap absent | New revision is not yet transport-eligible; publisher retries the same outbox sequence |
| Immutable ConfigMap exists; current-status remains at predecessor | New revision is not eligible for new bindings; existing predecessor eligibility is unchanged; retry CAS |
| Current-status advanced; PostgreSQL acknowledgement missing | Operator may use the verified sequence; publisher replays, compares exact state and acknowledges without creating a new sequence |
| Higher or conflicting Kubernetes sequence exists | Do not overwrite; stop as projection conflict and reconcile against PostgreSQL authority |
| Revocation committed in PostgreSQL but status transport is not yet updated | Revocation propagation is not instantaneous; new effect authorization requires a sufficiently fresh status object, bounded by the Human-approved expiry |

Operator restart re-reads current status and the exact immutable projection rather
than trusting a local serialized file. Publisher restart resumes from the durable
outbox and uses the same sequence/CAS rules.

### Representation alternatives

| Representation | Disposition |
| --- | --- |
| Two namespaced ConfigMaps as defined above | `RECOMMENDED`; uses the existing Kubernetes API without freezing a new public CRD; still requires Human acceptance of RBAC/admission/trust and schema |
| Dedicated internal Runtime Profile Projection CRD | `ALTERNATIVE`; stronger typed status/watch semantics, but introduces a CRD/API and requires a separate explicit G2 decision |
| Authenticated read-only projection API owned by the PostgreSQL service | `ALTERNATIVE`; stronger request-time source identity/freshness, but adds runtime service availability and authentication dependencies |
| Operator direct PostgreSQL repository access | `NOT_RECOMMENDED`; couples operator to Product storage credentials/schema and expands cross-plane authority |
| Human-written serialized file | `REJECTED_FOR_PRODUCTION`; cannot prove PostgreSQL origin, current eligibility or revocation |

### Disconnection behavior

Projection transport availability and provider/Gateway availability are separate.
Loss of the projection service must not authorize new effects, but it also must not
unconditionally prevent safe convergence.

| Requested operation while current eligibility cannot be verified | Recommended behavior |
| --- | --- |
| New Runtime binding, `START`, new execution dispatch or `REPLACE` | Fail closed; issue no new provider effect |
| Read-only provider observation | Permit only for an already persisted exact binding/correlation using no newly resolved privilege; mark Profile eligibility observation stale/unknown |
| Drain or cancel active accepted work | Permit only when the operation was already authorized or a new explicit emergency/convergence authorization is durably available; otherwise `RECOVERY_REQUIRED` |
| `STOP` safe convergence | Preserve the dispatch barrier and permit already authorized observe/drain/cancel/stop steps; do not require a fresh Profile projection merely to prevent new work or reduce harm |
| Destructive cleanup, archive, transcript deletion or adoption | Reject while authority/eligibility is unavailable |

The maximum cached-status age for effect-producing operations, maximum safe
observation age, and any emergency authorization lifetime are unresolved Human
values. No implicit authorization arises from connectivity loss.

The Runtime Profile carries only opaque Secret References. The PostgreSQL publisher
never resolves secret values and the projection never contains them. A separately
authorized Platform credential binding maps the exact scoped reference to a
Kubernetes `SecretKeyRef`; the operator service account resolves that reference and
projects it only into the allowlisted `OPENCLAW_GATEWAY_TOKEN` process slot.

The credential binding must carry namespace, security domain, Runtime Profile
revision/digest, logical Secret Reference, exact Kubernetes Secret namespace/name/key,
credential-binding revision, allowed operation class and revocation state. The
operator service account receives `get` permission only for accepted scoped Secret
objects; broad list/watch, cross-namespace resolution and name inference are not
granted. The operator compares every scope/revision field before reading the Secret.

Credential revocation denies new resolution for binding/start/dispatch/replace. It
does not silently authorize deletion or prove that an already materialized value has
disappeared from a process. Continuing observe/drain/cancel/stop after revocation
requires either an already authorized bounded control credential or a separate
explicit convergence authorization; if neither exists, return `RECOVERY_REQUIRED`.
The control/execution credential split, rotation overlap and forced removal timing
are unresolved Human decisions. Defining this credential binding/trust path remains
an authentication-architecture G2 decision and is not implemented here.

### Human acceptance values still unresolved

- exact workspace snapshot/overlay mechanism and cross-generation State/Memory
  Reference semantics;
- native ownership metadata field, ownership nonce encoding, deterministic session
  key shape and PostgreSQL persistence schema;
- fixed-version RPC parameters/results for create, lookup, activity observation,
  drain/cancel, stop and replace, including safe idempotency boundaries;
- operation timeouts, observation freshness and recovery/Human intervention policy;
- transcript field allowlist, redaction profile, retention, legal hold and stable
  source locator;
- ConfigMap name encoding, payload size ceiling, projection namespace, admission
  mechanism and accepted cluster-admin trust boundary;
- binding eligibility lease/renewal values, projection expiry, clock skew and
  emergency revocation policy;
- credential-binding representation, control versus execution credential policy,
  rotation overlap and revocation timing.

These values must be accepted explicitly; implementation must not fill them with
defaults inferred from fixtures or current temporary files.

### Implementation path after Human acceptance

1. publish the accepted internal schemas and conformance fixtures for ownership,
   eligibility, projection sequence/CAS, disconnect behavior and credential binding;
2. under separately allocated persistence authority, add durable ownership/
   correlation and projection-outbox repository fields without creating a second
   Profile or Evidence authority;
3. implement the PostgreSQL-owned publisher, chosen Kubernetes representation,
   admission/RBAC and idempotent recovery tests;
4. implement an operator read/verify adapter and credential resolver with exact
   scope/revision/digest checks and operation-specific fail-closed behavior;
5. only after fixed-version RPC conformance proves the accepted semantics, extend the
   production transport allowlist and lifecycle adapter incrementally;
6. validate restart/partial-success/revocation/disconnection with real services,
   then separately consider Batch B execution/Evidence/Outcome work.

Every step requires its own Human implementation allocation. This Batch A decision
draft performs none of them.

## Production image packaging status

The operator image now packages the production import closure (`operator`, `core`,
`gateway`, and `runtime` source packages) and a lockfile-backed exact
`openclaw@2026.7.1-2` installation on Node `22.23.1`. It copies source directories,
not test directories, and runs as `nobody`. The lock preserves the authoritative npm
integrity and engine declaration. No credential is part of the build context,
Dockerfile, image configuration or build argument.

An image-equivalent clean import and the configured source preflight passed. The one
Docker build attempt could not obtain the pinned Python and Node base-image metadata
because the configured Docker registry proxy timed out; it was cancelled after the
bounded wait and was not retried. Therefore a runnable built image and in-image
configured preflight remain `NOT_PROVEN`, as do deployment and lifecycle acceptance.

Future build recovery requires all of the following environmental preconditions
before one new build attempt is authorized:

- the existing Docker daemon responds within the agreed bounded preflight;
- the configured registry path, without switching mirrors or global Docker settings,
  completes TLS-verified manifest access for exact base tags
  `python:3.12-slim-bookworm` and `node:22.23.1-bookworm-slim`;
- the build network can reach the locked Python and npm artifact URLs using ordinary
  certificate and integrity verification; no TLS, version, digest or npm integrity
  check is disabled;
- sufficient local disk/build-cache capacity exists and no unrelated build owns the
  task context; and
- the build context is this reviewed candidate or an explicitly accepted successor,
  is clean, and contains no credential material.

Only after those conditions are explicitly proven may the original root-context
`operator/Dockerfile` build run once, followed by actual-image checks for the formal
entrypoint, non-root identity, Python/Node/OpenClaw dependency integrity and
configured preflight. Image-equivalent imports do not satisfy that gate.
