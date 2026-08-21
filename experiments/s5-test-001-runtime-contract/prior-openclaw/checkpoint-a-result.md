# S5-SPIKE-002 — CHECKPOINT A RESULT

## 1. Overall

**PASS**

OpenClaw is materially different from the Hermes runtime studied in
S5-SPIKE-001. Its normal runtime unit is a long-lived, shared Gateway that can
host multiple isolated logical agents, each with multiple durable sessions,
while each execution is a queued, asynchronous, event-streaming run correlated
by `runId`. This falsifies any implicit 1:1 equivalence among Platform Agent
Instance, runtime process, container, Gateway, OpenClaw Agent, Session, or Run.

The evidence does not contradict the decomposed Runtime Contract Candidate v0.
It challenges several areas that must remain explicit and non-universal:

- Runtime Binding cardinality and the identity of a runtime realization;
- readiness as a projection of several independent observations;
- the meaning of `InfrastructureAvailable` for remote/shared Gateways;
- the scope and ownership of persistent state;
- optional cancellation and native lifecycle operations.

This is a research result, not a Contract approval or OpenClaw integration.

### Evidence method and confidence

- **PINNED SOURCE**: official OpenClaw source/docs at commit
  `4343b38ce7630fddaa16bfb72262e071d25424f6`.
- **OFFICIAL DOCS**: official documentation, retrieved 2026-08-22. Documentation
  is treated as consistent with the pinned source snapshot where the same files
  exist, but the hosted site itself is a moving target.
- **LOCAL**: local environment inspection only. No OpenClaw executable was
  installed, no Gateway was started, and no model was invoked.
- **INFERENCE**: bounded architectural interpretation from cited evidence; it
  is labelled where material.

Checkpoint A does not require live/model evidence. Runtime behavior that cannot
be established from authoritative material remains `UNKNOWN` and is assigned to
Checkpoint B.

## 2. OpenClaw Identity

| Field | Observed value | Evidence |
|---|---|---|
| Version | `2026.8.1` on the pinned `main` snapshot | [package.json at pinned commit](https://github.com/openclaw/openclaw/blob/4343b38ce7630fddaa16bfb72262e071d25424f6/package.json#L1-L9) |
| Commit | `4343b38ce7630fddaa16bfb72262e071d25424f6` (2026-08-21T16:34:18Z) | Official GitHub commit lookup performed 2026-08-22 |
| Distribution | MIT-licensed Node.js CLI/package (`openclaw`); source, npm/global installation, Docker/Compose, and Kubernetes manifests are documented distribution/realization forms | [package metadata](https://github.com/openclaw/openclaw/blob/4343b38ce7630fddaa16bfb72262e071d25424f6/package.json), [installation](https://docs.openclaw.ai/install), [Docker](https://docs.openclaw.ai/install/docker), [Kubernetes](https://docs.openclaw.ai/install/kubernetes) |
| Execution Environment | Evidence-only inspection on macOS; no local OpenClaw install. Upstream supports macOS launchd, Linux systemd, Windows Scheduled Task, direct process, Docker/Compose, and Kubernetes | [Gateway runbook](https://docs.openclaw.ai/gateway), [Kubernetes](https://docs.openclaw.ai/install/kubernetes) |

The version is a source snapshot identity, not a claim that `2026.8.1` was the
latest stable release on the retrieval date. A Provider package must pin an
immutable tag/digest/commit rather than follow `main`.

## 3. Runtime Anatomy

### Gateway

The Gateway is OpenClaw's always-on, local-first control plane and primary
network/service boundary. It owns channel connections and routing, agent RPC,
session access, Control UI, health, configuration reload, and coordination of
agent runs. Clients normally connect through an authenticated WebSocket
endpoint. One Gateway can host multiple agents and channels.

Evidence: [Gateway runbook](https://docs.openclaw.ai/gateway),
[Gateway protocol](https://docs.openclaw.ai/gateway/protocol), and
[official FAQ](https://docs.openclaw.ai/help/faq).

### Agent

An OpenClaw Agent is a configured, logical per-persona isolation scope within a
Gateway, identified by `agentId`. It owns a workspace, an `agentDir`, model/auth
configuration and a session store. It is not normally a process, Pod, container,
or single execution. A default install has the `main` agent; configured
`agents.entries` add more agents.

Evidence: [Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent)
and [Agents CLI](https://docs.openclaw.ai/cli/agents).

### Session

A Session is a durable conversation/context boundary owned by one OpenClaw
Agent. It has a session key and durable session ID, transcript/history,
metadata, model/context accounting, run status, and lifecycle such as reset,
archive, delete and maintenance. Routing scope can create multiple sessions per
agent (main, sender, peer, group, thread, spawned sub-agent, or explicit key).
Runs for a session are serialized.

Evidence: [Session model](https://docs.openclaw.ai/concepts/session),
[Session tools](https://docs.openclaw.ai/concepts/session-tool), and
[Sessions CLI](https://docs.openclaw.ai/cli/sessions).

### Run

A Run is one serialized agent-loop turn inside a Session: message intake,
context assembly, model inference, tool execution, streaming and persistence.
Gateway RPC `agent` validates and accepts work, resolves/persists the Session,
and immediately returns `{runId, acceptedAt}`. `agent.wait` and lifecycle/events
then correlate progress and terminal outcome. Runs are queued per session and
under a global concurrency limit.

Evidence: [Agent loop](https://docs.openclaw.ai/agent-loop) and
[Agent CLI](https://docs.openclaw.ai/cli/agent).

### Workspace

The Workspace is an Agent's working directory and prompt/bootstrap content
home. It contains instructions, persona/user/memory files, workspace-local
skills and ordinary working files. It is the default cwd but not, by itself, a
security sandbox. It is explicitly separate from OpenClaw's state directory,
configuration, credentials and session database. Sandboxing can instead expose
per-session, per-agent or shared sandbox workspaces.

Evidence: [Agent workspace](https://docs.openclaw.ai/concepts/agent-workspace)
and [Sandboxing](https://docs.openclaw.ai/gateway/sandboxing).

### Persistent State

Authoritative upstream material identifies at least:

- Gateway/global configuration and shared state under `OPENCLAW_STATE_DIR`;
- shared SQLite workspace/setup state;
- per-agent SQLite state containing auth/model/routing/session/transcript and
  other agent-scoped runtime data;
- channel/provider credentials and connection state;
- agent Workspace files including explicit memory;
- managed/shared/workspace skills and installed plugins;
- logs, caches, delivery/recovery data, scheduled automation state, and legacy
  migration/archive artifacts;
- optional sandbox/container workspaces and plugin data.

The Workspace and runtime state directory are distinct persistence domains.
Neither is proven portable into another runtime merely because it is durable.

Evidence: [Agent workspace](https://docs.openclaw.ai/concepts/agent-workspace),
[FAQ: state layout](https://docs.openclaw.ai/help/faq), and
[Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent).

## 4. Topology & Cardinality

### Typical relationships

```text
Platform Agent Instance (future, logical)
        0..* Runtime Bindings / realization references
                         |
                         v
             OpenClaw Gateway endpoint
              1 process/service normally
              0..1 Pod/container in a container realization
                         |
                         +---- 1..* OpenClaw Agents
                         |          |
                         |          +---- 0..* Sessions
                         |                    |
                         |                    +---- 0..* Runs over time
                         |
                         +---- channels, plugins, health, Control UI
```

The `0..*` values describe representable/native relationships, not recommended
Platform defaults.

| Pair | Observed/native cardinality | Finding |
|---|---|---|
| Gateway : process | normally 1:1 for one Gateway service instance | Multiple Gateway instances require distinct ports/config/state/workspace roots. A supervisor may replace the process without changing the logical Gateway endpoint. |
| Gateway : Agent | 1:N | Explicitly supported in one Gateway process. |
| Agent : Session | 1:N | Session routing scopes and explicit/spawned sessions create multiple durable sessions. |
| Session : active Run | normally 1:0..1 executing, with additional queued work | Runs are serialized per Session; the Session persists across runs. |
| Session : historical Run | 1:N over time | Transcripts/events and run status belong to the durable session context. Exact retention of a first-class run record needs live/source verification. |
| Run : process | N:1 over time, potentially M:N across recovery | Many runs execute in the Gateway process; a run may fail/abort if its process disappears. No run-per-process topology. |
| Gateway : Pod/container | logical Gateway 1:0..N over time; typical current deployment 1:1 at an instant | Upstream Kubernetes manifests deploy a single Gateway Pod with persistent storage; replacement changes the Pod, not necessarily the logical endpoint/state. |
| Agent : Pod/container | N:1 in the typical shared Gateway deployment | Agent-scoped or session-scoped tool sandboxes may create extra containers, but those are execution sandboxes, not the Gateway or Agent identity. |
| Platform Agent Instance : OpenClaw Agent | **not inherently 1:1; policy/Provider mapping required** | A plausible mapping is 1:1 logical identity, but a Platform Instance could bind to an existing agent/session or use a shared Gateway. Checkpoint A must not freeze this. |
| Platform Agent Instance : Session | **unknown/policy-dependent** | A long-lived Platform Instance could own many sessions; a task-scoped instance might select one. OpenClaw does not choose the Platform cardinality. |
| Platform Agent Instance : Gateway | N:1 is natively supported; 1:1 is an isolation policy | Shared Gateway is the normal multi-agent anatomy. |

Sources: [Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent),
[multiple Gateways](https://docs.openclaw.ai/gateway/multiple-gateways),
[agent loop](https://docs.openclaw.ai/agent-loop),
[sandboxing](https://docs.openclaw.ai/gateway/sandboxing), and
[Kubernetes topology](https://docs.openclaw.ai/install/kubernetes).

## 5. Lifecycle & Recovery

### Native Lifecycle

- Gateway CLI: install, start, status/probe, restart, stop, uninstall, foreground
  run, configuration reload, secrets reload, logs, doctor/repair and update.
- Agent CLI/config: list, add, delete, bind/unbind, set identity; Agent creation is
  configuration/state mutation inside the Gateway, not process provisioning.
- Session operations: create implicitly/by spawn, inspect/search/history/send,
  reset, patch, archive/pin, delete and retention maintenance.
- Run operations: submit/accept, wait, stream events, timeout/abort/cancel.

Sources: [Gateway CLI](https://docs.openclaw.ai/cli/gateway),
[Agents CLI](https://docs.openclaw.ai/cli/agents), and
[Session tools](https://docs.openclaw.ai/concepts/session-tool).

### Supervisor

The process supervisor is the normal owner of Gateway process recovery:
launchd on macOS, systemd on Linux, Scheduled Task/Startup launcher on Windows,
or a container orchestrator restart policy. OpenClaw explicitly recommends one
lifecycle owner and detects conflicting supervisors. It has application-level
restart recovery/safe-mode behavior, but does not replace the external service
manager for a dead process.

### Kubernetes

Kubernetes owns Pod/container restart and replacement, Service routing, storage
attachment and Secret/ConfigMap projection in the upstream Kubernetes form.
The upstream deployment is a single Gateway Pod plus Service, PVC, ConfigMap
and Secret. Kubernetes probes process/Gateway endpoints but does not understand
Agent, Session or Run semantic success.

### Provider Candidate

A future experimental Provider would own translation between platform intent
and the selected realization:

- provision a managed Gateway or connect to an external one;
- create/select/configure an OpenClaw Agent and its Workspace/state references;
- preserve shared-Gateway ownership boundaries;
- map invocation, `runId`, lifecycle events and cancellation;
- normalize layered observations without exposing native payloads to Core;
- never delete a shared external Gateway or unrelated Agents/Sessions.

This is an inference about the candidate boundary, not an implementation.

### Platform

The Platform should own desired semantic outcome, authorization/policy and
recovery verification. It should not assume it owns the Gateway process,
OpenClaw's internal recovery, a remote supervisor, or every native Agent and
Session sharing that Gateway.

Evidence: [Gateway supervision](https://docs.openclaw.ai/gateway),
[restart recovery](https://docs.openclaw.ai/gateway/restart-recovery), and
[Kubernetes](https://docs.openclaw.ai/install/kubernetes).

## 6. Observation Model

| Layer | Native evidence | What it proves | What it does not prove |
|---|---|---|---|
| Process | service-manager status/PID, container state, logs, exit code; `gateway status --deep` scans services | A process/service exists or failed | Authenticated Gateway RPC, channel/model/tool readiness, Run success |
| Gateway | `gateway status`, `gateway probe`, authenticated WS connection, `/healthz` | endpoint reachability and Gateway liveness/identity at the relevant level | all channels/dependencies ready or a new Run can complete semantically |
| Protocol | authenticated WebSocket connect and RPC response; JSON probe contract | protocol is usable for the tested method and auth context | model credentials, tool dependencies, execution completion |
| Dependencies | `status --deep`, `health --verbose`, per-channel probes, `models status --check/--probe`, plugin diagnostics | selected channel/model/auth/plugin dependencies at a point in time | all possible Run paths or business semantics |
| Execution | `runId`, agent lifecycle events, streamed assistant/tool events, `agent.wait`, CLI exit status | acceptance, progress and terminal outcome for one Run | ongoing Gateway health or portability of resulting state |

OpenClaw's Kubernetes docs distinguish `/healthz`, `/readyz` and newer
`/startupz`, and warn that status code alone is insufficient because a catch-all
route may return 200. `/readyz` includes channel-account health, while
`/startupz` is better for traffic admission because a failed channel should not
evict an otherwise usable Gateway. This directly supports multi-condition,
tri-state observation rather than one `READY` bit.

Sources: [Health checks](https://docs.openclaw.ai/gateway/health),
[Kubernetes probes](https://docs.openclaw.ai/install/kubernetes), and
[Models status](https://docs.openclaw.ai/cli/models).

## 7. Interaction Model

| Concern | Finding |
|---|---|
| Submission | Gateway WS RPC `agent`; CLI `openclaw agent`; channel message routing; embedded local execution is also available but bypasses the Gateway path. |
| Acceptance | Asynchronous: `agent` returns `{runId, acceptedAt}` immediately after validation/session resolution. |
| Correlation | `runId` correlates lifecycle/event flow; Session is selected by `sessionKey`/`sessionId`. |
| Streaming | Native event stream includes lifecycle plus assistant/tool deltas. Channel-facing block/preview streaming is separately configurable and may be coalesced. |
| Completion | Terminal lifecycle end plus final result from `agent.wait`; CLI completed turn exits 0. Semantic completion means the agent loop reached a terminal success and produced/persisted its result, not merely that RPC submission returned. |
| Failure | Validation/RPC rejection; lifecycle error; model/auth/tool/provider error; timeout; abort/cancel; process loss; delivery failure. CLI error/timeout/cancel exits 1. Transport acceptance and terminal semantic success are distinct. |
| Cancellation | OpenClaw has abort/cancel paths and run timeout; exact public RPC authorization, idempotency and terminal-state race semantics require Checkpoint B/source tests. Treat cancellation as **LIMITED**, not a guaranteed universal Contract operation. |

The native interaction model is therefore **hybrid asynchronous + runId-based +
event-streaming**, with synchronous waiting available as a convenience. It is
not simple synchronous request/response.

Sources: [Agent loop](https://docs.openclaw.ai/agent-loop),
[Gateway protocol](https://docs.openclaw.ai/gateway/protocol),
[Agent CLI](https://docs.openclaw.ai/cli/agent), and
[Streaming](https://docs.openclaw.ai/concepts/streaming).

### Semantic success and failure

Successful submission is only acceptance. Successful semantic completion is a
terminal successful Run after model/tool loop completion with result payload
and persistence/delivery metadata where applicable. Semantic failure is a
terminal execution error, timeout or cancellation even if the original RPC was
accepted and the Gateway remained healthy. Channel delivery is another outcome
layer and may fail after agent execution succeeds.

## 8. Model & Credential Configuration

Models use canonical `provider/model` references. Defaults and fallbacks are
configured at Agent defaults/entries; Sessions can pin/override model and auth
profile where policy permits. Provider endpoint/model metadata belongs under
`models.providers` in Gateway/agent configuration. Auth selection rotates
eligible profiles before model fallback.

Credentials are per-agent auth profiles supporting API keys, tokens and OAuth,
plus environment/config/store sources. Static credentials may use `SecretRef`
markers backed by environment, file, exec or store providers. Current docs say
auth/profile/session state is stored in per-agent SQLite; older JSON auth stores
are migrated by `doctor`. Gateway connection auth (token/password/identity) is a
separate credential concern from model-provider auth.

A Provider must pass references/secret projections, never credential values
through Control Plane status or repository artifacts.

Sources: [Models](https://docs.openclaw.ai/concepts/models),
[Models CLI](https://docs.openclaw.ai/cli/models),
[model authentication](https://docs.openclaw.ai/gateway/authentication), and
[Secrets management](https://docs.openclaw.ai/gateway/secrets).

## 9. Capability / Tool Model

OpenClaw has distinct native concepts:

- **Tools** are typed callable actions exposed to the model. Built-ins and
  plugin/MCP tools are filtered through profile, allow/deny policy, provider,
  sandbox, channel and plugin availability.
- **Skills** are `SKILL.md` instruction packs loaded into agent context. They can
  be workspace-local, personal/shared, managed/bundled or plugin-provided.
- **Plugins** add executable/runtime capabilities including tools, skills,
  channels, model providers and hooks, with packaging/config/lifecycle.
- **MCP servers/tools** can be mapped by plugins/bundles into native tools.
- **Agent configuration** scopes visible skills and tool policy per Agent.

Sources: [Capabilities overview](https://docs.openclaw.ai/tools),
[Skills](https://docs.openclaw.ai/tools/skills),
[tool configuration](https://docs.openclaw.ai/gateway/config-tools), and
[plugin bundles/MCP](https://docs.openclaw.ai/plugins/bundles).

### A22 — Capability Binding translation

**Yes, plausibly; not proven live.** A platform-owned Capability Binding can
name an opaque capability and policy/config/credential references. An
OpenClaw-specific Provider can translate it into skill visibility, tool policy,
plugin installation/configuration or MCP tool exposure. Core need not understand
OpenClaw tool names, schemas, plugin layouts or skill precedence.

Limits: OpenClaw distinguishes instructional Skills from executable Tools and
Plugins; availability can change with policy, sandbox and plugin state. A
platform binding therefore needs declared type/requirements and readiness
evidence. Treating every capability as a Tool would leak/flatten native
semantics. Capability Contract design is out of scope.

## 10. State Classification

| Classification | OpenClaw examples | Checkpoint A conclusion |
|---|---|---|
| Runtime Internal State | Gateway config/version, plugin registry/cache, service/restart metadata, logs, delivery queues, shared setup DB, channel connection state | Provider/runtime-owned implementation state; not portable by default |
| Agent State | agent identity/config, model/auth routing metadata, per-agent SQLite data, persona/instructions and some memory content | Mixed: OpenClaw-native representation; may contain enterprise-owned intent but cannot be declared portable wholesale |
| Session State | session key/ID, transcript, context/compaction, model pins, token accounting, run status, parent/child/thread bindings | Durable OpenClaw session state; native schema and semantics are runtime-specific |
| Workspace State | `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, `MEMORY.md`, daily memory, skills and working files | Semantically important and separately back-up-able, but only a subset may be portable after policy/schema translation |
| Potential Portable State | explicit user/agent instructions, selected memory documents, user-created artifacts, declarative capability references | Candidate only. Portability, conflict rules, secret filtering and fidelity are unproven; do not call the whole Workspace portable |

The same physical database can contain several ownership classes. Physical path
does not establish conceptual ownership. State Contract design remains deferred.

## 11. Managed vs External Runtime

OpenClaw can operate as **both**:

- **Managed Runtime**: Provider/substrate provisions a pinned OpenClaw package
  or image, Gateway process/Deployment, persistent storage, configuration and
  secret projections; Provider observes the Gateway and respects native/
  substrate recovery.
- **External Runtime**: Provider connects through authenticated Gateway WS/RPC
  to an already-running local or remote Gateway. The external owner retains
  process, infrastructure, upgrade and often shared-Agent lifecycle authority.

Remote access is a documented native mode via configured remote URL, VPN/
Tailscale or SSH tunnel, and it retains Gateway authentication.

### A25 — `InfrastructureAvailable` for remote Gateway

For an external remote Gateway, underlying infrastructure is outside Provider
authority and usually not observable. `InfrastructureAvailable` should be
`UNKNOWN`/not-applicable-with-owner-external, not inferred `TRUE` from RPC
reachability. `GatewayAvailable` or `ProtocolUsable` can be observed separately.
The external service owner may provide an optional infrastructure signal, but
absence of that signal is not a runtime failure.

Sources: [Remote Gateway](https://docs.openclaw.ai/gateway/remote),
[Gateway runbook](https://docs.openclaw.ai/gateway), and
[Kubernetes](https://docs.openclaw.ai/install/kubernetes).

### A26 — Provider distribution metadata

A Provider would need at least:

- upstream OpenClaw version and source commit/tag;
- immutable npm package integrity or container image digest/source build;
- Node/runtime and OS/architecture requirements;
- selected realization (`service`, `docker`, `kubernetes`, `external`);
- CLI/Gateway protocol and state/schema compatibility versions;
- startup command, service ownership, port/bind/auth/TLS/remote endpoint;
- config/state/workspace paths and persistence/storage requirements;
- probe endpoints/RPC methods and their version availability;
- installed plugin/provider/channel inventory and compatibility;
- Provider version and supported Candidate Contract range;
- upgrade/migration/doctor requirements and backup/rollback constraints;
- concurrency/sandbox/container requirements and declared capabilities.

## 12. Runtime Capability Matrix

| Runtime capability | Status | Authoritative evidence / boundary |
|---|---|---|
| Shared Gateway service | SUPPORTED | One Gateway hosts multiple agents/channels |
| Multiple Agents per Gateway | SUPPORTED | `agents.entries`, bindings and per-agent isolation |
| Multiple Sessions per Agent | SUPPORTED | routing scopes, explicit keys and session tools |
| Asynchronous run submission | SUPPORTED | immediate `{runId, acceptedAt}` |
| Correlated wait/result | SUPPORTED | `agent.wait`, lifecycle events, CLI projection |
| Event/delta streaming | SUPPORTED | lifecycle, assistant and tool deltas |
| Synchronous convenience invocation | SUPPORTED | CLI/wait path over asynchronous core |
| Semantic failure normalization | LIMITED | native terminal errors exist; cross-provider taxonomy and delivery separation need Provider mapping/tests |
| Cancellation | LIMITED | abort/cancel/timeout paths exist; public race/idempotency semantics unverified |
| Per-session serialization | SUPPORTED | native session and global queues |
| Gateway managed service lifecycle | SUPPORTED | launchd/systemd/Windows service operations |
| Kubernetes managed realization | SUPPORTED | upstream single-Pod Deployment manifests |
| External/remote Gateway | SUPPORTED | authenticated remote WS endpoint documented |
| Native dead-process recovery | UNSUPPORTED | external supervisor/orchestrator owns a dead Gateway process; OpenClaw owns application restart recovery after process return |
| Gateway health/reachability | SUPPORTED | status/probe/health and HTTP probe contracts |
| Dependency readiness | LIMITED | channel/model auth probes and plugin diagnostics exist; no single complete execution-readiness proof |
| Execution readiness | UNKNOWN | no model/run performed; dependency probes cannot prove arbitrary run success |
| Persistent runtime/agent/session state | SUPPORTED | Workspace plus state/per-agent SQLite and PVC guidance |
| State portability | UNKNOWN | no cross-runtime migration evidence |
| Tool policy and Skills | SUPPORTED | native separate surfaces |
| Plugin/MCP extension | SUPPORTED | native plugins and bundle MCP mapping |
| Horizontal Gateway scale / HA | UNKNOWN | multi-Gateway docs emphasize isolation/redundancy; shared-store/active-active semantics not established |
| Per-Agent process isolation | UNSUPPORTED as default; LIMITED via sandboxes | Agents normally share Gateway process; tool sandboxes can be agent/session scoped |
| Run-per-container | UNSUPPORTED as native topology | Runs occur inside Gateway agent loop; optional tool sandboxes are not Run identity |
| Upgrade with compatibility negotiation | LIMITED | update/migration mechanisms exist; Candidate Contract/Provider negotiation does not |

## 13. Falsification Matrix

| ID | Target | Status | Evidence | Candidate impact |
|---|---|---|---|---|
| F01 | Provider Isolation | **SURVIVES** | Gateway RPC/config/tool/session semantics can remain in Provider; no Core branch was needed for this report | Keep native protocol, paths and errors Provider-owned |
| F02 | Runtime Binding | **SURVIVES** | A logical join is useful precisely because Platform Instance, shared Gateway, Agent and Session are distinct | Binding must permit shared endpoint + selected agent/session and ownership metadata; no 1:1 identity |
| F03 | Agent Instance / Runtime realization separation | **SURVIVES** | OpenClaw Agent is logical state inside a shared process; Sessions/Runs have separate lifetimes | Strong evidence against equating Platform Agent Instance to container/process/Gateway |
| F04 | Runtime Instance definition/cardinality | **CHALLENGED** | One Gateway/process/Pod commonly hosts N Agents and N Sessions; sandboxes add other containers | Do not require one universal Runtime Instance object or cardinality; realization identity is Provider-specific |
| F05 | Interaction Contract | **SURVIVES** | Async acceptance, `runId`, events and terminal wait fit Candidate's request/correlation/result model | Async acceptance and delivery outcome must remain first-class; sync-only interface is falsified |
| F06 | Streaming optionality | **SURVIVES** | OpenClaw supports native event/delta streaming, but a Provider could project only terminal result | Optional declaration remains correct |
| F07 | Cancel optionality | **SURVIVES** | Abort/cancel exists but detailed guarantees are not established | Optional capability with declared semantics; never assume universal cancel |
| F08 | RuntimeAvailable normalization | **SURVIVES** | process, Gateway, protocol and execution are observably different | Tri-state layered conditions strengthened; avoid one boolean READY |
| F09 | DependencyReady separation | **SURVIVES** | channel/model/plugin probes differ from Gateway liveness and arbitrary Run readiness | Dependency condition should be scoped/named and may be partial/unknown |
| F10 | Managed Runtime definition | **SURVIVES** | Service manager/Kubernetes can own realization while Provider declares/converges desired availability | Managed does not mean Platform performs every restart; ownership must be explicit |
| F11 | External Runtime shared contract | **SURVIVES** | Remote authenticated Gateway exposes the same protocol while lifecycle/infrastructure remain external | Shared interaction/observation semantics with different ownership/capabilities is plausible |
| F12 | State boundary | **CHALLENGED** | Workspace, per-agent/session SQLite, credentials and runtime ops state are distinct but physically/semantically mixed | Requirements/references fit Candidate; ownership/portable subset cannot be inferred from directories |
| F13 | Descriptor/package metadata | **SURVIVES** | npm/source/image/service/Kubernetes/remote forms require distinct immutable realization metadata | Descriptor should not assume container image; schema/protocol/state compatibility matter |
| F14 | Capability Declaration | **SURVIVES** | Tools, Skills, plugins/MCP, remote mode, cancel, probes and lifecycle vary independently | Capability vocabulary is necessary but must not flatten Tool vs Skill or promise runtime internals |
| F15 | Control Plane Core source change = 0 | **SURVIVES** | Repository inspection after the spike shows no production source modification; only this experiment artifact is added | Second-runtime anatomy is expressible without OpenClaw-specific Core code; implementation remains unproven |

## 14. AP-S5-002 Assessment

**SUPPORTED** — Runtime Choice, Not Runtime Collection.

OpenClaw is not a second container logo behind a common start method. It is a
shared, stateful control plane/runtime with native Agents, Sessions, routing,
channels, tools, workspaces and asynchronous Runs. Supporting it should mean
choosing a compatible realization/binding and respecting its ownership model,
not importing all native concepts into Platform Core or provisioning one copy
per Platform Agent by default.

## 15. AP-S5-003 Assessment

**SUPPORTED** — Enterprise Capability Ownership.

OpenClaw exposes rich runtime-native Tools, Skills, plugins and MCP mappings,
but these are runtime mechanisms rather than the enterprise capability identity
itself. A Provider can translate a platform-owned binding into those mechanisms
without Core learning OpenClaw internals. Evidence also warns that policy,
credentials, sandboxing and plugin readiness must remain governed above the
runtime-specific projection.

## 16. AP-S5-004 Assessment

**SUPPORTED** — Runtime / Model Responsibility Separation.

OpenClaw includes native model-provider selection, fallback and credential
rotation inside the runtime. That does not make the Runtime identical to a
Model. Gateway/process health is explicitly separable from model credential/
provider probes and Run completion. A platform Model Plane may have reduced
visibility when OpenClaw owns native model routing, but Core should not encode
OpenClaw provider/model fields.

## 17. Candidate v0 Contradictions

No explicit statement in the decomposed Candidate v0 is contradicted.

The following stronger assumptions would be contradicted and must not be added
to Candidate v0:

1. Runtime Instance = Gateway = process = Pod/container = Agent Instance.
2. One Platform Agent Instance requires one Gateway or one container.
3. A runtime interaction is synchronous request/response without acceptance,
   correlation or event phases.
4. Gateway reachable/Pod Ready implies dependencies ready or Run success.
5. Managed means the Platform itself restarts every process.
6. External runtime infrastructure availability can be inferred from endpoint
   reachability.
7. All durable runtime state is Agent-owned or portable.
8. Capability means a single native Tool schema.
9. Package/distribution metadata can assume a container image.

## 18. Candidate v0 Strengthened Areas

1. Provider isolation: OpenClaw-native RPC, routing, agent/session selection,
   configuration, errors and events can remain outside Core.
2. Binding/realization separation: necessary for shared Gateway cardinality.
3. Optional asynchronous interaction with correlation/result/event projection.
4. Tri-state layered observation and explicit dependency separation.
5. Ownership-aware managed versus external modes over one shared conceptual
   contract.
6. Desired semantic recovery separated from native/supervisor/Kubernetes action.
7. Distribution metadata separated from logical Runtime Descriptor identity.
8. Persistence requirements without claims of state ownership or portability.
9. Capability declarations instead of a mandatory monolithic runtime interface.

## 19. Unknowns Requiring Checkpoint B

1. Start a pinned immutable OpenClaw distribution and capture exact process,
   ports, files, migrations and probe payloads without model credentials.
2. Validate authenticated Gateway protocol handshake and exact version fields.
3. Submit a no-real-model or controlled-failure Run and capture `agent`
   acceptance, `runId`, event ordering, `agent.wait`, terminal failure and
   persistence behavior.
4. Test cancellation before start, while queued, during model wait and during a
   tool call; determine idempotency and terminal race behavior.
5. Kill/restart Gateway under its supervisor and observe accepted/active Run,
   Session and event-stream recovery semantics.
6. Verify `/healthz`, `/readyz`, `/startupz`, WS health and model/plugin probes
   on the exact pinned distribution; record unsupported routes explicitly.
7. Create two Agents and multiple Sessions in one Gateway; confirm storage and
   policy isolation without inspecting credential values.
8. Determine whether deleting an Agent archives, migrates or deletes its
   Sessions/Workspace and what a Provider may safely own.
9. Validate remote Gateway behavior when infrastructure evidence is unavailable
   and when transport/auth fails independently.
10. Inventory persistent state before/after restart and replacement with same
    versus fresh storage; do not infer portability.
11. Test one bounded Capability Binding translation (for example a harmless
    workspace Skill or disabled mock MCP tool) without Core changes.
12. Establish immutable release/package/image digest and architecture support;
    `main` must not be the Checkpoint B execution artifact.

No real model completion is required until separately authorized by Checkpoint
B scope.

## 20. Repository Validation

| Check | Result |
|---|---|
| Production Source Changed | **No**. Control Plane Core source change = 0. |
| Tests | Not applicable to a research-only Markdown artifact; no product tests run. |
| Lint | Not applicable; no source/config code added. |
| `git diff --check` | **PASS** (2026-08-22; no output). |
| Secrets | No secrets added; source/evidence contains only public identifiers and URLs. |
| Cleanup | No OpenClaw process/container, state directory, credentials or temporary runtime assets created. |
| Git Status | Branch `codex/s5-spike-001-checkpoint-a`; one untracked intended path: `experiments/s5-spike-002-runtime-openclaw/`. No other worktree changes reported by `git status --short --branch`. |

### Primary authoritative references

All references are official OpenClaw sources. Hosted docs were retrieved on
2026-08-22; source identity is pinned above.

- [Pinned OpenClaw source tree](https://github.com/openclaw/openclaw/tree/4343b38ce7630fddaa16bfb72262e071d25424f6)
- [Gateway runbook](https://docs.openclaw.ai/gateway)
- [Gateway protocol](https://docs.openclaw.ai/gateway/protocol)
- [Agent loop](https://docs.openclaw.ai/agent-loop)
- [Multi-agent routing](https://docs.openclaw.ai/concepts/multi-agent)
- [Sessions](https://docs.openclaw.ai/concepts/session)
- [Agent workspace](https://docs.openclaw.ai/concepts/agent-workspace)
- [Health checks](https://docs.openclaw.ai/gateway/health)
- [Kubernetes deployment](https://docs.openclaw.ai/install/kubernetes)
- [Models and authentication](https://docs.openclaw.ai/gateway/authentication)
- [Capabilities overview](https://docs.openclaw.ai/tools)

## 21. Recommendation

**PASS_TO_CHECKPOINT_B**

Checkpoint B should be a bounded, pinned-distribution falsification experiment,
not an integration. It should prioritize native async interaction/cancellation,
shared-Gateway cardinality, layered readiness, recovery ownership and state
inventory. Human review is still required before changing Candidate v0,
freezing any Contract, or implementing a Provider.

**STOP. Do not begin Checkpoint B automatically.**
