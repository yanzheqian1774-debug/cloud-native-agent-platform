import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey,readTeam} from '../api/digitalEmployees';
import type {CurrentWork} from '../problems/currentWorkReadback';
import {verifyTeam} from './teamState';
export function WorkTeamContext({work}:{work:CurrentWork}){
 const [params]=useSearchParams(),team=params.get('teamRef'),revision=params.get('teamRevision'),digest=params.get('teamDigest');
 const run=work.execution.workflowRunId,preparation=work.execution.digest,problem=work.problem.business_problem_id,problemRevision=work.problem.revision_id,problemDigest=work.problem.digest,key=JSON.stringify([team,revision,digest,run,preparation,problem,problemRevision,problemDigest]);
 const [result,setResult]=useState<{key:string;title:string}|null>(null);
 useEffect(()=>{let live=true;const controller=new AbortController(),withdraw=()=>{live=false;controller.abort();setResult(null)};
 if(import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==='true'&&run&&team&&team.length<=200&&revision&&revision.length<=200&&digest&&/^[a-f0-9]{64}$/.test(digest))void(async()=>{const before=await getWorkbenchSession(controller.signal),value=await readTeam(team,revision,controller.signal);await verifyTeam(before,value,team,revision,digest);if(!value.revision.work_links?.some(w=>w.workflow_run_id===run&&w.preparation_digest===preparation&&w.business_problem_id===problem&&w.problem_revision_id===problemRevision&&w.problem_digest===problemDigest))return;const after=await getWorkbenchSession(controller.signal);if(live&&workbenchPrincipalKey(before)===workbenchPrincipalKey(after))setResult({key,title:value.revision.title})})().catch(()=>{if(live)setResult(null)});
 window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[team,revision,digest,key,run,preparation,problem,problemRevision,problemDigest]);
 return result?.key===key?<aside className="f3-work-notice"><p>关联团队：{result.title}</p><Link to={'/teams?'+new URLSearchParams({team:team!,revision:revision!})}>返回原团队</Link></aside>:null;
}
