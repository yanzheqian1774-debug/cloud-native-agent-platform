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
  type EmployeeDefinitionSummary,
  type EmployeeInstance,
} from "../api/digitalEmployees";
import { EmployeeProfileLoader } from "./EmployeeProfile";
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
    <header className="px-page-title"><div><p>数字员工 <small>Digital Employee</small></p><h1>数字员工定义与身份链管理</h1><span>Employee Definition、Agent exact revision 与 Instance 保持独立身份。</span></div><button className="px-primary-button" onClick={() => { setPanel("create"); updateUrl({ panel: "create" }); }}>查看可信 Agent 候选</button></header>
    <section className="px-truth-banner" role="status"><span className="px-status neutral">TRUSTED READ BFF</span><strong>数字员工只读页面已切换到可信 session 与当前 grant</strong><p>Agent/Employee LIST 与 exact revision、Instance、Assignment、Placement 读取均使用正式 Workbench BFF；LIST 仅用于发现，不授予详情 READ。</p><p>Definition publicationState 不等于 matchability；Runtime Profile 绑定不代表 Runtime 已启动；Assignment 存在不代表员工正在工作。</p><p>创建、生命周期、通用 Execution、Runtime 观测、Evidence 与 Outcome 仍未接通，本页面不会退回客户端身份 header 或私有 actor。</p></section>
    <nav className="px-view-tabs" aria-label="数字员工管理">{([[
      "definitions", "员工档案",
    ], ["create", "Agent 候选"], ["instance", "实例"], ["assignment", "工作分配"], ["work", "工作关联"]] as const).map(([key, label]) => <button key={key} className={panel === key ? "active" : ""} onClick={() => { setPanel(key); updateUrl({ panel: key }); }}>{label}</button>)}</nav>
    {detailBusy && <p role="status" className="agent-state">正在通过可信 session 读取 exact Definition……</p>}
    {workBusy && <p role="status" className="agent-state">正在按精确身份读取实例或工作分配……</p>}
    {error && <div role="alert" className="qto-alert"><strong>{error.kind}</strong><span>{controlledMessage(error)}</span>{selectedIdentity && <button onClick={() => void readDefinitionExact(selectedIdentity)}>重新读取 exact revision</button>}</div>}
    {workError && <div role="alert" className="qto-alert"><strong>{workError.kind}</strong><span>{controlledMessage(workError)}</span></div>}

    {panel === "definitions" && <div className="px-master-detail"><aside><label className="px-center-search">当前已加载页搜索<input value={query} onChange={event => updateUrl({ q: event.target.value })} /></label><label className="px-center-search">发布状态筛选<select value={status} onChange={event => updateUrl({ status: event.target.value })}><option value="ALL">ALL</option><option value="PUBLISHED">PUBLISHED</option><option value="NOT_PUBLISHED">NOT_PUBLISHED</option></select></label>{listError && <div role="alert" className="qto-alert"><strong>{listError.kind}</strong><span>{controlledMessage(listError)}</span></div>}<nav aria-label="Employee Definition 列表">{visible.map(item => <button key={`${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}`} className={selectedIdentity?.id === item.employeeDefinitionId && selectedIdentity.revision === item.employeeDefinitionRevisionId ? "selected" : ""} onClick={() => select(item)}><strong>{item.role}</strong><small>{item.publicationState} · {item.employeeDefinitionRevisionId}</small></button>)}</nav>{!visible.length && listState === "READY" && !listError && <div className="px-empty"><strong>当前已加载页没有匹配定义</strong><p>不会将单页结果冒充完整集合，也不会用 Agent 身份填充。</p></div>}{nextCursor && <button type="button" disabled={listState === "LOADING"} onClick={() => void loadMoreEmployees(nextCursor)}>{listState === "LOADING" ? "正在读取下一页……" : "加载下一页"}</button>}<small>LIST 仅返回发现摘要；每次选择都独立执行 exact READ。</small></aside><section>{selected ? <DefinitionDetail item={selected} /> : !detailBusy && !error ? <div className="px-empty large">尚未读取 Employee Definition 详情</div> : null}</section></div>}

    {panel === "create" && <section className="px-center-card employee-form"><h2>可信 Agent 候选 · 只读</h2><p>该 LIST 只包含正式 owner 选定的发布 revision；不会选择第一条或推断 latest。Agent LIST 不授予 exact READ，Digital Employee 创建写端口尚未接通。</p>{agentError && <div role="alert" className="qto-alert"><strong>{agentError.kind}</strong><span>{controlledMessage(agentError)}</span></div>}<ul className="px-binding-list">{agents.map(agent => <li key={agent.definitionId}><span>{agent.name}</span><strong>{agent.title}</strong><small>{agent.definitionId} · {agent.revisionId}</small><small>{agent.enabled && !agent.archived ? "正式发布候选" : "发布 revision；当前不可用于创建"}</small></li>)}</ul>{agentNextCursor && <button type="button" onClick={() => void loadMoreAgents()}>加载更多 Agent</button>}<button className="px-primary-button" disabled title="可信创建端口尚未注册">创建数字员工定义尚未接通</button></section>}

    {panel === "instance" && <section className="px-center-card employee-form"><h2>实例 · Digital Employee Instance</h2><p>当前正式端口不支持列表；仅以可信 session 和 exact Instance READ 读取已知 ID。读取到的 Definition ID/revision/digest 会再次 exact READ 核对。</p><Field label="Instance ID" value={instanceId} set={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setInstanceId(value); setInstance(null); setInstanceDefinition(null); setAssignment(null); }} /><div className="agent-actions"><button disabled title="可信 Instance 创建端口尚未注册">创建 Instance 尚未接通</button><button disabled={workBusy || !instanceId.trim()} onClick={() => void readInstanceExact()}>按精确 ID 读取</button></div>{instance && <InstanceDetail value={instance} boundDefinition={instanceDefinition} />}</section>}

    {panel === "assignment" && <section className="px-center-card employee-form"><h2>工作分配 · Assignment</h2><p>{instance ? `归属 Instance：${instance.instanceId}。Assignment 读取仍需独立 exact grant。` : "请先在“实例”页按精确 ID 读取；当前 API 没有 Assignment 列表。"}</p><Field label="Assignment ID" value={assignmentId} set={value => { workGeneration.current += 1; activeWorkRead.current?.abort(); setWorkState("READY"); setAssignmentId(value); setAssignment(null); }} /><div className="agent-actions"><button disabled title="可信 Assignment 创建端口尚未注册">创建 Assignment 尚未接通</button><button disabled={!instance || workBusy || !assignmentId.trim()} onClick={() => void readAssignmentExact()}>按精确 ID 读取</button></div>{assignment && <AssignmentDetail value={assignment} />}</section>}

    {panel === "work" && <EmployeeWorkParticipation key={`${instance?.instanceId ?? "none"}:${assignment?.assignmentId ?? "none"}`} definition={instanceDefinition} instance={instance} assignment={assignment} initialCoordinates={{ placementId: params.get("placementId") ?? "", attemptId: params.get("attemptId") ?? "", agentInstanceId: params.get("agentInstanceId") ?? "" }} onCoordinates={coordinates => updateUrl({ panel: "work", instanceId: instance?.instanceId ?? "", assignmentId: assignment?.assignmentId ?? "", ...coordinates })} />}
  </main>;
}

function Field({ label, value, set }: { label: string; value: string; set: (value: string) => void }) {
  return <label>{label}<input value={value} onChange={event => set(event.target.value)} /></label>;
}

function DefinitionDetail({ item }: { item: EmployeeDefinition }) {
  return <article className="px-object-detail"><EmployeeProfileLoader item={item} /><section><h3>独立生命周期操作</h3><div className="agent-actions"><button disabled>验证 exact revision</button><button disabled>人工审核 exact digest</button><button disabled>发布 immutable revision</button></div><p>可信写端口未在固定 305 候选中注册；不退回私有 header API。</p></section><section><h3>版本与变更</h3><p>当前最小 exact READ 不披露 history、aggregate facts 或相邻 revision；保持未接通。</p></section></article>;
}

function InstanceDetail({ value, boundDefinition }: { value: EmployeeInstance; boundDefinition: EmployeeDefinition | null }) {
  const reference = value.employeeDefinition ?? value.legacyDefinitionReference;
  return <dl className="employee-facts"><dt>Instance</dt><dd>{value.instanceId}</dd><dt>Identity boundary</dt><dd>{value.employeeDefinition ? "独立 Employee Definition" : "LEGACY_UNVERIFIED 历史引用（未迁移）"}</dd><dt>绑定 Definition</dt><dd>{reference?.employeeDefinitionId ?? "未提供"}</dd><dt>绑定 revision</dt><dd>{reference?.employeeDefinitionRevisionId ?? "未提供"}</dd><dt>绑定 digest</dt><dd>{reference?.digest ?? "未提供"}</dd><dt>绑定版本读取</dt><dd>{boundDefinition ? `${boundDefinition.role} · exact revision verified（允许合法历史发布版本）` : "尚无可核对的 Digital Employee Definition"}</dd><dt>Owner / organization</dt><dd>{value.ownerId} / {value.organizationId}</dd><dt>Lifecycle</dt><dd>{value.lifecycle}</dd><dt>Matching / Execution / Health</dt><dd>未披露 / {value.execution.reasonCode} / {value.health.reasonCode}</dd></dl>;
}

function AssignmentDetail({ value }: { value: EmployeeAssignment }) {
  return <dl className="employee-facts"><dt>Assignment / Instance</dt><dd>{value.assignmentId} / {value.instanceId}</dd><dt>状态与角色</dt><dd>{value.lifecycle} · {value.businessRole}</dd><dt>受派对象</dt><dd>{value.assigneeId}</dd><dt>有效期</dt><dd>{value.effectiveFrom} → {value.effectiveUntil ?? "无固定结束时间"}</dd><dt>Plan / Workflow 绑定</dt><dd>{value.binding.state} · {value.binding.reasonCode}</dd></dl>;
}
