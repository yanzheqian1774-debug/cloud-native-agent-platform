# S5-TEST-001 — RESULT

## 1. Overall

**STOP**

The bounded remediation established real Hermes availability, but the real
model submission returned an HTTP error with no output or usage. The authorized
remediation budget is exhausted. Runtime Contract Candidate v1 is not eligible
for proposal because ED-S5-001 remains open.

## 2. Repository Isolation

- Branch: `codex/s5-test-001-hermes-contract-verification`
- Worktree: `/private/tmp/s5-test-001-hermes-contract-verification`
- Base: `d5c6d998ec3c506323157d8850248a331c4d18d2`
- Production/Core source change: **0**
- Prior Hermes evidence was not modified.
- Prior OpenClaw artifacts were copied into the test directory without
  modifying the source worktree. Checkpoint A and B hashes match the hashes
  recorded in accepted Checkpoint C.

## 3. Runtime Identity

- Hermes: `v0.20.4`
- Distribution: `nousresearch/hermes-agent:v2026.8.18`
- Digest:
  `sha256:22e37bb4ed1b0f50cb6bd991dca7ecacd6c9f29df9b4a20fc989d32bc763ccf6`
- Architecture: Linux arm64 container on Docker Desktop/macOS arm64
- Execution environment: local isolated Docker container and ephemeral
  `/opt/data`
- Version/digest changed from prior evidence: **no**
- OpenClaw evidence identity: `2026.7.1-2 (0790d9f)`, accepted prior real
  Gateway evidence; this test used a recorded native evidence client, not a
  newly started OpenClaw Gateway.

## 4. Candidate v1 Baseline

Candidate v1 from S5-SPIKE-002 Checkpoint C was used unchanged as the
verification target. The experimental Python types are an evidence harness,
not a Contract freeze, ADR, production API, or schema.

## 5. Descriptor Verification

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-D01 | PASS | Descriptor selects logical runtime and Provider without caller branches. |
| AC-D02 | PASS | Hermes version, immutable digest and architecture are recorded; OpenClaw distribution identity remains distinct. |
| AC-D03 | PASS | Interaction and ownership capabilities are declared without native protocol/configuration fields in the caller. |

## 6. Runtime Binding Verification

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-B01 | PASS | Both Providers are selected by registered Binding ID. |
| AC-B02 | PASS | Binding carries Provider/Descriptor/ownership associations and opaque references. |
| AC-B03 | PASS | Provider-native realization data does not enter the generic caller. |
| AC-B04 | PASS | No universal Runtime Instance type is present or needed. |

## 7. Managed Ownership Verification

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-O01 | PASS | Hermes Binding used managed ownership. |
| AC-O02 | PASS | Provider provisioned, observed and cleaned its container realization. |
| AC-O03 | PASS | OpenClaw external ownership uses the same generic boundary with reduced infrastructure visibility. |
| AC-O04 | INCONCLUSIVE | Semantic recovery was gated on positive success and was not run. No restart was called recovery. |

## 8. Observation Verification

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-H01 | PASS | Observations use TRUE/FALSE/UNKNOWN/NOT_APPLICABLE vocabulary. |
| AC-H02 | PASS | `RuntimeAvailable=TRUE` was established by a real Hermes health interaction. |
| AC-H03 | PASS | Managed container state established `InfrastructureAvailable=TRUE`. |
| AC-H04 | PASS | `DependencyReady=UNKNOWN`; health did not overclaim model readiness. |
| AC-H05 | PASS | Protocol evidence remains Provider detail, not a universal condition. |
| AC-H06 | PASS | No `TaskReady` Runtime condition exists. |

## 9. Interaction Verification

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-I01 | PASS | Generic submission and correlation are shared. |
| AC-I02 | PASS | Hermes returns an inline terminal outcome and receives no fake handle. |
| AC-I03 | PASS | OpenClaw retains deferred handle then observe semantics. |
| AC-I04 | PASS | Terminal success/failure categories are generic. |
| AC-I05 | PASS | Runtime identity, Provider identity and latency are normalized. |
| AC-I06 | PASS | Same caller source handles inline and deferred paths without runtime-name branches. |

## 10. Real Kimi E2E

**FAIL**

Bounded attempt sequence:

1. Initial preflight: container exited before health. No request was sent.
2. One diagnosis: exit code 2; pinned CLI rejected legacy `--host`, `--port`
   and `--api-key` arguments.
3. One evidence-supported remediation: use the pinned image's documented
   `API_SERVER_*` environment configuration and `gateway run` entrypoint form.
4. Remediation: real Hermes health succeeded, then submission returned a
   sanitized `HTTPError` in 18 ms. Output was absent and usage was absent.

No further diagnosis, retry or configuration change was attempted.

## 11. Credential Security

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC-S01 | PASS | Existing Secret was accessed read-only by namespace/name/key reference. |
| AC-S02 | PASS | Raw credential was not printed. |
| AC-S03 | PASS | Raw credential is absent from argv; Docker inherits named environment variables. |
| AC-S04 | PASS | Ephemeral `.env` was mode-restricted and removed with temporary state. |
| AC-S05 | PASS | No credential value is stored in code, tests, output snapshots or this report. |

## 12. Negative Dependency Path

**NOT RUN.** The task permits this only after successful positive E2E.

## 13. Semantic Recovery

**NOT RUN.** Positive E2E did not succeed. Process availability after the
startup correction is not claimed as semantic recovery.

## 14. Cross-Runtime Substitutability

**PASS within the two-runtime experimental evidence boundary.**

The same `generic_caller.execute` source exercised:

- Hermes Provider through a real managed Hermes runtime, producing a generic
  inline terminal failure;
- OpenClaw Provider through a recorded native accepted/terminal evidence
  client grounded in accepted real Checkpoint B evidence, producing a generic
  deferred terminal failure.

A newly live OpenClaw Gateway was not required and was not run. This proves
Provider/Contract shape substitutability, not new OpenClaw operational evidence
or production ecosystem support.

## 15. Generic Caller Source Diff

**Zero between runs.** Runtime selection changed only through Provider
registration and Binding ID. Caller source contains no Hermes, Kimi, OpenClaw,
Gateway, profile, session or native run-ID vocabulary.

## 16. Provider Extension Verdict

**PROVEN_FOR_TWO_EXPERIMENTAL_RUNTIMES**

This verdict is limited to Candidate v1 interaction/binding/observation shape.
It is not production ecosystem proof.

## 17. Candidate v1 Contradictions

None established. The failed real completion leaves evidence incomplete; it
does not require changing Candidate v1.

## 18. ED-S5-001

**OPEN**

Evidence: real Hermes became available, but meaningful Kimi output, semantic
SUCCESS, and non-zero usage were not established.

## 19. ED-S5-002

**CLOSED for experimental Contract/Provider evidence**

Evidence: same generic caller, both Provider implementations, no runtime-name
branches, no caller changes between executions, and zero Core changes. The
OpenClaw side reused recorded accepted real native evidence rather than starting
a new Gateway.

## 20. G-S5-RUNTIME-FREEZE-01

| Gate | Result |
| --- | --- |
| Two materially distinct Runtime evidence | PASS |
| Cross-runtime Candidate Human Review | PASS |
| Third-party Managed Runtime Real Model E2E | FAIL |
| Provider substitutability | PASS |
| Freeze Eligibility | **BLOCKED** |

No Contract freeze was performed.

## 21. Acceptance Criteria

| Group | Result |
| --- | --- |
| AC-D01-D03 | PASS |
| AC-B01-B04 | PASS |
| AC-O01-O03 | PASS |
| AC-O04 | INCONCLUSIVE |
| AC-H01-H06 | PASS |
| AC-I01-I06 | PASS |
| AC-M01 | PASS: real Hermes interaction |
| AC-M02 | INCONCLUSIVE: real Kimi interaction not authoritatively established |
| AC-M03 | FAIL: no meaningful output |
| AC-M04 | FAIL: no semantic SUCCESS |
| AC-M05 | FAIL: no non-zero usage/inference evidence |
| AC-M06 | PASS: generic correlation preserved |
| AC-M07 | PASS: runtime/Provider identity and latency captured |
| AC-S01-S05 | PASS |
| AC-X01-X08 | PASS within stated recorded-evidence limitation |

## 22. Validation

- S5-TEST-001 tests: `3 passed`
- Existing Hermes spike tests: `9 passed`
- Copied OpenClaw spike tests: `4 passed`
- Ruff check: passed for S5-TEST-001 Python artifacts
- Ruff format check: passed for S5-TEST-001 Python artifacts
- Repository tests: not required; no repository package was imported or
  modified
- New-artifact whitespace/diff check: passed
- Secret scan: passed
- Skipped live stages are not reported as PASS

## 23. Cleanup

- Positive/remediation containers: removed by Provider cleanup
- Diagnostic container: removed
- Ephemeral `/opt/data` directories and credential file: removed
- Kubernetes Secret: unchanged
- Cleanup verification: passed; no matching container or auxiliary temporary
  directory remains

## 24. Remaining Unknowns

- Exact HTTP failure classification after real Hermes availability
- Whether the request reached Kimi
- Successful output and usage fidelity
- Negative dependency semantics after a successful baseline
- Semantic recovery after restoring the authorized model Binding
- Newly live OpenClaw substitutability in this session

## 25. Human Decisions Required

Decide whether to authorize a new bounded evidence task to diagnose the HTTP
failure. This task's remediation budget must not be extended retroactively.

## 26. Recommendation

**MORE_EVIDENCE_REQUIRED**

Stop after this report. Do not freeze the Runtime Contract, edit ADRs, start
S5-DEV, start S5-SPIKE-003, or automatically start a Runtime Contract Proposal.
