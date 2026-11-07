import {WorkbenchRequestError,readWorkbenchSession} from '../api/businessWorkspace';
import type {ExecutionView} from '../api/preparedExecution';
import {artifactMatchesSource} from '../problems/artifactProvenance';
import * as api from './api';

export type SupplementTarget=api.Semantics['target']&{criterion_revision_ids:string[];expected_problem_version:number};
export type SupplementSpec={plan_version:number;plan_digest:string;expected_proposal_revision:number;source_snapshot:api.ExactRef;new_target:SupplementTarget;employee:api.ExactRef;skill:api.ExactRef;reason:string;idempotency_key:string};
export type SupplementReceipt={schemaVersion:'planning-sales-supplement-receipt.v1';proposal:api.Proposal;digest:string;request:SupplementSpec;requestKey:string;confirmation_required:true;executionStarted:false;modelCalls:0};
export type SupplementPreparation={state:'READY';spec:Omit<SupplementSpec,'idempotency_key'>}|{state:'BLOCKED';gaps:string[]}|{state:'SAVED';revision:number};
const checks=['source','exceptions','totals','reconciliations','gross_profit_dimensions','row_contributions','claim_boundary'];
const equal=(a:api.ExactRef|undefined,b:api.ExactRef)=>Boolean(a)&&(['resource_id','revision_id','digest'] as const).every(k=>a![k]===b[k]);
export const supplementPrincipal=(session:Awaited<ReturnType<typeof readWorkbenchSession>>)=>JSON.stringify(session.principal);

export function isSavedSales(view:ExecutionView){
 return view.executionStarted&&view.progress?.state==='SUCCEEDED'&&view.artifacts.some(a=>{
  if(a.contentAccess!=='AUTHORIZED'||!a.content||!artifactMatchesSource(a.content,view.preparation.source_snapshot))return false;
  try{const v=JSON.parse(a.content);return v.schemaVersion==='sales-diagnostic-output.v1'&&v.operation==='RENDER_REPORT'}catch{return false}
 });
}

async function request<T>(path:string,body?:SupplementSpec,csrf?:string):Promise<T>{
 const response=await fetch('/api/workbench/v1/'+path,{method:body?'POST':'GET',credentials:'same-origin',signal:AbortSignal.timeout(15000),headers:{Accept:'application/json',...(body?{'Content-Type':'application/json','X-CSRF-Token':csrf??''}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const value=await response.json().catch(()=>null);
 if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(value?.reasonCode??'SALES_SUPPLEMENT_UNAVAILABLE',response.status);
 return value.result as T;
}
export const readSupplement=(id:string,key:string)=>request<SupplementReceipt>(`planning-v2/${encodeURIComponent(id)}/sales-supplements/by-key/${encodeURIComponent(key)}`);
export const submitSupplement=(id:string,spec:SupplementSpec,csrf:string)=>request<SupplementReceipt>(`planning-v2/${encodeURIComponent(id)}/sales-supplements`,spec,csrf);

export function verifySupplement(value:SupplementReceipt,id:string,spec:SupplementSpec){
 const r=value.request;
 if(value.schemaVersion!=='planning-sales-supplement-receipt.v1'||value.requestKey!==spec.idempotency_key||value.proposal.proposal_id!==id||value.proposal.revision!==spec.expected_proposal_revision+1||value.proposal.origin?.kind!=='HUMAN_RESOURCE_SUPPLEMENT'||value.proposal.invocation_id!=null||value.executionStarted!==false||value.modelCalls!==0||!r||r.idempotency_key!==spec.idempotency_key||r.plan_version!==spec.plan_version||r.plan_digest!==spec.plan_digest||r.expected_proposal_revision!==spec.expected_proposal_revision||r.reason!==spec.reason||!equal(r.source_snapshot,spec.source_snapshot)||!equal(r.skill,spec.skill)||!equal(r.employee,spec.employee)||!equal(r.new_target.problem,spec.new_target.problem)||!equal(r.new_target.criteria,spec.new_target.criteria)||r.new_target.expected_problem_version!==spec.new_target.expected_problem_version||JSON.stringify(r.new_target.criterion_revision_ids)!==JSON.stringify(spec.new_target.criterion_revision_ids))throw Error('补交回执与原请求不一致，请保留原记录核查。');
}

/** Read existing canonical owners only; the supplement owner decides admission. */
export async function inspectSupplement(view:ExecutionView):Promise<SupplementPreparation>{
 const p=view.preparation,h=await api.history(p.plan_id);
 const old=h.plans.find(v=>v.plan.version===p.plan_version&&v.digest===p.plan_digest);
 if(!old||old.plan.semantics.target.problem.resource_id!==p.semantics.target.problem.resource_id)throw Error('原执行与已确认方案不一致，请重新读取原工作。');
 const successors=h.proposals.filter(v=>v.origin?.kind==='HUMAN_RESOURCE_SUPPLEMENT'&&equal(v.origin.predecessor_plan,{resource_id:p.plan_id,revision_id:String(p.plan_version),digest:p.plan_digest})&&equal(v.semantics.target.problem,old.plan.semantics.target.problem));
 if(successors.length)return {state:'SAVED',revision:Math.max(...successors.map(v=>v.revision))};
 if(Math.max(...h.plans.map(v=>v.plan.version))!==p.plan_version)return {state:'BLOCKED',gaps:['已有后继方案，请先从原方案查看当前办理状态。']};
 const input=await request<{target:SupplementTarget;criteria:{applicability:{check?:string};created_by:string}[]}>(`planning-input/${encodeURIComponent(p.semantics.target.problem.resource_id)}`);
 const gaps:string[]=[];
 if(!equal(input.target.problem,old.plan.semantics.target.problem))gaps.push('业务目标版本已变化，请先确认本次补交是否仍沿用原目标。');
 if(equal(input.target.criteria,old.plan.semantics.target.criteria)||input.criteria.length!==checks.length||new Set(input.criteria.map(c=>c.applicability.check)).size!==checks.length||input.criteria.some(c=>!checks.includes(c.applicability.check??'')||!c.created_by.startsWith('human:')))gaps.push('等待正式完成标准补齐：需要覆盖三维毛利贡献、逐行依据与核对规则。');
 const revision=Math.max(...h.proposals.map(v=>v.revision));
 const groups=await api.candidates(p.plan_id,revision);
 const selected=(kind:string)=>old.plan.semantics.requirements.filter(r=>r.kind===kind&&r.selected).map(r=>r.selected!);
 function successor(kind:string){
  const before=selected(kind);
  if(before.length!==1)return null;
  const found=groups.groups.filter(g=>g.kind===kind).flatMap(g=>g.candidates).filter(c=>c.publication==='PUBLISHED'&&c.permission==='READABLE'&&c.reference.resource_id===before[0].resource_id&&c.reference.revision_id!==before[0].revision_id);
  const unique=[...new Map(found.map(c=>[JSON.stringify(c.reference),c.reference])).values()];
  return unique.length===1?unique[0]:null;
 }
 const skill=successor('SKILL'),employee=successor('EMPLOYEE');
 if(!skill)gaps.push('等待分维度毛利分析能力的已发布、可读取后继版本；候选不唯一时先由维护方核对。');
 if(!employee)gaps.push('等待使用该分析能力的数字员工准备完成并可读取。');
 if(gaps.length||!skill||!employee)return {state:'BLOCKED',gaps};
 return {state:'READY',spec:{plan_version:p.plan_version,plan_digest:p.plan_digest,expected_proposal_revision:revision,source_snapshot:p.source_snapshot,new_target:input.target,skill,employee,reason:'补齐原销售目标：沿用原资料，增加区域、渠道、产品毛利贡献和逐行依据；原方案及结果保留。'}};
}
