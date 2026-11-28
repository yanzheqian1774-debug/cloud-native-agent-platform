import {WorkbenchRequestError} from './businessWorkspace';
export type WorkLink={fixedCycleContentComplete?:boolean;fixedCycle?:import('./conversationFixedFocus').FixedCycleFocus;link_id:string;readable:boolean;title?:string;target?:null|{problemId:string;revisionId:string;problemDigest:string;executionDigest?:string}};
export type MessageFacts={assistantResponse?:boolean;requestKey?:string;userMessageId?:string;invokedBy?:string;response?:{conversationRoute?:{relation:string};inputSource?:import('./draftAssistanceTypes').ConversationInputSourceReference;resultKind?:string;answer?:string;dataNeeds?:string[]};readable?:boolean;readState?:'ACCESS_RESTRICTED'|'TEMPORARILY_UNAVAILABLE'|'SOURCE_MISMATCH';intentId?:string;messageId?:string;action?:string;ownerRequestKey?:string;attemptState?:string;state?:string;reasonCode?:string|null;source?:import('./conversationActions').SourceReference|null;observation?:{title?:string;objective?:string;inputNotes?:string;capability?:{capabilityId:string;revisionId:string;digest:string;inputs:string;outputs:string;acceptanceCriteria:string[];manualInvolvement:string;exclusions:string};state:string;transport?:string;resultKind?:string;reasonCode?:string;contentDisposition?:string;questions?:string[]}|null};
export type PrivateMessage={goalId?:string;message_id:string;sequence:number;author_id?:string;content:string;focus_link_id?:string;disposition:string;created_at?:string;request_key?:string;kind?:string;facts?:MessageFacts};
export type PrivateConversation={conversation:{conversation_id:string;title:string;version:number;created_at:string};messages:PrivateMessage[];links:WorkLink[]};
export async function conversationRequest<T>(path='',csrf?:string,body?:unknown,signal?:AbortSignal):Promise<T>{
 const response=await fetch('/api/workbench/v1/conversations'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',signal,headers:{Accept:'application/json',...(body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf??''})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const value=await response.json();if(!response.ok){if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));throw new WorkbenchRequestError(value.reasonCode??'CONVERSATION_UNAVAILABLE',response.status)}return value.result as T;
}

export const readConversationHead=(identity:string)=>conversationRequest<Pick<PrivateConversation,'conversation'>>('/'+encodeURIComponent(identity)+'/head');

export type ConversationMessagePage={conversation:PrivateConversation['conversation'];messages:PrivateMessage[];page:{hasMore:boolean;nextCursor:string|null;resumeCursor?:string|null}};
export async function readConversationMessages(identity:string,before?:string,signal?:AbortSignal){
 const value=await conversationRequest<ConversationMessagePage>('/'+encodeURIComponent(identity)+'/messages?'+new URLSearchParams({limit:'50',...(before?{before}:{})}),undefined,undefined,signal);
 if(value?.conversation?.conversation_id!==identity||!Number.isSafeInteger(value.conversation.version)||!Array.isArray(value.messages)||typeof value.page?.hasMore!=='boolean'||!(value.page.nextCursor===null||typeof value.page.nextCursor==='string')||value.page.hasMore&&!value.page.nextCursor||!(value.page.resumeCursor===undefined||value.page.resumeCursor===null||typeof value.page.resumeCursor==='string'))throw new WorkbenchRequestError('CONVERSATION_MESSAGE_PAGE_INVALID',503);
 return value;
}
export const readConversationWorkLinks=(identity:string,signal?:AbortSignal)=>conversationRequest<Pick<PrivateConversation,'conversation'|'links'>>('/'+encodeURIComponent(identity)+'/work-links',undefined,undefined,signal);

export type CapabilityConversationContext={conversation:PrivateConversation['conversation'];message:PrivateMessage|null};
export const readCapabilityConversationContext=(identity:string,signal?:AbortSignal)=>conversationRequest<CapabilityConversationContext>('/'+encodeURIComponent(identity)+'/capability-context',undefined,undefined,signal);
export type UnderstandingSuccessPage={conversation:PrivateConversation['conversation'];items:{message:PrivateMessage;userMessage:PrivateMessage|null}[];page:{hasMore:boolean;nextCursor:string|null;resumeCursor?:string|null};unavailable:boolean};
export const readUnderstandingSuccessPage=(identity:string,before?:string)=>conversationRequest<UnderstandingSuccessPage>('/'+encodeURIComponent(identity)+'/understanding-successes?'+new URLSearchParams({limit:'50',...(before?{before}:{})}));
