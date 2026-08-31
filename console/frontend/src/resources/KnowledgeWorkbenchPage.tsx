import { useEffect, useRef, useState } from "react";
import {
  createKnowledge,
  getKnowledge,
  knowledgeAction,
  listKnowledge,
  purgeKnowledge,
  KnowledgeRequestError,
  type KnowledgeProjection,
  type KnowledgeResource,
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
      if (id) setSelected(await getKnowledge(id));
      setError(null);
      setState("READY");
    } catch (reason) { recordError(reason); }
  }

  useEffect(() => {
    let active = true;
    listKnowledge().then((resources) => {
      if (!active) return;
      setItems(resources); setState("READY");
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

  const value = selected?.knowledge;
  const currentRevision = value?.revisions.find((item) => item.revisionId === (value.currentDraftRevisionId ?? value.publishedRevisionId));
  const source = currentRevision?.content.source;
  const documents = currentRevision?.content.documents ?? [];
  const chunkCount = documents.reduce((total, document) => total + document.chunks.length, 0);
  const latestJob = value?.ingestionJobs.at(-1);
  const recoveryRequired = value?.lifecycleState === "RECOVERY_REQUIRED" || value?.purge?.status === "RECOVERY_REQUIRED";
  const visibleItems = items.filter((item) => `${item.name} ${item.knowledgeId} ${item.lifecycleState}`.toLowerCase().includes(filter.toLowerCase()));

  return <main className="agent-workbench">
    <header><p className="eyebrow">Enterprise Resource Workbench</p><h1>Knowledge Workbench</h1><p>Govern sources, immutable Knowledge Packs, ingestion, authorized retrieval provenance and derived index recovery. Browser state never becomes lifecycle authority.</p></header>
    {state === "LOADING" && <p role="status" className="agent-state">Loading authorized Knowledge resources…</p>}
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

      <section><p className="eyebrow">Citation and provenance</p><h3>Authorized retrieval boundary</h3><p>Provenance is bound to the exact source and revision above. Citation records appear only after an independently authorized retrieval; this Workbench does not infer citations from indexed content.</p><p className="qto-disclosure">Denied and absent Knowledge use the same bounded disclosure. Counts above are rendered only after an authorized scoped aggregate response.</p></section>

      <section><p className="eyebrow">Lifecycle impact</p><h3>Archive and compliance purge</h3><p>Archive removes this Pack from ordinary active views while preserving revision, Citation, Evidence and audit history. Purge is exceptional: it removes prohibited payloads and derived vectors, may require resumable recovery, and preserves only a non-sensitive tombstone.</p><div className="agent-actions"><button onClick={() => void act("archive")}>Archive Pack</button><button onClick={() => purgeDialog.current?.showModal()}>Review purge impact</button></div></section>
      <KnowledgeTechnicalProjection projection={selected} />
    </>}</section></div>

    <dialog ref={purgeDialog} aria-labelledby="knowledge-purge-title"><form method="dialog" onSubmit={(event) => { event.preventDefault(); void purge(); }}><div className="section-heading"><div><p className="eyebrow">Exceptional operation</p><h2 id="knowledge-purge-title">Authorize Knowledge purge</h2></div><button type="button" aria-label="Close purge dialog" onClick={() => purgeDialog.current?.close()}>×</button></div><p>This can remove source, document and chunk payloads plus derived Qdrant vectors. Cross-store completion is resumable and may become RECOVERY_REQUIRED.</p><label>Authorization identity<input required value={authorizationId} onChange={(event) => setAuthorizationId(event.target.value)} /></label><label>Non-sensitive reason classification<input required value={reasonClassification} onChange={(event) => setReasonClassification(event.target.value)} /></label><div className="agent-actions"><button type="button" onClick={() => purgeDialog.current?.close()}>Cancel</button><button className="primary" disabled={state === "SAVING" || !authorizationId || !reasonClassification} type="submit">Confirm authorized purge</button></div></form></dialog>
  </main>;
}
