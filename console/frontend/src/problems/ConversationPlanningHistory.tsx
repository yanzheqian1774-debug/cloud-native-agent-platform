import {conversationRequest,type PrivateConversation,type PrivateMessage} from '../api/privateConversation';
import type {Invocation} from '../planning/planningRequests';
import type {SourceReference} from '../api/conversationActions';

export function planningQuestion(message:PrivateMessage){
 const facts=message.facts,observation=facts?.observation;
 return message.kind==='SOURCE'&&facts?.readable!==false&&facts?.source?.kind==='PLANNING'&&observation?.state==='SUCCEEDED'&&observation.resultKind==='NEEDS_CLARIFICATION'&&observation.questions?.length?observation.questions:null;
}
/** Persist only owner-read questions. Unknown writes recover by the same source key. */
export async function retainPlanningQuestion(conversation:string,csrf:string,key:string,planning:Invocation,verify:()=>Promise<void>){
 const target=planning.invocation.target;
 if(!target.suggestion_context_id||!Number.isInteger(target.request_revision)||!target.problem)throw Error('原追问来源不完整，未提交补充说明。');
 const source:SourceReference={kind:'PLANNING',invocationId:target.invocation_id,contextId:target.suggestion_context_id,requestRevision:target.request_revision!,target:target.problem};
 const requestKey=key+':planning-question:'+target.invocation_id;
 await verify();
 let current=await conversationRequest<PrivateConversation>('/'+conversation);
 let saved=current.messages.find(message=>message.request_key===requestKey);
 if(!saved){
  await verify();
  await conversationRequest('/'+conversation+'/sources',csrf,{expectedVersion:current.conversation.version,idempotencyKey:requestKey,source});
  current=await conversationRequest<PrivateConversation>('/'+conversation);
  saved=current.messages.find(message=>message.request_key===requestKey);
 }
 await verify();
 if(!saved||!planningQuestion(saved)||canonical(saved.facts?.source)!==canonical(source))throw Error('原追问尚未核实保存，补充说明未提交；请稍后再试。');
 return current;
}

function canonical(value:unknown):string{if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(value&&typeof value==='object'&&!Array.isArray(value))return '{'+Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>JSON.stringify(key)+':'+canonical(item)).join(',')+'}';return JSON.stringify(value)}
