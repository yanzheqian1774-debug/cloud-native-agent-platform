import { useEffect, useRef, useState } from "react";
import {
  approveEmployeeDefinition,
  DigitalEmployeeRequestError,
  getEmployeeDefinition,
  getWorkbenchSession,
  publishEmployeeDefinition,
  validateEmployeeDefinition,
  workbenchPrincipalKey,
  type EmployeeCommandResult,
  type EmployeeDefinition,
  type EmployeeLifecycleCommand,
  type EmployeeLifecycleState,
} from "../api/digitalEmployees";
import { EmployeeAuthorizationRequest } from "./EmployeeAuthorizationRequest";

type Action = "VALIDATE" | "APPROVE" | "PUBLISH";
type FrozenLifecycle = { action: Action; command: EmployeeLifecycleCommand; principalKey: string };

const actionLabel: Record<Action, string> = { VALIDATE: "校验修订", APPROVE: "批准修订", PUBLISH: "发布修订" };
const requiredState: Record<Action, EmployeeLifecycleState> = { VALIDATE: "DRAFT", APPROVE: "VALIDATED", PUBLISH: "APPROVED" };
const lifecycleLabel: Record<EmployeeLifecycleState, string> = {
  DRAFT: "草稿",
  VALIDATED: "已校验",
  APPROVED: "已批准",
  PUBLISHED: "已发布",
  REJECTED: "已拒绝",
  DEPRECATED: "已弃用",
};

function errorMessage(error: DigitalEmployeeRequestError) {
  if (error.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") return "可信会话已切换；原命令未发送。";
  if (error.status === 401) return "可信会话已失效。";
  if (error.status === 403 || error.status === 404) return "动作权限或成员详情读取权限不足；资源存在性不披露。";
  if (error.status === 409) return `CAS、摘要、转换或成员当前资格冲突：${error.reasonCode}`;
  if (error.status === 422) return `命令不符合正式契约：${error.reasonCode}`;
  return `服务暂不可用：${error.reasonCode}`;
}

export function EmployeeLifecycleActions({
  item,
  initialResult,
  onReadback,
}: {
  item: EmployeeDefinition;
  initialResult?: EmployeeCommandResult;
  onReadback: (definition: EmployeeDefinition, result: EmployeeCommandResult) => void;
}) {
  const [latest, setLatest] = useState(initialResult);
  const [expectedVersion, setExpectedVersion] = useState(initialResult ? String(initialResult.aggregateVersion) : "");
  const [frozen, setFrozen] = useState<FrozenLifecycle | null>(null);
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [commandFailed, setCommandFailed] = useState(false);
  const [needsAuthorization, setNeedsAuthorization] = useState(false);
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const inFlight = useRef(false);
  const lifecycle = latest?.lifecycleState ?? item.lifecycleState;

  useEffect(() => () => {
    generation.current += 1;
    activeRequest.current?.abort();
  }, []);

  async function prepare(action: Action) {
    const version = Number(expectedVersion);
    if (!Number.isInteger(version) || version < 1 || lifecycle !== requiredState[action] || inFlight.current) return;
    inFlight.current = true;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setMessage(null);
    setCommandFailed(false);
    try {
      const session = await getWorkbenchSession(controller.signal);
      if (turn !== generation.current) return;
      const command: EmployeeLifecycleCommand = Object.freeze({
        employeeDefinitionDigest: item.employeeDefinitionDigest.replace(/^sha256:/, ""),
        expectedVersion: version,
        commandId: `employee-${action.toLowerCase()}:${crypto.randomUUID()}`,
      });
      setFrozen({ action, command, principalKey: workbenchPrincipalKey(session) });
      setUnknown(false);
      setNeedsAuthorization(false);
      setCommandFailed(false);
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError ? reason : new DigitalEmployeeRequestError("WORKBENCH_SESSION_UNAVAILABLE", 503);
      setMessage(errorMessage(value));
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
    setMessage(null);
    try {
      const call = frozen.action === "VALIDATE" ? validateEmployeeDefinition
        : frozen.action === "APPROVE" ? approveEmployeeDefinition
          : publishEmployeeDefinition;
      const result = await call(
        item.employeeDefinitionId,
        item.employeeDefinitionRevisionId,
        frozen.command,
        frozen.principalKey,
        controller.signal,
      );
      if (turn !== generation.current) return;
      setLatest(result);
      setExpectedVersion(String(result.aggregateVersion));
      setFrozen(null);
      setUnknown(false);
      setNeedsAuthorization(false);
      setCommandFailed(false);
      try {
        const definition = await getEmployeeDefinition(result.employeeDefinitionId, result.employeeDefinitionRevisionId, controller.signal);
        if (turn !== generation.current) return;
        setMessage(`${actionLabel[frozen.action]}已确认，并完成所选修订核对。`);
        onReadback(definition, result);
      } catch (readReason) {
        if (turn !== generation.current || (readReason instanceof DOMException && readReason.name === "AbortError")) return;
        const readError = readReason instanceof DigitalEmployeeRequestError ? readReason : null;
        setMessage(readError && (readError.status === 403 || readError.status === 404)
          ? `${actionLabel[frozen.action]}命令已确认；当前无权读取详情。`
          : `${actionLabel[frozen.action]}命令已确认；详情读回暂不可用。`);
      }
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      if (turn !== generation.current) return;
      const value = reason instanceof DigitalEmployeeRequestError ? reason : new DigitalEmployeeRequestError("EMPLOYEE_COMMAND_RESULT_UNKNOWN", 503, true);
      setUnknown(value.unknownResult);
      setNeedsAuthorization(!value.unknownResult && (value.status === 403 || value.status === 404));
      setCommandFailed(true);
      setMessage(value.unknownResult
        ? "结果未知；原 commandId、摘要和 expectedVersion 已冻结，只能重放原命令。"
        : errorMessage(value));
      if (value.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") setFrozen(null);
    } finally {
      inFlight.current = false;
      if (turn === generation.current) setBusy(false);
    }
  }

  return <section className="employee-lifecycle" aria-labelledby="employee-lifecycle-title">
    <header className="employee-section-heading"><div><h3 id="employee-lifecycle-title">生命周期操作</h3><p>校验、批准和发布是独立操作；每次提交都会重新核对当前访问权限。</p></div><span className={`employee-capability-state ${lifecycle ? "available" : "warning"}`}><i />{lifecycle ? `当前状态 · ${lifecycleLabel[lifecycle]}` : "部分实现 · 正式详情接口未提供状态"}</span></header>
    <label className="employee-version-input">期望聚合版本<input type="number" min="1" step="1" value={expectedVersion} onChange={event => { setExpectedVersion(event.target.value); setFrozen(null); }} /><small>{latest ? "来源：最近一次正式命令结果" : "当前详情不披露聚合版本，请使用权威命令结果。"}</small></label>
    <div className="employee-lifecycle-flow">{(["VALIDATE", "APPROVE", "PUBLISH"] as const).map(action => <button type="button" key={action} disabled={busy || Boolean(frozen) || lifecycle !== requiredState[action] || !Number.isInteger(Number(expectedVersion)) || Number(expectedVersion) < 1} onClick={() => void prepare(action)}><span>{actionLabel[action]}</span><small>需要当前操作权限与成员读取权限</small></button>)}</div>
    {!lifecycle && <p className="employee-honesty-note">当前 exact 详情响应没有生命周期字段，无法仅凭“未发布”判断阶段。获得正式状态后才能启用操作。</p>}
    {frozen && <div className="employee-command-confirmation"><span className="employee-confirmation-state">等待用户明确确认</span><h4>{actionLabel[frozen.action]} · {item.role}</h4><p>将对所选修订 <code>{item.employeeDefinitionRevisionId}</code> 使用版本 {frozen.command.expectedVersion}。</p><details><summary>查看冻结 commandId 与摘要</summary><code>{frozen.command.commandId}</code><code>{frozen.command.employeeDefinitionDigest}</code></details><div className="employee-form-actions"><button type="button" className="employee-secondary-button" disabled={busy || unknown} onClick={() => setFrozen(null)}>取消</button><button type="button" className="px-primary-button" disabled={busy} onClick={() => void submit()}>{busy ? "正在提交……" : unknown ? "重放原命令" : "确认提交"}</button></div></div>}
    {needsAuthorization && frozen && <EmployeeAuthorizationRequest
      title={`申请${actionLabel[frozen.action]}所需权限`}
      grants={[
        { owner: "EMPLOYEE", action: frozen.action, resource: `employee:${item.employeeDefinitionId}:aggregate` },
        { owner: "EMPLOYEE", action: "READ", resource: `employee:${item.employeeDefinitionId}:${item.employeeDefinitionRevisionId}` },
        ...item.members.filter(member => member.kind === "AGENT").map(member => ({
          owner: "AGENT" as const,
          action: "READ" as const,
          resource: `agent:${member.resourceId}:${member.revisionId}`,
        })),
      ]}
      principalKey={frozen.principalKey}
      onApproved={submit}
    />}
    {message && <div role={unknown || commandFailed ? "alert" : "status"} className={`employee-command-state ${unknown ? "unknown" : commandFailed ? "failed" : "success"}`}><strong>{unknown ? "结果未知" : commandFailed ? "命令未执行" : "命令状态"}</strong><span>{message}</span></div>}
    <div className="employee-unavailable-actions"><span className="employee-capability-state missing"><i />未实现</span><p>编辑、删除、停用、实例化没有本轮已接受正式契约，继续保留为欠项。</p></div>
  </section>;
}
