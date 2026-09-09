# S5-V023-IMPL-308 — P1 Verified Model Foundation

## Fixed identity

- Base/source commit: `f189212232fc194859a695f0307e83b0c7b73c0f`
- Base tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`
- Entry `origin/main`: `f189212232fc194859a695f0307e83b0c7b73c0f`
- Branch: `codex/s5-v023-impl-308-p1-verified-model-foundation`
- Checkpoint: `BOUNDED_CONTRACT_CHECK_AND_IMPLEMENTATION`

The local and remote task branch names and repository text had no prior 308
occupant at entry. The worktree was detached at the fixed base before the task
branch was created. Git worktree metadata showed no other worktree using the
task branch.

## Bounded contract map

| P1 obligation | Existing owner / port | Current implementation | Exact gap | Bounded modification path |
| --- | --- | --- | --- | --- |
| Resolve exact Model identity and configuration | Future Model domain owns resolution; Agent owns thin desired binding; Runtime only translates | Agent validation returns `UNVERIFIED_OPAQUE_REFERENCE`; runtime selects provider/model from environment | No scope-aware exact revision/digest resolver or typed authoritative readback | Add an internal typed resolution and consumption port; do not add a Model authority, persistence, route or public DTO |
| Prove current subject may use the Model | Existing trusted authorization owners; 305 owns Workbench BFF and authorization wiring | No Model-specific authorized resolver is wired | Authorization must precede lookup and remain separate from identity resolution | Require an injected authorization port and fail closed when absent/denied; leave 305 wiring open |
| Prove provider connection or invocation | Existing runtime/provider adapters | Configured provider/model can invoke, but configuration is not evidence of connection or invocation | No shared evidence contract connects Model resolution to a real provider result | Keep connection and invocation states explicit and independently `NOT_VERIFIED` unless authoritative evidence is supplied; perform no external call in 308 |
| Agent/Runtime typed consumption | Agent binding validator, Digital Employee application, Native Runtime/provider | Model references remain opaque strings or environment fields | Shared consumers cannot truthfully claim authorization or provider verification | Deliver the independent port first; leave shared consumer and browser wiring pending owner confirmation |

## Meaning of verified

The bounded foundation records three independent facts and never infers one
from another:

1. exact Model identity/configuration resolution;
2. authorization of the current subject for that exact identity;
3. provider connection and Model invocation verification.

Identity resolution and authorization are required for a resolved consumption
binding. Provider connection and invocation evidence remain independently
`NOT_VERIFIED`, `VERIFIED`, or `FAILED`. A configured endpoint/profile reference
does not establish either provider state.

## Architecture and compatibility boundary

This is a G1 internal implementation behind the accepted thin Model Binding
boundary. It does not create `ModelDefinition`, a Model repository, a migration,
a public endpoint or schema, routing, fallback, policy selection, credentials,
or complete Model Control V2. Historical opaque references remain untouched and
are not upgraded. The future Model authority supplies exact identities and
digests; the consumer only validates and reads them.

The durable repository and current remote refs did not contain a readable
`REVIEW-304` artifact, branch, issue or pull request. Therefore 308 does not
infer any additional guarantee from that unavailable review artifact.

## 305 overlap

The committed 305 path list at entry was:

- `console/backend/src/agent_console/authority_contracts.py`
- `console/backend/src/agent_console/authority_postgres.py`
- `console/backend/src/agent_console/grant_administration_application.py`
- `console/backend/src/agent_console/workbench_bff.py`
- `console/backend/src/agent_console/workbench_bff_schemas.py`
- `console/backend/src/agent_console/workbench_owner_authorization.py`
- `console/backend/tests/test_workbench_authorization_postgres.py`
- `console/backend/tests/test_workbench_bff.py`
- `docs/engineering/S5-V023-IMPL-305-TRUSTED-WORKBENCH-BFF.md`

308 will not modify these paths, `app.py`, bootstrap, session/grant modules,
supervisor/listener, migrations or shared CI. Uncommitted 305 paths are not
observable from Git branch metadata and are not assumed free.

## Validation plan

Focused tests cover exact success/readback, revision/digest/provider/profile
mismatch, scope and authorization denial, unpublished/disabled/unavailable
configuration, separated provider evidence, absent authority, and no implicit
selection. Repository quality gates follow after the focused suite.

## Current delivery state

`PARTIAL_DRAFT`: the independent foundation is authorized. Agent, Digital
Employee, Runtime, 305 BFF and browser wiring remain explicit follow-up work
until path ownership and trusted authorization context are available.
