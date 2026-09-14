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
  type EmployeeDefinition,
  type EmployeeCommandResult,
  type EmployeeDefinitionSummary,
  type EmployeeInstance,
} from "../api/digitalEmployees";
import { EmployeeProfileLoader } from "./EmployeeProfile";
import { EmployeeDefinitionAssembly } from "./EmployeeDefinitionAssembly";
import { EmployeeLifecycleActions } from "./EmployeeLifecycleActions";
import { EmployeeWorkParticipation } from "./EmployeeWorkParticipation";

type Panel = "definitions" | "create" | "instance" | "assignment" | "work";
type ReadError = { code: string; kind: string };
type ExactDefinition = { id: string; revision: string; digest?: string };

function exactFromSummary(item: EmployeeDefinitionSummary): ExactDefinition {
  return {
    id: item.employeeDefinitionId,
    revision: item.employeeDefinitionRevisionId,
    digest: item.employeeDefinitionDigest,
  };
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

async function readInstanceDefinition(value: EmployeeInstance, signal?: AbortSignal) {
  const reference = value.employeeDefinition;
  if (!reference) return null;
  const definition = await getEmployeeDefinition(
    reference.employeeDefinitionId,
    reference.employeeDefinitionRevisionId,
    signal,
  );
  if (definition.employeeDefinitionId !== reference.employeeDefinitionId
    || definition.employeeDefinitionRevisionId !== reference.employeeDefinitionRevisionId
    || definition.employeeDefinitionDigest !== reference.digest) {
    throw new DigitalEmployeeRequestError("INSTANCE_DEFINITION_IDENTITY_MISMATCH", 409);
  }
  return definition;
}

function verifyAssignmentInstance(value: EmployeeAssignment, instanceId: string, assignmentId: string) {
  if (value.instanceId !== instanceId) {
    throw new DigitalEmployeeRequestError("ASSIGNMENT_INSTANCE_IDENTITY_MISMATCH", 409);
  }
  if (value.assignmentId !== assignmentId) {
    throw new DigitalEmployeeRequestError("ASSIGNMENT_IDENTITY_MISMATCH", 409);
  }
  return value;
}

export function DigitalEmployeesPage() {
  const [params, setParams] = useSearchParams();
  const [items, setItems] = useState<EmployeeDefinitionSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string>();
  const [selectedIdentity, setSelectedIdentity] = useState<ExactDefinition | null>(null);
  const [selected, setSelected] = useState<EmployeeDefinition | null>(null);
  const [agents, setAgents] = useState<AgentDefinitionSummary[]>([]);
  const [agentNextCursor, setAgentNextCursor] = useState<string>();
  const [panel, setPanel] = useState<Panel>((params.get("panel") as Panel) || "definitions");
  const [instanceId, setInstanceId] = useState(params.get("instanceId") ?? "");
  const [assignmentId, setAssignmentId] = useState(params.get("assignmentId") ?? "");
  const [instance, setInstance] = useState<EmployeeInstance | null>(null);
  const [instanceDefinition, setInstanceDefinition] = useState<EmployeeDefinition | null>(null);
  const [assignment, setAssignment] = useState<EmployeeAssignment | null>(null);
  const [listState, setListState] = useState<"LOADING" | "READY">("LOADING");
  const [detailState, setDetailState] = useState<"LOADING" | "READY">("READY");
  const [workState, setWorkState] = useState<"READY" | "LOADING">(params.get("instanceId") ? "LOADING" : "READY");
  const [listError, setListError] = useState<ReadError | null>(null);
  const [error, setError] = useState<ReadError | null>(null);
  const [workError, setWorkError] = useState<ReadError | null>(null);
  const [agentError, setAgentError] = useState<ReadError | null>(null);
  const [latestCommand, setLatestCommand] = useState<EmployeeCommandResult | null>(null);
  const listGeneration = useRef(0);
  const detailGeneration = useRef(0);
  const workGeneration = useRef(0);
  const activeDetailRead = useRef<AbortController | null>(null);
  const activeWorkRead = useRef<AbortController | null>(null);
  const query = params.get("q") ?? "";
  const status = params.get("status") ?? "ALL";

  const visible = useMemo(() => items.filter(item =>
    (status === "ALL" || item.publicationState === status)
    && `${item.employeeDefinitionId} ${item.employeeDefinitionRevisionId} ${item.role}`
      .toLowerCase().includes(query.toLowerCase())), [items, query, status]);

  function updateUrl(values: Record<string, string>) {
    const next = new URLSearchParams(params);
    Object.entries(values).forEach(([key, value]) => value ? next.set(key, value) : next.delete(key));
    setParams(next);
  }

  async function readDefinitionExact(exact: ExactDefinition) {
    const turn = ++detailGeneration.current;
    activeDetailRead.current?.abort();
    const controller = new AbortController();
    activeDetailRead.current = controller;
    setSelectedIdentity(exact);
    setSelected(null);
    setDetailState("LOADING");
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
      setError(null);
      setDetailState("READY");
    } catch (reason) {
      if (turn !== detailGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setSelected(null);
      setError(toReadError(reason));
      setDetailState("READY");
    }
  }

  async function loadMoreEmployees(cursor: string) {
    const turn = ++listGeneration.current;
    setListState("LOADING");
    try {
      const page = await listEmployeeDefinitions(cursor);
      if (turn !== listGeneration.current) return;
      setItems(current => {
        const known = new Set(current.map(item => `${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`));
        return [...current, ...page.items.filter(item => !known.has(`${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`))];
      });
      setNextCursor(page.nextCursor);
      setListError(null);
      setListState("READY");
    } catch (reason) {
      if (turn !== listGeneration.current) return;
      setListError(toReadError(reason));
      setListState("READY");
    }
  }

  useEffect(() => {
    const listTurn = ++listGeneration.current;
    const controller = new AbortController();
    const fromUrl = params.get("employeeDefinitionId") && params.get("employeeDefinitionRevisionId")
      ? { id: params.get("employeeDefinitionId")!, revision: params.get("employeeDefinitionRevisionId")! }
      : null;
    if (fromUrl) queueMicrotask(() => void readDefinitionExact(fromUrl));
    listEmployeeDefinitions(undefined, controller.signal).then(page => {
      if (listTurn !== listGeneration.current) return;
      setItems(page.items);
      setNextCursor(page.nextCursor);
      setListError(null);
      setListState("READY");
      if (!fromUrl && page.items[0]) void readDefinitionExact(exactFromSummary(page.items[0]));
    }).catch(reason => {
      if (listTurn !== listGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setListError(toReadError(reason));
      setListState("READY");
    });
    return () => {
      controller.abort();
      activeDetailRead.current?.abort();
      listGeneration.current += 1;
      detailGeneration.current += 1;
    };
    // Initial URL context is intentionally captured once; subsequent selection is explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    listAgentDefinitions(undefined, controller.signal).then(page => {
      if (!active) return;
      setAgents(page.items);
      setAgentNextCursor(page.nextCursor);
      setAgentError(null);
    }).catch(reason => {
      if (!active || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setAgentError(toReadError(reason));
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  async function loadMoreAgents() {
    if (!agentNextCursor) return;
    try {
      const page = await listAgentDefinitions(agentNextCursor);
      setAgents(current => {
        const known = new Set(current.map(item => item.definitionId));
        return [...current, ...page.items.filter(item => !known.has(item.definitionId))];
      });
      setAgentNextCursor(page.nextCursor);
      setAgentError(null);
    } catch (reason) {
      setAgentError(toReadError(reason));
    }
  }

  useEffect(() => {
    const knownInstanceId = params.get("instanceId");
    const knownAssignmentId = params.get("assignmentId");
    if (!knownInstanceId) return;
    const turn = ++workGeneration.current;
    const controller = new AbortController();
    activeWorkRead.current = controller;
    getEmployeeInstance(knownInstanceId, controller.signal).then(async value => {
      if (value.instanceId !== knownInstanceId) throw new DigitalEmployeeRequestError("INSTANCE_IDENTITY_MISMATCH", 409);
      const definition = await readInstanceDefinition(value, controller.signal);
      const assignmentValue = knownAssignmentId
        ? verifyAssignmentInstance(
          await getEmployeeAssignment(knownInstanceId, knownAssignmentId, controller.signal),
          value.instanceId,
          knownAssignmentId,
        )
        : null;
      return { value, definition, assignmentValue };
    }).then(result => {
      if (turn !== workGeneration.current) return;
      setInstance(result.value);
      setInstanceDefinition(result.definition);
      setAssignment(result.assignmentValue);
      setWorkError(null);
      setWorkState("READY");
    }).catch(reason => {
      if (turn !== workGeneration.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      setInstance(null);
      setInstanceDefinition(null);
      setAssignment(null);
      setWorkError(toReadError(reason));
      setWorkState("READY");
    });
    return () => {
      controller.abort();
      workGeneration.current += 1;
    };
    // URL identities are read once as coordinates, then authoritative objects are fetched.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function select(item: EmployeeDefinitionSummary) {
    const exact = exactFromSummary(item);
    updateUrl({
      panel: "definitions",
      employeeDefinitionId: exact.id,
      employeeDefinitionRevisionId: exact.revision,
    });
    void readDefinitionExact(exact);
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
    setItems(current => {
      const withoutExact = current.filter(item =>
        item.employeeDefinitionId !== summary.employeeDefinitionId
        || item.employeeDefinitionRevisionId !== summary.employeeDefinitionRevisionId);
      return [summary, ...withoutExact];
    });
  }

  async function readInstanceExact(id = instanceId.trim()) {
    if (!id) return;
    const turn = ++workGeneration.current;
    activeWorkRead.current?.abort();
    const controller = new AbortController();
    activeWorkRead.current = controller;
    setWorkState("LOADING");
    try {
      const value = await getEmployeeInstance(id, controller.signal);
      if (value.instanceId !== id) throw new DigitalEmployeeRequestError("INSTANCE_IDENTITY_MISMATCH", 409);
      const definition = await readInstanceDefinition(value, controller.signal);
      if (turn !== workGeneration.current) return;
      setInstance(value);
      setInstanceDefinition(definition);
      setAssignment(null);
      setAssignmentId("");
      setWorkError(null);
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
    try {
      const value = verifyAssignmentInstance(
        await getEmployeeAssignment(instance.instanceId, id, controller.signal),
        instance.instanceId,
        id,
      );
      if (turn !== workGeneration.current) return;
      setAssignment(value);
      setWorkError(null);
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

  return <main className="px-page px-center-page employee-management">
    <header className="px-page-title employee-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工管理</h1><span>定义企业业务角色与职责，并以精确 Agent 修订完成受治理装配。</span></div><button className="px-primary-button" onClick={() => { setPanel("create"); updateUrl({ panel: "create" }); }}>＋ 创建数字员工</button></header>
    <section className="employee-overview" aria-label="当前页面能力概况">
      <article><span className="employee-overview-icon blue" aria-hidden="true">员</span><div><small>当前已加载定义</small><strong>{items.length}</strong><span>仅当前授权与已加载页</span></div></article>
      <article><span className="employee-overview-icon green" aria-hidden="true">A</span><div><small>可用 Agent 候选</small><strong>{agents.filter(agent => agent.enabled && !agent.archived).length}</strong><span>仅当前已加载候选</span></div></article>
      <article><span className="employee-overview-icon amber" aria-hidden="true">写</span><div><small>生命周期装配</small><strong>部分实现</strong><span>正式权限取得待 305</span></div></article>
      <article><span className="employee-overview-icon red" aria-hidden="true">!</span><div><small>运行与结果</small><strong>未实现</strong><span>不将发布表达为可运行</span></div></article>
    </section>
    <section className="px-truth-banner employee-trust-banner" role="status"><span className="px-status neutral">可信会话与当前授权</span><strong>读取已接通；写命令按已接受契约装配</strong><p>LIST 仅用于发现，每次详情仍独立执行 exact READ。CREATE、VALIDATE、APPROVE、PUBLISH 会在提交时重新读取 session 与 CSRF；权限取得路径仍由 305 闭合。</p><p>浏览器不发送身份 header，也不回退私有 API 或私有 actor。发布不等于可匹配、已实例化、已分配、已放置或已运行。</p></section>
    <nav className="px-view-tabs" aria-label="数字员工管理">{([[
      "definitions", "员工档案",
    ], ["create", "Agent 候选"], ["instance", "实例"], ["assignment", "工作分配"], ["work", "工作关联"]] as const).map(([key, label]) => <button key={key} className={panel === key ? "active" : ""} onClick={() => { setPanel(key); updateUrl({ panel: key }); }}>{label}</button>)}</nav>
    {detailBusy && <p role="status" className="agent-state">正在通过可信 session 读取 exact Definition……</p>}
    {workBusy && <p role="status" className="agent-state">正在按精确身份读取实例或工作分配……</p>}
    {error && <div role="alert" className="qto-alert"><strong>详情读取未完成</strong><span>{controlledMessage(error)}</span>{selectedIdentity && <button onClick={() => void readDefinitionExact(selectedIdentity)}>重新读取精确修订</button>}</div>}
    {workError && <div role="alert" className="qto-alert"><strong>工作关联读取未完成</strong><span>{controlledMessage(workError)}</span></div>}

    {panel === "definitions" && <div className="px-master-detail employee-master-detail"><aside><div className="employee-list-heading"><strong>数字员工定义</strong><span>{visible.length} 条当前页结果</span></div><label className="px-center-search">搜索当前已加载页<input value={query} onChange={event => updateUrl({ q: event.target.value })} placeholder="搜索职责角色或技术 ID" /></label><label className="px-center-search">发布状态<select value={status} onChange={event => updateUrl({ status: event.target.value })}><option value="ALL">全部状态</option><option value="PUBLISHED">已发布</option><option value="NOT_PUBLISHED">未发布</option></select></label><p className="employee-page-scope">搜索和筛选仅作用于已加载页，不代表全局结果。</p>{listError && <div role="alert" className="qto-alert"><strong>列表读取失败</strong><span>{controlledMessage(listError)}</span></div>}<nav aria-label="Employee Definition 列表" className="employee-definition-list">{visible.map(item => <button key={`${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`} className={selectedIdentity?.id === item.employeeDefinitionId && selectedIdentity.revision === item.employeeDefinitionRevisionId ? "selected" : ""} aria-current={selectedIdentity?.id === item.employeeDefinitionId && selectedIdentity.revision === item.employeeDefinitionRevisionId ? "true" : undefined} onClick={() => select(item)}><span className="employee-avatar" aria-hidden="true">员</span><span><strong>{item.role}</strong><small>正式名称未提供</small><small>{item.employeeDefinitionRevisionId}</small></span><span className={`employee-state-chip ${item.publicationState === "PUBLISHED" ? "published" : "draft"}`}>{item.publicationState === "PUBLISHED" ? "已发布" : "未发布"}</span></button>)}</nav>{!visible.length && listState === "READY" && !listError && <div className="px-empty"><strong>当前已加载页没有匹配定义</strong><p>不会将单页结果冒充完整集合，也不会用 Agent 身份填充。</p></div>}{nextCursor && <button type="button" className="employee-secondary-button" disabled={listState === "LOADING"} onClick={() => void loadMoreEmployees(nextCursor)}>{listState === "LOADING" ? "正在读取下一页……" : "加载下一页"}</button>}<small>LIST 仅返回发现摘要；每次选择都独立执行 exact READ。</small></aside><section>{selected ? <DefinitionDetail item={selected} latestCommand={latestCommand} onReadback={applyCommandReadback} /> : !detailBusy && !error ? <div className="px-empty large">尚未读取 Employee Definition 详情</div> : null}</section></div>}

    {panel === "create" && <EmployeeDefinitionAssembly agents={agents} hasMoreAgents={Boolean(agentNextCursor)} agentError={agentError ? controlledMessage(agentError) : undefined} onLoadMoreAgents={() => void loadMoreAgents()} onReadback={applyCommandReadback} />}

    {panel === "instance" && <section className="px-center-card employee-form"><h2>实例 · Digital Employee Instance</h2><p>当前正式端口不支持列表；仅以可信 session 和 exact Instance READ 读取已知 ID。读取到的 Definition ID/revision/digest 会再次 exact READ 核对。</p><Field label="Instance ID" value={instanceId} set={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setInstanceId(value); setInstance(null); setInstanceDefinition(null); setAssignment(null); }} /><div className="agent-actions"><button disabled title="可信 Instance 创建端口尚未注册">创建 Instance 尚未接通</button><button disabled={workBusy || !instanceId.trim()} onClick={() => void readInstanceExact()}>按精确 ID 读取</button></div>{instance && <InstanceDetail value={instance} boundDefinition={instanceDefinition} />}</section>}

    {panel === "assignment" && <section className="px-center-card employee-form"><h2>工作分配 · Assignment</h2><p>{instance ? `归属 Instance：${instance.instanceId}。Assignment 读取仍需独立 exact grant。` : "请先在“实例”页按精确 ID 读取；当前 API 没有 Assignment 列表。"}</p><Field label="Assignment ID" value={assignmentId} set={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setAssignmentId(value); setAssignment(null); }} /><div className="agent-actions"><button disabled title="可信 Assignment 创建端口尚未注册">创建 Assignment 尚未接通</button><button disabled={!instance || workBusy || !assignmentId.trim()} onClick={() => void readAssignmentExact()}>按精确 ID 读取</button></div>{assignment && <AssignmentDetail value={assignment} />}</section>}

    {panel === "work" && <EmployeeWorkParticipation key={`${instance?.instanceId ?? "none"}:${assignment?.assignmentId ?? "none"}`} definition={instanceDefinition} instance={instance} assignment={assignment} initialCoordinates={{ placementId: params.get("placementId") ?? "", attemptId: params.get("attemptId") ?? "", agentInstanceId: params.get("agentInstanceId") ?? "" }} onCoordinates={coordinates => updateUrl({ panel: "work", instanceId: instance?.instanceId ?? "", assignmentId: assignment?.assignmentId ?? "", ...coordinates })} />}
  </main>;
}

function Field({ label, value, set }: { label: string; value: string; set: (value: string) => void }) {
  return <label>{label}<input value={value} onChange={event => set(event.target.value)} /></label>;
}

function DefinitionDetail({ item, latestCommand, onReadback }: { item: EmployeeDefinition; latestCommand: EmployeeCommandResult | null; onReadback: (definition: EmployeeDefinition, result: EmployeeCommandResult) => void }) {
  const command = latestCommand?.employeeDefinitionId === item.employeeDefinitionId && latestCommand.employeeDefinitionRevisionId === item.employeeDefinitionRevisionId ? latestCommand : undefined;
  return <article className="px-object-detail"><EmployeeProfileLoader item={item} /><EmployeeLifecycleActions key={`${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`} item={item} initialResult={command} onReadback={onReadback} /><section className="employee-version-boundary"><span className="employee-capability-state missing"><i />未实现</span><h3>版本历史与变更</h3><p>当前最小 exact READ 不披露历史、相邻修订、变更时间或 actor；不以浏览器 diff 冒充审计记录。</p></section></article>;
}

function InstanceDetail({ value, boundDefinition }: { value: EmployeeInstance; boundDefinition: EmployeeDefinition | null }) {
  const reference = value.employeeDefinition ?? value.legacyDefinitionReference;
  return <dl className="employee-facts"><dt>Instance</dt><dd>{value.instanceId}</dd><dt>Identity boundary</dt><dd>{value.employeeDefinition ? "独立 Employee Definition" : "LEGACY_UNVERIFIED 历史引用（未迁移）"}</dd><dt>绑定 Definition</dt><dd>{reference?.employeeDefinitionId ?? "未提供"}</dd><dt>绑定 revision</dt><dd>{reference?.employeeDefinitionRevisionId ?? "未提供"}</dd><dt>绑定 digest</dt><dd>{reference?.digest ?? "未提供"}</dd><dt>绑定版本读取</dt><dd>{boundDefinition ? `${boundDefinition.role} · exact revision verified（允许合法历史发布版本）` : "尚无可核对的 Digital Employee Definition"}</dd><dt>Owner / organization</dt><dd>{value.ownerId} / {value.organizationId}</dd><dt>Lifecycle</dt><dd>{value.lifecycle}</dd><dt>Matching / Execution / Health</dt><dd>未披露 / {value.execution.reasonCode} / {value.health.reasonCode}</dd></dl>;
}

function AssignmentDetail({ value }: { value: EmployeeAssignment }) {
  return <dl className="employee-facts"><dt>Assignment / Instance</dt><dd>{value.assignmentId} / {value.instanceId}</dd><dt>状态与角色</dt><dd>{value.lifecycle} · {value.businessRole}</dd><dt>受派对象</dt><dd>{value.assigneeId}</dd><dt>有效期</dt><dd>{value.effectiveFrom} → {value.effectiveUntil ?? "无固定结束时间"}</dd><dt>Plan / Workflow 绑定</dt><dd>{value.binding.state} · {value.binding.reasonCode}</dd></dl>;
}
