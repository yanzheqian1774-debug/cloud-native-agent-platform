# S5-SPIKE-002 — CHECKPOINT B RESULT

## 1. Overall

**PASS**

A generic experimental caller interacted with a real OpenClaw Gateway through
an isolated experimental Provider. The caller submitted generic input, received
an opaque correlation, observed a terminal event, and received a normalized
failure outcome. It contained no OpenClaw Gateway, WebSocket, Agent, Session,
Run, Workspace, model, or RPC vocabulary.

The real native path was:

```text
ExecutionRequest
  -> experimental OpenClaw Provider
  -> Gateway agent RPC
  <- accepted + runId + acceptedAt
  -> Gateway agent.wait RPC(runId)
  <- terminal error + endedAt
  -> normalized ExecutionOutcome(FAILED)
```

No external model credential was configured. OpenClaw accepted both real Runs,
then terminated them with the expected missing-provider-auth failure. This is a
successful interaction-boundary experiment, not a model completion test.

Finding: **SUBMIT_OBSERVE_OUTCOME** is the minimum faithful model. A synchronous
`invoke -> result` may be a convenience projection, but cannot be the only
Candidate interaction shape.

No production source, ADR, CRD, Operator, Runtime, API, Console, Model Plane,
State Plane, or Capability Registry artifact was changed.

## 2. Repository Isolation

| Field | Result |
|---|---|
| Branch | `codex/s5-spike-002-openclaw` |
| Base | `d5c6d998ec3c506323157d8850248a331c4d18d2` (`codex/s5-spike-001-checkpoint-a` HEAD when isolation began) |
| Worktree | `/Users/tristan/Projects/cloud-native-agent-platform` converted into the dedicated task worktree by non-destructive `git switch -c` |
| Checkpoint A Preserved | **YES** — `checkpoint-a-result.md` carried unchanged into the new branch |
| S5-SPIKE-001 Preserved | **YES** — all Hermes commits/files at the base remain unchanged; no history rewrite or squash |
| Production Source Changed | **NO; 0 files** |
| Git Status | branch `codex/s5-spike-002-openclaw`; one intended untracked experiment directory; no tracked-file diff |

The new branch was created before Checkpoint B experimentation. `main` remains
at `3cd910f150a13e366c45cd6f83878f395a74efe8`; it was not modified.

## 3. OpenClaw Runtime Identity

| Field | Observed value |
|---|---|
| Runtime | OpenClaw |
| Executed version | `2026.7.1-2` |
| Executed build identity | `0790d9f` reported by `dist/index.js --version` |
| Distribution | Official npm package `openclaw@2026.7.1-2` |
| Registry integrity | `sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g==` |
| Runtime entry | `node .../node_modules/openclaw/dist/index.js` |
| Node | `v22.23.1` |
| Host | macOS, loopback-only Gateway on `127.0.0.1:18799` |
| State | isolated `/private/tmp/s5-spike-002-openclaw-state` |
| Workspace | isolated `/private/tmp/s5-spike-002-openclaw-workspace` |
| Model credential | none |

### Distribution metadata anomaly

The official registry reported stable `2026.7.1-2`. The Checkpoint A source
snapshot version `2026.8.1` was not published at that npm version. The installed
`2026.7.1-2` artifact contained the built runtime and executed successfully via
`dist/index.js`, but omitted the normal package manifest/CLI wrapper needed for
`node_modules/.bin/openclaw`. Its advertised matching Git tag could not be
resolved during the experiment, and attempts to retrieve/build the later pinned
source snapshot were incomplete/truncated. No artifact was patched.

This strengthens F13: a Descriptor needs independently verifiable package
integrity, native build identity, source identity, entrypoint and compatibility;
a human-readable version string alone is insufficient.

## 4. Experimental Boundary

### Generic Types

- `ExecutionRequest(input_text)`
- `ExecutionHandle(correlation_id)`
- `ExecutionEvent(kind, correlation_id, observed_at_ms, detail)`
- `ExecutionOutcome(kind, correlation_id, message, observed_at_ms)`
- `Observation(name, TRUE|FALSE|UNKNOWN|NOT_APPLICABLE, reason)`
- `ExperimentalProvider` protocol with `observe`, `submit`, and `await_outcome`

These are spike-only names, not formal Contract vocabulary.

### Provider

`openclaw_provider.py` owns:

- Gateway URL and authenticated native CLI/RPC invocation;
- OpenClaw Agent ID and Session key inside `OpenClawBinding`;
- native `agent` and `agent.wait` parameter/result shapes;
- idempotency-key/run correlation translation;
- health translation;
- native status/error normalization;
- secret lookup by environment-variable reference.

The Provider shells out to the documented OpenClaw CLI/Gateway integration
surface because this runtime version publishes no supported external client
library. It does not import OpenClaw internals into the generic boundary.

### Generic Caller Contaminated

**NO.** `generic_caller.py` imports only generic experimental types. A spike-local
test scans the file for `openclaw`, `gateway`, `websocket`, `agentId`,
`sessionKey`, and `runId`; all are absent.

## 5. Real Interaction Path

Two real native executions were observed.

### Direct native evidence run

1. Native `health` RPC returned `ok: true`, default Agent `main`, zero initial
   Sessions, and a real per-agent Session store path.
2. `agent` RPC submitted message input for Agent `main` and Session
   `agent:main:checkpoint-b-native`.
3. Immediate response:

   ```json
   {
     "runId": "s5-spike-002-b-real-001",
     "sessionKey": "agent:main:checkpoint-b-native",
     "status": "accepted",
     "acceptedAt": 1787331606278
   }
   ```

4. Gateway log recorded separate per-Session and global queue enqueue/dequeue.
5. Native OpenAI provider resolution failed because no API key existed.
6. Separate `agent.wait` returned:

   ```json
   {
     "runId": "s5-spike-002-b-real-001",
     "status": "error",
     "endedAt": 1787331607025,
     "error": "FailoverError: No API key found ..."
   }
   ```

### Generic caller through Provider

The Provider health/submit/wait path produced:

```json
{
  "outcome": {
    "kind": "failed",
    "correlationId": "s5-openclaw-cfb30bd6-b4c4-4906-aa73-a472ea9cb495",
    "message": "runtime dependency unavailable: model credential not configured",
    "observedAtMs": 1787331777945
  }
}
```

The generic caller never received Agent ID, Session key, Gateway URL, RPC method,
native model provider, auth-store path, or native error text.

## 6. Submission & Acceptance

Submission and execution completion are distinct.

- Required native submission fields included `message` and `idempotencyKey`.
- Provider additionally supplied native opaque binding data (`agentId`,
  `sessionKey`).
- `agent` acknowledged in 135 ms for the direct run and 15 ms for the Provider
  run according to Gateway logs.
- The acknowledgement was `status: accepted`, before model/provider resolution
  completed.
- The Gateway subsequently queued the Run in both a Session lane and a global
  lane.
- Failure arrived later as a native execution error.

Transport success and immediate acceptance therefore do not imply dependency
readiness or semantic success.

## 7. Correlation / Run Identity

OpenClaw used the required native `idempotencyKey` as `runId`. That identifier:

- appeared in immediate acceptance;
- appeared in Gateway logs;
- keyed the independent `agent.wait` observation;
- appeared in the terminal snapshot;
- was projected as opaque `ExecutionHandle.correlation_id`.

The generic boundary does not promise that every runtime uses an idempotency key
or exposes a native Run object. It requires only a Provider-supplied opaque
correlation when asynchronous observation is declared.

## 8. Events / Streaming

Observed event order at the Gateway/protocol level:

1. WebSocket open;
2. authenticated `connect`;
3. `hello-ok` advertising 218 methods and 30 events;
4. health event;
5. `agent` response with accepted Run;
6. client connection close (CLI one-shot behavior);
7. Session/global queue activity;
8. terminal agent error recorded by the Gateway;
9. new WebSocket connection;
10. `agent.wait` terminal snapshot;
11. close.

The experimental Provider normalized acceptance and terminal response as
`ExecutionEvent(ACCEPTED)` then `ExecutionEvent(TERMINAL)`.

Native Gateway event capability was observed during handshakes and health
events, and official runtime docs/source expose agent lifecycle streaming. The
one-shot CLI transport did not keep one connection subscribed across the Run,
so assistant/tool delta streaming and native agent-event ordering were **not
observed live**. Streaming remains optional/declared; this experiment must not
invent intermediate events.

## 9. Terminal Outcome

Both real executions terminated with native `status: error`, not timeout or
transport rejection. Cause: OpenClaw's selected `openai/gpt-5.5` dependency had
no configured API key. The Gateway remained healthy and protocol-usable.

This is semantic execution failure after acceptance. It is not a Gateway
availability failure.

Cancellation was not exercised because missing auth caused terminal failure in
under one second. Native `sessions.abort` accepts a Session key and optional
`runId`, but its race/idempotency semantics remain unverified. Credential
debugging was intentionally stopped.

## 10. Normalized Experimental Outcome

Native:

```text
status=error
FailoverError / missing-provider-auth
native auth-store path and remediation
```

Normalized:

```text
kind=FAILED
correlation=<opaque>
message="runtime dependency unavailable: model credential not configured"
observedAt=<endedAt>
```

The normalized outcome preserved semantic category while removing OpenClaw
provider name, filesystem layout and remediation text.

## 11. Interaction Model Finding

**SUBMIT_OBSERVE_OUTCOME**

Evidence:

- `agent` returned acceptance and correlation before execution;
- execution ran on queued Session/global lanes;
- terminal outcome was obtained later with `agent.wait(runId)`;
- Gateway advertises event streaming separately;
- a synchronous CLI can wait, but that is a projection over asynchronous
  semantics;
- reconnect/observation was demonstrated by using separate WebSocket
  connections for submit and wait.

Candidate v0 should allow:

```text
Submit -> Handle -> Observe (events and/or wait/poll) -> Outcome
```

It may also permit a convenience `invoke-and-wait`, but must not define the
runtime interaction contract solely as `invoke(request) -> result`.

## 12. Runtime Binding & Cardinality

Observed concrete topology at one instant:

```text
1 experimental Platform Agent Instance intent
  -> 1 Runtime Binding candidate (Provider-owned OpenClaw binding data)
  -> 1 selected OpenClaw Agent "main"
  -> 2 selected Sessions across direct/Provider evidence
  -> 1 Run per submission, multiple Runs over Agent/Gateway lifetime
  -> 1 shared Gateway
  -> 1 foreground Node process
  -> no container/Pod in this realization
```

| Relationship | Classification | Evidence |
|---|---|---|
| Experimental Agent Instance : Runtime Binding | 1:1 in this harness; **CONDITIONAL** generally | Harness selected one logical binding; Candidate does not require universal 1:1 |
| Runtime Binding : OpenClaw Agent | 1:1 in this harness; **CONDITIONAL** generally | Binding selected `main`; shared/rotating Agents remain possible Provider policy |
| OpenClaw Agent : Session | **1:N** | Direct and Provider runs used two distinct Session keys under `main`; health/session state recorded both |
| Session : Run | **1:N over time**, 1 active at a time for observed lane | Gateway queued per Session; persisted Session outlived terminal Run |
| Gateway : OpenClaw Agent | **1:N supported**, 1:1 observed configured roster | Native health returned default Agent array; upstream supports multiple Agents |
| Gateway : Session | **1:N** | Multiple Sessions under the one real Gateway |
| Gateway : Run | **1:N over time** | Two real accepted Runs used the same Gateway process |
| Gateway : Process | **1:1 at an instant; CONDITIONAL over recovery** | Foreground Gateway ran in one Node process, then a replacement process reused state/port |
| Gateway : container/Pod | **NOT_APPLICABLE** in this realization | Direct host process, no Docker/Pod |
| Agent : process | **N:1 supported; 1:1 observed roster/process** | Agent is logical config/state inside Gateway, not a process |

### Does Runtime Binding remain useful?

**YES.** It isolated native endpoint, Agent and Session selection from the
generic caller and prevented Agent Instance from collapsing into Gateway,
process, Session, or Run. Binding needs opaque Provider data, ownership mode and
cardinality metadata; it must not mandate a universal native instance identity.

## 13. Observation Model

### While Gateway running

| Condition | Value | Evidence |
|---|---|---|
| InfrastructureAvailable | **UNKNOWN** | Gateway RPC could not prove host/process-supervisor infrastructure |
| RuntimeAvailable | **TRUE** | native health RPC `ok: true` |
| ProtocolAvailable | **TRUE** | authenticated WS connect, `hello-ok`, health RPC |
| DependencyReady | **UNKNOWN** before Run | health response included no proof of selected model credential; later execution proved it unavailable |
| Execution state/outcome | **FAILED** | accepted Run later returned terminal missing-auth error |

After terminal failure, scoped model dependency readiness for that selected path
could be normalized **FALSE**, but a global `DependencyReady` remains ambiguous
unless it names the dependency/scope.

### While Gateway stopped

| Condition | Value | Evidence |
|---|---|---|
| InfrastructureAvailable | **UNKNOWN** | host remained present but Provider had no authoritative substrate probe |
| RuntimeAvailable | **FALSE** | Gateway RPC connection failed |
| ProtocolAvailable | **FALSE** | handshake/RPC impossible |
| DependencyReady | **UNKNOWN** | cannot infer dependency state from protocol loss |
| Execution | **NOT_APPLICABLE** | no Run submitted during outage |

### Candidate impact

No new universal Runtime condition is required by this evidence. Separate
RuntimeAvailable and ProtocolAvailable are useful experimental observations,
but exact condition vocabulary remains a human Candidate decision. Native
plugin/channel/model details should remain Provider-specific evidence.

## 14. Managed vs External

| Shared semantic | Managed Gateway | External Gateway |
|---|---|---|
| Descriptor | OpenClaw/protocol/Provider compatibility | same |
| Binding | endpoint + native Agent/Session selection | same |
| Interaction | `agent`, correlation, events/wait, outcome | same |
| Observation | Gateway/protocol/dependency/execution projection | same, with less infrastructure evidence |
| Capability declaration | async, wait, stream, cancel, state, lifecycle flags | same vocabulary; different values/owners |
| Ownership | Provider/substrate may own workload | external owner retains workload/shared resources |

| Differing semantic | Managed | External |
|---|---|---|
| Provision | Provider/substrate capability may create Gateway | unsupported/not owned |
| InfrastructureAvailable | Kubernetes/service-manager evidence may exist | normally UNKNOWN |
| Restart | Provider may request substrate/service action | external owner only |
| Recovery | Provider can observe; substrate/native runtime acts | Provider observes only unless explicitly delegated |
| Cleanup | only Provider-owned workload/state | disconnect/unbind; never delete shared Gateway/resources |
| Upgrade | Provider may converge pinned package/image | external owner; Provider only reports compatibility |

One experimental Provider semantic boundary can represent both modes. Concrete
lifecycle methods must be capability/ownership-sensitive, not mandatory no-ops.

## 15. Recovery Ownership

One bounded failure/recovery observation was performed.

| Field | Evidence |
|---|---|
| Failure | operator sent SIGINT to foreground Gateway |
| Failure detected by | experimental Provider health RPC failure |
| Recovery action performed by | experiment operator restarted the Gateway process with the same command/state |
| Recovery observed by | Provider health RPC transitioned RuntimeAvailable/ProtocolAvailable FALSE -> TRUE |
| State continuity | same state directory/workspace were reused; Session files remained present |
| Semantic recovery verified by | **not verified**; no failed Run was retried/resumed and model dependency remained unavailable |

Restart **did not equal** semantic recovery. The experiment proved endpoint/
protocol recovery and state presence only. It did not prove replay, resume,
exactly-once execution, successful dependency restoration, or business outcome.

## 16. State Evidence

Only names/metadata were inventoried; credential values and transcript content
were not inspected.

| Item | Class | Owner | Persistence | Required for recovery | Portable evidence | Platform ownership evidence |
|---|---|---|---|---|---|---|
| `openclaw.json` + last-good | Runtime Internal/config | OpenClaw/operator | file; survived restart | yes for same configuration | none | none |
| `state/openclaw.sqlite` + WAL/SHM | Runtime Internal/shared | OpenClaw | durable files; survived restart | likely for shared runtime continuity | none | none |
| `identity/device.json` | Runtime Internal/credential-adjacent | OpenClaw | file | likely for Gateway identity | none | none |
| `agents/main/sessions/sessions.json` | Agent/Session | OpenClaw | file; created/updated by Runs | yes for native Session continuity | none | none |
| two trajectory JSONL/path pairs | Execution/Run + Session | OpenClaw | files; survived restart | not proven required | none | none |
| skill prompt cache | Runtime Internal/Capability cache | OpenClaw | files | regenerable/unknown | none | none |
| config audit and stability bundles | Runtime Internal/operations | OpenClaw | files | not required for functional restart; useful diagnostics | none | none |
| workspace bootstrap files | Workspace/Agent | OpenClaw/operator | separate Git-initialized directory | used for Agent context | potential semantic content only; untested | none |
| disposable Gateway token | Credential | experiment operator | environment only; not written to repository | required for protocol auth | not portable state | none |
| model credential | Credential | absent | absent | required for selected model success | not applicable | none |

Physical durability did not prove portable or Platform-owned state. No State
Contract is proposed.

## 17. Capability Observation

Architecturally possible without Core changes: **YES, with Provider translation**.

Real startup loaded nine native plugins and registered commands; the state tree
also contained skill-workshop and skill prompt-cache data. OpenClaw separates
Tools, Skills and executable Plugins. The Provider could translate an opaque
Platform Capability Binding into native skill visibility, tool policy,
plugin/MCP configuration and credential references.

No capability was installed or bound in this checkpoint. Readiness and policy
must be observed separately; Core should not understand native plugin names,
tool schemas, skill paths or prompt caches.

## 18. Model Binding Observation

Architecturally possible without Core changes: **YES, with reduced governance
visibility unless the Provider reports it**.

OpenClaw selected `openai/gpt-5.5`, loaded its native provider plugin, resolved a
per-Agent auth store, and failed with a native missing-auth classification.
The Provider normalized that dependency failure without exposing model config or
filesystem details to the generic caller.

A Platform Model Binding could remain opaque to Core and translate inside the
Provider into OpenClaw model/profile configuration plus credential references.
Runtime-native routing/fallback remains OpenClaw execution behavior; enterprise
governance remains Platform policy/observation. No Model Plane was implemented.

## 19. Falsification Matrix

| ID | Target | Result | Live evidence | Candidate impact |
|---|---|---|---|---|
| F01 | Provider Isolation | **STRENGTHENED** | generic caller completed real path with zero native vocabulary | Keep all native RPC/binding/error translation Provider-side |
| F02 | Runtime Binding | **STRENGTHENED** | binding selected shared endpoint + Agent + Session independently of generic request | Binding is useful; needs opaque data/ownership/cardinality |
| F03 | Agent Instance / realization separation | **STRENGTHENED** | one intent mapped through logical Agent/Session to shared Gateway/process | Never equate Agent Instance with realization object |
| F04 | Runtime Instance/cardinality | **CHALLENGED** | one Gateway/process hosted multiple Sessions/Runs; Agent was not a process | No universal Runtime Instance identity/cardinality |
| F05 | Interaction Contract | **STRENGTHENED** | accepted handle then independent wait returned terminal error | Submit/observe/outcome required; sync-only contradicted |
| F06 | Streaming optionality | **SURVIVES** | Gateway advertised events; one-shot Provider used wait and terminal projection | Stream remains optional capability; no fake events |
| F07 | Cancel optionality | **INCONCLUSIVE** | native abort method exists but Run failed too quickly to test | Keep optional; exact semantics require later evidence |
| F08 | RuntimeAvailable normalization | **STRENGTHENED** | health TRUE while execution failed; FALSE during stop; TRUE after restart | Runtime, protocol, dependency, execution must stay separate |
| F09 | DependencyReady separation | **STRENGTHENED** | health succeeded before missing-model-auth terminal failure | Dependency readiness is scoped and independently observed |
| F10 | Managed Runtime definition | **STRENGTHENED** | operator owned process restart; Provider observed convergence only | Managed does not mean Core performs every action |
| F11 | External Runtime shared contract | **SURVIVES** | same URL/auth/interaction/observation works without workload ownership | shared semantics plausible; infrastructure/lifecycle ownership differs |
| F12 | State boundary | **CHALLENGED** | config, shared DB, Session/trajectory, Workspace and credential state were distinct/mixed | declare requirements/references; do not infer portability/ownership |
| F13 | Descriptor/package metadata | **STRENGTHENED** | npm version, integrity, runtime hash, missing wrapper/manifest and unresolved tag differed | immutable artifact + entrypoint + source/build/protocol compatibility required |
| F14 | Capability Declaration | **SURVIVES** | native plugins/skills/tool mechanisms existed independently of interaction/lifecycle | declare capabilities; Provider translates; avoid native vocabulary in Core |
| F15 | Core source change = 0 | **STRENGTHENED** | real Provider prototype added only under experiment path | second runtime completed boundary test with zero Core changes |

## 20. AP-S5-002

**SUPPORTED** — Runtime Choice, Not Runtime Collection.

The integration choice includes a shared stateful Gateway, Agent/Session binding,
async interaction, Provider-specific distribution, ownership and capability
semantics. It is not a collection of runtime images behind one synchronous
method.

## 21. AP-S5-003

**SUPPORTED** — Enterprise Capability Ownership.

OpenClaw-native Plugins, Tools and Skills remain projection mechanisms. A
Platform Capability Binding can stay platform-owned while a Provider translates
it. No Core change or understanding of OpenClaw internals was necessary.

## 22. AP-S5-004

**SUPPORTED** — Runtime / Model Responsibility Separation.

The Gateway was RuntimeAvailable and ProtocolAvailable while model dependency
resolution failed. OpenClaw owned native provider selection/execution; the
Platform-side boundary normalized the outcome. Runtime and Model readiness are
demonstrably different.

## 23. Candidate v0 Contradictions

No explicit decomposed Candidate v0 statement was contradicted.

The following possible stronger interpretations are contradicted by live
evidence:

1. mandatory synchronous `invoke -> result`;
2. acceptance implies semantic success;
3. RuntimeAvailable implies DependencyReady;
4. Agent Instance equals Agent, Session, Run, Gateway, process, or container;
5. one Runtime Binding must provision one process/container;
6. restart proves semantic recovery;
7. durable native state proves portability/Platform ownership;
8. version string alone is sufficient distribution identity.

## 24. Candidate v0 Required Modifications

Evidence-only recommendations; none implemented:

1. Make submit/correlation/observation/outcome the normative asynchronous shape
   when interaction is declared; define sync invocation only as convenience.
2. Require opaque correlation for accepted asynchronous work and clarify
   idempotency ownership without assuming native `runId` vocabulary.
3. Allow reconnectable terminal observation separately from event streaming.
4. Keep Runtime Binding cardinality/provider realization identity open and
   ownership-aware.
5. Scope dependency observations; a single unqualified boolean can mislead.
6. Include immutable distribution integrity, executable entrypoint, native build
   identity and compatibility metadata, not only runtime version/image.
7. Preserve tri-state/not-applicable observations and separate action from
   semantic recovery verification.

These are Candidate inputs requiring human review, not Contract changes.

## 25. Unknowns for Checkpoint C

1. Successful real-model completion and result payload semantics.
2. Live assistant/tool delta event ordering on a persistent WS client.
3. Cancel before queue, while queued, during model execution and during tools;
   race/idempotency/terminal snapshot semantics.
4. Active Run behavior across connection loss and Gateway process replacement.
5. Exactly-once/dedupe retention across restart.
6. Multi-Agent live isolation in one Gateway (only one Agent configured here).
7. External remote Gateway with infrastructure explicitly unobservable.
8. Managed container/Kubernetes realization and PVC replacement behavior.
9. Safe Agent/Session cleanup ownership on a shared external Gateway.
10. Concrete bounded Capability Binding translation.
11. Concrete Model Binding/profile translation using reference-only secrets.
12. Portable subset/fidelity of Workspace or Session state.
13. Stable mapping among npm version, source tag/commit and runtime build hash.
14. Whether `ProtocolAvailable` should be universal Candidate vocabulary or
    Provider-specific detail.

## 26. Acceptance Criteria

| AC | Result | Evidence |
|---|---|---|
| AC-B01 | **PASS** | dedicated branch/worktree established before prototype |
| AC-B02 | **PASS** | Hermes evidence/commits preserved unchanged |
| AC-B03 | **PASS** | Checkpoint A preserved unchanged |
| AC-B04 | **PASS** | Production/Core change = 0 |
| AC-B05 | **PASS** | real OpenClaw `2026.7.1-2 (0790d9f)` Gateway executed |
| AC-B06 | **PASS** | generic caller contamination test passes |
| AC-B07 | **PASS** | Provider owns native translation |
| AC-B08 | **PASS** | two real native accepted/terminal interactions |
| AC-B09 | **PASS** | `accepted` and `acceptedAt` captured |
| AC-B10 | **PASS** | two real `runId` correlations captured |
| AC-B11 | **PASS** | terminal missing-auth failures captured |
| AC-B12 | **PASS** | normalized generic `FAILED` outcome captured |
| AC-B13 | **PASS** | `SUBMIT_OBSERVE_OUTCOME` classification |
| AC-B14 | **PASS** | cardinality table and Binding conclusion completed |
| AC-B15 | **PASS** | layered observation evaluated running/stopped/restarted |
| AC-B16 | **PASS** | managed/external shared/different semantics evaluated |
| AC-B17 | **PASS** | one bounded stop/restart observation; semantic recovery unverified |
| AC-B18 | **PASS** | state inventoried/classified; no portability claim |
| AC-B19 | **PASS** | AP-S5-002 supported |
| AC-B20 | **PASS** | AP-S5-003 supported |
| AC-B21 | **PASS** | AP-S5-004 supported |
| AC-B22 | **PASS** | F01-F15 re-evaluated |
| AC-B23 | **PASS** | no real secret used/exposed/committed; disposable literal only |
| AC-B24 | **PASS** | validation and cleanup checks completed; no process/temp artifacts remain |
| AC-B25 | **PASS** | Checkpoint C not started |

## 27. Validation

| Check | Result |
|---|---|
| Spike-local pytest | **PASS** — 4 passed |
| Ruff | **PASS** — `All checks passed!` |
| Ruff format check | **PASS** — 5 files already formatted |
| Repository tests | **SKIPPED** — experiment imports no repository production package and changes no production source |
| `make check` | **SKIPPED** — same reason; spike-local targeted validation is applicable |
| `git diff --check` | **PASS** — each untracked artifact checked with `--no-index`; no output |
| Secret scan | **PASS** — no API-key/private-key patterns found |
| Generic contamination scan | **PASS** in spike-local test |
| Production source diff | **PASS** — `git diff --name-only` empty; only intended untracked experiment path |

Initial validation used `UV_CACHE_DIR=/private/tmp/s5-spike-002-uv-cache`
because the sandbox correctly denied uv's default home cache. The first test run
found a contamination-test docstring false positive and lint issues; those were
fixed, then the full targeted validation was rerun.

## 28. Cleanup

Final cleanup verified:

- Gateway foreground process stopped;
- port `18799` no longer reachable/listening;
- temporary runtime package removed;
- temporary state and Workspace removed;
- incomplete source/archive attempts removed;
- temporary uv cache removed;
- no user OpenClaw state or credentials created/modified;
- repository contains only the intended experiment path changes.

All named temporary targets were removed after the inventory was recorded. Port
`18799` had no listener. Generated `__pycache__` directories were also removed.
The disposable test token and all runtime/Session/Workspace state are therefore
unrecoverable from the cleaned temporary paths; only sanitized evidence remains
in the repository.

## 29. Recommendation

**PASS_TO_CHECKPOINT_C**

Checkpoint C should synthesize the cross-runtime evidence and request human
decisions where Candidate vocabulary changes are proposed. It should not assume
successful model completion, cancellation, streaming, state portability,
multi-Agent isolation or package/source traceability are proven by Checkpoint B.

**STOP. Do not begin Checkpoint C automatically. Do not edit ADRs or freeze the
Runtime Contract.**
