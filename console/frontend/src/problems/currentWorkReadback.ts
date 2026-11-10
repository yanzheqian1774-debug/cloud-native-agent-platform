import {conversationScope} from './conversationViewState';
import {listBusinessProblems,readWorkbenchSession,WorkbenchRequestError,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';

export type WorkQuestion={questionKey:string;questionDigest:string;question:string;expiresAt:string;answer:string|null;expired:boolean};
export type CurrentWork={problem:BusinessProblemRevision;execution:ExecutionView;conversation:string;originVerified:boolean;questions:WorkQuestion[];questionsReadable:boolean};
export const terminalWork=new Set(['SUCCEEDED','FAILED','CANCELLED','CANCELED','RECOVERY_REQUIRED','UNKNOWN','OUTCOME_UNKNOWN']);
export const pendingQuestions=(w:CurrentWork,now:number)=>terminalWork.has(w.execution.progress?.state??'')?[]:w.questions.filter(q=>q.answer===null&&!q.expired&&Date.parse(q.expiresAt)>now);
async function mapBounded<T,R>(values:T[],map:(value:T)=>Promise<R>):Promise<R[]>{
 const results:R[]=new Array(values.length);let next=0;
 await Promise.all(Array.from({length:Math.min(4,values.length)},async()=>{while(next<values.length){const index=next++;results[index]=await map(values[index])}}));return results;
}
async function questions(digest:string){
 const response=await fetch(`/api/workbench/v1/prepared-executions/${encodeURIComponent(digest)}/native-progress`,{credentials:'same-origin',headers:{Accept:'application/json'}});
 const body=await response.json();if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'PROGRESS_UNAVAILABLE',response.status);
 if(!Array.isArray(body.result?.questions)||body.result.questions.some((q:WorkQuestion)=>typeof q.questionKey!=='string'||typeof q.questionDigest!=='string'||typeof q.question!=='string'||typeof q.expired!=='boolean'||!(q.answer===null||typeof q.answer==='string')||!Number.isFinite(Date.parse(q.expiresAt))))throw Error('QUESTION_PROJECTION_INVALID');
 return body.result.questions as WorkQuestion[];
}
export async function readCurrentWork(){
 const session=await readWorkbenchSession(),scope=conversationScope(session);let limited=false;
 const problems=await listBusinessProblems();
 const refs=new Map<string,{problemId:string;conversation:string;originVerified:boolean}>();
 try{
  const conversations=await conversationRequest<{items:{conversation_id:string}[]}>();
  const records=await mapBounded(conversations.items,async c=>{try{const record=await conversationRequest<PrivateConversation>('/'+c.conversation_id);let ownedExecution:string|undefined;try{ownedExecution=(await conversationRequest<{state?:{execution?:string}}>('/'+c.conversation_id+'/journey')).state?.execution}catch{/* Linked history can remain readable without a journey journal. */}return {record,ownedExecution}}catch{limited=true;return null}});
  for(const item of records)for(const link of item?.record.links??[]){
   if(link.readable&&link.target?.executionDigest){const digest=link.target.executionDigest,originVerified=item?.ownedExecution===digest,prior=refs.get(digest);if(!prior||(!prior.originVerified&&originVerified))refs.set(digest,{problemId:link.target.problemId,conversation:item!.record.conversation.conversation_id,originVerified});}else if(!link.readable)limited=true;
  }
 }catch{limited=true}
 const records=await mapBounded([...refs],async([digest,ref]):Promise<CurrentWork|null>=>{
  try{
   const execution=await preparedRequest<ExecutionView>(digest),problem=problems.problems.find(p=>p.business_problem_id===ref.problemId);
   if(!Array.isArray(execution.artifacts)||!Array.isArray(execution.events)||!Array.isArray(execution.preparation?.participants)||!Array.isArray(execution.preparation?.semantics?.tasks))throw Error('WORK_PROJECTION_INVALID');
   if(!problem||execution.digest!==digest||execution.preparation.semantics.target.problem.resource_id!==ref.problemId)throw Error('WORK_IDENTITY_MISMATCH');
   let qs:WorkQuestion[]=[],questionsReadable=true;
   try{qs=await questions(digest)}catch{questionsReadable=false;limited=true}
   return {problem,execution,conversation:ref.conversation,originVerified:ref.originVerified,questions:qs,questionsReadable};
  }catch{limited=true;return null}
 });
 if(conversationScope(await readWorkbenchSession())!==scope)throw Error('登录身份已变化，请重新读取当前工作。');
 return {scope,works:records.filter((r):r is CurrentWork=>r!==null),limited,unlinkedProblems:problems.problems.filter(p=>!records.some(w=>w?.problem.business_problem_id===p.business_problem_id)).length};
}
