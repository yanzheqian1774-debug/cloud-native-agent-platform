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

- `conformance_harness/__init__.py`
- `conformance_harness/adapters.py`
- `conformance_harness/fixtures.py`
- `conformance_harness/manifest.py`
- `conformance_harness/models.py`
- `conformance_harness/runner.py`
- `conformance_harness/fixtures/criteria.json`
- `conformance_harness/fixtures/capability_request.json`
- `tests/conformance_harness/test_adapters.py`
- `tests/conformance_harness/test_fixtures.py`
- `tests/conformance_harness/test_manifest.py`
- `tests/conformance_harness/test_runner.py`
- `tests/conformance_harness/test_targets.py`
- `docs/evidence/s5/v0.2/s5-test-005/README.md`
- `pyproject.toml` (adds only `.` to pytest test discovery)

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
