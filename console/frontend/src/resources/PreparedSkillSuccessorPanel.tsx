import {useEffect,useRef,useState} from 'react';
import {Link,useLocation,useSearchParams} from 'react-router-dom';
import {readWorkbenchSession,WorkbenchRequestError} from '../api/businessWorkspace';
import type {DirectoryItem} from '../api/resourceDirectory';
import {actor,decodeIntent,marker,preparedPath,request,safeContent,successorPath,verifyAdoption,verifyPrepared,verifyRead,type PreparedIntent,type PreparedReceipt,type PreparedSkillRead} from './preparedSkillHandoff';

export function PreparedSkillSuccessorPanel({item}:{item:DirectoryItem}){
 const location=useLocation(),[params]=useSearchParams(),identity=JSON.stringify([item.identity,item.revisionId,item.digest,location.pathname,location.search]);
 const [loaded,setLoaded]=useState<PreparedSkillRead|null>(null),[principal,setPrincipal]=useState(''),[intent,setIntent]=useState<PreparedIntent|null>(null),[prepared,setPrepared]=useState<PreparedReceipt|null>(null),[managed,setManaged]=useState(false),[editing,setEditing]=useState(false),[content,setContent]=useState(''),[reason,setReason]=useState(''),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const state=useRef({mounted:false,epoch:0,flight:false,abort:new AbortController()});
 const store=(i:PreparedIntent)=>{sessionStorage.setItem(marker(i.principal,item),JSON.stringify(i));setIntent(i)};
 useEffect(()=>{
  const current=state.current;current.mounted=true;
  const valid=(epoch:number)=>current.mounted&&epoch===current.epoch;
  const withdraw=()=>{current.epoch++;current.abort.abort();current.flight=false;setLoaded(null);setPrepared(null);setManaged(false);setPrincipal('');setEditing(false);setContent('');setReason('');setError('当前登录或页面范围已变化，请重新核对原操作。');setBusy(false)};
  async function load(){
   const epoch=++current.epoch;current.abort.abort();current.abort=new AbortController();const signal=current.abort.signal;current.flight=true;
   try{
    const session=await readWorkbenchSession(signal);if(!valid(epoch))return;
    const who=actor(session);setLoaded(null);setPrepared(null);setManaged(false);setBusy(true);setError('');setPrincipal(who);
    const raw=sessionStorage.getItem(marker(who,item)),previous=raw?decodeIntent(raw,who,item):null;setIntent(previous);
    const value=await request<PreparedSkillRead>(preparedPath(item),signal);verifyRead(value,item);if(actor(await readWorkbenchSession(signal))!==who)throw Error('当前登录身份已变化。');if(!valid(epoch))return;setLoaded(value);setContent(JSON.stringify(previous?.content??value.revision.content,null,2));setReason(previous?.reason??'');
    if(previous&&!previous.rejected){
     const saved=await request<PreparedReceipt>(successorPath(previous)+'/by-key/'+encodeURIComponent(previous.commandKey),signal);verifyPrepared(saved,previous);if(actor(await readWorkbenchSession(signal))!==who)throw Error('当前登录身份已变化。');if(!valid(epoch))return;setPrepared(saved);
     if(previous.managementKey&&!previous.managementRejected){const receipt=await request<unknown>('resource-management/skill/commands/'+encodeURIComponent(previous.managementKey),signal);await verifyAdoption(receipt,previous,saved,session,signal);if(valid(epoch))setManaged(true)}
    }
   }catch(e){if(valid(epoch)){setPrepared(null);setManaged(false);setError(e instanceof Error?e.message:'原后继操作尚未核实。')}}
   finally{if(valid(epoch)){current.flight=false;setBusy(false)}}
  }
  void load();window.addEventListener('focus',load);window.addEventListener('workbench-session-expired',withdraw);
  return()=>{current.mounted=false;current.epoch++;current.abort.abort();window.removeEventListener('focus',load);window.removeEventListener('workbench-session-expired',withdraw)};
 // The exact resource/location remounts this scope. Reading never prepares or adopts.
 // eslint-disable-next-line react-hooks/exhaustive-deps
 },[identity]);
 function guard(){const epoch=state.current.epoch;return()=>{if(!state.current.mounted||epoch!==state.current.epoch)throw Error('当前页面已变化，原操作记录保留。')}}
 async function session(assertCurrent:()=>void){assertCurrent();const s=await readWorkbenchSession(state.current.abort.signal);assertCurrent();if(actor(s)!==principal)throw Error('当前登录身份已变化，原操作记录保留。');return s}
 async function recover(){
  if(state.current.flight||busy||!intent)return;state.current.flight=true;setBusy(true);setError('');const valid=guard(),operationEpoch=state.current.epoch,isCurrent=()=>state.current.mounted&&state.current.epoch===operationEpoch;
  try{const s=await session(valid),receipt=await request<PreparedReceipt>(successorPath(intent)+'/by-key/'+encodeURIComponent(intent.commandKey),state.current.abort.signal);verifyPrepared(receipt,intent);await session(valid);valid();setPrepared(receipt);if(intent.managementKey&&!intent.managementRejected){const adoption=await request<unknown>('resource-management/skill/commands/'+encodeURIComponent(intent.managementKey),state.current.abort.signal);await verifyAdoption(adoption,intent,receipt,s,state.current.abort.signal);valid();setManaged(true)}}
  catch(e){if(isCurrent()){setManaged(false);setError(e instanceof Error?e.message:'原操作尚未读回，保留同一请求。')}}finally{if(isCurrent()){state.current.flight=false;setBusy(false)}}
 }
 async function prepare(){
  if(state.current.flight||busy||!loaded||!principal||(intent&&!intent.rejected))return;state.current.flight=true;setBusy(true);setError('');const valid=guard(),operationEpoch=state.current.epoch,isCurrent=()=>state.current.mounted&&state.current.epoch===operationEpoch;let submitted:PreparedIntent|null=null;
  try{
   const s=await session(valid),fresh=await request<PreparedSkillRead>(preparedPath(item),state.current.abort.signal);verifyRead(fresh,item);await session(valid);valid();
   if(fresh.successorPreparationEnabled!==true||fresh.publishedRevisionId!==item.revisionId||fresh.aggregateVersion!==loaded.aggregateVersion)throw Error('准备条件或原版本已变化，请重新读取后核对。');
   const value:unknown=JSON.parse(content);safeContent(value);if(!reason.trim()||reason.length>1000)throw Error('请填写本次准备后继的原因，且不超过1000字。');
   submitted={version:1,principal,identity:item.identity,revision:item.revisionId,digest:item.digest,commandKey:crypto.randomUUID(),expectedVersion:fresh.aggregateVersion,content:value,reason:reason.trim()};store(submitted);
   const receipt=await request<PreparedReceipt>(successorPath(submitted),state.current.abort.signal,{expectedVersion:submitted.expectedVersion,expectedPublishedDigest:submitted.digest,content:submitted.content,reason:submitted.reason,commandKey:submitted.commandKey},s.csrfToken);verifyPrepared(receipt,submitted);await session(valid);valid();setPrepared(receipt);setEditing(false);
  }catch(e){if(isCurrent()){if(submitted&&e instanceof WorkbenchRequestError&&[400,403,404,409,422].includes(e.status))store({...submitted,rejected:true});setPrepared(null);setManaged(false);setError(e instanceof Error?e.message:'原提交尚未核实，请读取原操作，不重复保存。')}}finally{if(isCurrent()){state.current.flight=false;setBusy(false)}}
 }
 async function adopt(){
  if(state.current.flight||busy||!intent||!prepared||managed)return;
  if(!intent.managementKey&&loaded?.successorPreparationEnabled!==true)return;
  if(intent.managementKey&&!intent.managementRejected)return recover();
  state.current.flight=true;setBusy(true);setError('');const valid=guard(),operationEpoch=state.current.epoch,isCurrent=()=>state.current.mounted&&state.current.epoch===operationEpoch;let submitted:PreparedIntent|null=null;
  try{const s=await session(valid);submitted={...intent,managementKey:crypto.randomUUID(),managementRejected:false};store(submitted);const value=await request<unknown>('resource-management/skill/commands',state.current.abort.signal,{action:'adopt-prepared',commandKey:submitted.managementKey,identity:submitted.identity,expectedVersion:prepared.aggregateVersion,preparedCommandKey:submitted.commandKey},s.csrfToken);await verifyAdoption(value,submitted,prepared,s,state.current.abort.signal);await session(valid);valid();setManaged(true)}
  catch(e){if(isCurrent()){if(submitted&&e instanceof WorkbenchRequestError&&[400,403,404,409,422].includes(e.status))store({...submitted,managementRejected:true});setManaged(false);setError(e instanceof Error?e.message:'维护接续尚未核实，请读取原操作。')}}finally{if(isCurrent()){state.current.flight=false;setBusy(false)}}
 }
 const continuation=new URLSearchParams({kind:'skill',managedResource:item.identity,resourceTab:'测试'}),conversation=params.get('returnConversation'),execution=params.get('fromExecution');if(conversation&&conversation.length<=200)continuation.set('returnConversation',conversation);if(execution&&/^[a-f0-9]{64}$/.test(execution))continuation.set('fromExecution',execution);
 const allowed=loaded?.successorPreparationEnabled===true&&loaded.publishedRevisionId===item.revisionId;
 return <section aria-label="原技能后继准备" className="rm-pending"><h2>原技能后继准备</h2><p>保留本版本和已有引用，另行准备同一技能的后继草稿；测试、发布和员工引用分别核对。</p>
 {busy&&<p role="status">正在核对原版本或原操作…</p>}
 {!busy&&!allowed&&!intent&&<p role="status">当前未开放此版本的后继准备，原版本仍可查看。</p>}
 {!intent&&allowed&&!editing&&<button disabled={busy} onClick={()=>setEditing(true)}>准备技能后继</button>}
 {((editing&&!prepared)||intent?.rejected)&&allowed&&<form className="rm-form" aria-label="准备原技能后继" onSubmit={e=>{e.preventDefault();void prepare()}}><label>后继配置<textarea aria-label="后继配置" value={content} onChange={e=>setContent(e.target.value)} rows={10} disabled={busy}/></label><label>准备原因<input aria-label="准备原因" value={reason} onChange={e=>setReason(e.target.value)} maxLength={1000} disabled={busy}/></label><p>配置不能包含明文凭据。保存只创建草稿，随后接续测试与发布。</p><button disabled={busy||!reason.trim()} type="submit">保存后继草稿</button></form>}
 {intent&&!intent.rejected&&!managed&&<button disabled={busy} onClick={()=>void recover()}>读取原后继操作</button>}
 {prepared&&!managed&&<><p role="status">后继草稿已保存，原版本保留。还需明确接续资源维护。</p>{(allowed||Boolean(intent?.managementKey&&!intent.managementRejected))&&<button disabled={busy} onClick={()=>void adopt()}>{intent?.managementKey&&!intent.managementRejected?'读取原维护接续':'接续测试与发布'}</button>}{!allowed&&!intent?.managementKey&&<p>当前未开放新的维护接续，可继续读取原操作。</p>}</>}
 {managed&&<><p role="status">已核对后继草稿和资源维护回执；尚未由本入口发布或执行。</p><Link to={'/skills?'+continuation}>进入后继测试与发布</Link></>}
 {error&&<details><summary>查看准备或恢复状态</summary><p>{error}</p><p>原操作和原版本保留；读取与刷新不会再次创建后继或接管维护。</p></details>}
 </section>;
}
