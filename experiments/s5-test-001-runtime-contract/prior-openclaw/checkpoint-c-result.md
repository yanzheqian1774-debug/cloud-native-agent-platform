# S5-SPIKE-002 — CHECKPOINT C RESULT

## 1. Overall

**PASS**

Hermes and OpenClaw provide enough materially different evidence to produce a
smaller cross-runtime Runtime Contract Candidate v1 for human review. Candidate
v1 is architecture evidence only: it is not frozen, not an ADR, not a production
schema, and not authorization to implement.

The synthesis removes one weak abstraction and narrows several others:

- **Runtime Instance is rejected as a universal platform concept.** Neither
  runtime provides stable cross-runtime semantics beyond Runtime Binding plus
  Provider-specific realization references.
- **Synchronous `Invoke -> Result` is rejected as the universal interaction
  model.** Hermes returned a blocking response; OpenClaw returned acceptance and
  correlation before a separately observed terminal outcome.
- **The minimum interaction lifecycle is hybrid:** submit with correlation,
  then either return a terminal outcome inline or observe it later. Separate
  wait, streaming and cancellation are conditional capabilities.
- **Runtime Binding survives** as the logical association between Agent
  Instance intent, Provider/runtime selection, ownership mode, references and
  Provider realization. It does not impose 1:1 cardinality.
- **Managed and External are ownership modes sharing one semantic boundary,**
  not separate Contracts or runtime types.
- **Observation remains layered.** Infrastructure and dependencies are
  conditional; protocol availability is useful Provider evidence but is not
  justified as a new universal Runtime condition; execution is not runtime
  health.
- **Persistence is not portability.** The Runtime boundary declares
  requirements, references and continuity constraints without claiming State
  ownership.

No new runtime check was required. No production source or prior evidence was
changed.

## 2. Evidence Baseline

### Hermes — S5-SPIKE-001

Accepted evidence used:

- Checkpoint A/A.2: Hermes v0.20.4,
  `nousresearch/hermes-agent:v2026.8.18`, immutable image digest, three real
  provisions, real Gateway/API interaction, layered health ambiguity and HTTP
  200 semantic failure.
- Checkpoint B: native s6 process recovery, plain-Docker Provider recreation,
  Kubernetes workload recreation, same/fresh-state comparisons, persistence
  inventory, recovery ownership and instance/cardinality analysis.
- Checkpoint C: Hermes-derived Candidate v0 and responsibility/capability
  matrices.
- ED-S5-001 closure attempts: failure evidence only. Two real Hermes responses
  were semantic failures with zero usage; later controlled attempts stopped at
  runtime availability. No successful real-model completion is claimed.

### OpenClaw — S5-SPIKE-002

Accepted evidence used:

- Checkpoint A: official source/docs anatomy, Gateway/Agent/Session/Run/
  Workspace distinctions, shared topology, async protocol, state and
  capability model.
- Checkpoint B: real OpenClaw `2026.7.1-2 (0790d9f)` Gateway, immediate native
  acceptance with `runId`, independent terminal observation with `agent.wait`,
  normalized missing-model-auth failure, stop/restart observation, state
  inventory, isolated Provider and generic-caller contamination test.
- Experimental boundary/provider/tests: generic submit/handle/event/outcome
  concepts, Provider isolation and 4 passing spike-local tests.

### Integrity and limits

- Repository base: `d5c6d998ec3c506323157d8850248a331c4d18d2`.
- Branch: `codex/s5-spike-002-openclaw`.
- Checkpoint A SHA-256:
  `ff9046f2ec134af64f42b3d5b569508749854e84a57b3eb563e421a176c91e4a`.
- Checkpoint B SHA-256:
  `e1cb8934d0a10789b7448ecec685671e35f082508a672799f2dec88c2375413e`.
- No successful third-party real-model completion exists.
- No live Hermes stream/cancel/external-mode/upgrade test exists.
- No live OpenClaw successful model, cancel, assistant/tool delta stream,
  multi-Agent, managed container/Kubernetes or external remote test exists.
- Neither runtime demonstrated horizontal scale or cross-runtime state
  portability.
- The same unchanged generic caller/interface was not executed against both
  Providers.

## 3. Hermes vs OpenClaw Comparison Matrix

Classification meanings:

- **COMMON_SEMANTIC** — stable cross-runtime meaning is evidenced.
- **PROVIDER_SPECIFIC** — native representation/action belongs in Provider.
- **CONDITIONAL_CAPABILITY** — supported/required only when declared.
- **EXECUTION_SEMANTIC** — belongs to an execution outcome/lifecycle, not
  Runtime health/lifecycle.
- **UNRESOLVED** — evidence is insufficient.

| Concern | Hermes evidence | OpenClaw evidence | Classification | Candidate implication |
|---|---|---|---|---|
| Runtime identity | Hermes v0.20.4/release and image identity | OpenClaw version + native build hash | COMMON_SEMANTIC | Descriptor needs logical runtime identity distinct from artifact |
| Distribution/package | immutable OCI image/digest, entrypoint, architecture | npm integrity, bundled entrypoint, build hash; manifest/tag anomaly | COMMON_SEMANTIC | immutable realization metadata required; container assumptions rejected |
| Binding | experimental logical binding survived container/PID replacement | binding held endpoint + Agent + Session selection across Runs/restart | COMMON_SEMANTIC | retain logical Runtime Binding with opaque native data |
| Realization | container, Pod, profile, gateway process | Gateway endpoint/process, Agent/Session; host process realization | PROVIDER_SPECIFIC | Provider realization identity/reference only |
| Agent mapping | container/profile mapping remained ambiguous | Agent is logical per-persona scope in shared Gateway | PROVIDER_SPECIFIC | no universal Agent Instance mapping/cardinality |
| Session mapping | native Sessions directory; semantics unpopulated/unknown | durable Sessions observed; Agent:Session 1:N | PROVIDER_SPECIFIC | Session reference may be opaque binding/execution detail |
| Execution/run mapping | blocking chat completion with runtime request ID/correlation | accepted `runId`, queued Run, later terminal snapshot | EXECUTION_SEMANTIC | cross-runtime correlation/outcome; native Run object not universal |
| Gateway/process topology | s6 container supervises Gateway; process can restart in container | one Gateway process hosts Agent/Sessions/Runs; process replaced on restart | PROVIDER_SPECIFIC | no process/Gateway/Agent 1:1 assumption |
| Lifecycle | managed availability through Provider/substrate/native layers | foreground/service lifecycle; Provider observed stop/restart | COMMON_SEMANTIC | desired availability + ownership, not universal imperative methods |
| Provision | real Docker/Kubernetes managed provision | plausible upstream, not exercised in B | CONDITIONAL_CAPABILITY | managed provision optional |
| Configuration | env, profile/config, port/API settings | JSON config, Agent/model/plugin settings | PROVIDER_SPECIFIC | Provider translates opaque/reference intent |
| Observation | container, gateway, API and detailed health | health RPC, protocol handshake, execution outcome | COMMON_SEMANTIC | normalized observations with evidence/time/reason |
| Health/readiness | detailed model health false-positive; API can be down while gateway runs | Gateway health true while model auth execution fails | COMMON_SEMANTIC | runtime/dependency/execution separation required |
| Interaction | real HTTP OpenAI-compatible blocking endpoint | real WS RPC async submit/wait | CONDITIONAL_CAPABILITY | interaction declared capability with shared execution semantics |
| Submission | HTTP call blocks until native response | `agent` immediately accepts | COMMON_SEMANTIC | submit exists; acceptance phase may be immediate-terminal or deferred |
| Correlation | generic correlation + Hermes runtime request ID observed | idempotency key mapped to `runId` | COMMON_SEMANTIC | opaque cross-runtime correlation required for submitted execution |
| Streaming | documented SSE, not live-tested | Gateway events advertised; assistant/tool deltas not live-tested | CONDITIONAL_CAPABILITY | stream optional; semantics unresolved |
| Wait/observe | blocking response serves as inline terminal observation | separate reconnectable `agent.wait(runId)` live-tested | CONDITIONAL_CAPABILITY | terminal outcome required; separate wait/poll optional by interaction mode |
| Completion | no successful model completion | no successful model completion | UNRESOLVED | successful payload/fidelity not freeze-ready |
| Failure | HTTP 200 assistant/error content, zero usage; runtime availability failures | terminal `error` after accepted Run | EXECUTION_SEMANTIC | semantic failure independent of transport/runtime availability |
| Cancellation | upstream hint only, not exercised | native abort method exists, not exercised | UNRESOLVED | optional capability; no common cancel semantics yet |
| Recovery | s6, Provider or Kubernetes acted at different failure layers | operator restarted; Provider observed protocol recovery only | COMMON_SEMANTIC | detection/action/observation/verification ownership model |
| Persistence | named volume preserved runtime-local material; fresh storage lost it | SQLite/session/trajectory/workspace files survived restart | COMMON_SEMANTIC | declare requirements/continuity; do not claim portability |
| State ownership | runtime-local vs potential Agent/session/memory remained mixed | runtime/Agent/Session/Workspace/credential classes mixed | COMMON_SEMANTIC | physical storage does not determine semantic ownership |
| Workspace | profile/home includes skills/sessions/memories/config | separate Agent Workspace with bootstrap/memory/skills/files | PROVIDER_SPECIFIC | Runtime may consume workspace reference; Platform Workspace is separate boundary |
| Model binding | Provider translated provider/model/credential; native health misleading | runtime selected provider/model/auth store; Provider normalized missing auth | COMMON_SEMANTIC | runtime consumes translated binding; Model governance remains outside |
| Capability/tool mechanism | skills/tools bundled under runtime home/profile | distinct Tools, Skills, Plugins and MCP mechanisms | PROVIDER_SPECIFIC | platform capability identity cannot equal native mechanism |
| Managed mode | live Docker/Kubernetes provision and layered recovery | lifecycle/ownership model plausible; host process exercised, not managed provision | CONDITIONAL_CAPABILITY | ownership mode over shared Contract |
| External mode | not live-tested | remote Gateway documented; same interaction boundary plausible, not remotely deployed | CONDITIONAL_CAPABILITY | shared semantics plausible; production proof absent |
| Scaling evidence | concurrent-writer warning; no scale test | shared Gateway cardinality; no horizontal scale test | UNRESOLVED | scaling declaration optional/unknown |
| Upgrade evidence | image replacement concept only | distribution anomaly/update mechanisms; no upgrade test | UNRESOLVED | upgrade optional; compatibility metadata required |
| Cleanup/ownership | Provider cleanup and Kubernetes resources; state continuity mattered | external/shared Gateway requires non-destructive disconnect semantics | COMMON_SEMANTIC | Provider must respect resource ownership; cleanup capability varies |

## 4. Candidate v0 Disposition

| Candidate v0 element | Disposition | Cross-runtime evidence and v1 treatment |
|---|---|---|
| Runtime Descriptor | **SURVIVED** | both runtimes need logical identity, Provider compatibility and capability/constraint discovery without Core branches |
| Package/distribution metadata | **MODIFIED** | retain as versioned realization metadata associated with Descriptor; add integrity, entrypoint, build/source identity and protocol/state compatibility; do not assume OCI package |
| Runtime Binding | **MODIFIED** | survives strongly, but contains association/references/ownership only; cardinality and native selection remain Provider-specific |
| Runtime Instance | **REJECTED** | no stable platform semantics distinct from Binding plus Provider realization reference; native units differ too much |
| Realization | **SURVIVED** | retain only as Provider-specific observed/owned resource identity and evidence; not a universal platform object |
| Lifecycle Semantics | **MODIFIED** | desired availability and ownership survive; imperative provision/start/restart/delete are optional capabilities, not universal API |
| Provider Boundary | **SURVIVED** | both runtime prototypes isolate native configuration, interaction, errors, health and realization detail; production proof remains absent |
| Interaction Contract | **MODIFIED** | replace invoke-shaped ambiguity with hybrid submit/correlation/terminal-outcome lifecycle; inline and deferred outcomes supported |
| Observation Contract | **MODIFIED** | retain normalized observation; add NOT_APPLICABLE; keep conditions conditional/scoped; protocol evidence does not become universal condition |
| Capability Declaration | **SURVIVED** | lifecycle, interaction, streaming, cancel, state, recovery, scale and upgrade vary independently |
| Managed Runtime semantics | **MODIFIED** | becomes Binding ownership mode with optional lifecycle capabilities, not a separate type/Contract |
| External Runtime semantics | **MODIFIED** | same Contract and Binding semantics with external ownership/limited visibility; no separate type/Contract |
| Condition model | **MODIFIED** | InfrastructureAvailable conditional; RuntimeAvailable minimum normalized runtime observation; DependencyReady scoped/conditional; TaskReady rejected; ProtocolAvailable Provider detail/optional observation |
| Recovery ownership | **SURVIVED** | detection -> appropriate owner acts -> Provider observes -> Platform verifies is supported by both runtimes |
| State boundary | **MODIFIED** | Contract declares storage/reference/continuity constraints and observed state classes only; Runtime does not own portable State semantics |

## 5. Interaction Contract Finding

### Option evaluation

| Option | Result | Evidence |
|---|---|---|
| A. Invoke -> Result | **REJECTED as universal** | fits Hermes blocking surface only; loses OpenClaw acceptance, handle and later outcome |
| B. Submit -> Handle -> Observe -> Outcome | **SUPPORTED for async runtimes** | directly observed in OpenClaw; Hermes can be projected as already-terminal submission but did not expose separate observe |
| C. Hybrid | **SELECTED** | faithfully represents Hermes inline terminal response and OpenClaw deferred terminal observation without forcing fake async or sync behavior |
| D. Another model | **NOT JUSTIFIED** | no smaller model covers both semantic paths |

### Minimum cross-runtime execution semantics

```text
Submit execution intent
  -> correlation/handle
  -> either:
       terminal outcome returned inline
     or
       accepted/non-terminal state -> later observe/wait/event -> terminal outcome
```

The handle may be logically produced and consumed within one Provider call for a
blocking runtime, but correlation must remain available in the outcome/evidence.
This does not require a durable platform Run resource.

| Candidate concept | Classification | Reason |
|---|---|---|
| Submit | **REQUIRED** | both runtimes accepted execution input |
| Execution Handle | **REQUIRED when submission is non-terminal; OPTIONAL as separately exposed object for inline completion** | OpenClaw requires it; Hermes blocking path need not expose an intermediate object |
| Correlation ID | **REQUIRED** | generic/runtime correlations observed in both; exact native propagation Provider-specific |
| Observe | **REQUIRED for non-terminal accepted work** | otherwise OpenClaw outcome cannot be recovered; inline Hermes result already supplies observation |
| Wait | **OPTIONAL CAPABILITY** | OpenClaw live-tested; Hermes blocking endpoint does not need separate wait |
| Stream | **OPTIONAL CAPABILITY** | native documentation exists; no shared live semantics |
| Cancel | **OPTIONAL CAPABILITY / UNRESOLVED semantics** | neither runtime live-tested |
| Terminal Outcome | **REQUIRED when interaction is declared** | both produced semantic terminal failure |
| Semantic Success | **REQUIRED category; successful shape UNRESOLVED** | correctness requires distinction, though neither third-party runtime succeeded |
| Semantic Failure | **REQUIRED category** | live evidence in both contradicts transport-only success |
| Usage | **OPTIONAL outcome metadata** | Hermes exposed zero usage; OpenClaw failure did not establish common fidelity |
| Latency/timestamps | **OPTIONAL outcome metadata; observation time required** | both measured time, but native fields differ |
| Native Evidence Reference | **OPTIONAL PROVIDER DETAIL** | useful for diagnostics; must be bounded/sanitized and cannot redefine outcome |

## 6. Runtime Binding Finding

**Runtime Binding survived both runtimes.**

Minimum responsibility: a platform-owned logical association connecting Agent
Instance runtime intent to one Provider/runtime selection and ownership mode,
carrying opaque references the Provider needs, while outliving replaceable
native realizations. It is not the runtime process, Gateway, Agent, Session,
profile, container, Pod, endpoint or execution.

| Candidate Binding association | Classification | Evidence |
|---|---|---|
| Agent Instance identity | **REQUIRED** | Binding needs the platform-side subject; Agent Instance remains future/not implemented |
| Runtime Provider | **REQUIRED** | translation/observation owner differs by runtime |
| Runtime Descriptor/package | **REQUIRED selection/reference** | reproducibility and compatibility require runtime/distribution identity |
| Mode/ownership | **REQUIRED** | managed/external behavior differs primarily by authority/ownership |
| Configuration references | **OPTIONAL** | both consume config, but defaults/external preconfiguration may suffice |
| Credential references | **OPTIONAL** | required only for selected interactions/dependencies; values never belong in Binding/status |
| Workspace references | **OPTIONAL** | native workspace semantics differ and may be external/prebound |
| State references | **OPTIONAL** | continuity/storage may be required; State ownership remains outside Runtime Contract |
| Observed realization references | **OPTIONAL observation, not desired identity** | useful for recovery/debugging; native units replace/change |

Cardinality is **CONDITIONAL/Provider-specific**. Candidate v1 must not prescribe
Agent Instance:Binding, Binding:Gateway, Binding:Agent, Binding:Session,
Binding:process or Binding:realization as universal 1:1 relationships.

## 7. Runtime Instance Finding

**REMOVE Runtime Instance from Candidate v1.**

No stable platform-level semantic remains after subtracting:

- Agent Instance: platform logical Agent lifecycle identity;
- Runtime Binding: platform logical association and ownership/reference point;
- Provider realization: native endpoint/profile/Gateway/container/Pod/process
  identities and resources;
- execution correlation: Session/Run/request identity.

For Hermes, a candidate Runtime Instance could mean container, profile, Gateway
or a logical unit across replacement. For OpenClaw, one Gateway/process can host
many Agents, Sessions and Runs, while an Agent is logical state and tool
sandboxes may create extra containers. Naming a universal Runtime Instance does
not add evidence-supported semantics; it only relocates ambiguity.

Candidate v1 should use:

- Binding identity for the stable platform association;
- Provider-specific realization references for observed/owned native resources;
- execution handle/correlation for submitted work.

If a future third runtime demonstrates a stable cross-runtime lifecycle object
not covered by these concepts, Runtime Instance may be reconsidered. It is not
retained as an unresolved placeholder.

## 8. Observation / Condition Finding

| Candidate observation | Disposition | Evidence-supported meaning |
|---|---|---|
| InfrastructureAvailable | **CONDITIONAL** | applicable when Provider/platform owns or can authoritatively observe required substrate resources; external visibility may be absent |
| RuntimeAvailable | **UNIVERSAL minimum when lifecycle/interaction/observation is declared** | Provider can determine whether the promised runtime surface responds; UNKNOWN allowed |
| ProtocolAvailable | **PROVIDER_DETAIL / optional diagnostic observation** | OpenClaw distinguished WS handshake from process; Hermes distinguished Gateway/API, but evidence does not justify a universal named condition |
| DependencyReady | **CONDITIONAL and scoped** | only for declared required dependency; native aggregate health may lie/omit scope |
| Execution state/outcome | **EXECUTION_NOT_RUNTIME** | acceptance, running, completion/failure/cancel belong to submitted execution |
| TaskReady | **REJECTED as Runtime condition** | neither runtime proved independent task readiness; it conflates scheduling/execution with health |

### Value model

Candidate v1 needs **TRUE / FALSE / UNKNOWN / NOT_APPLICABLE**.

- `UNKNOWN`: the condition applies, but current evidence is missing, stale or
  insufficient. Example: external infrastructure is expected to exist but the
  Provider cannot observe it; dependency usability before a real probe.
- `NOT_APPLICABLE`: the condition does not participate in the selected
  Binding/mode/capability. Example: Pod/container availability for a direct host
  process realization, or managed-infrastructure condition for a purely
  external connection whose Contract excludes infrastructure semantics.

They are semantically distinct. `NOT_APPLICABLE` must not count as false or
degraded; `UNKNOWN` must not count as true/ready. An omitted undeclared
condition may be preferable to emitting NOT_APPLICABLE, but the value remains
needed when a common observation projection explicitly enumerates conditions.

Minimum observation fields remain: normalized name/scope, value, stable reason,
bounded message, observation time, transition time when known, and optional
sanitized native evidence/realization reference.

## 9. Managed / External Finding

**Option C: Binding/ownership modes sharing one Contract.**

Separate Contracts or Runtime types are not justified. Descriptor, Binding,
capability declaration, interaction, normalized outcome and observation share
the same semantics. Ownership/capability differences determine allowed actions.

| Concern | Managed mode | External mode |
|---|---|---|
| Provision ownership | Provider/substrate may own if declared | external owner; normally unsupported |
| Infrastructure visibility | conditional, often available | often UNKNOWN or NOT_APPLICABLE to Contract promise |
| Restart ownership | native runtime, substrate or Provider as declared | external owner unless explicitly delegated |
| Recovery ownership | layered; Platform verifies promised semantics | external owner acts; Provider observes available semantics |
| Cleanup ownership | Provider cleans only resources it owns | disconnect/unbind; never delete shared external resources |
| Upgrade ownership | optional Provider/substrate capability | external owner; Provider reports compatibility |
| Observation | normalized shared model | same model with reduced visibility |
| Interaction | shared execution semantics when declared | same |

“Managed” means desired lifecycle/operational semantics and ownership are
declared and can converge; it does not mean the Control Plane performs every
action.

## 10. Recovery Model Finding

Cross-runtime sequence:

```text
promised condition/failure detected
  -> lowest appropriate declared owner acts
  -> Provider observes and translates evidence
  -> Platform verifies the semantics promised by the Binding
```

Classification: **SUPPORTED**.

Hermes demonstrated three concrete action owners: native s6 restarted Gateway,
Kubernetes replaced a Pod, and the experimental Provider recreated a plain
Docker container. OpenClaw demonstrated operator-owned process restart and
Provider-observed Runtime/Protocol FALSE -> TRUE, while execution/dependency
recovery remained unverified.

Modification from simplistic reconciliation: the Platform owns the desired
semantic and verification criteria, not every trigger or action. Provider,
runtime, substrate and external owner participation must remain explicit.

## 11. State Boundary Finding

| State class | Hermes evidence | OpenClaw evidence | Runtime Candidate v1 treatment |
|---|---|---|---|
| Runtime Internal | config, gateway metadata, logs, skill copies | config/last-good, shared SQLite, logs/audit/stability, caches | Provider declares/binds requirements and continuity; native format stays internal |
| Agent State | profile-scoped potential identity/memory/session | Agent config/identity/model/routing data | expose references/constraints only; ownership unresolved outside Runtime Contract |
| Session State | native Sessions directory, unpopulated | persisted Session index/transcripts/trajectory linkage | native semantics Provider-specific; no portability claim |
| Execution State | request/native response IDs and logs | run correlation, terminal snapshots, trajectories | execution correlation/outcome only; persistence capability optional |
| Workspace State | Hermes home/profile mixes config/skills/memory | separate Agent Workspace/bootstrap/memory/skills/files | Runtime may consume reference; Platform Workspace boundary separate |
| Credential State | env/Secret/profile `.env` mechanisms | Gateway token/model auth store/reference mechanisms | Provider consumes references; governance owns values; never status/persistence by Contract |
| Potential Portable State | sessions/memories only speculative | selected instructions/memory/artifacts speculative | unresolved and outside Runtime Contract; State Contract needed later |

Runtime Contract Candidate v1 must declare only:

- storage/persistence capability and requirements;
- state/workspace/credential references needed by the Binding;
- ownership and cleanup constraints;
- continuity expectations across realization replacement/restart/upgrade;
- whether native execution/session persistence is supported;
- observed state requirement violations without exposing secret/native schema.

Provider must translate references, bind storage/config/credentials safely,
observe required state presence where possible, and respect ownership on
cleanup/recovery. Portable-state semantics, migration, conflict resolution,
retention/governance and Platform State ownership remain outside Runtime
Contract Candidate v1.

## 12. Capability / Model / Workspace Boundary

| Boundary principle | Assessment | Evidence |
|---|---|---|
| Runtime executes enterprise capabilities but does not own enterprise capabilities | **STRONGLY_SUPPORTED** | Hermes skills/tools and OpenClaw Tools/Skills/Plugins/MCP are materially different native mechanisms; Provider translation avoids Core coupling |
| Runtime consumes model binding/configuration but does not own enterprise Model Plane governance | **STRONGLY_SUPPORTED** | both runtimes were available while native model dependency failed; credentials/config/routing were runtime-specific, governance intent remained outside |
| Runtime may consume/use Workspace semantics while Platform Workspace ownership remains separate | **SUPPORTED** | OpenClaw explicitly separates Workspace from runtime state; Hermes mixes home/profile categories, so translation/reference is needed rather than Runtime ownership |

The evidence supports separation, not a Capability, Model or Workspace Contract
design. Concrete cross-runtime binding translation remains evidence debt.

## 13. AP-S5-001 Assessment

**SUPPORTED — Restart is not Recovery.**

- Hermes: new PID preceded API verification; replacement Pod/process did not
  prove model/task usability; fresh state changed continuity semantics.
- OpenClaw: restarted Gateway restored health/protocol only; failed execution
  was not resumed/retried and model dependency remained unavailable.

Recovery means the semantics promised by the particular Binding/mode have been
re-established and verified. A restart is one possible action/evidence point.

## 14. AP-S5-002 Assessment

**SUPPORTED as architecture/product direction, not technically proven product
strategy.**

Two runtimes required different topology, distribution, state, interaction,
health, recovery and native capability mechanisms, yet common platform
semantics remained small. This supports officially choosing a small supported
set while enabling other Providers and keeping product semantics independent of
runtime internals.

The spike does not prove ecosystem demand, support cost, certification policy,
market selection or the optimal number of official runtimes.

## 15. AP-S5-003 Assessment

**STRONGLY_SUPPORTED.**

Runtime-native skill/tool/plugin representations differ enough that making them
the enterprise capability identity would couple Core and governance to one
runtime. Provider translation is plausible with zero Core changes, though a
concrete cross-runtime Capability Binding was not executed.

## 16. AP-S5-004 Assessment

**STRONGLY_SUPPORTED.**

Both runtime surfaces were available while model configuration/credentials
made execution semantically fail. Provider-specific model selection and client
behavior are Runtime execution concerns; enterprise model policy, credential
governance, catalog/routing intent and cross-runtime observability remain Model
Plane concerns.

## 17. Provider Extension Test

**PARTIALLY_PROVEN.**

Proven experimentally:

- Hermes Provider isolated Hermes paths/profiles/config/API/error semantics;
- OpenClaw Provider isolated Gateway RPC/Agent/Session/run/model error semantics;
- both kept Control Plane Core source changes at zero;
- both exposed native-free generic callers within their experiments;
- OpenClaw added a materially different Provider without requiring a Core
  runtime branch.

Not proven:

- one identical generic caller/interface was executed unchanged against both
  Providers. Hermes used `RuntimeRequest/RuntimeResult`; OpenClaw deliberately
  introduced lifecycle-shaped request/handle/event/outcome types to falsify the
  synchronous assumption.
- production Provider SDK/API stability, conformance tests, packaging,
  security, compatibility and operational integration.

Candidate v1 supplies a cross-runtime proposal that could enable the unchanged
caller test next; it must not retroactively label that test complete.

## 18. Runtime Contract Candidate v1

> **CANDIDATE v1 · NOT FROZEN · HERMES + OPENCLAW DERIVED**

### 18.1 Stable Platform Semantics

- A logical Runtime Binding associates Agent Instance runtime intent with a
  Runtime Provider/Descriptor, ownership mode, references and declared
  capabilities.
- Agent Instance, Runtime Binding, Provider realization and submitted execution
  correlation remain distinct.
- Platform semantics define desired availability, normalized observations,
  execution outcome categories, ownership constraints and semantic recovery
  criteria.
- No universal Runtime Instance object exists in v1.

### 18.2 Runtime Descriptor / Distribution Metadata

- Descriptor identifies logical runtime, compatible Candidate/Provider ranges,
  modes, capabilities, constraints and a versioned distribution realization.
- Distribution metadata records immutable artifact integrity, native runtime
  version/build/source identity when available, executable/start mechanism,
  platform/architecture requirements, configuration/health mechanisms,
  protocol/state compatibility, ports/endpoints, storage/credential needs and
  known concurrency/scale constraints.
- Format is not assumed to be an image, package, binary or service.

### 18.3 Runtime Binding

- Required association: Agent Instance identity, Provider, Descriptor/
  distribution selection and ownership mode.
- Optional references: configuration, credentials, Workspace and State.
- Optional observations: current Provider realization references.
- Cardinality/native identity remains Provider-specific.

### 18.4 Provider Boundary

- Declares compatibility, capabilities, constraints and ownership.
- Realizes or connects the Binding without runtime-specific Core branches.
- Translates native configuration/references/lifecycle/interaction/observation.
- Normalizes semantic outcomes/errors independent of transport status.
- Reports UNKNOWN/NOT_APPLICABLE honestly and preserves sanitized native
  evidence only as optional detail.
- Respects resource/state ownership during recovery, replacement and cleanup.

### 18.5 Lifecycle / Ownership Semantics

- Required: desired availability/ownership and convergence/cleanup intent for
  promised semantics.
- Concrete provision/start/restart/recreate/delete/upgrade actions are optional
  Provider/substrate/native/external-owner capabilities.
- Managed and External are Binding ownership modes over the same semantic
  boundary.

### 18.6 Observation Contract

- Minimum normalized runtime observation with value
  TRUE/FALSE/UNKNOWN/NOT_APPLICABLE, scope/reason, bounded message and time.
- RuntimeAvailable is the minimum runtime-level availability projection where
  runtime observation/interaction is promised.
- InfrastructureAvailable and scoped DependencyReady are conditional.
- Protocol/native health dimensions remain optional Provider evidence unless a
  future human decision promotes a cross-runtime semantic.
- Execution state/outcome is excluded from Runtime health.

### 18.7 Execution Interaction Contract

- Conditional as a Runtime capability; required responsibilities apply when
  execution interaction is declared.
- Submit execution intent without native paths/profile/Gateway concepts.
- Return correlation and either terminal outcome inline or non-terminal
  acceptance for later observation.
- For non-terminal acceptance, provide an outcome-observation mechanism.
- Normalize terminal semantic success/failure/cancel/timeout/unknown categories
  as supported, independent of transport/native status.
- Separate wait, stream and cancel are optional declared capabilities.
- Usage, latency/timestamps and sanitized native evidence are optional outcome
  metadata.

### 18.8 Capability Declaration

- Declares supported/limited/unsupported/unknown capabilities plus constraints,
  ownership and compatibility.
- Covers interaction mode, wait, stream, cancel, managed provision/lifecycle,
  external connection, observation visibility, native/workload recovery,
  persistence/recreate, multiple realizations, scale and upgrade as applicable.
- Unsupported capability is absence/declaration, never a misleading no-op.

### 18.9 Provider-Specific Realization

- Native endpoint, Gateway, process, container, Pod, profile, Agent, Session,
  workspace or service identity remains Provider-specific.
- Provider may expose bounded realization references for observation/audit/
  recovery without making them stable Platform identity.

### 18.10 State-Related Declarations / Constraints

- Declare persistence/storage/config/workspace/credential reference needs,
  ownership, cleanup and continuity expectations.
- Provider translates/binds and observes requirements without exposing secret
  values or claiming native state is portable.
- State portability/migration/Platform State semantics are explicit non-goals.

### 18.11 Recovery Semantics

- Detect promised semantic violation, let the appropriate declared owner act,
  let Provider observe/translate, and let Platform verify promised semantics.
- Restart/resource recreation alone never proves recovery.

### 18.12 Explicit Non-goals

- production schema/API/SDK or operation names;
- frozen Contract or conformance level;
- Runtime Instance abstraction;
- universal imperative lifecycle interface;
- Agent Instance/State/Capability/Model/Workspace Contract design;
- universal provision, infrastructure visibility, streaming, cancellation,
  scaling, upgrade, native health detail or portable state;
- runtime-specific Core fields/branches.

## 19. Required Cross-Runtime Responsibilities

| Responsibility | Classification | Minimum evidence-supported requirement |
|---|---|---|
| Descriptor identity/compatibility | REQUIRED CROSS-RUNTIME | identify logical runtime, Provider compatibility and constraints |
| Distribution reproducibility | REQUIRED CROSS-RUNTIME | immutable realization identity/integrity + executable/build compatibility facts |
| Runtime Binding association | REQUIRED CROSS-RUNTIME | join Agent Instance intent to Provider/runtime/mode without native identity collapse |
| Provider isolation | REQUIRED CROSS-RUNTIME | all native translation remains outside Core |
| Capability declaration | REQUIRED CROSS-RUNTIME | declare supported/unsupported/unknown behavior and constraints |
| Ownership declaration | REQUIRED CROSS-RUNTIME | identify resource/lifecycle/state/cleanup authority |
| Normalized observation | REQUIRED CROSS-RUNTIME | honest value/reason/time for promised runtime semantics |
| Runtime availability projection | REQUIRED CROSS-RUNTIME when runtime observation/interaction promised | distinguish runtime surface from infra/dependency/execution |
| Execution submission/correlation | REQUIRED CROSS-RUNTIME when interaction declared | native-free intent and opaque correlation |
| Terminal semantic outcome | REQUIRED CROSS-RUNTIME when interaction declared | success/failure categories independent of transport status |
| Deferred outcome observation | REQUIRED CROSS-RUNTIME when submission can be non-terminal | reconnect/wait/poll/event mechanism sufficient to reach outcome |
| Recovery ownership/verification | REQUIRED CROSS-RUNTIME for managed promises | action owner distinct from semantic verifier |
| Cleanup ownership safety | REQUIRED CROSS-RUNTIME | never delete external/shared/unowned resources/state |
| State/reference constraint declaration | REQUIRED CROSS-RUNTIME when state/config/credentials/workspace required | requirements/continuity only, no portability claim |

## 20. Optional Runtime Capabilities

- managed provision and workload lifecycle;
- native process recovery;
- substrate/workload recovery;
- recreate with continuity choices;
- external connection mode;
- infrastructure visibility;
- scoped dependency readiness observation;
- separate wait/poll operation;
- streaming/events;
- cancellation;
- usage/cost/latency/native evidence metadata;
- persistent native session/execution state;
- multiple Agents/profiles/realizations;
- horizontal scale/high availability;
- upgrade/migration coordination;
- native detailed-health projection;
- Workspace/State/Capability/Model binding translation features beyond minimal
  opaque references.

Each optional capability needs declared constraints and ownership. Lack of a
capability must not prevent the Runtime from satisfying smaller declared
semantics.

## 21. Provider-Specific Responsibilities

- resolve native artifact/entrypoint/service/endpoint details;
- map Binding references to native Agent/profile/Gateway/Session/workspace/
  process/container/service selection;
- translate runtime-native configuration, model/provider selection,
  credentials, Skills/Tools/Plugins/MCP and storage mechanisms;
- choose native submission payload/API/RPC and map correlation;
- interpret HTTP/RPC/native finish/error/event shapes;
- implement inline or deferred terminal observation according to capability;
- derive scoped dependency evidence without trusting misleading native health;
- combine substrate/process/protocol/native evidence;
- expose sanitized bounded diagnostics/realization references;
- select or defer concrete recovery action to native runtime/substrate/external
  owner;
- respect shared-resource/state ownership during cleanup and upgrade;
- report unsupported/unknown capability rather than emulate false success.

These responsibilities are Provider-specific implementations of shared
semantics, not fields to move into Core.

## 22. Rejected Abstractions

1. Universal platform-level **Runtime Instance**.
2. Universal imperative `provision/start/stop/restart/delete/invoke` interface.
3. Synchronous-only `Invoke -> Result` Contract.
4. Agent Instance = Runtime Binding/realization/Gateway/process/container/
   profile/Agent/Session/Run.
5. Universal 1:1 cardinality among those concepts.
6. One boolean READY or raw native health as semantic readiness.
7. `TaskReady` as a Runtime condition.
8. `ProtocolAvailable` as a new universal condition based only on OpenClaw's
   clearer protocol boundary.
9. Managed and External as separate Runtime Contracts/types.
10. Restart/recreate as proof of semantic recovery.
11. Persistent native state as proof of Agent ownership or portability.
12. Native Tool/Skill/plugin identity as enterprise Capability identity.
13. Runtime-native model routing as enterprise Model governance.
14. Container-image-only package metadata.
15. Unsupported optional operations implemented as successful no-ops.

## 23. Remaining Unknowns

- successful third-party result payload and semantic completion shape;
- cross-runtime successful usage/latency fidelity;
- persistent live event-stream ordering and reconnect/resume;
- cancellation races, idempotency and terminal classification;
- accepted/in-flight execution across Gateway/process replacement;
- dedupe/exactly-once expectations;
- one unchanged Candidate v1 caller and conformance suite across both Providers;
- external Hermes and real remote OpenClaw ownership/visibility behavior;
- OpenClaw multi-Agent live isolation and shared-Gateway cleanup;
- Hermes multi-profile behavior;
- managed OpenClaw container/Kubernetes recovery/state behavior;
- horizontal scale/HA and concurrency safety for either runtime;
- runtime upgrade/state-schema compatibility and rollback;
- concrete cross-runtime Capability Binding translation;
- concrete cross-runtime Model Binding/reference-only credential translation;
- Workspace ownership/translation fidelity;
- portable State subset, migration and semantic continuity;
- Descriptor trust/signature/publisher/compatibility-negotiation model;
- exact universal condition vocabulary and freshness policy;
- whether Runtime Binding is one per Agent Instance or supports multiple active/
  fallback runtimes;
- governance, audit, tenancy and security conformance.

## 24. Evidence Debt

### ED-S5-001 — Hermes Real Model Completion Evidence

**OPEN / CARRIED FORWARD.**

It is non-blocking for Candidate v1 synthesis but blocking for the Runtime
Contract Freeze Gate. Failed responses and runtime-availability failures remain
failure evidence only. They do not establish successful interaction.

Closure still requires a human-reviewed Hermes-supported secret-binding/
profile procedure and one successful real external-model execution through the
generic boundary, without exposing the credential.

### New OpenClaw evidence debt

- **ED-S5-002-01 — OpenClaw Successful Real-Model Completion:** OPEN. Real native
  acceptance/correlation/terminal failure was proven; success was not.
- **ED-S5-002-02 — OpenClaw Stream and Cancel Semantics:** OPEN. Persistent agent
  event ordering, reconnect/resume and cancellation races were not live-tested.
- **ED-S5-002-03 — OpenClaw Distribution Traceability:** OPEN. npm integrity and
  runtime build hash were captured, but package wrapper/manifest and source-tag
  traceability were inconsistent.
- **ED-S5-002-04 — Shared Gateway Ownership/Isolation:** OPEN. Multiple Sessions
  were live; multiple Agents and safe shared-resource cleanup were not.
- **ED-S5-002-05 — Managed/External Realization Evidence:** OPEN. host-process
  lifecycle was observed; managed Kubernetes/container and real remote external
  modes were not.

### Cross-runtime evidence debt

- **ED-S5-002-06 — Candidate v1 Shared Caller Test:** OPEN. Implement one
  experiment-only Candidate v1 caller/conformance harness unchanged across
  Hermes and OpenClaw Providers after human review of Candidate v1 vocabulary.

## 25. G-S5-RUNTIME-FREEZE-01 Status

| Freeze condition | Status | Evidence |
|---|---|---|
| 1. At least two materially distinct runtimes completed boundary evidence | **PASS** | Hermes blocking HTTP/container/s6 runtime and OpenClaw shared Gateway/Agent/Session/async RPC runtime completed A/B boundary evidence |
| 2. At least one third-party Managed Runtime completed successful real-model interaction end-to-end | **FAIL** | Hermes ED-S5-001 open; OpenClaw intentionally had no model credential/success |
| 3. Cross-runtime Candidate passed Human Architecture Review | **PENDING** | Candidate v1 is submitted by this report; no human approval yet |

**Overall freeze gate: FAIL / NOT ELIGIBLE TO FREEZE.**

Candidate v1 must remain non-frozen even if human review accepts its direction,
until condition 2 passes.

## 26. ADR Impact Candidates

No ADR was edited.

| ADR | Candidate disposition | Evidence-based rationale |
|---|---|---|
| ADR-0003 | **CLARIFY** | distinguish desired semantic recovery/verification from runtime-native, Provider and Kubernetes actions; avoid equating Agent readiness with workload/runtime health |
| ADR-0004 | **AMEND** | pluggable Runtime/Provider architecture survives, but universal imperative adapter/Runtime Instance assumptions should yield to Binding + capability/ownership + hybrid execution semantics; human review required |
| ADR-0005 | **CLARIFY** | both runtimes prove runtime availability separate from native model dependency/semantic execution; document reduced visibility/governance when runtime owns native model clients |

These are future human-owned disposition candidates, not approved changes.

## 27. What This Does NOT Prove

| Level | Proven | Not proven |
|---|---|---|
| Architecture Evidence | two different runtimes challenge/support Candidate concepts; Candidate v1 can be reviewed | correctness/completeness of final Runtime Contract; human approval |
| Experimental Provider Evidence | two isolated experimental Providers kept native details out of their callers and Core | one shared stable Provider SDK/API or unchanged caller across both |
| Production Provider Readiness | nothing | security hardening, HA, upgrades, migrations, conformance, support, packaging, performance, observability, compatibility |
| Runtime Certification | nothing | supported versions/platforms, capability guarantees, SLOs, isolation, vulnerability response, interoperability |
| Enterprise Production Readiness | nothing | tenancy, RBAC, policy, audit, secret governance, compliance, scale, disaster recovery, cost/SLA, operational support |

The spike also does not prove successful third-party model execution, semantic
recovery after an active execution failure, state portability, horizontal
scaling, safe multi-tenancy, upgrade compatibility, or end-to-end Capability/
Model/Workspace integration.

## 28. Repository Validation

| Check | Result |
|---|---|
| Branch/worktree | `codex/s5-spike-002-openclaw` at base `d5c6d99`; dedicated existing worktree |
| Production/Core source changes | **0** |
| S5-SPIKE-001 evidence | **PRESERVED**; no tracked diff/history rewrite |
| S5-SPIKE-002 A/B evidence | **PRESERVED**; hashes recorded in Section 2 |
| New artifact scope | only `experiments/s5-spike-002-runtime-openclaw/checkpoint-c-result.md` |
| Tests | **SKIPPED** — synthesis-only Markdown change; no code changed after Checkpoint B's 4 passing tests |
| Ruff/format | **SKIPPED** — no Python/source change in Checkpoint C |
| `git diff --check` | **PASS** — Checkpoint C checked with `--no-index`; no output |
| Secret scan | **PASS** — no API-key/private-key patterns found in experiment artifacts |
| Repository status | branch `codex/s5-spike-002-openclaw`; one intended untracked experiment directory; no tracked-file diff |
| New runtime experiment | **NONE**; preserved evidence was sufficient |

## 29. Human Decisions Required

1. Accept, revise or reject removal of universal Runtime Instance.
2. Accept, revise or reject the hybrid submit/correlation/inline-or-deferred
   terminal-outcome interaction model.
3. Decide whether separate outcome observation is a required capability only
   for non-terminal acceptance, as Candidate v1 proposes.
4. Approve Runtime Binding's minimum responsibility and decide unresolved
   Agent Instance:Binding multiplicity/fallback semantics.
5. Approve Managed/External as Binding ownership modes rather than separate
   Contracts/types.
6. Approve condition vocabulary: RuntimeAvailable minimum;
   InfrastructureAvailable and scoped DependencyReady conditional;
   ProtocolAvailable Provider detail; TaskReady excluded.
7. Approve TRUE/FALSE/UNKNOWN/NOT_APPLICABLE semantics and omission/freshness
   behavior.
8. Decide Descriptor/distribution trust, compatibility negotiation and
   publisher/verification policy.
9. Decide whether to authorize ED-S5-002-06 shared caller/conformance work before
   or after successful Hermes real-model evidence.
10. Define the safe human-reviewed route to close ED-S5-001 without broad
    credential debugging.
11. Decide ADR-0003/0004/0005 future disposition; no edit is authorized here.
12. Confirm that Candidate v1 remains non-frozen until all freeze-gate
    conditions pass.

## 30. Recommendation

**PASS_TO_HUMAN_ARCHITECTURE_REVIEW**

Human review should evaluate Candidate v1 and the decisions above. The Runtime
Contract must not freeze: G-S5-RUNTIME-FREEZE-01 condition 2 failed and
condition 3 is pending. No S5 development, ADR edit, Hermes retry, third-runtime
spike or Candidate v1 implementation should begin automatically.

**STOP. Do not close S5-SPIKE-002 formally. Do not freeze the Runtime Contract.**
