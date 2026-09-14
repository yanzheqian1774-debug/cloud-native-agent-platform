import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  DigitalEmployeeRequestError,
  employeeControlledState,
  getEmployeeAssignment,
  getEmployeeDefinition,
  getEmployeeInstance,
  listAgentDefinitions,
  listEmployeeDefinitions,
  type AgentDefinitionSummary,
  type EmployeeAssignment,
  type EmployeeCommandResult,
  type EmployeeDefinition,
  type EmployeeDefinitionSummary,
  type EmployeeInstance,
  type WorkbenchPage,
} from "../api/digitalEmployees";
import { EmployeeDefinitionAssembly } from "./EmployeeDefinitionAssembly";
import { EmployeeLifecycleActions } from "./EmployeeLifecycleActions";
import { EmployeeProfileLoader } from "./EmployeeProfile";
import { EmployeeWorkParticipation } from "./EmployeeWorkParticipation";

type PageMode = "employees" | "create";
type DetailSection = "overview" | "capabilities" | "instances" | "assignments";
type ReadError = { code: string; kind: string };
type ExactDefinition = { id: string; revision: string; digest?: string };
type CachedPage = WorkbenchPage<EmployeeDefinitionSummary> & { cursor?: string };

function exactFromSummary(item: EmployeeDefinitionSummary): ExactDefinition {
  return { id: item.employeeDefinitionId, revision: item.employeeDefinitionRevisionId, digest: item.employeeDefinitionDigest };
}

function exactKey(value: Pick<ExactDefinition, "id" | "revision">) {
  return `${value.id}\u0000${value.revision}`;
}

function shortIdentity(value: string) {
  return value.length <= 30 ? value : `${value.slice(0, 16)}…${value.slice(-9)}`;
}

function toReadError(reason: unknown): ReadError {
  const value = reason instanceof DigitalEmployeeRequestError
    ? reason
    : new DigitalEmployeeRequestError("WORKBENCH_READ_UNAVAILABLE", 503);
  return { code: value.reasonCode, kind: employeeControlledState(value) };
}

function controlledMessage(error: ReadError) {
  if (error.kind === "authentication required") return "需要可信 Workbench session。";
  if (error.kind === "denied" || error.kind === "not found") return "资源不可用或当前访问未获授权。";
  return error.code;
}

async function readInstanceDefinition(value: EmployeeInstance, selected?: ExactDefinition, signal?: AbortSignal) {
  const reference = value.employeeDefinition;
  if (!reference) throw new DigitalEmployeeRequestError("INSTANCE_DEFINITION_NOT_VERIFIABLE", 409);
  if (selected && (reference.employeeDefinitionId !== selected.id
    || reference.employeeDefinitionRevisionId !== selected.revision
    || (selected.digest && reference.digest !== selected.digest))) {
    throw new DigitalEmployeeRequestError("INSTANCE_NOT_RELATED_TO_SELECTED_EMPLOYEE", 409);
  }
  const definition = await getEmployeeDefinition(reference.employeeDefinitionId, reference.employeeDefinitionRevisionId, signal);
  if (definition.employeeDefinitionId !== reference.employeeDefinitionId
    || definition.employeeDefinitionRevisionId !== reference.employeeDefinitionRevisionId
    || definition.employeeDefinitionDigest !== reference.digest) {
    throw new DigitalEmployeeRequestError("INSTANCE_DEFINITION_IDENTITY_MISMATCH", 409);
  }
  return definition;
}

function verifyAssignmentInstance(value: EmployeeAssignment, instanceId: string, assignmentId: string) {
  if (value.instanceId !== instanceId) throw new DigitalEmployeeRequestError("ASSIGNMENT_INSTANCE_IDENTITY_MISMATCH", 409);
  if (value.assignmentId !== assignmentId) throw new DigitalEmployeeRequestError("ASSIGNMENT_IDENTITY_MISMATCH", 409);
  return value;
}

export function DigitalEmployeesPage() {
  const [params, setParams] = useSearchParams();
  const legacyPanel = params.get("panel");
  const [mode, setMode] = useState<PageMode>(params.get("mode") === "create" || legacyPanel === "create" ? "create" : "employees");
  const [detailSection, setDetailSection] = useState<DetailSection>((params.get("section") as DetailSection)
    || (legacyPanel === "instance" ? "instances" : legacyPanel === "assignment" || legacyPanel === "work" ? "assignments" : "overview"));
  const [pages, setPages] = useState<CachedPage[]>([]);
  const [pageIndex, setPageIndex] = useState(0);
  const [selectedIdentity, setSelectedIdentity] = useState<ExactDefinition | null>(null);
  const [selected, setSelected] = useState<EmployeeDefinition | null>(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const [agents, setAgents] = useState<AgentDefinitionSummary[]>([]);
  const [agentNextCursor, setAgentNextCursor] = useState<string>();
  const [instanceId, setInstanceId] = useState(params.get("instanceId") ?? "");
  const [assignmentId, setAssignmentId] = useState(params.get("assignmentId") ?? "");
  const [instance, setInstance] = useState<EmployeeInstance | null>(null);
  const [instanceDefinition, setInstanceDefinition] = useState<EmployeeDefinition | null>(null);
  const [assignment, setAssignment] = useState<EmployeeAssignment | null>(null);
  const [listState, setListState] = useState<"LOADING" | "READY">("LOADING");
  const [detailState, setDetailState] = useState<"LOADING" | "READY">("READY");
  const [workState, setWorkState] = useState<"READY" | "LOADING">("READY");
  const [listError, setListError] = useState<ReadError | null>(null);
  const [detailError, setDetailError] = useState<ReadError | null>(null);
  const [workError, setWorkError] = useState<ReadError | null>(null);
  const [agentError, setAgentError] = useState<ReadError | null>(null);
  const [latestCommand, setLatestCommand] = useState<EmployeeCommandResult | null>(null);
  const listGeneration = useRef(0);
  const detailGeneration = useRef(0);
  const workGeneration = useRef(0);
  const activeDetailRead = useRef<AbortController | null>(null);
  const activeWorkRead = useRef<AbortController | null>(null);
  const listScroll = useRef<HTMLDivElement | null>(null);
  const savedListScroll = useRef(0);
  const query = params.get("q") ?? "";
  const status = params.get("status") ?? "ALL";
  const items = useMemo(() => pages[pageIndex]?.items ?? [], [pages, pageIndex]);
  const currentPage = pages[pageIndex];

  const filteredRevisions = useMemo(() => items.filter(item =>
    (status === "ALL" || item.publicationState === status)
    && `${item.employeeDefinitionId} ${item.employeeDefinitionRevisionId} ${item.role}`.toLowerCase().includes(query.toLowerCase())), [items, query, status]);

  const groups = useMemo(() => {
    const grouped = new Map<string, EmployeeDefinitionSummary[]>();
    filteredRevisions.forEach(item => grouped.set(item.employeeDefinitionId, [...(grouped.get(item.employeeDefinitionId) ?? []), item]));
    return [...grouped.entries()].map(([id, revisions]) => ({ id, revisions }));
  }, [filteredRevisions]);

  function updateUrl(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setParams(next);
  }

  function resetRelatedContext() {
    workGeneration.current += 1;
    activeWorkRead.current?.abort();
    setInstance(null);
    setInstanceDefinition(null);
    setAssignment(null);
    setWorkError(null);
    setWorkState("READY");
    setInstanceId("");
    setAssignmentId("");
  }

  function discardSelection() {
    detailGeneration.current += 1;
    activeDetailRead.current?.abort();
    setSelectedIdentity(null);
    setSelected(null);
    setDetailError(null);
    setDetailState("READY");
    setMobileDetailOpen(false);
    resetRelatedContext();
  }

  function clearSelection() {
    discardSelection();
    updateUrl({ employeeDefinitionId: "", employeeDefinitionRevisionId: "", instanceId: "", assignmentId: "", placementId: "", attemptId: "", agentInstanceId: "" });
  }

  function changeFilter(key: "q" | "status", value: string) {
    discardSelection();
    updateUrl({ [key]: value, employeeDefinitionId: "", employeeDefinitionRevisionId: "", detail: "", instanceId: "", assignmentId: "", placementId: "", attemptId: "", agentInstanceId: "" });
  }

  async function readDefinitionExact(exact: ExactDefinition, openDetail = false) {
    const turn = ++detailGeneration.current;
    activeDetailRead.current?.abort();
    const controller = new AbortController();
    activeDetailRead.current = controller;
    if (selectedIdentity && exactKey(selectedIdentity) !== exactKey(exact)) resetRelatedContext();
    setSelectedIdentity(exact);
    setSelected(null);
    setDetailError(null);
    setDetailState("LOADING");
    if (openDetail) {
      savedListScroll.current = listScroll.current?.scrollTop ?? 0;
      setMobileDetailOpen(true);
    }
    try {
      const value = await getEmployeeDefinition(exact.id, exact.revision, controller.signal);
      if (value.employeeDefinitionId !== exact.id
        || value.employeeDefinitionRevisionId !== exact.revision
        || (exact.digest && value.employeeDefinitionDigest !== exact.digest)) {
        throw new DigitalEmployeeRequestError("EMPLOYEE_DEFINITION_IDENTITY_MISMATCH", 409);
      }
      if (turn !== detailGeneration.current) return;
      setSelected(value);
      setSelectedIdentity(exactFromSummary(value));
      setDetailState("READY");
    } catch (reason) {
      if (turn !== detailGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setSelected(null);
      setDetailError(toReadError(reason));
      setDetailState("READY");
    }
  }

  async function loadEmployeePage(cursor?: string, targetIndex = 0) {
    const turn = ++listGeneration.current;
    setListState("LOADING");
    try {
      const page = await listEmployeeDefinitions(cursor);
      if (turn !== listGeneration.current) return;
      const cached = { ...page, cursor };
      setPages(current => targetIndex < current.length
        ? current.map((value, index) => index === targetIndex ? cached : value)
        : [...current, cached]);
      setPageIndex(targetIndex);
      setListError(null);
      setListState("READY");
    } catch (reason) {
      if (turn !== listGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setListError(toReadError(reason));
      setListState("READY");
    }
  }

  async function restoreWorkContext(expected: ExactDefinition | null) {
    const knownInstanceId = params.get("instanceId");
    const knownAssignmentId = params.get("assignmentId");
    if (!knownInstanceId) return;
    const turn = ++workGeneration.current;
    const controller = new AbortController();
    activeWorkRead.current = controller;
    setWorkState("LOADING");
    try {
      const value = await getEmployeeInstance(knownInstanceId, controller.signal);
      if (value.instanceId !== knownInstanceId) throw new DigitalEmployeeRequestError("INSTANCE_IDENTITY_MISMATCH", 409);
      const definition = await readInstanceDefinition(value, expected ?? undefined, controller.signal);
      const assignmentValue = knownAssignmentId
        ? verifyAssignmentInstance(await getEmployeeAssignment(knownInstanceId, knownAssignmentId, controller.signal), knownInstanceId, knownAssignmentId)
        : null;
      if (turn !== workGeneration.current) return;
      setSelected(definition);
      setSelectedIdentity(exactFromSummary(definition));
      setInstance(value);
      setInstanceDefinition(definition);
      setAssignment(assignmentValue);
      setDetailSection(assignmentValue ? "assignments" : "instances");
      setWorkError(null);
      setWorkState("READY");
      setMobileDetailOpen(Boolean(params.get("detail")) || legacyPanel === "instance" || legacyPanel === "assignment" || legacyPanel === "work");
    } catch (reason) {
      if (turn !== workGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setSelected(null);
      setInstance(null);
      setInstanceDefinition(null);
      setAssignment(null);
      setWorkError(toReadError(reason));
      setWorkState("READY");
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    const turn = ++listGeneration.current;
    const fromUrl = params.get("employeeDefinitionId") && params.get("employeeDefinitionRevisionId")
      ? { id: params.get("employeeDefinitionId")!, revision: params.get("employeeDefinitionRevisionId")! }
      : null;
    if (params.get("instanceId")) queueMicrotask(() => void restoreWorkContext(fromUrl));
    else if (fromUrl) queueMicrotask(() => void readDefinitionExact(fromUrl, Boolean(params.get("detail"))));
    listEmployeeDefinitions(undefined, controller.signal).then(page => {
      if (turn !== listGeneration.current) return;
      setPages([{ ...page, cursor: undefined }]);
      setListError(null);
      setListState("READY");
    }).catch(reason => {
      if (turn !== listGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setListError(toReadError(reason));
      setListState("READY");
    });
    return () => {
      controller.abort();
      activeDetailRead.current?.abort();
      activeWorkRead.current?.abort();
      listGeneration.current += 1;
      detailGeneration.current += 1;
      workGeneration.current += 1;
    };
    // Initial route coordinates are consumed once; later changes are explicit UI actions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mode !== "create" || agents.length || agentError) return;
    const controller = new AbortController();
    listAgentDefinitions(undefined, controller.signal).then(page => {
      setAgents(page.items);
      setAgentNextCursor(page.nextCursor);
      setAgentError(null);
    }).catch(reason => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      setAgentError(toReadError(reason));
    });
    return () => controller.abort();
  }, [mode, agents.length, agentError]);

  async function loadMoreAgents() {
    if (!agentNextCursor) return;
    try {
      const page = await listAgentDefinitions(agentNextCursor);
      setAgents(current => {
        const known = new Set(current.map(item => `${item.definitionId}\u0000${item.revisionId}`));
        return [...current, ...page.items.filter(item => !known.has(`${item.definitionId}\u0000${item.revisionId}`))];
      });
      setAgentNextCursor(page.nextCursor);
      setAgentError(null);
    } catch (reason) {
      setAgentError(toReadError(reason));
    }
  }

  function select(item: EmployeeDefinitionSummary) {
    const exact = exactFromSummary(item);
    setDetailSection("overview");
    updateUrl({ mode: "employees", section: "overview", detail: "open", employeeDefinitionId: exact.id, employeeDefinitionRevisionId: exact.revision });
    void readDefinitionExact(exact, true);
  }

  function showSection(section: DetailSection) {
    setDetailSection(section);
    updateUrl({ section });
  }

  function applyCommandReadback(definition: EmployeeDefinition, result: EmployeeCommandResult) {
    const summary: EmployeeDefinitionSummary = {
      employeeDefinitionId: definition.employeeDefinitionId,
      employeeDefinitionRevisionId: definition.employeeDefinitionRevisionId,
      employeeDefinitionDigest: definition.employeeDefinitionDigest,
      role: definition.role,
      publicationState: definition.publicationState,
    };
    setLatestCommand(result);
    setSelected(definition);
    setSelectedIdentity(exactFromSummary(summary));
    setPages(current => current.map((page, index) => index === pageIndex
      ? { ...page, items: [summary, ...page.items.filter(item => exactKey(exactFromSummary(item)) !== exactKey(exactFromSummary(summary)))] }
      : page));
    setMode("employees");
    setMobileDetailOpen(true);
    updateUrl({ mode: "employees", detail: "open", employeeDefinitionId: summary.employeeDefinitionId, employeeDefinitionRevisionId: summary.employeeDefinitionRevisionId });
  }

  async function readInstanceExact(id = instanceId.trim()) {
    if (!id || !selectedIdentity) return;
    const turn = ++workGeneration.current;
    activeWorkRead.current?.abort();
    const controller = new AbortController();
    activeWorkRead.current = controller;
    setWorkState("LOADING");
    setWorkError(null);
    try {
      const value = await getEmployeeInstance(id, controller.signal);
      if (value.instanceId !== id) throw new DigitalEmployeeRequestError("INSTANCE_IDENTITY_MISMATCH", 409);
      const definition = await readInstanceDefinition(value, selectedIdentity, controller.signal);
      if (turn !== workGeneration.current) return;
      setInstance(value);
      setInstanceDefinition(definition);
      setAssignment(null);
      setAssignmentId("");
      setWorkState("READY");
      updateUrl({ instanceId: value.instanceId, assignmentId: "", placementId: "", attemptId: "", agentInstanceId: "" });
    } catch (reason) {
      if (turn !== workGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setInstance(null);
      setInstanceDefinition(null);
      setAssignment(null);
      setWorkError(toReadError(reason));
      setWorkState("READY");
    }
  }

  async function readAssignmentExact(id = assignmentId.trim()) {
    if (!instance || !id) return;
    const turn = ++workGeneration.current;
    activeWorkRead.current?.abort();
    const controller = new AbortController();
    activeWorkRead.current = controller;
    setWorkState("LOADING");
    setWorkError(null);
    try {
      const value = verifyAssignmentInstance(await getEmployeeAssignment(instance.instanceId, id, controller.signal), instance.instanceId, id);
      if (turn !== workGeneration.current) return;
      setAssignment(value);
      setWorkState("READY");
      updateUrl({ instanceId: instance.instanceId, assignmentId: value.assignmentId, placementId: "", attemptId: "", agentInstanceId: "" });
    } catch (reason) {
      if (turn !== workGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setAssignment(null);
      setWorkError(toReadError(reason));
      setWorkState("READY");
    }
  }

  const detailBusy = detailState === "LOADING";
  const workBusy = workState === "LOADING";
  const publishedRevisions = items.filter(item => item.publicationState === "PUBLISHED").length;

  return <main className="px-page px-center-page employee-management">
    <header className="px-page-title employee-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工</h1><span>从员工集合选择一个角色，查看其精确版本、装配与工作关系。</span></div><button className="px-primary-button" onClick={() => { setMode("create"); setMobileDetailOpen(false); updateUrl({ mode: "create", detail: "" }); }}>＋ 创建数字员工</button></header>
    <section className="employee-summary-strip" aria-label="当前加载范围"><span><strong>{new Set(items.map(item => item.employeeDefinitionId)).size}</strong> 个员工</span><span><strong>{items.length}</strong> 个修订</span><span><strong>{publishedRevisions}</strong> 个已发布修订</span><small>仅当前授权与当前 cursor 页；不是全局统计</small></section>

    {mode === "create" ? <><button type="button" className="employee-back-button" onClick={() => { setMode("employees"); updateUrl({ mode: "employees" }); }}>← 返回员工集合</button><EmployeeDefinitionAssembly agents={agents} hasMoreAgents={Boolean(agentNextCursor)} agentError={agentError ? controlledMessage(agentError) : undefined} onLoadMoreAgents={() => void loadMoreAgents()} onReadback={applyCommandReadback} /></> : <div className={`employee-object-center ${mobileDetailOpen ? "show-mobile-detail" : ""}`}>
      <section className="employee-collection" aria-label="员工集合">
        <div className="employee-collection-toolbar"><div><h2>员工集合</h2><p>{groups.length} 个员工 · {filteredRevisions.length} 个修订（当前页）</p></div><div className="employee-filters"><label><span>搜索当前页</span><input value={query} onChange={event => changeFilter("q", event.target.value)} placeholder="职责角色或技术 ID" /></label><label><span>发布状态</span><select value={status} onChange={event => changeFilter("status", event.target.value)}><option value="ALL">全部状态</option><option value="PUBLISHED">已发布</option><option value="NOT_PUBLISHED">未发布</option></select></label></div></div>
        {listError && <div role="alert" className="qto-alert"><strong>列表读取失败</strong><span>{controlledMessage(listError)}</span></div>}
        <div className="employee-collection-rows" ref={listScroll}>{groups.map(group => {
          const active = selectedIdentity?.id === group.id ? group.revisions.find(item => item.employeeDefinitionRevisionId === selectedIdentity.revision) ?? group.revisions[0] : group.revisions[0];
          const isSelected = Boolean(selectedIdentity && exactKey(selectedIdentity) === exactKey(exactFromSummary(active)));
          return <article key={group.id} className={`employee-collection-row ${isSelected ? "selected" : ""}`}><button className="employee-row-main" aria-current={isSelected ? "true" : undefined} onClick={() => select(active)}><span className="employee-avatar" aria-hidden="true">员</span><span className="employee-row-copy"><strong>{active.role}</strong><small title={group.id}>{shortIdentity(group.id)}</small><small>职责摘要需选择后 exact READ</small></span><span className={`employee-state-chip ${active.publicationState === "PUBLISHED" ? "published" : "draft"}`}>{active.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</span></button><label className="employee-revision-picker"><span>显示版本</span><select aria-label={`${active.role} 选择版本`} value={active.employeeDefinitionRevisionId} onChange={event => { const revision = group.revisions.find(item => item.employeeDefinitionRevisionId === event.target.value); if (revision) select(revision); }}>{group.revisions.map(item => <option key={item.employeeDefinitionRevisionId} value={item.employeeDefinitionRevisionId}>{shortIdentity(item.employeeDefinitionRevisionId)} · {item.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</option>)}</select>{group.revisions.length > 1 && <small>{group.revisions.length} 个当前页修订；未声明 latest</small>}</label></article>;
        })}{!groups.length && listState === "READY" && !listError && <div className="px-empty"><strong>当前页没有匹配记录</strong><p>搜索与筛选仅覆盖已加载页，不代表授权集合为空。</p></div>}</div>
        <nav className="employee-pagination" aria-label="Employee cursor 分页"><button type="button" disabled={pageIndex === 0 || listState === "LOADING"} onClick={() => { clearSelection(); setPageIndex(value => value - 1); }}>← 上一页</button><span>已加载 cursor 第 {pageIndex + 1} 页</span><button type="button" disabled={!currentPage?.nextCursor || listState === "LOADING"} onClick={() => { clearSelection(); const cached = pages[pageIndex + 1]; if (cached) setPageIndex(pageIndex + 1); else void loadEmployeePage(currentPage.nextCursor, pageIndex + 1); }}>{listState === "LOADING" ? "读取中……" : "加载下一页 →"}</button></nav>
      </section>

      <section className="employee-selected-detail" aria-label="选中员工详情"><button type="button" className="employee-mobile-back" onClick={() => { setMobileDetailOpen(false); updateUrl({ detail: "" }); requestAnimationFrame(() => { if (listScroll.current) listScroll.current.scrollTop = savedListScroll.current; }); }}>← 返回员工集合</button>{!selectedIdentity && <div className="employee-detail-placeholder"><span className="employee-avatar large" aria-hidden="true">员</span><h2>选择一个数字员工</h2><p>每次选择都会独立读取精确修订。版本选择不会自动把 latest 当作权威。</p></div>}{detailBusy && <p role="status" className="agent-state">正在读取选中员工的精确修订……</p>}{detailError && <div role="alert" className="qto-alert"><strong>详情读取未完成</strong><span>{controlledMessage(detailError)}</span>{selectedIdentity && <button onClick={() => void readDefinitionExact(selectedIdentity, true)}>重新读取精确修订</button>}</div>}{selected && <><header className="employee-detail-context"><div><p className="eyebrow">选中员工 · 精确修订</p><h2>{selected.role}</h2><p><code>{shortIdentity(selected.employeeDefinitionId)}</code> · <code>{shortIdentity(selected.employeeDefinitionRevisionId)}</code></p></div><span className={`employee-state-chip ${selected.publicationState === "PUBLISHED" ? "published" : "draft"}`}>{selected.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</span></header><nav className="employee-detail-tabs" aria-label="选中员工详情分类">{([['overview', '概览'], ['capabilities', '职责与能力'], ['instances', '实例'], ['assignments', '工作分配']] as const).map(([key, label]) => <button type="button" key={key} className={detailSection === key ? "active" : ""} onClick={() => showSection(key)}>{label}</button>)}</nav><article className="px-object-detail employee-detail-body">
        {detailSection === "overview" && <><EmployeeProfileLoader item={selected} section="overview" /><EmployeeLifecycleActions key={exactKey(exactFromSummary(selected))} item={selected} initialResult={latestCommand?.employeeDefinitionId === selected.employeeDefinitionId && latestCommand.employeeDefinitionRevisionId === selected.employeeDefinitionRevisionId ? latestCommand : undefined} onReadback={applyCommandReadback} /><section className="employee-version-boundary"><span className="employee-capability-state missing"><i />关联列表暂未接通</span><h3>完整版本历史</h3><p>当前页只展示 LIST 返回的修订，不能代表完整历史，也不推断 latest。当前没有 revision-history LIST。</p></section></>}
        {detailSection === "capabilities" && <EmployeeProfileLoader item={selected} section="capabilities" />}
        {detailSection === "instances" && <ExactInstancePanel selected={selected} instanceId={instanceId} setInstanceId={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setInstanceId(value); setInstance(null); setInstanceDefinition(null); setAssignment(null); setWorkError(null); }} instance={instance} boundDefinition={instanceDefinition} busy={workBusy} error={workError} onRead={() => void readInstanceExact()} />}
        {detailSection === "assignments" && <ExactAssignmentPanel selected={selected} instance={instance} assignmentId={assignmentId} setAssignmentId={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setAssignmentId(value); setAssignment(null); setWorkError(null); }} assignment={assignment} busy={workBusy} error={workError} onRead={() => void readAssignmentExact()} params={params} onCoordinates={coordinates => updateUrl({ instanceId: instance?.instanceId ?? "", assignmentId: assignment?.assignmentId ?? "", ...coordinates })} />}
      </article></>}</section>
    </div>}
  </main>;
}

function Field({ label, value, set }: { label: string; value: string; set: (value: string) => void }) {
  return <label>{label}<input value={value} onChange={event => set(event.target.value)} /></label>;
}

function ExactInstancePanel({ selected, instanceId, setInstanceId, instance, boundDefinition, busy, error, onRead }: { selected: EmployeeDefinition; instanceId: string; setInstanceId: (value: string) => void; instance: EmployeeInstance | null; boundDefinition: EmployeeDefinition | null; busy: boolean; error: ReadError | null; onRead: () => void }) {
  return <section className="employee-related-panel"><header><div><p className="eyebrow">当前员工 · {selected.role}</p><h3>实例</h3></div><span className="employee-capability-state partial"><i />关联列表暂未接通</span></header><p>当前没有按员工列出 Instance 的正式接口，因此不能显示“0 个实例”。</p><details><summary>技术详情：按精确 ID 核对关联实例</summary><p>只在 Instance 返回的 Definition ID、revision、digest 与当前员工完全一致后展示。</p><Field label="Instance ID" value={instanceId} set={setInstanceId} /><button disabled={busy || !instanceId.trim()} onClick={onRead}>{busy ? "读取中……" : "读取并验证归属"}</button></details>{error && <div role="alert" className="qto-alert"><strong>实例读取未完成</strong><span>{controlledMessage(error)}</span></div>}{instance && <InstanceDetail value={instance} boundDefinition={boundDefinition} />}</section>;
}

function ExactAssignmentPanel({ selected, instance, assignmentId, setAssignmentId, assignment, busy, error, onRead, params, onCoordinates }: { selected: EmployeeDefinition; instance: EmployeeInstance | null; assignmentId: string; setAssignmentId: (value: string) => void; assignment: EmployeeAssignment | null; busy: boolean; error: ReadError | null; onRead: () => void; params: URLSearchParams; onCoordinates: (coordinates: { placementId: string; attemptId: string; agentInstanceId: string }) => void }) {
  return <section className="employee-related-panel"><header><div><p className="eyebrow">当前员工 · {selected.role}</p><h3>工作分配</h3></div><span className="employee-capability-state partial"><i />关联列表暂未接通</span></header><p>当前没有按员工或实例列出 Assignment / Placement 的正式接口，因此不能显示零条或完整工作历史。</p><details><summary>技术详情：按精确 ID 核对工作分配</summary><p>{instance ? `已验证当前员工关联 Instance：${instance.instanceId}` : "请先在“实例”分类验证一个属于当前员工的 Instance。"}</p><Field label="Assignment ID" value={assignmentId} set={setAssignmentId} /><button disabled={!instance || busy || !assignmentId.trim()} onClick={onRead}>{busy ? "读取中……" : "读取并验证父链"}</button></details>{error && <div role="alert" className="qto-alert"><strong>工作关联读取未完成</strong><span>{controlledMessage(error)}</span></div>}{assignment && <><AssignmentDetail value={assignment} /><EmployeeWorkParticipation key={`${instance?.instanceId}:${assignment.assignmentId}`} definition={selected} instance={instance} assignment={assignment} initialCoordinates={{ placementId: params.get("placementId") ?? "", attemptId: params.get("attemptId") ?? "", agentInstanceId: params.get("agentInstanceId") ?? "" }} onCoordinates={onCoordinates} /></>}</section>;
}

function InstanceDetail({ value, boundDefinition }: { value: EmployeeInstance; boundDefinition: EmployeeDefinition | null }) {
  const reference = value.employeeDefinition;
  return <dl className="employee-facts"><dt>Instance</dt><dd>{value.instanceId}</dd><dt>员工归属</dt><dd>{boundDefinition ? `${boundDefinition.role} · exact identity verified` : "未通过当前员工归属核对"}</dd><dt>绑定 Definition / revision</dt><dd>{reference?.employeeDefinitionId ?? "未提供"}<br />{reference?.employeeDefinitionRevisionId ?? "未提供"}</dd><dt>Owner / organization</dt><dd>{value.ownerId} / {value.organizationId}</dd><dt>生命周期</dt><dd>{value.lifecycle}</dd><dt>Execution / Health</dt><dd>{value.execution.reasonCode} / {value.health.reasonCode}</dd></dl>;
}

function AssignmentDetail({ value }: { value: EmployeeAssignment }) {
  return <dl className="employee-facts"><dt>Assignment / Instance</dt><dd>{value.assignmentId} / {value.instanceId}</dd><dt>状态与角色</dt><dd>{value.lifecycle} · {value.businessRole}</dd><dt>受派对象</dt><dd>{value.assigneeId}</dd><dt>有效期</dt><dd>{value.effectiveFrom} → {value.effectiveUntil ?? "无固定结束时间"}</dd><dt>Plan / Workflow 绑定</dt><dd>{value.binding.state} · {value.binding.reasonCode}</dd></dl>;
}
