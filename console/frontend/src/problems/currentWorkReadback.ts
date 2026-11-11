import {conversationScope} from './conversationViewState';
import {listBusinessProblems,readBusinessProblem,readWorkbenchSession,WorkbenchRequestError,type BusinessProblemRevision} from '../api/businessWorkspace';
import {conversationRequest,type PrivateConversation} from '../api/privateConversation';
import {preparedRequest,type ExecutionView} from '../api/preparedExecution';

export type WorkQuestion={questionKey:string;questionDigest:string;question:string;expiresAt:string;answer:string|null;expired:boolean};
export type CurrentWork={problem:BusinessProblemRevision;execution:ExecutionView;conversation:string;originVerified:boolean;questions:WorkQuestion[];questionsReadable:boolean};
export const terminalWork=new Set(['SUCCEEDED','FAILED','CANCELLED','CANCELED','RECOVERY_REQUIRED','UNKNOWN','OUTCOME_UNKNOWN']);
export const pendingQuestions=(w:CurrentWork,now:number)=>terminalWork.has(w.execution.progress?.state??'')?[]:w.questions.filter(q=>q.answer===null&&!q.expired&&Date.parse(q.expiresAt)>now);
async function mapBounded<T,R>(values:T[],map:(value:T)=>Promise<R>,signal?:AbortSignal):Promise<R[]>{
 const results:R[]=new Array(values.length);let next=0;
 await Promise.all(Array.from({length:Math.min(4,values.length)},async()=>{while(next<values.length){signal?.throwIfAborted();const index=next++;results[index]=await map(values[index])}}));return results;
}
async function questions(digest:string,signal?:AbortSignal){
 // Bound this auxiliary read so saved work remains accessible when progress stalls.
 const deadline=AbortSignal.timeout(15000),readSignal=signal?AbortSignal.any([signal,deadline]):deadline;
 const response=await fetch(`/api/workbench/v1/prepared-executions/${encodeURIComponent(digest)}/native-progress`,{credentials:'same-origin',headers:{Accept:'application/json'},signal:readSignal});
 const body=await response.json();if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));
 if(!response.ok)throw new WorkbenchRequestError(body.reasonCode??'PROGRESS_UNAVAILABLE',response.status);
 if(!Array.isArray(body.result?.questions)||body.result.questions.some((q:WorkQuestion)=>typeof q.questionKey!=='string'||typeof q.questionDigest!=='string'||typeof q.question!=='string'||typeof q.expired!=='boolean'||!(q.answer===null||typeof q.answer==='string')||!Number.isFinite(Date.parse(q.expiresAt))))throw Error('QUESTION_PROJECTION_INVALID');
 return body.result.questions as WorkQuestion[];
}
export type WorkDirectoryRead={scope:string;works:CurrentWork[];limited:boolean;unlinkedProblems:number;loading:boolean};
export async function readCurrentWork(onProgress?:(value:WorkDirectoryRead)=>void,signal?:AbortSignal,options:{includeCompletedQuestions?:boolean}={}):Promise<WorkDirectoryRead>{
 const session=await readWorkbenchSession(signal),scope=conversationScope(session);let limited=false;
 const problemReads=new Map<string,ReturnType<typeof readBusinessProblem>>();
 // Share only this read's exact requests. A refresh always reauthorizes afresh.
 const executionReads=new Map<string,Promise<ExecutionView>>(),questionReads=new Map<string,Promise<WorkQuestion[]>>();
 const readExecution=(digest:string)=>{let read=executionReads.get(digest);if(!read){read=preparedRequest<ExecutionView>(digest,undefined,undefined,undefined,signal);executionReads.set(digest,read)}return read};
 const readQuestions=(digest:string)=>{let read=questionReads.get(digest);if(!read){read=questions(digest,signal);questionReads.set(digest,read)}return read};
 const problems=await listBusinessProblems(signal),works=new Map<string,CurrentWork>(),order=new Map<string,number>();
 const ordered=()=>[...works.values()].sort((a,b)=>(order.get(a.conversation)??0)-(order.get(b.conversation)??0)||a.execution.digest.localeCompare(b.execution.digest));
 const publish=()=>onProgress?.({scope,works:ordered(),limited,unlinkedProblems:0,loading:true});
 try{
  const conversations=await conversationRequest<{items:{conversation_id:string}[]}>('',undefined,undefined,signal);conversations.items.forEach((c,i)=>order.set(c.conversation_id,i));
  await mapBounded(conversations.items,async c=>{
   try{
    const record=await conversationRequest<Pick<PrivateConversation,'conversation'|'links'>>('/'+c.conversation_id+'/work-links',undefined,undefined,signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000));
    if(record.links.some(link=>!link.readable))limited=true;
    if(!record.links.some(link=>link.readable&&link.target?.problemId))return;
    let ownedExecution:string|undefined,ownedProblem:string|undefined;
    try{const state=(await conversationRequest<{state?:{execution?:string;problem?:{business_problem_id?:string}}}>('/'+c.conversation_id+'/journey',undefined,undefined,signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000))).state;ownedExecution=state?.execution;ownedProblem=state?.problem?.business_problem_id}catch{/* Readable historical links need not have a journey. */}
    for(const link of record.links){
     const digest=link.target?.executionDigest??(ownedProblem===link.target?.problemId?ownedExecution:undefined);
     if(!link.readable){limited=true;continue}if(!link.target||!digest)continue;
     const originVerified=ownedExecution===digest,prior=works.get(digest);if(prior&&(prior.originVerified||!originVerified))continue;
     try{
      const execution=await readExecution(digest),listed=problems.problems.find(p=>p.business_problem_id===link.target!.problemId);
      if(!Array.isArray(execution.artifacts)||!Array.isArray(execution.events)||!Array.isArray(execution.preparation?.participants)||!Array.isArray(execution.preparation?.semantics?.tasks))throw Error('WORK_PROJECTION_INVALID');
      const ref=execution.preparation.semantics.target?.problem;
      if(!listed||execution.digest!==digest||ref?.resource_id!==link.target.problemId||!ref.revision_id||!ref.digest)throw Error('WORK_IDENTITY_MISMATCH');
      let problem=listed;
      if(listed.revision_id!==ref.revision_id||listed.digest!==ref.digest){
       let read=problemReads.get(ref.resource_id);if(!read){read=readBusinessProblem(ref.resource_id,signal);problemReads.set(ref.resource_id,read)}
       const detail=await read,exact=detail.revisions?.find(p=>p.business_problem_id===ref.resource_id&&p.revision_id===ref.revision_id&&p.digest===ref.digest);
       if(detail.problem?.business_problem_id!==ref.resource_id||!exact)throw Error('WORK_PROBLEM_REVISION_UNAVAILABLE');
       problem=exact;
      }
      let qs:WorkQuestion[]=[],questionsReadable=true;
      if(options.includeCompletedQuestions||!terminalWork.has(execution.progress?.state??'')){try{qs=await readQuestions(digest)}catch{signal?.throwIfAborted();questionsReadable=false;limited=true}}
      const existing=works.get(digest);if(!existing||(!existing.originVerified&&originVerified))works.set(digest,{problem,execution,conversation:record.conversation.conversation_id,originVerified,questions:qs,questionsReadable});publish();
     }catch{limited=true}
    }
   }catch{limited=true}
  },signal);
 }catch{signal?.throwIfAborted();limited=true}
 if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取当前工作。');
 const records=ordered();return {scope,works:records,limited,loading:false,unlinkedProblems:problems.problems.filter(p=>!records.some(w=>w.problem.business_problem_id===p.business_problem_id)).length};
}

export async function readSelectedWork(digest:string,origin:string,signal?:AbortSignal):Promise<{scope:string;work:CurrentWork}>{
 const scope=conversationScope(await readWorkbenchSession(signal));
 const execution=await preparedRequest<ExecutionView>(digest,undefined,undefined,undefined,signal),ref=execution.preparation?.semantics?.target?.problem;
 if(execution.digest!==digest||!ref?.resource_id||!ref.revision_id||!ref.digest||!Array.isArray(execution.artifacts)||!Array.isArray(execution.events)||!Array.isArray(execution.preparation.participants)||!Array.isArray(execution.preparation.semantics.tasks))throw Error('本次执行或固定问题版本尚未核实。');
 const detail=await readBusinessProblem(ref.resource_id,signal),problem=detail.revisions?.find(p=>p.business_problem_id===ref.resource_id&&p.revision_id===ref.revision_id&&p.digest===ref.digest);
 if(detail.problem?.business_problem_id!==ref.resource_id||!problem)throw Error('本次执行引用的问题版本当前不可读，未替换为最新版本。');
 let conversation='',originVerified=false,qs:WorkQuestion[]=[],questionsReadable=true;
 if(origin){try{
  const record=await conversationRequest<Pick<PrivateConversation,'conversation'|'links'>>('/'+encodeURIComponent(origin)+'/work-links',undefined,undefined,signal);let state:{execution?:string;problem?:{business_problem_id?:string}}|undefined;
  try{state=(await conversationRequest<{state?:typeof state}>('/'+encodeURIComponent(origin)+'/journey',undefined,undefined,signal)).state}catch{signal?.throwIfAborted()}
  const linked=record.conversation.conversation_id===origin&&record.links.some(l=>l.readable&&l.target?.problemId===ref.resource_id&&(l.target.executionDigest===digest||(state?.execution===digest&&state.problem?.business_problem_id===ref.resource_id)));
  if(linked){conversation=origin;originVerified=state?.execution===digest}
 }catch{signal?.throwIfAborted()}}
 if(!terminalWork.has(execution.progress?.state??'')){try{qs=await questions(digest,signal)}catch{signal?.throwIfAborted();questionsReadable=false}}
 if(conversationScope(await readWorkbenchSession(signal))!==scope)throw Error('登录身份已变化，请重新读取当前工作。');
 return {scope,work:{problem,execution,conversation,originVerified,questions:qs,questionsReadable}};
}
