import {useEffect,useRef,useState} from "react";
import {readBusinessProblem,readCriteriaSets,readProblemCriteria,transitionBusinessProblem,WorkbenchRequestError,newIdempotencyKey,type BusinessProblemDetail,type CriteriaSetRevision,type CriterionRevision} from "../api/businessWorkspace";
import {WorkbenchErrorNotice} from "./WorkbenchErrorNotice";

type Snapshot={detail:BusinessProblemDetail;sets:CriteriaSetRevision[];criteria:CriterionRevision[];criteriaReadable:boolean};
function target(value:Snapshot){
  const problem=value.detail.problem,revision=value.detail.revisions.find(item=>item.revision_id===problem.current_revision_id);
  const set=[...value.sets].sort((a,b)=>b.revision-a.revision)[0];
  if(!value.criteriaReadable||!revision||!set||set.problem_revision_id!==revision.revision_id||!set.ordered_criterion_revision_ids.length)return null;
  const members=set.ordered_criterion_revision_ids.map(id=>value.criteria.find(item=>item.revision_id===id));
  if(members.some(item=>!item))return null;
  return JSON.stringify([revision.revision_id,revision.digest,set.set_revision_id,set.digest,members.map(item=>[item!.revision_id,item!.digest])]);
}

// The owner CAS covers both Problem revisions and CriteriaSet writes. These are
// separate transactions: never infer activation from successful criteria saving.
export function ProblemPlanningGate({snapshot,csrfToken,contextKey,blocked,editingKey,onRefresh,onBusy}:{snapshot:Snapshot;csrfToken:string;contextKey:string;blocked:boolean;editingKey:string;onRefresh:()=>Promise<void>;onBusy:(value:boolean)=>void}){
  const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[notice,setNotice]=useState("");
  const flight=useRef(false),mounted=useRef(true);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false}},[]);
  const problem=snapshot.detail.problem,visibleTarget=target(snapshot);
  const currentEditing=useRef(editingKey);
  useEffect(()=>{currentEditing.current=editingKey},[editingKey]);
  const storage=`323.problem-confirm.${contextKey}.${problem.business_problem_id}`;
  async function confirm(){
    if(flight.current||blocked||!visibleTarget)return;
    flight.current=true;setBusy(true);onBusy(true);setError(null);setNotice("");
    try{
      const detail=await readBusinessProblem(problem.business_problem_id);
      const [sets,criteria]=await Promise.all([readCriteriaSets(problem.business_problem_id),readProblemCriteria(problem.business_problem_id)]);
      if(!mounted.current)return;
      if(currentEditing.current!==editingKey)throw new WorkbenchRequestError("PROBLEM_CONFIRMATION_INPUT_CHANGED",409);
      const freshTarget=target({detail,sets:sets.revisions,criteria:criteria.revisions,criteriaReadable:true});
      if(freshTarget!==visibleTarget||detail.problem.aggregate_version!==problem.aggregate_version){
        await onRefresh();throw new WorkbenchRequestError("PROBLEM_CRITERIA_CONFIRMATION_STALE",409);
      }
      if(detail.problem.current_state!=="DRAFT")throw new WorkbenchRequestError("BUSINESS_PROBLEM_TRANSITION_INVALID",409);
      const fingerprint=JSON.stringify([freshTarget,detail.problem.aggregate_version]);
      const saved=JSON.parse(sessionStorage.getItem(storage)??"null") as {fingerprint:string;key:string}|null;
      const key=saved?.fingerprint===fingerprint?saved.key:newIdempotencyKey("confirm-problem");
      sessionStorage.setItem(storage,JSON.stringify({fingerprint,key}));
      await transitionBusinessProblem(csrfToken,problem.business_problem_id,{toState:"ACTIVE",expectedVersion:detail.problem.aggregate_version,idempotencyKey:key});
      if(!mounted.current)return;
      await onRefresh();sessionStorage.removeItem(storage);
      setNotice("确认已保存。进入规划，不启动执行。");
    }catch(cause){setError(cause);setNotice("已保存的完成标准保留；问题确认尚未核实完成。请先刷新读取实际状态，再决定是否继续。");}
    finally{flight.current=false;setBusy(false);onBusy(false)}
  }
  async function refresh(){if(flight.current)return;flight.current=true;setBusy(true);onBusy(true);try{await onRefresh();setError(null);setNotice("已重新读取实际状态；未自动提交确认。")}catch(cause){setError(cause)}finally{flight.current=false;setBusy(false);onBusy(false)}}
  return <section className="px-inline-card px-boundary-card" aria-label="问题与完成标准确认">
    <span className="px-eyebrow">规划前确认</span><h2>{problem.current_state==="ACTIVE"&&visibleTarget?"问题与完成标准已保存，可进入规划":"确认问题与完成标准"}</h2>
    <p>进入规划，不启动执行。完成标准保存与问题确认是独立步骤。</p>
    {!visibleTarget&&<p role="status">请先保存关联当前问题修订的完成标准，并取得读取权限。</p>}
    {blocked&&<p>仍有未保存或未采用的内容，请先完成或清除后再确认。</p>}
    {problem.current_state==="DRAFT"&&<button type="button" className="px-primary-button" disabled={busy||blocked||!visibleTarget} onClick={()=>void confirm()}>确认问题与完成标准</button>}
    {problem.current_state==="ACTIVE"&&visibleTarget&&!blocked&&<a className="px-primary-button" href={`/work/plan?problem=${encodeURIComponent(problem.business_problem_id)}`}>制定建议计划</a>}
    <button type="button" disabled={busy||blocked} onClick={()=>void refresh()}>刷新确认状态</button>
    {notice&&<p role="status">{notice}</p>}
    {Boolean(error)&&<WorkbenchErrorNotice error={error} operation="确认问题与完成标准"/>}
  </section>;
}
