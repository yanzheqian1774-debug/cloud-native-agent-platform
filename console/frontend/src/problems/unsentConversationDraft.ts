import type {WorkbenchSession} from '../api/businessWorkspace';
const prefix='conversation-unsent.v1:';
const lifetime=24*60*60*1000;
export function unsentDraftKey(session:WorkbenchSession,conversation:string){
 return conversation?JSON.stringify([session.principal.principalId,session.principal.tenantId,session.principal.securityDomain,conversation]):undefined;
}
export function readUnsentDraft(key:string|undefined){
 if(!key)return '';
 try{const raw=sessionStorage.getItem(prefix+key);if(!raw)return '';const value:unknown=JSON.parse(raw);
  if(!value||typeof value!=='object'||!('text' in value)||typeof value.text!=='string'||value.text.length>1800||!('expiresAt' in value)||typeof value.expiresAt!=='number'||!Number.isFinite(value.expiresAt)||value.expiresAt<=Date.now()||value.expiresAt>Date.now()+lifetime){sessionStorage.removeItem(prefix+key);return ''}
  return value.text;
 }catch{return ''}
}
export function saveUnsentDraft(key:string|undefined,text:string){
 if(!key)return;
 try{if(!text||text.length>1800)sessionStorage.removeItem(prefix+key);else sessionStorage.setItem(prefix+key,JSON.stringify({text,expiresAt:Date.now()+lifetime}))}catch{/* Text recovery is never authority or a prerequisite for sending. */}
}
export function clearUnsentDrafts(){
 try{for(const key of Object.keys(sessionStorage))if(key.startsWith(prefix))sessionStorage.removeItem(key)}catch{/* Logout must not depend on browser storage. */}
}
