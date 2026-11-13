import {readWorkbenchSession} from '../api/businessWorkspace';
const root='/api/workbench/v1/ontology-maintenance';
type State={commandKey:string;identity:string;revision:string;status:'PENDING'|'SAVED'};
type Receipt={schemaVersion:string;commandKey:string;ontologyId:string;revision:string;digest:string;version:number};
export class OntologyReadUnknown extends Error {constructor(){super('上次读取准备结果尚未核实。请核对原记录，系统不会重复提交。')}}
const scopeOf=(s:Awaited<ReturnType<typeof readWorkbenchSession>>)=>JSON.stringify(s.principal);
export async function prepareRetainedOntologyRead(identity:string,revision:string,isCurrent:()=>boolean){
 const session=await readWorkbenchSession(),scope=scopeOf(session);if(!isCurrent())throw Error('当前查看对象已变化');
 const key=`ontology-maintenance.read.v1:${scope}:${identity}:${revision}`;
 const raw=sessionStorage.getItem(key);const prior=raw?JSON.parse(raw) as State:null;
 if(prior&&(prior.identity!==identity||prior.revision!==revision||typeof prior.commandKey!=='string'||!['PENDING','SAVED'].includes(prior.status)))throw new OntologyReadUnknown();
 async function checkIdentity(){const now=await readWorkbenchSession();if(!isCurrent()||scopeOf(now)!==scope)throw Error('登录身份或查看对象已变化，请重新打开');return now;}
 function accept(value:Receipt,p:State){if(value?.schemaVersion!=='ontology-maintenance-read.v1'||value.commandKey!==p.commandKey||value.ontologyId!==identity||value.revision!==revision||!/^[a-f0-9]{64}$/.test(value.digest)||!Number.isInteger(value.version))throw new OntologyReadUnknown();sessionStorage.setItem(key,JSON.stringify({...p,status:'SAVED'}));}
 if(prior?.status==='PENDING'){
  // Refresh/recovery only reads the original receipt. Never consumes a new key.
  const response=await fetch(`${root}/commands/${encodeURIComponent(prior.commandKey)}`,{credentials:'same-origin'});await checkIdentity();
  if(!response.ok)throw new OntologyReadUnknown();accept((await response.json()).result,prior);return;
 }
 const response=await fetch(`${root}/capabilities/${encodeURIComponent(identity)}`,{credentials:'same-origin'});const body=await response.json();await checkIdentity();
 if(!response.ok||body.result?.writeEligible!==true)throw Error('当前账号无权读取此修订');
 const current=await checkIdentity();
 // Caller has already observed exact detail READ denied. A known completed old
 // preparation may expire; a new key does not replay its old command.
 const pending:State={identity,revision,commandKey:crypto.randomUUID(),status:'PENDING'};
 sessionStorage.setItem(key,JSON.stringify(pending));
 try{
  const result=await fetch(root+'/commands',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':current.csrfToken},body:JSON.stringify({action:'PREPARE_READ',commandKey:pending.commandKey,ontologyId:identity,revision})});
  const value=await result.json();await checkIdentity();
  if(!result.ok){if(result.status>=400&&result.status<500&&![408,429].includes(result.status)&&typeof value.reasonCode==='string'){sessionStorage.removeItem(key);throw Error(value.reasonCode)}throw new OntologyReadUnknown()}
  accept(value.result,pending);
 }catch(error){if(sessionStorage.getItem(key)===JSON.stringify(pending))throw new OntologyReadUnknown();throw error}
}
