import {WorkbenchRequestError,readWorkbenchSession} from '../api/businessWorkspace';
import type {ExecutionView} from '../api/preparedExecution';
import {artifactMatchesSource} from '../problems/artifactProvenance';
import * as api from './api';
import type {EmployeeDefinition} from '../api/digitalEmployees';
import {listReadableResources} from '../api/resourceDirectory';

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
 const selected=(kind:string)=>old.plan.semantics.requirements.filter(r=>r.kind===kind&&r.selected).map(r=>r.selected!);
 // The predecessor legitimately targets the prior criteria set. Normal planning
 // candidate discovery requires a current target, so read current resource owners
 // directly here; the supplement owner still performs final exact admission.
 const skills:api.ExactRef[]=[],employees:api.ExactRef[]=[];
 const priorSkill=selected('SKILL'),priorEmployee=selected('EMPLOYEE');
 if(priorSkill.length===1){
  let cursor:string|null=null;const seen=new Set<string>();
  do{
   if(cursor&&seen.has(cursor)||seen.size>=20)throw Error('补交资源目录分页未核实完成。');
   if(cursor)seen.add(cursor);
   const page=await listReadableResources('skill',priorSkill[0].resource_id,'PUBLISHED',cursor);
   for(const item of page.items)if(item.kind==='skill'&&item.identity===priorSkill[0].resource_id&&item.revisionId!==priorSkill[0].revision_id&&item.state==='PUBLISHED'&&item.isCurrentPublished&&item.enabled)skills.push({resource_id:item.identity,revision_id:item.revisionId,digest:item.digest});
   cursor=page.nextCursor;
  }while(cursor);
 }
 if(priorEmployee.length===1){
  const before=await request<EmployeeDefinition>('employees/'+encodeURIComponent(priorEmployee[0].resource_id)+'/revisions/'+encodeURIComponent(priorEmployee[0].revision_id));
  if(before.employeeDefinitionId!==priorEmployee[0].resource_id||before.employeeDefinitionRevisionId!==priorEmployee[0].revision_id||before.employeeDefinitionDigest!==priorEmployee[0].digest)throw Error('原员工准确版本不一致。');
  const key=(m:EmployeeDefinition['members'][number])=>JSON.stringify([m.kind,m.resourceId,m.revisionId,m.digest]);
  const nonSkill=(value:EmployeeDefinition)=>value.members.filter(m=>m.kind!=='SKILL').map(key).sort();
  let cursor:string|null=null;const seen=new Set<string>();
  do{
   if(cursor&&seen.has(cursor)||seen.size>=20)throw Error('补交员工目录分页未核实完成。');
   if(cursor)seen.add(cursor);
   const page:{items:api.EmployeeOption[];nextCursor?:string|null}=await request<{items:api.EmployeeOption[];nextCursor?:string|null}>('employees?'+new URLSearchParams({pageSize:'100',...(cursor?{cursor}:{})}));
   for(const item of page.items){
    if(item.employeeDefinitionId!==priorEmployee[0].resource_id||item.employeeDefinitionRevisionId===priorEmployee[0].revision_id||item.publicationState!=='PUBLISHED')continue;
    // LIST is discovery only; the exact owner READ proves current access.
    try{
     const exact=await request<EmployeeDefinition>('employees/'+encodeURIComponent(item.employeeDefinitionId)+'/revisions/'+encodeURIComponent(item.employeeDefinitionRevisionId));
     if(exact.employeeDefinitionId!==item.employeeDefinitionId||exact.employeeDefinitionRevisionId!==item.employeeDefinitionRevisionId||exact.employeeDefinitionDigest!==item.employeeDefinitionDigest)throw Error('补交员工准确版本不一致。');
     const skillMembers=exact.members.filter(m=>m.kind==='SKILL');
     const compatible=before.role===exact.role&&JSON.stringify(before.responsibilities)===JSON.stringify(exact.responsibilities)&&JSON.stringify(nonSkill(before))===JSON.stringify(nonSkill(exact))&&skillMembers.length===1&&skills.some(r=>key(skillMembers[0])===JSON.stringify(['SKILL',r.resource_id,r.revision_id,r.digest]));
     if(exact.publicationState==='PUBLISHED'&&compatible)employees.push({resource_id:exact.employeeDefinitionId,revision_id:exact.employeeDefinitionRevisionId,digest:exact.employeeDefinitionDigest});
    }catch(e){if(!(e instanceof WorkbenchRequestError&&[403,404].includes(e.status)))throw e;}
   }
   cursor=page.nextCursor??null;
  }while(cursor);
 }
 function unique(refs:api.ExactRef[]){const values=[...new Map(refs.map(r=>[JSON.stringify(r),r])).values()];return values.length===1?values[0]:null}
 const skill=unique(skills),employee=unique(employees);
 if(!skill)gaps.push('等待分维度毛利分析能力的已发布、可读取后继版本；候选不唯一时先由维护方核对。');
 if(!employee)gaps.push('等待使用该分析能力的数字员工准备完成并可读取。');
 if(gaps.length||!skill||!employee)return {state:'BLOCKED',gaps};
 return {state:'READY',spec:{plan_version:p.plan_version,plan_digest:p.plan_digest,expected_proposal_revision:revision,source_snapshot:p.source_snapshot,new_target:input.target,skill,employee,reason:'补齐原销售目标：沿用原资料，增加区域、渠道、产品毛利贡献和逐行依据；原方案及结果保留。'}};
}
