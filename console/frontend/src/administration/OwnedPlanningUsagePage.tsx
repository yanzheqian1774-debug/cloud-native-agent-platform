import {useEffect,useRef,useState} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';
import type {PrivateConversation} from '../api/privateConversation';
import {PageHeader,StatusBadge} from '../components/WorkspacePrimitives';
import './ExecutionOperationsPage.css';

type Receipt={schemaVersion:string;reservationId:string;settlement:{status:'ESTIMATE_SETTLED'|'PENDING_RECONCILIATION';reservation_retained:boolean;estimate_microusd?:number;input_tokens?:number;output_tokens?:number};providerInvoice:'NOT_VERIFIED'};
type Item={invocation:string;conversation:string;title:string;receipt:Receipt};
type Snapshot={items:Item[];limited:boolean;readAt:string};
class AccessChanged extends Error{}
const actorKey=(v:{principal:unknown})=>JSON.stringify(v.principal);
const integer=(v:unknown):v is number=>typeof v==='number'&&Number.isSafeInteger(v)&&v>=0;
function validate(value:Receipt){
 const s=value?.settlement;
 if(value?.schemaVersion!=='provider-usage-read.v1'||typeof value.reservationId!=='string'||!value.reservationId||value.providerInvoice!=='NOT_VERIFIED'||!s)throw Error('原调用计量格式未核实。');
 if(s.status==='ESTIMATE_SETTLED'){
  if(s.reservation_retained!==false||!integer(s.estimate_microusd)||!integer(s.input_tokens)||!integer(s.output_tokens))throw Error('本地估算结算记录不完整。');
 }else if(s.status!=='PENDING_RECONCILIATION'||s.reservation_retained!==true||s.estimate_microusd!==undefined)throw Error('原预留状态未核实。');
 return value;
}
function usd(micro:bigint){return 'USD '+(micro/1000000n)+'.'+(micro%1000000n).toString().padStart(6,'0')}
export function OwnedPlanningUsagePage(){
 const [params,setParams]=useSearchParams(),[snapshot,setSnapshot]=useState<Snapshot|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[revision,setRevision]=useState(0);
 const epoch=useRef(0);
 const invalidate=()=>{epoch.current++};
 useEffect(()=>{
  const token=++epoch.current,abort=new AbortController();let live=true,timer:ReturnType<typeof setTimeout>|undefined;
  const withdraw=(message:string)=>{epoch.current++;abort.abort();setSnapshot(null);setBusy(false);setError(message)};
  const expired=()=>withdraw('当前登录已失效，已撤下原计量记录。');
  const focus=()=>{withdraw('正在重新核对当前读取范围。');setRevision(n=>n+1)};
  async function load(){
   setBusy(true);setSnapshot(null);setError('');
   let until=Date.now()+30000;
   async function session(){const v=await readWorkbenchSession(abort.signal);until=Math.min(until,Date.parse(v.session.expiresAt),Date.parse(v.session.idleExpiresAt));if(!Number.isFinite(until)||until<=Date.now())throw new AccessChanged('登录或读取快照已到期。');return actorKey(v)}
   try{
    const actor=await session();
    async function read<T>(path:string):Promise<T>{
     if(await session()!==actor)throw new AccessChanged('当前登录身份已变化。');
     const r=await fetch('/api/workbench/v1/'+path,{credentials:'same-origin',signal:abort.signal,headers:{Accept:'application/json'}}),body=await r.json().catch(()=>null);
     if(r.status===401){window.dispatchEvent(new Event('workbench-session-expired'));throw new AccessChanged('当前登录已失效。')}
     if(!r.ok)throw new WorkbenchRequestError(body?.reasonCode??'USAGE_NOT_READABLE',r.status);
     if(await session()!==actor)throw new AccessChanged('当前登录身份已变化。');
     if(!body||!Object.hasOwn(body,'result'))throw Error('读取结果未核实。');return body.result as T;
    }
    const index=await read<{items:{conversation_id:string}[]}>('conversations');
    if(!Array.isArray(index.items))throw Error('会话列表未核实。');
    let limited=index.items.length>20;
    const refs=new Map<string,{conversation:string;title:string}>();
    for(const entry of index.items.slice(0,20)){
     try{
      const c=await read<PrivateConversation>('conversations/'+encodeURIComponent(entry.conversation_id));
      if(c.conversation.conversation_id!==entry.conversation_id||typeof c.conversation.title!=='string'||!Array.isArray(c.messages))throw Error('会话身份未核实。');
      for(const message of c.messages){
       const facts=message.facts,source=facts?.source;
       if(facts?.readable===false){limited=true;continue}
       if(source?.kind!=='PLANNING')continue;
       if(typeof source.invocationId!=='string'||!source.invocationId||source.invocationId.length>256){limited=true;continue}
       if(refs.size>=100&&!refs.has(source.invocationId)){limited=true;continue}
       if(!refs.has(source.invocationId))refs.set(source.invocationId,{conversation:entry.conversation_id,title:c.conversation.title});
      }
     }catch(e){if(e instanceof AccessChanged||abort.signal.aborted)throw e;limited=true}
    }
    const items:Item[]=[];
    for(const [invocation,ref] of refs){try{const receipt=validate(await read<Receipt>('planning-v2/invocations/'+encodeURIComponent(invocation)+'/usage'));items.push({invocation,...ref,receipt})}catch(e){if(e instanceof AccessChanged||abort.signal.aborted)throw e;limited=true}}
    if(await session()!==actor)throw new AccessChanged('当前登录身份已变化。');
    if(live&&token===epoch.current){setSnapshot({items,limited,readAt:new Date().toISOString()});timer=setTimeout(()=>withdraw('本次读取快照已到期，请重新读取当前计量记录。'),Math.max(0,until-Date.now()))}
   }catch(e){if(live&&token===epoch.current){setSnapshot(null);setError(e instanceof Error?e.message:'计量记录尚未读回。')}}
   finally{if(live&&token===epoch.current)setBusy(false)}
  }
  void load();window.addEventListener('workbench-session-expired',expired);window.addEventListener('focus',focus);
  return()=>{live=false;invalidate();abort.abort();clearTimeout(timer);window.removeEventListener('workbench-session-expired',expired);window.removeEventListener('focus',focus)};
 },[revision]);
 const all=snapshot?.items??[],settled=all.filter(i=>i.receipt.settlement.status==='ESTIMATE_SETTLED'),pending=all.filter(i=>i.receipt.settlement.status==='PENDING_RECONCILIATION');
 const query=params.get('q')??'',status=params.get('state')??'ALL',selected=all.find(i=>i.invocation===params.get('invocation'));
 const visible=all.filter(i=>i.title.toLowerCase().includes(query.toLowerCase())&&(status==='ALL'||i.receipt.settlement.status===status));
 const hasKnown=!!snapshot&&(!snapshot.limited||all.length>0),known=settled.reduce((n,i)=>n+BigInt(i.receipt.settlement.estimate_microusd!),0n);
 function update(k:string,v:string){setParams(p=>{const n=new URLSearchParams(p);if(v)n.set(k,v);else n.delete(k);return n})}
 return <main className="px-page execution-operations"><PageHeader eyebrow="运营与治理" title="费用与使用量" description="核对本人会话关联的原规划调用计量与本地估算结算，返回原工作继续查看。" actions={<><button disabled={busy} onClick={()=>{setSnapshot(null);setRevision(n=>n+1)}}>重新读取计量记录</button><Link to="/work">返回会话</Link></>}/>
 <section className="operations-scope"><p>范围：最多20段本人会话、100个去重后的规划调用；只读取已有记录，不发起调用或结算。本地估算不是供应商账单，未结算预留和不可读记录不计作零费用。尚未覆盖理解调用、全部执行用量及组织预算。</p><p>快照最多保留30秒，登录失效或重新读取时撤下旧数值。</p>{snapshot&&<small>本次读取：{new Date(snapshot.readAt).toLocaleString('zh-CN')}</small>}{snapshot?.limited&&<p role="status">部分关联不可读、格式未核实或达到读取上限；以下不是完整费用总额。</p>}{busy&&<p role="status">正在核对原调用计量…</p>}{error&&<p role="alert">{error}</p>}</section>
 <section className="operations-metrics" aria-label="已读规划计量统计">{[['可读原调用',hasKnown?all.length:'—'],['本地估算结算',hasKnown?settled.length:'—'],['保留原预留',hasKnown?pending.length:'—'],['已读结算估算小计',settled.length?usd(known):'—']].map(([name,value])=><article key={name}><span>{name}</span><strong>{value}</strong></article>)}</section>
 <section className="operations-content"><div className="operations-filters"><label>查找会话<input aria-label="查找会话" value={query} maxLength={200} onChange={e=>update('q',e.target.value)}/></label><label>计量状态<select aria-label="计量状态" value={status} onChange={e=>update('state',e.target.value)}><option value="ALL">全部可读状态</option><option value="ESTIMATE_SETTLED">本地估算已结算</option><option value="PENDING_RECONCILIATION">原预留保留</option></select></label></div>
 {snapshot&&(visible.length?<div className="operations-table"><table><caption>当前已核实的原规划调用</caption><thead><tr><th>原会话</th><th>计量状态</th><th>本地估算</th><th>查看与返回</th></tr></thead><tbody>{visible.map(i=><tr key={i.invocation}><td>{i.title}</td><td>{i.receipt.settlement.status==='ESTIMATE_SETTLED'?'本地估算已结算':'原预留保留'}</td><td>{i.receipt.settlement.status==='ESTIMATE_SETTLED'?usd(BigInt(i.receipt.settlement.estimate_microusd!)):'待核实，不能认定零费用'}</td><td><button onClick={()=>update('invocation',i.invocation)}>查看原计量</button><Link to={'/work?'+new URLSearchParams({conversation:i.conversation})}>返回原会话</Link></td></tr>)}</tbody></table></div>:<p role="status">当前返回范围没有匹配的可读规划计量；这不表示没有调用或费用。</p>)}
 </section>
 {selected&&<section className="operations-content" aria-label="原规划计量详情"><h2>{selected.title}</h2><StatusBadge>{selected.receipt.settlement.status==='ESTIMATE_SETTLED'?'本地估算已结算':'原预留保留'}</StatusBadge>{selected.receipt.settlement.status==='ESTIMATE_SETTLED'?<><p>本地估算：{usd(BigInt(selected.receipt.settlement.estimate_microusd!))}</p><p>输入 {selected.receipt.settlement.input_tokens} Token · 输出 {selected.receipt.settlement.output_tokens} Token</p></>:<p>尚未取得可结算计量，原预留保持；不代表远端未处理或零费用。</p>}<p>供应商账单尚未核实；本地估算结算不代表业务结果通过。</p><details><summary>原记录标识</summary><p>调用：{selected.invocation}</p><p>预留：{selected.receipt.reservationId}</p></details><Link to={'/work?'+new URLSearchParams({conversation:selected.conversation})}>返回这次调用的原会话</Link></section>}
 {params.has('invocation')&&snapshot&&!selected&&<p role="status">所选原计量当前未读回，不展示旧缓存，也不会重新发起调用。</p>}
 </main>;
}
