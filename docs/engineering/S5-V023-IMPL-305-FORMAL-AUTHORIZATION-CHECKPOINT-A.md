# S5-V023-IMPL-305 Formal Authorization Checkpoint A

Status: `G1_PLAN_COMPLETE / IMPLEMENTATION_AUTHORIZED / SESSION_OPEN`

This checkpoint continues the bounded IMPL-305 backend task from source
`1fe09dde452a7aa83f77230832878a39bdb4322b` and tree
`440fcd3f38cfd9c3d33b3aa2a4ce7c0376844948`. It does not change a public CRD,
the Kubernetes API group, a frozen Contract, the authority model, or a database.
It composes the already implemented direct grant-request path with domain-owned
exact-target validation.

## Action, target, disclosure, and recovery table

| User action | Request and decision actors | Exact grant target | Canonical target proof | Scope and disclosure | Idempotency, CAS, and recovery | Consumer |
| --- | --- | --- | --- | --- | --- | --- |
| Create a Success Criterion | authenticated applicant; independent scoped grant administrator | `SUCCESS_CRITERION CREATE success-criterion:collection` and the existing operation-required `SUCCESS_CRITERION READ success-criterion:collection` | the fixed collection identity is accepted only for the closed CREATE/READ action set | trusted session tenant/security domain; request response discloses only request state/actions | replay the same grant-request key/payload; decision uses request aggregate `expectedVersion` | 299 |
| Revise a Success Criterion | same separation | `SUCCESS_CRITERION REVISE/READ success-criterion:{successCriterionId}` plus predecessor `SUCCESS_CRITERION READ success-criterion:revision:{revisionId}` | an existing criterion row and exact predecessor revision in the trusted scope | unknown and foreign-scope identifiers share the non-disclosing request-not-found result | command result unknown replays the original criterion command; CAS never substitutes another predecessor | 299 |
| Read a new criterion revision | same separation | `SUCCESS_CRITERION READ success-criterion:revision:{revisionId}` | the immutable revision exists in the trusted scope | no automatic READ is minted by CREATE | if CREATE committed but its response is unknown, first replay the original create command; then request the returned exact revision | 299 |
| Create the first Criteria Set for a Problem | same separation | `SUCCESS_CRITERIA_SET CREATE/READ success-criteria-set:{problemId}` plus the operation's existing exact Problem and member-revision READ requirements | the canonical Problem exists in the trusted scope; this is the pre-existing identity rule before a set revision exists | the target is derived from the already known Problem context, not from a hidden set enumeration | preserve the created criterion revision and frozen set command while authorization is pending; replay only the original set command after an unknown result | 299 |
| Revise/read a Criteria Set | same separation | `SUCCESS_CRITERIA_SET REVISE/READ success-criteria-set:{problemId}` plus exact Problem/member reads | the canonical Problem exists in scope; owner validation and the command repository enforce the exact predecessor/member facts | no set, member, or foreign Problem contents are disclosed by grant request status | stale aggregate/predecessor remains a conflict; the client must reread and explicitly choose a new exact base | 299 |
| Create an Employee revision | authenticated applicant; independent scoped grant administrator | existing bootstrap `EMPLOYEE CREATE employee:collection`; no implied object READ | fixed collection identity, closed to CREATE | create result returns the new definition/revision coordinates without members or private facts | unknown result replays the same `commandId` and payload | 310 |
| Validate/approve/publish an Employee revision | same separation; business APPROVE is not grant approval | `EMPLOYEE VALIDATE/APPROVE/PUBLISH employee:{definitionId}:aggregate` | at least one canonical Employee revision for that definition exists in the trusted scope | an unknown or foreign aggregate is not disclosed | grant decision CAS is independent of Employee aggregate CAS; Employee command replays keep the original command/payload | 310 |
| Read the new Employee revision | same separation | `EMPLOYEE READ employee:{definitionId}:{revisionId}` | the exact immutable Employee revision exists in the trusted scope | CREATE does not grant READ; exact read remains separately authorized | replay the original create before requesting coordinates when create outcome is unknown | 310 |
| Validate an Employee's first Agent member | same separation | `AGENT READ agent:{definitionId}:{revisionId}` | the exact Agent revision exists in the trusted scope; current lifecycle/digest eligibility remains checked by the Employee command | coordinates come from the bounded Agent list/selected exact member, without granting object READ | authorization can be requested before the lifecycle command; a failed member check writes no Employee lifecycle fact | 310 |

Direct requests use the existing `exact-grant-request.v1` body and require an
external immutable authority generation to declare requestability for the chosen
bounded purposes. The first integration uses `WORKBENCH_SUCCESS_CRITERIA` for the
Success Criterion/Criteria Set members and `WORKBENCH_EMPLOYEE_LIFECYCLE` for the
Employee/Agent members. Adding those rules does not add a grant: an independent
current `GRANT_ADMIN / DECIDE / grant-scope:{tenant}:{securityDomain}` decision is
still required, and issuer and subject must differ.

## Files and symbols

Implementation is limited to:

- `business_problem_repository.py` and `PostgresBusinessProblemRepository`:
  add a caller-transaction target-existence port for the two Business Problem
  owned authorization namespaces.
- `agent_definition_repository.py` and `PostgresAgentDefinitionRepository`:
  add exact Agent revision target validation on the caller connection.
- `digital_employee_definition.py` and
  `PostgresEmployeeDefinitionRepository`: add Employee collection, aggregate,
  and exact-revision target validation on the caller connection.
- `workbench_grant_targets.py`: compose the existing creator-continuation
  validator with the three domain target validators without moving owner facts;
  continuation behavior is unchanged.
- `workbench_bootstrap.py`: inject the composed validator into the existing
  authority foundation.
- focused unit, composition, PostgreSQL, and public BFF tests; update the 305
  handoff documentation with the fixed purposes, errors, and recovery sequence.

No public response DTO or operation route is required for resource-coordinate
discovery: collection coordinates are fixed, Criteria Set coordinates derive
from the already selected Problem, and create/list results already return the
definition and revision identifiers needed to construct exact targets.

## Shared consumer plan

The 299 and 310 branches have independently changed shared authority, repository,
bootstrap, BFF, and domain files. Consumers must not copy whole blobs or merge the
entire 305 branch. Their minimum dependency is the semantic target-validation
port and composition plus the existing grant request/decision contracts already
consumed by their fixed candidates. Each consumer must reconcile its own newer
repository and bootstrap changes symbol by symbol.

The 299 closure needs Success Criterion/Criteria Set target rules and the existing
Problem creator continuation. The 310 closure needs Employee aggregate/exact and
Agent exact-revision target rules. Neither dependency makes the other consumer's
frontend or worktree part of IMPL-305.

## Explicit retained gap

The existing component can revoke a grant atomically, and current authorization
checks observe expiry and committed revocation. A public grant-revocation route
is not added here because the current 305 decision record still marks its CAS,
immutable revocation result, and readback DTO as open. Inventing that contract
would exceed this task's instruction not to change an unfrozen authorization
contract. The implementation and tests continue independently for formal request,
decision, exact-target validation, grant use, expiry/current-revocation effect,
and unknown-result recovery.
