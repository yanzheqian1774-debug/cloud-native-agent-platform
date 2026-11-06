import {conversationRequest,type PrivateConversation} from './privateConversation';
import {WorkbenchRequestError} from './businessWorkspace';
export type SourceReference={kind:'DRAFT';invocationId:string;contextId:string;turnId:string;turnVersion:number}|{kind:'PROBLEM';target:{problemId:string;revisionId:string;problemDigest:string}}|{kind:'PLANNING';invocationId:string;contextId:string;requestRevision:number;target:Record<string,unknown>};
export function continuationQuery(search=window.location.search){const c=new URLSearchParams(search).get('returnConversation');return c?'&returnConversation='+encodeURIComponent(c):''}
export async function conversationActionHeaders(conversation:string|null,csrf:string,action:'DRAFT'|'CREATE_PROBLEM'|'PLANNING'|'PLANNING_CONTINUE',payload:Record<string,unknown>,source:SourceReference|null,expectedOwnerVersion:number,humanText?:string):Promise<Record<string,string>>{
 if(!conversation)return {};
 const ownerKey=String(payload.idempotencyKey??payload.idempotency_key);
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(action+':'+ownerKey));
 const key=Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
 let current=await conversationRequest<PrivateConversation>('/'+conversation);
 const known=current.messages.find(m=>m.kind==='ACTION_INTENT'&&m.facts?.ownerRequestKey===ownerKey&&m.facts?.action===action);
 if(known?.facts?.attemptState==='UNKNOWN')throw new WorkbenchRequestError('CONVERSATION_ACTION_ALREADY_CLAIMED_READ_ONLY',409);
 const text=action==='DRAFT'?'明确请求草稿辅助：'+(humanText??String(payload.content)):action==='CREATE_PROBLEM'?'明确确认创建业务问题：'+String(payload.title)+'\n'+String(payload.description):'明确请求当前问题的规划建议：'+((payload.answers as string[]).join('\n')||'依据已确认目标与标准生成建议');
 const existing=current.messages.find(m=>m.request_key==='confirm:'+key);
 const message=existing?{identity:existing.message_id}:await conversationRequest<{identity:string}>('/'+conversation+'/messages',csrf,{idempotencyKey:'confirm:'+key,expectedVersion:current.conversation.version,content:text.slice(0,2048)});
 current=await conversationRequest<PrivateConversation>('/'+conversation);
 const body={idempotencyKey:'action:'+key,expectedVersion:current.conversation.version,messageId:message.identity,action,payload,source,expectedOwnerVersion,confirmed:true};
 // Original payload and expectedVersion are stable on recovery; a claimed
 // original route can never be dispatched again through this helper.
 const intent=known?.facts?.intentId?{intentId:known.facts.intentId,claimed:false}:await conversationRequest<{intentId:string;claimed:boolean}>('/'+conversation+'/intents',csrf,body);
 if(intent.claimed)throw new WorkbenchRequestError('CONVERSATION_ACTION_ALREADY_CLAIMED_READ_ONLY',409);
 return {'X-Conversation-ID':conversation,'X-Conversation-Intent':intent.intentId};
}
