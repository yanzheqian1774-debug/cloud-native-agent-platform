# G1: Explicit fixed-work configuration succession in the original conversation

Status: isolated implementation and targeted validation completed; default OFF.
Resource agent owns this isolated candidate; root is the sole actual publisher.
0079 is additive and must be applied explicitly before enabling the new route.

## Problem and first delivery boundary

The actual saved purchase work and its conversation handoff are already committed.
The newly required Native Skill has a different explicit executor and I/O schema;
its Employee and Team versions must succeed the deterministic versions. Original
work heads bind exact Team revisions. Original 0073 handoffs are immutable and
unique per conversation. Neither record may be rewritten, and a fresh chat may
not hide this lifecycle gap.

First additive transition must cover the observed never-bound, never-started
configuration in its original empty conversation. It must be explicit and show
old/new Team, Employee, Skill and work differences. This first transition does NOT
constitute completion of post-BOUND/WAIT/inflight configuration maintenance. Those
remain in the full goal and require a separately proved transition, preserving
every historical target, period and result. No restrictive first implementation
may be described as complete fixed-work lifecycle support.

## Compatibility and authority

Do not edit 0073 or relax its unique/immutable constraints; do not change the old
work-head Team invariant or historical revision reads. Reuse original authoring
SAVE under the new Team version to create an explicitly linked successor config,
with immutable predecessor/current identity facts. Keep original root handoff as
conversation anchor. A new internal v2 source relation may resolve the exact
successor through additional facts; old v1 requests/records remain unchanged.
No Agent/Task/Workflow/Runtime lifecycle, CRD, infrastructure or auth architecture
changes. Original BrowserSession, original conversation ownership/current grants,
original authoring/current Team READ+REVISE owners remain authority. No READ grant
implies START/ANSWER/model authority. Config succession does not bind a target,
activate trigger, migrate old criteria, dispatch or invoke a model.

## Required checks before implementation can be frozen

- Exact old and new work refs, team refs, source body/instruction/schedule and
  resource-version diff; same authenticated subject/domain and original chat.
- Whole predecessor chain and unique current successor; current-head/CAS proof.
- First boundary: no original messages, journal, BOUND, service preparations,
  triggers, Native WAIT or in-flight execution; refusal cannot be bypassed by
  a new command key. Old completed/UNKNOWN facts never replayed.
- Same command replay returns immutable original receipt, stale preview/current
  source or revoked grants refuses; no silent fallback to a different Team.
- Every consumer uses shared exact version-aware source facts, including original
  conversation adoption/source selection, target-review guard, BIND, fixed-chat
  provenance/focus, ServicePlanningRegistry, BoundServiceExecutionBridge and
  neutral-goal state. No raw-table shortcut accidentally treats predecessor as
  current. Historical source reads keep old exact facts, not current pointers.
- New BIND remains separately explicit after the original actual one-C1 target
  preparation and active completion criteria, with source/schema/body/admission
  provenance; service/cycle authority remains independently issued and checked.
- UI stays in existing fixed-work/source review flow, shows version differences,
  original-chat return and non-executing state; no internal-resource assembly
  burden on business users. Prototype review needed before visual acceptance.

## Consumer inventory inspected

fixed_work_authoring_postgres (old Team invariant / history),
workbench_fixed_work_source, fixed_work_sources_postgres,
conversation_goal_neutral, fixed_chat_delivery, fixed_chat_facts,
fixed_work_service_admission and frozen P0 bound_service_execution.
Additional actual consumers must be enumerated by source search before coding.

## Verification strategy

Isolated real original-owner PostgreSQL authoring and original chat chain, not
manually inserted work/handoff/binding records. At least: exact positive
pre-target succession and original-chat use; replay without extra writes; wrong
subject/Team/work/digest/body/schedule; stale/branching predecessor; BOUND/WAIT/
message/UNKNOWN refusal; revoked grants before effect; old v1 read/handoff/BIND
regressions. Then integrated generic Native source/Skill/Employee/Team versions,
real model calls, budget/audit and actual original-chat result under root.
Full post-BOUND maintenance and two actual 24h-separated periods remain open.

## Product and independent G1 review

Prototype delivery review confirms existing team-routines / routine-detail-v6 /
routine-change can carry the update. No new top-level entry or visible clone.
One logical fixed work must project exactly one current arrangement and an
explicit effective point; all old versions remain historical. Only future
unoccurred events may use an upgraded arrangement. Preserve existing enabled/off
state under its original authority; this first never-started scope remains off.
Do not synthesize a user message or target. Resource technical tuples fold into
details. UNKNOWN keeps original command and arrangement until actual readback.

Planning independent source review found no existing legal owner shortcut and no
G2 conflict in this bounded additive first transition. It requires directory,
readiness and old SAVE to enforce current/superseded state, and shared original
conversation/work locks in the same transaction as SAVE and facts to prevent a
visible orphan successor. The review is not code or PostgreSQL acceptance.

Implementation order: pure exact version diff/request contract, additive typed
PostgreSQL schema/compatibility, atomic original-owner operation with real
fixtures, shared source consumer integration, existing UI action and difference
review, integrated regression/freeze. Do not release the first pure layer alone.

### Final narrowing during owner validation

Changed Employee references are read through the original immutable Employee
repository after current exact Employee READ; the preview includes those records'
composition references, including Skill revision/digest, not arbitrary Skill
bodies or execution authority. Immutable receipt validation recomputes the same
composition projection. Current Employee READ is required again before returning
a succession receipt containing these differences.

The successor configuration remains attached to the original conversation at its
exact saved revision. A new ordinary SAVE on that physical successor is rejected
(after exact original command replay), rather than silently creating a revision
without that conversation relationship. The detail marks its configuration fixed
and retains the separate, explicit team-version succession operation. Changing
instruction/schedule after this attachment is outside this first pre-target slice.

### Bounded chain reads

Work and conversation readers first locate their exact logical chain, then validate
all facts in that chain. They do not scan other actors' or teams' chains. Directory
retirement filtering happens in SQL before pagination; only returned page chains
are fully validated, with a request-local chain cache. No validation result is
cached across transactions. An explicit disposable-storage corruption test proves
an unrelated malformed chain cannot block the original work/chat or disclose it.
The scope-level short authoring mutex prevents command/work lock inversion; no
model, provider or network operation occurs while this write lock is held.
