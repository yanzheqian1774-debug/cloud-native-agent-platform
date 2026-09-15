import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  decideEmployeeGrantRequest,
  DigitalEmployeeRequestError,
  getWorkbenchSession,
  inspectEmployeeGrantRequest,
  workbenchPrincipalKey,
  type GrantRequestStatus,
  type WorkbenchSession,
} from "../api/digitalEmployees";

function adminMessage(error: unknown) {
  if (!(error instanceof DigitalEmployeeRequestError)) return "授权服务暂不可用。";
  if (error.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") return "管理员会话已切换，请重新检查申请。";
  if (error.reasonCode === "GRANT_SELF_APPROVAL_PROHIBITED") return "申请人与决定人相同，不能作出独立决定。";
  if (error.status === 401) return "管理员会话已失效，请重新登录。";
  if (error.status === 404) return "申请不可见、已越权，或当前身份不能作出独立决定。";
  if (error.status === 409) return `申请状态已变化；请重新检查，不会自动替换基线。${error.reasonCode}`;
  if (error.status === 422) return `决定不符合正式契约：${error.reasonCode}`;
  return `授权服务暂不可用：${error.reasonCode}`;
}

export function EmployeeGrantAdministrationPage() {
  const [params, setParams] = useSearchParams();
  const [session, setSession] = useState<WorkbenchSession | null>(null);
  const [requestId, setRequestId] = useState(params.get("request") ?? "");
  const [request, setRequest] = useState<GrantRequestStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const decisionKeys = useRef<Record<string, string>>({});

  useEffect(() => {
    const controller = new AbortController();
    getWorkbenchSession(controller.signal).then(setSession).catch(reason => setError(adminMessage(reason)));
    return () => controller.abort();
  }, []);

  async function inspect() {
    if (!session || !requestId.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const exact = requestId.trim();
      setRequest(await inspectEmployeeGrantRequest(exact, workbenchPrincipalKey(session)));
      setParams({ request: exact });
    } catch (reason) {
      setRequest(null);
      setError(adminMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  async function decide(decision: "APPROVE" | "REJECT") {
    if (!session || !request || request.state !== "PENDING" || busy) return;
    const fingerprint = `${request.requestId}\u0000${request.aggregateVersion}\u0000${decision}`;
    const idempotencyKey = decisionKeys.current[fingerprint] ?? `employee-grant-decision:${crypto.randomUUID()}`;
    decisionKeys.current[fingerprint] = idempotencyKey;
    setBusy(true);
    setError(null);
    try {
      await decideEmployeeGrantRequest(
        request.requestId,
        {
          expectedVersion: request.aggregateVersion,
          decision,
          reasonCategory: decision === "APPROVE" ? "ASSIGNED_BUSINESS_DUTY" : "REQUEST_NOT_JUSTIFIED",
          basisType: "TICKET",
          basisReference: `S5-V023-IMPL-310:${request.requestId}`,
          ...(decision === "APPROVE" ? { expiresAt: new Date(Date.now() + 60 * 60 * 1000).toISOString() } : {}),
        },
        idempotencyKey,
        workbenchPrincipalKey(session),
      );
      delete decisionKeys.current[fingerprint];
      setRequest(await inspectEmployeeGrantRequest(request.requestId, workbenchPrincipalKey(session)));
    } catch (reason) {
      setError(adminMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return <main className="px-page employee-grant-admin">
    <header className="px-page-title"><div><p>授权管理 <small>Exact Grant Administration</small></p><h1>数字员工权限决定</h1><span>只处理申请人提供的精确申请编号；不提供跨主体列表、搜索或计数。</span></div><a href="/digital-employees">返回数字员工</a></header>
    {!session && <section className="employee-command-state failed"><strong>管理员需独立登录</strong><span>{error ?? "正在读取管理员会话……"}</span><a className="px-primary-button" href="/api/workbench/v1/login">登录授权管理工作台</a></section>}
    {session && <><section className="employee-authorization-request"><h2>检查精确申请</h2><label>申请编号<input value={requestId} disabled={busy} onChange={event => setRequestId(event.target.value)} /></label><p>未知、不可见、自我决定或缺少 DECIDE 权限的申请不会被进一步区分。</p><button className="px-primary-button" disabled={busy || !requestId.trim()} onClick={() => void inspect()}>{busy ? "正在检查……" : "检查授权申请"}</button></section>
    {error && <p role="alert" className="employee-inline-error">{error}</p>}
    {request && <section className="employee-authorization-request" aria-label="授权申请决定"><span className={`employee-capability-state ${request.state === "APPROVED" ? "available" : request.state === "REJECTED" ? "missing" : "warning"}`}><i />{request.state === "PENDING" ? "等待决定" : request.state === "APPROVED" ? "已批准" : "已拒绝"}</span><h2>核对并处理授权申请</h2><dl><dt>申请编号</dt><dd><code>{request.requestId}</code></dd><dt>状态版本</dt><dd>{request.aggregateVersion}</dd><dt>申请用途</dt><dd>{request.purpose}</dd><dt>请求操作</dt><dd>{request.requestedActions.join("、")}</dd></dl>{request.state === "PENDING" ? <div className="employee-form-actions"><button disabled={busy} onClick={() => void decide("REJECT")}>拒绝申请</button><button className="px-primary-button" disabled={busy} onClick={() => void decide("APPROVE")}>批准精确权限</button></div> : <p>这是不可覆盖的终态；申请人可返回原页面刷新并恢复冻结命令。</p>}</section>}</>}
  </main>;
}
