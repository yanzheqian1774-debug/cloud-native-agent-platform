import {preparationNotice} from './preparationNotice';
import {modelResult,type ModelProgress} from '../api/modelStream';
import {readWorkbenchSession} from "../api/businessWorkspace";
import type {Proposal} from "./api";
import type {PlanningPolicy} from "./api";
export type PlanningInput = {target: Record<string, unknown>; title: string; description: string;resourceAutomation?:{enabled:boolean;readonlyContinuationEnabled?:boolean}};
export type PlanningBody={target:Record<string,unknown>;policy:PlanningPolicy;output_language:string;answers:string[];idempotency_key:string;source_proposal?:{resource_id:string;revision_id:string;digest:string};predecessor_invocation_id?:string};
export type ActivityInput={state:string;originalQuestion?:string;question?:string;choices?:{label:string;contextToken:string}[];planningRequest:PlanningBody|null};
export type Invocation = {admission?: {context_id:string;ready:boolean;reasonCode?:string;maximum_new_calls:number;cumulative_call_cap:number;total_cost_cap_microusd?:number};adaptive?: {stop_reason: string; limits: {maximum_attempts: number; total_seconds:number}; attempts: {invocation_id:string;kind:string|null}[]};invocation: {provider_configuration?:{protocol?:string};bounded_new_calls?:number;target: {invocation_id: string;suggestion_context_id?:string;request_revision?:number; problem?: {problem?: {resource_id?: string}}}; request?: {answers: string[];source_proposal?:unknown;idempotency_key?:string}; submitted_at?: string}; result: {validation_diagnostic?:{locations?:{path:(string|number)[];rule?:string;contractFacts?:{subcondition?:string}}[]};technical_status: string; reason?: string; kind: string | null; questions?: string[]; proposal?: Proposal | null;proposal_digest?:string|null; generated_at?: string}; facts_status: string};
export async function planningRequest<T>(path: string, body?: object,extraHeaders:Record<string,string>={},expected?:{principal:string;isCurrent:()=>boolean},progress?:(p:ModelProgress)=>void): Promise<T> {
  const session = await readWorkbenchSession();
  if(expected&&(!expected.isCurrent()||JSON.stringify(session.principal)!==expected.principal))throw new Error("登录身份或当前页面已变化，未派发本次请求。");
  const response = await fetch(`/api/workbench/v1/${path}`, {method: body ? "POST" : "GET", credentials: "same-origin", headers: {"Content-Type": "application/json", "X-CSRF-Token": session.csrfToken,...(progress?{Accept:"text/event-stream"}:{}),...extraHeaders}, ...(body ? {body: JSON.stringify(body)} : {})});
  if(progress)return modelResult<T>(response,progress,(status,reason)=>new Error(status===401?"会话已失效，请重新登录后读回原请求":status===422?"显式规划策略存在冲突或输入超出范围":status===409?"目标或请求状态已变化，请先读回原记录":`规划服务未能完成此操作，请核对权限与配置（${reason??status}）`));
  const value = await response.json();
  if (!response.ok && path === 'question-activity-input' && preparationNotice(value.reasonCode)) throw new Error(preparationNotice(value.reasonCode)+'（'+value.reasonCode+'）');
  if (!response.ok) throw new Error(response.status === 401 ? "会话已失效，请重新登录后读回原请求" : response.status === 422 ? "显式规划策略存在冲突或输入超出范围" : response.status === 409 ? "目标或请求状态已变化，请先读回原记录" : `规划服务未能完成此操作，请核对权限与配置（${value.reasonCode ?? response.status}）`);
  return value.result as T;
}
