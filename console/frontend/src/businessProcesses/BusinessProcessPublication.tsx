import {useEffect,useRef,useState} from 'react';
import {getWorkbenchSession,workbenchPrincipalKey} from '../api/digitalEmployees';
import {BusinessProcessRequestError,checkBusinessProcessEditorAccess,publishBusinessProcess,readBusinessProcessPublicationReceipt,type BusinessProcessContent,type BusinessProcessRecord,type BusinessProcessPublicationCommand,type BusinessProcessPublicationReceipt} from '../api/businessProcesses';

function publicationFailure(error:BusinessProcessRequestError){
 const messages:Record<string,string>={
  BUSINESS_PROCESS_REFERENCE_NOT_PUBLISHED:'关联的资料或数字人版本尚未发布。请先完成关联版本的发布，再发布业务定义。',
  BUSINESS_PROCESS_REFERENCE_VERSION_MISMATCH:'关联版本的内容依据不一致，请重新核对关联版本后再发布。',
  BUSINESS_PROCESS_REFERENCE_UNAVAILABLE:'关联的资料或数字人当前不可用，请核对关联状态后再发布。',
  BUSINESS_PROCESS_REFERENCE_NOT_FOUND:'当前无法读取关联的资料或数字人，请核对关联内容和访问范围。',
  BUSINESS_PROCESS_REFERENCE_ADAPTER_UNAVAILABLE:'关联内容尚未完成适配，暂不能发布此业务定义。',
 };
 return messages[error.code]??(error.status===409?'草稿版本已变化，请重新读取后核对。':error.status===422?'定义仍有缺项，请完善后再发布。':'当前无法发布，请核对账号和使用范围。');
}

export function BusinessProcessPublication({detail,onNavigate,onRefresh}:{detail:BusinessProcessRecord<BusinessProcessContent>;onNavigate:(revision:string)=>void;onRefresh:()=>void}){
 const [principal,setPrincipal]=useState(''),[allowed,setAllowed]=useState(false),[accessUnknown,setAccessUnknown]=useState(false);
 const [pending,setPending]=useState<BusinessProcessPublicationCommand|null>(null),[retry,setRetry]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const controller=useRef<AbortController|null>(null),storage=useRef(''),inFlight=useRef(false);
 useEffect(()=>{
  let active=true,sequence=0;const abort=new AbortController();controller.current=abort;
  const load=async()=>{const round=++sequence;setAllowed(false);setAccessUnknown(false);
   try{const session=await getWorkbenchSession(AbortSignal.any([abort.signal,AbortSignal.timeout(30_000)]));const identity=workbenchPrincipalKey(session);
    const key='business-process-publication:v1:'+JSON.stringify([identity,detail.objectId]);
    const saved=sessionStorage.getItem(key),command=saved?JSON.parse(saved) as BusinessProcessPublicationCommand:null;
    if(command&&(command.objectId!==detail.objectId||typeof command.commandId!=='string'||typeof command.revisionId!=='string'||typeof command.digest!=='string'||!Number.isInteger(command.expectedVersion)||command.expectedVersion<1))throw new Error('INVALID_LOCAL_PUBLICATION');
    if(active&&round===sequence){storage.current=key;setPrincipal(identity);setPending(command);setRetry(false)}
    await checkBusinessProcessEditorAccess('PROCESS',detail.objectId,'PUBLISH',identity,abort.signal);
    if(active&&round===sequence)setAllowed(true);
   }catch(cause){if(active&&round===sequence)setAccessUnknown(!(cause instanceof BusinessProcessRequestError&&(cause.status===403||cause.status===404)))}
  };
  const expire=()=>{active=false;abort.abort();setPrincipal('');setAllowed(false);setPending(null);setError('登录已失效，请重新登录后核实原提交。')};
  window.addEventListener('focus',load);window.addEventListener('workbench-session-expired',expire);void load();
  return()=>{active=false;abort.abort();window.removeEventListener('focus',load);window.removeEventListener('workbench-session-expired',expire)};
 },[detail.objectId]);
 const accepted=(value:BusinessProcessPublicationReceipt,command:BusinessProcessPublicationCommand)=>{
  if(value.objectId!==command.objectId||value.revisionId!==command.revisionId||value.digest!==command.digest||value.contentVersion!==command.expectedVersion||value.state!=='PUBLISHED'||value.executionAuthorized!==false||value.publicationVersion<1)throw new BusinessProcessRequestError('INVALID_RECEIPT',503,true);
  sessionStorage.removeItem(storage.current);setPending(null);setRetry(false);onRefresh();
 };
 const run=async(mode:'publish'|'reconcile'|'retry')=>{
  if(inFlight.current||!principal||!controller.current||controller.current.signal.aborted)return;
  if(mode!=='reconcile'&&!allowed)return;
  let command=pending;const signal=controller.current.signal;inFlight.current=true;setBusy(true);setError('');
  try{
   if(!command){if(mode!=='publish'||!detail.revisionId||!detail.digest)return;command={objectId:detail.objectId,revisionId:detail.revisionId,digest:detail.digest,expectedVersion:detail.aggregateVersion,commandId:'business-process-publish:'+crypto.randomUUID()};sessionStorage.setItem(storage.current,JSON.stringify(command));setPending(command)}
   const value=mode==='reconcile'?await readBusinessProcessPublicationReceipt(command.commandId,principal,signal):await publishBusinessProcess(command,principal,signal);
   if(!signal.aborted)accepted(value,command);
  }catch(cause){if(signal.aborted)return;
   if(mode==='reconcile'){setRetry(cause instanceof BusinessProcessRequestError&&cause.code==='BUSINESS_PROCESS_COMMAND_NOT_FOUND');setError('原发布尚未核实，已保留原提交。不会自动再次发布。')}
   else if(mode==='publish'&&cause instanceof BusinessProcessRequestError&&!cause.outcomeUnknown){sessionStorage.removeItem(storage.current);setPending(null);setError(publicationFailure(cause))}
   else setError('发布结果尚未核实，已保留原提交。请先核实，不要重复发布。');
  }finally{inFlight.current=false;if(!signal.aborted)setBusy(false)}
 };
 const state=detail.publicationState;if(!state)return null;
 const currentDraft=state.currentStateAvailable&&state.draft?.revisionId===detail.revisionId;
 const complete=detail.definitionValidation?.status==='COMPLETE';
 return <section className="bp-card" aria-label="发布与草稿"><h2>发布与草稿</h2>
  {state.currentStateAvailable?<><p>{state.published?'当前发布版已固定，后续编辑保存在修改草稿中。':'尚未发布，当前内容为登记草稿。'}发布只固定业务定义，不会启动工作或替换历史引用。</p>
   <div className="bp-actions">{state.published&&state.published.revisionId!==detail.revisionId&&<button onClick={()=>onNavigate(state.published!.revisionId)}>查看当前发布版</button>}{state.draft&&state.draft.revisionId!==detail.revisionId&&<button onClick={()=>onNavigate(state.draft!.revisionId)}>查看修改草稿</button>}</div></>:<p>当前发布版与修改草稿状态不可读，仍可查看已获授权的这个版本。</p>}
  {accessUnknown&&<p>发布资格暂未核实，请重新读取后核对。</p>}
  {error&&<p role="alert">{error}</p>}
  {pending&&principal?<div className="bp-notice"><p>有一份发布提交尚待核实。</p><button disabled={busy} onClick={()=>void run('reconcile')}>核实原发布</button>{retry&&allowed&&<button disabled={busy} onClick={()=>void run('retry')}>重试同一份发布</button>}</div>:currentDraft&&allowed&&<><button className="bp-primary" disabled={busy||!complete} onClick={()=>void run('publish')}>发布当前业务定义</button>{!complete&&<p>请先补齐定义校验列出的内容。</p>}</>}
  {busy&&<p role="status">正在发布或核实原提交…</p>}
 </section>;
}
