import {WorkbenchRequestError} from './businessWorkspace';
export type WorkLink={link_id:string;readable:boolean;title?:string;target?:{problemId:string;revisionId:string;problemDigest:string;executionDigest?:string}};
export type PrivateMessage={message_id:string;sequence:number;content:string;focus_link_id?:string;disposition:string;created_at:string};
export type PrivateConversation={conversation:{conversation_id:string;title:string;version:number;created_at:string};messages:PrivateMessage[];links:WorkLink[]};
export async function conversationRequest<T>(path='',csrf?:string,body?:unknown):Promise<T>{
 const response=await fetch('/api/workbench/v1/conversations'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{Accept:'application/json',...(body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':csrf??''})},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const value=await response.json();if(!response.ok){if(response.status===401)window.dispatchEvent(new Event('workbench-session-expired'));throw new WorkbenchRequestError(value.reasonCode??'CONVERSATION_UNAVAILABLE',response.status)}return value.result as T;
}
