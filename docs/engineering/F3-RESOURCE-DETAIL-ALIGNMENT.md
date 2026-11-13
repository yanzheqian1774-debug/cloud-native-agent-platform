# F3 resource detail alignment (G1)

Authority: user-authorized V6.9-F3 delivery, isolated frontend worktree based on
12dade1. Frozen prototype is read-only. No runtime, database, policy, model or
public contract changes are part of this candidate.

## Plan

Reuse F3ResourceDetail as the only managed Skill/MCP detail frame. Its three
primary tabs are overview, content/definition, and references/impact; history is
an independent entry in the publication banner. The final `detailBefore689`
prototype override removes the earlier fourth history tab. The frozen runnable
page, rather than an earlier source fragment, is the reference. Move existing professional controls inside the content tab, preserving
all typed command handlers, stale-version checks, original request recovery and
backend-owned receipts. Legacy resourceTab links select the corresponding section
without switching to a second full-page detail. Retain one editing draft and exact
published/historical content. Publication impact/selected upgrades appear only in
the explicit publish step, not the normal version page. Use one contextual return
and keep a directory fallback. Resource return state remains finite and validated.

Affected components: ResourceDetailView, F3ResourceDetail, ResourceVersionImpact,
SelectedResourceUpgrade presentation, ResourceManagement entry labels, shared
resource detail CSS and browser tests. No private conversation source changes.

Compatibility: legacy professional links remain resolvable. No operation is removed
or made automatically executable. Viewing tabs, history or impact is read-only.
Saved snapshot content and test revision matching stay unchanged. Existing pending
publication recovery remains accessible and must never resubmit an unknown result.

Validation: lint/build, targeted browser flows for exact revisions, draft edit/
cancel/save, test and publication entry, unknown receipts, legacy links, single
return and keyboard/mobile navigation. Fixture screenshots are candidate UI evidence
only; actual ordinary-account writes and installed visual acceptance belong to the
integrator's later deployment. Compare frozen prototype at the same viewport.

Risks: legacy deep-link tab mapping; mounting multiple upgrade components causing
locks or duplicate queries; stale draft content accidentally replacing publication;
unsafe return URLs; stale tests being interpreted as current. Keep a single mounted
operation body, preserve current backend safeguards, test each boundary.

## Verified route and resource differences

- Managed Skill: `/skills?managedResource=<id>`. Existing deep links using
  `resourceTab` now stay inside the same frame. Fixed published read-only references
  (`selected`, `resourceRevision`, `resourceDigest`) remain separate read-only
  projections, not a third authoring implementation. Prototype `resource-version68`
  finally renders three tabs and publication banner; `resource-history689` owns
  history. Earlier four-tab source is overridden by `detailBefore689`.
- MCP: `/mcp?managedResource=<id>` reuses the same managed frame but retains
  endpoint/secret-reference settings, health, discovery and tool selection. Skill
  operation tests and Skill-only publication are not exposed as MCP operations.
- Knowledge: `DefinitionManagement` at `/knowledge?managedResource=<id>` is a
  different existing owner UI. It currently places selected publication impact,
  document body, index status and history together; this mismatch is present, not
  fixed by Skill/MCP CSS. Preserve Markdown content and exact source/index facts
  when separately integrating the shared frame.
- Ontology: `/ontology` uses `OntologyPage`, with a directory and lifecycle panel.
  It is not the frozen domain detail navigation yet. The prototype preserves
  objects/relations, rules/sources, Agent use and impact; do not replace these with
  generic Skill fields. Actual publication/read permission projection and exact
  domain evidence remain owned by the ongoing mainline, not this UI candidate.
- Tools: `/tools/draft?id=<id>&revision=<revision>` uses `ToolDraftPage`, preserving
  exact draft identity, pending-save readback, declared input/output and effect.
  Read-only/tool import/test views are separate domain operations. Their full
  prototype interaction parity has not been verified in this candidate.

These are source/isolated-browser findings, not installed-platform acceptance.
No old task snapshot, governance state, endpoint or public schema is modified.

## Candidate validation (2026-11-13)

- Resource-focused browser suite: 43 passed (final three-tab navigation).
- Selected publication/recovery and updated screenshots: 13 passed, with selected
  resource upgrades enabled. Double-click/unknown/stale-preview/partial-readback
  and MCP exact revision tests retain their original command assertions.
- Earlier broader run: 102/105 passed. The mobile original-resource journey and
  duplicate-alert locator were resolved in the focused run; the independent
  employee stalled-read test passed when re-observed in isolation (1 passed),
  without changes to the employee implementation or its stalled-read assertion.
- Frontend lint passed; final production build and commit checks are recorded by
  the integrator handoff evidence. No installed deployment or real model run is
  claimed by these fixture results.

The prototype comparison uses the final runnable frozen source at 1440x900 and
the same synthetic title/purpose in the candidate fixture at 1440x900. The design
preview toolbar and product navigation shell have different framing; this is a
review comparison, not a claim of pixel-identical whole-platform acceptance.
Actual ordinary-account deployment and lifecycle writes remain integration gates.
