import { useEffect, useRef, useState } from "react";
import {
  DigitalEmployeeRequestError,
  inspectEmployeeGrantRequest,
  submitEmployeeGrantRequest,
  type ExactGrantRequest,
  type GrantRequestStatus,
} from "../api/digitalEmployees";

function authorizationMessage(error: DigitalEmployeeRequestError) {
  if (error.reasonCode === "WORKBENCH_SESSION_CONTEXT_CHANGED") return "可信会话已切换；原权限申请未继续。";
  if (error.status === 401) return "可信会话已失效，请重新登录。";
  if (error.status === 404) return "申请或目标在当前授权范围内不可见。";
  if (error.status === 409) return `权限申请状态冲突：${error.reasonCode}`;
  if (error.status === 422) return `精确权限申请不符合正式契约：${error.reasonCode}`;
  return `权限服务暂不可用：${error.reasonCode}`;
}

export function EmployeeAuthorizationRequest({
  title,
  grants,
  principalKey,
  onApproved,
}: {
  title: string;
  grants: ExactGrantRequest[];
  principalKey: string;
  onApproved: () => Promise<void>;
}) {
  const [request, setRequest] = useState<GrantRequestStatus | null>(null);
  const [requestKey, setRequestKey] = useState(() => `employee-grant-request:${crypto.randomUUID()}`);
  const [busy, setBusy] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => {
    generation.current += 1;
    activeRequest.current?.abort();
  }, []);

  async function submit() {
    if (busy) return;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setError(null);
    try {
      const value = await submitEmployeeGrantRequest(grants, requestKey, principalKey, controller.signal);
      if (turn !== generation.current) return;
      setRequest(value);
      setUnknown(false);
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError
        ? reason
        : new DigitalEmployeeRequestError("AUTHORIZATION_RESULT_UNKNOWN", 503, true);
      setUnknown(value.unknownResult);
      setError(value.unknownResult
        ? "申请结果未知；已保留原幂等键与精确权限集合，只能重放原申请。"
        : authorizationMessage(value));
    } finally {
      if (turn === generation.current) setBusy(false);
    }
  }

  async function refresh() {
    if (!request || busy) return;
    const turn = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true);
    setError(null);
    try {
      const value = await inspectEmployeeGrantRequest(request.requestId, principalKey, controller.signal);
      if (turn !== generation.current) return;
      setRequest(value);
      if (value.state === "APPROVED") await onApproved();
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError
        ? reason
        : new DigitalEmployeeRequestError("AUTHORIZATION_REQUEST_UNAVAILABLE", 503);
      setError(authorizationMessage(value));
    } finally {
      if (turn === generation.current) setBusy(false);
    }
  }

  function startNewRequest() {
    setRequest(null);
    setRequestKey(`employee-grant-request:${crypto.randomUUID()}`);
    setUnknown(false);
    setError(null);
  }

  return <section className="employee-authorization-request" aria-label="数字员工权限申请">
    <span className="employee-confirmation-state">正式精确权限</span>
    <h4>{title}</h4>
    {!request && <p>申请不会直接授权；另一位具备精确决定权限的管理员必须独立批准。</p>}
    {request && <><span className={`employee-capability-state ${request.state === "APPROVED" ? "available" : request.state === "REJECTED" ? "missing" : "warning"}`}><i />{request.state === "PENDING" ? "等待独立管理员决定" : request.state === "APPROVED" ? "权限已批准" : "申请已拒绝"}</span><dl><dt>申请编号</dt><dd><code>{request.requestId}</code></dd><dt>状态版本</dt><dd>{request.aggregateVersion}</dd><dt>申请操作</dt><dd>{request.requestedActions.join("、")}</dd></dl></>}
    <details><summary>查看申请的精确权限</summary><ul>{grants.map(item => <li key={`${item.owner}:${item.action}:${item.resource}`}><code>{item.owner} {item.action} {item.resource}</code></li>)}</ul></details>
    {error && <p role="alert" className="employee-inline-error">{error}</p>}
    <div className="employee-form-actions">
      {request?.state === "PENDING" && <a className="employee-secondary-button" href={`/authorization-admin?request=${encodeURIComponent(request.requestId)}`} target="_blank" rel="noreferrer">在独立管理员窗口打开</a>}
      {request?.state === "REJECTED" && <button type="button" className="employee-secondary-button" onClick={startNewRequest}>准备新申请</button>}
      {!request && <button type="button" className="px-primary-button" disabled={busy} onClick={() => void submit()}>{busy ? "正在提交……" : unknown ? "重放原申请" : "提交正式权限申请"}</button>}
      {request && request.state !== "REJECTED" && <button type="button" className="px-primary-button" disabled={busy} onClick={() => void refresh()}>{busy ? "正在检查……" : "刷新权限状态并继续"}</button>}
    </div>
  </section>;
}
