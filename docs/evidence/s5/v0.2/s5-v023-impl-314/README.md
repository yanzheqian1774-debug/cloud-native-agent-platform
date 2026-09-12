# S5-V023-IMPL-314 Evidence

## Checkpoint 1 — allocation and G1 plan

`S5-V023-IMPL-314` is the collision-free Human-authorized implementation carrier
for OpenClaw production Transport and explicit assembly, Batch A. The fixed source
is `f189212232fc194859a695f0307e83b0c7b73c0f`; the fixed tree is
`a8a9251d5d2e47605d18bb63e362164ec4c920d2`. They equal the read-only preparation
baseline and freshly fetched `origin/main` at allocation time.

The G1 plan and exact path/coordination table are recorded in
`docs/engineering/S5-V023-IMPL-314-OPENCLAW-PRODUCTION-TRANSPORT.md`.

No production implementation, deployment, model call, certification, release
acceptance, or complete OpenClaw execution capability is claimed by this
checkpoint.

## Recovery and Batch A continuation

The original worktree was recovered at
`/Users/tristan/.codex/worktrees/3198/cloud-native-agent-platform` on branch
`codex/s5-v023-impl-314-openclaw-production-transport`. Checkpoint 1 is commit
`8a058d293ab0db196402e3b6ece1c9d0c22a13f0`, tree
`3d7f75f929ad9a5ec84f8c0c804b83dece2d07fa`. The interrupted hook result is
`UNKNOWN`; it was not reconstructed as a pass.

The recovered production work implements exact manifest, npm lock, executable,
Node, client configuration, credential projection, authenticated Gateway health,
server version, configured agent and workspace preflight. The operator source
startup explicitly selects OpenClaw through Factory -> Adapter -> Provider ->
Transport only when configured and otherwise stays unconfigured without Native
fallback. Production execution remains explicitly unsupported.

Lifecycle mapping was re-audited before continuation. No accepted decision equates
Platform stop with OpenClaw session archive plus transcript deletion, and current
facts cannot prove ownership of an adopted session across restart. Production
`start`, `observe_runtime`, `stop` and `replace` therefore fail with
`RUNTIME_LIFECYCLE_UNSUPPORTED` without RPC effects. The exact mapping and Human
decision items are recorded in the G1 plan.

Checkpoint 2 is commit `7ef558f50254925f68c3be4fb28deab096b8e53f`. It
contains the bounded preflight, source-level explicit assembly, fail-closed
unsupported operations, focused tests, lifecycle audit and recovery evidence.
Draft PR #169 carries the branch for review; it is not Ready and grants no merge
or completion claim.

Focused fixture validation after recovery: `36 passed`. This covers existing
provider/adapter/factory behavior, exact target compatibility, production preflight,
sanitized failure classification, explicit lifecycle/execution unsupported behavior,
bootstrap selection and the real `kopf` startup function call path.

Repository validation: `make check` passed Ruff lint, Ruff formatting and pytest;
pytest reported `1597 passed, 134 skipped` with one existing Starlette/httpx
deprecation warning. Skips were environment-gated PostgreSQL, Qdrant, frontend
dependency and isolated-Linux checks, not converted into passes.

## Batch A continuation evidence

Git recovery matched the fixed continuation point exactly before writing: HEAD
`fe6689a108bb1517fffe21017612b72f86405057`, tree
`c787d3cc4fb00d882de5317e480ea399898b0d21`, clean index/worktree, no Git lock and no
other writer in the task worktree. The two interrupted read-only command groups had
ended and no missing result was represented as a pass.

Draft PR #169 automatic CI at that exact head completed on attempt 1:

- run `34697436806` (`CI`): `SUCCESS`; Quality Gates, Frontend Quality Gates and
  Agent Workbench Browser Acceptance all succeeded;
- run `34697436797` (`Employee Identity Chain`): `SUCCESS`; PostgreSQL Identity
  Chain, PostgreSQL Skill Invocation and PostgreSQL Business Problem and Plan Entry
  all succeeded.

No manual rerun was requested. CI does not replace authenticated RPC or image proof.

The original Gateway PID `71906` was confirmed as owned by this task using its exact
cwd, loopback listener and isolated state path. Its credential was not recoverable,
so it was stopped gracefully without deleting transcript or business state. A first
replacement exposed a safe configuration rejection for missing `gateway.mode`; the
task-local configuration was corrected to explicit `local` mode rather than using
`--allow-unconfigured`. The durable validation Gateway is PID `93744`, cwd
`/Users/tristan/.codex/worktrees/3198/cloud-native-agent-platform`, listening only on
`127.0.0.1:19314` and `[::1]:19314`, with state under
`/private/tmp/s5-v023-impl-314-probe.b0zeMp`.

Credential material is a new random task-local value stored only in a mode-0600
temporary file outside the repository and projected into the existing
`secret-ref:openclaw-gateway -> OPENCLAW_GATEWAY_TOKEN` environment slot. Its value
was never printed or passed as a command-line argument. With that reference, real
authenticated read-only RPC returned:

- `health`: authenticated response, `eventLoop.degraded=false`;
- `status`: `runtimeVersion=2026.7.1-2`;
- `agents.list`: exact agent `s5-v023-impl-314-runtime-1-g1` with workspace
  `/tmp/s5-v023-impl-314-probe.b0zeMp/workspaces/runtime-1/g1` (canonical equivalent
  of the configured `/private/tmp` path).

The production Transport -> Provider -> Adapter -> Factory bootstrap then passed
against that real Gateway and returned provider kind `openclaw`. No model, session,
agent or lifecycle write RPC was called.

The production operator image packaging now includes the exact Python import closure
`operator/core/gateway/runtime`, plus Node `22.23.1` and a production npm lock for
exact `openclaw@2026.7.1-2` with the accepted integrity. Only source directories are
copied into the final image. A clean image-equivalent formal entrypoint import passed,
focused packaging/bootstrap/operator/OpenClaw tests reported `20 passed`, and the
complete `make check` gate reported `1599 passed, 134 skipped` with the existing
Starlette/httpx deprecation warning.

One real Docker build was attempted. Docker daemon preflight responded, but both
Python and Node base-image metadata requests to the configured registry proxy timed
out. The build was cancelled after a bounded 90-second no-progress window and was
not retried or followed by a Docker restart. Consequently, a runnable image and
in-image configured preflight remain `NOT_PROVEN`; no build success is claimed.

The G1 plan now contains two concentrated `PROPOSED / NOT_ACCEPTED / NOT_IMPLEMENTED`
contracts: a recommended exclusive agent/workspace plus generation-scoped session
native realization, and a PostgreSQL-owner immutable revision plus mutable status
projection transported through Kubernetes. They do not implement lifecycle or
Profile projection semantics. `execute` and `observe_execution` remain unsupported.
No deployment, certification, Batch B dispatch/recovery/Evidence/Outcome, complete
OpenClaw lifecycle or release claim is made.

## Human G2 decision draft refinement

The reviewed implementation candidate remained
`cd99b0ea7b2ae749b56d7364310e024af62921a4`, tree
`9fb01d05982ee2a26e037f8af87008d2b9690eda`, before this documentation-only
refinement. Production source, tests, Gateway state, credentials and image packaging
were not changed.

The existing two `PROPOSED / NOT_ACCEPTED / NOT_IMPLEMENTED` sections were refined
into a Human-decidable G2 draft without allocating a new identifier. The refinement
records:

- explicit file, durable-memory, credential and context inheritance across Platform
  generations, while preserving Platform generation != OpenClaw session;
- fixed-version capability classification: live authenticated proof only for
  `health`, `status` and `agents.list`; agent/session/abort handlers are source-only
  evidence; all lifecycle and execution calls remain unavailable through the current
  production transport;
- durable ownership proof, partial-success, timeout, restart and ambiguous-effect
  handling without an external exactly-once claim;
- transcript as mutable controlled raw material, not formal Evidence, with any future
  normalized/redacted record remaining subordinate to the existing Evidence
  authority;
- operation-specific Profile eligibility for publication, supersession, existing
  bindings and explicit revocation; not-latest is not automatically ineligible;
- a recommended two-ConfigMap Kubernetes transport, explicit PostgreSQL authority,
  RBAC/admission/publisher/field-manager separation, outbox sequence, CAS and
  idempotent intermediate-state recovery without a cross-system transaction claim;
- disconnection behavior that rejects new effect-producing work while preserving
  already authorized observe/drain/cancel/stop needed for safe convergence; and
- scoped credential binding/resolution/revocation boundaries with no implicit
  authorization.

All values not fixed by current contracts are concentrated in the Human acceptance
list. The implementation path is conditional on a future Human G2 decision and new
bounded implementation allocations. No lifecycle/Profile/credential/Evidence code,
RPC, Docker access probe, image build, deployment, Batch B work or 309 operation was
performed. The production image remains `NOT_PROVEN`; only its future environmental
preconditions were documented.

## Human-accepted schema/conformance batch 1

Entry checkpoint matched commit
`bc5a3cb8315acb8560568d1029f2c827a82b9ed0`, tree
`a6ef15995648942943d8cc02a23cb63a6e7254bc`, with a clean index/worktree, no Git
lock and no competing worktree writer. The prior reviewed implementation and
authenticated evidence checkpoint remains
`cd99b0ea7b2ae749b56d7364310e024af62921a4`, tree
`9fb01d05982ee2a26e037f8af87008d2b9690eda`.

The Human accepted the exclusive Runtime Instance to agent/workspace direction,
separate Platform generation and OpenClaw session identities, same-workspace file
retention, no successor transcript copy, observe-first recovery, positive stop
evidence, PostgreSQL Profile authority and exact scope-first Secret Reference
direction. This acceptance authorized only schema/conformance and fixed-version RPC
capability validation; it did not retroactively change the earlier proposal record
or authorize production lifecycle/Profile/credential implementation.

The internal, non-frozen conformance artifact is
`manifests/acceptance/openclaw/openclaw-lifecycle-conformance-v1.json`, tested by
`tests/acceptance/openclaw/test_openclaw_lifecycle_conformance.py`. It reuses the
accepted execution contract and PostgreSQL owner, records missing OpenClaw mapping
fields, makes ambiguous effects observe-only/`RECOVERY_REQUIRED`, and asserts that
the production transport still contains no session lifecycle write allowlist.

### Real RPC evidence

The existing task-owned Gateway was revalidated as PID `93744`, cwd
`/Users/tristan/.codex/worktrees/3198/cloud-native-agent-platform`, loopback port
`19314`, state root `/private/tmp/s5-v023-impl-314-probe.b0zeMp`. The existing
mode-0600 credential reference was injected only through the environment. No secret
was printed, placed in arguments or committed.

The bounded test created only:

- agent `s5-v023-impl-314-conformance-a1`;
- workspace
  `/private/tmp/s5-v023-impl-314-probe.b0zeMp/workspaces/conformance-a1`;
- g1 session `ff9a00c9-3036-4ff8-b064-bab44976e9d7` at canonical key
  `agent:s5-v023-impl-314-conformance-a1:s5-v023-impl-314-runtime-c1-g1`;
- g2 session `b8eff756-7efe-431f-9982-6cfc393809d4` at canonical key
  `agent:s5-v023-impl-314-conformance-a1:s5-v023-impl-314-runtime-c1-g2`.

`agents.create` returned the exact normalized ID and canonical workspace;
`agents.update` identity data was saved and read through `agents.list`;
agent-scoped file/workspace listing returned the created bootstrap files;
`sessions.create` returned distinct g1/g2 IDs with `runStarted=false` and no parent,
fork, task, message or command hook; list/describe/resolve/get and patch were exercised
without model/tool work. Both transcripts contained only the provider header and
`sessions.get` returned zero messages.

Arbitrary `metadata` was rejected for both agent update and session patch. Supported
agent identity/workspace and session label/category fields are mutable by callers
holding the relevant Gateway admin/write scope, so they are correlation only and not
unforgeable ownership proof. `sessions.resolve` returned a full canonical key even
with a mismatched `agentId`, while `sessions.get` rejected that mismatch. Conformance
therefore prohibits resolve-only ownership or isolation decisions.

No abort, delete, archive, model, tool, arbitrary shell, dispatch, production
lifecycle, Profile projection, credential binding, PostgreSQL migration, Docker
probe/build, deploy, Batch B or 309 action occurred. The two empty sessions, agent
and workspace are retained because provider-native transcript headers and exact live
correlations now exist; cleanup was not forced.
