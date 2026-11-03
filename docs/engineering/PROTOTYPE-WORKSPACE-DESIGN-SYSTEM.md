# Shared business workspace — V2.59

The target is the effective current business catalog in the user's complete
Portal V2.59 package, not its historical desktop/mobile entries or public portal.
The package-01 artifact records individual file hashes. Representative bindings:

| Design | SHA256 |
| --- | --- |
| D01 | afb0533b445f7bd7983ad238fe0d1b3a4a82ba8ce5fe04f3ac29bd2d00bd714a |
| S04 | c345221e4db0f6ec5f0a1250ed26d2d978deb362bb2642f6697016dbfb70bf8e |
| W01 | 691de1adba180d0ead65a724023cb033634c3d0da7109053abc2255c75e70d3c |

## Shared vocabulary

Primary #0866ff, hover #0755d4, ink #101e4b, muted #607597,
border #dce7f8, page #f3f8ff, surface white. Retain success, warning and
danger semantics. A published definition is never labelled a successful run.
Font: Inter / PingFang SC / Microsoft YaHei / system sans-serif. Page headings
24px (21px mobile), section 18px, subsection 16px, body/control 13–14px,
metadata 11–12px. Shared spacing 8/12/16/24px; controls minimum 36px; card
radius 8px, control radius 6px. Keyboard outline 3px blue, offset 3px.

NavigationIcon is the code-native inline SVG family: 24-unit viewbox,
currentColor, 1.6–1.8 stroke; decorative SVGs are hidden from accessibility APIs.
BusinessNavigation is the route/label/icon inventory. The two-square brand mark
and Chinese product label follow the current prototype. No emoji substitutes,
remote image/icon service, extra font dependency or downloaded brand asset.

## Components and adoption

| Pattern | Implementation | Adoption |
| --- | --- | --- |
| Grouped sidebar/mobile menu | BusinessNavigation | ConsoleShell, every business route |
| Resource category bar | ResourceNavigation | Skill, MCP, Knowledge, Workflow |
| Breadcrumb | RouteBreadcrumb | Every shell route; exact page labels |
| Heading/actions | PageHeader | Knowledge, Workflow, Runtime; planning successor |
| Keyboard tabs/panel | WorkspaceTabs | Skill and MCP product/technical views; arrows, Home/End |
| Lifecycle label | StatusBadge | Workflow/Runtime exact detail; planning target read |
| Feedback/retry | ControlledState | Shared evidence plus Workflow/Runtime controlled states |
| Buttons/forms/filter/table | workspace-system.css | Existing management controls, no new command authority |
| Modal and side panel | Native dialog / EvidenceInspector styles | Knowledge dialogs, existing evidence inspector |
| Lists/detail/empty | Shared layout/selection styles | Resource workbenches; domain content remains intact |

Shared CSS is imported after the existing page modules in App.tsx. It is scoped
to the business shell and does not restyle the independent technical plane.
Deep links, exact revisions, readonly digests, form semantics and existing focus
return remain intact. Every old route remains reachable; advanced management is
collapsed except when its current route requires it. On mobile, a keyboard
operable full menu replaces the long off-screen strip and closes on navigation.

## Readiness and evidence

A failed collection read is unknown, not empty or measured zero. Workflow,
Runtime, Skill, MCP and Agent metrics withdraw unverifiable counts; Knowledge
retains its already explicit unavailable count. New creation is disabled until
read recovery; error recovery is explicit GET, not replay of a write. Denied and
not-found feedback do not disclose private error identifiers.

Representative Workflow screenshots use synthetic interfaces and are not proof
of a real published Workflow or run. Native comparison uses W01's 1536x1100;
125% equivalent is 1229x880, separately labelled from actual browser zoom.
Mobile 390x844 and resource schema tests at actual CSS zoom 1.25 cover overflow.
Existing evidence focus, session expiry, criteria CAS/UNKNOWN, planning history,
resource review and task authorization regressions must continue to pass.

## Package boundary

Package 02 delivers the common system and its representative page adoption.
It does not complete package 04's resource-specific tabs, card-based employee
catalog, workflow lane designer or original-file knowledge preview. Those remain
explicit page-level differences. No whole-product pixel acceptance, real business
acceptance, merge or release is inferred from these screenshots or checks.
