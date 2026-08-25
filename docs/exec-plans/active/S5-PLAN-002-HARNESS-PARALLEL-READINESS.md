# S5-PLAN-002 — Harness & Parallel Delivery Readiness Plan

## 1. Session identity and authority

| Field | Value |
| --- | --- |
| Session | `S5-PLAN-002` |
| Title | Harness & Parallel Delivery Readiness Plan |
| Type | `PLAN` |
| Version | v0.2 CONNECT — Digital Employee Technical Preview |
| Checkpoint | B — Parallel Readiness Convergence and Pilot Candidate |
| Lifecycle / authorization | `CLOSING / AUTHORIZED` |
| Source | `S5-REL-017` — closed; reopening prohibited |
| Baseline | `7c1bc0266b39c913497fd67dcd4b7783f288dc57` |
| Branch | `codex/s5-plan-002-harness-parallel-readiness` |
| Human gate | S5-PLAN-002 Close Confirmation |

This Session owns planning and repository-native planning metadata only. It
does not authorize a pilot, Harness implementation, production or test changes,
parallel Agent execution, downstream Session activation, certification,
production readiness, Contract/Schema freeze, or release acceptance.

## 2. Current v0.2 baseline and project state

The authorized baseline is the durable-main merge of PR #55. It includes the
bounded MVS execution path and its safety tests. Source and tests remain the
authority for current behavior; accepted architecture remains the authority
for architecture. The Governance Registry and Project State contain metadata
lag for several later Sessions, so absence from those summaries is not proof
that work did not occur. This plan does not repair unrelated historical rows.

`S5-REL-017` is `CLOSED / COMPLETED / PASS_WITH_CONSTRAINTS / SESSION_CLOSED`.
It is provenance only and is not reopened or repurposed.

## 3. Historical Harness evidence

The historical architecture describes an Enterprise Research & Engineering
Team with seven logical roles. Current repository manifests contain four
executable engineering Agents and two four-node workflow examples. Controller
tests cover DAG scheduling, parallel runnable nodes, dependency failure and
timeout propagation, skipped descendants, and final aggregation. Hermes
evidence distinguishes container, Gateway, API, dependency, and task health;
it records stopped/unavailable Gateway behavior and authentication/model
failures. Historical evidence is input, not an automatic current claim.

## 4. Current executable role inventory

| Logical role | Repository state | Pilot representation |
| --- | --- | --- |
| Orchestrator | No executable Agent manifest; orchestration exists in Workflow/controller behavior | Parent Codex task |
| Researcher | No current executable engineering Agent manifest | Read-only child role if authorized later |
| Architect | Executable Agent and workflow role | Architecture/ownership reviewer |
| Builder | Executable Agent and workflow role | Sole authoritative writer |
| Tester | Executable Agent and workflow role | Test/evidence reviewer |
| Reviewer | Executable Agent and workflow role | Identity/security/replay reviewer specialization |
| Writer | No current executable engineering Agent manifest | Parent assembles durable handoff; future implementation required for an Agent |

The logical pool may retain all seven roles without claiming all seven are
implemented or should run simultaneously.

## 5. Historical-versus-current classification

| Observation | Classification | Basis |
| --- | --- | --- |
| Seven-role reference pool | `HISTORICAL_ONLY` | Superseded historical architecture |
| Architect, Builder, Tester, Reviewer manifests | `CURRENT_AND_VERIFIED` | Current repository manifests/workflows |
| Orchestrator, Researcher, Writer executable Agents | `NOT_FOUND` | No current matching Agent manifests |
| Dependency skip and terminal failure aggregation | `CURRENT_AND_VERIFIED` | Current controller tests |
| Workflow may remain Running after any upstream failure | `SUPERSEDED` as a general claim | Independent active work may remain Running; blocked descendants are skipped and terminal graphs fail |
| Hermes stopped Gateway with running container | `CURRENT_AND_VERIFIED` as recorded evidence | Hermes evidence bundle |
| Hermes readiness/certification | `NOT_YET_PROVEN` | ED-S5-001 and combination-scoped evidence |
| Mac M1 / 16 GB operating limit | `NOT_FOUND` | Not established at this baseline |
| Conversation/task/worktree enforcement | `REQUIRES_REVALIDATION` | Conventions exist; durable automated enforcement does not |

## 6. Readiness risks and contradictions

- A seven-role diagram is not seven executable roles or a concurrency target.
- Copying a task packet is descriptive, not enforcement against duplicates,
  stale branches, shared-path collisions, or late results.
- Container health cannot stand in for Agent, Gateway, dependency, or task
  readiness.
- Current product workflow propagation does not prove Codex parent-child task
  propagation.
- Multiple clean worktrees do not prevent semantic conflicts on shared paths.
- Repository lifecycle summaries can lag durable Git history.
- Long conversations risk losing authority, ownership, and gate context unless
  the state is written durably before rotation.
- Parallel review can reduce elapsed time only if integration and rework do not
  erase the gain.

## 7. Session/Task/Conversation/Worktree routing model

Every routed unit must carry this identity, both in the full task packet and a
durable machine-checkable record:

| Required field | Rule |
| --- | --- |
| Project/version | Exact repository and release objective |
| Logical Session | ID, canonical title, type, and Track |
| Checkpoint | Current authorized checkpoint |
| Parent/child | Parent task ID and unique child task ID |
| Conversation | Exact Codex conversation ID |
| Workspace | Absolute worktree path |
| Git | Branch or detached policy, baseline SHA, authorized head SHA |
| Scope | Exact writable and prohibited paths |
| Ownership | Owner and time-bounded lease |
| Outcome | Expected result |
| Stop Conditions | Exact mandatory stop list and escalation target |
| Gates | Current gate and next Human gate |
| Lifecycle | Current state, lease expiry, and close/reopen state |

One logical writable Session maps to one authoritative conversation, one
branch, one isolated worktree, and one primary PR. Read-only children use clean
detached worktrees or immutable exact heads. Durable enforcement candidates
for later authorization are a task-routing manifest, ownership/lease manifest,
preflight validator, duplicate-Session detector, branch/worktree validator,
shared-path collision detector, parent-child result manifest, and closeout
validator. None is implemented by this plan.

Before dispatch, the parent must query the authoritative Session/task
inventory, branch/worktree ownership, open PR ownership, and active path
leases. A matching active Session or duplicate parent/child routing identity is
a hard stop, not a reusable task. A writable child must prove a clean isolated
worktree, its exact authorized branch and baseline/head ancestry, and exclusive
path ownership before its first write. Read-only reviewers must prove a clean
detached worktree or immutable snapshot. Repeat the preflight before accepting
results; expiry, branch drift, unexpected commits, or a second task with the
same logical Session invalidates the route.

## 8. Authoritative writer model

`AUTHORITATIVE_WRITER_COUNT: EXACTLY_1`. The parent grants one lease over exact
paths to the Builder. Reviewers do not edit, commit, push, resolve conflicts,
or mutate PRs. The writer may not expand scope, delegate its lease, or accept a
review result that targets a different head. Shared-path changes remain
serialized even when prepared in separate worktrees. No child creates a
logical Session, merges, mutates a PR, or performs final acceptance; those
actions remain with the authoritative parent and applicable Human gate.

## 9. Read-only reviewer model

Reviewers receive the same baseline, authorized head, task packet, scope, and
acceptance criteria. They return findings and evidence with exact paths,
commands, result states, and Git provenance. They never become implicit
writers. A reviewer rejection blocks acceptance; it does not authorize the
reviewer to fix the defect. Findings against stale heads are labelled stale
and rerun or explicitly dispositioned.

## 10. Role pool and dynamic activation policy

`ROLE_POOL_SIZE: 7`

`CURRENT_EXECUTABLE_REPOSITORY_ROLES: ARCHITECT / BUILDER / TESTER / REVIEWER`

`HISTORICAL_ONLY_OR_MISSING_ROLES: ORCHESTRATOR / RESEARCHER / WRITER`

`INITIAL_ACTIVE_ROLE_COUNT: 3`

`MAXIMUM_INITIAL_PILOT_ROLE_COUNT: 4`

`AUTHORITATIVE_WRITER_COUNT: EXACTLY_1`

`READ_ONLY_REVIEWER_COUNT: 1_TO_3`

`SEVEN_SIMULTANEOUS_ROLES: NOT_RECOMMENDED_FOR_FIRST_PILOT`

The first pilot starts with exactly three active roles: the parent
Orchestrator, one writable Builder, and one read-only Architecture/Ownership
Reviewer. Only after resource preflight may a fourth, read-only combined
Identity/Security/Replay and Test/Evidence Reviewer activate. The general
reviewer allowance is one to three, but the initial pilot maximum is four total
roles and therefore two reviewers. Seven simultaneous workers are not
recommended. Roles activate only for independent, bounded work with explicit
evidence consumers and expire at their result or parent cancellation.

## 11. Shared-file/path ownership matrix

| Scope | Sole writer | Read-only consumers | Rule |
| --- | --- | --- | --- |
| `task_controller.py` | Owning implementation Session | Architecture, test, security reviewers | Serialized |
| `workflow_controller.py` | Owning implementation Session | Architecture, test, evidence reviewers | Serialized |
| `resources.py` | Core/Runtime owner selected by Portfolio handoff | Other Tracks | Serialized on overlap |
| Core identity/representation | Track A owner | B–E | Versioned handoff; no concurrent semantic writer |
| Runtime Provider interfaces | Track B owner | A, C–E | Provider-local writers only after interface gate |
| Capability Gateway interfaces | Track C owner | A, B, D, E | No Runtime bypass |
| Public schemas/CRDs | Separately authorized G2/integration owner | All others | No parallel writer |
| Governance/Portfolio files | Active PLAN or REL owner | All implementation Tracks | One governance writer |
| Shared CI/Harness configuration | Authorized TEST/E owner | Component Sessions | Adapters/results via handoff only |
| Product/Technical shared contracts | Track D backend DTO owner | Track E Technical View | Backend handoff before consumer writes |

## 12. Parallel-safe and serialized work classification

Potentially parallel-safe read-only work includes Golden Demo product design,
architecture review, identity/replay/security review, test/evidence planning,
OpenClaw/Skill/MCP evidence research, and observability/fault-injection
planning. Each must use immutable inputs and return evidence rather than edits.

Serialized or single-owner work includes the three Operator paths named above,
Core identity and representation, Runtime and Capability interfaces, public
schemas/CRDs, governance and Portfolio files, shared CI/Harness configuration,
and shared Product/Technical View contracts. Provider-local or UI-local
writable work can be parallel only in separate worktrees after interfaces and
ownership are fixed and paths do not overlap.

## 13. Failure/timeout/cancellation propagation

Allowed orchestration states are `PENDING`, `ACTIVE`, `BLOCKED`, `STOPPED`,
`FAILED`, `SKIPPED`, `COMPLETED`, and `CLOSED`.

| Event | Deterministic disposition |
| --- | --- |
| Builder failure | Writer becomes `FAILED`; dependent acceptance/integration becomes `BLOCKED`; reviewers may finish read-only evidence but cannot promote PASS |
| Tester failure/timeout | Test result becomes `FAILED`; timeout is never PASS; dependent gate is `BLOCKED` |
| Reviewer rejection | Review is `COMPLETED` with rejection; parent gate becomes `BLOCKED` pending writer rework and exact-head rereview |
| Parent cancellation | Active children receive cancellation; pending children become `SKIPPED`; parent becomes `STOPPED` after acknowledgements or recorded timeout |
| Child cancellation | Child becomes `STOPPED`; required dependent work becomes `BLOCKED`; optional work is explicitly dispositioned |
| Worktree drift/branch mismatch | Affected unit stops before writes; evidence becomes invalid until exact provenance is restored |
| Shared-path collision | Both conflicting write routes stop; Human selects one owner or serial order |
| Context loss | Stop mutation; reconstruct from durable handoff and Git, then revalidate routing |
| Gateway unavailable | Runtime-dependent work is `BLOCKED` or `FAILED` by deadline; never infer task success |
| Container healthy, Agent/Gateway not ready | Runtime is not ready; invocation is prohibited or fails explicitly |
| Missing/incomplete evidence | Result is `BLOCKED` or `FAILED`, never PASS |
| Unknown outcome | Preserve `UNKNOWN` in evidence and block dependent acceptance; never coerce it to success |
| Late result after parent closure | Quarantine as late evidence; do not mutate or reopen the closed parent |

No failed, timed-out, cancelled, skipped, unrun, unknown, or stale-head result
may be counted as PASS.

## 14. Parent-child evidence collection

The parent owns the acceptance ledger. Every child returns its routing ID,
role, input baseline/head, completion state, commands or inspection method,
findings, artifacts, limitations, and observed head. The parent checks identity,
scope, freshness, and required-result completeness before acceptance. Conflicts
are recorded rather than silently reconciled. Only the parent can assemble the
candidate and present it to the Human gate.

## 15. Human gate and stop-condition model

Human approval is required for pilot activation, ownership expansion, a second
writer, scope or path expansion, architecture/public-interface decisions,
merge, claim promotion, Session closure, and downstream activation. Stop on
identity conflict, repository/origin drift, dirty/shared worktree, duplicate
Session, ownership collision, unexpected commits or paths, architecture
redefinition, ambiguous downstream identity/sequencing, required production,
test, or Harness changes outside the active scope, or implied readiness,
certification, freeze, or release claims.

## 16. Conversation-length and context-continuity model

Rotate a conversation before context compaction threatens faithful recovery,
when the checkpoint changes materially, or when a fresh owner is authorized.
Before rotation, commit or otherwise durably record the canonical current-state
summary, accepted decisions, open risks and Evidence Debt, exact Git provenance,
active ownership/leases, current checkpoint, results, and next Human gate. The
handoff also records repository/PR state, exact tests and CI state, and all
explicit reopen prohibitions. The new conversation must verify that record
before acting. Conversational memory alone is never authority. Human-confirmed post-merge state may be forward-
imported by a later authorized Session with exact provenance; the closed Session
is never reopened.

## 17. Durable handoff artifact specification

A handoff must contain: Session/routing identity; objective and acceptance
criteria; baseline, authorized head, branch/worktree/PR; lifecycle and gate;
owned/read-only/prohibited paths; accepted decisions; completed validation with
exact results; unresolved findings and Evidence Debt; child-result ledger;
changed-path inventory; rollback; next action; and expiry/closure state. It must
be repository-native or attached to immutable Git/PR provenance and readable
without the originating conversation.

## 18. Resource and concurrency limits

Start with at most three concurrent active workers, including the parent.
Increase to four only after measuring memory/CPU pressure, tool contention,
review latency, and clean cancellation on the actual machine. Use one writer
and one or two read-only reviewers; serialize the optional third reviewer if
capacity is uncertain. Reduce concurrency after resource saturation, repeated
timeouts, queueing that erases wall-clock gain, or more than one context-loss or
routing incident. The historical Mac M1 / 16 GB constraint is unverified and
must be measured rather than assumed.

## 19. Pilot design

`PILOT_EXECUTION: NOT_AUTHORIZED`.

| Field | Candidate |
| --- | --- |
| Objective | Produce one synthetic routing and evidence closeout artifact while independent reviewers assess ownership, security/replay, and evidence completeness; compare with a serial rehearsal using the same packet |
| Pilot Session type | `TEST`, because the primary deliverable is orchestration/evidence validation rather than product behavior |
| Parent Session | A new Human-allocated `TEST` Session, with S5-PLAN-002 as predecessor and governance handoff; exact ID is intentionally unassigned |
| Predecessors | Closed S5-PLAN-002 after Human Close Confirmation; closed S5-REL-017 is inherited provenance only and is never reopened |
| Selection state | `HUMAN_PILOT_SELECTION_GATE_REQUIRED`; no Pilot Session is created or activated by this plan |
| Roles | Initial 3: parent Orchestrator, sole writable Builder, read-only Architecture/Ownership Reviewer; optionally add one combined Identity/Security/Test reviewer or split within maximum 4 |
| Writer | Exactly one Builder |
| Read-only packages | Architecture/ownership; identity/security/replay; test/evidence, serialized if capacity requires |
| Writable paths | Sole writer: `docs/evidence/s5/v0.2/s5-plan-002/pilot/README.md`; all other repository paths read-only |
| Baseline | `7c1bc0266b39c913497fd67dcd4b7783f288dc57`, unless a later Human gate explicitly authorizes a new exact durable-main baseline |
| Duration | Maximum 60 minutes from dispatch to collected child results, followed by exact-head validation |
| Success | No collision/duplicate/routing/context-loss incident; all required child states known; final tests pass; quality does not regress; wall-clock improves against a comparable baseline |
| Failure | Any stop condition, unknown child, escaped defect, unresolved rejection, failed required gate, or rework/latency that removes benefit |
| Rollback | Stop children, preserve evidence, abandon unmerged pilot branch or revert only through a separately reviewed change |
| Human gates | Pilot ID and baseline allocation; Pilot authorization; any scope/ownership change; merge; result/acceleration claim |

The pilot should avoid public schemas, CRDs, governance files, shared Harness
configuration, and cross-Track interface ownership.

## 20. Speed, stability, and quality metrics

Capture the same definitions for a comparable serial baseline and the pilot:

| Dimension | Measures |
| --- | --- |
| Speed | Wall-clock duration; active compute duration; blocked/wait duration; reviewer latency; test/CI latency |
| Rework | Writer rework count; repeated review rounds; reverted changes |
| Coordination | Merge conflicts; path collisions; duplicate tasks; routing errors; context-loss incidents |
| Quality | Escaped defects; reviewer severity/count; failed or unknown child states; final targeted/full test and CI results |
| Human load | Human interventions, ownership decisions, and gate latency |

The proposed 30%–40% wall-clock acceleration is a hypothesis, not an achieved
result. Promotion requires a comparable baseline, exact metric records, no
quality regression, and Human review.

## 21. Rollback and recovery

All pilot changes remain isolated and unmerged until accepted. On failure,
stop new dispatch, cancel or allow safe read-only completion, revoke ownership
leases, preserve logs/results, verify the authoritative branch, and return to
the last accepted head. Never repair drift by merging unrelated branches or by
allowing a reviewer to become a writer. Resume only with a new routing preflight
and Human authorization when the stopping condition requires it.

## 22. Downstream Portfolio sequencing

No item below is activated by this plan.

1. Human closes this readiness plan, then allocates the exact `TEST` Pilot
   Session ID and baseline at the Human Pilot Selection Gate.
2. Separately authorize, run, and assess the bounded pilot; accept a concurrency policy only from
   measured evidence.
3. Authorize `S5-TEST-005` for the conformance Harness schema, runner, fixtures,
   and evidence contract. It must not redefine component semantics.
4. Complete required Product View work and its backend DTO handoff; Technical
   View follows the shared contract without owning it.
5. Complete the Document/File extension after the first MVS, including DENY,
   isolation, integrity, approval, and evidence boundaries.
6. Gather real Native model/network evidence before broad execution claims.
7. Gather exact-version OpenClaw managed-profile evidence after stable A/C/E
   handoffs; Native remains deterministic fallback.
8. Treat Skill/MCP discovery and governance as separate bounded evidence and
   implementation work with authorization, integrity, and zero-call DENY.
9. Keep enterprise Job/Memory/State work deferred until its architecture and
   ownership gates exist; do not infer it from Harness readiness.
10. Authorize `S5-IMPL-012` only after A–D, `S5-TEST-005`, deterministic
    fixtures, synchronized views, environment, and identity-correlation entry
    conditions pass.

## 23. Evidence Debt

- No repository-native routing, ownership-lease, duplicate detection,
  shared-path collision, child-result, or closeout validator exists.
- Actual Codex cancellation/failure propagation is unproven by product
  Workflow tests.
- Machine concurrency and resource limits require measurement.
- Serial comparison data and pilot metrics do not yet exist.
- Orchestrator, Researcher, and Writer are not current executable repository
  Agents.
- Long-conversation rotation and late-result quarantine are specified but not
  exercised.
- Hermes remains Experimental; its availability and certification debt is not
  changed by this plan.
- Repository lifecycle metadata lag requires separately authorized correction.

## 24. Exit criteria

Checkpoint B exits to Human Close Confirmation only when this plan and its
evidence index are internally consistent; the Portfolio, Registry, and Project
State uniquely register S5-PLAN-002; only authorized paths changed; links and
Session IDs are valid; secrets are absent; repository checks and exact-head PR
quality gates pass; and the Draft PR remains unmerged. Plan acceptance does not
authorize the pilot or any downstream Session. The pilot ID remains Human-
owned at a separate selection gate. Final Session closure requires Human Close
Confirmation and a separately authorized durable integration path.

`PLAN_STATE: COMPLETE_FOR_HUMAN_CLOSE_CONFIRMATION`

`PILOT_STATE: RECOMMENDED_ONLY / NOT_ACTIVE / NOT_AUTHORIZED`

`RESULT: READY_TO_CLOSE`
