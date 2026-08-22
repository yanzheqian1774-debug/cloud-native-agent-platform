# Checkpoint B — failure, recovery, state, and instance evidence

> Experimental, spike-only, non-production. This evidence does not freeze a
> Runtime Contract or authorize production integration.

Environment: platform base `3cd910f150a13e366c45cd6f83878f395a74efe8`,
Checkpoint A evidence commit `8149daae81f46031a7196c57efaf48a0e2cc7268`,
branch `codex/s5-spike-001-checkpoint-a`, Hermes v0.20.4, image
`nousresearch/hermes-agent:v2026.8.18`, RepoDigest
`sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`.
The experimental provider baseline is the Checkpoint A commit above.

## E4 — gateway process failure

Experiment: kill the real supervised Hermes gateway PID while leaving its
container and Docker volume running.

Hypothesis: runtime-native supervision can restore the process without
Provider, substrate, or platform recovery action, while the outage remains
externally observable.

Procedure and trigger: provision a clean container, establish liveness and
detailed-health baseline, write a non-secret marker under `/opt/data`, then
send SIGKILL to gateway PID 123.

Timeline:

- Failure injection: `2026-08-21T13:34:28.938825Z`
- API/gateway unavailability observed: `13:34:29.908972Z`
- New gateway start recorded by Hermes: `13:34:33.201812Z`
- Hermes recorded prior unclean exit: `13:34:36.033122Z`
- API and detailed health restored with PID 244: `13:34:37.351956Z`
- Detection latency: 0.948 s
- Total recovery duration: 7.904 s

Observed: the container remained running with the same start timestamp and
zero Docker restarts. s6 restarted the gateway; neither the Provider nor
Docker/Kubernetes nor a Control Plane acted. Hermes' exit diagnostics recorded
the prior PID, new PID, prior heartbeat, and unclean exit. The marker survived.

Result: PASS. Detection owner is the external Provider/platform observer;
recovery owner is Hermes/s6; recovery mechanism is runtime-native process
supervision. State impact was not observed for the test artifact. Process
restart restored InfrastructureAvailable and RuntimeAvailable, but
DependencyReady and TaskReady remain unverified because ED-S5-001 is open.

Architecture learning: recovery action and recovery observation have different
owners. Native process recovery must not be described as Control Plane or
Kubernetes reconciliation.

## E5 — container/workload failure

### Case A — plain Docker container

Trigger: delete the whole Hermes container while preserving its named volume.

- Failure: `2026-08-21T13:35:13.454518Z`
- Container absence observed: `13:35:14.595350Z`
- No automatic recreation after three seconds
- Interaction unavailable while absent
- Explicit Provider recreation action: `13:35:18.328161Z`
- New container running: `13:35:19.746908Z`
- Interaction restored: `13:35:30.980110Z`
- Provider action to interaction restoration: 11.084 s
- Total failure to restoration: 18.460 s

Result: PASS. Docker without a desired-state controller did not recreate the
workload. The Provider action recreated it. Docker started the new container;
Hermes initialized its gateway; the preserved marker survived. Platform
semantic recovery was established only through API/liveness observation, not
by container creation alone.

### Case B — Kubernetes Deployment in kind

Substrate: existing `agentos-dev` kind cluster, isolated namespace
`s5-spike-001`, spike-only Deployment, Service, Secret, and `emptyDir`. The
verified local image was imported into and pinned to one worker. No CRD or
production Operator participated.

Trigger: delete ready Pod `hermes-checkpoint-b-646c6cbbcf-2xvdr`, UID
`1d09bd75-6b09-4ae6-b734-436b862d1137`.

- Failure: `2026-08-21T13:41:50.198223Z`
- Replacement observed: `13:41:50.942544Z`
- New Pod running: `13:41:51.803667Z`
- Old UID absent: `13:41:55.087921Z`
- New Pod ready/API healthy: `13:42:01.329898Z`
- New Pod: `hermes-checkpoint-b-646c6cbbcf-6xrcf`
- New UID: `10d39e05-869f-460f-8df8-c4553ad0d097`
- Total recovery duration: 11.968 s
- Container restarts in replacement Pod: 0

Result: PASS. Kubernetes Deployment/ReplicaSet recreated the Pod without
Provider or platform recovery action. Kubernetes readiness established the
cheap Hermes interaction surface, not model/task usability. The `emptyDir`
marker was lost. Kubernetes recovery is therefore necessary and useful for
workload semantics but insufficient for all candidate Runtime semantics.

## E6 — state persistence

Experiment: inventory metadata in a live isolated Hermes volume; recreate the
container with the same volume; then recreate with a fresh volume. No user
Hermes data was accessed. Credential values were never inspected.

| State category | Before | Same persistent volume | Fresh volume | Physical owner | Semantic owner candidate |
|---|---|---|---|---|---|
| `config.yaml` | present, 100128 B | present, 100128 B | regenerated, 100128 B | `/opt/data` volume/Hermes | Runtime configuration |
| `.env` credential file | absent | absent | absent | `/opt/data` if used | Provider/governance mechanism unresolved |
| API key binding | environment present | reinjected | reinjected | workload environment | Provider/infrastructure binding |
| `gateway_state.json` | present, 532 B | present, 532 B | regenerated, 532 B | `/opt/data`/Hermes | Runtime-local lifecycle metadata |
| Bundled skills | 483 files | 483 files | 483 regenerated files | image + `/opt/data` sync | Runtime capability material |
| Sessions | directory, 0 files | directory, 0 files | directory, 0 files | `/opt/data`/Hermes | Potential Agent/runtime state; untested |
| Memories | directory, 0 files | directory, 0 files | directory, 0 files | `/opt/data`/Hermes | Potential Agent/runtime state; untested |
| Logs | 10 files | 11 files | 9 new files | `/opt/data`/Hermes | Runtime operations state |
| Test marker | present, SHA-256 `0e65df…cb75` | same hash | absent | `/opt/data` volume | Experiment artifact |
| Kubernetes `emptyDir` marker | present before Pod deletion | not applicable | absent in replacement Pod | Pod-local storage | Ephemeral infrastructure state |

Result: PASS. Workload replacement with the persistent volume preserved
runtime-local material exactly where measured. Fresh storage regenerated
defaults but lost the marker and prior operational history. Runtime recovery
can occur with fresh state, but it is not identity/state recovery. Persistence
does not demonstrate cross-runtime schema compatibility or state portability.

Required recovery state depends on desired semantics: config and gateway
metadata support behavioral continuity; credentials must be rebound; sessions
and memories were unpopulated and remain unknown. The concurrent-writer warning
was respected; no two containers mounted the same volume concurrently.

## E7 — instance mapping

Evidence scale: SUPPORTED, PARTIAL, WEAK, UNKNOWN.

| Criterion | Model A: Instance=Container | Model B: Instance=Profile | Model C: Logical binding |
|---|---|---|---|
| Isolation | SUPPORTED by container/resource boundary | PARTIAL; upstream profile isolation, shared process/resources | PARTIAL; provider-defined |
| Provisioning | SUPPORTED and measured | PARTIAL from upstream facts; not provisioned live | SUPPORTED conceptually by provider boundary, not production-tested |
| Failure domain | SUPPORTED: Pod/container deletion affects one realization | PARTIAL: gateway/profile can restart within shared container | SUPPORTED: binding can outlive realization; direct evidence from recreated container |
| Recovery | SUPPORTED but substrate-dependent | PARTIAL via s6 profile services | SUPPORTED as separation of desired semantics from recovery owner |
| State ownership | WEAK if identity collapses into replaceable container | PARTIAL: profile scopes state but remains Hermes-specific | SUPPORTED as a place to reference state without equating it to runtime |
| Upgrade | PARTIAL; replace container/image | UNKNOWN live for profile upgrades | PARTIAL; binding can select realization, not tested |
| Observability | PARTIAL; container state misses gateway/API/model | PARTIAL; native profile status available | SUPPORTED as normalized projection need |
| Security | SUPPORTED for container boundary; credentials still external | WEAK/PARTIAL due shared container and process tree | PARTIAL; policy unspecified |
| Cost/resource efficiency | WEAK for one container per Agent | SUPPORTED upstream for shared multi-profile container | PARTIAL; provider can choose realization |
| Scaling | PARTIAL; replicas conflict with shared state semantics | WEAK/UNKNOWN; ports and shared resource limits constrain | PARTIAL; can express non-1:1 realization, untested |
| Multi-tenancy readiness | PARTIAL with strong container isolation | WEAK without stronger shared-host controls | UNKNOWN; governance not defined |
| Runtime portability | WEAK; container is implementation-specific | WEAK; profile is Hermes-specific | SUPPORTED as an abstraction goal, not proven |
| Complexity | SUPPORTED/simple but overly coupled | PARTIAL/runtime-specific | PARTIAL/more indirection |

Assessment:

- Model A is PARTIAL: useful deployment/failure isolation, but a replaceable
  container is not a durable logical Agent identity and misses profiles and
  external runtimes.
- Model B is PARTIAL: profiles are meaningful Hermes identities and efficient,
  but mapping them into platform Core would couple the platform to Hermes and
  share container failure/security domains.
- Model C is the strongest candidate, still PARTIAL: evidence supports
  separating logical identity/binding from replaceable runtime realization.
  It accommodates Models A and B as Provider choices, but remains a hypothesis.

Recommended candidate: HYBRID centered on Model C. Agent Instance should not be
assumed equal to Runtime Instance. A logical Runtime Binding may reference a
provider-managed realization that is a container, profile, gateway, or remote
endpoint. This is not accepted architecture.

## Failure-domain matrix

| Failure domain | Signal | Detected by | Recovered by | Mechanism | Platform action? | State impact | Final semantic verification |
|---|---|---|---|---|---|---|---|
| Gateway SIGKILL | API unavailable, PID change, unclean-exit record | Provider/external probe and Hermes | Hermes/s6 | supervised child restart | No recovery action; observation needed | marker preserved | API/detailed health only; model/task unknown |
| API surface invalid config | gateway running, API unavailable | Provider probe | UNKNOWN | no recovery observed | configuration correction likely required | none measured | API reachability plus invocation |
| Plain container deletion | Docker object absent, connection refused | Provider/substrate observer | Provider in experiment | explicit recreate | Provider action required | volume preserved | API/liveness; dependency/task unknown |
| Kubernetes Pod deletion | Pod UID changes, readiness false→true | Kubernetes and observer | Deployment/ReplicaSet | new Pod | No concrete platform action | `emptyDir` lost | Pod Ready + Hermes health; dependency/task unknown |
| Persistent state missing | regenerated defaults, marker/history absent | Provider inventory | Provider/Hermes defaults | attach fresh storage/bootstrap | Platform decision depends on desired identity continuity | prior state lost | compare required state plus runtime/task checks |
| Model provider missing | HTTP 200 failure content, zero tokens | Provider invocation classifier | Human/config owner; not tested | configure credential/provider | Yes if dependency semantic required | no state change measured | successful real-model invocation |

## Restarted versus recovered

Restarted: the required infrastructure object or runtime process exists again.

Recovered: the platform's required normalized runtime semantics are satisfied
again and verified. At minimum for this spike that includes
InfrastructureAvailable and RuntimeAvailable. DependencyReady and TaskReady
must be required when the desired workload semantics promise executable Agent
tasks; ED-S5-001 prevents proving them here.

E4 and E5 prove that restart is observable earlier than full semantic recovery.
Kubernetes Pod Ready and Hermes detailed health are insufficient evidence of
model/task recovery.

## Managed Runtime candidate

Candidate: a Managed Runtime is a runtime whose desired lifecycle and
operational semantics can be expressed by the platform, translated by a
Provider into substrate/runtime configuration, observed as normalized
conditions, and restored by the appropriate owner until those semantics are
verified again.

Assessment: SUPPORTED, with an important qualification: “managed” does not mean
the Control Plane performs every recovery action. It owns desired semantic
outcomes; Hermes/s6, Kubernetes, or a Provider may own concrete recovery.
The exact promised condition set is not frozen.

## Preliminary capability implications

| Capability | Evidence level | Basis |
|---|---|---|
| Managed Provision | SUPPORTED | three Docker provisions and isolated Deployment |
| Health Observation | LIMITED | process/API visible; model/task false positives |
| Native Process Recovery | SUPPORTED | measured s6 recovery |
| Workload Recovery | SUPPORTED with desired-state substrate; LIMITED in plain Docker | Deployment vs plain-container comparison |
| Persistent State | SUPPORTED | named volume survival measured |
| Recreate | SUPPORTED | same/fresh storage measured |
| Multiple Instances | LIMITED | upstream profiles; no live multi-profile test |
| Horizontal Scale | UNKNOWN | concurrent shared-state constraint; no scale test |
| External Mode | UNKNOWN | not exercised |

This is preliminary Checkpoint B evidence, not the final E8 matrix.
