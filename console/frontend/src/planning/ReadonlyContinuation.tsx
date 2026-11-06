import {useEffect,useRef,useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {readWorkbenchSession} from '../api/businessWorkspace';
import {useAutomaticReadback} from '../journey/useAutomaticReadback';
import {continuationQuery} from '../api/conversationActions';
import {linkExecution} from './executionConversationLink';
import * as api from './api';

export function ReadonlyContinuation({id,approved,allowStart,expectedScope}:{id:string;approved:api.Confirmation;allowStart:boolean;expectedScope:string}){
 const navigate=useNavigate(),epoch=useRef(0),flight=useRef(false);
 const identity=JSON.stringify([id,approved.plan.version,approved.digest]);
 const [linkIssue,setLinkIssue]=useState(''),[destination,setDestination]=useState('');
 const [error,setError]=useState(''),[pending,setPending]=useState(true),[observed,setObserved]=useState(false);
 const subject=useRef<{id:string;scope:string}|null>(null),readUntil=useRef(0),submitted=useRef(false),storageKey=useRef('');
 async function accept(value:api.ReadonlyContinuation,token:number){
  const current=await readWorkbenchSession(),saved=subject.current,r=value.receipt;
  if(!saved||current.principal.principalId!==saved.id||JSON.stringify([current.principal.tenantId,current.principal.securityDomain])!==saved.scope)throw new Error('READONLY_CONTINUATION_IDENTITY_CHANGED');
  if(r.subject!==saved.id||r.sourcePlanId!==id||r.sourcePlanVersion!==approved.plan.version||r.sourcePlanDigest!==approved.digest||r.preparationDigest!==value.execution.digest||value.execution.preparation.semantics.target.problem.resource_id!==approved.plan.semantics.target.problem.resource_id)throw new Error('READONLY_CONTINUATION_BINDING_MISMATCH');
  if(token!==epoch.current)return;
  setPending(false);setError('');
  const next=`/work?problem=${encodeURIComponent(approved.plan.semantics.target.problem.resource_id)}&execution=${encodeURIComponent(r.preparationDigest)}${continuationQuery()}`;
  const conversation=new URLSearchParams(window.location.search).get('returnConversation');
  if(conversation){try{await linkExecution(conversation,approved.plan.semantics.target.problem,r.preparationDigest,JSON.stringify(current.principal),()=>token===epoch.current)}catch(e){if(token!==epoch.current)return;if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(current.principal)||e instanceof Error&&/IDENTITY_CHANGED/.test(e.message)){setDestination('');setLinkIssue('');throw Error('READONLY_CONTINUATION_IDENTITY_CHANGED',{cause:e})}if(token===epoch.current){setDestination(next);setLinkIssue(e instanceof Error?e.message:'EXECUTION_LINK_NOT_VERIFIED')}return;}}
  if(token!==epoch.current)return;
  if(JSON.stringify((await readWorkbenchSession()).principal)!==JSON.stringify(current.principal))throw Error('READONLY_CONTINUATION_IDENTITY_CHANGED');
  if(token===epoch.current){if(storageKey.current)sessionStorage.removeItem(storageKey.current);navigate(next);}
 }
 useEffect(()=>{const token=++epoch.current;let active=true;
  async function begin(){try{
   const session=await readWorkbenchSession();if(!active||token!==epoch.current)return;const p=session.principal;if(JSON.stringify(p)!==expectedScope)throw Error('READONLY_CONTINUATION_IDENTITY_CHANGED');subject.current={id:p.principalId,scope:JSON.stringify([p.tenantId,p.securityDomain])};
   const key='readonly-continuation:'+JSON.stringify([p.principalId,p.tenantId,p.securityDomain,identity]);
   // A started/uncertain execution command is recovered only through GET. The
   // fixed backend Plan identity also prevents session or key changes minting Runs.
   storageKey.current=key;const saved=sessionStorage.getItem(key);if(!saved&&!allowStart){setPending(false);return}readUntil.current=(saved?Number(saved):Date.now())+90000;submitted.current=Boolean(saved)||allowStart;setObserved(submitted.current);let result:api.ReadonlyContinuation;
   if(saved||!allowStart)result=await api.readReadonlyContinuation(id,approved.plan.version);
   else{sessionStorage.setItem(key,String(Date.now()));result=await api.continueReadonlyWork(id,approved.plan.version,session.csrfToken)}
   if(active)await accept(result,token);
  }catch(e){if(active&&token===epoch.current){const status=e&&typeof e==='object'&&'status'in e?e.status:undefined;if(!allowStart&&status===404&&!submitted.current){setError('');setPending(false);return}setError(e instanceof Error?e.message:'READONLY_CONTINUATION_UNAVAILABLE');setPending((![401,403,409,422].includes(Number(status))&&(status!==404||Date.now()<readUntil.current))&&!(e instanceof Error&&/IDENTITY_CHANGED|BINDING_MISMATCH/.test(e.message)))}}}
  void begin();return()=>{active=false;if(epoch.current===token)epoch.current=token+1};
 // Immutable Plan identity scopes one command; props cannot resubmit it.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity,allowStart,expectedScope]);
 useAutomaticReadback({identity,enabled:pending&&Boolean(error),read:async()=>{if(flight.current)return true;flight.current=true;const token=epoch.current;try{await accept(await api.readReadonlyContinuation(id,approved.plan.version),token);return false}catch(e){const status=e&&typeof e==='object'&&'status'in e?e.status:undefined;if([401,403,409,422].includes(Number(status))||(status===404&&Date.now()>=readUntil.current)||e instanceof Error&&/IDENTITY_CHANGED|BINDING_MISMATCH/.test(e.message)){if(token===epoch.current)setPending(false);return false}throw e}finally{flight.current=false}}});
 if(linkIssue)return <section className="planning-card" aria-label="执行已接续，会话关联待核实"><h2>原执行已接续，会话关联尚未核实</h2><p>执行回执已读回。当前只需核对会话关联，不会再次启动任务。</p><Link to={destination}>继续查看原执行与成果</Link><details><summary>查看关联依据</summary><code>{linkIssue}</code></details></section>;
 if(!allowStart&&!observed)return null;
 return <section className="planning-card" aria-label="接续执行准备" aria-live="polite"><h2>资源已备齐，正在接续办理</h2><p>{pending?(allowStart?'平台正在装配实例、核验独立执行权限，并接续只读任务；执行与标准评价将自动呈现。':'正在核对上次接续记录与执行状态，不会重复派发任务。'):'本次接续尚待核查，原请求与已完成准备均保留。'}</p>{error&&<details><summary>查看核查依据</summary><code>{error}</code><p>页面只读取原请求状态，不会自动重试未知执行。</p></details>}</section>;
}
