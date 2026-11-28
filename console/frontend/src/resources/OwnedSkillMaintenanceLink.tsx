import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {ownedSkillCandidate,readOwnedSkillAccess,skillMaintenanceHref} from './ownedSkillAccess';
export function OwnedSkillMaintenanceLink({identity,subject,tenantId,securityDomain}:{identity:string;subject:string;tenantId:string;securityDomain:string}){
 const [params]=useSearchParams(),[allowed,setAllowed]=useState(false);
 useEffect(()=>{
  let live=true,epoch=0;let controller:AbortController|null=null;
  const read=()=>{const generation=++epoch;controller?.abort();controller=new AbortController();setAllowed(false);void readOwnedSkillAccess(controller.signal).then(value=>{if(live&&generation===epoch&&value.subject===subject&&value.scope.tenantId===tenantId&&value.scope.securityDomain===securityDomain)setAllowed((Array.isArray(value.accessCandidates)?value.accessCandidates:[]).some(x=>ownedSkillCandidate(x)&&x.identity===identity))}).catch(()=>{if(live&&generation===epoch)setAllowed(false)})};
  const withdraw=()=>{epoch++;controller?.abort();setAllowed(false)};
  read();window.addEventListener('focus',read);window.addEventListener('workbench-session-expired',withdraw);
  return()=>{live=false;epoch++;controller?.abort();window.removeEventListener('focus',read);window.removeEventListener('workbench-session-expired',withdraw)};
 },[identity,subject,tenantId,securityDomain]);
 if(!allowed)return null;
 return <div className="resource-detail-return"><Link className="f3-directory-secondary" to={skillMaintenanceHref(identity,params.toString())}>核对维护资格</Link><small>进入当前定义核对；本页历史版本与已有引用保持不变。</small></div>;
}
