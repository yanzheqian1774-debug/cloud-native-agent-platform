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

## Open Human decisions and packaging limitation

1. Select the native realization for one Platform Runtime Instance under the
   external shared-Gateway profile: preconfigured agent, generation-scoped session,
   another object, or lifecycle-unsupported.
2. If Session is selected, define create/adopt ownership proof, durable correlation,
   restart recovery, idempotency, graceful stop, transcript retention, replacement
   and ambiguous-effect behavior. Archive/delete cannot be inferred as stop.
3. Define the authoritative production projection path for a published Runtime
   Profile. The current internal bootstrap can verify a serialized record's
   self-consistency, but the repository has no operator-facing export/controller,
   signature, API trust path or direct repository contract that proves the file was
   emitted by the PostgreSQL Runtime Profile authority.
4. Authorize the packaging path if configured OpenClaw startup must run in the
   shipped operator image. `operator/Dockerfile` currently copies only `operator/`
   and exposes only `operator/src`; it contains neither `core/src` nor `runtime/src`.
   A clean image-equivalent import already fails on the baseline `agent_core`
   dependency, and configured OpenClaw startup would additionally lack
   `agent_runtime`. The source entrypoint uses a lazy import so this change does not
   add the latter failure to the unconfigured path, but the production-image path is
   not validated.
