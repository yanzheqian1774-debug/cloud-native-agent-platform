# S5-REL-028 — Native evidence and shared read model integration evidence

## Candidate identity and provenance

- Session: `S5-REL-028`
- Task: `[S5-REL-028] Native Evidence and Shared Read Model Durable Integration`
- Architecture authority: `S5-ARCH-010 / Hybrid F`
- Human Integration Implementation Decision: `APPROVED_WITH_CONSTRAINTS`
- Checkpoint: `A — BOUNDED_DURABLE_INTEGRATION_CANDIDATE`
- Durable baseline and merge first parent:
  `13bc16f746a58912bc093ff249ff390250ce20cf`
- Source session: Human-confirmed closed `S5-IMPL-014`
- Source branch: `codex/s5-impl-014-native-evidence-shared-read-model`
- Source PR: #70, retained `OPEN / DRAFT / UNMERGED`
- Source head and merge second parent:
  `443214c0a0277473648f68800ad008f981d758c9`
- Source commits:
  - `6295aea5be9e421b0e259a0b1cce1c2dedc0f140` — native execution evidence read model;
  - `443214c0a0277473648f68800ad008f981d758c9` — P1 safety-boundary correction.
- Integration branch:
  `codex/s5-rel-028-native-evidence-shared-read-model-integration`
- Provenance-preserving integration merge:
  `af3dab64deec8a95138a28f7f7dd5c3ce44c6e7f`
- Integration tree: `08478be3445aea91519d8b7cafa086d6d2cbdab7`

The integration is an explicit true two-parent merge. It preserves both source
commits and does not squash, rebase, cherry-pick, amend, fast-forward, or rewrite
source history. The merge was conflict-free and its tree exactly equals the
source-head tree. All 29 source blobs initially matched the source head.

## Exact candidate scope

The source contributes exactly these 29 paths:

1. `PROJECT_STATE.md`
2. `console/backend/src/agent_console/app.py`
3. `console/backend/src/agent_console/execution_snapshot.py`
4. `console/backend/src/agent_console/graph_projection.py`
5. `console/backend/src/agent_console/preview_schemas.py`
6. `console/backend/src/agent_console/preview_service.py`
7. `console/backend/src/agent_console/shared_views.py`
8. `console/backend/tests/test_execution_evidence_security.py`
9. `console/backend/tests/test_execution_snapshot.py`
10. `console/backend/tests/test_preview_api.py`
11. `console/frontend/src/App.tsx`
12. `console/frontend/src/api/executionPreview.ts`
13. `console/frontend/src/product/adapter.ts`
14. `console/frontend/src/shared/executionSnapshotTypes.ts`
15. `console/frontend/src/technical/adapter.ts`
16. `console/frontend/tests/test_s5_impl_011_technical_view.py`
17. `core/src/agent_core/execution_evidence/__init__.py`
18. `core/src/agent_core/execution_evidence/domain.py`
19. `core/src/agent_core/execution_evidence/ports.py`
20. `core/src/agent_core/execution_evidence/sqlite.py`
21. `core/tests/test_compatibility.py`
22. `core/tests/test_execution_evidence.py`
23. `core/tests/test_sqlite_evidence_repository.py`
24. `docs/evidence/s5/v0.2/s5-impl-014/README.md`
25. `docs/governance/REGISTRY.md`
26. `operator/src/agent_operator/execution_coordinator.py`
27. `operator/src/agent_operator/task_controller.py`
28. `operator/tests/test_execution_coordinator.py`
29. `operator/tests/test_task_controller.py`

The REL successor modifies the two source-inventory governance paths,
`PROJECT_STATE.md` and `docs/governance/REGISTRY.md`, and adds only this file,
`docs/evidence/s5/v0.2/s5-rel-028/README.md`. The baseline-to-candidate inventory
is therefore exactly 30 unique paths, not 32. After the bounded governance
updates, the other 27 source paths remain byte-identical to the source head;
the S5-IMPL-014 evidence README is among those exact blobs. There are no file
mode changes, deletions, renames, or unexpected paths.

## Authority and P1 safety boundaries

Kubernetes Workflow and Task resources remain execution and current-state
authority. The append-only Execution Evidence Repository is evidence authority
only. Production evidence is bound to Kubernetes-owned Workflow UID and Task
UID subjects; display names and `workflow.unbound` are not production evidence
associations. Platform Execution Identity remains the execution correlation
spine.

Evidence replay is idempotent for the same record identity and stable digest.
A repeated identity with a different digest fails closed. Repository-assigned
sequence, timestamps, SQLite details, paths, and process metadata are excluded
from the stable producer digest. Namespace and security-domain reads remain
isolated.

Evidence and Citation references are independently authorized. Denied
references disclose no identity, metadata, digest, or count. DENY requires zero
Provider calls and zero live citations, and authorization is resolved before
evidence loading.

The existing Canonical Graph remains relation and visibility authority. Graph
relation identity, direction, cardinality, evidence, visibility, and payload
are preserved verbatim. The frontend consumes those relations and creates no
canonical relation IDs.

The deterministic assembler freezes one high-water mark and produces one
shared snapshot with sibling Product and Technical projections. A complete
snapshot requires unique terminal execution evidence and contiguous consistent
ordinals. A contiguous non-terminal prefix is `PARTIAL`, never a verified
success.

## Persistence and presentation limits

SQLite is an explicit-path, bounded local single-node adapter. Its append
transaction, schema verification, subject indexes, idempotent replay and
digest-conflict behavior do not establish exactly-once execution, shared-file
system safety, high availability, multi-node durability, migration support, or
production certification. Database, WAL and SHM files are runtime artifacts and
must not enter Git.

`synthetic-preview` is deterministic, visibly synthetic and performs no live
Runtime or Provider operation. `live` consumes only the internal preview API.
Loading, partial, stale, denied, unavailable, not-found, unknown and failure
states remain explicit; live mode never silently falls back to the fixture.

## Validation and CI evidence separation

These evidence classes are independent:

1. Source-head CI: GitHub Actions run `33065548477` completed `SUCCESS` at
   `443214c0a0277473648f68800ad008f981d758c9`; Quality Gates and Frontend
   Quality Gates passed. Source validation recorded 726 passing tests.
2. Integrated-candidate-head CI: required after the final candidate is pushed.
   Its exact run ID and result are GitHub/PR-native evidence and are reported at
   Checkpoint return; this commit cannot refer to its own future CI run.
3. Future exact-main-merge CI: `NOT_AVAILABLE / NOT_AUTHORIZED`. Source or
   candidate CI cannot substitute for validation of a future main merge SHA.

The final candidate gate includes P1 regressions; evidence domain and SQLite;
Task controller/coordinator; snapshot, API, security, Product, Technical,
combined and compatibility/import-ownership tests; standard collection and
duplicate-node audit; full `make check`; Ruff lint and format; clean frontend
install, lint, TypeScript and production build; browser QA; exact path/blob and
provenance checks; API/CRD/schema, authority, Graph, dependency, workflow,
authorization, secret, artifact, claim, relative-link and rollback audits.

## Rollback and unsupported claims

Before any main merge, retain or close the Draft integration PR and retain the
REL branch. If a future Human-authorized main merge occurs, rollback is:

```text
git revert -m 1 <future-main-merge-commit>
```

Rollback does not delete persisted evidence, reverse external effects, replay a
Provider, change CRDs, or perform dependency cleanup.

This candidate remains unmerged. It changes no public API, CRD/schema,
Workflow/Task lifecycle semantics, Canonical Graph semantics, dependency or
lockfile, CI workflow, Runtime Manager, OpenClaw, Hermes, MCP, Knowledge,
Recovery, Golden Demo, Certification, production-readiness, Release-readiness,
or Release-acceptance claim. No downstream task has started. The next decision
is the Human S5-REL-028 Review Gate.
