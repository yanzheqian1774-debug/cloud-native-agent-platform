import {useManagementActions} from '../management/useManagementActions';
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

const requiredState: Record<Action, EmployeeLifecycleState> = { VALIDATE: "DRAFT", APPROVE: "VALIDATED", PUBLISH: "APPROVED" };
const targetState: Record<Action, EmployeeLifecycleState> = { VALIDATE: "VALIDATED", APPROVE: "APPROVED", PUBLISH: "PUBLISHED" };
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
  business = false,
}: {
  business?: boolean;
  item: EmployeeDefinition;
  initialResult?: EmployeeCommandResult;
  onReadback: (definition: EmployeeDefinition, result: EmployeeCommandResult) => void;
}) {
  const permissions=useManagementActions({kind:'employees',item});
  const actionLabel:Record<Action,string>=business?{VALIDATE:"验证草稿",APPROVE:"确认发布资格",PUBLISH:"发布定义"}:{VALIDATE:"校验修订",APPROVE:"批准修订",PUBLISH:"发布修订"};
  const [latest, setLatest] = useState(initialResult);
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

  const markerKey = (principal:string) => 'employee-lifecycle.v1:'+JSON.stringify([principal,item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]);
  useEffect(() => {
    let live=true;
    void getWorkbenchSession().then(session=>{
      const principal=workbenchPrincipalKey(session),raw=sessionStorage.getItem(markerKey(principal));
      if(!raw||!live)return;
      const original=JSON.parse(raw) as FrozenLifecycle;
      if(original.principalKey!==principal||!Object.hasOwn(requiredState,original.action)||original.command.employeeDefinitionDigest!==item.employeeDefinitionDigest.replace(/^sha256:/,'')||!Number.isInteger(original.command.expectedVersion)||original.command.expectedVersion<1||!original.command.commandId)throw Error('LIFECYCLE_INTENT_INVALID');
      setFrozen(original);setUnknown(true);setMessage('原操作结果尚未核实；只读取所选修订，不重复提交。');
    }).catch(()=>{if(live)setMessage('原操作依据尚未核实，请核对当前账号。')});
    return()=>{live=false};
    // The parent keys this component by the exact revision.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function recover() {
    if(!frozen||inFlight.current)return;
    inFlight.current=true;setBusy(true);const turn=++generation.current;
    try{
      const before=await getWorkbenchSession(),definition=await getEmployeeDefinition(item.employeeDefinitionId,item.employeeDefinitionRevisionId),after=await getWorkbenchSession();
      if(turn!==generation.current)return;
      if(workbenchPrincipalKey(before)!==frozen.principalKey||workbenchPrincipalKey(after)!==frozen.principalKey||definition.employeeDefinitionId!==item.employeeDefinitionId||definition.employeeDefinitionRevisionId!==item.employeeDefinitionRevisionId||definition.employeeDefinitionDigest!==item.employeeDefinitionDigest)throw Error('LIFECYCLE_READ_CONTEXT_CHANGED');
      const stages=['DRAFT','VALIDATED','APPROVED','PUBLISHED'];
      if(!Number.isInteger(definition.aggregateVersion)||(definition.aggregateVersion??0)<=frozen.command.expectedVersion||stages.indexOf(definition.lifecycleState??'')<stages.indexOf(targetState[frozen.action]))throw Error('LIFECYCLE_RESULT_UNCONFIRMED');
      const result:EmployeeCommandResult={resourceKind:definition.resourceKind,employeeDefinitionId:definition.employeeDefinitionId,employeeDefinitionRevisionId:definition.employeeDefinitionRevisionId,employeeDefinitionDigest:definition.employeeDefinitionDigest,aggregateVersion:definition.aggregateVersion!,lifecycleState:definition.lifecycleState!};
      sessionStorage.removeItem(markerKey(frozen.principalKey));setLatest(result);setFrozen(null);setUnknown(false);setCommandFailed(false);setMessage('已读回当前修订状态；原命令没有重发，此读取不代替原提交回执。');onReadback(definition,result);
    }catch{if(turn===generation.current)setMessage('原操作仍未核实；保留原记录，只读取，不重复提交。')}
    finally{inFlight.current=false;if(turn===generation.current)setBusy(false)}
  }

  async function prepare(action: Action) {
    if (lifecycle !== requiredState[action] || inFlight.current) return;
    inFlight.current = true;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setMessage(null);
    setCommandFailed(false);
    try {
      if(!permissions.allows(action,await permissions.refresh())) {setMessage("当前操作尚未获准；原内容保持不变。");return;}
      const session = await getWorkbenchSession(controller.signal);
      if (turn !== generation.current) return;
      const current = await getEmployeeDefinition(item.employeeDefinitionId, item.employeeDefinitionRevisionId, controller.signal);
      const checkedSession = await getWorkbenchSession(controller.signal);
      if (turn !== generation.current) return;
      if (workbenchPrincipalKey(session) !== workbenchPrincipalKey(checkedSession)) throw new DigitalEmployeeRequestError("WORKBENCH_SESSION_CONTEXT_CHANGED", 409);
      if (!Number.isInteger(current.aggregateVersion) || (current.aggregateVersion ?? 0) < 1) {
        setMessage("当前服务未提供可核验版本，暂不能提交。请联系管理员更新服务后重新查询。");
        return;
      }
      if (current.lifecycleState !== requiredState[action] || current.employeeDefinitionDigest !== item.employeeDefinitionDigest) {
        setMessage("对象状态或修订已变化，请刷新详情后核对当前可操作事项；本次未提交。");
        return;
      }
      const command: EmployeeLifecycleCommand = Object.freeze({
        employeeDefinitionDigest: current.employeeDefinitionDigest.replace(/^sha256:/, ""),
        expectedVersion: current.aggregateVersion!,
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
    if (!frozen || unknown || inFlight.current) return;
    inFlight.current = true;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setMessage(null);
    try {
      if(!permissions.allows(frozen.action,await permissions.refresh())) {setMessage("当前操作尚未获准；原记录仍保留。");return;}
      const call = frozen.action === "VALIDATE" ? validateEmployeeDefinition
        : frozen.action === "APPROVE" ? approveEmployeeDefinition
          : publishEmployeeDefinition;
      sessionStorage.setItem(markerKey(frozen.principalKey),JSON.stringify(frozen));
      const result = await call(
        item.employeeDefinitionId,
        item.employeeDefinitionRevisionId,
        frozen.command,
        frozen.principalKey,
        controller.signal,
      );
      if (turn !== generation.current) return;
      const checked=await getWorkbenchSession(controller.signal);
      if(turn!==generation.current)return;
      if(workbenchPrincipalKey(checked)!==frozen.principalKey||result.resourceKind!==item.resourceKind||result.employeeDefinitionId!==item.employeeDefinitionId||result.employeeDefinitionRevisionId!==item.employeeDefinitionRevisionId||result.employeeDefinitionDigest!==item.employeeDefinitionDigest||result.aggregateVersion!==frozen.command.expectedVersion+1||result.lifecycleState!==targetState[frozen.action])throw new DigitalEmployeeRequestError('EMPLOYEE_RECEIPT_MISMATCH',503,true);
      sessionStorage.removeItem(markerKey(frozen.principalKey));
      setLatest(result);
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
      if(!value.unknownResult)sessionStorage.removeItem(markerKey(frozen.principalKey));
      setUnknown(value.unknownResult);
      setNeedsAuthorization(!value.unknownResult && (value.status === 403 || value.status === 404));
      setCommandFailed(true);
      setMessage(value.unknownResult
        ? "结果未知；原操作已保留，只读取原修订，不重复提交。"
        : errorMessage(value));
      if (value.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") setFrozen(null);
    } finally {
      inFlight.current = false;
      if (turn === generation.current) setBusy(false);
    }
  }

  return <section className="employee-lifecycle" aria-labelledby="employee-lifecycle-title">
    <header className="employee-section-heading"><div><h3 id="employee-lifecycle-title">{business?"验证与发布":"生命周期操作"}</h3><p>校验、批准和发布是独立操作；每次提交都会重新核对当前访问权限。</p></div><span className={`employee-capability-state ${lifecycle ? "available" : "warning"}`}><i />{lifecycle ? `当前状态 · ${lifecycleLabel[lifecycle]}` : "部分实现 · 正式详情接口未提供状态"}</span></header>
    <p className="employee-honesty-note">系统在准备操作时核对最新状态与版本；确认前不会提交业务命令。</p>
    {!["VALIDATE","APPROVE","PUBLISH"].some(action=>permissions.allows(action))&&<p role="status">{permissions.ready?"当前没有可执行的验证或发布操作。":"正在核对验证与发布资格。"}<button onClick={()=>void permissions.refresh()}>重新核对操作资格</button></p>}
    <div className="employee-lifecycle-flow">{(["VALIDATE", "APPROVE", "PUBLISH"] as const).filter(action=>permissions.allows(action)).map(action => <button type="button" key={action} disabled={busy || Boolean(frozen) || lifecycle !== requiredState[action]} onClick={() => void prepare(action)}><span>{actionLabel[action]}</span><small>需要当前操作权限与成员读取权限</small></button>)}</div>
    {!lifecycle && <p className="employee-honesty-note">当前 exact 详情响应没有生命周期字段，无法仅凭“未发布”判断阶段。获得正式状态后才能启用操作。</p>}
    {frozen && <div className="employee-command-confirmation"><span className="employee-confirmation-state">等待用户明确确认</span><h4>{actionLabel[frozen.action]} · {item.role}</h4>{business?<p>将对当前选中的草稿执行{actionLabel[frozen.action]}；已有任务保持原引用。</p>:<p>将对所选修订 <code>{item.employeeDefinitionRevisionId}</code> 使用版本 {frozen.command.expectedVersion}。</p>}<details><summary>查看冻结 commandId 与摘要</summary><code>{frozen.command.commandId}</code><code>{frozen.command.employeeDefinitionDigest}</code></details><div className="employee-form-actions"><button type="button" className="employee-secondary-button" disabled={busy || unknown} onClick={() => setFrozen(null)}>取消</button><button type="button" className="px-primary-button" hidden={!unknown&&!permissions.allows(frozen.action)} style={!unknown&&!permissions.allows(frozen.action)?{display:'none'}:undefined} disabled={busy} onClick={() => void (unknown ? recover() : submit())}>{busy ? "正在核对……" : unknown ? "读取原修订状态" : "确认提交"}</button></div></div>}
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
    {!business&&<div className="employee-unavailable-actions"><span className="employee-capability-state missing"><i />未实现</span><p>原修订不原地编辑，可在后继维护中调整职责与资源；删除、停用和实例化继续保留为欠项。</p></div>}
  </section>;
}
