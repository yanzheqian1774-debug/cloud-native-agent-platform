import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';

export type OntologyAction='CREATE'|'REVISE'|'VALIDATE'|'TEST'|'REVIEW'|'PUBLISH'|'DEPRECATE';
export type MaintenanceOutcome={ontology_id:string;revision_id:string;version:number;digest:string;state:string};
export type MaintenanceReceipt={schemaVersion:'ontology-maintenance-receipt.v1';commandKey:string;ontologyId:string;action:OntologyAction;outcome:MaintenanceOutcome;writeEligible:boolean};
type Pending={commandKey:string;identity:string;action:OntologyAction};
const root='/api/workbench/v1/ontology-maintenance';
const actions:OntologyAction[]=['CREATE','REVISE','VALIDATE','TEST','REVIEW','PUBLISH','DEPRECATE'];
const scopeOf=(s:Awaited<ReturnType<typeof readWorkbenchSession>>)=>JSON.stringify([s.principal.principalId,s.principal.tenantId,s.principal.securityDomain]);
const storageKey=(scope:string,id:string)=>`ontology-maintenance.pending.v1:${scope}:${id}`;
function restored(scope:string,id:string):Pending|null{try{const value=JSON.parse(sessionStorage.getItem(storageKey(scope,id))??'null');return value&&value.identity===id&&typeof value.commandKey==='string'&&actions.includes(value.action)?value:null}catch{return null}}
function persist(scope:string,id:string,pending:Pending|null){if(pending)sessionStorage.setItem(storageKey(scope,id),JSON.stringify(pending));else sessionStorage.removeItem(storageKey(scope,id))}

function validReceipt(value:MaintenanceReceipt|undefined,p:Pending){const v=value?.outcome;return value?.schemaVersion==='ontology-maintenance-receipt.v1'&&value.commandKey===p.commandKey&&value.ontologyId===p.identity&&value.action===p.action&&typeof value.writeEligible==='boolean'&&v?.ontology_id===p.identity&&typeof v.revision_id==='string'&&v.revision_id.length>0&&Number.isInteger(v.version)&&v.version>0&&typeof v.digest==='string'&&/^[a-f0-9]{64}$/.test(v.digest)&&v.state===p.action}

export function useOntologyMaintenance(identity:string){
 const [creationAvailable,setCreationAvailable]=useState(false),[allowed,setAllowed]=useState<OntologyAction[]>([]),[ready,setReady]=useState(false),[pending,setPending]=useState<Pending|null>(null),[checking,setChecking]=useState(false),[message,setMessage]=useState(''),[receipt,setReceipt]=useState<MaintenanceReceipt|null>(null);
 const current=useRef<{identity:string;scope:string;pending:Pending|null;posting:boolean}|null>(null);
 const [stateIdentity,setStateIdentity]=useState('');
 useLayoutEffect(()=>{const owner={identity,scope:'',pending:null as Pending|null,posting:false};current.current=owner;return()=>{if(current.current===owner)current.current=null}},[identity]);
 const recover=useCallback(async()=>{
  const owner=current.current;if(!owner)return;const p=owner.pending;if(!p||owner.posting)return;
  setChecking(true);
  try{const session=await readWorkbenchSession();if(current.current!==owner)return;if(scopeOf(session)!==owner.scope){owner.pending=null;setPending(null);setAllowed([]);setCreationAvailable(false);setReceipt(null);setMessage('登录身份已变化，请刷新后核对。');return;}
   const response=await fetch(`${root}/commands/${encodeURIComponent(p.commandKey)}`,{credentials:'same-origin',headers:{Accept:'application/json'}});
   const body=await response.json();if(current.current!==owner)return;
   const value=body.result as MaintenanceReceipt;
   if(!response.ok||!validReceipt(value,p)){setMessage('尚未核实上次提交结果。请稍后再次核对，系统不会重复提交。');return}
   persist(owner.scope,owner.identity,null);owner.pending=null;setPending(null);setReceipt(value);setMessage('已读取上次提交结果。');
  }catch{if(current.current===owner)setMessage('暂时无法核对上次提交结果。已保留原记录，不会重复提交。')}
  finally{if(current.current===owner)setChecking(false)}
 },[]);
 useEffect(()=>{const owner=current.current;if(!owner)return;let active=true;
  void(async()=>{try{const session=await readWorkbenchSession();if(!active||current.current!==owner)return;setStateIdentity(identity);setReady(false);setAllowed([]);setCreationAvailable(false);setReceipt(null);setMessage('');owner.scope=scopeOf(session);owner.pending=restored(owner.scope,identity);setPending(owner.pending);
    const response=await fetch(`${root}/capabilities/${encodeURIComponent(identity)}`,{credentials:'same-origin',headers:{Accept:'application/json'}});const body=await response.json();if(!active||current.current!==owner)return;
    if(response.ok&&body.result?.schemaVersion==='ontology-maintenance-capabilities.v1'&&Array.isArray(body.result.allowedActions)){setAllowed(actions.filter(a=>body.result.allowedActions?.includes(a)));setCreationAvailable(body.result.creationAvailable===true||body.result.allowedActions?.includes('CREATE')===true)}
   }catch{if(active&&current.current===owner)setAllowed([])}finally{if(active&&current.current===owner){setReady(true);if(owner.pending)void recover()}}})();
  return()=>{active=false};
 },[identity,recover]);
 async function submit(action:OntologyAction,payload:Record<string,unknown>){
  const owner=current.current;if(!owner||owner.identity!==identity||stateIdentity!==identity||!ready||!allowed.includes(action)||owner.pending||owner.posting||!owner.scope)return null;
  owner.posting=true;setChecking(true);setMessage('');
  try{const session=await readWorkbenchSession();if(current.current!==owner||scopeOf(session)!==owner.scope){if(current.current===owner){setAllowed([]);setCreationAvailable(false);setMessage('登录身份已变化，请刷新后再操作。')}return null}
   const p={commandKey:crypto.randomUUID(),identity:owner.identity,action};
   // Persist BEFORE POST. Failed storage means no request is sent.
   persist(owner.scope,owner.identity,p);owner.pending=p;setPending(p);
   const response=await fetch(`${root}/commands`,{method:'POST',credentials:'same-origin',headers:{Accept:'application/json','Content-Type':'application/json','X-CSRF-Token':session.csrfToken},body:JSON.stringify({...payload,action,commandKey:p.commandKey,ontologyId:owner.identity})});
   const body=await response.json();if(current.current!==owner)return null;
   if(!response.ok){if(response.status>=400&&response.status<500&&![408,429].includes(response.status)&&typeof body.reasonCode==='string'){persist(owner.scope,owner.identity,null);owner.pending=null;setPending(null);setMessage(body.reasonCode??'本次修改未被接受，请检查后再提交。')}else setMessage('提交结果尚未核实。已保留本次记录，请核对结果。');return null}
   const value=body.result as MaintenanceReceipt;
   if(!validReceipt(value,p)){setMessage('提交结果尚未核实。已保留本次记录，请核对结果。');return null}
   persist(owner.scope,owner.identity,null);owner.pending=null;setPending(null);setReceipt(value);return value;
  }catch{if(current.current===owner)setMessage(owner.pending?'连接中断，提交结果尚未核实。请核对原记录，系统不会重复提交。':'无法准备本次提交，尚未发送。');return null}
  finally{owner.posting=false;if(current.current===owner)setChecking(false)}
 }
 const visible=stateIdentity===identity;return {creationAvailable:visible&&creationAvailable,allowed:visible?allowed:[],ready:visible&&ready,pending:visible?pending:null,checking:visible&&checking,message:visible?message:'',receipt:visible?receipt:null,submit,recover};
}
