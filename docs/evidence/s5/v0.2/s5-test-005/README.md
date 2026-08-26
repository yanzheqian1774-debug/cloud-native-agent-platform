# S5-TEST-005 Checkpoint A — Conformance Harness Candidate

## Session and provenance

- Session: `S5-TEST-005` — Conformance Harness
- Type / Track: `TEST / E1 — CONFORMANCE_HARNESS`
- Lifecycle: `ACTIVE / IN_PROGRESS`
- Checkpoint: `A — CONFORMANCE_HARNESS_CANDIDATE` (step 1 of 3)
- Conversation: new dedicated conversation; no child Agents or parallel Agent work
- Worktree: `/private/tmp/s5-test-005-conformance-harness`
- Branch: `codex/s5-test-005-conformance-harness`
- Authorized baseline and initial HEAD:
  `df76e0b36dcb42c12e25852a04fd0086dac987a8`
- Final candidate HEAD: the commit containing this artifact, resolved exactly by
  `git rev-parse HEAD` and recorded in the Draft PR; a commit cannot contain its
  own content-addressed SHA.
- Source of truth: `origin/main` at the authorized baseline; baseline drift: none

## Architecture and boundaries

The Harness is an internal test package. It observes existing component seams
and does not define or change production behavior. Import direction is one-way:
the Harness imports existing components, while production packages do not import
the Harness. The change adds no endpoint, CRD/schema field, public wire value,
dependency, lockfile change, persistent state, runtime behavior, certification,
release acceptance, or Contract freeze.

The result model is immutable and machine-readable. Each passing result names
an exact target, profile, and version/candidate boundary. Diagnostics are
whitespace-normalized, bounded to 240 characters, and redacted when they contain
credential-like markers. Caller-provided mappings and loaded fixtures are
defensively copied.

## Changed-path inventory

- `conformance_harness/src/conformance_harness/__init__.py`
- `conformance_harness/src/conformance_harness/adapters.py`
- `conformance_harness/src/conformance_harness/fixtures.py`
- `conformance_harness/src/conformance_harness/manifest.py`
- `conformance_harness/src/conformance_harness/models.py`
- `conformance_harness/src/conformance_harness/runner.py`
- `conformance_harness/fixtures/criteria.json`
- `conformance_harness/fixtures/capability_request.json`
- `tests/conformance_harness/test_adapters.py`
- `tests/conformance_harness/test_fixtures.py`
- `tests/conformance_harness/test_manifest.py`
- `tests/conformance_harness/test_runner.py`
- `tests/conformance_harness/test_targets.py`
- `docs/evidence/s5/v0.2/s5-test-005/README.md`
- `pyproject.toml` (adds only `conformance_harness/src` to pytest discovery)

No dependency, packaging, version, or build-backend configuration changed.

## Manifest and disposition semantics

The closed `s5-test-005/v1` manifest schema rejects unknown or missing fields,
unknown criterion types, duplicate IDs, invalid profiles, and malformed JSON.
Criteria and explicit selections execute in criterion-ID order.

- `PASS`: the adapter completed and returned completed supporting evidence.
- `FAIL`: an assertion or adapter boundary failed; a stable reason code and
  bounded diagnostic are retained.
- `UNRUN`: no adapter exists or supporting evidence is incomplete. It is never
  counted as PASS.
- `NOT_APPLICABLE`: the criterion does not apply to the selected Harness
  profile. It is never counted as PASS.

Stable reason codes are `CRITERION_PASSED`, `ASSERTION_FAILED`,
`ADAPTER_ERROR`, `ADAPTER_NOT_REGISTERED`, `EVIDENCE_INCOMPLETE`,
`PROFILE_NOT_APPLICABLE`, and `SELECTION_EXCLUDED` (reserved for an explicitly
excluded selection record in a future bounded revision).

## Criterion and result matrix

Profile executed: `mvs-native`.

| Criterion | Exact target / profile / boundary | Classification | Result |
| --- | --- | --- | --- |
| `A2-IDENTITY-001` | A2 Identity Spine / `internal-v0.2-candidate` / `v0.2` | `TESTED` | `PASS` |
| `A3-COMPAT-001` | A3 Compatibility Interpreter / `legacy-task-v0.2-candidate` / `v0.2` | `TESTED` | `PASS` |
| `B-NATIVE-001` | Native Runtime Provider / `native/mock/deterministic` / `native-provider-v0.2-candidate` | `SUPPORTED_CANDIDATE` | `PASS` |
| `C-GATEWAY-001` | Capability Gateway synthetic REST / `synthetic-rest/deterministic` / `capability-gateway-v0.2-candidate` | `TESTED` | `PASS` |
| `E-MVS-001` | Bounded MVS Task execution integration / `native+synthetic-rest` / `v0.2-candidate` | `SUPPORTED_CANDIDATE` | `PASS` |
| `E-WORKFLOW-OPTIONAL-001` | Workflow terminal propagation / optional / `not-yet-proven` | `NOT_YET_PROVEN` | `NOT_APPLICABLE` |

Arithmetic: total `6` = PASS `5` + FAIL `0` + UNRUN `0` +
NOT_APPLICABLE `1`. The summary is derived from individual results and replayed
twice with byte-equivalent normalized records in tests.

## Fixture inventory

- `criteria.json`: normative only for this internal candidate; six closed-schema
  criteria and explicit applicability profiles.
- `capability_request.json`: deterministic synthetic REST input, explicitly
  classified `EXPERIMENTAL`; it is not production Capability evidence.

The loader rejects absolute paths, traversal, missing files, directories,
malformed JSON, and symlink escapes. Every return value is a defensive copy.

## Validation evidence

Executed from the isolated candidate worktree using the already-provisioned
repository environment (no dependency resolution or lockfile mutation):

- Targeted Harness: `pytest tests/conformance_harness -q` — `27 passed`.
- Full pytest: `pytest -q` — `490 passed`, one existing
  Starlette/httpx deprecation warning.
- Ruff lint: `ruff check .` — passed.
- Ruff format: `ruff format --check .` — `96 files already formatted`.
- Frontend lint: `npm run lint` — passed.
- Frontend build: `npm run build` — passed; Vite transformed 38 modules.
- Repository gate: `make check` with the provisioned environment in offline
  mode — passed; Ruff plus `490 passed`, one existing warning.
- Git diff check, changed-path ownership, import direction/cycle, public
  API/CRD/schema, dependency/lockfile, secret-pattern, relative-link, and
  deletion/revert-only rollback audits — passed before candidate commit.

Exact-head reruns, push, Draft PR creation, and PR CI remain required before
Checkpoint A exit.

## Identity and security findings

- Platform Execution Identity remains authoritative across interpreter,
  Provider, Capability, and MVS adapter evidence.
- Agent Instance IDs and native Provider/capability request IDs remain distinct
  typed identities. Native IDs are correlation-only.
- No live credentials, network targets, or credential-bearing fixture values
  are used. `synthetic.invalid` and deterministic in-process transports are the
  only Capability evidence.
- Diagnostic redaction is a bounded Harness safeguard, not a production secret
  scanning or governance claim.

## Limitations and Evidence Debt

- This is an internal candidate, not a certification suite or frozen contract.
- PASS covers only the exact current component/profile/version boundary named in
  each row. It does not prove all versions, environments, clouds, providers, or
  production readiness.
- Workflow terminal propagation is explicitly `NOT_APPLICABLE` to the initial
  profile and remains not yet proven here.
- Compatibility Manifest fixtures remain experimental upstream evidence and are
  not converted into tested Harness PASS results.
- OpenClaw, Hermes, Document/File, Product View, Technical View, Golden Demo,
  Alibaba Cloud qualification, and release readiness are not targets and gain
  no support, certification, or acceptance from this candidate.
- Synthetic REST evidence proves deterministic adapter behavior only; it does
  not prove a live external Capability service.
- Exact-head CI and Human review remain mandatory.

## Rollback

Rollback is deletion/revert-only: remove the new `conformance_harness/`,
`tests/conformance_harness/`, and this evidence directory, or revert the single
candidate commit. Production components and configuration require no rollback
because none are modified and no production package imports the Harness.

## Checkpoint state

Candidate result: `PASS_WITH_CONSTRAINTS`, contingent on exact-head local gates,
Draft PR CI, and Human review. This does not close the Session. The next action
is delivery of the isolated Draft PR followed by the Human S5-TEST-005
Conformance Harness Review Gate.

## Checkpoint B — safety and evidence convergence

### Provenance

- Checkpoint: `B — CONFORMANCE_HARNESS_SAFETY_CONVERGENCE_AND_EXIT_CANDIDATE`
- Checkpoint A head: `7686ee43498d9da82c5e20557665029f6b2ea261`
- Checkpoint B final head: the correction commit containing this section,
  resolved by `git rev-parse HEAD` and recorded exactly by Draft PR #58; a Git
  commit cannot embed its own content-addressed SHA.
- Baseline remains `df76e0b36dcb42c12e25852a04fd0086dac987a8`.
- Worktree, branch and PR remain the Checkpoint A worktree,
  `codex/s5-test-005-conformance-harness`, and Draft PR #58.
- No child Agent, parallel writer, competing PR or downstream Product View,
  Technical View, Golden Demo or release PR was active at preflight.

### Problems identified and bounded corrections

Checkpoint A kept classification inside `Evidence`, allowed inconsistent result
objects to be constructed directly, had no explicit manifest/fixture resource
bounds, accepted arbitrary fixture suffixes and credential-shaped content, and
used the repository root (`.`) on pytest's import path. Checkpoint B:

- separates typed `Disposition` and `EvidenceClassification` on every result;
- cross-validates result, manifest and supporting-evidence classifications;
- requires each PASS evidence record to identify criterion ID and deterministic
  execution provenance;
- limits PASS authority to completed `TESTED` or `SUPPORTED_CANDIDATE` evidence;
- rejects contradictory results, duplicate report criteria and unreconciled
  summaries;
- adds manifest limits of 256 KiB, 256 criteria and 32 nesting levels;
- adds fixture limits of 64 KiB and 32 nesting levels, JSON-only suffixes,
  duplicate-key and duplicate-identity rejection, finite-number enforcement,
  symlink confinement and credential-shape rejection;
- avoids stringifying unsupported hostile exception objects, redacts sensitive
  diagnostics and unrelated host paths, and caps diagnostics at 240 characters;
- deep-freezes evidence observations and emits deterministic compact, sorted
  JSON bytes for replay comparison; and
- moves the internal package under `conformance_harness/src/conformance_harness`
  so pytest imports only `conformance_harness/src`, not the repository root.

### Result versus evidence model

Disposition answers whether a criterion ran and satisfied its assertion.
Evidence classification answers the authority and maturity of evidence. They
are separate enum fields. Construction fails when evidence identifies another
criterion or classification, PASS lacks completed evidence, a non-PASS carries
completed pass evidence, results duplicate a criterion, or summary arithmetic
differs from individual results.

`NOT_APPLICABLE` does not automatically mean `NOT_YET_PROVEN`. The Workflow row
has both only because the manifest explicitly records
`evidence_classification=NOT_YET_PROVEN` while profile evaluation independently
produces `disposition=NOT_APPLICABLE`. Neither it nor UNRUN contributes to PASS.

### Exact six-criterion proof matrix

| Criterion | Disposition | Evidence classification | Completed proof and exact boundary |
| --- | --- | --- | --- |
| `A2-IDENTITY-001` | `PASS` | `TESTED` | Current-head in-process execution proves deterministic identity recovery and native-correlation separation for A2 / `internal-v0.2-candidate` / `v0.2`. |
| `A3-COMPAT-001` | `PASS` | `TESTED` | Current-head in-process execution runs the interpreter twice and proves equal envelopes plus unchanged caller data for `legacy-task-v0.2-candidate` / `v0.2`. |
| `B-NATIVE-001` | `PASS` | `SUPPORTED_CANDIDATE` | Current-head deterministic mock execution proves the exact Native requested/effective target and correlation-only native invocation ID for `native-provider-v0.2-candidate`. |
| `C-GATEWAY-001` | `PASS` | `TESTED` | Current-head synthetic REST execution proves equal repeated outcomes and preserved Platform Execution Identity for `capability-gateway-v0.2-candidate`. |
| `E-MVS-001` | `PASS` | `SUPPORTED_CANDIDATE` | Current-head Native plus synthetic REST execution completes Runtime and Capability outcomes under the same Platform identity for `v0.2-candidate`. |
| `E-WORKFLOW-OPTIONAL-001` | `NOT_APPLICABLE` | `NOT_YET_PROVEN` | No adapter runs under `mvs-native`; no evidence is fabricated and no PASS is counted. |

Arithmetic remains total `6` = PASS `5` + FAIL `0` + UNRUN `0` +
NOT_APPLICABLE `1`.

### Determinism and isolation evidence

- Selection and result ordering are sorted by criterion ID; duplicate manifest
  and selection IDs fail before execution.
- Repeated runs produce equal immutable reports and byte-identical normalized
  JSON records.
- Adapter registries are copied per runner. One caller or runner cannot mutate
  another runner's registry, counters or summary.
- A failed criterion records bounded FAIL while the next independent criterion
  still runs and records its own result.
- Manifest input, fixture content, adapter caller data and nested evidence are
  defensively copied; evidence mappings and nested sequences are immutable.
- No clock, repository, global counter, mutable singleton or nondeterministic ID
  source is used by the Harness.

### Pytest discovery boundary

`pyproject.toml` adds only `conformance_harness/src` to pytest `pythonpath`.
Existing explicit `testpaths` remain unchanged. Virtual environments, temporary
directories, build outputs, fixtures and evidence directories therefore are not
added to test collection. No project dependency, version, package metadata,
build backend or lockfile changes.

### Checkpoint B validation

- `uv run pytest tests/conformance_harness -q`: `57 passed`.
- Targeted A2/A3/Native/Capability/MVS component regressions: `189 passed`.
- `make check`, using the provisioned environment offline: Ruff passed; full
  pytest `520 passed`, with one existing Starlette/httpx warning.
- `npm run lint`: passed.
- `npm run build`: passed; Vite transformed 38 modules.
- Manifest/fixture bound tests, hostile diagnostic tests, import ownership,
  arithmetic, deterministic serialization and state isolation tests: passed.
- Exact changed-path, import/cycle, production-import, public API/CRD/schema,
  dependency/lockfile, secret/redaction, relative-link, rollback and Git diff
  audits are rerun before the Checkpoint B commit.
- Exact-final-head GitHub Quality and Frontend Quality Gates remain required
  after push.

### Explicit non-promotion boundary

- Executable Harness: `INTERNAL_TEST_CANDIDATE`
- Component certification: `NOT_GRANTED`
- Provider certification: `NOT_GRANTED`
- Production readiness: `NOT_GRANTED`
- Release acceptance: `NOT_GRANTED`
- Contract freeze / schema freeze: `NO / NO`
- Product MVS: `NOT_COMPLETE`
- Golden Demo: `NOT_IMPLEMENTED_BY_THIS_SESSION`
- OpenClaw / Hermes support: `NOT_GRANTED_BY_THIS_SESSION`

### Remaining Evidence Debt and rollback

The Harness does not prove live external Capability services, Workflow terminal
propagation, external runtimes, all versions/environments, production security,
certification, readiness or release acceptance. Human review and separately
authorized durable integration remain required.

Rollback remains deletion/revert-only. Reverting the Checkpoint B correction
returns exactly to Checkpoint A; reverting the complete PR removes only the
Harness, tests/evidence and test-discovery entry. No production rollback or
migration exists because production semantics and state are unchanged.
