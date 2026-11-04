import { useEffect, useRef, useState } from "react";
import { readWorkbenchSession } from "../api/businessWorkspace";
import "./ontology.css";
import { ontologyError, validateOntologyImport } from "./ontologyPresentation";

type Content = { name: string; business_owner: string; data_owner: string; rules: { included_kinds: string[] }; metrics: { code: string; name: string }[]; mappings: { code: string }[]; objects: { code: string }[] };
type RecordValue = { ontology_id: string; revision_id: string; version: number; digest: string; content: Content; state: string; facts: { action: string; actor: string }[] };
type Item = { ontology_id: string; revision_id: string; name: string; digest: string; version: number };
const root = "/api/workbench/v1/business-ontologies";
async function request<T>(path: string, payload?: unknown): Promise<T> {
  const session = payload ? await readWorkbenchSession() : null;
  const response = await fetch(root + path, { method: payload ? "POST" : "GET", credentials: "same-origin", headers: { Accept: "application/json", ...(payload ? { "Content-Type": "application/json", "X-CSRF-Token": session!.csrfToken } : {}) }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.reasonCode ?? "当前操作未完成");
  return body.result as T;
}

const labels: Record<string, string> = { CREATE: "草稿已创建", REVISE: "后继草稿", VALIDATE: "定义校验通过", TEST: "样本验证通过", REVIEW: "独立审核通过", PUBLISH: "已发布", DEPRECATE: "已废弃" };
export function OntologyPage() {
  const [items, setItems] = useState<Item[]>([]), [value, setValue] = useState<RecordValue | null>(null);
  const [content, setContent] = useState<Content | null>(null), [identity, setIdentity] = useState("sales-diagnosis"), [revision, setRevision] = useState("r1");
  const [reason, setReason] = useState("销售诊断业务口径维护"), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  const sequence = useRef(0);
  const [fileName, setFileName] = useState("");
  const dirty = !!value && (JSON.stringify(content) !== JSON.stringify(value.content) || revision !== value.revision_id);
  async function refresh() { setItems((await request<{ items: Item[] }>("")).items); }
  useEffect(() => { let active = true; request<{ items: Item[] }>("").then(v => { if (active) setItems(v.items); }).catch(e => { if (active) setMessage(ontologyError(e)); }); return () => { active = false; }; }, []);
  async function load(id: string, rev: string, force = false) {
    if (dirty && !force) { setMessage("有尚未保存的后继编辑，请先创建后继修订或放弃编辑，再切换版本。"); return; }
    const current = ++sequence.current; setBusy(true); setMessage("");
    try { const v = await request<RecordValue>(`/${encodeURIComponent(id)}/revisions/${encodeURIComponent(rev)}`); if (current === sequence.current) { setValue(v); setContent(v.content); setIdentity(id); setRevision(rev); setFileName(""); } }
    finally { if (current === sequence.current) setBusy(false); }
  }
  async function act(action: string) {
    setBusy(true); setMessage("");
    try {
      const result = await request<{ revision_id: string }>(`/${encodeURIComponent(identity)}/${action.toLowerCase()}`, { request_key: crypto.randomUUID(), revision_id: revision, expected_version: value?.version ?? 0, reason, ...(["CREATE", "REVISE"].includes(action) ? { content } : { digest: value?.digest }) });
      await load(identity, result.revision_id, true); await refresh(); setMessage(labels[action]);
    } catch (error) { setMessage(ontologyError(error)); } finally { setBusy(false); }
  }
  return <main className="ontology-page"><nav aria-label="面包屑"><a href="/catalog">企业资源</a> / 业务本体</nav><header><p className="ontology-eyebrow">业务标准与口径</p><h1>业务本体</h1><p>统一销售对象、指标和规则，让每次诊断使用可确认、可追溯的业务定义。</p><span className="ontology-badge">合成数据 · 只读验证</span></header>
    <div role="status" aria-live="polite" className="ontology-message">{message}</div>
    <div className="ontology-layout"><section aria-label="业务定义目录"><h2>业务定义目录</h2><p>仅显示当前账号有权查看的修订。</p><button disabled={busy} onClick={() => refresh().catch(e => setMessage(ontologyError(e)))}>刷新目录</button>{items.length === 0 && <p>暂无可见定义。可导入已准备的业务定义包创建草稿。</p>}{items.map(i => <button className="ontology-item" disabled={busy} aria-pressed={value?.ontology_id === i.ontology_id && value?.revision_id === i.revision_id} key={i.ontology_id + i.revision_id} onClick={() => load(i.ontology_id, i.revision_id).catch(e => setMessage(ontologyError(e)))}><strong>{i.name}</strong><span className="ontology-revision">{i.revision_id}</span></button>)}</section>
    <section aria-label="业务定义维护"><h2>{value ? value.content.name : "创建业务定义"}</h2><label className="ontology-file">导入业务定义包<span className="ontology-file-button">选择定义文件</span><span className="ontology-file-name">{fileName || "尚未选择文件（JSON）"}</span><input type="file" accept=".json" disabled={busy} onChange={async event => { try { const file = event.target.files?.[0]; if (!file) return; if (file.size > 98304) throw new Error("定义包过大"); const parsed: unknown = JSON.parse(await file.text()); validateOntologyImport(parsed); const v = parsed as Content; setContent(v); setValue(null); setFileName(file.name); setMessage("定义包已载入，保存后由服务端校验"); } catch (e) { setMessage(ontologyError(e)); } }} /></label>
    <div className="ontology-fields"><label>业务定义标识<input value={identity} disabled={!!value} onChange={e => setIdentity(e.target.value)} /></label><label>修订标识<input value={revision} onChange={e => setRevision(e.target.value)} /></label></div>
    {dirty && <div className="ontology-notice"><strong>正在编辑后继草稿，已保存修订保持不变。</strong><p>请输入新的修订标识，再创建后继修订并重新审核。尚未保存的修改不会用于诊断。</p><button disabled={busy} onClick={() => { setContent(value!.content); setRevision(value!.revision_id); setMessage("已放弃后继编辑，重新显示已保存修订。"); }}>放弃未保存编辑</button></div>}{content && <><label>业务名称<input value={content.name} onChange={e => setContent({ ...content, name: e.target.value })} /></label><div className="ontology-fields"><label>业务负责人<input value={content.business_owner} onChange={e => setContent({ ...content, business_owner: e.target.value })} /></label><label>数据负责人<input value={content.data_owner} onChange={e => setContent({ ...content, data_owner: e.target.value })} /></label></div><label className="ontology-check"><input type="checkbox" checked={content.rules.included_kinds.includes("RETURN")} onChange={e => setContent({ ...content, rules: { ...content.rules, included_kinds: e.target.checked ? ["SALE", "RETURN"] : ["SALE"] } })} />销售金额冲减退货</label><p>取消记录始终排除；各币种分别计算。变更口径需创建后继修订并重新审核。</p><h3>指标与对象</h3><ul>{content.metrics.map(m => <li key={m.code}>{m.name}</li>)}</ul><p>{content.objects.length} 类业务对象 · {content.mappings.length} 个来源映射</p></>}
    <label>维护说明<input value={reason} onChange={e => setReason(e.target.value)} /></label><div className="ontology-actions"><button disabled={busy || !content || !!value} onClick={() => act("CREATE")}>保存草稿</button><button disabled={busy || !value || revision === value.revision_id} onClick={() => act("REVISE")}>创建后继修订</button>{["VALIDATE", "TEST", "REVIEW", "PUBLISH", "DEPRECATE"].map(a => <button key={a} disabled={busy || dirty || !value || revision !== value.revision_id || !({VALIDATE:["CREATE","REVISE"],TEST:["VALIDATE"],REVIEW:["TEST"],PUBLISH:["REVIEW"],DEPRECATE:["PUBLISH"]} as Record<string,string[]>)[a].includes(value.state)} onClick={() => act(a)}>{({ VALIDATE: "校验定义", TEST: "验证样本", REVIEW: "独立审核", PUBLISH: "发布修订", DEPRECATE: "废弃修订" } as Record<string, string>)[a]}</button>)}</div>
    {value && <><h3>修订状态：{labels[value.state] ?? value.state}</h3><ol>{value.facts.map((f, i) => <li key={i}>{labels[f.action] ?? f.action} · {f.actor}</li>)}</ol><details><summary>查看精确版本与依据</summary><p className="ontology-digest">{value.ontology_id} / {value.revision_id}<br />{value.digest}</p></details>{!dirty && value.state === "PUBLISH" && <a href={`/ontology/sales?ontology=${encodeURIComponent(value.ontology_id)}&revision=${encodeURIComponent(value.revision_id)}`}>使用此版本进行销售诊断 →</a>}</>}
    </section></div></main>;
}
