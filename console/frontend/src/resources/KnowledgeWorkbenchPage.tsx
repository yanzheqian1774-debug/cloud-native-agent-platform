import { useEffect, useState } from "react";
import {
  createKnowledge, getKnowledge, knowledgeAction, listKnowledge,
  KnowledgeRequestError, type KnowledgeProjection, type KnowledgeResource,
} from "../api/knowledgeResources";
import { KnowledgeTechnicalProjection } from "./KnowledgeTechnicalProjection";

export function KnowledgeWorkbenchPage() {
  const [items, setItems] = useState<KnowledgeResource[]>([]);
  const [selected, setSelected] = useState<KnowledgeProjection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  async function refresh(id?: string) {
    try { setItems(await listKnowledge()); if (id) setSelected(await getKnowledge(id)); setError(null); }
    catch (reason) { setError(reason instanceof KnowledgeRequestError ? reason.reasonCode : "KNOWLEDGE_UNAVAILABLE"); }
  }
  useEffect(() => {
    let active = true;
    listKnowledge().then((values) => { if (active) setItems(values); }).catch((reason) => {
      if (active) setError(reason instanceof KnowledgeRequestError ? reason.reasonCode : "KNOWLEDGE_UNAVAILABLE");
    });
    return () => { active = false; };
  }, []);
  async function create() {
    setSaving(true); try { const value = await createKnowledge(); await refresh(value.knowledge.knowledgeId); } finally { setSaving(false); }
  }
  async function act(action: string, digest?: string) {
    if (!selected) return;
    setSaving(true);
    try { const value = await knowledgeAction(selected.knowledge.knowledgeId, action, selected.knowledge.aggregateVersion, digest); setSelected(value); await refresh(); }
    catch (reason) { setError(reason instanceof KnowledgeRequestError ? reason.reasonCode : "KNOWLEDGE_ACTION_FAILED"); }
    finally { setSaving(false); }
  }
  const value = selected?.knowledge;
  const draft = value?.revisions.find((item) => item.revisionId === value.currentDraftRevisionId);
  return <main className="agent-workbench">
    <header><p className="eyebrow">Enterprise Resource Workbench</p><h1>Knowledge Workbench</h1><p>Manage governed sources, immutable revisions, ingestion, index snapshots, Evidence and recovery.</p></header>
    {error && <div role="alert"><strong>Action unavailable</strong><span className="technical-value">{error}</span></div>}
    <div className="agent-layout"><aside><h2>Knowledge resources</h2><button disabled={saving} onClick={() => void create()}>Create governed Knowledge source</button><ul className="agent-list">{items.map((item) => <li key={item.knowledgeId}><button onClick={() => void refresh(item.knowledgeId)}><strong>{item.name}</strong><span>{item.lifecycleState} · v{item.aggregateVersion}</span></button></li>)}</ul></aside>
      <section className="agent-detail">{!value ? <p>Select a Knowledge resource.</p> : <><header><p className="eyebrow">{value.lifecycleState}</p><h2>{value.name}</h2><span className="technical-value">{value.knowledgeId}</span></header>
        {draft && <section><h3>Current immutable candidate</h3><label>Exact revision digest<input readOnly value={draft.digest}/></label><div className="agent-actions">{draft.state === "DRAFT" && <button onClick={() => void act("validation")}>Validate draft</button>}{draft.state === "VALIDATED" && <button onClick={() => void act("reviews", draft.digest)}>Human review exact digest</button>}{draft.state === "HUMAN_REVIEWED" && <button onClick={() => void act("publications", draft.digest)}>Publish immutable revision</button>}</div></section>}
        <section><h3>Knowledge operations</h3><div className="agent-actions">{value.publishedRevisionId && <button onClick={() => void act("ingestion")}>Ingest and index</button>}{value.activeIndexSnapshotId && <button onClick={() => void act("rebuild")}>Rebuild derived index</button>}<button onClick={() => void act("archive")}>Archive</button></div><p>{value.ingestionJobs.at(-1)?.status ?? "Not ingested"}</p></section>
        <KnowledgeTechnicalProjection projection={selected} /></>}</section></div>
  </main>;
}
