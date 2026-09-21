import {readWorkbenchSession} from "../api/businessWorkspace";
import type {Proposal} from "./api";
export type PlanningInput = {target: Record<string, unknown>; title: string; description: string};
export type Invocation = {invocation: {target: {invocation_id: string}; request?: {answers: string[]}; submitted_at?: string}; result: {technical_status: string; reason?: string; kind: string | null; questions?: string[]; proposal?: Proposal | null; generated_at?: string}; facts_status: string};
export async function planningRequest<T>(path: string, body?: object): Promise<T> {
  const session = await readWorkbenchSession();
  const response = await fetch(`/api/workbench/v1/${path}`, {method: body ? "POST" : "GET", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": session.csrfToken}, ...(body ? {body: JSON.stringify(body)} : {})});
  const value = await response.json();
  if (!response.ok) throw new Error(value.reasonCode ?? (response.status === 422 ? "显式规划策略存在冲突或输入超出范围" : "PLANNING_UNAVAILABLE"));
  return value.result as T;
}
