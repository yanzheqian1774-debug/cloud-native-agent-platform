# P3 ontology frontend — bounded implementation

Base c920f88. Own ontology/OntologyPage.tsx, ontology.css,
ontologyPresentation.ts, new local ontology components and their tests only.
No conversation, model, API/owner contract, runtime or published resource changes.

Frozen F3 was rendered at 1440x1000: ontology -> 编辑 / 创建新版本 ->
resource-edit68, final simpleEditor687, screenshots under parent evidence
ontology-p3-prototype-r1. It has description/structured definition tabs, readonly
candidate relationship graph, object detail, differences before applying a generated
suggestion, source/publication explanation and existing lifecycle.

Current API accepts JSON business-ontology.v1 and business-document-rules.v1,
maximum import 98304 bytes. Actual object/relationship schema differs from the
prototype demonstration data. Project actual object codes/identity/properties,
relation endpoint/key/cardinality, mapping exact refs and rule fields without
inventing instances, labels, synonyms or missing facts. Display definitions and
instances separately; no instance API means no instance assertions.

Implement structured JSON edit and import preview with parse errors preserving
local unsubmitted text. Valid editing and graph share the same candidate. Invalid
text never replaces current graph silently and cannot be persisted or published.
The API rejects invalid CREATE/REVISE content; do not copy prototype's invalid
server-draft claim. Preserve all original content fields and immutable revisions.

Natural-language proposal API does not exist. Retain the prototype's editing
intent, but explicitly unavailable generation; never implement a fixed example
as actual understanding. This separate backend/profile adaptation is not part of
this frontend package. Structure editing and graph reading proceed independently.

Preserve existing lifecycle and independent REVIEW policy. Compare actual saved
version with candidate before save; a revision edit invalidates existing checks by
creating a new revision. Do not reuse old TEST or publish edited unsaved data.

Controlled tests: imports (both formats, malformed, oversized), content preservation,
invalid edit blocks save, candidate graph changes, type/object detail and relation
navigation, no fabricated document-rule graph/instances, version switching/dirty
state, lifecycle request exactness, 1440 and narrow layout. Full lint/build and
normal hooks. Actual ordinary maintainer and business execution owned by parent.

Conditional estimate: 60–90 minutes for this bounded frontend + controlled visual
verification, excluding hook queue; real NL generation requires an approved bounded
API/profile and cannot be estimated as a frontend-only task. Final prototype pixel
acceptance remains with prototype reviewer after parent installation.

## I5 retained scope audit

Read outputs/V6.8-I5本体简化增量/交付与走查说明.html. This is a local
prototype handoff, not proof that backend capabilities exist. It explicitly keeps
mapping, rule provenance, object details, Agent definition query and version history.
Do not drop them while simplifying the editor.

| Capability | First version confirmed / existing code | Evidence boundary or later work |
| --- | --- | --- |
| Metric meaning, aliases and units | Sales Metric fields, ontology_query.resolve and fixed currency unit are existing bounded implementation; show exact recorded aliases/unit/expression | Enterprise-wide unit conversion and arbitrary formulas are not implemented or newly approved |
| Controlled mappings and identity | Existing SourceMapping exact reference/digest, identity_fields, typed properties; mapped_rows validates mapping and relation keys | External enterprise sources remain proposed; do not fabricate live instances |
| Relations and applicable rules | Exact schema relation and document/sales rule definitions are retained; show navigation and applicable scope | General relation traversal/Agent semantic-query UI from historical prototype needs separate verification, not claimed connected |
| Action constraints | ActionContract exact Skill/executor, READ_ONLY operations; show declaration | Declaring an ontology action does not authorize any tool invocation |
| Gap candidate completion | Description + difference-confirmation is confirmed product intent | I5 supports one local example only; real model proposal/patch and conflict/source validation are backend integration gaps |
| Sources, object detail, versions | Existing schema can project definition and fixed references; existing owner lifecycle retained | Real dependency impact and ordinary-account query/upgrade acceptance require parent verification |

No narrowing to four fixed fields: structured editing retains complete supported
schema, metrics, mappings, identity, relations, actions and rules. No expansion to
a general inference engine or drag-and-drop graph editor.

## Bounded stage validation and remaining work

Implemented full supported JSON editing, preview from the same parsed candidate,
object identity/properties and declared relation navigation, metric aliases/unit,
exact mapping references, rules/actions, and explicit saved-version difference
confirmation before REVISE. Invalid text stays unsubmitted; failed owner validation
retains it. Existing owner actions and independent review remain unchanged.

Nine controlled browser checks passed, including existing sales/document regression,
the specialized four detail tabs and independent readonly history. The selected
read and edit views now use full width without the old directory sidebar. Existing
READ filtering supplies the history list; a partial list is explicitly labeled.
1440 editor/detail and 390 viewport evidence is retained under ontology-p3-ui-r5
and ontology-p3-visual-r4. Full frontend lint ran earlier; final changed-file lint
and production build passed. Independent visual acceptance remains with reviewer.

Agent使用 presents only saved definitions and declared action constraints; it does
not simulate queries. 引用与影响 explicitly states the reverse-reference list has
not been read and never equates missing data with zero impact. Actual query and
impact retrieval remain backend integration gaps, alongside natural-language
structured patch generation.
Local invalid text is preserved while mounted, not persisted as an owner draft;
cross-page/reload editing recovery is not delivered by this stage.

Ordinary-account actual permission is blocked separately: parent's
ontology-ordinary-current-r4 found test-resource preparation pending/uncertain and
no business-ontology snapshot match/collection admission. No empty-list inference,
permission expansion, or actual environment mutation is made in this package.

Final frozen ontology-import was also rendered in the browser: it advertises model
schema / field mapping / table template, but explicitly only displays a selected
filename and uses builtin samples (no upload/read). Therefore spreadsheet/CSV/RDF
import is not an implemented service capability. Current production owner import
remains the two JSON schemas above; do not advertise unsupported formats or silently
translate unsupported semantics. Real import preview uses the parsed actual JSON
candidate and preserves prior candidate on malformed/oversized replacement.

Final specialized detail verification: ontology -> 版本与变更影响 renders
resource-version68 with ontology-specific tabs 对象与关系 / 规则与来源 /
Agent使用 / 引用与影响, plus independent 历史记录. Do not copy the three-tab
layout used by other resource kinds. Current saved-version graph shows object
identity, attributes/unit and synonyms with explicit missing values, relation-source
navigation, raw fixed-version definition and folded professional reference. These
specialized read-detail tabs are the next outer-layout boundary, not a new design.
