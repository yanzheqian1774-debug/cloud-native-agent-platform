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
export type WorkDirectoryRead={scope:string;works:CurrentWork[];limited:boolean;unlinkedProblems:number;loading:boolean};
export async function readCurrentWork(onProgress?:(value:WorkDirectoryRead)=>void):Promise<WorkDirectoryRead>{
 const session=await readWorkbenchSession(),scope=conversationScope(session);let limited=false;
 const problems=await listBusinessProblems(),works=new Map<string,CurrentWork>(),order=new Map<string,number>();
 const ordered=()=>[...works.values()].sort((a,b)=>(order.get(a.conversation)??0)-(order.get(b.conversation)??0)||a.execution.digest.localeCompare(b.execution.digest));
 const publish=()=>onProgress?.({scope,works:ordered(),limited,unlinkedProblems:0,loading:true});
 try{
  const conversations=await conversationRequest<{items:{conversation_id:string}[]}>();conversations.items.forEach((c,i)=>order.set(c.conversation_id,i));
  await mapBounded(conversations.items,async c=>{
   try{
    const record=await conversationRequest<PrivateConversation>('/'+c.conversation_id,undefined,undefined,AbortSignal.timeout(15000));
    if(!record.links.some(link=>link.readable&&link.target?.problemId))return;
    let ownedExecution:string|undefined,ownedProblem:string|undefined;
    try{const state=(await conversationRequest<{state?:{execution?:string;problem?:{business_problem_id?:string}}}>('/'+c.conversation_id+'/journey',undefined,undefined,AbortSignal.timeout(15000))).state;ownedExecution=state?.execution;ownedProblem=state?.problem?.business_problem_id}catch{/* Readable historical links need not have a journey. */}
    for(const link of record.links){
     const digest=link.target?.executionDigest??(ownedProblem===link.target?.problemId?ownedExecution:undefined);
     if(!link.readable){limited=true;continue}if(!link.target||!digest)continue;
     const originVerified=ownedExecution===digest,prior=works.get(digest);if(prior&&(prior.originVerified||!originVerified))continue;
     try{
      const execution=await preparedRequest<ExecutionView>(digest),problem=problems.problems.find(p=>p.business_problem_id===link.target!.problemId);
      if(!Array.isArray(execution.artifacts)||!Array.isArray(execution.events)||!Array.isArray(execution.preparation?.participants)||!Array.isArray(execution.preparation?.semantics?.tasks))throw Error('WORK_PROJECTION_INVALID');
      if(!problem||execution.digest!==digest||execution.preparation.semantics.target.problem.resource_id!==link.target.problemId)throw Error('WORK_IDENTITY_MISMATCH');
      let qs:WorkQuestion[]=[],questionsReadable=true;try{qs=await questions(digest)}catch{questionsReadable=false;limited=true}
      const existing=works.get(digest);if(!existing||(!existing.originVerified&&originVerified))works.set(digest,{problem,execution,conversation:record.conversation.conversation_id,originVerified,questions:qs,questionsReadable});publish();
     }catch{limited=true}
    }
   }catch{limited=true}
  });
 }catch{limited=true}
 if(conversationScope(await readWorkbenchSession())!==scope)throw Error('登录身份已变化，请重新读取当前工作。');
 const records=ordered();return {scope,works:records,limited,loading:false,unlinkedProblems:problems.problems.filter(p=>!records.some(w=>w.problem.business_problem_id===p.business_problem_id)).length};
}
