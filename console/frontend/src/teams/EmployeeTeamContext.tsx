import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey,readTeam,type EmployeeDefinition} from '../api/digitalEmployees';
import {verifyTeam} from './teamState';
export function EmployeeTeamContext({item}:{item:EmployeeDefinition}){
 const [params]=useSearchParams(),team=params.get('teamRef'),revision=params.get('teamRevision'),digest=params.get('teamDigest'),key=JSON.stringify([params.toString(),team,revision,digest,item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]);
 const [result,setResult]=useState<{key:string;title:string;owner:string;mine:boolean}|null>(null);
 useEffect(()=>{let live=true;const controller=new AbortController();const withdraw=()=>{live=false;controller.abort();setResult(null)};
 if(['teamRef','teamRevision','teamDigest','teamDirectoryQuery'].every(name=>params.getAll(name).length<=1)&&(params.get('teamDirectoryQuery')?.length??0)<=200&&import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==='true'&&team&&team.length<=200&&revision&&revision.length<=200&&digest&&/^[a-f0-9]{64}$/.test(digest))void(async()=>{const before=await getWorkbenchSession(controller.signal),value=await readTeam(team,revision,controller.signal);await verifyTeam(before,value,team,revision,digest);const after=await getWorkbenchSession(controller.signal);if(workbenchPrincipalKey(before)!==workbenchPrincipalKey(after)||!value.revision.members.some(m=>m.employee_definition_id===item.employeeDefinitionId&&m.employee_revision_id===item.employeeDefinitionRevisionId&&m.employee_digest===item.employeeDefinitionDigest))return;if(live)setResult({key,title:value.revision.title,owner:value.revision.owner_id,mine:value.revision.owner_id===after.principal.principalId})})().catch(()=>{if(live)setResult(null)});
 window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[params,key,team,revision,digest,item.employeeDefinitionId,item.employeeDefinitionRevisionId,item.employeeDefinitionDigest]);
 return result?.key===key?<div className="employee-team-context"><p>来自团队：{result.title} · 团队负责人：{result.owner}</p><Link to={'/teams?'+new URLSearchParams({team:team!,revision:revision!,...(params.get('teamDirectoryQuery')?{q:params.get('teamDirectoryQuery')!}:{})})}>返回原团队</Link></div>:<p className="employee-team-context">团队归属与维护人：暂未提供</p>;
}
