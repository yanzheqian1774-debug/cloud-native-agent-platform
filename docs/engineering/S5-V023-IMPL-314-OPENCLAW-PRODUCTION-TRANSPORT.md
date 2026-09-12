# S5-V023-IMPL-314 — OpenClaw Production Transport and Explicit Assembly, Batch A

## Task carrier

- Type: `IMPL / Runtime Integration / G1`
- Lifecycle: `ACTIVE / AUTHORIZED / SESSION_OPEN`
- Human scope: Batch A only; production Transport and explicit assembly
- Fixed source: `f189212232fc194859a695f0307e83b0c7b73c0f`
- Fixed tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`
- Branch: `codex/s5-v023-impl-314-openclaw-production-transport`
- Worktree: `/Users/tristan/.codex/worktrees/3198/cloud-native-agent-platform`
- Pull request: `PENDING / DRAFT_REQUIRED`

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
to an isolated, preconfigured OpenClaw agent workspace and a generation-scoped
session: create/adopt, observe, archive-delete, and bounded replace. They do not
start, stop, restart, or claim ownership of the Gateway process.

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
2. Implement observe-first session lifecycle behavior and explicit distinctions
   for missing configuration, authentication failure, Gateway unavailability,
   protocol failure, and possible-effect ambiguity. Never fallback to Native or
   blindly repeat an ambiguous effect.
3. Add production bootstrap parsing for one published Runtime Profile revision,
   resolve the one allowed Secret Reference using the existing Kubernetes Secret
   projection, assemble Transport -> Provider -> Adapter -> Factory, and call it
   from the operator startup entry.
4. Add focused unit/integration tests, then run a live exact-version Gateway in
   task-owned directories and port without a model task. Verify authenticated
   readiness, formal bootstrap selection, observation, and controlled session
   shutdown.
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
- start/observe/stop/replace preserve Platform Runtime Instance, Placement,
  generation and session correlation rules;
- live validation proves exact package, authenticated Gateway readiness and
  controlled lifecycle only, with zero model tasks.

## Out of scope

External model invocation; production execution dispatch or continuous execution
observation; dispatch claims; persistent recovery; terminal Evidence/Outcome;
trusted browser execution; public API/CRD/auth vocabulary; 299/305/308 business
logic; and any 309 environment operation remain excluded.

