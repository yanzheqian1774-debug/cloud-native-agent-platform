import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,workbenchPrincipalKey,readTeam,readTeamWork} from '../api/digitalEmployees';
import {verifyTeam} from './teamState';

/** URL coordinates are hints; both the team and its original work must be readable. */
export function ConversationTeamContext({conversation,preparation}:{conversation:string;preparation:string}){
 const [params]=useSearchParams(),team=params.get('teamRef'),revision=params.get('teamRevision'),digest=params.get('teamDigest');
 const key=JSON.stringify([team,revision,digest,conversation,preparation]);
 const [result,setResult]=useState<{key:string;title:string}|null>(null);
 useEffect(()=>{let live=true;const controller=new AbortController(),withdraw=()=>{live=false;controller.abort();setResult(null)};
 if(import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==='true'&&team&&team.length<=200&&revision&&revision.length<=200&&digest&&/^[a-f0-9]{64}$/.test(digest))void(async()=>{
  const before=await getWorkbenchSession(controller.signal),value=await readTeam(team,revision,controller.signal);
  await verifyTeam(before,value,team,revision,digest);
  const work=await readTeamWork(team,revision,controller.signal);
  if(work.teamId!==team||work.revisionId!==revision||work.teamDigest!==digest)return;
  const matches=work.items.filter(w=>w.preparationDigest===preparation&&w.originVerified&&w.originConversationId===conversation&&value.revision.work_links?.some(link=>link.workflow_run_id===w.workflowRunId&&link.preparation_digest===w.preparationDigest&&link.business_problem_id===w.problemId&&link.problem_revision_id===w.problemRevisionId&&link.problem_digest===w.problemDigest));
  if(matches.length!==1)return;
  const after=await getWorkbenchSession(controller.signal);
  if(live&&workbenchPrincipalKey(before)===workbenchPrincipalKey(after))setResult({key,title:value.revision.title});
 })().catch(()=>{if(live)setResult(null)});
 window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;controller.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[team,revision,digest,key,conversation,preparation]);
 return result?.key===key?<aside className="conversation-team-source" aria-label="来源团队"><span>来源团队：{result.title}</span><Link to={'/teams?'+new URLSearchParams({team:team!,revision:revision!})}>返回原团队</Link></aside>:null;
}
