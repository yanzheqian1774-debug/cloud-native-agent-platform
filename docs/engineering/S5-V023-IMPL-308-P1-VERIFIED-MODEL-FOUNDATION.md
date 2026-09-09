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

Focused tests cover exact success/readback, authorization subject/scope/binding
mismatch, resolved scope/identity/revision/digest mismatch,
unpublished/disabled/unavailable configuration, absent authority or resolver,
authorization-before-lookup, denial nondisclosure, and no implicit selection.
Provider Evidence is excluded because no formal source contract exists.
Repository quality gates follow after the focused suite.

## Contract recheck and bounded implementation

The post-checkpoint source/decision recheck found no current formal Model owner
for identity, revision, digest, or secret-free configuration readback. The
Model Definition and immutable Revision catalog remains v0.2.4 product/roadmap
direction. Accepted ADR-0005 defines future platform-level Model abstractions,
but records the runtime-local provider interface and embedded Agent model
configuration as partial implementation with known architecture drift.

The existing authority foundation accepts exact owner/action/resource grants,
but no accepted Model-specific owner, action, or resource encoding exists.
Therefore this task does not mint `USE_MODEL`, `READ_MODEL`, or equivalent
authorization semantics. The injected authorization port returns an opaque
decision bound to the current subject, scope, and exact requested binding; a
future authorized composition owner must adapt its accepted vocabulary.

Existing Execution Evidence records execution-scoped provider correlation and
call count, but do not define provider-connection or model-invocation Evidence
bound to an exact Model identity/revision/digest, including health freshness.
No Evidence reader, verification-state system, or provider probe is added.

The bounded implementation is isolated to:

- `console/backend/src/agent_console/model_binding_resolution.py`
- `console/backend/tests/test_model_binding_resolution.py`

It provides internal typed values and injected authorization/resolution ports,
then enforces authorization before lookup, exact scope/identity/revision/digest
matching, published/enabled/configuration-available checks, and fail-closed
absence/denial. It exposes no default/list/display-name resolution path and
contains no credentials, persistence, external call, or shared consumer wiring.

Validation on the implementation worktree:

- focused: `18 passed`;
- repository `make check`: Ruff lint and format checks passed, then
  `1601 passed, 134 skipped` (the skips require separately provisioned external
  services or environments).

## Current delivery state

`PARTIAL_DRAFT`: the independent contract-preparation module and test fakes are
implemented. They are not a formal Model owner, production authorization
adapter, or provider Evidence source. Agent, Digital Employee, Runtime, 305 BFF
and browser wiring remain explicit follow-up work until path ownership, a
formal Model owner, accepted authorization semantics, and Evidence contracts
are available.

The minimum implementable contract decision candidate is recorded at
`architecture/s5/v0.2/S5-V023-IMPL-308-P1-VERIFIED-MODEL-CONTRACT-CANDIDATE-V1.md`.
Its status is `PROPOSED / NOT_ACCEPTED / NOT_FROZEN`; it does not authorize the
production, persistence, authority, Evidence, or shared-consumer changes it
recommends.
