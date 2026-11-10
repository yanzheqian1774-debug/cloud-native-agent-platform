import type {WorkbenchSession} from "../api/businessWorkspace";
export const conversationScope=(session:WorkbenchSession)=>JSON.stringify([session.principal.principalId,session.principal.tenantId,session.principal.securityDomain,session.session.expiresAt]);
const key=(scope:string,id:string)=>`conversation-view.v1:${scope}:${id}`;
export type ConversationView={composer?:string;scrollTop?:number;railScroll?:number;url?:string};
export function readConversationView(scope:string,id:string):ConversationView{
  try{return JSON.parse(sessionStorage.getItem(key(scope,id))??"{}")}catch{return {}}
}
export function writeConversationView(scope:string,id:string,patch:ConversationView){
  if(!scope)return;
  try{sessionStorage.setItem(key(scope,id),JSON.stringify({...readConversationView(scope,id),...patch}))}catch{/* Full storage must never prevent reading or switching. */}
}
export function conversationUrl(scope:string,id:string){
  const saved=readConversationView(scope,id).url;
  if(saved){const url=new URL(saved,window.location.origin);if(url.origin===window.location.origin&&url.pathname==="/work"&&url.searchParams.get("problem")===id)return url.pathname+url.search;}
  return `/work?${new URLSearchParams({problem:id})}`;
}

export function clearConversationViewState(){
  try{for(const name of Object.keys(sessionStorage))if(['conversation-view.v1:','work-view.v1:','private-list-scroll:','conversation-list.scroll:'].some(prefix=>name.startsWith(prefix)))sessionStorage.removeItem(name)}catch{/* Presentation cleanup never changes authoritative records or command receipts. */}
}
