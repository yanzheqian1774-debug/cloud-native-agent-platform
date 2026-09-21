import {readWorkbenchSession} from "../api/businessWorkspace";
import type {Proposal} from "./api";
export type PlanningInput = {target: Record<string, unknown>; title: string; description: string};
export type Invocation = {adaptive?: {stop_reason: string; limits: {maximum_attempts: number; total_seconds:number}; attempts: {invocation_id:string;kind:string|null}[]};invocation: {target: {invocation_id: string}; request?: {answers: string[]}; submitted_at?: string}; result: {technical_status: string; reason?: string; kind: string | null; questions?: string[]; proposal?: Proposal | null; generated_at?: string}; facts_status: string};
export async function planningRequest<T>(path: string, body?: object): Promise<T> {
  const session = await readWorkbenchSession();
  const response = await fetch(`/api/workbench/v1/${path}`, {method: body ? "POST" : "GET", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": session.csrfToken}, ...(body ? {body: JSON.stringify(body)} : {})});
  const value = await response.json();
  if (!response.ok) throw new Error(response.status === 401 ? "会话已失效，请重新登录后读回原请求" : response.status === 422 ? "显式规划策略存在冲突或输入超出范围" : response.status === 409 ? "目标或请求状态已变化，请先读回原记录" : `规划服务未能完成此操作，请核对权限与配置（${value.reasonCode ?? response.status}）`);
  return value.result as T;
}
