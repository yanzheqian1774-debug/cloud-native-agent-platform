import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {DigitalEmployeeRequestError,getWorkbenchSession,previewFixedWorkInstruction,workbenchPrincipalKey,type WorkbenchSession} from '../api/digitalEmployees';
import type {FixedItem,FixedTeam,FixedTrigger} from '../api/fixedWorkDrafts';

export function FixedWorkNaturalPreview({team,session,title,instruction,prior,busy,onPropose}:{team:FixedTeam;session:WorkbenchSession;title:string;instruction:string;prior:FixedItem|null;busy:boolean;onPropose:(value:{title:string;trigger:FixedTrigger})=>void}){
 const [pending,setPending]=useState(false),[issues,setIssues]=useState<string[]>([]),[error,setError]=useState(''),[detail,setDetail]=useState('');
 const identity=JSON.stringify([team,title,instruction,prior?.digest,workbenchPrincipalKey(session)]),latest=useRef(identity),flight=useRef<AbortController|null>(null),epoch=useRef(0);
 useLayoutEffect(()=>{latest.current=identity},[identity]);
 useEffect(()=>{const invalidate=()=>{epoch.current++;flight.current?.abort()};const expire=()=>{invalidate();setPending(false);setIssues([]);setError('登录状态已变化，原输入仍保留。')};window.addEventListener('workbench-session-expired',expire);return()=>{invalidate();window.removeEventListener('workbench-session-expired',expire)}},[]);
 async function preview(){if(pending||busy||!instruction.trim())return;const c=new AbortController();flight.current=c;const token=epoch.current,key=identity,principal=workbenchPrincipalKey(session);setPending(true);setError('');setDetail('');setIssues([]);
  try{const previous=prior?{workId:prior.draft.workId,revisionId:prior.draft.revisionId,digest:prior.digest}:null;const result=await previewFixedWorkInstruction(team,{instruction,...(title.trim()?{title}:{}),previous},principal,c.signal);
   if(workbenchPrincipalKey(await getWorkbenchSession(c.signal))!==principal)throw Error('登录身份已变化，请重新读取配置。');
   if(result.team?.teamId!==team.teamId||result.team.revisionId!==team.revisionId||result.team.digest!==team.digest||result.instruction!==instruction||JSON.stringify(result.previous)!==JSON.stringify(previous)||result.modelInvoked!==false||result.executionEnabled!==false||result.authorityGranted!==false||result.validation!=='CONFIGURATION_STRUCTURE_ONLY'||!Array.isArray(result.issues)||result.issues.some(x=>typeof x!=='string'))throw Error('本次预览尚未核实，原输入仍保留。');
   if(token!==epoch.current||c.signal.aborted||latest.current!==key)return;
   setIssues(result.issues);if(result.issues.length)return;
   const t=result.candidateTrigger;if(!t||!result.proposedTitle?.trim()||result.proposedTitle.length>120||!['SCHEDULE','EVENT'].includes(t.kind))throw Error('安排字段尚未完整，原输入仍保留。');
   if(t.kind==='SCHEDULE'){if(!t.timezone||!t.localTime||!/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(t.localTime)||!['DAILY','WEEKDAY'].includes(t.cadence??'')||t.eventDescription!==null)throw Error('定时安排尚未完整。');new Intl.DateTimeFormat('zh-CN',{timeZone:t.timezone}).format()}else if(!t.eventDescription?.trim()||t.timezone!==null||t.localTime!==null||t.cadence!==null)throw Error('事件条件尚未完整。');
   onPropose({title:result.proposedTitle,trigger:t});setIssues(['已提取明确的安排字段。请核对下方预览与差异，再确认保存；没有开始运行。']);
  }catch(e){if(token===epoch.current&&!c.signal.aborted&&latest.current===key){setError('暂未完成安排核对，原输入仍保留。');setDetail(e instanceof DigitalEmployeeRequestError?e.reasonCode:e instanceof Error?e.message:'')}}finally{if(token===epoch.current&&!c.signal.aborted)setPending(false)}
 }
 return <section aria-label="从说明核对安排"><p>从说明中提取明确的时间、频率或事件。不能确定的内容会提示核对，不会自动补入默认安排。</p><button className="px-primary-button" disabled={busy||pending||!instruction.trim()} onClick={()=>void preview()}>{pending?'正在核对安排…':'从说明生成安排预览'}</button>{issues.map((issue,i)=><p role="status" key={i}>{issue}</p>)}{error&&<p role="alert">{error}</p>}{detail&&<details><summary>技术详情</summary><code>{detail}</code></details>}</section>;
}
