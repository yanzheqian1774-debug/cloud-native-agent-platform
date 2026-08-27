import { defaultSelectedExecutionContext } from "./executionSnapshotFixture.ts";
import type { SelectedExecutionContextValue, SharedExecutionSnapshot } from "./executionSnapshotTypes.ts";

const KEYS: (keyof SelectedExecutionContextValue)[] = ["employeeId", "revisionId", "workId", "workflowId", "taskId", "executionId", "graphSnapshotId"];

export function serializeSelectedContext(value: SelectedExecutionContextValue): string {
  const params = new URLSearchParams();
  KEYS.forEach((key) => params.set(key, value[key]));
  return params.toString();
}

export function parseSelectedContext(search: string, snapshot: SharedExecutionSnapshot): SelectedExecutionContextValue {
  const params = new URLSearchParams(search);
  const suppliedKeys = [...params.keys()];
  if (suppliedKeys.length === 0) return { ...defaultSelectedExecutionContext };
  if (
    suppliedKeys.length !== KEYS.length
    || !suppliedKeys.every((key) => KEYS.includes(key as keyof SelectedExecutionContextValue))
    || KEYS.some((key) => params.getAll(key).length !== 1)
  ) return { ...defaultSelectedExecutionContext };
  const candidate = Object.fromEntries(KEYS.map((key) => [key, params.get(key)])) as unknown as SelectedExecutionContextValue;
  const validEmployee = snapshot.employees.some((employee) => employee.id === candidate.employeeId);
  const stableKeys = KEYS.filter((key) => key !== "employeeId");
  if (!validEmployee || stableKeys.some((key) => candidate[key] !== snapshot.selectedContext[key])) return { ...defaultSelectedExecutionContext };
  return candidate;
}
