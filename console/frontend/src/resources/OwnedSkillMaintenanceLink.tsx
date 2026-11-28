import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {ownedResourceCandidate,readOwnedResourceAccess,resourceMaintenanceHref,type OwnedResourceKind} from './ownedSkillAccess';
type MaintenanceLinkProps={identity:string;subject:string;tenantId:string;securityDomain:string};
export function OwnedResourceMaintenanceLink({kind,identity,subject,tenantId,securityDomain}:MaintenanceLinkProps&{kind:OwnedResourceKind}){
 const [params]=useSearchParams(),[allowed,setAllowed]=useState(false);
 useEffect(()=>{
  let live=true,epoch=0;let controller:AbortController|null=null;
  const read=()=>{const generation=++epoch;controller?.abort();controller=new AbortController();setAllowed(false);void readOwnedResourceAccess(kind,controller.signal).then(value=>{if(live&&generation===epoch&&value.subject===subject&&value.scope.tenantId===tenantId&&value.scope.securityDomain===securityDomain)setAllowed((Array.isArray(value.accessCandidates)?value.accessCandidates:[]).some(x=>ownedResourceCandidate(x)&&x.kind===kind&&x.identity===identity))}).catch(()=>{if(live&&generation===epoch)setAllowed(false)})};
  const withdraw=()=>{epoch++;controller?.abort();setAllowed(false)};
  read();window.addEventListener('focus',read);window.addEventListener('workbench-session-expired',withdraw);
  return()=>{live=false;epoch++;controller?.abort();window.removeEventListener('focus',read);window.removeEventListener('workbench-session-expired',withdraw)};
 },[kind,identity,subject,tenantId,securityDomain]);
 if(!allowed)return null;
 return <div className="resource-detail-return"><Link className="f3-directory-secondary" to={resourceMaintenanceHref(kind,identity,params.toString())}>核对维护资格</Link><small>进入当前定义核对；本页历史版本与已有引用保持不变。</small></div>;
}

export function OwnedSkillMaintenanceLink(props:MaintenanceLinkProps){return <OwnedResourceMaintenanceLink {...props} kind="skill"/>}
