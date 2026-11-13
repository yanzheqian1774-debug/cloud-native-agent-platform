import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getEmployeeDefinition,getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import type {DirectoryItem} from '../api/resourceDirectory';
import {employeeReturnContext} from './resourceJourneyLinks';

export function EmployeeResourceReturn({item}:{item:DirectoryItem}){
 const [params]=useSearchParams(),[href,setHref]=useState<{key:string;value:string}|null>(null);const key=JSON.stringify([params.toString(),item.kind,item.identity,item.revisionId,item.digest]);
 useEffect(()=>{let live=true;const abort=new AbortController();const withdraw=()=>{live=false;setHref(null)};void(async()=>{
  const context=employeeReturnContext(params);if(!context)return;const before=await getWorkbenchSession(abort.signal),employee=await getEmployeeDefinition(context.id,context.revision,abort.signal),after=await getWorkbenchSession(abort.signal);
  if(workbenchPrincipalKey(before)!==workbenchPrincipalKey(after)||employee.employeeDefinitionId!==context.id||employee.employeeDefinitionRevisionId!==context.revision||employee.employeeDefinitionDigest!==context.digest||!employee.members.some(m=>m.kind.toLowerCase()===item.kind&&m.resourceId===item.identity&&m.revisionId===item.revisionId&&m.digest.replace(/^sha256:/,'')===item.digest.replace(/^sha256:/,'')))return;
  const query=new URLSearchParams({employeeDefinitionId:context.id,employeeDefinitionRevisionId:context.revision,employeeDefinitionDigest:context.digest,section:context.section,detail:'1'});if(context.view)query.set('employeeView',context.view);if(context.back)query.set('resourceBack',context.back);if(context.capabilityBack)query.set('capabilityReturn',context.capabilityBack);if(context.team)for(const [name,value] of Object.entries(context.team))query.set(name,value);if(live)setHref({key,value:'/employees?'+query});
 })().catch(()=>{if(live)setHref(null)});window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;abort.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,params,item]);
 return href?.key===key?<Link to={href.value}>返回引用员工</Link>:null;
}
