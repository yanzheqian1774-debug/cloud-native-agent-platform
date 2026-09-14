import { useEffect, useRef, useState } from "react";
import {
  DigitalEmployeeRequestError,
  employeeControlledState,
  getEmployeePlacement,
  type EmployeeAssignment,
  type EmployeeDefinition,
  type EmployeeInstance,
  type EmployeePlacement,
  type EmployeePlacementReadContext,
} from "../api/digitalEmployees";

type ExactPlacementCoordinates = Omit<EmployeePlacementReadContext, "instanceId" | "assignmentId">;

const emptyCoordinates: ExactPlacementCoordinates = { placementId: "", attemptId: "", agentInstanceId: "" };

function Fact({ label, value, state }: { label: string; value: string; state: "known" | "unknown" }) {
  return <article className={`employee-work-stage ${state}`}><span>{label}</span><strong>{value}</strong></article>;
}

function placementDecisionLabel(value: string) {
  if (value === "PLACED") return "已放置（不代表执行成功）";
  return `未知状态（${value}）`;
}

function verifyPlacementBinding(
  value: EmployeePlacement,
  instance: EmployeeInstance,
  assignment: EmployeeAssignment,
  coordinates: ExactPlacementCoordinates,
) {
  const expected = {
    instanceId: instance.instanceId,
    assignmentId: assignment.assignmentId,
    attemptId: coordinates.attemptId,
    agentInstanceId: coordinates.agentInstanceId,
  };
  if (value.placementId !== coordinates.placementId
    || Object.entries(expected).some(([key, expectedValue]) => value.binding[key as keyof typeof expected] !== expectedValue)) {
    throw new DigitalEmployeeRequestError("PLACEMENT_BINDING_IDENTITY_MISMATCH", 409);
  }
  return value;
}

export function EmployeeWorkParticipation({
  definition,
  instance,
  assignment,
  initialCoordinates,
  onCoordinates,
}: {
  definition: EmployeeDefinition | null;
  instance: EmployeeInstance | null;
  assignment: EmployeeAssignment | null;
  initialCoordinates?: Partial<ExactPlacementCoordinates>;
  onCoordinates: (coordinates: ExactPlacementCoordinates) => void;
}) {
  const [coordinates, setCoordinates] = useState<ExactPlacementCoordinates>({ ...emptyCoordinates, ...initialCoordinates });
  const [placement, setPlacement] = useState<EmployeePlacement | null>(null);
  const [state, setState] = useState<"READY" | "LOADING">("READY");
  const [error, setError] = useState<{ kind: string; code: string } | null>(null);
  const generation = useRef(0);
  const activeRead = useRef<AbortController | null>(null);
  const restored = useRef(false);
  const runtimeProfile = definition?.members.find(member => member.kind === "RUNTIME_PROFILE") ?? null;

  useEffect(() => () => {
    generation.current += 1;
    activeRead.current?.abort();
  }, []);

  useEffect(() => {
    if (!restored.current && instance && assignment && coordinates.placementId && coordinates.attemptId && coordinates.agentInstanceId) {
      restored.current = true;
      void readPlacement();
    }
    // Restored URL coordinates are consumed only after authoritative parents are read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instance?.instanceId, assignment?.assignmentId]);

  async function readPlacement() {
    if (!instance || !assignment || !coordinates.placementId || !coordinates.attemptId || !coordinates.agentInstanceId) return;
    const turn = ++generation.current;
    activeRead.current?.abort();
    const controller = new AbortController();
    activeRead.current = controller;
    setState("LOADING");
    try {
      const value = verifyPlacementBinding(
        await getEmployeePlacement({
          instanceId: instance.instanceId,
          assignmentId: assignment.assignmentId,
          ...coordinates,
        }, controller.signal),
        instance,
        assignment,
        coordinates,
      );
      if (turn !== generation.current) return;
      setPlacement(value);
      setError(null);
      setState("READY");
      onCoordinates(coordinates);
    } catch (reason) {
      if (turn !== generation.current || (reason instanceof DOMException && reason.name === "AbortError")) return;
      const value = reason instanceof DigitalEmployeeRequestError
        ? reason
        : new DigitalEmployeeRequestError("WORKBENCH_READ_UNAVAILABLE", 503);
      setPlacement(null);
      setError({ kind: employeeControlledState(value), code: value.reasonCode });
      setState("READY");
    }
  }

  function changeCoordinate(key: keyof ExactPlacementCoordinates, value: string) {
    generation.current += 1;
    activeRead.current?.abort();
    setCoordinates(current => ({ ...current, [key]: value }));
    setPlacement(null);
    setError(null);
    setState("READY");
  }

  const hiddenError = error?.kind === "denied" || error?.kind === "not found";
  return <section className="employee-work-participation" aria-labelledby="employee-work-title">
    <header><div><p className="eyebrow">可信只读关联 · 不推导完整流程</p><h3 id="employee-work-title">当前工作关联</h3></div><span className="binding-status unbound">不推导在线状态</span></header>
    <p>以下对象是分别读取并核实的事实，不表示配置、放置、执行和结果已形成完整成功流程。</p>

    <section className="employee-work-group employee-runtime-binding" aria-labelledby="employee-work-runtime-title"><h4 id="employee-work-runtime-title">Runtime Profile 配置引用</h4><p>{runtimeProfile ? <><strong>{runtimeProfile.resourceId}</strong> · {runtimeProfile.revisionId}</> : "当前 Employee 修订未提供 Runtime Profile 成员绑定。"}</p><small>来源：当前 Employee 修订的成员绑定。Runtime Profile exact 详情未接通，未核实其配置内容。</small></section>

    <section className="employee-work-group" aria-labelledby="employee-work-facts-title"><h4 id="employee-work-facts-title">已核实的工作事实</h4><div className="employee-work-stages" aria-label="分别核实的工作对象">
      <Fact label="Instance" value={instance?.instanceId ?? "尚未读取"} state={instance ? "known" : "unknown"} />
      <Fact label="Assignment" value={assignment?.assignmentId ?? "尚未读取"} state={assignment ? "known" : "unknown"} />
      <Fact label="Placement" value={placement ? `${placementDecisionLabel(placement.decision)} · ${placement.placementId}` : "尚未读取"} state={placement ? "known" : "unknown"} />
    </div></section>

    <section className="employee-unavailable-summary" aria-labelledby="employee-work-unavailable-title"><span className="employee-capability-state partial"><i />部分实现</span><div><h4 id="employee-work-unavailable-title">执行、证据与结果尚未接通</h4><p>Execution、Evidence 与 Outcome 没有本页可用的正式读取端口；当前已核实的 Assignment 或 Placement 不代表已经执行或已有业务结果。</p></div></section>

    {error && <div role="alert" className="qto-alert"><strong>{error.kind}</strong><span>{error.kind === "authentication required" ? "需要可信 Workbench session。" : hiddenError ? "资源不可用或当前访问未获授权。" : error.code}</span></div>}

    {placement && <section className="employee-placement-detail" aria-label="Placement 权威详情">
      <header><div><p className="eyebrow">正式 Placement exact READ</p><h4>相关放置记录</h4></div><span className="binding-status verified">父链已核实</span></header>
      <dl className="employee-profile-grid">
        <div><dt>放置标识</dt><dd><code>{placement.placementId}</code></dd></div>
        <div><dt>放置状态</dt><dd>{placementDecisionLabel(placement.decision)}</dd></div>
        <div><dt>Runtime Instance</dt><dd><code>{placement.runtimeInstanceId}</code></dd></div>
        <div><dt>请求标识</dt><dd><code>{placement.requestId}</code></dd></div>
        <div><dt>观测新鲜度</dt><dd>尚未接通</dd></div>
        <div><dt>策略版本</dt><dd><code>{placement.policyVersion}</code></dd></div>
        <div className="wide"><dt>兼容事实</dt><dd>{placement.compatibilityFacts.length ? placement.compatibilityFacts.join("；") : "未提供"}</dd></div>
        <div className="wide"><dt>限制</dt><dd>{placement.limitationCodes.length ? placement.limitationCodes.join("；") : "未记录限制"}</dd></div>
      </dl>
      <details className="employee-technical-details"><summary>Placement 父链与原始状态</summary><dl><dt>Instance ID</dt><dd>{placement.binding.instanceId}</dd><dt>Assignment ID</dt><dd>{placement.binding.assignmentId}</dd><dt>Attempt ID</dt><dd>{placement.binding.attemptId}</dd><dt>Agent Instance ID</dt><dd>{placement.binding.agentInstanceId}</dd><dt>决策原值</dt><dd>{placement.decision}</dd><dt>Digest</dt><dd>{placement.digest}</dd></dl></details>
      <p className="employee-disclosure">精确身份仅供父链核对，不构成相关对象的读取权限；PLACED 不等于执行成功，执行成功也不等于 Business Outcome 完成。</p>
    </section>}

    <details className="employee-technical-details employee-placement-operation"><summary>{placement ? "查询其他 Placement" : "技术操作：按精确坐标读取 Placement"}</summary><p>读取需要 Placement、Attempt 与 Agent Instance 坐标，并继续核对当前 Instance 与 Assignment 父链。</p><fieldset disabled={!instance || !assignment || state === "LOADING"}><legend>Placement 精确查询坐标</legend><div className="employee-work-fields"><label>Placement ID<input value={coordinates.placementId} onChange={event => changeCoordinate("placementId", event.target.value)} /></label><label>Attempt ID<input value={coordinates.attemptId} onChange={event => changeCoordinate("attemptId", event.target.value)} /></label><label>Agent Instance ID<input value={coordinates.agentInstanceId} onChange={event => changeCoordinate("agentInstanceId", event.target.value)} /></label></div><button type="button" onClick={() => void readPlacement()} disabled={!instance || !assignment || !coordinates.placementId || !coordinates.attemptId || !coordinates.agentInstanceId || state === "LOADING"}>{state === "LOADING" ? "正在通过可信 session 读取……" : "读取精确工作关联"}</button></fieldset></details>
    {!instance && <p role="status">请先在“实例”标签页按精确 ID 读取 Instance。</p>}
    {instance && !assignment && <p role="status">请在当前标签页按精确 ID 读取 Assignment。</p>}
  </section>;
}
