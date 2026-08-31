# S5-IMPL-052 Checkpoint A1 Evidence

## Status

`CHECKPOINT_A1_IMPLEMENTATION_COMPLETE / DRAFT_PR_ONLY / AWAITING_TRACK_A`

This evidence covers independently implementable Workflow Definition and Runtime
Profile product work. It does not claim final Checkpoint A, Integration Ready,
v0.2.2 completion, deployment, release, runtime execution, or migration-chain
completion.

## Entry revalidation

- Authorized baseline and worktree HEAD: `6c3b72e416fa21dc77be94d9be4bb054b39caef4`.
- `origin/main` revalidated at the same commit before implementation.
- Branch: `codex/s5-impl-052-workflow-runtime-profile`.
- Initial worktree was clean and isolated.
- No S5-IMPL-052 Registry, repository, branch, worktree, PR, issue, or visible
  Human-allocation collision was found.
- Track A owns migration `0006` and Agent-domain paths. No Track A source was
  copied or imported.

## Implemented result

### Workflow Definition

- Scoped canonical aggregate, immutable revisions, canonical digest, optimistic
  concurrency, append-only lifecycle facts, exact-digest Human review,
  publication, successor history, and deterministic version comparison.
- Canonical Tasks with deterministic topological ordering, duplicate/unknown/
  self-dependency rejection, cycle rejection, inputs, outputs, capability
  requirements, exact typed references, retry limits, timeouts, and bounded
  failure policies.
- Runtime Profile references resolve only through the routed typed service seam.
  Unknown or unpublished exact revisions fail closed. Agent/Skill/MCP/Knowledge
  reference resolver composition remains unavailable until durable Track A
  assembly and therefore fails closed.
- Catalog, dashboard, list/detail, Builder, DAG/policy inspection, review,
  publication, successor/history/comparison, relationship/consumer inspection,
  and Product/Technical sibling projections are present.

### Runtime Profile

- Scoped canonical aggregate, immutable revisions, canonical digest, optimistic
  concurrency, append-only lifecycle facts, exact-digest Human review,
  publication, and successors.
- Declarative Native Kubernetes and bounded OpenClaw definitions with requests/
  limits, isolation, state mode, session affinity, typed Secret references, and
  provider-specific compatibility validation.
- Catalog, dashboard, detail, lifecycle actions, history, and Product/Technical
  sibling projections are present.

## Migration 0007

- Track B exclusively adds
  `console/backend/migrations/0007_workflow_runtime_profiles.sql`.
- The migration adds separate `workflow_definition` and `runtime_profile`
  schemas, scoped aggregate rows, append-only fact tables, primary/unique/
  foreign-key constraints, and checksum-bound migration metadata.
- Migration 0007 was applied from an empty PostgreSQL 15 database and its
  checksum compatibility was validated by both adapters.
- Migrations `0001`–`0005` are unchanged. No placeholder or copied migration
  `0006` exists. The complete `0001`→`0007` chain is intentionally not claimed.

## Shared paths used and justification

- `console/backend/src/agent_console/app.py`: exactly two router imports and two
  `include_router` calls. No Wave 1 route, Agent route, lifecycle authority,
  execution authority, Pod authority, or Track A resolver composition moved
  into the composition root.
- `console/frontend/src/App.tsx`: imports and routes the two authorized
  Workbenches and adds their navigation entries; all Wave 1 routes are retained.
- `console/frontend/src/components/ConsoleShell.tsx`: adds direct navigation to
  the two product modules while retaining Product, Technical, and Workflow Run
  links.
- `console/frontend/src/styles/app.css`: adds module-local responsive Workbench
  layout styles; existing selectors are not changed.
- `.github/workflows/ci.yml`: adds only `WORKFLOW_RUNTIME_DATABASE_URL` and
  `WORKFLOW_RUNTIME_TEST_DATABASE_URL` to the existing PostgreSQL jobs so the
  new real adapters and browser journey are exercised. No dependency, job
  authority, or validation weakening was introduced.

No package manifest, lockfile, Python dependency, or migration `0001`–`0006`
path was changed.

## Runtime safety boundaries

- Schemas reject unknown fields and services recursively reject Pod YAML, Pod
  names, raw environment, exec/command, raw Secret values, and unsanitized-log
  fields.
- Only `secret-ref:` typed references are accepted; secret values are neither
  persisted nor digested.
- Runtime Profiles contain no operation that creates/deletes Pods, executes
  commands or OpenClaw, selects Pod names, observes Pod state, routes instances,
  scales workloads, or treats Kubernetes as Product authority.
- Product and Technical views project the same backend-owned records and cannot
  mutate authority independently.

## Validation evidence

- Focused repository/service/API/PostgreSQL/restart suite: `20 passed`.
- Real PostgreSQL 15 migration, scope, optimistic concurrency, checksum, and
  restart tests: `4 passed` within the focused suite.
- Frontend `npm run lint`: passed.
- Frontend `npm run build`: passed; Vite production build completed.
- Real backend + PostgreSQL 15 + Qdrant + Chromium Workflow/Runtime acceptance:
  `3 passed`, including publication, exact Runtime binding, validation failure,
  empty/loading presentation, bounded OpenClaw projection, and denied state.
- Final clean full Playwright suite: `6 passed`, covering Agent, Skill/MCP,
  Knowledge, Workflow Definition, Runtime Profile, restart recovery, validation
  failure, and disclosure-safe denial.
- Pre-commit: Ruff lint, Ruff format, and full pytest hooks passed with the real
  integration services available.
- `make check`: Ruff passed, format check passed (`234 files`), pytest
  `1103 passed, 1 skipped, 1 warning`; Kubernetes Workflow/Task controllers and
  CRD regressions were included unchanged.
- The one skip is the repository's separately gated direct-Qdrant test; the real
  Knowledge Chromium journey using Qdrant passed.
- Warning: existing Starlette/httpx deprecation warning only.

## Browser and state behavior

The browser journey used the real FastAPI backend, PostgreSQL 15, Qdrant for the
Wave 1 regression, and Chromium. Browser state is presentation state only.
Loading, empty, denial, validation failure, retryable failure, and ready states
are explicit and do not synthesize authoritative resources.

## Agent dependency and limitations

- S5-IMPL-051 and migration `0006` are not durably integrated.
- No unmerged Agent source or migration was copied or imported.
- Final exact Agent/Skill/MCP/Knowledge reference composition, byte-for-byte
  verification of migrations `0001`–`0006`, complete `0001`→`0007` migration
  validation, cross-module binding acceptance, fresh exact-head CI, and final
  Checkpoint A remain blocked on durable Track A integration.
- OpenClaw is declaration-only; actual execution remains v0.2.3 scope.

## Next gate

Controlled pause after a clean Draft PR. Await S5-IMPL-051 and migration `0006`
Durable Integration, merge advanced `origin/main` normally without rebase, then
perform final assembly and cross-module validation. Do not mark the PR Ready or
route it for integration before that gate.
