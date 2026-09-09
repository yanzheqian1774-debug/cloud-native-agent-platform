# S5-V023-IMPL-310 — Digital Employee work participation

Status: `OPEN / G1 / PARTIAL_DRAFT`

## Fixed object and parallel ownership

- Base/source: `f189212232fc194859a695f0307e83b0c7b73c0f`.
- Base tree: `a8a9251d5d2e47605d18bb63e362164ec4c920d2`.
- Branch: `codex/s5-v023-impl-310-digital-employee-work-participation`.
- Worktree: `/Users/tristan/.codex/worktrees/23a9/cloud-native-agent-platform`.
- Remote `main` matched the fixed source when the Session was opened.
- IMPL-305 owns Workbench BFF, browser session/grant, owner authorization and
  shared startup wiring. IMPL-308 owns the verified Model foundation. This task
  does not edit either path set, migrations 0001-0018, `app.py`, bootstrap,
  supervisor, or owner PostgreSQL wiring.

## Bounded fact map

| User question | Product location | Formal owner/port | Current fact | Gap kept open |
|---|---|---|---|---|
| Who is this employee and what is it responsible for? | Definition profile | Digital Employee Definition exact/list reads; Agent Definition exact read | Employee `role` and `responsibilities`; exact Agent `name`, `title`, `businessPurpose`, `duties`, `capabilities` | Employee Definition has no display-name field; Agent text is not HR job authority |
| Which capabilities and resources are configured? | Definition profile and exact-member list | Digital Employee Definition composition | One exact Agent and exact Workflow/Skill/MCP/Knowledge/Runtime Profile members | A configured or bound resource does not prove actual use |
| Which persistent employee is selected? | Instance panel | Digital Employee Instance exact read | Exact published Definition revision/digest, owner, organization and lifecycle | No Instance list port or complete lifecycle UI |
| What work was assigned? | Assignment panel | Assignment exact read under an Instance | Exact Assignment/Instance relation, assignee, business role, lifecycle and effective interval | No Assignment list and no Plan binding in this projection |
| Where is the work placed? | Work participation panel | Placement exact read with Assignment, Attempt and Agent Instance read context | Placement decision, Runtime Instance, policy, compatibility, freshness when projected | No complete work history; exact read only |
| Did work actually run and finish? | Work participation panel | Governed execution / Resource Use owners | Current Placement projection explicitly reports execution and Outcome unavailable when absent | Safe browser BFF and general execution projection remain with IMPL-305/follow-up |
| What Evidence may be inspected? | Work participation details/navigation | Independently authorized execution/Evidence owner | Only exact references may be carried across views | A reference is not permission to read content; Placement exposes no Evidence references |

Agent `name`, `content.title`, `businessPurpose`, `duties`, and `capabilities`
remain Agent Definition facts. They are rendered with explicit source labels and
are never copied into the Digital Employee Definition authority. Digital Employee
Definition owns only its exact identity, `role`, `responsibilities`, predecessor,
exact composition, lifecycle decision facts, publication and matching state.

## G1 implementation plan

1. Extend the existing Digital Employee frontend client only for already-present
   exact-read ports and abortable reads. Do not add a new HTTP endpoint or browser
   identity mechanism.
2. Add a profile component that resolves the exact primary Agent revision and
   distinguishes Employee-owned fields from Agent-sourced descriptive fields.
3. Add an exact-read work participation component for Instance, Assignment and
   Placement. Persist only known identities in the URL; always read authoritative
   state again after refresh. Guard object switches and late responses.
4. Present configured, bound, assigned, placed/observed, executed and terminal
   states separately. Unknown or unavailable facts remain unknown/unavailable.
5. Provide navigation carrying exact identifiers to existing technical/Evidence
   surfaces, while disclosing that protected contents still require independent
   authorization and IMPL-305 BFF wiring.
6. Add source-level and component/browser-focused tests for provenance, exact-read
   coverage, scope/error handling, late-response protection, refresh recovery,
   keyboard semantics and narrow-screen layout.

## Compatibility and risk

This is a bounded Product projection over current private HTTP DTOs. It changes
no CRD, database schema, frozen Contract, execution state machine, Runtime
lifecycle, authorization semantics or source of truth. The main risk is accidental
inference from configuration to operation; labels and tests therefore preserve
each state boundary. A second risk is treating URL or browser state as authority;
URL values are used only as exact read coordinates and never as work-state facts.

## Delivery boundary

Formal browser authorization and shared route registration remain outside this
branch until IMPL-305 releases those paths. Component tests or intercepted browser
responses are adapter evidence, not a real-service product journey. This Session
must remain `PARTIAL_DRAFT` until the formal BFF path is integrated and verified.

## Recoverable checkpoint

Implemented paths:

- `console/frontend/src/api/digitalEmployees.ts`: abortable Instance and
  Assignment exact reads plus the existing Placement exact-read route contract.
- `console/frontend/src/digital-employees/EmployeeProfile.tsx`: Employee-owned
  profile fields, exact Agent revision resolution, Agent-sourced duties and
  capabilities, and exact resource links.
- `console/frontend/src/digital-employees/EmployeeWorkParticipation.tsx`:
  read-only configured/bound/assigned/placed/execution/terminal projection,
  Runtime identity/freshness, and execution/Evidence navigation.
- `console/frontend/src/digital-employees/DigitalEmployeesPage.tsx`: clear
  Definition/Instance/Assignment navigation, exact identity refresh recovery,
  authoritative readback and late-response protection.
- `console/frontend/src/styles/resource-management.css`: page-scoped layout and
  narrow-screen behavior; no shared global design authority was changed.
- `console/frontend/tests/test_s5_v023_impl_310_digital_employee_work.py` and
  `console/frontend/tests/e2e/digital-employee-work-participation.spec.ts`:
  provenance/boundary source checks and explicitly mocked `TEST_ADAPTER` browser
  coverage.

Validation at this checkpoint:

- Frontend lint: passed.
- Frontend production build: passed.
- Targeted frontend/backend tests: `15 passed` with one existing Starlette
  deprecation warning.
- Mocked Playwright component journey: `3 passed`, including reload readback,
  delayed-response isolation, denied-read redaction and 390 px overflow coverage.
- `git diff --check`: passed.
- Real PostgreSQL adapter validation was attempted with a task-owned
  `s5-310-postgres` container on `127.0.0.1:57310`. The first connection arrived
  before initialization completed; the retry stalled with the local Docker
  control path. The task-owned test process was stopped and the container was
  removed. This is not recorded as a real-service pass.

Read-only parallel path inventory:

- IMPL-305 currently owns
  `console/backend/src/agent_console/authority_contracts.py`,
  `authority_postgres.py`, `grant_administration_application.py`,
  `workbench_bff.py`, `workbench_bff_schemas.py`,
  `workbench_owner_authorization.py`, its two Workbench authorization/BFF tests,
  and `docs/engineering/S5-V023-IMPL-305-TRUSTED-WORKBENCH-BFF.md`.
- IMPL-308 currently contributes
  `docs/engineering/S5-V023-IMPL-308-P1-VERIFIED-MODEL-FOUNDATION.md`; its planned
  resolver/tests remain separately owned.
- The implementation path intersection with both inventories is empty.

Unique next step: after IMPL-305 releases the shared BFF surface, register an
independently authorized read projection for governed execution/Runtime and
Evidence references, then replace the browser `TEST_ADAPTER` with a real-service
journey. Do not add a second state store or infer Evidence permission from a
Placement reference.
