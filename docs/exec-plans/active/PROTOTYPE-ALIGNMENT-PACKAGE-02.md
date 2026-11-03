# Prototype alignment package 02

Task authority: user instruction of 2026-11-03 to complete package 01 and proceed
in order, handling ordinary implementation issues autonomously.

Baseline: PR 188 candidate `01cbe0223f6643d331574d431c8cadf43317735e`.
This is a bounded frontend successor, not a reopening of ARCH-323 or a change to
IMPL-324 business execution authority. No real provider call, business mutation,
merge or release is part of this task.

## Scope and gate

G0 presentation-only correction over existing interfaces. Reuse the blue/white
business workspace and its `#0866ff` primary. Align the prototype Chinese brand label and preserve all
existing routes, permissions, lifecycle and command semantics.

- Extract the existing inline SVG icon vocabulary into one reusable component;
  add semantically distinct management/support icons in the same stroke style.
- Unify resource workbench color variables with the existing business shell;
  retain success, warning and danger meanings.
- Correct the top search placeholder/status wrapping on desktop and preserve
  narrow viewport behavior. Search remains disabled until actually implemented.
- Validate representative Employee, Skill and planning pages using explicitly
  labeled mock-interface evidence. This is not full-page visual acceptance.

## Design binding

The latest complete local portal is `Portal-V2.58-PC-Complete`, whose
`CURRENT-VERSION.txt` and `delivery-v259/Integration.json` identify V2.59.
Use its selected business SVGs as the current target and the older
R35-BP1 `PAGE-CONTRACT.md` for unchanged business functional meaning,
and business page SVGs D01/D04/S04/P06 for the shared blue/white visual
language. Original file hashes and the complete 245-current-page mapping are recorded
in the package-01 deliverable in the current chat's outputs directory. Existing
324 locked design and bounded historical acceptance remain unchanged. Do not
copy portal illustrations or switch to the P11 dark scenario navigation.

## Compatibility and validation

Affected: ConsoleShell, shared SVG presentation, business/resource CSS variables.
No dependencies, APIs, schema or persistence changes. Required checks: frontend
lint/build, existing shell/employee/resource/planning browser interaction tests,
same-viewport screenshots, 125% zoom-equivalent and narrow layout verification,
applicable repository quality checks. Report environment skips separately.

## Exit

Provide reviewable diff and screenshots with remaining full-Tab/layout gaps
assigned to package 04. Engineering verification, visual review, business
acceptance and merge/release remain separately recorded.

Latest-baseline supplement: R3 P03/P04/P08/P10/P12/P13 are selected reviewed
visual/interaction goals. In particular P04 now proposes save-and-plan orchestration
with separate durable steps and fail-closed continuation; this package does not
implement or implicitly approve new business orchestration. Current navigation
also has grouped business/people/operations areas; retain its full migration in
the next visual batch rather than treating icon/color changes as full alignment.

## Completion scope, 2026-11-03 continuation

User explicitly requests completion of package 02 followed by dependency-ordered
package 03. Complete grouped navigation (work/collaboration, people/resources,
operations/governance), route-aware breadcrumbs, shared resource navigation,
keyboard-operable tabs, controlled feedback and common control/layout styles.
Keep every existing route reachable, using a collapsed technical group for
advanced entries. No invented business-process page or fake notifications.
Apply shared patterns across existing management pages; use Workflow as the
representative form/catalog/detail/state page. Do not count resource-specific
editors, employee role reorganisation or missing backend features as shared UI.

G1 plan for readiness feedback: distinguish collection read failure from a
successful empty collection, suppress unverified metrics and disable new writes
when the collection cannot be read. Re-read is explicit GET only; never replay
commands. Existing endpoint contracts, ownership and lifecycle remain intact.
Tests cover loading, denied/unavailable, successful empty, recovery, selected
version/source links, keyboard navigation, native-size and zoom/mobile overflow.
Risk: hidden navigation and changed focus can regress evidence return; run the
existing focus and dialogue suites in addition to resource UI checks.

Package 03 independent work: inspect existing save/activate/plan APIs and scoped
real-case recovery, then implement continuous review in a separate plan before
coding. A valid live identity and independent execution grant remain requirements
for real-case execution; no fixture is a substitute for that evidence.


## Engineering handoff

Shared scope implemented: grouped desktop/mobile navigation, resource categories,
route breadcrumbs, reusable header/tabs/status/feedback, common control/table/
modal/side-panel styles, and collection-read readiness across six resource areas.
See docs/engineering/PROTOTYPE-WORKSPACE-DESIGN-SYSTEM.md for adoption and
explicit domain-page differences assigned to package 04. Current tests and
screenshots are archived with the chat deliverable. Human business acceptance,
merge and release remain pending; package 03 can proceed independently.
