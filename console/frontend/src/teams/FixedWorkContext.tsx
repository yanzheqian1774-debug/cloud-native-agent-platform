import {useEffect,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {getWorkbenchSession,readFixedWorkDraft,readFixedWorkActivity,workbenchPrincipalKey} from '../api/digitalEmployees';
import {verifyFixedItem} from '../api/fixedWorkDrafts';
import type {CurrentWork} from '../problems/currentWorkReadback';
const names=['teamRef','teamRevision','teamDigest','fixedWorkRef','fixedWorkRevision','fixedWorkDigest'] as const;
export function FixedWorkContext({work}:{work:CurrentWork}){
 const [params]=useSearchParams(),[verified,setVerified]=useState<{key:string;title:string;href:string}|null>(null);
 const values=names.map(k=>params.get(k)??''),key=JSON.stringify([values,work.execution.workflowRunId,work.execution.digest]),valid=import.meta.env.VITE_TEAM_DEFINITIONS_ENABLED==='true'&&names.every(k=>params.getAll(k).length===1)&&values.every(v=>v.length>0&&v.length<=200)&&[values[2],values[5]].every(v=>/^[a-f0-9]{64}$/.test(v));
 useEffect(()=>{let live=true;const abort=new AbortController(),withdraw=()=>{live=false;abort.abort();setVerified(null)};if(!valid)return;
 const [teamId,revisionId,digest,workId,workRevision,workDigest]=JSON.parse(key)[0] as string[];
 const team={teamId,revisionId,digest};
 void(async()=>{const before=await getWorkbenchSession(abort.signal),item=await readFixedWorkDraft(team,workId,workRevision,abort.signal);await verifyFixedItem(item,team);if(item.digest!==workDigest)throw Error('binding');const activity=await readFixedWorkActivity(team,workId,workRevision,abort.signal);if(activity.workDigest!==item.digest||activity.workId!==workId||activity.revisionId!==workRevision||!activity.items.some(r=>r.runId===work.execution.workflowRunId&&r.preparationDigest===work.execution.digest))return;const after=await getWorkbenchSession(abort.signal);if(live&&workbenchPrincipalKey(before)===workbenchPrincipalKey(after))setVerified({key,title:item.draft.title,href:'/teams?'+new URLSearchParams({view:'routines',fixedTeam:teamId,fixedRevision:revisionId,fixedDigest:digest,openWork:workId,openRevision:workRevision,openDigest:workDigest})})})().catch(()=>{if(live)setVerified(null)});
 window.addEventListener('workbench-session-expired',withdraw);return()=>{live=false;abort.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[key,valid,work.execution.workflowRunId,work.execution.digest]);
 return valid&&verified?.key===key?<aside className="f3-work-notice"><p>固定工作：{verified.title}</p><Link to={verified.href}>返回原固定工作</Link></aside>:null;
}
