# S5-V023-IMPL-224 Checkpoint A Evidence

## Entry and blocker verification

- Human-authorized allocation `S5-V023-IMPL-224` was globally unused across repository content/history, local and remote refs, tags, worktrees, GitHub PRs/issues, and visible Codex tasks before mutation.
- Baseline commit `9a0e9b50b7d47a055ac2df3879f1b02224d9d966`, tree `a1ee033300ffe6a099378d249a947b52fbf5e0b4`, and exact-main CI `33748191196 / push / attempt 1 / SUCCESS` matched the authorization.
- Migrations `0008`-`0010` were not edited. Their entry SHA-256 values were respectively `3712ceaaa22262e1597befaa5402f1ba9be8207d670356e61cdcb906b132f252`, `159135dc0e8e8005963501703f3ede0a9ad6d6ea08218b7e3212839d5232cd12`, and `c6c98d583e1d10e6783d42a128d56fb1545e8c90c14c726018049c6a61240c54`.
- The two IMPL-240 blockers were reproduced: no atomic successor-Plan correction operation existed, and the extended Unit of Work linked only pre-existing Evidence/Outcome identities.
- Open PRs #136 and #138 target only `release/v0.2.2-maintenance`; active IMPL-223 owns API/bootstrap paths. No authorized IMPL-224 path overlaps them.

## Complete application-command persistence matrix

Every row is authorized before disclosure, scoped by namespace and security domain, claims `(scope, actor, command type, idempotency key)` with a digest over the complete normalized operation, uses explicit expected aggregate versions, creates minimum-disclosure Evidence inside the transaction, stores a typed deterministic result, and rolls back the entire transaction on any failed write or readback.

| IMPL-240 command | Exact input and precondition | Created / transitioned | Outcome | Successor |
| --- | --- | --- | --- | --- |
| `APPROVE_AND_CONTINUE` | exact Plan identity/version/digest; expected paused Run version; `PENDING_APPROVAL` | approval decision, Evidence, command, replay result; Plan→`APPROVED`, Run→`RESUME_REQUESTED` | forbidden | none |
| `REJECT_PLAN` | exact Plan identity/version/digest and target version; `PENDING_APPROVAL` | rejection decision, Evidence, command, replay result; Plan→`REJECTED` | forbidden | none |
| `CORRECT_PLAN` | exact source Plan identity/version/digest and Plan CAS; correctable source | immutable successor Plan, exact lineage, correction fact, Evidence, command, replay result; predecessor→`SUPERSEDED` without content rewrite | forbidden | Plan, mandatory |
| `REQUEST_INTERVENTION` | exact scoped eligible target and expected version | request fact, `REQUESTED` transition, Evidence, command, replay result | forbidden | none |
| `REVIEW_INTERVENTION` | exact `REQUESTED` intervention and unchanged target version | immutable review, Evidence, command, replay result | forbidden | none |
| `APPLY_INTERVENTION_DECISION` | exact review/decision, `REQUESTED`; authorized decision and valid target edge | decision plus `AUTHORIZED`, `APPLICATION_PENDING`, `APPLIED` transitions, guarded target CAS, Evidence, command, replay result | forbidden | optional only when the selected intervention operation requires one |
| `RETRY_ATTEMPT` | exact failed Attempt and expected version | Evidence, command, replay result | forbidden | next-ordinal Attempt with exact predecessor, mandatory |
| `CREATE_SUCCESSOR_RUN` | exact terminal Run and exact still-approved Plan binding | Evidence, command, replay result | forbidden | Run with exact predecessor and approved Plan binding, mandatory |
| `REPLACE_RUNTIME` | exact affected Attempt, eligible scoped Placement, matching Runtime desired command, expected version | explicit Attempt/Placement/Runtime-command relations, Evidence, control command, replay result | forbidden | none; Placement is immutable |
| `CANCEL_CONTROLLED_EXECUTION` | exact nonterminal Run/Task Run/Attempt and expected version | guarded target→`CANCELLATION_PENDING`, Evidence, command, replay result | forbidden | none |
| `COMPLETE_EXECUTION_WITH_OUTCOME` | exact nonterminal Run/Task Run/Attempt, expected version, actual allowed terminal state | guarded terminal transition, exact-target Outcome, completion Evidence, command, replay result | exactly one, mandatory | none |

There is no unsupported enum member outside this matrix. Outcome creation is rejected for every operation except `COMPLETE_EXECUTION_WITH_OUTCOME`, and that operation rejects absent Evidence, absent/multiple Outcome, nonterminal states, already-terminal targets, or mismatched exact target/result identities.

## Migration and semantics

Migration `0011_workflow_control_plan_evidence_outcome.sql` is required. It adds successor Plan provenance and closed correction facts; makes Evidence/Outcome links identify the exact control command rather than only a transition; and adds checked Outcome bindings for the exact terminal Run, Task Run, or Attempt. Existing rows retain their identities and content.

The successor Plan has a new identity, exact predecessor composite identity, deterministic one-successor constraint, immutable source revision/digest, new revision/digest/canonical bytes, scoped actor and closed authority/reason classifications, positive CAS version, and deterministic lineage readback. The predecessor's business bytes and digest are never updated.

Evidence and terminal Outcome records are inserted before their exact-operation links and command result are committed. Evidence rejects keys associated with prompts, credentials, request bodies, logs, unrestricted diagnostics, secrets, or tokens. A failure at Evidence, Outcome, relation, command, result, claim completion, or readback rolls back target/Plan transitions and every newly inserted fact.

## Scope

Only migration `0011`, Workflow Control domain/repository adapter, focused tests, and this bounded Evidence document are changed. IMPL-240 application code, IMPL-223 API/bootstrap, frontend, Runtime/providers, deployment, CI, migrations `0008`-`0010`, and release paths are untouched.

## Validation

- Focused domain plus PostgreSQL 15 suite: `18 passed` against an isolated `postgres:15-alpine` service, including repeated migration application and restart replay.
- Complete repository `make check`: `1402 passed, 39 skipped`, Ruff lint and Ruff format check passed. PostgreSQL-specific Workflow Control tests are intentionally executed separately with their scoped database URL so older adapter tests can retain their fail-closed newer-schema checks.
- `uv run pre-commit run --all-files`: passed; no files were modified.
- `git diff --check`, exact-path/prohibited-scope audit, migration `0008`-`0010` checksum audit, and bounded credential/secret scan: passed.
