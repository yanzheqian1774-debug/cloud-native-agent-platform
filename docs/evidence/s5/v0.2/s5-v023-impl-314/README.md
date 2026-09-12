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

Focused fixture validation after recovery: `36 passed`. This covers existing
provider/adapter/factory behavior, exact target compatibility, production preflight,
sanitized failure classification, explicit lifecycle/execution unsupported behavior,
bootstrap selection and the real `kopf` startup function call path.

Repository validation: `make check` passed Ruff lint, Ruff formatting and pytest;
pytest reported `1597 passed, 134 skipped` with one existing Starlette/httpx
deprecation warning. Skips were environment-gated PostgreSQL, Qdrant, frontend
dependency and isolated-Linux checks, not converted into passes.

Live bounded facts recovered without exposing credentials or raw logs:

- exact CLI: `OpenClaw 2026.7.1-2 (0790d9f)`;
- host Node: `v22.23.1`, satisfying the pinned package engine range;
- one task-owned Gateway PID `71906` listens on loopback port `19314` from the task
  worktree and isolated temporary state directory;
- `/healthz` returned HTTP `200`;
- authenticated Gateway RPC is `UNKNOWN`: the prior token was not present in the
  recoverable caller or process environment, and a bounded client call failed before
  authentication because the configured Secret reference was unavailable;
- no model task and no lifecycle write RPC was executed.

The shipped operator image currently copies only `operator/` and exposes only
`operator/src`; an image-equivalent import fails on the pre-existing `agent_core`
dependency, and configured OpenClaw startup would additionally lack `agent_runtime`.
The repository also has no authoritative operator-facing Runtime Profile projection
path. Those limitations prevent a complete production-image assembly claim and
remain Human decision items. No deployment, certification, complete OpenClaw
lifecycle or real execution claim is made.
