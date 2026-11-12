import { useEffect, useRef, useState } from "react";
import { readWorkbenchSession } from "../api/businessWorkspace";
import "./ontology.css";
import { ontologyError, validateOntologyImport } from "./ontologyPresentation";

type SalesContent = { schema_version?: "business-ontology.v1"; name: string; business_owner: string; data_owner: string; rules: { included_kinds: string[] }; metrics: { code: string; name: string }[]; mappings: { code: string }[]; objects: { code: string }[] };
type DocumentContent = { schema_version: "business-document-rules.v1"; name: string; business_owner: string; data_owner: string; scope: string; mappings: { code: string }[]; rules: { code: string; name: string; kind: "REQUIRED_SECTION" | "SINGLE_VALUE_FIELD"; section: string; field?: string }[] };
type Content = SalesContent | DocumentContent;
type DocumentCheck = { schemaVersion: string; documentTitle?: string; rulesDigest: string; sourceDigest: string; findings: { ruleCode: string; ruleName: string; status: string; evidence: { documentId: string; line: number; text: string }[] }[] };
function RuleEvidence({ value }: { value: RecordValue }) {
  const checks = value.facts.filter(f => f.action === "TEST").at(-1)?.result?.checks?.filter(c => c.schemaVersion === "document-rule-result.v1") ?? [];
  const status: Record<string, string> = { SATISFIED: "满足", MISSING: "缺失", UNKNOWN: "待确认", CONFLICT: "冲突" };
  if (!checks.length) return null;
  return <section aria-label="文档规则验证结果"><h3>文档规则验证结果</h3><p>规则版本：{value.revision_id}。样本运行完成；以下为逐项业务判定。</p>{checks.map((check, index) => <div key={index}><p>{Object.entries(status).map(([code, label]) => `${check.findings.filter(f => f.status === code).length} 项${label}`).join(" · ")}</p>{check.findings.map(finding => <article key={finding.ruleCode}><h4>{finding.ruleName} · {status[finding.status] ?? finding.status}</h4>{finding.evidence.length ? <ul>{finding.evidence.map((line, i) => <li key={i}>{check.documentTitle ?? "原文"} · 第 {line.line} 行：{line.text}</li>)}</ul> : <p>在绑定原文中未找到相应内容。</p>}</article>)}<details><summary>规则与来源依据</summary><p className="ontology-digest">文档标识：{[...new Set(check.findings.flatMap(f => f.evidence.map(e => e.documentId)))].join("、")}<br/>规则：{check.rulesDigest}<br/>来源：{check.sourceDigest}</p></details></div>)}</section>;
}
type RecordValue = { ontology_id: string; revision_id: string; version: number; digest: string; content: Content; state: string; facts: { action: string; actor: string; result?: { checks?: DocumentCheck[] } }[] };
type Item = { ontology_id: string; revision_id: string; name: string; digest: string; version: number };
const root = "/api/workbench/v1/business-ontologies";
async function request<T>(path: string, payload?: unknown): Promise<T> {
  const session = payload ? await readWorkbenchSession() : null;
  const response = await fetch(root + path, { method: payload ? "POST" : "GET", credentials: "same-origin", headers: { Accept: "application/json", ...(payload ? { "Content-Type": "application/json", "X-CSRF-Token": session!.csrfToken } : {}) }, ...(payload ? { body: JSON.stringify(payload) } : {}) });
  const body = await response.json();
  if (!response.ok) throw new Error(body.reasonCode ?? "当前操作未完成");
  return body.result as T;
}

const labels: Record<string, string> = { CREATE: "草稿已创建", REVISE: "修改草稿已保存", VALIDATE: "定义校验通过", TEST: "样本运行完成", REVIEW: "独立审核通过", PUBLISH: "已发布", DEPRECATE: "已废弃" };
export function OntologyPage() {
  const [items, setItems] = useState<Item[]>([]), [value, setValue] = useState<RecordValue | null>(null);
  const [content, setContent] = useState<Content | null>(null), [identity, setIdentity] = useState("sales-diagnosis"), [revision, setRevision] = useState("r1");
  const [reason, setReason] = useState("业务定义维护"), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const sequence = useRef(0);
  const [fileName, setFileName] = useState("");
  const dirty = !!value && (JSON.stringify(content) !== JSON.stringify(value.content) || revision !== value.revision_id);
  async function refresh() { setItems((await request<{ items: Item[] }>("")).items); }
  useEffect(() => { let active = true; request<{ items: Item[] }>("").then(v => { if (active) setItems(v.items); }).catch(e => { if (active) setMessage(ontologyError(e)); }); return () => { active = false; }; }, []);
  async function load(id: string, rev: string, force = false) {
    if (dirty && !force) { setMessage("有尚未保存的后继编辑，请先创建后继修订或放弃编辑，再切换版本。"); return; }
    const current = ++sequence.current; setBusy(true); setMessage("");
    try { const v = await request<RecordValue>(`/${encodeURIComponent(id)}/revisions/${encodeURIComponent(rev)}`); if (current === sequence.current) { validateOntologyImport(v.content); setValue(v); setContent(v.content); setIdentity(id); setRevision(rev); setFileName(""); setEditing(false); } }
    finally { if (current === sequence.current) setBusy(false); }
  }
  async function act(action: string) {
    setBusy(true); setMessage("");
    try {
      const result = await request<{ revision_id: string }>(`/${encodeURIComponent(identity)}/${action.toLowerCase()}`, { request_key: crypto.randomUUID(), revision_id: action === "REVISE" ? `r-${crypto.randomUUID()}` : revision, expected_version: value?.version ?? 0, reason, ...(["CREATE", "REVISE"].includes(action) ? { content } : { digest: value?.digest }) });
      await load(identity, result.revision_id, true); await refresh(); setMessage(labels[action]);
    } catch (error) { setMessage(ontologyError(error)); } finally { setBusy(false); }
  }
  return <main className="ontology-page"><nav aria-label="面包屑"><a href="/catalog">企业资源</a> / 业务本体</nav><header><p className="ontology-eyebrow">业务标准与口径</p><h1>业务本体</h1><p>管理销售口径与文档核对规则，让每次分析使用可确认、可追溯的业务定义。</p><span className="ontology-badge">合成数据 · 只读验证</span></header>
    <div role="status" aria-live="polite" className="ontology-message">{message}</div>
    <div className="ontology-layout"><section aria-label="业务定义目录"><h2>业务定义目录</h2><p>仅显示当前账号有权查看的修订。</p><button disabled={busy} onClick={() => refresh().catch(e => setMessage(ontologyError(e)))}>刷新目录</button>{items.length === 0 && <p>暂无可见定义。可导入已准备的业务定义包创建草稿。</p>}{items.map(i => <button className="ontology-item" disabled={busy} aria-pressed={value?.ontology_id === i.ontology_id && value?.revision_id === i.revision_id} key={i.ontology_id + i.revision_id} onClick={() => load(i.ontology_id, i.revision_id).catch(e => setMessage(ontologyError(e)))}><strong>{i.name}</strong><span className="ontology-revision">{i.revision_id}</span></button>)}</section>
    <section aria-label="业务定义维护"><h2>{value ? value.content.name : "创建业务定义"}</h2>{!value && <label className="ontology-file">导入业务定义包<span className="ontology-file-button">选择定义文件</span><span className="ontology-file-name">{fileName || "尚未选择文件（JSON）"}</span><input type="file" accept=".json" disabled={busy} onChange={async event => { try { const file = event.target.files?.[0]; if (!file) return; if (file.size > 98304) throw new Error("定义包过大"); const parsed: unknown = JSON.parse(await file.text()); validateOntologyImport(parsed); const v = parsed as Content; setContent(v); setValue(null); setEditing(true); setFileName(file.name); setMessage("定义包已载入，保存后由服务端校验"); } catch (e) { setMessage(ontologyError(e)); } }} /></label>}
    {!value && <label>业务定义标识<input value={identity} onChange={e => setIdentity(e.target.value)} /></label>}
    {dirty && <div className="ontology-notice"><strong>正在编辑后继草稿，已保存修订保持不变。</strong><p>保存后形成修改草稿，验证和发布前不会用于新的执行。</p><button disabled={busy} onClick={() => { setContent(value!.content); setRevision(value!.revision_id); setEditing(false); setMessage("已放弃后继编辑，重新显示已保存修订。"); }}>放弃未保存编辑</button></div>}{content && <><label>业务名称<input disabled={busy || !editing} value={content.name} onChange={e => setContent({ ...content, name: e.target.value })} /></label><div className="ontology-fields"><label>业务负责人<input disabled={busy || !editing} value={content.business_owner} onChange={e => setContent({ ...content, business_owner: e.target.value })} /></label><label>数据负责人<input disabled={busy || !editing} value={content.data_owner} onChange={e => setContent({ ...content, data_owner: e.target.value })} /></label></div>{content.schema_version === "business-document-rules.v1" ? <section aria-label="文档核对规则"><h3>文档核对规则</h3><p>适用范围：{content.scope}</p><ul>{content.rules.map(rule => <li key={rule.code}><strong>{rule.name}</strong> · {rule.kind === "REQUIRED_SECTION" ? "必备章节" : "单一字段值"}<label>核对章节 · {rule.name}<input disabled={busy || !editing} value={rule.section} onChange={event => setContent({ ...content, rules: content.rules.map(item => item.code === rule.code ? { ...item, section: event.target.value } : item) })}/></label>{rule.kind === "SINGLE_VALUE_FIELD" && <label>字段名称 · {rule.name}<input disabled={busy || !editing} value={rule.field ?? ""} onChange={event => setContent({ ...content, rules: content.rules.map(item => item.code === rule.code ? { ...item, field: event.target.value } : item) })}/></label>}</li>)}</ul><p>{content.mappings.length} 个来源映射。满足表示匹配已定义规则，不代表业务内容正确；缺失、待确认和冲突会分别显示。</p></section> : <><label className="ontology-check"><input disabled={busy || !editing} type="checkbox" checked={content.rules.included_kinds.includes("RETURN")} onChange={e => setContent({ ...content, rules: { ...content.rules, included_kinds: e.target.checked ? ["SALE", "RETURN"] : ["SALE"] } })} />销售金额冲减退货</label><p>取消记录始终排除；各币种分别计算。变更口径需创建后继修订并重新审核。</p><h3>指标与对象</h3><ul>{content.metrics.map(m => <li key={m.code}>{m.name}</li>)}</ul><p>{content.objects.length} 类业务对象 · {content.mappings.length} 个来源映射</p></>}</>}
    <label>维护说明<input value={reason} onChange={e => setReason(e.target.value)} /></label><div className="ontology-actions">
      {!value && <button disabled={busy || !content} onClick={() => act("CREATE")}>保存草稿</button>}
      {value && !editing && value.state !== "DEPRECATE" && <button disabled={busy} onClick={() => setEditing(true)}>{value.state === "PUBLISH" ? "修改定义" : "继续编辑"}</button>}
      {value && editing && <><button disabled={busy || !dirty} onClick={() => act("REVISE")}>保存修改</button><button disabled={busy} onClick={() => { setContent(value.content); setEditing(false); }}>取消编辑</button></>}
      {value && !editing && !dirty && ({CREATE:"VALIDATE",REVISE:"VALIDATE",VALIDATE:"TEST",TEST:"REVIEW",REVIEW:"PUBLISH"} as Record<string,string>)[value.state] && <button disabled={busy} onClick={() => act(({CREATE:"VALIDATE",REVISE:"VALIDATE",VALIDATE:"TEST",TEST:"REVIEW",REVIEW:"PUBLISH"} as Record<string,string>)[value.state])}>{({CREATE:"验证定义",REVISE:"验证定义",VALIDATE:"运行样本",TEST:"独立审核",REVIEW:"发布定义"} as Record<string,string>)[value.state]}</button>}
      {value?.state === "TEST" && !editing && <p>当前业务定义发布策略要求由另一位有权限的审核人审核；样本运行完成不代表每项业务规则均满足。</p>}
      {value?.state === "PUBLISH" && !editing && <details><summary>更多操作</summary><button disabled={busy} onClick={() => act("DEPRECATE")}>废弃定义</button></details>}
    </div>
    {value && <><RuleEvidence value={value}/><h3>定义状态：{labels[value.state] ?? value.state}</h3><details><summary>查看变更记录</summary><ol>{value.facts.map((f, i) => <li key={i}>{labels[f.action] ?? f.action} · {f.actor}</li>)}</ol></details><details><summary>查看精确版本与依据</summary><p className="ontology-digest">{value.ontology_id} / {value.revision_id}<br />{value.digest}</p></details>{!dirty && value.content.schema_version !== "business-document-rules.v1" && value.state === "PUBLISH" && <a href={`/ontology/sales?ontology=${encodeURIComponent(value.ontology_id)}&revision=${encodeURIComponent(value.revision_id)}`}>使用此版本进行销售诊断 →</a>}</>}
    </section></div></main>;
}
