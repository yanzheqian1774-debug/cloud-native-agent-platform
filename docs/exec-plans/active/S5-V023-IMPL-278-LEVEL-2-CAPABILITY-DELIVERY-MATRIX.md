# S5-V023-IMPL-278 — Level-2 Capability Delivery Matrix

## Authority and execution boundary

- Session: S5-V023-IMPL-278, OPEN; Human Pre-Merge review pending.
- Accepted local baseline: `583c7faf8b2730b891682312d14a92d9a237e52d`.
- Accepted baseline tree: `f38f266d5d2c9dc969c3403f88ccbb791e3715e0`.
- Human supplied baseline CI: `34079265417 / attempt 1 / push / main / SUCCESS`; not new 278 validation.
- 274: Human-confirmed CLOSED / DURABLY_INTEGRATED_VIA_REL_277 / PR_149_MERGED / SESSION_CLOSED; shared frontend paths RELEASED; REOPEN PROHIBITED.
- Gate: Human accepted Knowledge G1 plan and pinned-baseline local implementation/tests/ordinary commit.
- Remote: `REMOTE_MAIN_NOT_REVERIFIED`; SSH port 22 rejected by environment. No SSH/proxy/authentication changes. No remote-latest claim from local refs.
- Before push/PR: verify actual remote main and path overlap; report advancement without automatic merge/rebase. One non-force push / Draft PR; no merge/deployment.
- Accessible collision audit: visible active tasks, first archived page, local formal branches/remotes/tags and commit subject history found no second 278 allocation. This same task's control records and execution instance are one Session. Remote PR/Issue audit and older archived pages remain UNKNOWN.
- This worktree is the sole 278 writer. No access to 276 worktrees or runtime assets.
- Historical architecture, Registry and closed Session records are unchanged.

## Classification and evidence rules

`IMPLEMENTED` means the named source operation exists; it does not mean a complete lifecycle was accepted. `PARTIAL` means only part of the user operation is connected. `NOT_CONNECTED` means the frontend operation is missing even if backend domain code exists. `PLANNED` is direction only. `UNKNOWN` is not verified. Scope is independent: use `P1_SCOPE_UNCONFIRMED` when version assignment is unconfirmed; use `OUT_OF_SCOPE` only with explicit authority. P1 gaps stay OPEN.

Evidence levels are separate: **button/route exists**, **real request wired**, **complete lifecycle accepted**. None can replace another. Tests listed below were inspected unless an executed result is recorded in the validation section. Human visual acceptance and historical stability debt remain OPEN.

Scope authority: [CONTROL-254](S5-V023-CONTROL-254-P1-CORE-CAPABILITY-AND-BUSINESS-ASSEMBLY-BASELINE.md), its P1-A/P1-B matrix; [PRODUCT](../../../PRODUCT.md); [ARCH-018](../../../architecture/s5/v0.2/S5-ARCH-018-BOUNDED-PRODUCT-CONTINUITY-PERSISTENCE-V1.md). Accepted architecture and implementation are separate. The full 274 Level-2 report was not available as readable task output during inspection; source, not report or REAL badges, establishes current findings.

Paths below are repository-relative. `F` = `console/frontend/src/`; `B` = `console/backend/src/agent_console/`; `E` = `console/frontend/tests/e2e/`. These are navigation abbreviations, not expanded write authority.

## Platform inventory — all primary surfaces and supporting routes

| L1 / route | L2 operation | P1 authority | Frontend source / UI | Backend/source evidence | Completion and normal/failure/history evidence | Gap/dependency/state |
|---|---|---|---|---|---|---|
| Home `/dashboard` | totals, attention, capability overview | P1 Chinese-first | F/dashboard/ProductDashboardPage.tsx | F/api/productAssembly.ts dashboard GET; domain not fully audited | route exists; request adapter exists; full normal/denied/history UNKNOWN | PARTIAL; full business completeness OPEN |
| Business `/work` | list and select historical problem | P1-B | F/problems/ProblemWorkspacePage.tsx | F/api/problemPlanning.ts `/api/internal/v0.2.1/problems` | real list, loading/error/empty; selected problem in URL | IMPLEMENTED source slice; independent acceptance OPEN |
| Business `/work` | search and status filtering | P1-B | same; input and three buttons | no handlers on these controls | buttons exist; not operational | NOT_CONNECTED / OPEN; not modified by 278 |
| Business `/problems` | analyze, plan, human review | P1-B | F/problems/ProblemPlanningPage.tsx | problemPlanning analysis stream/resume/rematch adapters | APIs exist; complete current authority/lifecycle not audited | PARTIAL; durable Business Problem authority connection UNKNOWN |
| Business `/work` | success criteria, approval, evidence/context | P1-B | ProblemDetail/ContextPanel | current problem projection | shows interpretation and approval; explicitly not execution | PARTIAL; close/reopen/follow-up and new authority connection OPEN |
| Digital Employee `/digital-employees` | template catalog/filter/detail/exact composition | P1-A Digital Employee | F/digital-employees/DigitalEmployeesPage.tsx | product `/digital-employee-templates` GET | real read-only template; errors/empty; identity/revision/digest | IMPLEMENTED source slice, complete lifecycle NOT accepted |
| Digital Employee | create/edit/publish/instantiate; Assignment/Placement; actual-use history | P1-A Digital Employee | create disabled; instance/placement unavailable | current page calls only template projection; broader backend UNKNOWN here | no writable product chain | NOT_CONNECTED / OPEN |
| Agent `/agent-center`, `/agents` | catalog/deep-link/authoring/lifecycle | P1 supporting composition | F/administration/PlatformSupportPages.tsx; F/resources/AgentWorkbenchPage.tsx | product catalog and agentDefinitions adapter | directory real; Agent Workbench full operation audit UNKNOWN; E/agent-workbench.spec.ts exists | PARTIAL; do not confuse Definition with Instance |
| Skill `/skills` | create/edit source contract | P1-A Skill | F/resources/SkillWorkbenchPage.tsx, Builder read-only | F/api/skillMcpResources.ts | create submits fixed supplier content; fields shown read-only | PARTIAL / OPEN user authoring |
| Skill | validation/review/publication/test/clone/import/export/lifecycle/history | P1-A Skill | same shared ResourceWorkbench | real adapter operations | requests wired, busy/conflict paths and revision history; E/skill-mcp-workbench.spec.ts | PARTIAL; full lifecycle acceptance UNKNOWN |
| Skill | exact binding/Attempt invocation/input/output/failure/timeout/replay | P1-A Skill | same; first eligible MCP and bounded test | managed capability adapter; Attempt domain not audited here | button is not proof of approved Attempt use | PARTIAL / OPEN; separate backend/execution dependency |
| MCP `/mcp` | register/endpoint/credentials | P1-A MCP | F/resources/McpWorkbenchPage.tsx uses ResourceWorkbench | fixed localhost endpoint; secret reference only | current create not editable | PARTIAL / OPEN |
| MCP | health/discovery/tool selection/call/history/drift | P1-A MCP | ResourceWorkbench | discoverMcp/healthMcp/selectTool/invokeMcp adapters | wired operations; picks first tool; approved endpoint/trust independently required | PARTIAL / OPEN; no real endpoint acceptance claim |
| Knowledge `/knowledge` | authoring/lifecycle/retrieval/history/import/quality | P1-A Knowledge; quality extras preexisting | F/resources/KnowledgeWorkbenchPage.tsx | B/knowledge_api.py, lifecycle_service, quality, PostgreSQL/Qdrant | detailed matrix below | PARTIAL until executed gates; no complete P1 claim |
| Workflow `/workflow-definitions` | definition/builder/validation/review/publish/successor/comparison | P1-A Workflow | F/workflows/WorkflowWorkbenchPage.tsx | F/api/workflowDefinitions.ts private v0.2.2 API | existing builder and requests; E/workflow-runtime-workbench.spec.ts | PARTIAL; exact binding and all lifecycle semantics not fully audited |
| Workflow / execution `/tasks`, `/runtime` | Run/Task/Attempt, intervention, retry/cancel/outcome | P1-A Workflow/Runtime | F/problems/PlanningDirectoryPage.tsx; route wrappers | current exact HTTP consumption UNKNOWN | route does not establish execution | UNKNOWN / OPEN |
| Runtime `/runtime-profiles` | profile create/validate/review/publish/successor/history | P1-A Runtime | F/runtime/RuntimeProfileWorkbenchPage.tsx | F/api/runtimeProfiles.ts | fixed Native/OpenClaw content; declaration lifecycle only | PARTIAL / OPEN editable product authoring |
| Runtime | startup/readiness/execution/stop/Placement/instance history | P1-A Runtime | same page explicitly grants no execution authority | separate runtime source not audited | profile != instance or real execution | NOT_CONNECTED at this surface / OPEN |
| Evidence `/evidence` | planning citations/human decisions/approval/events | P1 Evidence | F/evidence/EvidenceCenterPage.tsx | problemPlanning list projection | real read, filter, technical IDs; /work return lacks exact problem | PARTIAL / OPEN precise context |
| Evidence | cross-Attempt execution Evidence/recovery | P1 Evidence | same; App.tsx query branch separate | aggregation not connected; query branch not fully audited | unavailable states; not inferred from approval | NOT_CONNECTED / OPEN |
| Outcome `/outcomes` | problem/criteria/plan context | P1 Outcome | F/outcomes/OutcomeCenterPage.tsx | problemPlanning list, not Outcome authority | real context, empty/error; no outcome values | PARTIAL |
| Outcome | evaluation/confirmation/feedback/history | P1 Outcome | same; actions disabled | authority not connected to page | approval != execution != business success | NOT_CONNECTED / OPEN |
| Catalog `/catalog` | list/filter/resource links | P1 supporting resources | F/catalog/ResourceCatalogPage.tsx | product catalog adapter | route/request exists; complete behavior UNKNOWN | PARTIAL / OPEN detailed audit |
| Relationships `/relationships` | exact resource relations and context | P1 composition | App UnifiedRelationshipsPage; F/shared/ResourceContext.ts | product relationships adapter | full active route behavior UNKNOWN | UNKNOWN / OPEN |
| Attention `/attention` | pending resources | P1 supporting operations | F/attention/AttentionPage.tsx | product attention GET adapter | full behavior UNKNOWN | UNKNOWN / OPEN |
| Permissions `/permissions` | owner/review/scope read | P1 minimum governance | PlatformSupportPages CatalogPage | product catalog GET | real read; error/empty; no permission write authority | PARTIAL |
| Permissions | request/approve/role edit/enterprise IAM | P1_SCOPE_UNCONFIRMED for full IAM | same, disabled | no wired write API | page REAL badge does not cover writes | NOT_CONNECTED / OPEN scope reconciliation |
| Operations `/operations` | cross-domain navigation | P1 operations | PlatformSupportPages static page | links only | navigation implemented, no runtime metrics | PARTIAL |
| Operations | live observation/Resource Use/alerts | P1 for basic use; advanced P1_SCOPE_UNCONFIRMED | same | unified read model not connected | no fabricated health/counts | NOT_CONNECTED / OPEN |
| Applications `/applications` | discovery/install/subscribe/publish | P1_SCOPE_UNCONFIRMED | PlatformSupportPages static page | no connected application authority | placeholders and disabled operations | PLANNED / NOT_CONNECTED |
| Security `/security` | events/policy/audit editing | P1_SCOPE_UNCONFIRMED beyond minimum disclosure | same | no connected event/policy authority | explanatory disclosure boundary only | NOT_CONNECTED / PLANNED |
| Models `/models` | model catalog/health/pricing/governance | P1_SCOPE_UNCONFIRMED; PRODUCT places broad governance v0.2.4 | same | no connected authority | references are not verified capability | NOT_CONNECTED |
| Usage `/usage` | measured usage/cost/billing | P1 basic use, expanded billing P1_SCOPE_UNCONFIRMED | same | no connected measurement/billing authority | NOT_COLLECTED/NOT_MEASURABLE; missing != zero | NOT_CONNECTED / OPEN basic use |
| Settings `/settings` | identity/notifications/integrations/backup | P1_SCOPE_UNCONFIRMED | same | no read/write settings API | disabled writes | PLANNED / NOT_CONNECTED |
| Help `/help` | product navigation/terms | supporting Chinese-first | same static page | frontend routes/terms | IMPLEMENTED source slice; no service promise | support tickets PLANNED / P1_SCOPE_UNCONFIRMED |

Shared fixture/demo/technical routes are not additional accepted platform capabilities. Product and Technical projections must preserve canonical identities. Other module fixed-input and unconnected-filter gaps are deliberately retained.

## Knowledge operation matrix

All private endpoints below use `/api/internal/v0.2.2/knowledge`. Backend authority: `knowledge_api.py`, `knowledge_schemas.py`, `knowledge_lifecycle_service.py`, `knowledge_quality.py`, `knowledge_ingestion.py`; authoritative SQL and derived Qdrant are unchanged.

| Operation | Baseline finding | Reused real interface / implementation | 278 local change | Negative/history/permission contract | State |
|---|---|---|---|---|---|
| Source creation | fixed name/source/document/content; no user form | POST root / CreateKnowledge / service.create | editable modal, input validation, retain input on failure, draft only | final backend validation; one in-flight request; no automatic retry after uncertain response | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| List/filter/detail/return | local filter, selected object lost on reload | GET root and `/{id}` | URL q/resourceId/revisionId/digest/view; exact mismatch fails visibly; return preserves filter | unavailable/denied do not select another object; keyed resource generation invalidates late response | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Document and revision detail | current source metadata only; technical digest history | aggregate revisions/content | choose historical revision, show source/document/chunk and digests; current commands labelled separately | published revision immutable; unknown revision/digest not replaced | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Validate/review/publish | already wired | `/validation`, `/reviews`, `/publications` | reuse; Chinese feedback, busy lock, exact version/digest | DRAFT -> VALIDATED -> HUMAN_REVIEWED -> PUBLISHED; no auto replay | IMPLEMENTED source; executed lifecycle below, Human acceptance OPEN |
| Successor | existing text input/API; incomplete validation/conflict handling | `/successors` expectedVersion/content | bounded content validation, retain input on stale, authoritative re-read errors handled | published predecessor and no active draft required; no other source fields rewritten | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Ingest/rebuild | already wired | `/ingestion`, `/rebuild` | reuse, busy protection, exact snapshot display | backend determines availability; no frontend publication inference | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Recovery | UI conflated purge and index recovery | `/recovery` calls ingest; `/purge` retries purge | index recovery only when no purge; failed purge returns to authorization confirmation | RECOVERY_REQUIRED never labelled complete | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Archive/purge | already wired, purge dialog | `/archive`, `/purge` | preserve archive semantics, authorization/reason input, Chinese confirmation | archive retains history; exceptional purge removes payload/vectors and leaves tombstone; partial HTTP202 retained | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Workbench retrieval | showed only latest citations | `/retrievals`; aggregate retrievals | query validation, all recorded history, snapshot/query/citation/revision/digest details, no-result state | DENY and absent bounded disclosure; not Attempt Evidence; no query reconstruction from digest | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Search playground | wired mode/metadata/ranks | `/operations/search`, `/operations/metadata` | reuse; query validation and resource result isolation | backend authorized filters; no results explicit | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Evaluation | wired creation/comparison, history missing | POST and existing GET `/operations/evaluations` | connect history; expose exact returned run/dataset fields | current recall as expected set is not independent quality acceptance | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Summary/duplicate/export | wired but combined display hid results | summaries, duplicates scan/GET/decisions, export GET | independent result section, read existing duplicate queue, truthful extractive label | duplicate decisions never delete/merge/rewrite; export displays authoritative JSON | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Import | fixed mixed-validity JSONL | imports preview and execute | txt/md/jsonl input, invalidation on edit, real preview/accepted/rejected/partial/idempotent retry, imported identity links | preview != import; counts only, no row failure reasons supplied; imported content stays Draft | IMPLEMENTED source; executed coverage below, Human acceptance OPEN |
| Attempt retrieval/use/Evidence | separate domain code, no Knowledge HTTP endpoint | knowledge_attempt_retrieval.py / attempt repository | no fabricated connection | Workbench citations cannot prove Attempt use or deterministic Attempt citation | NOT_CONNECTED / OPEN |
| New connectors/collection CRUD/multi-document editor/unarchive | no confirmed HTTP operation | none | not implemented | no backend expansion | OPEN; scope/API must be confirmed separately |

## Field and error mapping

- `name`: required meaningful input; backend NFC, <=500 UTF-8 bytes, no Cc. Frontend does not compute canonical IDs/digests.
- `source.sourceId`, `documentId`, `kind`, `provenance`: backend identifier regex `[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}`; kind defaults TEXT but no new enum contract invented.
- `source.content` and successor `content`: NFC/newline normalization; nonblank; <=512 KiB; paragraphs <=4 KiB; reject disallowed controls, retain text on failure. Backend ingest_text remains final authority.
- `expectedVersion`: current authoritative aggregateVersion, never user-generated. Review/publication `digest`: exact current revision. Stale failure refreshes authority and requires explicit input decision; lifecycle conflicts do not trigger automatic replay.
- `query`: nonblank, <=2000 UTF-8 bytes, no controls. Search `mode`: LEXICAL/SEMANTIC/HYBRID, topK retains 5. Metadata filters remain backend scoped.
- import `format`/`content`: TXT/MD <=1 MiB, JSONL <=5 MiB and backend <=1000 records with exact name/content fields. Backend preview may accept content later rejected by ingestion limits. Only backend returned counts are presented; detailed rejected-row causes are unavailable.
- purge `authorizationId`/`reasonClassification`: required; existing backend authorization semantics unchanged; no frontend-created permission authority.
- HTTP403/404: bounded unavailable-or-not-authorized message, raw safe reason retained. HTTP422 or known input error codes: field feedback. STALE_KNOWLEDGE: version conflict. Other409: lifecycle/operation conflict. 5xx/network: service failure/uncertain submission. No dangerous auto retries.

## Exact changed paths / validation plan

Only the six Human-authorized paths: this matrix; F/resources/KnowledgeWorkbenchPage.tsx; F/resources/KnowledgeTechnicalProjection.tsx; F/api/knowledgeResources.ts; E/knowledge-workbench.spec.ts; F/resources/KnowledgeWorkbenchPage.css.

The page-local CSS scopes responsive wrapping, dialog size, input controls and focus outline to Knowledge. Shared Shell, global focus mechanism, browser harness, backend, migration, CI and deployment remain unchanged.

Validation sequence: affected frontend lint/build and Knowledge browser test; real PostgreSQL/Qdrant lifecycle/denial/history/restart/purge assertions; isolated frontend transport fixtures for race and failure behavior; desktop1440/mobile390 and keyboard/dialog/return focus; final make check and relevant regression. No claim that fixture tests prove real services. Existing business assertions are preserved while adapting controls to editable Chinese-first forms.

## Environment ownership and executed evidence

- Created new containers `s5-278-postgres` and `s5-278-qdrant`, label `session=S5-V023-IMPL-278`, no shared data mounts; localhost ports57278 and63278 respectively. Docker inspect confirmed label and bindings before destructive tests. Existing images only; no network workaround.
- Existing unmodified isolated_browser_harness.py runs immutable candidate copies under `/private/tmp/s5-278/`; backend18278/frontend14278. No other Session backend or collection is used.
- First preflight failed because invocation omitted core/src and gateway/src; fixed invocation only. No test/harness weakening.
- Frontend lint PASS and live build PASS during development; build reports existing-sized bundle warning (>500kB). Final results will be appended after validation.
- Push/PR/PR-head CI: NOT_RUN. Remote main remains NOT_REVERIFIED.
- All completion claims remain bounded to the selected Knowledge operations. All other P1 gaps, Human visual acceptance and historical stability debt remain OPEN.

## Final local validation — 2026-09-07

- `npm --prefix console/frontend run lint`: PASS on final source/test changes.
- `VITE_SUPPLIER_QUALITY_DEMO_MODE=live npm --prefix console/frontend run build`: PASS. A >500kB bundle warning remains; no bundler/CI changes made.
- `make check` (local socket permission enabled): **1488 passed, 45 skipped, 1 warning**, PASS. Skips are existing real-dependency/platform conditions, not accepted capabilities. Initial sandbox execution had 3 socket-bind PermissionErrors; after allowing test-owned localhost sockets, the suite passed. Final log: `/private/tmp/s5-278/make-check-source-final.log`.
- Final isolated Knowledge browser selection: **3 passed, 0 skipped, 0 unexpected, 0 flaky**. Immutable candidate6, run7, real PostgreSQL and Qdrant. The original real business assertions remain, with editable Chinese controls and added actual STALE_KNOWLEDGE concurrency/re-read/explicit-resubmit assertions.
- Real journey: create, exact validate/review/publish, ingest and Qdrant snapshot/payload verification, authorized retrieval/citations, search, evaluation/comparison, summary, mixed-validity import and nonduplicating retry, duplicate classification, cross-tenant bounded denial, real version conflict, successor/new snapshot, one owned backend restart/readback, technical identity, archive, purge404, failed vector-store purge202/RECOVERY_REQUIRED.
- Frontend transport fixtures (not real-service proof): late search response after browser Back cannot contaminate the new resource; query reset, filter return, exact missing revision and detail/return focus; 390px input validation, two synchronous submit activations produce one request,503 retains text, Escape restores trigger focus,404 remains disclosure-safe.
- Defect found and fixed during mobile validation: textarea's implicit label changed with its text; explicit accessible names now preserve field access after error. The failing assertion was retained.
- Visual review: inspected `knowledge-1440.png` (real-service page) and `knowledge-390-form.png` (explicit transport-failure fixture); content wraps and modal scrolls within viewport. These are engineering visual checks, not Human visual acceptance. Images retained at `/private/tmp/s5-278/visual/` before harness artifact cleanup.
- Shared Shell/global focus/harness unchanged; only Knowledge-local focus handling and scoped CSS changed. Full cross-platform Browser Acceptance was not rerun; Knowledge-focused browser acceptance is the bounded validation claim.
- Remote main retry after validation again failed with SSH port22 Operation not permitted. `REMOTE_MAIN_NOT_REVERIFIED`; no push, Draft PR or source CI obtained.

Final harness evidence: `/private/tmp/s5-278/run-7/acceptance-evidence.json`.
- Acceptance state: `PASSED`; owned restart count `1`.
- Immutable before/after candidate manifest: `63fde61bf5ddbde88149534d447e3ebdeb7b8eb7dae19cafc3eba6bd9f97589e` / `63fde61bf5ddbde88149534d447e3ebdeb7b8eb7dae19cafc3eba6bd9f97589e`.

### Exact validated source file hashes (SHA-256)

- `console/frontend/src/resources/KnowledgeWorkbenchPage.tsx`: `6cbce9af68f9fe0696dfa68181fe648156b0641f32764da24cfd30a1b3c57f98`
- `console/frontend/src/resources/KnowledgeTechnicalProjection.tsx`: `057be8ea22b884b1044449a2aefa39e7d38f5bc3020a1d76bbdac03fed9ff3ea`
- `console/frontend/src/api/knowledgeResources.ts`: `6c8d4168455583993986ff269370d21e17af5f60725c34ce6c0dcf9e978fe144`
- `console/frontend/tests/e2e/knowledge-workbench.spec.ts`: `2c7046b3f269cff3d43ada5d4ca3764f81a9ee6800b2f3a760705c00424aef75`
- `console/frontend/src/resources/KnowledgeWorkbenchPage.css`: `6a0d7b567f39ab508d28b25ac5328bdbab4fc1f3564cc5adbe83a4218b50b4be`


### Remaining OPEN

Attempt-scoped Knowledge HTTP consumption and deterministic Attempt Evidence; complete Digital Employee/Workflow bindings in this Knowledge surface; new source connectors, collection/multi-document CRUD, unarchive and per-rejected-row import explanations without existing HTTP contracts. No simulated implementation added. Evaluation uses the existing workbench recall-derived expectation set, not independent quality certification. Other platform rows and P1_SCOPE_UNCONFIRMED assignments are not closed by this work.

Human visual acceptance, historical stability debt, remote-main/overlap re-verification, non-force push, Draft PR and exact PR-head CI remain OPEN. Local commit identity is reported by the task delivery response; this document does not embed a self-referential commit hash. No merge or deployment authorized/performed.


## Delivery continuation audit

- Five source/test SHA-256 values above were rechecked and all MATCH; final harness manifest matches this matrix. Prior completed validation is reused without rerunning full suites.
- Pre-commit and ordinary commit had not run at the continuation audit; no pending 278 command remained. Git's installed pre-commit hook requires pytest on commit; its actual result is reported with the local commit delivery.
- Six authorized paths only; no staged changes before delivery preparation. `git diff --check` PASS.
- Normal remote-main retry still blocked at SSH port22; no configuration changes or network workaround. Publication remains BLOCKED, not successful.
- Both known containers `s5-278-postgres` and `s5-278-qdrant` were label-verified as278, then removed with their own anonymous volumes after tests completed. No 278 backend/browser/harness/test process remained at audit.
- Retained redacted evidence bundle: `/private/tmp/s5-278/evidence/` (final acceptance summary, candidate manifest, browser counts/titles, final quality log and engineering images). Temporary harness tokens/control sockets and raw browser report were deleted. Immutable candidate source copies and non-sensitive task-local build/diagnostic files remain under `/private/tmp/s5-278/`; no shared runtime assets were touched.
- Session remains OPEN for remote publication and Human Pre-Merge review. This is bounded Knowledge local delivery, not complete platform/P1 acceptance.
