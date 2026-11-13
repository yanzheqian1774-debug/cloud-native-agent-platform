const states = ['QUEUED', 'STARTING', 'READY', 'STOPPING', 'BLOCKED', 'UNKNOWN'];
const reasons = ['WAITING_CAPACITY', 'START_BLOCKED', 'CURRENT_CONDITIONS_BLOCKED', 'OBSERVATION_UNAVAILABLE', null];
export function nativeHostStatus(value: unknown, digest: string, runId: unknown): string | null {
  if (value === undefined) return null;
  const unknown = '执行准备状态暂时无法核实，正在读取原记录；不会重新提交任务。';
  if (!value || typeof value !== 'object') return unknown;
  const v = value as Record<string, unknown>;
  if (v.preparationDigest !== digest || v.runId !== runId || typeof v.runId !== 'string' || !v.runId.trim() || !states.includes(String(v.state)) || !reasons.includes(v.reasonCode as string | null) || !(v.observedAt === null || (typeof v.observedAt === 'string' && Number.isFinite(Date.parse(v.observedAt))))) return unknown;
  return ({
    QUEUED: '当前正在排队等待可用执行资源，进展会在这里继续更新。',
    STARTING: '正在准备执行环境，尚未确认任务开始执行。',
    READY: '执行环境已就绪，任务进展以实际工作步骤为准。',
    STOPPING: '执行环境正在停止，任务结果以已保存的执行记录为准。',
    BLOCKED: '当前执行条件尚未满足，暂时无法继续；原任务和记录已保留。',
    UNKNOWN: unknown,
  } as Record<string, string>)[String(v.state)];
}
