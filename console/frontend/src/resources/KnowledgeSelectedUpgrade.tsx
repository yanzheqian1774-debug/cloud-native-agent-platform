import {useEffect,useState} from 'react';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {SelectedResourceUpgrade,type UpgradeCandidate,type UpgradeSource} from './SelectedResourceUpgrade';
type Projection={kind:string;identity:string;revision:string;digest:string;subject:string;scope:{tenantId:string;securityDomain:string};dependencies:{incoming:UpgradeCandidate[]}};
export function KnowledgeSelectedUpgrade({resource,blocked,onLock,onRefresh}:{resource:UpgradeSource;blocked:boolean;onLock:(locked:boolean)=>void;onRefresh:()=>Promise<void>}){
 const [result,setResult]=useState<{key:string;rows:UpgradeCandidate[]}|null>(null),[failed,setFailed]=useState(false),[attempt,setAttempt]=useState(0);
 const published=resource.revisions.find(r=>r.revisionId===resource.publishedRevisionId);
 const identity=resource.resourceId,revision=published?.revisionId,digest=published?.digest,key=JSON.stringify([identity,revision,digest,resource.aggregateVersion]);
 useEffect(()=>{let live=true;const controller=new AbortController();const withdraw=()=>{live=false;controller.abort();setResult(null);setFailed(true)};
  const read=async()=>{if(!revision||!digest)throw Error();const before=await readWorkbenchSession(controller.signal);const response=await fetch('/api/workbench/v1/resource-directory/'+['knowledge',identity,revision].map(encodeURIComponent).join('/')+'/references',{credentials:'same-origin',signal:controller.signal});if(!response.ok)throw Error();const value=(await response.json()).result as Projection;const after=await readWorkbenchSession(controller.signal);if(JSON.stringify(before.principal)!==JSON.stringify(after.principal)||value.subject!==after.principal.principalId||value.scope?.tenantId!==after.principal.tenantId||value.scope?.securityDomain!==after.principal.securityDomain||value.kind!=='knowledge'||value.identity!==identity||value.revision!==revision||value.digest!==digest||!Array.isArray(value.dependencies?.incoming))throw Error();if(live){setResult({key,rows:value.dependencies.incoming});setFailed(false)}};
  void read().catch(()=>{if(live){setResult(null);setFailed(true)}});window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[identity,revision,digest,key,attempt]);
 const current=result?.key===key?result:null;
 return <>{failed&&<p role="status">引用信息暂不可读，不能据此判断没有引用。<button onClick={()=>setAttempt(n=>n+1)}>重新核对引用</button></p>}<SelectedResourceUpgrade resource={resource} candidates={current?.rows??[]} candidatesReady={!!current} blocked={blocked} onUpgradeLock={onLock} onUpgradeRefresh={onRefresh}/></>;
}
