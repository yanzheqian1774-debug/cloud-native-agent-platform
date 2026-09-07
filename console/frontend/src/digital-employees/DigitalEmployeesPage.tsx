import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { listAgentDefinitions } from "../api/agentDefinitions";
import {
  createEmployeeAssignment, createEmployeeDefinition, createEmployeeInstance,
  decideEmployeeDefinition, DigitalEmployeeRequestError, employeeControlledState,
  getEmployeeAssignment, getEmployeeDefinition, getEmployeeInstance,
  listEmployeeDefinitions, type EmployeeAssignment, type EmployeeDefinition,
  type EmployeeInstance, type EmployeeMember,
} from "../api/digitalEmployees";

type Panel = "definitions" | "create" | "instance" | "assignment";
type Candidate = EmployeeMember & { label: string };
const blank = { id: "", revision: "", role: "", responsibilities: "", agent: "" };
const stage = (item: EmployeeDefinition) => item.published ? "PUBLISHED" : item.facts.some(f => f.action === "APPROVE") ? "HUMAN_REVIEWED" : item.facts.some(f => f.action === "VALIDATE") ? "VALIDATED" : "DRAFT";

export function DigitalEmployeesPage() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<EmployeeDefinition[]>([]);
  const [selected, setSelected] = useState<EmployeeDefinition | null>(null);
  const [agents, setAgents] = useState<Candidate[]>([]);
  const [panel, setPanel] = useState<Panel>((params.get("panel") as Panel) || "definitions");
  const [form, setForm] = useState(blank);
  const [members, setMembers] = useState<EmployeeMember[]>([]);
  const [instanceId, setInstanceId] = useState("");
  const [instance, setInstance] = useState<EmployeeInstance | null>(null);
  const [assignmentForm, setAssignmentForm] = useState({ id: "", assignee: "", role: "", from: "", until: "" });
  const [assignment, setAssignment] = useState<EmployeeAssignment | null>(null);
  const [state, setState] = useState<"LOADING" | "READY" | "SAVING">("LOADING");
  const [error, setError] = useState<{ code: string; kind: string } | null>(null);
  const generation = useRef(0);
  const createTrigger = useRef<HTMLButtonElement>(null);
  const query = params.get("q") ?? "";
  const status = params.get("status") ?? "ALL";
  const visible = useMemo(() => items.filter(item => (status === "ALL" || stage(item) === status) && `${item.employeeDefinitionId} ${item.employeeDefinitionRevisionId} ${item.role} ${item.responsibilities.join(" ")}`.toLowerCase().includes(query.toLowerCase())), [items, query, status]);

  function updateUrl(values: Record<string, string>) { const next = new URLSearchParams(params); Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key)); setParams(next); }
  function fail(reason: unknown) { const value = reason instanceof DigitalEmployeeRequestError ? reason : new DigitalEmployeeRequestError("DIGITAL_EMPLOYEE_UNAVAILABLE", 503); setError({ code: value.reasonCode, kind: employeeControlledState(value) }); setState("READY"); }
  async function load(exact?: { id: string; revision: string }) {
    const turn = ++generation.current; setState("LOADING");
    try {
      const definitions = await listEmployeeDefinitions(); if (turn !== generation.current) return;
      setItems(definitions);
      const fromUrl = params.get("employeeDefinitionId") && params.get("employeeDefinitionRevisionId") ? { id: params.get("employeeDefinitionId")!, revision: params.get("employeeDefinitionRevisionId")! } : undefined;
      const target = exact ?? fromUrl;
      const detail = target ? await getEmployeeDefinition(target.id, target.revision) : definitions[0] ?? null;
      if (turn !== generation.current) return; setSelected(detail); setError(null); setState("READY");
    } catch (reason) { if (turn === generation.current) fail(reason); }
  }
  useEffect(() => {
    const turn = ++generation.current;
    const target = params.get("employeeDefinitionId") && params.get("employeeDefinitionRevisionId") ? { id: params.get("employeeDefinitionId")!, revision: params.get("employeeDefinitionRevisionId")! } : undefined;
    listEmployeeDefinitions().then(async definitions => ({ definitions, detail: target ? await getEmployeeDefinition(target.id, target.revision) : definitions[0] ?? null })).then(({ definitions, detail }) => {
      if (turn !== generation.current) return; setItems(definitions); setSelected(detail); setError(null); setState("READY");
    }).catch(reason => { if (turn === generation.current) fail(reason); });
    return () => { generation.current += 1; };
    // Initial URL context is intentionally captured once; subsequent selection is explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { if (panel !== "create") return; let active = true; listAgentDefinitions().then(values => { if (!active) return; setAgents(values.flatMap(value => { const revision = value.revisions.find(r => r.revisionId === value.publishedRevisionId); return revision && value.enabled && !value.archived ? [{ kind: "AGENT" as const, resourceId: value.definitionId, revisionId: revision.revisionId, digest: revision.digest, label: value.name }] : []; })); }).catch(fail); return () => { active = false; }; }, [panel]);
  function select(item: EmployeeDefinition) { setSelected(item); updateUrl({ panel: "definitions", employeeDefinitionId: item.employeeDefinitionId, employeeDefinitionRevisionId: item.employeeDefinitionRevisionId }); }
  async function act(action: "validate" | "approve" | "publish") {
    if (!selected) return; setState("SAVING");
    try { await decideEmployeeDefinition(selected, action); await load({ id: selected.employeeDefinitionId, revision: selected.employeeDefinitionRevisionId }); }
    catch (reason) { if (reason instanceof DigitalEmployeeRequestError && reason.status === 409) { try { setSelected(await getEmployeeDefinition(selected.employeeDefinitionId, selected.employeeDefinitionRevisionId)); setError({ code: reason.reasonCode, kind: employeeControlledState(reason) }); setState("READY"); return; } catch (readError) { fail(readError); return; } } fail(reason); }
  }
  async function create() {
    const agent = agents.find(value => value.resourceId === form.agent); if (!agent) { setError({ code: "PRIMARY_AGENT_REQUIRED", kind: "validation error" }); return; }
    setState("SAVING"); try {
      const primary: EmployeeMember = { kind: agent.kind, resourceId: agent.resourceId, revisionId: agent.revisionId, digest: agent.digest };
      const value = await createEmployeeDefinition({ employeeDefinitionId: form.id, employeeDefinitionRevisionId: form.revision, role: form.role, responsibilities: form.responsibilities.split("\n").map(value => value.trim()).filter(Boolean), members: [primary, ...members], expectedVersion: 0, commandId: `create:${crypto.randomUUID()}` });
      setForm(blank); setMembers([]); setPanel("definitions"); updateUrl({ panel: "definitions", employeeDefinitionId: value.employeeDefinitionId, employeeDefinitionRevisionId: value.employeeDefinitionRevisionId }); await load({ id: value.employeeDefinitionId, revision: value.employeeDefinitionRevisionId }); queueMicrotask(() => createTrigger.current?.focus());
    } catch (reason) { fail(reason); }
  }
  async function instantiate() { if (!selected || !instanceId.trim()) return; setState("SAVING"); try { const created = await createEmployeeInstance(selected, instanceId.trim()); setInstance(await getEmployeeInstance(created.instanceId)); setError(null); setState("READY"); } catch (reason) { fail(reason); } }
  async function assign() { if (!instance) return; setState("SAVING"); try { await createEmployeeAssignment(instance.instanceId, { assignmentId: assignmentForm.id, assigneeId: assignmentForm.assignee, businessRole: assignmentForm.role, effectiveFrom: new Date(assignmentForm.from).toISOString(), ...(assignmentForm.until ? { effectiveUntil: new Date(assignmentForm.until).toISOString() } : {}) }); setAssignment(await getEmployeeAssignment(instance.instanceId, assignmentForm.id)); setError(null); setState("READY"); } catch (reason) { fail(reason); } }
  const busy = state !== "READY";

  return <main className="px-page px-center-page employee-management">
    <header className="px-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工定义与身份链管理</h1><span>Employee Definition 是独立业务身份；Agent Definition 是精确装配成员；Instance 是另一个持久身份。</span></div><button ref={createTrigger} className="px-primary-button" onClick={() => { setPanel("create"); updateUrl({ panel: "create" }); }}>创建数字员工定义</button></header>
    <section className="px-truth-banner" role="status"><span className="px-status success">MANAGEMENT CONNECTED</span><strong>管理已接通真实 HTTP/PostgreSQL authority</strong><p>发布不代表 matching；执行未连接；三项生命周期操作不会自动串行。</p></section>
    <nav className="px-view-tabs" aria-label="数字员工管理">{([["definitions", "定义"], ["create", "创建装配"], ["instance", "Instance"], ["assignment", "Assignment"]] as const).map(([key, label]) => <button key={key} className={panel === key ? "active" : ""} onClick={() => { setPanel(key); updateUrl({ panel: key }); }}>{label}</button>)}</nav>
    {busy && <p role="status" className="agent-state">{state === "LOADING" ? "正在读取权威数据……" : "正在提交，请勿重复操作……"}</p>}
    {error && <div role="alert" className="qto-alert"><strong>{error.kind}</strong><span>{error.kind === "denied" || error.kind === "not found" ? "资源不可用或当前访问未获授权。" : error.code}</span><button onClick={() => void load(selected ? { id: selected.employeeDefinitionId, revision: selected.employeeDefinitionRevisionId } : undefined)}>重新读取权威状态</button></div>}
    {panel === "definitions" && <div className="px-master-detail"><aside><label className="px-center-search">真实搜索<input value={query} onChange={event => updateUrl({ q: event.target.value })} /></label><label className="px-center-search">生命周期筛选<select value={status} onChange={event => updateUrl({ status: event.target.value })}><option>ALL</option>{["DRAFT", "VALIDATED", "HUMAN_REVIEWED", "PUBLISHED"].map(value => <option key={value}>{value}</option>)}</select></label><nav aria-label="Employee Definition 列表">{visible.map(item => <button key={`${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`} className={selected?.employeeDefinitionRevisionId === item.employeeDefinitionRevisionId ? "selected" : ""} onClick={() => select(item)}><strong>{item.role}</strong><small>{stage(item)} · {item.employeeDefinitionRevisionId}</small></button>)}</nav>{!visible.length && !busy && <div className="px-empty"><strong>没有匹配定义</strong><p>不会用模板或 Agent 身份填充。</p></div>}</aside><section>{selected ? <DefinitionDetail item={selected} busy={busy} act={act} /> : <div className="px-empty large">尚无 Employee Definition</div>}</section></div>}
    {panel === "create" && <section className="px-center-card employee-form"><h2>用真实输入装配</h2><p>主 Agent 选择器只显示 Agent API 返回的已发布、启用资源。其他资源必须粘贴 API 返回的 exact kind/ID/revision/digest；UI 不伪造选项。</p><div className="employee-form-grid"><Field label="Employee Definition ID" value={form.id} set={value => setForm({ ...form, id: value })} /><Field label="Revision ID" value={form.revision} set={value => setForm({ ...form, revision: value })} /><Field label="业务角色" value={form.role} set={value => setForm({ ...form, role: value })} /><label>业务职责（每行一项）<textarea value={form.responsibilities} onChange={event => setForm({ ...form, responsibilities: event.target.value })} /></label><label>主 Agent（必选）<select value={form.agent} onChange={event => setForm({ ...form, agent: event.target.value })}><option value="">请选择可验证 Agent</option>{agents.map(value => <option key={value.resourceId} value={value.resourceId}>{value.label} · {value.revisionId}</option>)}</select></label></div><ExactMemberEditor members={members} setMembers={setMembers} /><button className="px-primary-button" disabled={busy || !form.id || !form.revision || !form.role || !form.responsibilities.trim() || !form.agent} onClick={() => void create()}>仅创建 Draft</button></section>}
    {panel === "instance" && <section className="px-center-card employee-form"><h2>创建或读取 Instance</h2><p>使用当前精确 Employee Definition ID/revision；不会接受 Agent Definition identity 冒充。</p><Field label="Instance ID" value={instanceId} set={setInstanceId} /><div className="agent-actions"><button disabled={!selected?.published || busy || !instanceId} onClick={() => void instantiate()}>创建并权威读回</button><button disabled={busy || !instanceId} onClick={() => { setState("LOADING"); getEmployeeInstance(instanceId).then(value => { setInstance(value); setError(null); setState("READY"); }).catch(fail); }}>按精确 ID 读取</button></div>{instance && <InstanceDetail value={instance} />}</section>}
    {panel === "assignment" && <section className="px-center-card employee-form"><h2>Assignment</h2><p>{instance ? `归属 Instance：${instance.instanceId}` : "请先在 Instance 面板创建或读取实例；当前 API 没有 Assignment 列表。"}</p><div className="employee-form-grid"><Field label="Assignment ID" value={assignmentForm.id} set={value => setAssignmentForm({ ...assignmentForm, id: value })} /><Field label="Assignee ID" value={assignmentForm.assignee} set={value => setAssignmentForm({ ...assignmentForm, assignee: value })} /><Field label="业务角色" value={assignmentForm.role} set={value => setAssignmentForm({ ...assignmentForm, role: value })} /><Field type="datetime-local" label="生效时间" value={assignmentForm.from} set={value => setAssignmentForm({ ...assignmentForm, from: value })} /><Field type="datetime-local" label="结束时间（可选）" value={assignmentForm.until} set={value => setAssignmentForm({ ...assignmentForm, until: value })} /></div><button disabled={!instance || busy || !assignmentForm.id || !assignmentForm.assignee || !assignmentForm.role || !assignmentForm.from} onClick={() => void assign()}>创建并权威读回</button>{assignment && <dl className="employee-facts"><dt>Assignment / Instance</dt><dd>{assignment.assignmentId} / {assignment.instanceId}</dd><dt>状态与角色</dt><dd>{assignment.lifecycle} · {assignment.businessRole}</dd><dt>有效期</dt><dd>{assignment.effectiveFrom} → {assignment.effectiveUntil ?? "无固定结束时间"}</dd></dl>}</section>}
  </main>;
}

function Field({ label, value, set, type = "text" }: { label: string; value: string; set: (value: string) => void; type?: string }) { return <label>{label}<input type={type} value={value} onChange={event => set(event.target.value)} /></label>; }
function ExactMemberEditor({ members, setMembers }: { members: EmployeeMember[]; setMembers: (value: EmployeeMember[]) => void }) { const [draft, setDraft] = useState<EmployeeMember>({ kind: "WORKFLOW", resourceId: "", revisionId: "", digest: "" }); const valid = draft.resourceId && draft.revisionId && /^(sha256:)?[a-f0-9]{64}$/.test(draft.digest) && !(draft.kind === "RUNTIME_PROFILE" && members.some(value => value.kind === draft.kind)) && !members.some(value => value.kind === draft.kind && value.resourceId === draft.resourceId); return <section><h3>其他精确引用（可多项；Runtime 最多一项）</h3><div className="employee-member-row"><select aria-label="资源类型" value={draft.kind} onChange={event => setDraft({ ...draft, kind: event.target.value as EmployeeMember["kind"] })}>{["WORKFLOW", "SKILL", "MCP", "KNOWLEDGE", "RUNTIME_PROFILE"].map(value => <option key={value}>{value}</option>)}</select><input aria-label="Resource ID" placeholder="Resource ID" value={draft.resourceId} onChange={event => setDraft({ ...draft, resourceId: event.target.value })} /><input aria-label="Revision ID" placeholder="Revision ID" value={draft.revisionId} onChange={event => setDraft({ ...draft, revisionId: event.target.value })} /><input aria-label="Digest" placeholder="64 位 digest" value={draft.digest} onChange={event => setDraft({ ...draft, digest: event.target.value })} /><button disabled={!valid} onClick={() => { setMembers([...members, draft]); setDraft({ ...draft, resourceId: "", revisionId: "", digest: "" }); }}>添加引用</button></div><ul className="px-binding-list">{members.map(value => <li key={`${value.kind}:${value.resourceId}`}><span>{value.kind}</span><strong>{value.resourceId}</strong><small>{value.revisionId}</small><button onClick={() => setMembers(members.filter(item => item !== value))}>移除</button></li>)}</ul></section>; }
function DefinitionDetail({ item, busy, act }: { item: EmployeeDefinition; busy: boolean; act: (action: "validate" | "approve" | "publish") => void }) { const current = stage(item); return <article className="px-object-detail"><header><div><span className="px-status info">{current}</span><h2>{item.role}</h2><p>{item.responsibilities.join("；")}</p></div></header><dl><dt>Employee Definition</dt><dd><code>{item.employeeDefinitionId}</code></dd><dt>Revision</dt><dd><code>{item.employeeDefinitionRevisionId}</code></dd><dt>Digest</dt><dd><code>{item.employeeDefinitionDigest}</code></dd><dt>Aggregate version</dt><dd>{item.aggregateVersion}</dd><dt>来源</dt><dd>PostgreSQL Digital Employee Definition authority</dd><dt>Matching</dt><dd>{item.matchable ? "已获独立授权" : "未授权（发布不等于可匹配）"}</dd></dl><section><h3>精确装配成员</h3><ul className="px-binding-list">{item.members.map(member => <li key={`${member.kind}:${member.resourceId}`}><span>{member.kind}</span><strong>{member.resourceId}</strong><small>{member.revisionId}</small><small>{member.digest}</small></li>)}</ul></section><section><h3>独立生命周期操作</h3><div className="agent-actions"><button disabled={busy || current !== "DRAFT"} onClick={() => act("validate")}>验证 exact revision</button><button disabled={busy || current !== "VALIDATED"} onClick={() => act("approve")}>人工审核 exact digest</button><button disabled={busy || current !== "HUMAN_REVIEWED"} onClick={() => act("publish")}>发布 immutable revision</button></div><p>每次仅执行一个操作并权威读回；CAS stale 后只刷新，不自动重放。</p></section><section><h3>决策事实</h3>{item.facts.length ? <ol>{item.facts.map(fact => <li key={fact.ordinal}>{fact.ordinal}. {fact.action} · {fact.decisionId}</li>)}</ol> : <p>尚无事实。Revision history/list API 未提供，保持 OPEN。</p>}</section></article>; }
function InstanceDetail({ value }: { value: EmployeeInstance }) { const reference = value.employeeDefinition ?? value.legacyDefinitionReference; return <dl className="employee-facts"><dt>Instance</dt><dd>{value.instanceId}</dd><dt>Identity boundary</dt><dd>{value.employeeDefinition ? "独立 Employee Definition" : "LEGACY_UNVERIFIED 历史引用（未迁移）"}</dd><dt>Definition/revision</dt><dd>{reference?.employeeDefinitionId} / {reference?.employeeDefinitionRevisionId}</dd><dt>Owner / organization</dt><dd>{value.ownerId} / {value.organizationId}</dd><dt>Lifecycle</dt><dd>{value.lifecycle}</dd><dt>管理 / Matching / Execution</dt><dd>可用 / 未授权 / {value.execution.reasonCode}</dd></dl>; }
