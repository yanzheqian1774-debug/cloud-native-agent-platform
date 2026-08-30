# S5-IMPL-037 Checkpoint A evidence

## Checkpoint scope

This evidence file records the G1 plan and validation evidence for Checkpoint A
of S5-IMPL-037, Package 7 supplier-quality live journey integration. Checkpoint
A leaves the authorized diff uncommitted for review. It does not authorize a
commit, push, pull request, merge, deployment, S5-TEST-007 mutation, or
downstream work.

## Entry revalidation

- Durable baseline: `457a9240e4ce85ef354dec84b991797c28b428be`.
- Expected branch:
  `codex/s5-impl-037-package-7-live-journey-integration`.
- Current branch and `HEAD` were revalidated as the expected branch at the
  exact durable baseline before this plan was written.
- `origin/main` was fetched and resolved to the same durable baseline.
- CI run `33266294559` was revalidated as workflow `CI`, event `push`, branch
  `main`, conclusion `success`, and head SHA equal to the durable baseline.
- GitHub pull-request and issue searches found no existing S5-IMPL-037 task or
  pull request and no pull request whose head is the expected branch.
- Repository text search found no competing S5-IMPL-037 task record.
- Worktree and branch inspection found the expected branch checked out only in
  this worktree. The parallel S5-TEST-007 worktree is separate and remains
  untouched.
- No `CODEOWNERS` file or path-specific ownership rule is present. The 17
  authorized paths below are therefore owned solely by this task's exact
  scope; no other branch or worktree was found to claim S5-IMPL-037.
- The worktree was clean before this file, the first repository mutation, was
  added.
- The Package 7 materialized input at
  `examples/s5-v0.2-supplier-quality/` was inspected read-only and remains
  unchanged.

## G1 implementation plan

### Dependency composition

The new backend bridge will be an internal, replaceable composition layer. It
will consume the existing Package 7 materialized pack and invoke existing
authorities in this order:

1. Resolve a server-configured absolute materialized root whose final component
   is exactly `s5-v02-supplier-quality-demo`.
2. Validate the scope marker, scenario manifest, canonical manifest digest,
   checksum manifest, every allowlisted checksum, exact scenario identity,
   namespace, tenant, and security domain. Tenant/domain authorization occurs
   before any scoped business input is read.
3. Generate the exact three-task plan through `PlanningEngine` and
   `SupplierQualityReferenceGenerator`, then issue an exact approval and use
   the approved canonical workflow revision and digest.
4. Materialize the Package 7 role declarations through the existing Definition
   Authority by creating Definition versions, explicit publication decisions,
   and explicit match-authorization decisions. Package files remain
   declarations and never become authority by themselves.
5. Submit one bounded `PublishedRoleMatcher` request for the executable plan.
   Matching remains advisory and performs no runtime or provider calls.
6. Make one authorization-first Knowledge retrieval for the exact
   tenant/domain scope, record retrieval evidence, and assemble governed
   citations. Denied, malformed, digest-conflicted, stale, or unavailable
   paths perform zero Knowledge source reads and zero execution calls.
7. Derive the existing runtime requirement from the approved revision and
   exact role bindings, then run the existing `NativePlacementEvaluator` once
   for the executable binding. Placement performs zero execution, provider,
   or Capability Gateway calls.
8. Mint Platform execution identities from approved platform-owned inputs,
   construct existing internal envelopes without generating an Agent or Native
   Agent resource, and invoke the existing `TaskExecutionCoordinator` once per
   task. Its injected existing `NativeRuntimeProvider` is invoked once per
   task. No task requires a Capability Gateway call.
9. Persist normalized execution evidence through a bridge-owned in-memory
   implementation of the existing append-only Evidence repository port. This
   introduces no database or persistent infrastructure dependency and does not
   change Evidence ownership or deletion semantics.
10. Assemble existing WorkflowOutcome documents and existing shared snapshot
    and Graph projections from the genuine execution/evidence results.
11. Register the completed live result through
    `LiveJourneyCoordinator.register_live`, expose the same backend-generated
    journey identity to Product and Technical projections, and stream existing
    `journey-event.v1` events.

The bridge does not modify the Planning, Definition, Matching, Knowledge,
Runtime Placement, Runtime Provider, Graph, Evidence, CRD, shared DTO, or
lifecycle authorities it composes.

### Authority and identity ownership

- The server-configured materialized root owns Package 7 input bytes only.
- Planning owns the canonical plan, revision, approval, digest, and successor
  lineage.
- Definition Authority owns version, publication, and match-authorization
  decisions; Package declarations cannot publish or authorize themselves.
- Published Role Matching owns advisory match decisions only.
- Knowledge authorization gates the single scoped source read, while existing
  Knowledge evidence and citation assemblers own governed evidence/citations.
- Runtime Placement owns the non-executing placement decision.
- Platform execution identity is minted by existing Core identity types;
  provider-native correlation IDs remain evidence and never substitute for a
  Platform identity.
- `TaskExecutionCoordinator` is the execution authority and the existing
  `NativeRuntimeProvider` is the provider boundary. The bridge does not call a
  provider directly.
- Existing Outcome, Execution Evidence, shared snapshot, Graph, Live Journey,
  SSE, intervention, and feedback types retain their established ownership.
- Product and Technical views consume one shared live backend journey and may
  not invent, relabel, or diverge identifiers.

### Exact call-count contract for the initial three-task journey

- Planning generator: exactly 1 call.
- Published Role Matcher: exactly 1 bounded request.
- Knowledge source: exactly 1 read after authorization; zero reads on every
  denial or pre-retrieval validation failure.
- Native placement: exactly 1 evaluation for the one executable runtime
  binding; zero execution/provider effects during placement.
- Task execution coordinator: exactly 3 calls, one for each approved task.
- Native Runtime Provider: exactly 3 calls, one through each coordinator call.
- Capability Gateway: exactly 0 calls because no approved task requires a
  capability invocation.
- Fixture or synthetic execution authority: exactly 0 calls.
- Denied, mismatched, stale, unavailable, or incompatible paths: exactly 0
  coordinator/provider calls.

The implementation tests will expose and assert these counts rather than infer
them from successful output.

### Initiation, replay, correction, approval, rerun, and reset

- `POST /api/internal/demo/v1/supplier-quality-journeys` accepts only the exact
  Package 7 scenario identity and a bounded replay identity.
- Exact replay returns the original backend journey and performs no duplicate
  planning, read, placement, or execution effects. Reusing a replay identity
  with a different request returns a conflict.
- Malformed input, checksum conflict, authorization denial, stale authority, or
  unavailable authority fails truthfully and never registers a synthetic
  fallback.
- Demo correction is routed back through Planning to create a canonical
  successor candidate. It requires a fresh exact approval before execution.
- Demo rerun re-evaluates current Definition publication/authorization,
  matching, Knowledge authorization/retrieval, placement, and then invokes the
  existing coordinator under fresh Platform execution identities. Predecessor
  and successor Outcomes and Evidence remain preserved and distinguishable.
- `DELETE /api/internal/demo/v1/supplier-quality-journeys/{journey_id}` requires
  exact scenario, namespace, journey, tenant, security domain, and a
  server-issued confirmation token bound to all five identities.
- Reset may remove only the bridge-owned active registration, bounded SSE
  buffer/subscriptions for that exact scope, and bridge transient replay state.
  It will not delete canonical planning/approval history, Definition decisions,
  Knowledge documents/decisions/evidence/citations, execution evidence,
  Outcomes, intervention/feedback records, Kubernetes resources, Package 7
  inputs, or unrelated journeys.

### Live and synthetic UI separation

- The frontend will add an explicit supplier-quality live-demo mode that starts
  the internal demo endpoint once with a stable replay identity.
- In that mode, both Product and Technical routes receive the same returned
  backend journey ID and render only the live journey/intervention surface.
- Live mode remains continuously and visibly labeled `LIVE_EXECUTION`; it never
  renders or blends synthetic preview fixture panels.
- A live failure, denial, stale result, or unavailable backend is displayed
  truthfully as an unavailable/failed live state with no fixture fallback.
- Existing synthetic preview remains available only in its explicitly
  synthetic, non-authoritative mode, and its controls are not presented as live
  effects.
- English and Simplified Chinese messages, desktop layout, and 390x844 mobile
  layout will be verified in the in-app Browser.

### Exact authorized path ownership

Only these 17 paths may change:

1. `console/backend/src/agent_console/supplier_quality_demo.py`
2. `console/backend/src/agent_console/supplier_quality_demo_schemas.py`
3. `console/backend/src/agent_console/app.py`
4. `console/backend/src/agent_console/live_journey.py`
5. `console/backend/src/agent_console/live_journey_stream.py`
6. `console/backend/src/agent_console/intervention_feedback.py`
7. `console/backend/tests/test_supplier_quality_demo.py`
8. `console/backend/tests/test_supplier_quality_demo_api.py`
9. `console/backend/tests/test_live_journey.py`
10. `console/backend/tests/test_live_journey_stream.py`
11. `console/frontend/src/api/supplierQualityDemo.ts`
12. `console/frontend/src/pages/ProductViewPage.tsx`
13. `console/frontend/src/pages/TechnicalViewPage.tsx`
14. `console/frontend/src/App.tsx`
15. `console/frontend/src/i18n/messages.ts`
16. `tests/test_s5_impl_037_package_7_live_integration.py`
17. `docs/evidence/s5/v0.2/s5-impl-037/README.md`

No extra frontend test file is planned. Existing frontend lint, type checking,
production build, focused backend/integration tests, and Browser QA provide the
frontend verification within the authorized path budget.

### Validation plan

Validation will cover:

- Package 7 bootstrap/reset determinism and checksum enforcement.
- Successful start, exact replay, replay conflict, malformed input, foreign or
  relative root rejection, checksum failure, authorization denial, stale or
  unavailable authority, and truthful no-fallback behavior.
- Exact canonical planning/approval, Definition publication and match
  authorization, one matching request, authorization-first one-read Knowledge
  retrieval, governed evidence/citations, non-executing placement, coordinator
  and provider call counts, zero Capability Gateway/fixture effects, and zero
  denied/mismatched runtime effects.
- Genuine Outcomes, append-only Execution Evidence, shared snapshot/Graph
  projection, identical Product/Technical IDs/evidence/citations/revision/
  outcome/intervention, and ordered bounded SSE events.
- Correction, fresh exact approval, rerun with fresh Platform execution
  identity, successor lineage, and preserved predecessor/successor
  Outcome/Evidence history.
- Exact scoped reset, replay-state and SSE cleanup, preservation of planning,
  approval, Definition, Knowledge, Outcome, Evidence, intervention/feedback,
  Kubernetes, Package 7, and unrelated journey state.
- English and Simplified Chinese UI, desktop viewport, and 390x844 mobile
  viewport in the in-app Browser, including the absence of synthetic fixture
  panels in live mode.
- Focused backend and repository integration tests; frontend lint, type check,
  and build; repository Ruff checks; `make check`; all-files pre-commit; a
  post-hook exact path audit; post-hook `make check`; `git diff --check`; and a
  final audit that the diff is a subset of, and intended to contain exactly,
  the 17 authorized paths.

Actual commands, results, counts, Browser observations, and limitations will be
recorded below after execution. A validation will not be reported as passing
unless it was run in this worktree.

## G2 and STOP triggers

Work stops and reports exact evidence to CONTROL if implementation would
require any of the following:

- an eighteenth changed path or a new frontend test file;
- any mutation under `examples/s5-v0.2-supplier-quality/`;
- a public API, CRD, Kubernetes API group, frozen/shared DTO, lifecycle, tenant
  or authorization architecture change;
- a persistence/database dependency, Graph contract change, Evidence ownership
  or deletion change, runtime/provider implementation change, generated Native
  Agent, Solution Blueprint, external/OpenClaw runtime, or deployment;
- fixture/synthetic execution substituted for required live authority;
- an execution authority unable to issue Platform-owned identities;
- reset behavior that cannot be exact, scoped, and non-destructive;
- a Browser defect whose fix requires an unauthorized path;
- Package 6B, Package 9, credentials/data acquisition, governance, S5-TEST-007,
  or downstream work.

## Validation evidence

### Implemented boundary

- The exact Package 7 materialized inputs now enter one internal composition
  bridge through strict start/reset DTOs and the exact internal POST/DELETE
  routes. The bridge validates the trusted absolute root, final directory name,
  scope marker, manifest identity, manifest digest, checksum set, and every
  materialized runtime input before planning or scoped effects.
- The successful three-task path crosses Planning, exact approval, Definition
  publication/match authorization, one Published Role Matching request,
  authorization-first Knowledge retrieval, Knowledge evidence/citations,
  non-executing Native placement, three coordinator calls, three existing
  Native Provider invocations, append-only Execution Evidence, Outcome,
  shared snapshot/Graph, live registration, and existing SSE projection.
- Exact start replay is effect-free; conflicting replay fails closed.
  Correction creates an immutable Planning successor, approval is bound to its
  exact digest, and rerun revalidates Definition/Matching/Knowledge/placement
  before issuing three fresh Platform execution identities. Predecessor and
  successor Outcome/Evidence history remains distinct.
- Reset removes only the exact bridge-owned active registration, scoped SSE
  state, and transient replay state. Tests verify that Package 7 inputs,
  planning/evidence/outcome history, intervention/feedback history, and an
  unrelated live journey remain preserved.
- The Core identity and Evidence adapter is dependency-injected from the
  already-authorized application composition root. This preserves the frozen
  Core-consumer rollback boundary; no guard, shared contract, Core path, or
  eighteenth path was changed.
- Live frontend mode consumes one backend-issued response for both Product and
  Technical routes, verifies their identity/revision equality at the API
  boundary, labels both routes `LIVE_EXECUTION`, and does not render synthetic
  fixture panels in live mode. Synthetic preview behavior remains unchanged
  outside explicit live mode.

### Exact successful-path counts

Focused tests observed and asserted:

- planning generator: 1;
- Published Role Matcher requests: 1;
- authorized Knowledge source reads: 1;
- Native placement evaluations: 1;
- Task execution coordinator calls: 3;
- Native Provider invocations: 3;
- Capability Gateway invocations: 0;
- fixture/synthetic executions: 0.

Authorization denial was verified with zero Knowledge source reads, placement,
coordinator, provider, Gateway, fixture, and live-registration effects.
Checksum/root failures were verified before planning or scoped effects.
Unavailable placement was verified with zero coordinator/provider effects.

### Automated validation results

- Package 7 plus focused backend/API/live/SSE/integration suite:
  `45 passed, 1 warning`.
- Frozen Core-consumer compatibility guard after composition-root injection:
  `2 passed`.
- Ruff on all changed Python paths: passed; 11 files already formatted.
- Frontend `npm run lint`: passed.
- Frontend `npm run build` (`tsc -b && vite build`): passed; 72 modules
  transformed and production assets emitted successfully.
- First complete `make check` after the compatibility-boundary adjustment:
  Ruff lint passed, all 159 Python files passed format verification, and all
  `941` repository tests passed with one warning.
- `pre-commit run --all-files`: Ruff lint, Ruff format, and pytest hooks all
  passed. SHA-256 fingerprints for all 17 authorized files were identical
  before and after the hook run; the hook made no mutation.
- Required post-hook `make check`: Ruff lint passed, all 159 Python files
  passed format verification, and all `941` tests passed with one warning.
- `git diff --check`: passed before validation and is rerun in the terminal
  audit below.

The warning in focused and repository test runs is the existing
Starlette/httpx `TestClient` deprecation warning; it is unrelated to this
change and does not affect test results.

An initial repository-wide run exposed the frozen Core-consumer rollback guard
because the new bridge directly imported Core types. No test was weakened.
The implementation was refactored to inject those types and the transient
Evidence adapter from the already-authorized application composition root;
the focused suite and the full 941-test repository gate then passed.

### Browser QA

The in-app Browser exercised the final live-mode UI against the local backend
and Vite server using the checksum-validated materialized Package 7 root.

- Product and Technical routes rendered the same backend journey, canonical
  revision/digest, shared snapshot, Graph snapshot, Platform execution,
  approval, placement, evidence, citation, outcome, and intervention identity
  spine.
- Desktop Product and Technical views were visually inspected in English.
  Long Technical identifiers wrap within their cards; measured document width
  equaled viewport width with no horizontal overflow.
- Product and Technical routes were inspected at `390x844` in English and
  Simplified Chinese. Both had document width equal to viewport width, no
  horizontal overflow, visible `LIVE_EXECUTION` labeling, and no synthetic or
  fixture panel text.
- Route switching preserves live mode without carrying unrelated synthetic
  query identifiers.
- A clean-console pass reported no errors or warnings during normal live
  operation.
- The backend was then intentionally stopped and the page reloaded. The UI
  displayed `LIVE_EXECUTION · ERROR` and “No synthetic preview was
  substituted”; DOM checks confirmed no synthetic or fixture content. The
  backend was restarted and the Product route recovered to the live journey.
  The intentional proxy connection error occurred only during this required
  unavailable-state test.
- Browser and local server sessions were closed after QA.

### Limitations and non-goals

- Demo registration, replay state, SSE buffers, and the bridge adapter for the
  existing append-only Evidence port are deliberately process-local. A process
  restart removes active presentation/replay state; no persistent dependency
  was authorized or introduced. Completed Outcome/Evidence preservation is
  verified across exact scoped reset within that process.
- Package 7 materialization intentionally contains the eight runtime inputs,
  while `bootstrap.sh` and `reset.sh` remain source-side control scripts. The
  bridge validates the exact declared script digest entries and every
  materialized runtime checksum; the immutable Package 7 suite separately
  verifies deterministic bootstrap/reset behavior.
- The existing Native Provider is invoked with its bounded deterministic mock
  compatibility profile, but its injected invocation computes the live result
  from the validated Package 7 cases. No external model, generated Native
  Agent, Capability Gateway operation, external Runtime, deployment, or
  synthetic execution substitution was introduced.
- This checkpoint does not change public APIs, CRDs, the Kubernetes API group,
  shared DTOs, architecture/governance documents, dependencies/lockfiles, CI,
  Runtime implementation, Package 7, S5-TEST-007, or downstream work.

### Terminal audit

The terminal Checkpoint A audit verifies the branch remains
`codex/s5-impl-037-package-7-live-journey-integration`, `HEAD` remains the
durable baseline, Package 7 remains byte-identical, the working tree contains
exactly the 17 authorized changed paths listed above, and all changes remain
uncommitted. No commit, push, pull request, merge, deployment, or downstream
session was performed.

### Stalled-validation recovery

Human gate `S5-IMPL-037_CHECKPOINT_A_STALLED_VALIDATION_RECOVERY_V1`
authorized a read-only process audit and one non-overlapping recovery hook run.

- The reported `8h23m` was not the duration of a running pre-commit process.
  A read-only process audit found no active pre-commit, pytest, `uv run`, Ruff,
  Vite, uvicorn, or frontend development-server process. The only matching
  processes were the audit shell and its `rg` child. The value was therefore
  task/conversation elapsed time, not hook elapsed time.
- `lsof` found no listener on port 8000 or 5173; all QA servers remained
  stopped. No validation or server process required interruption.
- Recovery entry state remained at the durable baseline on the expected
  branch, with no staged changes, ten expected tracked unstaged files, and
  seven expected untracked files. The staged diff SHA-256 was the empty-stream
  digest `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
  the tracked unstaged diff SHA-256 was
  `d3a3a8d331533b329846842d036bd53e475fda45a405893bfefd0ed7f1026624`.
- Sixteen current file hashes matched the saved pre-hook fingerprint exactly.
  The only expected difference was this authorized Evidence README, which had
  been deliberately completed with validation results after the saved
  fingerprint. No implementation file differed.
- The single recovery invocation of `pre-commit run --all-files` completed in
  9.73 seconds: Ruff lint passed, Ruff format passed, and pytest passed.
- Before/after status, staged/unstaged diff hashes, and all 17 current file
  hashes were identical. The recovery hook made no mutation and introduced no
  unauthorized path.
- The Evidence text in this subsection was the only deliberate post-hook
  mutation. The post-hook `make check` passed Ruff lint, format verification
  for all 159 Python files, and all 941 tests with the one existing
  Starlette/httpx warning. `git diff --check` and the trailing-whitespace audit
  passed; the final path comparison returned exactly the 17 authorized paths
  with zero staged files, and Package 7 remained unchanged. A final process and
  port audit again found no lingering validation process or QA server.

## Checkpoint C terminal validation

Human gate `S5-IMPL-037_CHECKPOINT_C_TERMINAL_IMPLEMENTATION_V1` authorized
terminal validation, one exact-parent commit, a normal branch push, one Draft
pull request, and exact-head CI observation. This subsection records the final
repository state and validations available before that immutable commit.

### Terminal entry audit

- `origin` is
  `git@github.com:yanzheqian1774-debug/cloud-native-agent-platform.git`.
- A fresh fetch resolved `origin/main`, local `HEAD`, and the durable baseline
  to `457a9240e4ce85ef354dec84b991797c28b428be`.
- The checked-out branch is exactly
  `codex/s5-impl-037-package-7-live-journey-integration`; no other worktree
  owns it and no existing issue, pull request, or pull-request head collides
  with S5-IMPL-037.
- Baseline CI run `33266294559` remains completed/successful for workflow `CI`,
  event `push`, branch `main`, and the exact durable-baseline SHA.
- Package 7 is byte-identical to the durable baseline and has no status entry.
- The separate S5-TEST-007 worktree remains clean on its expected branch at the
  durable baseline. It was not resumed or mutated.
- S5-REL-039 and S5-REL-040 have no repository branch/worktree, GitHub issue,
  or GitHub pull-request collision. S5-REL-039 remains the primary future REL
  allocation candidate and S5-REL-040 the fallback; neither was started.
- The accepted Checkpoint A 17-file hash-manifest digest was revalidated as
  `d30d36235bde79e2497f27f4c46f332a06b706cfdd175eccc90f3b8a94599754`
  before terminal validation.

### Terminal validation results

- Focused immutable Package 7, backend, API, live-journey, SSE, and repository
  integration matrix: `45 passed, 1 warning`.
- Ruff lint on all 11 changed Python paths: passed.
- Ruff format verification: all 11 changed Python paths already formatted.
- Frontend ESLint: passed.
- Frontend TypeScript and production build (`tsc -b && vite build`): passed;
  72 modules transformed and production assets emitted.
- Final pre-hook `make check`: Ruff lint passed, all 159 Python files passed
  format verification, and all `941` tests passed with one warning.
- The all-files pre-hook fingerprint contained zero staged files, tracked
  unstaged diff SHA-256
  `d3a3a8d331533b329846842d036bd53e475fda45a405893bfefd0ed7f1026624`,
  and 17-file manifest digest
  `d30d36235bde79e2497f27f4c46f332a06b706cfdd175eccc90f3b8a94599754`.
- One Checkpoint C `pre-commit run --all-files` invocation completed in 9.56
  seconds: Ruff lint, Ruff format, and pytest hooks passed. Before/after status,
  staged/unstaged diff hashes, and the 17-file manifest were identical; hooks
  made no mutation.
- Required post-hook `make check`: Ruff lint passed, all 159 Python files
  passed format verification, and all `941` tests passed with one warning.
- The warning remains the existing Starlette/httpx `TestClient` deprecation;
  it is unrelated to S5-IMPL-037.

### Terminal live/fail-closed reconfirmation

The in-app Browser re-ran the terminal live-mode verification against the
checksum-validated Package 7 materialization:

- Product rendered `LIVE_EXECUTION`, exact approval, and governed citations;
  Technical rendered `LIVE_EXECUTION`, Graph, and Evidence.
- Neither route contained `SYNTHETIC` or `FIXTURE` content, neither overflowed
  horizontally, and the clean live pass emitted no console warning or error.
- After the backend was intentionally stopped, reload displayed
  `LIVE_EXECUTION`, `ERROR`, and “No synthetic preview was substituted,” with
  no synthetic or fixture content.
- The Browser tab, Vite server, and backend server were closed after the check.

### Pre-commit terminal boundary

The only post-hook change is this authorized Evidence subsection. The final
pre-commit audit must still show exactly the 17 authorized paths, no staged
files before explicit staging, a clean `git diff --check`, unchanged Package 7,
and an untouched S5-TEST-007 worktree. The resulting commit must have the
durable baseline as its sole parent. Commit SHA, Draft PR URL/inventory, and
exact-head CI results are necessarily external post-commit facts and are
returned in the Checkpoint C terminal handoff without adding a second commit.
