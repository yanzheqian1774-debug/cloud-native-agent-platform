# S5-SPIKE-008 — Authoring and dual-view mock evidence

## Session identity and provenance

- Session: `S5-SPIKE-008 — Authoring and view mock prototype`
- Type / Track / Checkpoint: `SPIKE / D / B`
- Version: `v0.2 CONNECT — Digital Employee Technical Preview`
- Authorized baseline and initial head:
  `8d5e9c08b05a03e7ea098b871e82d848dd6ae067`
- Source of truth at preflight: `origin/main`, exact baseline match
- Branch: `codex/s5-spike-008-authoring-view-mock-prototype`
- Checkpoint A head: `cd001a1f911d9cacd83bee277ec74d4996fac674`
- Final head authority: the exact GitHub draft-PR head and delivery report. A
  commit cannot contain its own object ID; the PR head is the non-self-referential
  final provenance record.
- Classification: **INTERNAL MOCK / NON-AUTHORITATIVE / VERSION UNFROZEN**
- Production implementation, support, certification and readiness: **NOT GRANTED**

The worktree was created clean and isolated at the authorized baseline after
the default checkout was correctly rejected as dirty and owned by another
logical Session. No child Agent, parallel implementation, shared writer or
second logical S5-SPIKE-008 Session was used.

Checkpoint B reused the same conversation, branch, worktree and draft PR #59.
Recovery preflight proved no commit or push occurred after Checkpoint A, local,
remote and PR heads remained equal, `origin/main` remained the authorized
baseline, the index was empty, and preserved changes were only the reported
isolated i18n work. Human recovery authorization granted one bounded shared
scope exception for the prototype-only discovery shim described below.

## Exact changed-path inventory

| Path | Ownership and purpose |
| --- | --- |
| `experiments/s5-spike-008-authoring-view-mock-prototype/README.md` | isolated prototype usage and boundary |
| `experiments/s5-spike-008-authoring-view-mock-prototype/prototype.py` | disposable authoring/Diff and view-projection reference behavior |
| `experiments/s5-spike-008-authoring-view-mock-prototype/i18n.py` | isolated message-key lookup and business display projection |
| `experiments/s5-spike-008-authoring-view-mock-prototype/fixtures/customer-complaint-quality-improvement.json` | deterministic synthetic fixture |
| `experiments/s5-spike-008-authoring-view-mock-prototype/locales/en-US.json` | English prototype message catalog |
| `experiments/s5-spike-008-authoring-view-mock-prototype/locales/zh-CN.json` | Simplified Chinese prototype message catalog |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/index.html` | static interaction mock structure |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/styles.css` | isolated responsive presentation |
| `experiments/s5-spike-008-authoring-view-mock-prototype/web/app.js` | isolated client-only mock interactions |
| `experiments/s5-spike-008-authoring-view-mock-prototype/tests/test_prototype.py` | targeted fixture/interaction boundary tests |
| `tests/test_s5_spike_008_prototype.py` | Human-authorized prototype-only test discovery shim |
| `docs/evidence/s5/v0.2/s5-spike-008/README.md` | this evidence artifact |

The root test shim is the only Human-authorized shared-scope exception. No
shared configuration, production Console path, backend, product DTO, controller,
Workflow, Runtime Provider, Capability Gateway, CRD, schema, Registry, Project
State, dependency declaration or lockfile is changed.

Checkpoint B modifies the prototype README, fixture, isolated tests, and three
web files plus this evidence artifact. It adds `i18n.py`, two locale catalogs,
and the one exact discovery shim. `prototype.py` remains unchanged from
Checkpoint A. No other baseline-to-final path exists.

## Users, personas and assumptions

The primary Product View user is a quality manager or business operator who
needs to describe an outcome, review the proposed workforce and plan, supervise
progress, and understand conclusions without selecting infrastructure. The
secondary Technical View user is a platform engineer who needs the exact
identity, Binding, Provider, authorization, evidence and limitation chain.

The fixtures are synthetic and deterministic. They assume no real customer
records, enterprise Knowledge source, credential, policy engine, persistence,
Runtime invocation or production authorization semantics. Digital Employee is
a business projection and is not identical to an Agent Definition, Instance,
Task, Runtime Session, Profile or Provider identity.

## Primary three-step business journey

1. Enter the single plain-language customer complaint analysis problem.
2. Review the two suggested Digital Employees, bounded three-step work plan,
   proposed count of two mock Instances, expected Knowledge sources and Human
   confirmation.
3. Start deterministic mock work and view progress, business Outcome and
   citations. Technical details remain available through a secondary drawer.

Runtime selection is hidden from the default business flow. The Product View
says “Execution environment available.” Any alternative Runtime would require
explicit Human confirmation; silent fallback is prohibited.

## Digital Employee directory and authoring model

The directory provides name, role title and description, business
responsibilities, can/cannot-do boundaries, status and authorized Knowledge
scope for a Customer Insight Specialist and a Quality Analysis Specialist.

The authoring prototype preserves the published mock definition as immutable
input. Editing creates a separate Draft. The AI suggestion is stored as
`PENDING_HUMAN_REVIEW`; it does not alter a field until a Human accepts the
candidate. The deterministic field Diff retains published and Draft values.
Empty required fields or pending suggestions fail closed. Reject produces
`DRAFT_REJECTED_NOT_PUBLISHED`. Approval is required before mock publish, which
returns `IN_MEMORY_ONLY_NOT_PERSISTED` and performs no real publication.
Defensive-copy tests prove caller fixture input is not mutated.

## Product View mock inventory

- Digital Employee directory cards with clear business boundaries;
- one-question business entry;
- employee and bounded plan recommendation;
- proposed mock Instance count and expected sources;
- Human plan confirmation;
- business status, assigned employees, progress and current step;
- prioritized business Outcome and intervention state;
- business-friendly Runtime availability without implementation detail;
- view-only citations with visible mock/governance limitations;
- authoring published/Draft/suggestion/Diff/approve/reject/publish states.

## Technical View mock inventory

- Definition, Agent Definition reference, Instance, Task, Workflow and Platform
  Execution identities;
- requested/effective Runtime, target, version and Binding;
- Runtime Provider and provider-native correlation identities;
- Capability decision and request identity, Provider call count and replay
  barrier;
- internal Outcome and evidence classification;
- desired/effective Instance count, selected Instance, mock utilization and
  recommendation-only capacity presentation;
- Knowledge Collection, Asset, Revision, authorization, retrieved Evidence ID,
  fixture version, citations and provider correlation;
- explicit `DENY`, `UNKNOWN`, `NOT_SUPPORTED` and `NOT_YET_PROVEN` states;
- no automatic retry after possible effects and no exactly-once claim.

## Product-to-Technical mapping

| Product concept | Technical evidence for the same truth |
| --- | --- |
| Mira, Customer Insight Specialist | Digital Employee `de.synthetic.customer-insight.v1`; Definition `definition.synthetic.customer-insight.v1` |
| Assigned mock work | Agent Definition ref `agent-definition.synthetic.customer-insight.v1`; Instance `instance.synthetic.customer-insight.001`; Task `task.synthetic.qi-1042`; Workflow `workflow.synthetic.complaint-analysis.v1` |
| Execution status and Outcome | Platform Execution Identity `pei-synthetic-qi-1042-attempt-1`; internal Outcome `SUCCEEDED / DETERMINISTIC_SYNTHETIC_MOCK` |
| Execution environment available | requested/effective `Native`; target `native deterministic mock profile`; Binding `binding.synthetic.native.qi-1042` |
| Two-person proposed capacity | desired/effective Instance count `2`; selected Instance and `62%` mock utilization; no scale action |
| Approved Knowledge sources | Collection `knowledge-collection.synthetic.quality.v1`; three distinct Asset, Revision and Retrieved Evidence identities |
| Available citations | exact citations link to the three mock Asset revisions and evidence IDs |
| No intervention needed | Capability `ALLOW`, one Provider call; DENY fixture separately proves zero calls |

Both views copy the same Platform Execution Identity from the execution fixture.
Provider-native correlation is distinct and cannot replace Platform identity.

## Initial dual-language preview

The isolated preview supports `zh-CN` and `en-US`. It preserves the v0.1
foundation: catalogs are addressed by stable Message Key; lookup order is the
selected locale, `en-US` default, then the Message Key itself. The demo selects
`zh-CN` locally without redefining the global default-locale contract.

Static Product labels, navigation, authoring actions/states, Runtime
explanations, Knowledge/Citation labels, Technical section headings, error
states and critical actions use message keys. Localized fixture projections
provide role titles/descriptions, responsibilities, can/cannot-do content,
work-plan content, Knowledge Collection/Asset titles and Citation display text.
Missing `zh-CN`, missing `en-US`, unknown-locale and non-blank critical-action
fallbacks are covered by deterministic Python tests.

| Term | zh-CN | en-US |
| --- | --- | --- |
| Digital Employee | 数字员工 | Digital Employee |
| Definition | 定义 | Definition |
| Instance | 实例 | Instance |
| Task | 任务 | Task |
| Workflow | 工作流 | Workflow |
| Execution Identity | 执行身份 | Execution Identity |
| Runtime | 运行环境 | Runtime |
| Capability | 能力 | Capability |
| Enterprise Knowledge | 企业知识 | Enterprise Knowledge |
| Outcome | 执行结果 | Outcome |
| Evidence | 执行证据 | Evidence |
| Citation | 知识引用 | Citation |
| Draft | 草稿 | Draft |
| Diff | 变更对比 | Diff |
| Approval | 审批 | Approval |

The source timestamp remains `2026-08-26T04:00:00Z` and is always inspectable
in Technical View. `Intl.DateTimeFormat` formats its UTC display, while
`Intl.NumberFormat` formats duration, counts, Citation ordinals and utilization
for the selected locale. There is no string-concatenated date/number format.

Locale switching does not recreate or mutate the execution fixture. Tests and
browser QA prove byte-identical Digital Employee, Definition, Instance, Task,
Workflow, Platform Execution, Knowledge Asset/Revision and provider-native
identities; unchanged Runtime support state, Capability decision, Provider call
count, Outcome disposition and evidence classification. Stable reason code
`LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED` remains visible beside an English or
Chinese display explanation.

## Runtime support presentation

| Runtime | Product label | Technical state and limitation | Demo role |
| --- | --- | --- | --- |
| Native | `可用 / Available` | `INTEGRATED_COMPONENT_TESTED_CANDIDATE`; deterministic mock profile; `NOT_CERTIFIED`; production readiness not granted | primary execution path |
| OpenClaw `2026.7.1-2` | `实验性 / 当前不可用` / `Experimental / Currently unavailable` | exact-version Candidate; `LIVE_MANAGED_PROFILE_EVIDENCE_REQUIRED`; support `NOT_GRANTED` | compatibility and safe rejection only |
| Hermes | `实验性 / Experimental` | `NOT_CURRENTLY_CERTIFIABLE`; support `NOT_GRANTED` | Evidence Debt and extension boundary only |

The architecture panel describes Stable Core, a minimal logical Provider
boundary, pluggable Runtime Providers, Runtime Packages, Compatibility
Manifest and Conformance Evidence. Managed Native Profile/Extension/Plugin
options are labelled `FUTURE_V0_3_PLANNING_ONLY / IMPLEMENTATION_PROHIBITED`.

## Knowledge and Citation evidence

The view-only fixture contains one Collection and three Assets/Revisions, an
internal mock Binding, synthetic Provider, deterministic ALLOW evidence,
zero-call DENY evidence, three Retrieved Evidence IDs and three citations.
Labels are exact: `INTERNAL_MOCK / VERSION_UNFROZEN`, `SYNTHETIC / VIEW_ONLY`,
`LIVE ENTERPRISE PROVIDER: NOT_IMPLEMENTED`, and `GOVERNANCE: NOT_GRANTED`.
It contains no vector/chunk internals and implements no ingestion, RAG,
document parsing, production Knowledge Provider, public DTO or authorization
semantics.

Localized Collection, Asset and Citation titles are display-only. Collection,
Asset, Revision and Retrieved Evidence identities, authorization decisions,
ALLOW call count and DENY zero-call evidence remain identical across locales.
Product View exposes no vector/chunk details.

## Mock-state coverage

The deterministic state manifest includes: empty; Draft; Diff pending
approval; approved mock definition; business question entered; employee
recommendation; plan awaiting confirmation; execution running; execution
succeeded; capability denied; outcome unknown; OpenClaw unavailable; Hermes
experimental; Knowledge authorization allowed and denied; citation available;
and citation unavailable or stale. Success is the primary interactive path;
the remaining states are explicit fixture/test evidence for later UX review.

## Test discovery and validation evidence

Executed on 2026-08-26 against the candidate worktree:

- Checkpoint A baseline: direct prototype suite **22 Python/pytest tests**;
  repository standard suite **520 Python/pytest tests**. The 22 direct tests
  were not included in `make check` and the two counts were not added.
- Checkpoint B direct command:
  `uv run pytest experiments/s5-spike-008-authoring-view-mock-prototype/tests`:
  **32 passed** (22 baseline + 10 i18n/mapping/format tests).
- discovery-shim command:
  `uv run pytest tests/test_s5_spike_008_prototype.py`: **32 passed**.
- standard `uv run pytest --collect-only -q`: **552 tests**; exactly 32 nodes
  use the shim path, zero use the excluded experiment path, and a sorted-node
  duplicate search is empty. Thus 520 + 32 = 552 with no overlap.
- the shim loads one exact resolved test module, rejects paths outside the
  expected experiment root, fails closed if absent/unloadable, and exposes
  existing `test_*` callables to normal collection. It has no assertions,
  copied semantics, nested pytest, skip/xfail or production side effect.
- `pyproject.toml` remains unchanged; standard `make check` and GitHub Quality
  Gates now collect the prototype through the shim.
- full repository pytest: **552 passed**, with one existing Starlette/httpx
  deprecation warning;
- Ruff lint: **passed**;
- Ruff format check: **100 files already formatted**;
- `make check`: **passed**, including the same 552-test repository suite;
- production frontend `npm run lint` and `npm run build`: **passed** after
  `npm ci`; no frontend source, dependency or lockfile changed;
- browser QA: **passed** for complete zh-CN and en-US three-step paths; locale
  switch during plan review with state preserved; Draft/Diff/approval in both
  locales; Product/Technical switching; exact execution identity; Native
  success; OpenClaw unavailable; Hermes Experimental; Knowledge
  ALLOW/Citations; DENY/zero calls; UNKNOWN; and 390×844 responsive layout with
  no horizontal overflow. Role, responsibility and Citation content remained
  readable, focus styling is present and page warning/error logs were empty.
  The temporary local HTTP server was stopped and no screenshot or browser
  artifact was retained;
- remaining final-head, GitHub CI and audit results are recorded after commit
  in the draft PR and delivery report.

## Human UX01–UX11 decisions prepared

| ID | Candidate for Human decision | Spike evidence |
| --- | --- | --- |
| UX01 | Accept one-question, three-step primary business flow | complete interactive path |
| UX02 | Accept name, role, responsibilities, can/cannot-do and Knowledge Scope minimum | directory fixtures/cards |
| UX03 | Accept Draft, deterministic Diff and Human Approval | reference behavior and authoring UI |
| UX04 | Accept Product/Technical projections of one execution | exact identity equality tests/drawer |
| UX05 | Accept Native as primary visible execution path | support matrix and Product label |
| UX06 | Accept OpenClaw exact-version Candidate/unavailable pending live evidence | exact `2026.7.1-2` state |
| UX07 | Accept Hermes as Experimental/not currently certifiable | explicit support card |
| UX08 | Accept view-only Knowledge fixtures and citations | three traceable citations |
| UX09 | Confirm full Knowledge semantics require a separate ownership gate | visible governance limitation |
| UX10 | Accept proposed Instance count/utilization as mock evidence only | count and recommendation-only panel |
| UX11 | Require initial zh-CN/en-US preview | message catalogs, fallback and browser evidence |

These are prepared decisions, not approvals. Human acceptance remains pending.

## Limitations and Evidence Debt

- Static local prototype; no production Console route, API, backend or DTO.
- No persistence, authorization engine, publish service, workflow execution,
  Runtime invocation, retry, scaling, provider discovery or external call.
- No live OpenClaw evidence, Hermes certification, Native certification,
  support or production-readiness claim.
- No production Knowledge semantics, Provider, source, ingestion, RAG or
  governance. Full Knowledge ownership remains unresolved.
- Initial dual-language preview only; no production i18n framework change,
  authoritative multilingual DTO/schema, all-world locale, RTL, timezone
  governance or globalization certification.
- Mock identities and JSON shapes are disposable, internal and version-unfrozen;
  downstream implementation must adapt to the accepted Track A/D handoff and
  must not import this experiment into production.
- Human UX decision convergence and a separately authorized integration Session
  remain required. Golden Demo production integration has not started.

## Rollback

Delete or revert only
`experiments/s5-spike-008-authoring-view-mock-prototype/` and
`docs/evidence/s5/v0.2/s5-spike-008/`, plus delete the removable discovery shim
`tests/test_s5_spike_008_prototype.py`. There is no `pyproject.toml` rollback,
migration, persistent state,
Runtime resource, Knowledge index, dependency or lockfile cleanup. Production
behavior and public contracts are unaffected.
