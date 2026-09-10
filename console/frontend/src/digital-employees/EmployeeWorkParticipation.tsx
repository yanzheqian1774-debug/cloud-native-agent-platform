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
    <header><div><p className="eyebrow">可信只读工作关联 · exact read only</p><h2 id="employee-work-title">从配置到实际工作的事实链</h2></div><span className="binding-status">不推导在线状态</span></header>
    <p>当前没有 Instance、Assignment 或 Placement 列表端口。这里只读取输入并由正式 owner 在当前授权事务内核对的精确身份，不声称“全部实例”或“完整历史”。</p>

    <div className="employee-work-stages" aria-label="员工工作参与阶段">
      <Fact label="已配置 configured" value={runtimeProfile ? `Runtime Profile ${runtimeProfile.revisionId}` : "未提供 Runtime Profile"} state={runtimeProfile ? "known" : "unknown"} />
      <Fact label="已绑定 bound" value={instance ? `Instance ${instance.instanceId}` : "尚未读取 Instance"} state={instance ? "known" : "unknown"} />
      <Fact label="已分配 assigned" value={assignment ? `Assignment ${assignment.assignmentId} · ${assignment.lifecycle}` : "尚未读取 Assignment"} state={assignment ? "known" : "unknown"} />
      <Fact label="实际放置 placed" value={placement ? `${placement.decision} · Runtime ${placement.runtimeInstanceId}` : "未知 / 尚未读取"} state={placement ? "known" : "unknown"} />
      <Fact label="实际执行 execution" value="未知 / 正式 Execution READ 尚未接通" state="unknown" />
      <Fact label="实际终态 terminal" value="未知 / Outcome READ 尚未接通" state="unknown" />
    </div>

    <fieldset disabled={!instance || !assignment || state === "LOADING"}>
      <legend>按精确 Placement 身份读取</legend>
      <div className="employee-work-fields">
        <label>Placement ID<input value={coordinates.placementId} onChange={event => changeCoordinate("placementId", event.target.value)} /></label>
        <label>Attempt ID<input value={coordinates.attemptId} onChange={event => changeCoordinate("attemptId", event.target.value)} /></label>
        <label>Agent Instance ID<input value={coordinates.agentInstanceId} onChange={event => changeCoordinate("agentInstanceId", event.target.value)} /></label>
      </div>
      <button type="button" onClick={() => void readPlacement()} disabled={!instance || !assignment || !coordinates.placementId || !coordinates.attemptId || !coordinates.agentInstanceId || state === "LOADING"}>{state === "LOADING" ? "正在通过可信 session 读取……" : "读取精确工作关联"}</button>
    </fieldset>
    {!instance && <p role="status">先在“实例”页按精确 ID 读取 Instance。</p>}
    {instance && !assignment && <p role="status">再在“工作分配”页按精确 ID 读取 Assignment。</p>}
    {error && <div role="alert" className="qto-alert"><strong>{error.kind}</strong><span>{error.kind === "authentication required" ? "需要可信 Workbench session。" : hiddenError ? "资源不可用或当前访问未获授权。" : error.code}</span></div>}

    {placement && <section className="employee-placement-detail" aria-label="Placement 权威详情">
      <dl className="employee-profile-grid">
        <div><dt>Placement / request</dt><dd><code>{placement.placementId}</code><br /><code>{placement.requestId}</code></dd></div>
        <div><dt>Attempt / Agent Instance</dt><dd><code>{placement.binding.attemptId}</code><br /><code>{placement.binding.agentInstanceId}</code></dd></div>
        <div><dt>父链</dt><dd><code>{placement.binding.instanceId}</code><br /><code>{placement.binding.assignmentId}</code></dd></div>
        <div><dt>Runtime Instance</dt><dd><code>{placement.runtimeInstanceId}</code></dd></div>
        <div><dt>观测新鲜度</dt><dd>尚未接通</dd></div>
        <div><dt>Placement 决策</dt><dd>{placement.decision}</dd></div>
        <div><dt>策略版本</dt><dd><code>{placement.policyVersion}</code></dd></div>
        <div className="wide"><dt>兼容事实</dt><dd>{placement.compatibilityFacts.length ? placement.compatibilityFacts.join("；") : "未提供"}</dd></div>
        <div className="wide"><dt>限制</dt><dd>{placement.limitationCodes.length ? placement.limitationCodes.join("；") : "未记录限制"}</dd></div>
      </dl>
      <section className="employee-work-links" aria-label="执行与证据未接通状态">
        <article><strong>执行 / Runtime 详情尚未接通</strong><p><code>{placement.binding.attemptId}</code> · <code>{placement.runtimeInstanceId}</code></p><button type="button" disabled title="正式 Execution 与 Runtime 读取端口尚未接通">详情不可用</button></article>
        <article><strong>Evidence 读取尚未接通</strong><p>当前 Placement 最小投影没有 Evidence reference。</p><button type="button" disabled title="Evidence 内容需要独立读取授权">Evidence 不可用</button></article>
      </section>
      <p className="employee-disclosure">以上精确身份仅供核对，不构成相关对象的读取权限。Evidence reference 即使存在也不等于获准读取内容；执行成功也不等于 Business Outcome 完成。</p>
    </section>}
  </section>;
}
