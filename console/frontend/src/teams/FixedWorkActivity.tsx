import {useEffect,useState} from 'react';
import {Link} from 'react-router-dom';
import {FixedWorkReadAccess} from './FixedWorkReadAccess';
import {getWorkbenchSession,readFixedWorkActivity,workbenchPrincipalKey,type FixedWorkActivityResult,type WorkbenchSession} from '../api/digitalEmployees';
import type {FixedItem,FixedTeam} from '../api/fixedWorkDrafts';

const states:Record<string,string>={PENDING:'等待执行',RUNNING:'正在执行',SUCCEEDED:'执行已完成',FAILED:'执行失败，需核查',CANCELLED:'已取消',CANCEL_REQUESTED:'正在核对取消结果',RECOVERY_REQUIRED:'结果待核实'};
export function FixedWorkActivity({team,item,session}:{team:FixedTeam;item:FixedItem;session:WorkbenchSession}){
 const [data,setData]=useState<FixedWorkActivityResult|null>(null),[error,setError]=useState(''),[revision,setRevision]=useState(0);
 useEffect(()=>{let live=true;const abort=new AbortController();
 const verify=async()=>{if(workbenchPrincipalKey(await getWorkbenchSession(abort.signal))!==workbenchPrincipalKey(session))throw Error('登录身份已变化，请重新读取。')};
 const withdraw=()=>{live=false;abort.abort();setData(null);setError('登录已失效，请重新登录后读取。')};
 window.addEventListener('workbench-session-expired',withdraw);
 void(async()=>{await verify();const value=await readFixedWorkActivity(team,item.draft.workId,item.draft.revisionId,abort.signal);await verify();if(value.workId!==item.draft.workId||value.revisionId!==item.draft.revisionId||value.workDigest!==item.digest||value.windowLimit!==50||value.automaticTriggerStatus!=='NOT_OBSERVED'||!Array.isArray(value.items)||value.items.length>50||new Set(value.items.map(x=>x.eventId)).size!==value.items.length||value.items.some(x=>!x.eventId||!x.runId||!/^[a-f0-9]{64}$/.test(x.preparationDigest)||!Number.isInteger(x.aggregateVersion)||x.aggregateVersion<1||!Number.isFinite(Date.parse(x.recordedAt))))throw Error('执行记录与当前工作版本尚未核对一致。');if(live)setData(value)})().catch(()=>{if(live){setData(null);setError('执行记录暂未读取成功；已保存的安排不受影响。')}});
 return()=>{live=false;abort.abort();window.removeEventListener('workbench-session-expired',withdraw)};
 },[team,item,session,revision]);
 return <section className="f3-team-card" aria-label="固定工作执行记录"><div className="f3-team-actions"><h2>执行活动</h2><button onClick={()=>{setData(null);setError('');setRevision(v=>v+1)}}>刷新记录</button></div>{import.meta.env.VITE_FIXED_WORK_ACTIVITY_READ_ENABLED==='true'&&<FixedWorkReadAccess key={workbenchPrincipalKey(session)+item.digest} team={team} item={item} session={session} onReady={()=>{setData(null);setError('');setRevision(v=>v+1)}}/>}<p>展示最近记录中当前可读的执行。保存安排不代表自动运行已启用。</p>{error?<p role="alert">{error}</p>:!data?<p role="status">正在读取执行记录…</p>:data.items.length===0?<p>当前未读到可查看的执行记录。</p>:data.items.map(row=><article className="f3-team-work-row" key={row.eventId}><div><h3>{states[row.state]??'状态待核实'}</h3><p>{new Date(row.recordedAt).toLocaleString('zh-CN')}</p>{row.state==='SUCCEEDED'&&<p>业务结论请以任务中的结果和依据为准。</p>}</div><Link to={'/tasks?'+new URLSearchParams({work:row.preparationDigest,teamRef:team.teamId,teamRevision:team.revisionId,teamDigest:team.digest,fixedWorkRef:item.draft.workId,fixedWorkRevision:item.draft.revisionId,fixedWorkDigest:item.digest})}>查看任务与结果</Link></article>)}</section>;
}
