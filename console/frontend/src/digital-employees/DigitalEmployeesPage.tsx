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
  const detailScroll = useRef<HTMLElement | null>(null);
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
    requestAnimationFrame(() => {
      if (detailScroll.current) detailScroll.current.scrollTop = 0;
    });
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
  const selectedListSummary = selectedIdentity
    ? items.find(item => exactKey(exactFromSummary(item)) === exactKey(selectedIdentity))
    : undefined;

  return <main className="px-page px-center-page employee-management">
    <header className="px-page-title employee-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工</h1><span>从员工集合选择一个角色，查看所选修订、装配与工作关系。</span></div>{mode === "employees" && <button className="px-primary-button" onClick={() => { setMode("create"); setMobileDetailOpen(false); updateUrl({ mode: "create", detail: "" }); }}>＋ 创建数字员工</button>}</header>
    {mode === "employees" && <section className="employee-summary-strip" aria-label="当前加载范围"><span><strong>{new Set(items.map(item => item.employeeDefinitionId)).size}</strong> 个已加载员工</span><span><strong>{items.length}</strong> 个已加载修订</span><span><strong>{publishedRevisions}</strong> 个已加载的已发布修订</span><small>仅展示当前授权范围内的本批结果；不是全局统计</small></section>}

    {mode === "create" ? <><button type="button" className="employee-back-button" onClick={() => { setMode("employees"); updateUrl({ mode: "employees" }); }}>← 返回员工集合</button><EmployeeDefinitionAssembly agents={agents} hasMoreAgents={Boolean(agentNextCursor)} agentError={agentError ? controlledMessage(agentError) : undefined} onLoadMoreAgents={() => void loadMoreAgents()} onReadback={applyCommandReadback} /></> : <div className={`employee-object-center ${mobileDetailOpen ? "show-mobile-detail" : ""}`}>
      <section className="employee-collection" aria-label="员工集合">
        <div className="employee-collection-toolbar"><div><h2>员工集合</h2><p>{groups.length} 个员工 · {filteredRevisions.length} 个修订（当前批）</p></div><small>职责摘要在选择员工后显示</small><div className="employee-filters"><label><span>搜索当前结果</span><input value={query} onChange={event => changeFilter("q", event.target.value)} placeholder="职责角色或技术 ID" /></label><label><span>发布状态</span><select value={status} onChange={event => changeFilter("status", event.target.value)}><option value="ALL">全部状态</option><option value="PUBLISHED">已发布</option><option value="NOT_PUBLISHED">未发布</option></select></label></div></div>
        {listError && <div role="alert" className="qto-alert"><strong>列表读取失败</strong><span>{controlledMessage(listError)}</span></div>}
        <div className="employee-collection-rows" ref={listScroll}>{groups.map(group => {
          const active = selectedIdentity?.id === group.id ? group.revisions.find(item => item.employeeDefinitionRevisionId === selectedIdentity.revision) ?? group.revisions[0] : group.revisions[0];
          const isSelected = Boolean(selectedIdentity && exactKey(selectedIdentity) === exactKey(exactFromSummary(active)));
          const identityDisclosure = <details className="employee-row-identity"><summary>查看完整 ID</summary><code>{group.id}</code><code>{active.employeeDefinitionRevisionId}</code></details>;
          return <article key={group.id} className={`employee-collection-row ${isSelected ? "selected" : ""}`}><button className="employee-row-main" aria-current={isSelected ? "true" : undefined} onClick={() => select(active)}><span className="employee-avatar" aria-hidden="true">员</span><span className="employee-row-copy"><strong>{active.role}</strong><small>{shortIdentity(group.id)}</small></span><span className={`employee-state-chip ${active.publicationState === "PUBLISHED" ? "published" : "draft"}`}>{active.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</span></button>{group.revisions.length > 1 ? <label className="employee-revision-picker"><span>选择版本</span><select aria-label={`${active.role} 选择版本`} value={active.employeeDefinitionRevisionId} onChange={event => { const revision = group.revisions.find(item => item.employeeDefinitionRevisionId === event.target.value); if (revision) select(revision); }}>{group.revisions.map(item => <option key={item.employeeDefinitionRevisionId} value={item.employeeDefinitionRevisionId}>{shortIdentity(item.employeeDefinitionRevisionId)} · {item.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</option>)}</select><small>当前结果包含 {group.revisions.length} 个修订；请明确选择</small>{identityDisclosure}</label> : <div className="employee-single-revision"><span>单个修订</span><small>{shortIdentity(active.employeeDefinitionRevisionId)}</small>{identityDisclosure}</div>}</article>;
        })}{!groups.length && listState === "READY" && !listError && <div className="px-empty"><strong>当前结果没有匹配记录</strong><p>搜索与筛选仅覆盖已加载结果，不代表授权集合为空。</p></div>}</div>
        <nav className="employee-pagination" aria-label="员工分页"><button type="button" disabled={pageIndex === 0 || listState === "LOADING"} onClick={() => { clearSelection(); setPageIndex(value => value - 1); }}>← 上一页</button><span>第 {pageIndex + 1} 批</span><button type="button" disabled={!currentPage?.nextCursor || listState === "LOADING"} onClick={() => { clearSelection(); const cached = pages[pageIndex + 1]; if (cached) setPageIndex(pageIndex + 1); else void loadEmployeePage(currentPage.nextCursor, pageIndex + 1); }}>{listState === "LOADING" ? "读取中……" : "加载下一页 →"}</button></nav>
      </section>

      <section className="employee-selected-detail" aria-label="选中员工详情"><button type="button" className="employee-mobile-back" onClick={() => { setMobileDetailOpen(false); updateUrl({ detail: "" }); requestAnimationFrame(() => { if (listScroll.current) listScroll.current.scrollTop = savedListScroll.current; }); }}>← 返回员工集合</button>{!selectedIdentity && <div className="employee-detail-placeholder"><span className="employee-avatar large" aria-hidden="true">员</span><h2>选择一个数字员工</h2><p>每次选择都会读取所选修订；请从列表中明确选择要查看的修订。</p></div>}{detailBusy && <p role="status" className="agent-state">正在读取所选修订……</p>}{detailError && <div role="alert" className="qto-alert employee-detail-error"><strong>详情读取未完成</strong>{selectedListSummary && <section className="employee-denied-summary" aria-label="所选员工列表摘要"><span>所选员工</span><strong>{selectedListSummary.role}</strong><small>{shortIdentity(selectedListSummary.employeeDefinitionId)} · {shortIdentity(selectedListSummary.employeeDefinitionRevisionId)} · {selectedListSummary.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</small></section>}<span>{controlledMessage(detailError)}</span>{selectedIdentity && <button onClick={() => void readDefinitionExact(selectedIdentity, true)}>重试</button>}</div>}{selected && <><header className="employee-detail-context"><div><p className="eyebrow">选中员工 · 已核对修订</p><h2>{selected.role}</h2><p><code>{shortIdentity(selected.employeeDefinitionId)}</code> · <code>{shortIdentity(selected.employeeDefinitionRevisionId)}</code></p></div><span className={`employee-state-chip ${selected.publicationState === "PUBLISHED" ? "published" : "draft"}`}>{selected.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</span></header><nav className="employee-detail-tabs" aria-label="选中员工详情分类">{([['overview', '概览'], ['capabilities', '职责与能力'], ['instances', '实例'], ['assignments', '工作分配']] as const).map(([key, label]) => <button type="button" key={key} className={detailSection === key ? "active" : ""} onClick={() => showSection(key)}>{label}</button>)}</nav><article className="px-object-detail employee-detail-body" ref={detailScroll}>
        {detailSection === "overview" && <><EmployeeProfileLoader item={selected} section="overview" /><EmployeeLifecycleActions key={exactKey(exactFromSummary(selected))} item={selected} initialResult={latestCommand?.employeeDefinitionId === selected.employeeDefinitionId && latestCommand.employeeDefinitionRevisionId === selected.employeeDefinitionRevisionId ? latestCommand : undefined} onReadback={applyCommandReadback} /><section className="employee-version-boundary"><span className="employee-capability-state missing"><i />关联列表暂未接通</span><h3>完整版本历史</h3><p>当前结果不能代表完整历史；请以列表中明确选择的修订为当前查看对象。完整修订历史接口尚未接通。</p></section></>}
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

function instanceLifecycleLabel(value: string) {
  if (value === "ENABLED") return "已启用";
  if (value === "DISABLED") return "已停用";
  return `未知状态（${value}）`;
}

function instanceSignalLabel(kind: "execution" | "health", state: string, reasonCode: string) {
  if (kind === "execution" && state === "UNAVAILABLE" && reasonCode === "EXECUTION_NOT_ASSEMBLED") return "执行信息未接通";
  if (kind === "health" && state === "UNAVAILABLE" && reasonCode === "HEALTH_NOT_ASSEMBLED") return "健康信息未接通";
  return `未知状态（${state}）`;
}

function assignmentLifecycleLabel(value: string) {
  if (value === "ACTIVE") return "生效中";
  if (value === "INACTIVE") return "未生效";
  return `未知状态（${value}）`;
}

function assignmentBindingLabel(state: string, reasonCode: string) {
  if (state === "UNAVAILABLE" && reasonCode === "WORKFLOW_BINDING_NOT_ASSEMBLED") return "Plan / Workflow 绑定未接通";
  return `未知状态（${state}）`;
}

function ExactInstancePanel({ selected, instanceId, setInstanceId, instance, boundDefinition, busy, error, onRead }: { selected: EmployeeDefinition; instanceId: string; setInstanceId: (value: string) => void; instance: EmployeeInstance | null; boundDefinition: EmployeeDefinition | null; busy: boolean; error: ReadError | null; onRead: () => void }) {
  return <section className="employee-related-panel"><header><div><p className="eyebrow">当前员工 · {selected.role}</p><h3>实例</h3></div><span className="employee-capability-state partial"><i />关联列表暂未接通</span></header><p className="employee-business-summary">暂不支持按员工浏览实例列表；可使用已知实例 ID 查询。</p>{error && <div role="alert" className="qto-alert"><strong>实例读取未完成</strong><span>{controlledMessage(error)}</span></div>}{instance && <InstanceDetail value={instance} boundDefinition={boundDefinition} />}<details className="employee-exact-operation"><summary>{instance ? "查询其他实例" : "使用已知实例 ID 查询"}</summary><p>技术说明：只有 Instance 返回的 Definition ID、revision、digest 与当前 Employee 精确修订完全一致时，才展示读取结果。归属通过不表示实例正在运行或健康。</p><Field label="实例 ID" value={instanceId} set={setInstanceId} /><button disabled={busy || !instanceId.trim()} onClick={onRead}>{busy ? "读取中……" : "读取并验证归属"}</button></details></section>;
}

function ExactAssignmentPanel({ selected, instance, assignmentId, setAssignmentId, assignment, busy, error, onRead, params, onCoordinates }: { selected: EmployeeDefinition; instance: EmployeeInstance | null; assignmentId: string; setAssignmentId: (value: string) => void; assignment: EmployeeAssignment | null; busy: boolean; error: ReadError | null; onRead: () => void; params: URLSearchParams; onCoordinates: (coordinates: { placementId: string; attemptId: string; agentInstanceId: string }) => void }) {
  return <section className="employee-related-panel"><header><div><p className="eyebrow">当前员工 · {selected.role}</p><h3>工作分配</h3></div><span className="employee-capability-state partial"><i />关联列表暂未接通</span></header><p className="employee-business-summary">暂不支持按员工或实例浏览工作分配列表；可在已核实实例下使用已知 Assignment ID 查询。</p>{error && <div role="alert" className="qto-alert"><strong>工作关联读取未完成</strong><span>{controlledMessage(error)}</span></div>}{assignment && <><AssignmentDetail value={assignment} /><EmployeeWorkParticipation key={`${instance?.instanceId}:${assignment.assignmentId}`} definition={selected} instance={instance} assignment={assignment} initialCoordinates={{ placementId: params.get("placementId") ?? "", attemptId: params.get("attemptId") ?? "", agentInstanceId: params.get("agentInstanceId") ?? "" }} onCoordinates={onCoordinates} /></>}<details className="employee-exact-operation"><summary>{assignment ? "查询其他工作分配" : "使用已知 Assignment ID 查询"}</summary><p>{instance ? `已核实当前 Employee 关联实例：${instance.instanceId}。读取时仍会验证 Assignment 的实例父链。` : "请先在“实例”标签页读取并核实一个属于当前 Employee 精确修订的实例。"}</p><Field label="Assignment ID" value={assignmentId} set={setAssignmentId} /><button disabled={!instance || busy || !assignmentId.trim()} onClick={onRead}>{busy ? "读取中……" : "读取并验证父链"}</button></details></section>;
}

function InstanceDetail({ value, boundDefinition }: { value: EmployeeInstance; boundDefinition: EmployeeDefinition | null }) {
  const reference = value.employeeDefinition;
  return <section className="employee-read-result" aria-labelledby="employee-instance-result-title"><header><div><p className="eyebrow">正式 Instance exact READ</p><h4 id="employee-instance-result-title">已读取实例摘要</h4></div><span className="binding-status verified">员工归属已核实</span></header><dl className="employee-fact-grid"><div><dt>实例标识</dt><dd><code>{value.instanceId}</code></dd></div><div><dt>员工归属</dt><dd>{boundDefinition ? `${boundDefinition.role} · 与所选精确修订一致` : "未通过当前员工归属核对"}</dd></div><div><dt>组织 / 所有者</dt><dd>{value.organizationId} / {value.ownerId}</dd></div><div><dt>生命周期</dt><dd>{instanceLifecycleLabel(value.lifecycle)}</dd></div><div><dt>执行信息</dt><dd>{instanceSignalLabel("execution", value.execution.state, value.execution.reasonCode)}</dd></div><div><dt>健康信息</dt><dd>{instanceSignalLabel("health", value.health.state, value.health.reasonCode)}</dd></div></dl><details className="employee-technical-details"><summary>实例技术身份与原始状态</summary><dl><dt>Employee Definition ID</dt><dd>{reference?.employeeDefinitionId ?? "未提供"}</dd><dt>Revision ID</dt><dd>{reference?.employeeDefinitionRevisionId ?? "未提供"}</dd><dt>Digest</dt><dd>{reference?.digest ?? "未提供"}</dd><dt>生命周期原值</dt><dd>{value.lifecycle}</dd><dt>Execution 原值</dt><dd>{value.execution.state} / {value.execution.reasonCode}</dd><dt>Health 原值</dt><dd>{value.health.state} / {value.health.reasonCode}</dd></dl></details></section>;
}

function AssignmentDetail({ value }: { value: EmployeeAssignment }) {
  return <section className="employee-read-result" aria-labelledby="employee-assignment-result-title"><header><div><p className="eyebrow">正式 Assignment exact READ</p><h4 id="employee-assignment-result-title">当前查询的实例与工作分配</h4></div><span className="binding-status verified">实例父链已核实</span></header><dl className="employee-fact-grid"><div><dt>工作分配标识</dt><dd><code>{value.assignmentId}</code></dd></div><div><dt>关联实例</dt><dd><code>{value.instanceId}</code></dd></div><div><dt>业务角色</dt><dd>{value.businessRole}</dd></div><div><dt>受派对象</dt><dd>{value.assigneeId}</dd></div><div><dt>生命周期</dt><dd>{assignmentLifecycleLabel(value.lifecycle)}</dd></div><div><dt>Plan / Workflow 绑定</dt><dd>{assignmentBindingLabel(value.binding.state, value.binding.reasonCode)}</dd></div><div className="wide"><dt>有效期</dt><dd>{value.effectiveFrom} → {value.effectiveUntil ?? "无固定结束时间"}</dd></div></dl><details className="employee-technical-details"><summary>Assignment 原始状态</summary><dl><dt>生命周期</dt><dd>{value.lifecycle}</dd><dt>绑定状态</dt><dd>{value.binding.state}</dd><dt>诊断代码</dt><dd>{value.binding.reasonCode}</dd></dl></details></section>;
}
