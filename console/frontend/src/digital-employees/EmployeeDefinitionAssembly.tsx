import { useEffect, useRef, useState } from "react";
import {
  createEmployeeDefinition,
  DigitalEmployeeRequestError,
  getEmployeeDefinition,
  getWorkbenchSession,
  workbenchPrincipalKey,
  type AgentDefinitionSummary,
  type EmployeeCommandResult,
  type EmployeeCreateCommand,
  type EmployeeDefinition,
  type EmployeeLifecycleState,
} from "../api/digitalEmployees";

type FrozenCreate = { command: EmployeeCreateCommand; principalKey: string };

const lifecycleLabel: Record<EmployeeLifecycleState, string> = {
  DRAFT: "草稿",
  VALIDATED: "已校验",
  APPROVED: "已批准",
  PUBLISHED: "已发布",
  REJECTED: "已拒绝",
  DEPRECATED: "已弃用",
};

function commandMessage(error: DigitalEmployeeRequestError) {
  if (error.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") return "可信会话已切换；原命令未发送，请重新确认。";
  if (error.status === 401) return "可信会话已失效，请重新登录后再确认。";
  if (error.status === 403 || error.status === 404) return "当前身份没有创建权限，或依赖资源不可用。";
  if (error.status === 409) return `版本、摘要或幂等冲突：${error.reasonCode}`;
  if (error.status === 422) return `输入未通过正式契约校验：${error.reasonCode}`;
  return `服务暂不可用：${error.reasonCode}`;
}

export function EmployeeDefinitionAssembly({
  agents,
  hasMoreAgents,
  agentError,
  onLoadMoreAgents,
  onReadback,
}: {
  agents: AgentDefinitionSummary[];
  hasMoreAgents: boolean;
  agentError?: string;
  onLoadMoreAgents: () => void;
  onReadback: (definition: EmployeeDefinition, result: EmployeeCommandResult) => void;
}) {
  const [definitionId, setDefinitionId] = useState("");
  const [revisionId, setRevisionId] = useState("");
  const [role, setRole] = useState("");
  const [responsibilities, setResponsibilities] = useState("");
  const [agentIdentity, setAgentIdentity] = useState("");
  const [frozen, setFrozen] = useState<FrozenCreate | null>(null);
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<EmployeeCommandResult | null>(null);
  const [readback, setReadback] = useState<"NONE" | "READABLE" | "HIDDEN" | "UNAVAILABLE">("NONE");
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const inFlight = useRef(false);

  useEffect(() => () => {
    generation.current += 1;
    activeRequest.current?.abort();
  }, []);

  const selectedAgent = agents.find(agent => `${agent.definitionId}\u0000${agent.revisionId}` === agentIdentity);
  const responsibilityList = responsibilities.split("\n").map(value => value.trim()).filter(Boolean);
  const valid = Boolean(
    definitionId.trim()
    && revisionId.trim()
    && role.trim()
    && responsibilityList.length >= 1
    && responsibilityList.length <= 32
    && selectedAgent?.enabled
    && !selectedAgent?.archived,
  );

  async function prepare() {
    if (!valid || !selectedAgent || inFlight.current) return;
    inFlight.current = true;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setError(null);
    try {
      const session = await getWorkbenchSession(controller.signal);
      if (turn !== generation.current) return;
      const command: EmployeeCreateCommand = {
        employeeDefinitionId: definitionId.trim(),
        employeeDefinitionRevisionId: revisionId.trim(),
        role: role.trim(),
        responsibilities: [...responsibilityList],
        members: [{
          kind: "AGENT",
          resourceId: selectedAgent.definitionId,
          revisionId: selectedAgent.revisionId,
          digest: selectedAgent.digest,
        }],
        expectedVersion: 0,
        commandId: `employee-command:${crypto.randomUUID()}`,
      };
      Object.freeze(command.responsibilities);
      Object.freeze(command.members[0]);
      Object.freeze(command.members);
      Object.freeze(command);
      setFrozen({ command, principalKey: workbenchPrincipalKey(session) });
      setUnknown(false);
      setResult(null);
      setReadback("NONE");
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError
        ? reason
        : new DigitalEmployeeRequestError("WORKBENCH_SESSION_UNAVAILABLE", 503);
      setError(commandMessage(value));
    } finally {
      inFlight.current = false;
      if (turn === generation.current) setBusy(false);
    }
  }

  async function submit() {
    if (!frozen || inFlight.current) return;
    inFlight.current = true;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setError(null);
    try {
      const value = await createEmployeeDefinition(frozen.command, frozen.principalKey, controller.signal);
      if (turn !== generation.current) return;
      setResult(value);
      setUnknown(false);
      setFrozen(null);
      try {
        const definition = await getEmployeeDefinition(value.employeeDefinitionId, value.employeeDefinitionRevisionId, controller.signal);
        if (turn !== generation.current) return;
        setReadback("READABLE");
        onReadback(definition, value);
      } catch (readReason) {
        if (turn !== generation.current || (readReason instanceof DOMException && readReason.name === "AbortError")) return;
        const readError = readReason instanceof DigitalEmployeeRequestError ? readReason : null;
        setReadback(readError && (readError.status === 403 || readError.status === 404) ? "HIDDEN" : "UNAVAILABLE");
      }
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError
        ? reason
        : new DigitalEmployeeRequestError("EMPLOYEE_COMMAND_RESULT_UNKNOWN", 503, true);
      setUnknown(value.unknownResult);
      setError(value.unknownResult
        ? "创建结果未知。原 commandId 与语义 payload 已冻结；只能重放下面的原命令。"
        : commandMessage(value));
      if (value.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") setFrozen(null);
    } finally {
      inFlight.current = false;
      if (turn === generation.current) setBusy(false);
    }
  }

  return <section className="employee-assembly" aria-labelledby="employee-create-title">
    <header className="employee-section-heading">
      <div><p className="eyebrow">首批单 Agent 装配</p><h2 id="employee-create-title">创建数字员工定义</h2><p>先定义员工角色与职责，再选择一个正式 Agent 候选完成装配。</p></div>
      <span className="employee-capability-state partial"><i />部分实现 · 正式权限路径待接通</span>
    </header>

    <div className="employee-assembly-grid">
      <div className="employee-form-card">
        <h3>1. 业务定义</h3>
        <label>职责角色<input value={role} maxLength={200} onChange={event => setRole(event.target.value)} placeholder="例如：供应商质量负责人" /></label>
        <label>职责清单（每行一项，1–32 项）<textarea value={responsibilities} onChange={event => setResponsibilities(event.target.value)} placeholder="审查供应商质量异常&#10;协调整改与复核" /></label>
        <details><summary>高级设置 · 技术身份需配置（2 项必填）</summary>
          <p className="employee-identity-requirement">正式 CREATE 契约要求两个技术 ID，当前没有已批准的自动生成规则。首次创建不需要前驱修订，聚合版本固定从 0 开始。</p>
          <label>Employee Definition ID<input value={definitionId} onChange={event => setDefinitionId(event.target.value)} placeholder="employee:quality-lead" /></label>
          <label>Revision ID<input value={revisionId} onChange={event => setRevisionId(event.target.value)} placeholder="employee-revision:quality-lead:1" /></label>
        </details>
      </div>

      <div className="employee-form-card">
        <h3>2. 选择一个正式 Agent 候选</h3>
        <p>这里显示可用于创建的候选；它们不同于员工详情中的已绑定成员。选择候选不会授予详情读取权限。</p>
        {agentError && <p role="alert" className="employee-inline-error">{agentError}</p>}
        <div className="employee-agent-options">{agents.map(agent => { const identity = `${agent.definitionId}\u0000${agent.revisionId}`; const selectable = agent.enabled && !agent.archived; const chosen = agentIdentity === identity; return <label key={identity} className={chosen ? "selected" : ""}>
          <input type="radio" name="employee-agent" checked={agentIdentity === identity} disabled={!agent.enabled || agent.archived || Boolean(frozen)} onChange={() => setAgentIdentity(identity)} />
          <span className="employee-avatar" aria-hidden="true">A</span>
          <span><strong>{agent.name}</strong><span className="employee-agent-role">{agent.title || "未提供角色标题"}</span><small>{agent.revisionId}</small><span className={`employee-agent-choice-state ${chosen ? "chosen" : ""}`}>{chosen ? "已选择" : selectable ? "选择此候选" : "当前不可用于创建"}</span></span>
        </label>; })}</div>
        {hasMoreAgents && <button type="button" className="employee-secondary-button" onClick={onLoadMoreAgents}>加载更多 Agent</button>}
      </div>
    </div>

    {!frozen && <div className="employee-form-actions"><span>{valid ? "输入已满足前端校验；正式 owner 仍会再次校验。" : "请填写业务定义、选择一个可用 Agent，并在高级设置中配置契约要求的技术 ID。"}</span><button type="button" className="px-primary-button" disabled={!valid || busy} onClick={() => void prepare()}>检查并进入确认</button></div>}

    {frozen && <section className="employee-command-confirmation" aria-label="创建命令确认">
      <span className="employee-confirmation-state">等待用户明确确认</span>
      <h3>{frozen.command.role}</h3>
      <p>{frozen.command.responsibilities.join("；")}</p>
      <p>成员：{frozen.command.members[0].resourceId} / {frozen.command.members[0].revisionId}</p>
      <details><summary>查看冻结命令身份</summary><code>{frozen.command.commandId}</code><code>{frozen.command.employeeDefinitionId}</code><code>{frozen.command.employeeDefinitionRevisionId}</code></details>
      <div className="employee-form-actions"><button type="button" className="employee-secondary-button" disabled={busy || unknown} onClick={() => setFrozen(null)}>返回修改</button><button type="button" className="px-primary-button" disabled={busy} onClick={() => void submit()}>{busy ? "正在提交……" : unknown ? "重放原命令" : "确认创建"}</button></div>
    </section>}

    {error && <div role="alert" className={`employee-command-state ${unknown ? "unknown" : "failed"}`}><strong>{unknown ? "结果未知" : "命令未确认成功"}</strong><span>{error}</span></div>}
    {result && <div role="status" className="employee-command-state success"><strong>创建命令已确认 · {lifecycleLabel[result.lifecycleState]}</strong><span>聚合版本 {result.aggregateVersion} · {result.employeeDefinitionRevisionId}</span>{readback === "HIDDEN" && <span>当前无权读取详情；这不表示创建失败。</span>}{readback === "UNAVAILABLE" && <span>命令已确认，但详情读回暂不可用。</span>}{readback === "READABLE" && <span>已核对所选修订详情。</span>}</div>}
  </section>;
}
