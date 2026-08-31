import { useEffect, useRef, useState } from "react";
import {
  createKnowledge,
  createKnowledgeSuccessor,
  getKnowledge,
  knowledgeAction,
  listKnowledge,
  purgeKnowledge,
  retrieveKnowledge,
  KnowledgeRequestError,
  type KnowledgeProjection,
  type KnowledgeResource,
  type KnowledgeDashboard,
  type KnowledgeSearchResult,
  getKnowledgeDashboard,
  searchKnowledge,
  evaluateKnowledge,
  summarizeKnowledge,
  scanKnowledgeDuplicates,
  previewKnowledgeImport,
  exportKnowledge,
  executeKnowledgeImport,
  getKnowledgeDuplicateQueue,
  getKnowledgeMetadata,
  decideKnowledgeDuplicate,
  type KnowledgeMetadata,
  type QualityEntity,
} from "../api/knowledgeResources";
import { KnowledgeTechnicalProjection } from "./KnowledgeTechnicalProjection";

const denialCodes = new Set(["KNOWLEDGE_ACCESS_DENIED", "KNOWLEDGE_NOT_FOUND"]);

export function KnowledgeWorkbenchPage() {
  const [items, setItems] = useState<KnowledgeResource[]>([]);
  const [selected, setSelected] = useState<KnowledgeProjection | null>(null);
  const [state, setState] = useState<"LOADING" | "READY" | "SAVING" | "ERROR">("LOADING");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [authorizationId, setAuthorizationId] = useState("");
  const [reasonClassification, setReasonClassification] = useState("");
  const [view, setView] = useState<"PRODUCT" | "TECHNICAL">("PRODUCT");
  const [query, setQuery] = useState("supplier defect containment procedure");
  const [successorContent, setSuccessorContent] = useState("");
  const [dashboard, setDashboard] = useState<KnowledgeDashboard | null>(null);
  const [searchMode, setSearchMode] = useState<"LEXICAL"|"SEMANTIC"|"HYBRID">("HYBRID");
  const [searchResult, setSearchResult] = useState<KnowledgeSearchResult | null>(null);
  const [operationResult, setOperationResult] = useState<Record<string, unknown> | Array<Record<string, unknown>> | null>(null);
  const [metadata, setMetadata] = useState<KnowledgeMetadata | null>(null);
  const [searchFilters, setSearchFilters] = useState<Record<string, string>>({});
  const [evaluationRun, setEvaluationRun] = useState<QualityEntity | null>(null);
  const [importJob, setImportJob] = useState<QualityEntity | null>(null);
  const [duplicateQueue, setDuplicateQueue] = useState<QualityEntity[]>([]);
  const purgeDialog = useRef<HTMLDialogElement>(null);

  function recordError(reason: unknown) {
    const code = reason instanceof KnowledgeRequestError ? reason.reasonCode : "KNOWLEDGE_UNAVAILABLE";
    setError(denialCodes.has(code) ? "KNOWLEDGE_UNAVAILABLE_OR_NOT_AUTHORIZED" : code);
    setState("ERROR");
  }

  async function refresh(id?: string) {
    setState("LOADING");
    try {
      const resources = await listKnowledge();
      setItems(resources);
      setDashboard(await getKnowledgeDashboard());
      setMetadata(await getKnowledgeMetadata());
      if (id) setSelected(await getKnowledge(id));
      setError(null);
      setState("READY");
    } catch (reason) { recordError(reason); }
  }

  useEffect(() => {
    let active = true;
    listKnowledge().then(async (resources) => {
      if (!active) return;
      setItems(resources); setDashboard(await getKnowledgeDashboard()); setMetadata(await getKnowledgeMetadata()); setState("READY");
    }).catch((reason) => { if (active) recordError(reason); });
    return () => { active = false; };
  }, []);

  async function create() {
    setState("SAVING");
    try {
      const value = await createKnowledge();
      setNotice("Authoritative Knowledge draft created.");
      await refresh(value.knowledge.knowledgeId);
    } catch (reason) { recordError(reason); }
  }

  async function act(action: string, digest?: string) {
    if (!selected) return;
    setState("SAVING");
    try {
      const value = await knowledgeAction(selected.knowledge.knowledgeId, action, selected.knowledge.aggregateVersion, digest);
      setSelected(value); setItems(await listKnowledge()); setError(null); setNotice("Knowledge operation recorded by the backend."); setState("READY");
    } catch (reason) { recordError(reason); }
  }

  async function purge() {
    if (!selected || !authorizationId || !reasonClassification) return;
    setState("SAVING");
    try {
      const result = await purgeKnowledge(selected.knowledge.knowledgeId, selected.knowledge.aggregateVersion, authorizationId, reasonClassification);
      purgeDialog.current?.close();
      if ("knowledge" in result) {
        setSelected(result); setNotice("Purge is incomplete. Recovery is required.");
      } else {
        setSelected(null); setNotice("Authorized purge completed; only a non-sensitive tombstone remains.");
      }
      setItems(await listKnowledge()); setError(null); setState("READY");
    } catch (reason) { purgeDialog.current?.close(); recordError(reason); }
  }

  async function retrieve(authorization = "ALLOW") {
    if (!selected) return;
    setState("SAVING");
    try {
      const result = await retrieveKnowledge(selected.knowledge.knowledgeId, selected.knowledge.aggregateVersion, query, authorization);
      setSelected(result); setError(null); setNotice("Authorized retrieval and exact Citations recorded."); setState("READY");
    } catch (reason) { recordError(reason); }
  }

  async function successor() {
    if (!selected || !successorContent) return;
    setState("SAVING");
    try {
      const result = await createKnowledgeSuccessor(selected.knowledge.knowledgeId, selected.knowledge.aggregateVersion, successorContent);
      setSelected(result); setError(null); setNotice("Successor draft created without changing published history."); setState("READY");
    } catch (reason) { recordError(reason); }
  }

  async function qualitySearch() {
    setState("SAVING");
    try { setSearchResult(await searchKnowledge(query, searchMode, 5, { knowledgeId: value?.knowledgeId, ...searchFilters })); setError(null); setState("READY"); }
    catch (reason) { recordError(reason); }
  }

  async function qualityOperation(operation: "evaluation"|"summary"|"duplicates"|"import"|"export") {
    setState("SAVING");
    try {
      let result: Record<string, unknown> | Array<Record<string, unknown>>;
      if (operation === "evaluation") {
        const run = await evaluateKnowledge(query, searchResult?.results.map((item) => item.citation.chunkId) ?? [], searchMode, evaluationRun?.entityId);
        setEvaluationRun(run); result = run;
      }
      else if (operation === "summary" && value) result = await summarizeKnowledge(value.knowledgeId);
      else if (operation === "duplicates") { await scanKnowledgeDuplicates(); const queue = await getKnowledgeDuplicateQueue(); setDuplicateQueue(queue); result = queue; }
      else if (operation === "import") { const job = await previewKnowledgeImport("jsonl", '{"name":"Imported procedure","content":"Authorized draft content."}\n{"name":"","content":"Rejected without disclosure"}'); setImportJob(job); result = job; }
      else result = await exportKnowledge();
      setOperationResult(result); setDashboard(await getKnowledgeDashboard()); setError(null); setState("READY");
    } catch (reason) { recordError(reason); }
  }

  async function executeImport() {
    if (!importJob) return;
    setState("SAVING");
    try { const job = await executeKnowledgeImport(importJob.entityId); setImportJob(job); setOperationResult(job); setItems(await listKnowledge()); setError(null); setState("READY"); }
    catch (reason) { recordError(reason); }
  }

  async function decideDuplicate(candidateId: string, classification: "DUPLICATE"|"DISTINCT"|"NEEDS_INVESTIGATION") {
    setState("SAVING");
    try { await decideKnowledgeDuplicate(candidateId, classification); const queue = await getKnowledgeDuplicateQueue(); setDuplicateQueue(queue); setOperationResult(queue); setError(null); setState("READY"); }
    catch (reason) { recordError(reason); }
  }

  const value = selected?.knowledge;
  const currentRevision = value?.revisions.find((item) => item.revisionId === (value.currentDraftRevisionId ?? value.publishedRevisionId));
  const source = currentRevision?.content.source;
  const documents = currentRevision?.content.documents ?? [];
  const chunkCount = documents.reduce((total, document) => total + document.chunks.length, 0);
  const latestJob = value?.ingestionJobs.at(-1);
  const recoveryRequired = value?.lifecycleState === "RECOVERY_REQUIRED" || value?.purge?.status === "RECOVERY_REQUIRED";
  const visibleItems = items.filter((item) => `${item.name} ${item.knowledgeId} ${item.lifecycleState}`.toLowerCase().includes(filter.toLowerCase()));
  const latestRetrieval = value?.retrievals.at(-1);
  const evaluationBody = evaluationRun?.body as { binding?: { datasetVersionId?: string }; metrics?: { status?: string; recallAtK?: number; precisionAtK?: number; mrr?: number; citationCompleteness?: number }; comparison?: { status?: string; beforeRunId?: string; beforeDatasetVersionId?: string; deltas?: Record<string, number>; claim?: string; reason?: string } } | undefined;
  const importBody = importJob?.body as { status?: string; processedCount?: number; inputRecordCount?: number; acceptedCount?: number; rejectedCount?: number; retryable?: boolean; importedKnowledgeIds?: string[] } | undefined;

  return <main className="agent-workbench">
    <header><p className="eyebrow">Enterprise Resource Workbench</p><h1>Knowledge Workbench</h1><p>Govern sources, immutable Knowledge Packs, ingestion, authorized retrieval provenance and derived index recovery. Browser state never becomes lifecycle authority.</p></header>
    {state === "LOADING" && <p role="status" className="agent-state">Loading authorized Knowledge resources…</p>}
    {state === "SAVING" && <p role="status" className="agent-state">Recording the authorized operation…</p>}
    {notice && <div role="status" className="notice"><strong>{notice}</strong><button onClick={() => setNotice(null)}>Dismiss</button></div>}
    {error && <div role="alert" className="qto-alert"><strong>Knowledge unavailable</strong><span>{error === "KNOWLEDGE_UNAVAILABLE_OR_NOT_AUTHORIZED" ? "The resource is unavailable or you are not authorized to access it." : "The operation could not be completed."}</span><span className="technical-value">{error}</span><button onClick={() => void refresh(value?.knowledgeId)}>Retry</button></div>}

    <section className="agent-dashboard" aria-label="Authorized Knowledge summary">
      <article><strong>{items.length}</strong><span>Knowledge Packs in authorized scope</span></article>
      <article><strong>{items.filter((item) => item.lifecycleState === "AVAILABLE" && !item.archived).length}</strong><span>Published and indexed</span></article>
      <article><strong>{items.filter((item) => item.lifecycleState === "RECOVERY_REQUIRED").length}</strong><span>Recovery required</span></article>
    </section>

    <div className="agent-layout"><aside><div className="agent-list-heading"><h2>Knowledge Packs</h2><button disabled={state === "SAVING"} onClick={() => void create()}>Create governed source</button></div><label>Filter authorized Packs<input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Name, identity or lifecycle" /></label>
      {visibleItems.length === 0 && state === "READY" ? <p className="agent-empty">No authorized Knowledge Packs match this view.</p> : <ul className="agent-list">{visibleItems.map((item) => <li key={item.knowledgeId}><button className={value?.knowledgeId === item.knowledgeId ? "selected" : ""} onClick={() => void refresh(item.knowledgeId)}><strong>{item.name}</strong><span>{item.lifecycleState} · v{item.aggregateVersion}</span></button></li>)}</ul>}
    </aside>

    <section className="agent-detail">{!value ? <div className="agent-empty"><h2>Select a Knowledge Pack</h2><p>Authorized source identity, lifecycle, provenance, index snapshots and impact appear here.</p></div> : <>
      <header><p className="eyebrow">{value.lifecycleState} · {value.archived ? "Archived" : "Active record"}</p><h2>{value.name}</h2><span className="technical-value">{value.knowledgeId}</span></header>
      {recoveryRequired && <div role="alert" className="notice"><strong>RECOVERY_REQUIRED</strong><span>The system cannot prove the cross-store operation completed. Resume recovery before claiming availability or purge completion.</span></div>}

      <div className="agent-view-tabs" role="tablist" aria-label="Knowledge projection"><button role="tab" aria-selected={view === "PRODUCT"} onClick={() => setView("PRODUCT")}>Product View</button><button role="tab" aria-selected={view === "TECHNICAL"} onClick={() => setView("TECHNICAL")}>Technical View</button></div>

      {view === "PRODUCT" ? <>

      <section className="agent-review-card" aria-label="Knowledge quality dashboard"><div className="section-heading"><div><p className="eyebrow">Knowledge Dashboard</p><h3>Retrieval quality and operations</h3></div><span className="status success">{dashboard?.authority ?? "POSTGRESQL"}</span></div>
        <div className="agent-dashboard"><article><strong>{dashboard?.authorizedKnowledgeCount ?? items.length}</strong><span>Authorized Packs</span></article><article><strong>{dashboard?.activeSnapshotCount ?? 0}</strong><span>Active Qdrant snapshots</span></article><article><strong>{dashboard?.evaluationRunCount ?? 0}</strong><span>Evaluation runs</span></article><article><strong>{dashboard?.duplicateCandidateCount ?? 0}</strong><span>Duplicate candidates</span></article></div>
        <p className="qto-disclosure">Counts are scoped after authorization. PostgreSQL is authoritative; Qdrant is a derived semantic index.</p>
      </section>

      <section className="agent-review-card"><div className="section-heading"><div><p className="eyebrow">Source and Pack</p><h3>{currentRevision?.state ?? "NO_REVISION"} lifecycle</h3></div><span className={`status ${currentRevision?.state === "PUBLISHED" ? "success" : "warning"}`}>{currentRevision?.state ?? "UNKNOWN"}</span></div>
        <dl><dt>Source identity</dt><dd className="technical-value">{source?.sourceId ?? "NOT_RECORDED"}</dd><dt>Source kind</dt><dd>{source?.kind ?? "NOT_RECORDED"}</dd><dt>Provenance</dt><dd className="technical-value">{source?.provenance ?? "NOT_RECORDED"}</dd><dt>Knowledge Pack identity</dt><dd className="technical-value">{value.knowledgeId}</dd></dl>
        <div className="agent-dashboard"><article><strong>{documents.length}</strong><span>Authorized documents</span></article><article><strong>{chunkCount}</strong><span>Authorized chunks</span></article><article><strong>{value.revisions.length}</strong><span>Immutable revisions</span></article></div>
        {currentRevision && <label>Exact revision digest<input readOnly value={currentRevision.digest}/></label>}
        <div className="agent-actions">{currentRevision?.state === "DRAFT" && <button onClick={() => void act("validation")}>Validate draft</button>}{currentRevision?.state === "VALIDATED" && <button onClick={() => void act("reviews", currentRevision.digest)}>Human review exact digest</button>}{currentRevision?.state === "HUMAN_REVIEWED" && <button className="primary" onClick={() => void act("publications", currentRevision.digest)}>Publish immutable revision</button>}</div>
      </section>

      <section><div className="section-heading"><div><p className="eyebrow">Knowledge Operations</p><h3>Ingestion and derived index</h3></div><span className={`status ${latestJob?.status === "COMPLETED" ? "success" : latestJob ? "warning" : "neutral"}`}>{latestJob?.status ?? "NOT_INGESTED"}</span></div>
        <dl><dt>Ingestion job</dt><dd className="technical-value">{latestJob?.jobId ?? "NOT_STARTED"}</dd><dt>Source high-water mark</dt><dd>{latestJob?.highWaterMark ?? "NOT_RECORDED"}</dd><dt>Active index snapshot</dt><dd className="technical-value">{value.activeIndexSnapshotId ?? "NOT_INDEXED"}</dd></dl>
        <div className="agent-actions">{value.publishedRevisionId && !recoveryRequired && <button className="primary" onClick={() => void act("ingestion")}>Ingest and index</button>}{value.activeIndexSnapshotId && !recoveryRequired && <button onClick={() => void act("rebuild")}>Rebuild derived index</button>}{recoveryRequired && <button className="primary" onClick={() => void act("recovery")}>Resume recovery</button>}</div>
      </section>

      <section className="agent-section"><p className="eyebrow">Citation and provenance</p><h3>Authorized retrieval</h3><p>Provenance is bound to the exact source and revision. Citation records appear only after backend authorization and retrieval.</p><label>Retrieval query<input value={query} onChange={(event) => setQuery(event.target.value)} /></label><div className="agent-actions"><button className="primary" disabled={!value.activeIndexSnapshotId} onClick={() => void retrieve()}>Run authorized retrieval</button><button onClick={() => void retrieve("DENY")}>Verify denied disclosure</button></div>{latestRetrieval && <div className="knowledge-citations"><p className="technical-value">Authorization: {latestRetrieval.authorizationDecisionId}</p>{latestRetrieval.citations.map((citation) => <article key={citation.citationId}><span className="agent-status status-succeeded">CITATION</span><strong>{citation.documentId} · {citation.chunkId}</strong><p>{citation.content}</p><small>Source {citation.sourceId} · Provenance {citation.provenance}</small></article>)}</div>}<p className="qto-disclosure">Denied and absent Knowledge use the same bounded disclosure. Counts above are rendered only after an authorized scoped aggregate response.</p></section>

      <section className="agent-section" aria-label="Search Playground"><p className="eyebrow">Search Playground</p><h3>Inspect authorized raw recall, ranks and Citations</h3><label>Retrieval classification<select aria-label="Retrieval classification" value={searchMode} onChange={(event) => setSearchMode(event.target.value as typeof searchMode)}><option>LEXICAL</option><option>SEMANTIC</option><option>HYBRID</option></select></label>
        <div className="agent-dashboard" aria-label="Authorized metadata filters">{metadata && (["sourceId","documentId","contentType","revisionId","snapshotId"] as const).map((key) => <label key={key}>{key}<select aria-label={`Filter ${key}`} value={searchFilters[key] ?? ""} onChange={(event) => setSearchFilters((current) => ({...current,[key]:event.target.value}))}><option value="">Any authorized value</option>{metadata[key].map((option) => <option key={option} value={option}>{option}</option>)}</select></label>)}</div>
        <div className="agent-actions"><button className="primary" disabled={state === "SAVING"} onClick={() => void qualitySearch()}>Run Search Playground</button><button disabled={!searchResult || state === "SAVING"} onClick={() => void qualityOperation("evaluation")}>{evaluationRun ? "Compare evaluation run" : "Evaluate current result"}</button></div>
        {searchResult && <><p className="technical-value">{searchResult.classification} · {searchResult.tokenizerVersion} · RRF k={searchResult.fusion.k}</p>{searchResult.results.length === 0 ? <p className="agent-empty">No authorized results match this query and filter context.</p> : <table><thead><tr><th>Rank</th><th>Score</th><th>Citation</th></tr></thead><tbody>{searchResult.results.map((result) => <tr key={result.citation.chunkId}><td>{result.rank}</td><td>{result.score}</td><td><strong>{result.citation.documentId} · {result.citation.chunkId}</strong><p>{result.citation.content}</p></td></tr>)}</tbody></table>}</>}
        {evaluationRun && <article aria-label="Evaluation comparison"><h4>Evaluation evidence</h4><dl><dt>Run identity</dt><dd className="technical-value">{evaluationRun.entityId}</dd><dt>Dataset identity</dt><dd className="technical-value">{evaluationBody?.binding?.datasetVersionId}</dd><dt>Metric status</dt><dd>{evaluationBody?.metrics?.status}</dd>{evaluationBody?.comparison && <><dt>Before run</dt><dd className="technical-value">{evaluationBody.comparison.beforeRunId}</dd><dt>Before dataset</dt><dd className="technical-value">{evaluationBody.comparison.beforeDatasetVersionId}</dd><dt>Comparison</dt><dd>{evaluationBody.comparison.status} · {evaluationBody.comparison.claim ?? evaluationBody.comparison.reason}</dd></>}</dl>{evaluationBody?.comparison?.deltas && <table><thead><tr><th>Metric</th><th>Delta</th></tr></thead><tbody>{Object.entries(evaluationBody.comparison.deltas).map(([metric,delta]) => <tr key={metric}><td>{metric}</td><td>{delta}</td></tr>)}</tbody></table>}</article>}
      </section>

      <section className="agent-section" aria-label="Knowledge operations"><p className="eyebrow">Quality Operations</p><h3>Summaries, duplicate review and transfer</h3><div className="agent-actions"><button onClick={() => void qualityOperation("summary")}>Generate extractive summary</button><button onClick={() => void qualityOperation("duplicates")}>Scan duplicates</button><button onClick={() => void qualityOperation("import")}>Preview bounded import</button><button onClick={() => void qualityOperation("export")}>Export authorized facts</button></div>
        {importJob && <article aria-label="Import execution"><h4>Import {importBody?.status}</h4><p className="technical-value">{importJob.entityId}</p><dl><dt>Progress</dt><dd>{importBody?.processedCount ?? 0} / {importBody?.inputRecordCount}</dd><dt>Accepted Drafts</dt><dd>{importBody?.acceptedCount ?? 0}</dd><dt>Rejected records</dt><dd>{importBody?.rejectedCount ?? 0}</dd><dt>Retryable</dt><dd>{String(importBody?.retryable ?? false)}</dd></dl><div className="agent-actions"><button className="primary" disabled={state === "SAVING" || importBody?.status === "COMPLETED"} onClick={() => void executeImport()}>{importBody?.status === "PARTIAL" ? "Retry controlled import" : "Execute accepted preview"}</button></div><p>Imported content remains Draft and requires separate validation, Human review and publication.</p></article>}
        {duplicateQueue.length > 0 && <div aria-label="Duplicate review queue"><h4>Human duplicate-review queue</h4>{duplicateQueue.map((candidate) => { const body = candidate.body as { classification?:string;algorithmVersion?:string;threshold?:number;left?:{sourceId?:string;documentId?:string;chunkId?:string};right?:{sourceId?:string;documentId?:string;chunkId?:string} }; return <article key={candidate.entityId}><strong>{body.classification} candidate</strong><p className="technical-value">{candidate.entityId}</p><p>{body.algorithmVersion} · threshold {body.threshold}</p><p>{body.left?.sourceId} / {body.left?.documentId} / {body.left?.chunkId}<br/>{body.right?.sourceId} / {body.right?.documentId} / {body.right?.chunkId}</p>{candidate.decision ? <span className="status success">Human decision recorded</span> : <div className="agent-actions"><button onClick={() => void decideDuplicate(candidate.entityId,"DUPLICATE")}>Classify duplicate</button><button onClick={() => void decideDuplicate(candidate.entityId,"DISTINCT")}>Classify distinct</button><button onClick={() => void decideDuplicate(candidate.entityId,"NEEDS_INVESTIGATION")}>Needs investigation</button></div>}</article>})}</div>}
        {operationResult && !importJob && duplicateQueue.length === 0 && <pre className="technical-value">{JSON.stringify(operationResult, null, 2)}</pre>}<p className="qto-disclosure">Summaries are DETERMINISTIC_EXTRACTIVE_V1 with model NOT_APPLICABLE. Duplicate decisions record facts only; no content is deleted, merged or rewritten.</p></section>

      {value.publishedRevisionId && !value.currentDraftRevisionId && <section className="agent-section"><p className="eyebrow">Successor revision</p><h3>Update source content</h3><p>The published revision remains immutable. Updated sanitized content creates a successor draft and requires the full exact-digest lifecycle.</p><label>Successor source content<textarea rows={5} value={successorContent} onChange={(event) => setSuccessorContent(event.target.value)} /></label><div className="agent-actions"><button disabled={!successorContent} onClick={() => void successor()}>Create successor draft</button></div></section>}

      <section className="agent-section"><p className="eyebrow">Lifecycle impact</p><h3>Archive and compliance purge</h3><p>Archive removes this Pack from ordinary active views while preserving revision, Citation, Evidence and audit history. Purge is exceptional: it removes prohibited payloads and derived vectors, may require resumable recovery, and preserves only a non-sensitive tombstone.</p><div className="agent-actions"><button onClick={() => void act("archive")}>Archive Pack</button><button className="danger" onClick={() => purgeDialog.current?.showModal()}>Review purge impact</button></div></section>
      </> : <KnowledgeTechnicalProjection projection={selected} />}
    </>}</section></div>

    <dialog ref={purgeDialog} aria-labelledby="knowledge-purge-title"><form method="dialog" onSubmit={(event) => { event.preventDefault(); void purge(); }}><div className="section-heading"><div><p className="eyebrow">Exceptional operation</p><h2 id="knowledge-purge-title">Authorize Knowledge purge</h2></div><button type="button" aria-label="Close purge dialog" onClick={() => purgeDialog.current?.close()}>×</button></div><p>This can remove source, document and chunk payloads plus derived Qdrant vectors. Cross-store completion is resumable and may become RECOVERY_REQUIRED.</p><label>Authorization identity<input required value={authorizationId} onChange={(event) => setAuthorizationId(event.target.value)} /></label><label>Non-sensitive reason classification<input required value={reasonClassification} onChange={(event) => setReasonClassification(event.target.value)} /></label><div className="agent-actions"><button type="button" onClick={() => purgeDialog.current?.close()}>Cancel</button><button className="primary" disabled={state === "SAVING" || !authorizationId || !reasonClassification} type="submit">Confirm authorized purge</button></div></form></dialog>
  </main>;
}
