# S5-V023-IMPL-230 Checkpoint A Evidence

## Allocation and baseline

`S5-V023-IMPL-230` was allocated only after repository history, refs, branches,
tags, worktrees, all GitHub PRs/issues and visible Codex tasks showed no prior use
outside this authorized task. Fresh `origin/main` remained
`caea10abcdd68f28cae9ba81d6ebc81ae8669386`, tree
`0376c5ba28b239c978ee4013a1a00b69c5fa8d41`. CI run `33715736988`, push attempt
1 for that exact commit, was `SUCCESS`.

## Exact path ownership

- `operator/src/agent_operator/runtime_provider_factory.py`
- `operator/src/agent_operator/native_runtime_adapter.py`
- `operator/src/agent_operator/openclaw_runtime_adapter.py`
- `operator/tests/test_runtime_provider_factory.py`
- `operator/tests/test_native_runtime_adapter.py`
- `operator/tests/test_openclaw_runtime_adapter.py`
- `docs/evidence/s5/v0.2/s5-v023-impl-230/README.md`

No open PR or mutable worktree overlapped these paths before editing. Global
application/bootstrap, PostgreSQL repositories, migration `0008`, Evidence
repositories, Product identity creation, frontend, compatibility, CI, deployment
and Release Runner/Harness paths remain outside ownership.

## Implemented boundary

The factory accepts exactly one explicit `native` or `openclaw` selection and
rejects missing, ambiguous, unknown, absent or conflicting registration. Its
closed, deterministic registration tuple is inert metadata for later Track 270;
this task performs no global registration.

The Native adapter reuses the durable Runtime Manager and identity translator.
The OpenClaw adapter reuses the provider-local exact-version provider and Placement
driver. Both consume the existing typed internal execution envelope, exact
Placement and typed desired command. They reject Provider, Agent Instance, Runtime
Instance and Placement identity conflicts before effects. Provider/Kubernetes
identifiers remain subordinate correlations and never replace Product identities.

OpenClaw start observes first, including after process restart, and starts only
after a typed missing observation. Successful lifecycle facts preserve generation,
state, health, readiness and freshness. Stale, unknown and ambiguous failures remain
distinct; raw provider failure text is not retained. Stateful/stateless and session
affinity validation, graceful stop and one-generation bounded replacement remain in
the reused provider-local implementation.

## Validation

- focused new factory/adapters plus existing Native/OpenClaw/runtime acceptance and
  compatibility: `96 passed`;
- exact OpenClaw target: `2026.7.1-2`, tag
  `0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c`, accepted package integrity;
- live exact-version startup/readiness/shutdown: current accepted executable is not
  present on `PATH`; prior durable S5-IMPL-080 evidence is not represented as a new
  run by this task;
- `make check`: `1373 passed, 23 environment-gated skips`, one existing
  Starlette/httpx deprecation warning;
- Ruff lint and formatting: passed;
- `pre-commit run --all-files`: passed;
- post-pre-commit `make check`: passed with the same result;
- exact-path/overlap, prohibited-scope, secret/private-key, nondisclosure,
  generated-artifact, absolute-local-path and conflict-marker scans: passed.

## Claims and limitations

No PostgreSQL Product-identity write, global bootstrap, model-provider registration,
public CRD/API, dependency, deployment, v0.2.2 environment access, certification,
production readiness or complete Native/OpenClaw Product execution is claimed.
