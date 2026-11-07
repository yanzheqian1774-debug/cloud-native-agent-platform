import {useEffect,useLayoutEffect,useRef,useState} from 'react';
import {Link} from 'react-router-dom';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';
import type {ExecutionView} from '../api/preparedExecution';
import {useAutomaticReadback} from '../journey/useAutomaticReadback';
import {inspectSupplement,readSupplement,submitSupplement,supplementPrincipal,verifySupplement,type SupplementPreparation,type SupplementSpec,type SupplementReceipt} from './salesSupplementRequests';

type Pending={spec:SupplementSpec;state:'UNKNOWN'|'REJECTED'|'SAVED'};
export function SalesSupplement({view,conversation}:{view:ExecutionView;conversation:string}){
 const [preparation,setPreparation]=useState<SupplementPreparation|null>(null),[saved,setSaved]=useState<SupplementReceipt|null>(null),[pending,setPending]=useState<Pending|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState(''),[principal,setPrincipal]=useState('');
 const flight=useRef(false),epoch=useRef(0),identity=JSON.stringify([conversation,view.digest,view.preparation.plan_id,view.preparation.plan_version,view.preparation.plan_digest]);
 const current=useRef(identity);
 useLayoutEffect(()=>{current.current=identity;return()=>{current.current=""}},[identity]);
 const storage=(actor:string)=>'sales-supplement.v1:'+JSON.stringify([actor,identity]);
 const id=view.preparation.plan_id;
 useEffect(()=>{const token=++epoch.current;let live=true;flight.current=true;
  readWorkbenchSession().then(async session=>{
   const actor=supplementPrincipal(session),raw=sessionStorage.getItem(storage(actor)),prior=raw?JSON.parse(raw) as Pending:null;
   if(!live||token!==epoch.current)return;
   setPrincipal(actor);setPending(prior);
   if(prior&&prior.state!=='REJECTED'){
    const value=await readSupplement(id,prior.spec.idempotency_key);
    if(!live||token!==epoch.current)return;
    if(supplementPrincipal(await readWorkbenchSession())!==actor)throw Error('登录身份已变化，请重新打开原工作。');
    if(!live||token!==epoch.current)return;
    verifySupplement(value,id,prior.spec);setSaved(value);setPending({...prior,state:'SAVED'});
   }else{
    const value=await inspectSupplement(view);
    if(supplementPrincipal(await readWorkbenchSession())!==actor)throw Error('登录身份已变化，请重新打开原工作。');
    if(live&&token===epoch.current)setPreparation(value);
   }
  }).catch(e=>{if(live&&token===epoch.current)setError(e instanceof Error?e.message:'原补交记录尚未核实。')}).finally(()=>{if(live&&token===epoch.current){flight.current=false;setBusy(false)}});
  return()=>{live=false};
 // Identity remounts the card; no business or recovery POST runs in this effect.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity]);
 async function session(){const s=await readWorkbenchSession();if(supplementPrincipal(s)!==principal)throw Error('登录身份已变化，请重新打开原工作。');return s}
 async function act(submit=false){
  if(flight.current||!principal)return;flight.current=true;setBusy(true);setError('');const context=current.current,token=epoch.current;
  const valid=()=>context===current.current&&token===epoch.current;
  try{
   const s=await session();if(!valid())return;
   if(pending&&pending.state!=='REJECTED'){
    const value=await readSupplement(id,pending.spec.idempotency_key);await session();if(!valid())return;verifySupplement(value,id,pending.spec);setSaved(value);setPending({...pending,state:'SAVED'});return;
   }
   const fresh=await inspectSupplement(view);await session();if(!valid())return;
   setPreparation(fresh);
   if(!submit||fresh.state!=='READY')return;
   if(preparation?.state!=='READY'||JSON.stringify(fresh.spec)!==JSON.stringify(preparation.spec))throw Error('准备内容已更新，请核对新的准备摘要后再提交。');
   const spec={...fresh.spec,idempotency_key:crypto.randomUUID()},marker:Pending={spec,state:'UNKNOWN'};
   // Durably mark before sending. Reload, uncertainty or a second click uses GET.
   sessionStorage.setItem(storage(principal),JSON.stringify(marker));setPending(marker);
   try{
    const value=await submitSupplement(id,spec,s.csrfToken);await session();if(!valid())return;verifySupplement(value,id,spec);
    const done:Pending={spec,state:'SAVED'};sessionStorage.setItem(storage(principal),JSON.stringify(done));setPending(done);setSaved(value);
   }catch(e){
    if(valid()&&e instanceof WorkbenchRequestError&&[400,403,404,409,422].includes(e.status)){
     const rejected:Pending={spec,state:'REJECTED'};sessionStorage.setItem(storage(principal),JSON.stringify(rejected));setPending(rejected);setPreparation(null);
    }else if(valid()){
     // An uncertain transport gets one automatic original-key read, never POST.
     try{
      const value=await readSupplement(id,spec.idempotency_key);await session();if(!valid())return;verifySupplement(value,id,spec);
      const done:Pending={spec,state:'SAVED'};sessionStorage.setItem(storage(principal),JSON.stringify(done));setPending(done);setSaved(value);return;
     }catch{/* Unknown remains an original-key read task; never mint a retry. */}
    }
    throw e;
   }
  }catch(e){if(valid()){setPreparation(null);setSaved(null);setError(e instanceof Error?e.message:'补交结果尚未核实。')}}
  finally{flight.current=false;if(valid())setBusy(false)}
 }
 useAutomaticReadback({identity,enabled:Boolean(principal)&&!busy&&!pending&&preparation?.state==='BLOCKED',interval:15000,read:async()=>{await act();return true}});
 const revision=saved?.proposal.revision??(preparation?.state==='SAVED'?preparation.revision:null),unknown=pending?.state==='UNKNOWN';
 return <section className="planning-card sales-supplement" aria-label="原销售目标补交"><span className="px-eyebrow">继续原销售工作</span><h3>补齐分维度毛利分析</h3><p>沿用原资料，补充区域、渠道、产品的毛利变化贡献及逐行依据。原方案和结果保留。</p>
 {!revision&&!unknown&&<><p>系统核对已保存的完成标准、分析能力和数字员工准备情况，无需填写内部编号。</p><button type="button" disabled={busy||!principal} onClick={()=>void act()}>核对补交准备</button></>}
 {busy&&<p role="status">正在核对原工作与补交记录…</p>}
 {preparation?.state==='BLOCKED'&&<div role="status"><h4>补交准备尚未完成</h4><ul>{preparation.gaps.map(g=><li key={g}>{g}</li>)}</ul><p>准备完成后可继续；当前原结果仍可查看。</p></div>}
 {preparation?.state==='READY'&&!unknown&&!revision&&<section aria-label="补交准备摘要"><h4>可提交补交方案核验</h4><p>已读取新标准和同一能力、员工的已发布后继版本。提交后由原服务核验来源、版本及权限；方案确认和执行准入分别办理。</p><button type="button" className="px-primary-button" disabled={busy} onClick={()=>void act(true)}>生成补交方案</button></section>}
 {unknown&&!revision&&<div role="status"><p>原提交结果尚未核实。保留同一请求，只读取原回执，不重复生成方案。</p><button type="button" disabled={busy||!principal} onClick={()=>void act()}>读取原补交记录</button></div>}
 {revision&&<section aria-label="已保存销售补交"><h4>补交方案已保存</h4><p>尚未由本入口启动执行。继续核对方案、准备状态及准入，结果沿原工作返回本会话。</p><Link className="journey-secondary" to={`/work/planning/${encodeURIComponent(id)}?revision=${revision}&returnConversation=${encodeURIComponent(conversation)}`}>核对补交方案并继续</Link></section>}
 {error&&<div role="alert"><p>本次补交尚未核实完成。请核对准备状态与当前权限；旧结果保留。</p><details><summary>查看核对信息</summary><p>{error}</p></details></div>}
 </section>;
}
