import {readBusinessProblem,readCriteriaSets,readProblemCriteria,transitionBusinessProblem,WorkbenchRequestError,type CriteriaSetRevision} from "../api/businessWorkspace";

// Composition over existing owners. No invocation, plan confirmation or execution.
export async function enterSavedPlanningTarget({problemId,problemRevisionId,savedSet,csrfToken,idempotencyKey,isCurrent}:{problemId:string;problemRevisionId:string;savedSet:CriteriaSetRevision;csrfToken:string;idempotencyKey:string;isCurrent:()=>boolean}){
 const current=()=>{if(!isCurrent())throw new WorkbenchRequestError("PROBLEM_CONFIRMATION_INPUT_CHANGED",409)};
 async function readExact(){
  const [detail,sets,criteria]=await Promise.all([readBusinessProblem(problemId),readCriteriaSets(problemId),readProblemCriteria(problemId)]);current();
  const latest=[...sets.revisions].sort((a,b)=>b.revision-a.revision)[0];
  if(detail.problem.business_problem_id!==problemId||detail.problem.current_revision_id!==problemRevisionId||!latest||latest.set_revision_id!==savedSet.set_revision_id||latest.digest!==savedSet.digest||latest.problem_revision_id!==problemRevisionId||!latest.ordered_criterion_revision_ids.length||JSON.stringify(latest.ordered_criterion_revision_ids)!==JSON.stringify(savedSet.ordered_criterion_revision_ids)||latest.ordered_criterion_revision_ids.some(id=>!criteria.revisions.some(c=>c.revision_id===id)))throw new WorkbenchRequestError("PROBLEM_CRITERIA_CONFIRMATION_STALE",409);
  return detail;
 }
 current();let detail=await readExact();
 if(detail.problem.current_state==="DRAFT"){
  current();await transitionBusinessProblem(csrfToken,problemId,{toState:"ACTIVE",expectedVersion:detail.problem.aggregate_version,idempotencyKey});current();detail=await readExact();
 }
 if(detail.problem.current_state!=="ACTIVE")throw new WorkbenchRequestError("BUSINESS_PROBLEM_TRANSITION_INVALID",409);
 current();return `/work/plan?problem=${encodeURIComponent(problemId)}`;
}
